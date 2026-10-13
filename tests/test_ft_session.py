"""Offline lease/rotation/privacy tests. No real Keychain, dialogs or network."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import ft_session as s
from tools import ft_cloud_probe as c

TARGET = "a" * 64
DEVICE = "synthetic-device"
SELECTED = {"thing_name": DEVICE, "model_kind": "EXACT", "app_server": None}
FOUND = (1, 1, 0, 1, "EXACT", SELECTED)


def record():
    return {"schema_version": 1, "token": "SECRET_ACCESS", "refresh_token": "SECRET_REFRESH",
        "terminal_uuid": "synthetic-uuid", "issued_at": 1000., "hard_expires_at": 173800.,
        "last_seen": 1100., "target_digest": TARGET, "device_digest": hashlib.sha256(DEVICE.encode()).hexdigest(),
        "account_host": c.ACCOUNT_HOST, "revision": 1}


class Store:
    def __init__(self, value=None):
        self.value = copy.deepcopy(value)
        self.deleted = 0
        self.fail_save = False

    def load(self):
        return copy.deepcopy(self.value)

    def save(self, value):
        if self.fail_save:
            raise s.SessionError("STORE_DENIED")
        self.value = copy.deepcopy(value)

    def delete(self):
        self.value = None
        self.deleted += 1


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(record())
        self.now, self.elapsed = 1200., 10.
        self.manager = self.make_manager()
        self.discovery = patch.object(c, "_discover", return_value=FOUND).start()
        self.prompt = patch.object(c, "_native_prompt", side_effect=AssertionError("No dialog on reuse")).start()
        self.refresh = patch.object(c, "_refresh", return_value={"token": "NEW_ACCESS", "refresh_token": "NEW_REFRESH"}).start()
        self.addCleanup(patch.stopall)

    def make_manager(self):
        return s.SessionManager(self.store, wall=lambda: self.now, mono=lambda: self.elapsed,
                                lock=contextlib.nullcontext)

    def call(self, op="use"):
        return self.manager.command(op, None if op in {"status", "forget"} else TARGET)

    def test_reuse_new_manager_never_prompts(self):
        self.assertEqual(self.call()["session_state"], "REUSED")
        self.manager = self.make_manager()
        self.now += 120
        self.assertEqual(self.call()["session_state"], "REUSED")
        self.assertEqual(self.store.value["hard_expires_at"], 173800)
        self.prompt.assert_not_called()
        self.refresh.assert_not_called()

    def test_exact_expiry_no_network_and_delete(self):
        self.now = 173800
        self.assertEqual(self.call()["reason"], "EXPIRED")
        self.assertIsNone(self.store.value)
        self.discovery.assert_not_called()

    def test_before_expiry(self):
        self.now = 173799.9
        self.assertEqual(self.call()["status"], "SUCCESS")

    def test_sleep_counts_after_restart(self):
        self.now = 174000
        self.manager = self.make_manager()
        self.assertEqual(self.call()["reason"], "EXPIRED")

    def test_saved_clock_rollback(self):
        self.now = 1099
        self.assertEqual(self.call()["reason"], "CLOCK_ROLLBACK")
        self.discovery.assert_not_called()

    def test_in_process_monotonic_expiry(self):
        lease = s.Lease(record(), lambda: self.now, lambda: self.elapsed)
        self.elapsed += 172800
        with self.assertRaisesRegex(s.SessionError, "EXPIRED"):
            lease.check()

    def test_clock_rollback_between_calls(self):
        lease = s.Lease(record(), lambda: self.now, lambda: self.elapsed)
        self.now -= 1
        with self.assertRaisesRegex(s.SessionError, "CLOCK_ROLLBACK"):
            lease.check()

    def test_missing_session_no_dialog(self):
        self.store.value = None
        self.assertEqual(self.call()["reason"], "REAUTH_REQUIRED")
        self.prompt.assert_not_called()

    def test_schema_fields_and_types_fail_before_network(self):
        for key, value in [("token", "bad\nvalue"), ("refresh_token", {}), ("revision", True),
                           ("issued_at", float("nan")), ("hard_expires_at", 999999),
                           ("account_host", "untrusted.example"), ("target_digest", "b"*64),
                           ("schema_version", True), ("device_digest", "invalid")]:
            with self.subTest(key=key):
                self.store.value = record()
                self.store.value[key] = value
                self.assertEqual(self.call()["status"], "BLOCKED")
        self.store.value = dict(record(), password="DO_NOT_STORE")
        self.assertEqual(self.call()["reason"], "INVALID_SESSION")
        self.discovery.assert_not_called()

    def test_401_refresh_once_rotation_keeps_deadline(self):
        self.discovery.side_effect = [c.ProbeError("AUTH_FAILED", "AUTH_INVALID_HTTP401"), FOUND]
        report = self.call()
        self.assertEqual(report["session_state"], "REFRESHED")
        self.assertEqual(self.discovery.call_count, 2)
        self.refresh.assert_called_once()
        self.assertEqual(self.store.value["token"], "NEW_ACCESS")
        self.assertEqual(self.store.value["refresh_token"], "NEW_REFRESH")
        self.assertEqual(self.store.value["hard_expires_at"], 173800)

    def test_second_401_does_not_refresh_again(self):
        self.discovery.side_effect = c.ProbeError("AUTH_FAILED", "AUTH_INVALID_HTTP401")
        self.assertEqual(self.call()["reason"], "REAUTH_REQUIRED")
        self.refresh.assert_called_once()
        self.assertEqual(self.discovery.call_count, 2)
        self.assertIsNone(self.store.value)

    def test_transient_discovery_failure_keeps_session(self):
        for reason in ("DISCOVERY_FAILED", "TIMEOUT", "CONNECT_ERROR", "HTTP_ERROR", "AUTH_FAILED"):
            self.discovery.side_effect = c.ProbeError(reason)
            self.assertEqual(self.call()["reason"], reason)
            self.assertIsNotNone(self.store.value)
        self.refresh.assert_not_called()

    def test_refresh_timeout_retains_old_session(self):
        self.refresh.side_effect = c.ProbeError("TIMEOUT")
        self.assertEqual(self.call("refresh-check")["reason"], "TIMEOUT")
        self.assertEqual(self.store.value["token"], "SECRET_ACCESS")

    def test_refresh_rejected_401_forgets(self):
        self.refresh.side_effect = c.ProbeError("AUTH_FAILED", "AUTH_INVALID_HTTP401")
        self.assertEqual(self.call("refresh-check")["reason"], "REAUTH_REQUIRED")
        self.assertIsNone(self.store.value)

    def test_missing_refresh_requires_reauth_only_when_needed(self):
        self.store.value["refresh_token"] = None
        self.assertEqual(self.call()["status"], "SUCCESS")
        self.discovery.side_effect = c.ProbeError("AUTH_FAILED", "AUTH_INVALID_HTTP401")
        self.assertEqual(self.call()["reason"], "REAUTH_REQUIRED")
        self.refresh.assert_not_called()

    def test_expiry_during_refresh_never_persists_new_token(self):
        def refresh(*args):
            self.now = 173800
            return {"token": "NEW_ACCESS", "refresh_token": "NEW_REFRESH"}
        self.refresh.side_effect = refresh
        self.assertEqual(self.call("refresh-check")["reason"], "EXPIRED")
        self.discovery.assert_not_called()
        self.assertIsNone(self.store.value)

    def test_rotation_storage_failure_is_not_success(self):
        def refresh(*args):
            self.store.fail_save = True
            return {"token": "NEW_ACCESS", "refresh_token": "NEW_REFRESH"}
        self.refresh.side_effect = refresh
        self.assertEqual(self.call("refresh-check")["reason"], "STORE_DENIED")
        self.assertEqual(self.store.value["token"], "SECRET_ACCESS")

    def test_wrong_target_or_ambiguous_stops_callback(self):
        for found in [(2, 2, 0, 2, None, None), (1, 0, 0, 1, "OTHER", SELECTED),
                      (1, 1, 0, 1, "EXACT", dict(SELECTED, thing_name="changed"))]:
            self.discovery.return_value = found
            callback = unittest.mock.Mock()
            r = self.manager.command("use", TARGET, on_selected_camera=callback)
            self.assertEqual(r["reason"], "TARGET_MISMATCH")
            callback.assert_not_called()

    def test_status_forget_no_network(self):
        self.assertEqual(self.call("status")["session_state"], "ACTIVE")
        self.assertEqual(self.call("forget")["session_state"], "FORGOTTEN")
        self.discovery.assert_not_called()
        self.refresh.assert_not_called()

    def test_store_locked_and_exception_are_redacted(self):
        for exc in [s.SessionError("SESSION_LOCKED"), RuntimeError("SECRET_ACCESS")]:
            with patch.object(self.store, "load", side_effect=exc):
                report = self.call()
                self.assertEqual(report["status"], "BLOCKED")
                self.assertNotIn("SECRET", json.dumps(report))

    def test_expiry_cleanup_failure_is_explicit(self):
        self.now = 173800
        with patch.object(self.store, "delete", side_effect=s.SessionError("STORE_DENIED")):
            self.assertEqual(self.call(), {"status": "BLOCKED", "reason": "EXPIRED", "cleanup_pending": True})

    def test_revision_conflict(self):
        with self.assertRaisesRegex(s.SessionError, "REVISION_CONFLICT"):
            self.manager._save(record(), 88)

    def test_report_no_secrets_or_identifiers(self):
        report = json.dumps(self.call("refresh-check"))
        for secret in ("SECRET", "NEW_ACCESS", "NEW_REFRESH", TARGET, DEVICE, "synthetic-uuid"):
            self.assertNotIn(secret, report)

    def test_start_saves_once_after_unique_selection_and_no_password(self):
        self.store.value = None
        self.prompt.side_effect = [("email@example.invalid", None), ("PASSWORD_SECRET", None)]
        auth = {"token": "SECRET_ACCESS", "refresh_token": "SECRET_REFRESH", "terminal_uuid": "uuid",
                "account_host": c.ACCOUNT_HOST, "mfa": None}
        with patch.object(c, "_login", return_value=auth) as login, patch.object(c, "_load_pinned_der"):
            r = self.call("start")
        self.assertEqual(r["session_state"], "SESSION_CREATED")
        self.assertTrue(login.call_args.kwargs["refresh_token_needed"])
        self.assertEqual(set(self.store.value), s.FIELDS)
        self.assertNotIn("PASSWORD_SECRET", json.dumps(self.store.value))
        self.assertEqual(self.store.value["hard_expires_at"], self.now + 172800)

    def test_no_double_start(self):
        self.assertEqual(self.call("start")["reason"], "SESSION_BUSY")
        self.prompt.assert_not_called()

    def test_mfa_start_requests_and_persists_refresh_without_otp(self):
        self.store.value = None
        self.prompt.side_effect = [("mail@example.invalid", None), ("PASSWORD", None), ("OTP", None)]
        auth = {"token": None, "account_host": c.ACCOUNT_HOST, "terminal_uuid": "uuid",
                "mfa": {"process_id": "synthetic", "types": [c.MFA_EMAIL]}}
        with patch.object(c, "_login", return_value=auth), patch.object(c, "_send_mfa"), \
             patch.object(c, "_load_pinned_der"), patch.object(c, "_submit_mfa", return_value={
                 "token": "ACCESS", "refresh_token": "REFRESH"}) as submit:
            self.assertEqual(self.call("start")["status"], "SUCCESS")
        self.assertTrue(submit.call_args.kwargs["refresh_token_needed"])
        self.assertEqual(self.store.value["refresh_token"], "REFRESH")
        self.assertNotIn("OTP", json.dumps(self.store.value))
        self.assertNotIn("PASSWORD", json.dumps(self.store.value))

    def test_invalid_password_reasks_only_password_without_restarting_email(self):
        self.store.value = None
        self.prompt.side_effect = [("mail@example.invalid", None), (None, "INVALID_INPUT"), ("PASSWORD", None)]
        auth = {"token": "ACCESS", "refresh_token": "REFRESH", "terminal_uuid": "uuid",
                "account_host": c.ACCOUNT_HOST, "mfa": None}
        with patch.object(c, "_login", return_value=auth) as login, patch.object(c, "_load_pinned_der"):
            self.assertEqual(self.call("start")["status"], "SUCCESS")
        labels = [call.args[0] for call in self.prompt.call_args_list]
        self.assertEqual(sum("email" in label for label in labels), 1)
        self.assertEqual(sum("password" in label for label in labels), 2)
        login.assert_called_once()

    def test_bad_field_attempts_bounded_and_stage_redacted(self):
        self.store.value = None
        self.prompt.side_effect = [("mail@example.invalid", None)] + [(None, "INVALID_INPUT")] * 3
        with patch.object(c, "_login") as login, patch.object(c, "_load_pinned_der"):
            self.assertEqual(self.call("start"), {"status": "BLOCKED", "reason": "INVALID_INPUT", "stage": "PASSWORD_INPUT"})
        self.assertEqual(self.prompt.call_count, 4)
        login.assert_not_called()

    def test_invalid_field_retries_share_one_deadline(self):
        def prompt(*args, **kwargs):
            self.elapsed += 301
            return None, "INVALID_INPUT"
        self.prompt.side_effect = prompt
        with self.assertRaisesRegex(s.SessionError, "TIMEOUT"):
            self.manager._input("password", "PASSWORD_INPUT")
        self.prompt.assert_called_once()

    def test_session_guard_stops_each_device_budget_check(self):
        from tools.ft_sd_probe import _DeviceBudget
        guard = unittest.mock.Mock(side_effect=s.SessionError("EXPIRED"))
        budget = _DeviceBudget(session_guard=guard)
        with self.assertRaisesRegex(s.SessionError, "EXPIRED"):
            budget.check_time()
        guard.assert_called_once()
        self.assertEqual(budget.requests, 0)

    def test_sd_command_does_not_prompt_and_passes_live_deadline_guard(self):
        with patch("tools.ft_sd_probe.probe_selected_device", return_value={"status": "SUCCESS"}) as sd:
            self.assertEqual(self.call("sd-check")["status"], "SUCCESS")
            self.now = 173800
            with self.assertRaisesRegex(s.SessionError, "EXPIRED"):
                sd.call_args.kwargs["session_guard"]()
        self.prompt.assert_not_called()

    def test_media_hold_blocks_before_keychain_and_network(self):
        with patch.object(self.store, "load") as load:
            self.assertEqual(self.call("media-check")["reason"], "MEDIA_TRIAL_NOT_ENABLED")
            load.assert_not_called()
        self.discovery.assert_not_called()
        self.prompt.assert_not_called()

    def test_fixed_check_preserves_lease_and_propagates_blocked(self):
        with patch('tools.ft_sd_probe.probe_fixed_metadata', return_value={'status':'BLOCKED','reason':'MALFORMED_RESPONSE'}) as fixed:
            result=self.call('fixed-check')
            self.assertEqual(result['reason'],'SD_PROBE_BLOCKED')
            self.now=173800
            with self.assertRaises(s.SessionError): fixed.call_args.kwargs['session_guard']()
        self.prompt.assert_not_called()

    def test_media_session_guard_and_blocked_propagation(self):
        with patch("tools.ft_media_probe.LIVE_TRIAL_ENABLED", True), patch("tools.ft_media_probe.sample_selected_device", return_value={"status":"BLOCKED", "reason":"QUOTA"}) as sample:
            result = self.call("media-check")
            self.assertEqual(result["reason"], "MEDIA_PROBE_BLOCKED")
            self.now = 173800
            with self.assertRaises(s.SessionError):
                sample.call_args.kwargs["session_guard"]()
        self.prompt.assert_not_called()

    def test_json_duplicate_keys_and_nan_rejected(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(s.SessionError):
                s._json(raw)

    def test_real_file_lock_blocks_other_holder(self):
        with tempfile.TemporaryDirectory() as d, patch.object(s, "APP_DIR", Path(d).resolve()):
            with s.session_lock():
                with self.assertRaisesRegex(s.SessionError, "SESSION_BUSY"):
                    with s.session_lock():
                        pass


class RefreshTransportTests(unittest.TestCase):
    def test_refresh_exact_body_and_fixed_host(self):
        response = json.dumps({"error_code": 0, "result": {"token": "new", "refreshToken": "rotated"}}).encode()
        with patch.object(c, "_request", return_value=(200, response)) as request:
            self.assertEqual(c._refresh(c._Budget(), "refresh", "uuid")["refresh_token"], "rotated")
        args = request.call_args.args
        self.assertEqual(args[1:4], (c.ACCOUNT_HOST, "POST", "/"))
        c._validate_refresh_body(args[5], args[4])
        self.assertEqual(json.loads(args[5])["params"]["refreshToken"], "refresh")

    def test_refresh_body_guard_precedes_connection(self):
        bad = [b'{}', b'{"method":"reboot","params":{}}', b'{"method":"refreshToken","method":"refreshToken","params":{}}']
        with patch.object(c, "_open_connection") as conn:
            for body in bad:
                with self.assertRaises(c.ProbeError):
                    c._request(c._Budget(), c.ACCOUNT_HOST, "POST", "/", {}, body)
        conn.assert_not_called()

    def test_403_429_5xx_never_mark_auth_invalid(self):
        for code in (403, 429, 500, 503):
            with patch.object(c, "_request", return_value=(code, b'{}')):
                with self.assertRaises(c.ProbeError) as error:
                    c._discover(c._Budget(), "token", "uuid", TARGET)
                self.assertIsNone(error.exception.detail)
                with self.assertRaises(c.ProbeError) as error:
                    c._refresh(c._Budget(), "refresh", "uuid")
                self.assertIsNone(error.exception.detail)


if __name__ == "__main__":
    unittest.main()
