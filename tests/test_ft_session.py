"""Offline vendor lifetime/rotation/privacy tests. No real Keychain or network."""
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
    return {"schema_version": 3, "token": "SECRET_ACCESS", "refresh_token": "SECRET_REFRESH",
        "terminal_uuid": "synthetic-uuid", "issued_at": 1000.,
        "observation_started_at": 1000., "refresh_count": 0, "last_refresh_at": None,
        "last_verified_at": 1100.,
        "last_seen": 1100., "target_digest": TARGET, "device_digest": hashlib.sha256(DEVICE.encode()).hexdigest(),
        "account_host": c.ACCOUNT_HOST, "revision": 1}


def legacy_record(days=2):
    value = {k: v for k, v in record().items() if k in s.FIELDS}
    value.update(schema_version=1 if days == 2 else 2, hard_expires_at=1000+days*86400)
    if days != 2:
        value['lease_seconds'] = days*86400
    return value


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
        self.assertNotIn('hard_expires_at', self.store.value)
        self.prompt.assert_not_called()
        self.refresh.assert_not_called()

    def test_reuse_and_rotation_beyond_two_seven_thirty_days_across_restarts(self):
        for day in (2, 7, 30, 61):
            self.now = 1000 + day*86400
            self.manager = self.make_manager()
            self.discovery.side_effect = [c.ProbeError('AUTH_FAILED', 'AUTH_INVALID_HTTP401'), FOUND]
            result = self.call()
            self.assertEqual(result['status'], 'SUCCESS')
            self.assertEqual(result['local_expiry_policy'], 'VENDOR_MANAGED')
            self.assertIsNone(result['expires_at_utc'])
            self.assertEqual(result['session_age_seconds'], day*86400)
            self.assertEqual(self.store.value['issued_at'], 1000)
            self.assertNotIn('hard_expires_at', self.store.value)
        self.assertEqual(self.refresh.call_count, 4)
        self.assertEqual(result['observed_refresh_count'], 4)
        self.prompt.assert_not_called()

    def test_legacy_migration_past_each_old_local_cap_preserves_credentials(self):
        for day in (2, 7, 30):
            with self.subTest(day=day):
                self.store.value = legacy_record(day)
                self.now = 1000+40*86400
                self.manager = self.make_manager()
                result = self.call('status')
                self.assertEqual(result['status'], 'SUCCESS')
                self.assertEqual(self.store.value['schema_version'], 3)
                self.assertEqual(self.store.value['issued_at'], 1000)
                self.assertEqual(self.store.value['token'], 'SECRET_ACCESS')
                self.assertEqual(self.store.value['refresh_token'], 'SECRET_REFRESH')
                self.assertEqual(self.store.value['observation_started_at'], self.now)
                self.assertIsNone(result['last_verified_at_utc'])
                self.assertEqual(result['observed_refresh_count'], 0)
        self.discovery.assert_not_called(); self.refresh.assert_not_called(); self.prompt.assert_not_called()

    def test_retention_commands_cannot_reintroduce_local_caps(self):
        for command in ('retain-7', 'retain-30'):
            self.assertEqual(self.manager.command(command, TARGET)['reason'], 'INVALID_INPUT')
        self.assertEqual(self.store.value, record())
        self.discovery.assert_not_called(); self.refresh.assert_not_called()

    def test_vendor_schema_strict_metadata_and_no_deadline_or_password_fields(self):
        invalids = [('refresh_count', True), ('refresh_count', -1), ('refresh_count', 1.0),
                    ('refresh_count', 1), ('observation_started_at', float('inf')),
                    ('observation_started_at', 999), ('last_refresh_at', 1100),
                    ('last_verified_at', 1200), ('last_verified_at', float('nan'))]
        for key, value in invalids:
            bad = dict(record(), **{key: value})
            with self.subTest(key=key, value=value), self.assertRaises(s.SessionError):
                s.validate(bad)
        for key in ('password', 'hard_expires_at', 'lease_seconds'):
            with self.assertRaises(s.SessionError): s.validate(dict(record(), **{key: 172800}))

    def test_legacy_migration_write_failure_preserves_old_record(self):
        original = legacy_record()
        self.store.value = copy.deepcopy(original); self.store.fail_save = True
        self.now = 1000+40*86400
        self.assertEqual(self.call()['reason'], 'STORE_DENIED')
        self.assertEqual(self.store.value, original)
        self.discovery.assert_not_called()

    def test_legacy_schema_validation_precedes_migration_or_network(self):
        for days in (2, 7, 30):
            for key, value in [('hard_expires_at', float('nan')), ('revision', True),
                               ('account_host', 'untrusted.invalid'), ('password', 'DO_NOT_STORE')]:
                with self.subTest(days=days, key=key):
                    original = dict(legacy_record(days), **{key: value})
                    self.store.value = copy.deepcopy(original)
                    self.assertEqual(self.call()['reason'], 'INVALID_SESSION')
                    self.assertEqual(self.store.value['schema_version'], original['schema_version'])
        self.discovery.assert_not_called(); self.refresh.assert_not_called()

    def test_removed_retention_cli_rejected_before_reading_target_or_keychain(self):
        with patch.object(s, 'load_target', side_effect=AssertionError('No target read')), \
             patch.object(s, 'KeychainStore', side_effect=AssertionError('No store access')):
            for op in ('retain-7', 'retain-30'):
                out = io.StringIO()
                with contextlib.redirect_stdout(out): self.assertEqual(s.main([op]), 2)
                self.assertEqual(json.loads(out.getvalue())['reason'], 'INVALID_INPUT')

    def test_guarded_callback_gets_lease_check_without_changing_old_callback_api(self):
        called=[]
        def callback(token,terminal,selected,guard):
            guard();called.append(True);return {'status':'SAFE_CALLBACK'}
        report=self.manager.command('use',TARGET,on_selected_camera=callback,callback_with_guard=True)
        self.assertEqual(report['callback']['status'],'SAFE_CALLBACK');self.assertEqual(called,[True])
        self.assertNotIn('SECRET',json.dumps(report))

    def test_guarded_callback_allows_old_deadlines_but_rejects_nonboolean_option(self):
        def callback(token,terminal,selected,guard):
            self.now=1000+40*86400;guard();return {'status':'SUCCESS'}
        report=self.manager.command('use',TARGET,on_selected_camera=callback,callback_with_guard=True)
        self.assertEqual(report['status'],'SUCCESS')
        self.assertEqual(self.manager.command('use',TARGET,callback_with_guard=1)['reason'],'INVALID_INPUT')

    def test_old_exact_expiry_does_not_delete_tokens(self):
        self.now = 173800
        self.assertEqual(self.call()['status'], 'SUCCESS')
        self.assertIsNotNone(self.store.value)
        self.assertEqual(self.store.deleted, 0)

    def test_before_expiry(self):
        self.now = 173799.9
        self.assertEqual(self.call()["status"], "SUCCESS")

    def test_sleep_counts_after_restart(self):
        self.now = 174000
        self.manager = self.make_manager()
        self.assertEqual(self.call()["status"], "SUCCESS")

    def test_saved_clock_rollback(self):
        self.now = 1099
        self.assertEqual(self.call()["reason"], "CLOCK_ROLLBACK")
        self.discovery.assert_not_called()

    def test_monotonic_elapsed_has_no_local_expiry_and_rejects_rollback(self):
        lease = s.Lease(record(), lambda: self.now, lambda: self.elapsed)
        self.elapsed += 40*86400
        lease.check()
        self.elapsed -= 1
        with self.assertRaisesRegex(s.SessionError, 'CLOCK_ROLLBACK'): lease.check()

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

    def test_401_refresh_once_rotation_preserves_auth_age_and_records_observation(self):
        self.discovery.side_effect = [c.ProbeError("AUTH_FAILED", "AUTH_INVALID_HTTP401"), FOUND]
        report = self.call()
        self.assertEqual(report["session_state"], "REFRESHED")
        self.assertEqual(self.discovery.call_count, 2)
        self.refresh.assert_called_once()
        self.assertEqual(self.store.value["token"], "NEW_ACCESS")
        self.assertEqual(self.store.value["refresh_token"], "NEW_REFRESH")
        self.assertEqual(self.store.value['issued_at'], 1000)
        self.assertEqual(self.store.value['last_refresh_at'], self.now)
        self.assertEqual(report['observed_refresh_count'], 1)

    def test_second_401_does_not_refresh_again(self):
        self.discovery.side_effect = c.ProbeError("AUTH_FAILED", "AUTH_INVALID_HTTP401")
        report = self.call()
        self.assertEqual(report["reason"], "REAUTH_REQUIRED")
        self.assertEqual(report['reauth_cause'], 'ACCESS_REJECTED_AFTER_REFRESH')
        self.assertEqual(report['observation']['vendor_lifetime_status'], 'NOT_ESTABLISHED')
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
        result = self.call('refresh-check')
        self.assertEqual(result['reason'], 'TIMEOUT')
        self.assertNotIn('reauth_cause', result)
        self.assertEqual(result['observation']['vendor_lifetime_status'], 'NOT_ESTABLISHED')
        self.assertEqual(self.store.value['last_verified_at'], 1100)
        self.assertEqual(self.store.value["token"], "SECRET_ACCESS")

    def test_rejection_observation_bounds_last_vendor_success_and_redacts_identifiers(self):
        self.now = 1000+7*86400
        success = self.call()
        self.now = 1000+31*86400
        self.refresh.side_effect = c.ProbeError('AUTH_FAILED', 'AUTH_INVALID_HTTP401')
        failure = self.call('refresh-check')
        observation = failure['observation']
        self.assertEqual(observation['last_verified_at_utc'], success['last_verified_at_utc'])
        self.assertEqual(observation['session_age_seconds'], 31*86400)
        self.assertIsNone(observation['expires_at_utc'])
        for secret in ('SECRET', 'NEW_ACCESS', 'NEW_REFRESH', TARGET, DEVICE, 'synthetic-uuid'):
            self.assertNotIn(secret, json.dumps(failure))

    def test_legacy_migration_does_not_claim_vendor_acceptance(self):
        self.store.value = legacy_record()
        self.now = 1000+40*86400
        self.discovery.side_effect = c.ProbeError('AUTH_FAILED', 'AUTH_INVALID_HTTP401')
        self.refresh.side_effect = c.ProbeError('AUTH_FAILED', 'AUTH_INVALID_HTTP401')
        result = self.call()
        self.assertEqual(result['reason'], 'REAUTH_REQUIRED')
        self.assertIsNone(result['observation']['last_verified_at_utc'])
        self.assertEqual(result['observation']['observed_refresh_count'], 0)
        self.assertIsNone(self.store.value)

    def test_refresh_rejected_401_forgets(self):
        self.now = 1000+31*86400
        self.refresh.side_effect = c.ProbeError("AUTH_FAILED", "AUTH_INVALID_HTTP401")
        result = self.call('refresh-check')
        self.assertEqual(result['reason'], 'REAUTH_REQUIRED')
        self.assertEqual(result['reauth_cause'], 'REFRESH_REJECTED')
        self.assertEqual(result['observation']['session_age_seconds'], 31*86400)
        self.assertEqual(result['observation']['vendor_lifetime_status'], 'REFRESH_REJECTED')
        self.assertIsNone(self.store.value)
        self.prompt.assert_not_called()

    def test_missing_refresh_requires_reauth_only_when_needed(self):
        self.store.value["refresh_token"] = None
        self.assertEqual(self.call()["status"], "SUCCESS")
        self.discovery.side_effect = c.ProbeError("AUTH_FAILED", "AUTH_INVALID_HTTP401")
        result = self.call()
        self.assertEqual(result["reason"], "REAUTH_REQUIRED")
        self.assertEqual(result['reauth_cause'], 'NO_REFRESH_TOKEN')
        self.assertEqual(result['observation']['vendor_lifetime_status'], 'NOT_ESTABLISHED')
        self.refresh.assert_not_called()

    def test_refresh_crossing_old_deadline_persists_rotated_token(self):
        def refresh(*args):
            self.now = 173800
            return {"token": "NEW_ACCESS", "refresh_token": "NEW_REFRESH"}
        self.refresh.side_effect = refresh
        self.assertEqual(self.call("refresh-check")['status'], 'SUCCESS')
        self.assertEqual(self.store.value['token'], 'NEW_ACCESS')
        self.assertEqual(self.store.value['issued_at'], 1000)

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
        old_verified = self.store.value['last_verified_at']
        result = self.call('status')
        self.assertEqual(result['session_state'], 'ACTIVE')
        self.assertEqual(result['vendor_lifetime_status'], 'NOT_ESTABLISHED')
        self.assertEqual(self.store.value['last_verified_at'], old_verified)
        self.assertEqual(self.call("forget")["session_state"], "FORGOTTEN")
        self.discovery.assert_not_called()
        self.refresh.assert_not_called()

    def test_store_locked_and_exception_are_redacted(self):
        for exc in [s.SessionError("SESSION_LOCKED"), RuntimeError("SECRET_ACCESS")]:
            with patch.object(self.store, "load", side_effect=exc):
                report = self.call()
                self.assertEqual(report["status"], "BLOCKED")
                self.assertNotIn("SECRET", json.dumps(report))

    def test_vendor_rejection_cleanup_failure_does_not_claim_success(self):
        self.refresh.side_effect = c.ProbeError('AUTH_FAILED', 'AUTH_INVALID_HTTP401')
        with patch.object(self.store, "delete", side_effect=s.SessionError("STORE_DENIED")):
            result = self.call('refresh-check')
        self.assertEqual(result['reason'], 'STORE_DENIED')
        self.assertEqual(result['reauth_cause'], 'REFRESH_REJECTED')
        self.assertIsNotNone(self.store.value)

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
        self.assertEqual(set(self.store.value), s.VENDOR_FIELDS)
        self.assertNotIn("PASSWORD_SECRET", json.dumps(self.store.value))
        self.assertEqual(self.store.value['schema_version'], 3)
        self.assertIsNone(r['expires_at_utc'])
        self.assertNotIn('48-hour', self.prompt.call_args_list[0].args[0])

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
            self.now = 1099
            with self.assertRaisesRegex(s.SessionError, "CLOCK_ROLLBACK"):
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
            self.now=1099
            with self.assertRaises(s.SessionError): fixed.call_args.kwargs['session_guard']()
        self.prompt.assert_not_called()

    def test_media_session_guard_and_blocked_propagation(self):
        with patch("tools.ft_media_probe.LIVE_TRIAL_ENABLED", True), patch("tools.ft_media_probe.sample_selected_device", return_value={"status":"BLOCKED", "reason":"QUOTA"}) as sample:
            result = self.call("media-check")
            self.assertEqual(result["reason"], "MEDIA_PROBE_BLOCKED")
            self.now = 1099
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
