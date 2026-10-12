"""Tests for tools/ft_cloud_probe.py.

Every network, dialog, clock, and uuid dependency here is a synthetic fake
or a monkeypatched stdlib call; nothing in this file opens a real socket,
spawns a real osascript dialog, or contacts tplinkcloud.com. Run from the
repository root:
python3 -m unittest discover -s tests -t . -v
"""
import base64
import contextlib
import hashlib
import hmac
import http.client
import io
import json
import socket
import ssl
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

from tools import ft_cloud_probe as probe


def run_cli(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = probe.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue()


class TripwireHTTPSConnection:
    """Fails the test if anything tries to open a real HTTPS connection."""

    def __init__(self, *args, **kwargs):
        raise AssertionError("no real network access is permitted in ft_cloud_probe tests")


class TripwireSubprocessRun:
    def __call__(self, *args, **kwargs):
        raise AssertionError("no real subprocess/dialog is permitted in this test")


class FakeResponse:
    def __init__(self, status, body=b""):
        self.status = status
        self._body = body
        self._offset = 0

    def read(self, n=-1):
        if self._offset >= len(self._body):
            return b""
        if n is None or n < 0:
            chunk = self._body[self._offset:]
        else:
            chunk = self._body[self._offset:self._offset + n]
        self._offset += len(chunk)
        return chunk


def make_fake_connection_class(script, connections=None):
    """script: list popped once per request (getresponse) or connect call.

    Each entry is either an Exception instance to raise, or a (status, body)
    tuple returned as a FakeResponse. `connections` (if given) collects every
    constructed fake connection so a test can assert on close()/requests.
    """

    class FakeConnection:
        def __init__(self, host, port, context=None, timeout=None):
            self.host = host
            self.port = port
            self.context = context
            self.timeout = timeout
            self.closed = False
            self.sent = []
            if connections is not None:
                connections.append(self)

        def connect(self):
            action = script.pop(0)
            if isinstance(action, Exception):
                raise action

        def request(self, method, path, body=None, headers=None):
            self.sent.append((method, path, body, headers))

        def getresponse(self):
            action = script.pop(0)
            if isinstance(action, Exception):
                raise action
            status, body = action
            return FakeResponse(status, body)

        def close(self):
            self.closed = True

    return FakeConnection


def patch_connection(script, connections=None):
    cls = make_fake_connection_class(script, connections)
    return mock.patch.object(http.client, "HTTPSConnection", cls)


def patch_dialog(answers):
    """answers: list of (returncode, stdout) popped in call order."""
    state = {"answers": list(answers)}

    def fake_run(args, capture_output, text, timeout):
        if not state["answers"]:
            raise AssertionError("dialog called more times than scripted")
        returncode, stdout = state["answers"].pop(0)
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")

    return mock.patch.object(subprocess, "run", side_effect=fake_run)


def patch_uuid_sequence(values):
    it = iter(values)

    class _FakeUUID:
        def __init__(self, hexvalue):
            self.hex = hexvalue

    return mock.patch.object(uuid, "uuid4", side_effect=lambda: _FakeUUID(next(it)))


LOGIN_OK_BODY = json.dumps({"errorCode": 0, "result": {"token": "tok-1"}}).encode()
MFA_REQUIRED_BODY = json.dumps(
    {"errorCode": -20677, "result": {"MFAProcessId": "proc-1", "supportedMFATypes": [2]}}
).encode()
SEND_MFA_OK_BODY = json.dumps({"error_code": 0}).encode()
SUBMIT_MFA_OK_BODY = json.dumps({"errorCode": 0, "result": {"token": "tok-mfa"}}).encode()


def discovery_body(cameras):
    return json.dumps({"data": cameras}).encode()


ONE_C545D = [{"deviceType": "SMART.IPCAMERA", "model": "C545D", "thingName": "cam-1"}]
TWO_C545D = [
    {"deviceType": "SMART.IPCAMERA", "model": "C545D", "thingName": "cam-1"},
    {"deviceType": "SMART.IPCAMERA", "model": "c545d", "thingName": "cam-2"},
]
ZERO_C545D = [{"deviceType": "SMART.IPCAMERA", "model": "C210", "thingName": "cam-3"}]


class SigningVectorTests(unittest.TestCase):
    def test_sign_login_matches_hand_computed_vector(self):
        path = "/api/v2/account/login"
        body = b'{"a":1}'
        nonce = "FIXEDNONCE"
        content_md5, x_auth = probe._sign_login(path, body, nonce)

        expected_md5 = base64.b64encode(hashlib.md5(body).digest()).decode()
        sign_str = f"{expected_md5}\n9999999999\n{nonce}\n{path}"
        expected_sig = hmac.new(
            probe._ALT_SECRET_KEY.encode(), sign_str.encode(), hashlib.sha1
        ).hexdigest()

        self.assertEqual(content_md5, expected_md5)
        self.assertIn(f"Nonce={nonce}", x_auth)
        self.assertIn(f"Signature={expected_sig}", x_auth)
        self.assertIn(f"AccessKey={probe._ALT_ACCESS_KEY}", x_auth)
        self.assertIn("Timestamp=9999999999", x_auth)

    def test_signed_headers_vary_nonce_per_call(self):
        body = b"{}"
        h1 = probe._signed_headers("/p", body)
        h2 = probe._signed_headers("/p", body)
        self.assertNotEqual(h1["X-Authorization"], h2["X-Authorization"])


class CheckCommandOfflineTests(unittest.TestCase):
    def test_check_never_touches_network_or_dialog(self):
        with mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection), \
                mock.patch.object(subprocess, "run", TripwireSubprocessRun()):
            report = probe.check_command()
        self.assertEqual(report["status"], "AUTH_INPUT_REQUIRED")
        self.assertEqual(report["live_auth"], "NOT_TESTED")
        self.assertEqual(report["sd_download"], "NOT_IMPLEMENTED")
        self.assertEqual(report["ca_pin"], "OK")

    def test_check_reports_mismatch_without_raising(self):
        with mock.patch.object(probe, "CA_PATH", Path("/nonexistent/ft_cloud_probe_test.pem")):
            report = probe.check_command()
        self.assertEqual(report["ca_pin"], "MISMATCH")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "CA_PIN_MISMATCH")


class CaPinTests(unittest.TestCase):
    def test_wrong_ca_is_rejected(self):
        tampered = (
            "-----BEGIN CERTIFICATE-----\n"
            + base64.b64encode(b"not the real certificate bytes").decode()
            + "\n-----END CERTIFICATE-----\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as handle:
            handle.write(tampered)
            tmp_path = handle.name
        try:
            with mock.patch.object(probe, "CA_PATH", Path(tmp_path)):
                with self.assertRaises(probe.ProbeError) as ctx:
                    probe._load_pinned_der()
                self.assertEqual(ctx.exception.code, "CA_PIN_MISMATCH")
        finally:
            Path(tmp_path).unlink()

    def test_real_bundled_ca_matches_pin(self):
        der = probe._load_pinned_der()
        self.assertEqual(hashlib.sha256(der).hexdigest(), probe.CA_DER_SHA256)

    def test_context_never_disables_verification(self):
        context = probe._pinned_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_appended_unpinned_root_is_never_loaded(self):
        real_text = probe.CA_PATH.read_text(encoding="ascii")
        extra_root = (
            "-----BEGIN CERTIFICATE-----\n"
            + base64.b64encode(b"a totally different, unpinned root").decode()
            + "\n-----END CERTIFICATE-----\n"
        )
        tampered = real_text + extra_root
        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as handle:
            handle.write(tampered)
            tmp_path = handle.name
        try:
            with mock.patch.object(probe, "CA_PATH", Path(tmp_path)):
                with self.assertRaises(probe.ProbeError) as ctx:
                    probe._load_pinned_der()
                self.assertEqual(ctx.exception.code, "CA_PIN_MISMATCH")
                # The strict fullmatch rejects the file outright, so
                # _pinned_context never gets far enough to trust anything
                # from it, appended root included.
                with self.assertRaises(probe.ProbeError):
                    probe._pinned_context()
        finally:
            Path(tmp_path).unlink()


class RegionOriginTests(unittest.TestCase):
    def test_accepts_exact_listed_https_origin(self):
        for host in probe.HOSTS:
            self.assertEqual(probe._validate_region_origin(f"https://{host}"), host)
            self.assertEqual(probe._validate_region_origin(f"https://{host}/"), host)

    def test_rejects_unlisted_host_without_guessing(self):
        self.assertIsNone(probe._validate_region_origin("https://evil.example.com"))
        self.assertIsNone(probe._validate_region_origin("https://aps2-app-server.iot.i.tplinkcloud.com"))

    def test_rejects_non_https_creds_query_fragment_port_path(self):
        host = probe.HOSTS[0]
        bad = [
            f"http://{host}",
            f"https://user:pass@{host}",
            f"https://{host}?x=1",
            f"https://{host}#frag",
            f"https://{host}:8443",
            f"https://{host}/some/path",
            "not-a-url",
            "",
            None,
        ]
        for url in bad:
            self.assertIsNone(probe._validate_region_origin(url), url)

    def test_rejects_whitespace_and_control_characters(self):
        host = probe.HOSTS[0]
        bad = [
            f"https://{host}\n",
            f"https://{host} ",
            f" https://{host}",
            f"https://{host}\t",
            "https://" + host[:3] + "\x00" + host[3:],
            "https://" + host[:3] + "\x7f" + host[3:],
        ]
        for url in bad:
            self.assertIsNone(probe._validate_region_origin(url), url)


class BoundedTransportTests(unittest.TestCase):
    def test_http_redirect_is_rejected_not_followed(self):
        script = [(302, b"")]
        connections = []
        budget = probe._Budget()
        with patch_connection(script, connections):
            with self.assertRaises(probe.ProbeError) as ctx:
                probe._request(budget, probe.DISCOVERY_HOST, "GET", "/v2/things", {}, None)
        self.assertEqual(ctx.exception.code, "HTTP_ERROR")
        self.assertTrue(connections[0].closed)

    def test_connection_is_closed_even_on_failure(self):
        script = [socket.timeout()]
        connections = []
        budget = probe._Budget()
        with patch_connection(script, connections):
            with self.assertRaises(probe.ProbeError) as ctx:
                probe._request(budget, probe.DISCOVERY_HOST, "GET", "/v2/things", {}, None)
        self.assertEqual(ctx.exception.code, "TIMEOUT")
        self.assertTrue(connections[0].closed)

    def test_tls_error_is_redacted(self):
        script = [ssl.SSLError("real openssl detail must not leak")]
        budget = probe._Budget()
        with patch_connection(script):
            with self.assertRaises(probe.ProbeError) as ctx:
                probe._request(budget, probe.DISCOVERY_HOST, "GET", "/v2/things", {}, None)
        self.assertEqual(ctx.exception.code, "TLS_ERROR")
        self.assertNotIn("openssl", str(ctx.exception))

    def test_oversized_body_is_capped(self):
        oversized = b"a" * (probe.MAX_RESPONSE_BYTES + 1)
        script = [(200, oversized)]
        budget = probe._Budget()
        with patch_connection(script):
            with self.assertRaises(probe.ProbeError) as ctx:
                probe._request(budget, probe.DISCOVERY_HOST, "GET", "/v2/things", {}, None)
        self.assertEqual(ctx.exception.code, "PAYLOAD_TOO_LARGE")

    def test_invalid_host_is_rejected_before_any_connection(self):
        budget = probe._Budget()
        with mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            with self.assertRaises(probe.ProbeError) as ctx:
                probe._request(budget, "evil.example.com", "GET", "/v2/things", {}, None)
        self.assertEqual(ctx.exception.code, "CONNECT_ERROR")

    def test_invalid_path_for_host_is_rejected_before_any_connection(self):
        budget = probe._Budget()
        with mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            with self.assertRaises(probe.ProbeError) as ctx:
                probe._request(budget, probe.DISCOVERY_HOST, "GET", "/v2/arbitrary", {}, None)
        self.assertEqual(ctx.exception.code, "CONNECT_ERROR")

    def test_account_path_on_discovery_host_is_rejected(self):
        budget = probe._Budget()
        with mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            with self.assertRaises(probe.ProbeError) as ctx:
                probe._request(
                    budget, probe.DISCOVERY_HOST, "POST", "/api/v2/account/login", {}, b"{}"
                )
        self.assertEqual(ctx.exception.code, "CONNECT_ERROR")

    def test_chunk_stream_stops_once_time_budget_expires(self):
        class SlowTrickleResponse:
            """Yields many tiny chunks, advancing a fake clock on each read."""

            def __init__(self, clock):
                self.clock = clock
                self.calls = 0

            def read(self, n=-1):
                self.calls += 1
                self.clock[0] += probe.TOTAL_BUDGET_S  # each read blows the budget
                return b"x"

        budget = probe._Budget()
        clock = [budget.start]
        resp = SlowTrickleResponse(clock)
        with mock.patch.object(time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(probe.ProbeError) as ctx:
                probe._bounded_read(budget, resp)
        self.assertEqual(ctx.exception.code, "TIME_BUDGET_EXCEEDED")
        # Only the first chunk should have been read before the budget check
        # inside the loop stopped the trickle.
        self.assertEqual(resp.calls, 1)

    def test_request_closes_connection_when_chunk_trickle_expires_budget(self):
        class SlowTrickleResponse:
            def __init__(self, clock):
                self.clock = clock
                self.status = 200

            def read(self, n=-1):
                self.clock[0] += probe.TOTAL_BUDGET_S
                return b"x"

        budget = probe._Budget()
        clock = [budget.start]

        class FakeConnection:
            instances = []

            def __init__(self, host, port, context=None, timeout=None):
                self.closed = False
                FakeConnection.instances.append(self)

            def request(self, method, path, body=None, headers=None):
                pass

            def getresponse(self):
                return SlowTrickleResponse(clock)

            def close(self):
                self.closed = True

        with mock.patch.object(http.client, "HTTPSConnection", FakeConnection), \
                mock.patch.object(time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(probe.ProbeError) as ctx:
                probe._request(budget, probe.DISCOVERY_HOST, "GET", "/v2/things", {}, None)
        self.assertEqual(ctx.exception.code, "TIME_BUDGET_EXCEEDED")
        self.assertTrue(FakeConnection.instances[0].closed)

    def test_request_budget_cap(self):
        budget = probe._Budget()
        for _ in range(probe.MAX_REQUESTS):
            budget.use_request()
        with self.assertRaises(probe.ProbeError) as ctx:
            budget.use_request()
        self.assertEqual(ctx.exception.code, "REQUEST_LIMIT_EXCEEDED")

    def test_time_budget_cap(self):
        budget = probe._Budget()
        with mock.patch.object(time, "monotonic", return_value=budget.start + probe.TOTAL_BUDGET_S + 1):
            with self.assertRaises(probe.ProbeError) as ctx:
                budget.check_time()
        self.assertEqual(ctx.exception.code, "TIME_BUDGET_EXCEEDED")

    def test_tls_handshake_only_connects_and_closes_without_request(self):
        script = [None]
        connections = []
        budget = probe._Budget()
        with patch_connection(script, connections):
            probe._tls_handshake_only(budget, probe.HOSTS[0])
        self.assertTrue(connections[0].closed)
        self.assertEqual(connections[0].sent, [])

    def test_tls_handshake_only_reports_connect_failure(self):
        script = [OSError("no route")]
        budget = probe._Budget()
        with patch_connection(script):
            with self.assertRaises(probe.ProbeError) as ctx:
                probe._tls_handshake_only(budget, probe.HOSTS[0])
        self.assertEqual(ctx.exception.code, "CONNECT_ERROR")


class TlsCheckCommandTests(unittest.TestCase):
    def test_all_hosts_ok(self):
        script = [None, None, None]
        with patch_connection(script):
            report = probe.tls_check_command()
        self.assertEqual(report["status"], "OK")
        for host in probe.HOSTS:
            self.assertEqual(report["hosts"][host], "OK")

    def test_one_host_failure_marks_overall_failed(self):
        script = [None, ssl.SSLError("bad cert"), None]
        with patch_connection(script):
            report = probe.tls_check_command()
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["hosts"][probe.HOSTS[1]], "TLS_ERROR")

    def test_tls_check_never_sends_http_request(self):
        script = [None, None, None]
        connections = []
        with patch_connection(script, connections):
            probe.tls_check_command()
        for conn in connections:
            self.assertEqual(conn.sent, [])


class NativePromptTests(unittest.TestCase):
    def test_ok_answer_returns_text(self):
        with patch_dialog([(0, "secret-value\n")]):
            text, reason = probe._native_prompt("x")
        self.assertEqual(text, "secret-value")
        self.assertIsNone(reason)

    def test_canceled_returns_reason_without_network(self):
        with patch_dialog([(1, "")]):
            text, reason = probe._native_prompt("x")
        self.assertIsNone(text)
        self.assertEqual(reason, "CANCELED")

    def test_timeout_returns_reason(self):
        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="osascript", timeout=1)

        with mock.patch.object(subprocess, "run", side_effect=raise_timeout):
            text, reason = probe._native_prompt("x")
        self.assertIsNone(text)
        self.assertEqual(reason, "TIMEOUT")

    def test_empty_answer_rejected(self):
        with patch_dialog([(0, "\n")]):
            text, reason = probe._native_prompt("x")
        self.assertIsNone(text)
        self.assertEqual(reason, "INVALID_INPUT")

    def test_oversized_answer_rejected(self):
        with patch_dialog([(0, "a" * (probe.MAX_SECRET_LEN + 1) + "\n")]):
            text, reason = probe._native_prompt("x")
        self.assertIsNone(text)
        self.assertEqual(reason, "INVALID_INPUT")

    def test_script_argument_is_constant_across_calls(self):
        captured = []

        def fake_run(args, capture_output, text, timeout):
            captured.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="x\n", stderr="")

        with mock.patch.object(subprocess, "run", side_effect=fake_run):
            probe._native_prompt("Tapo account email:")
            probe._native_prompt("Tapo account password:")
        self.assertEqual(captured[0][0], probe.OSASCRIPT_PATH)
        self.assertIn("-e", captured[0])


class LoginCheckFlowTests(unittest.TestCase):
    def test_model_variants_are_diagnostic_not_automatic_target_selection(self):
        for model in ("C545D(UN)", "C545D 1.0", "Tapo C545D", "C545D(EU)1.0"):
            self.assertEqual(probe._c545d_model_kind(model), "VARIANT")
        for model in ("C545D-other", "C545D2", "private nickname C545D", "C545D/secret"):
            self.assertEqual(probe._c545d_model_kind(model), "OTHER")
        devices = [{"deviceType": "SMART.IPCAMERA", "thingName": "private-id",
                    "model": "C545D(UN)"}]
        report = self._run_with([(0, "owner@example.com\n"), (0, "password\n")],
                                [(200, LOGIN_OK_BODY), (200, discovery_body(devices))])
        self.assertEqual(report["c545d_model_variants"], 1)
        self.assertEqual(report["c545d_candidates"], 0)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertNotIn("private-id", json.dumps(report))

    def test_email_mfa_uses_single_email_endpoint_and_limits_password_scope(self):
        connections = []
        script = [(200, MFA_REQUIRED_BODY), (200, SEND_MFA_OK_BODY),
                  (200, SUBMIT_MFA_OK_BODY), (200, discovery_body(ONE_C545D))]
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "synthetic@example.invalid\n"),
                              (0, "unique-password-sentinel\n"), (0, "123456\n")]), \
                patch_connection(script, connections):
            report = probe.login_check_command()
        self.assertEqual(report["status"], "SUCCESS")
        self.assertEqual(len(connections), 4)
        send = connections[1].sent[0]
        self.assertEqual(connections[1].host, probe.ACCOUNT_HOST)
        self.assertEqual(send[1], "/api/v2/account/getEmailVC4TerminalMFA")
        payload = json.loads(send[2])
        self.assertEqual(set(payload), {"appType", "cloudUserName", "cloudPassword", "terminalUUID"})
        self.assertEqual(payload["cloudPassword"], "unique-password-sentinel")
        for connection in connections[2:]:
            self.assertNotIn("unique-password-sentinel", str(connection.sent))
        self.assertNotIn("unique-password-sentinel", json.dumps(report))
        with mock.patch.object(probe, "_open_connection") as connect:
            with self.assertRaises(probe.ProbeError):
                probe._request(probe._Budget(), probe.ACCOUNT_HOST, "POST",
                               "/api/v2/account/getPushVC4TerminalMFA", {}, b"{}")
            connect.assert_not_called()

    def test_input_timeout_reports_stage_without_advancing_auth(self):
        for answers, network, stage in [
            ([(None, "TIMEOUT")], [], "EMAIL_INPUT"),
            ([("synthetic@example.invalid", None), (None, "TIMEOUT")], [], "PASSWORD_INPUT"),
            ([("synthetic@example.invalid", None), ("password", None), (None, "TIMEOUT")],
             [(200, MFA_REQUIRED_BODY), (200, SEND_MFA_OK_BODY)], "OTP_INPUT"),
        ]:
            connections = []
            with self.subTest(stage=stage), \
                    mock.patch.object(probe.sys, "platform", "darwin"), \
                    mock.patch.object(probe.os.path, "exists", return_value=True), \
                    mock.patch.object(probe, "_native_prompt", side_effect=answers), \
                    patch_connection(network, connections):
                report = probe.login_check_command()
            self.assertEqual(report["stage"], stage)
            self.assertEqual(report["reason"], "TIMEOUT")
            self.assertEqual(len(connections), 2 if stage == "OTP_INPUT" else 0)

    def test_decimal_string_success_code_reaches_inventory(self):
        body = json.dumps({"errorCode": "0", "result": {"token": "private-token"}}).encode()
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "private-password\n")],
            [(200, body), (200, discovery_body(ONE_C545D))],
        )
        self.assertEqual(report["inventory_status"], "CLOUD_INVENTORY_ONLY")
        self.assertNotIn("private-token", json.dumps(report))
        self.assertNotIn("private-password", json.dumps(report))

    def test_decimal_string_error_never_accepts_a_token(self):
        body = json.dumps({"errorCode": "-20601", "result": {"token": "private-token"}}).encode()
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "password\n")], [(200, body)]
        )
        self.assertEqual(report["reason"], "AUTH_FAILED")
        self.assertEqual(report["stage"], "LOGIN")

    def test_decimal_string_mfa_flow(self):
        bodies = []
        for raw in (MFA_REQUIRED_BODY, SEND_MFA_OK_BODY, SUBMIT_MFA_OK_BODY):
            body = json.loads(raw)
            for key in ("errorCode", "error_code", "code"):
                if key in body:
                    body[key] = str(body[key])
            bodies.append((200, json.dumps(body).encode()))
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "password\n"), (0, "123456\n")],
            bodies + [(200, discovery_body(ONE_C545D))],
        )
        self.assertEqual(report["inventory_status"], "CLOUD_INVENTORY_ONLY")

    def test_normalized_codes_still_detect_conflicts_and_inner_failure(self):
        self.assertEqual(probe._account_error_code({"errorCode": "0", "code": 0}), (0, True))
        self.assertEqual(probe._account_error_code(
            {"errorCode": "0", "result": {"errorCode": "-20601"}}
        ), (-20601, True))
        for body in ({"errorCode": "0", "code": -1},
                     {"errorCode": "-1", "result": {"errorCode": "-2"}}):
            with self.subTest(body=body), self.assertRaises(probe.ProbeError) as caught:
                probe._account_error_code(body)
            self.assertEqual(caught.exception.detail, "CONFLICTING_CODES")

    def test_noncanonical_status_codes_remain_rejected(self):
        for value in (True, False, None, 0.0, [], {}, "", " 0", "0\n", "+0", "-0",
                      "00", "01", "-01", "0.0", "0e0", "٠", "０", "9" * 100):
            with self.subTest(value=value), self.assertRaises(probe.ProbeError) as caught:
                probe._extract_error_code({"errorCode": value})
            self.assertEqual(caught.exception.detail, "INVALID_CODE_TYPE")

    def _run_with(self, dialog_answers, network_script, platform="darwin", exists=True,
                  target_name_sha256=None):
        with mock.patch.object(probe.sys, "platform", platform), \
                mock.patch.object(probe.os.path, "exists", return_value=exists), \
                patch_dialog(dialog_answers), \
                patch_connection(network_script):
            return probe.login_check_command(target_name_sha256=target_name_sha256)

    def test_direct_login_no_mfa_single_c545d(self):
        script = [
            (200, LOGIN_OK_BODY),
            (200, discovery_body(ONE_C545D)),
        ]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertEqual(report["cameras_total"], 1)
        self.assertEqual(report["c545d_candidates"], 1)
        self.assertEqual(report["inventory_status"], "CLOUD_INVENTORY_ONLY")

    def test_mfa_flow_success(self):
        script = [
            (200, MFA_REQUIRED_BODY),
            (200, SEND_MFA_OK_BODY),
            (200, SUBMIT_MFA_OK_BODY),
            (200, discovery_body(ZERO_C545D)),
        ]
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n"), (0, "123456\n")], script
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["cameras_total"], 1)
        self.assertEqual(report["c545d_candidates"], 0)
        self.assertEqual(report["inventory_status"], "TARGET_NOT_FOUND")

    def test_duplicate_c545d_is_ambiguous(self):
        script = [(200, LOGIN_OK_BODY), (200, discovery_body(TWO_C545D))]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["c545d_candidates"], 2)
        self.assertEqual(report["inventory_status"], "TARGET_AMBIGUOUS")

    def test_media_host_is_not_used_for_account_redirect(self):
        other_host = probe.HOSTS[2]
        redirect_body = json.dumps({"errorCode": -20212, "result": {"appServerUrlV2": f"https://{other_host}"}}).encode()
        script = [
            (200, redirect_body),
            (200, LOGIN_OK_BODY),
            (200, discovery_body(ZERO_C545D)),
        ]
        connections = []
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]), \
                patch_connection(script, connections):
            report = probe.login_check_command()
        self.assertEqual(report["reason"], "UNSUPPORTED_REGION")
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0].host, probe.HOSTS[0])

    def test_redirect_to_unlisted_host_is_unsupported_region_not_guessed(self):
        redirect_body = json.dumps(
            {"result": {"appServerUrlV2": "https://evil.example.com"}}
        ).encode()
        script = [(200, redirect_body)]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "UNSUPPORTED_REGION")

    def test_auth_failure_is_not_retried(self):
        script = [(401, b"{}")]
        connections = []
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]), \
                patch_connection(script, connections):
            report = probe.login_check_command()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "AUTH_FAILED")
        self.assertEqual(len(connections), 1)

    def test_wrong_password_negative_code_no_result_is_auth_failed_one_call(self):
        wrong_password_body = json.dumps({"errorCode": -20104}).encode()
        connections = []
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]), \
                patch_connection([(200, wrong_password_body)], connections):
            report = probe.login_check_command()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "AUTH_FAILED")
        self.assertEqual(len(connections), 1)

    def test_negative_code_with_valid_looking_token_never_passes(self):
        malicious_body = json.dumps({"errorCode": -1, "result": {"token": "sneaky-token"}}).encode()
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n")], [(200, malicious_body)]
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "AUTH_FAILED")

    def test_negative_code_with_mfa_challenge_never_passes(self):
        malicious_body = json.dumps(
            {"errorCode": -1, "result": {"MFAProcessId": "p", "supportedMFATypes": [2]}}
        ).encode()
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n")], [(200, malicious_body)]
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "AUTH_FAILED")

    def test_unsupported_region_alongside_token_stops_before_discovery(self):
        bad_origin_body = json.dumps(
            {"errorCode": 0, "result": {"token": "tok-1", "appServerUrlV2": "https://evil.example.com"}}
        ).encode()
        connections = []
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]), \
                patch_connection([(200, bad_origin_body)], connections):
            report = probe.login_check_command()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "UNSUPPORTED_REGION")
        self.assertEqual(len(connections), 1)  # never reaches discovery

    def test_send_mfa_errorcode_negative_one_fails(self):
        script = [(200, MFA_REQUIRED_BODY), (200, json.dumps({"errorCode": -1}).encode())]
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n")], script
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MFA_FAILED")

    def test_send_mfa_empty_ack_still_requires_successful_code_submission(self):
        for ack in (b"", b"{}"):
            with self.subTest(ack=ack):
                script = [(200, MFA_REQUIRED_BODY), (200, ack), (200, b"{}")]
                report = self._run_with(
                    [(0, "owner@example.com\n"), (0, "hunter2\n"), (0, "123456\n")], script
                )
                self.assertEqual(report["status"], "BLOCKED")
                self.assertEqual(report["reason"], "MFA_FAILED")
                self.assertEqual(report["stage"], "MFA_SUBMIT")

    def test_send_mfa_empty_object_ack_then_verified_submission(self):
        script = [(200, MFA_REQUIRED_BODY), (200, b"{}"),
                  (200, SUBMIT_MFA_OK_BODY), (200, discovery_body(ONE_C545D))]
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n"), (0, "123456\n")], script
        )
        self.assertEqual(report["inventory_status"], "CLOUD_INVENTORY_ONLY")

    def test_send_mfa_non_200_ack_stops_before_code_prompt(self):
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n")],
            [(200, MFA_REQUIRED_BODY), (503, b"private-response")],
        )
        self.assertEqual(report["detail"], "MFA_SEND_HTTP_ERROR")
        self.assertEqual(report["stage"], "MFA_SEND")
        self.assertNotIn("private-response", json.dumps(report))

    def test_submit_mfa_negative_code_with_token_fails(self):
        script = [
            (200, MFA_REQUIRED_BODY),
            (200, SEND_MFA_OK_BODY),
            (200, json.dumps({"errorCode": -1, "result": {"token": "sneaky"}}).encode()),
        ]
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n"), (0, "123456\n")], script
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MFA_FAILED")

    def test_discovery_nonzero_code_with_data_fails(self):
        script = [
            (200, LOGIN_OK_BODY),
            (200, json.dumps({"errorCode": -1, "data": ONE_C545D}).encode()),
        ]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "DISCOVERY_FAILED")

    def test_discovery_may_omit_code_on_success(self):
        script = [(200, LOGIN_OK_BODY), (200, discovery_body(ONE_C545D))]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertEqual(report["inventory_status"], "CLOUD_INVENTORY_ONLY")

    def test_malformed_camera_missing_model_is_rejected_not_zero(self):
        bad_cameras = [{"deviceType": "SMART.IPCAMERA", "thingName": "cam-1"}]
        script = [(200, LOGIN_OK_BODY), (200, discovery_body(bad_cameras))]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")
        self.assertEqual(report["stage"], "DISCOVERY")
        self.assertEqual(report["detail"], "INVALID_DISCOVERY_RECORD")

    def test_malformed_camera_missing_thing_name_is_rejected_not_zero(self):
        bad_cameras = [{"deviceType": "SMART.IPCAMERA", "model": "C545D"}]
        script = [(200, LOGIN_OK_BODY), (200, discovery_body(bad_cameras))]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")
        self.assertEqual(report["stage"], "DISCOVERY")
        self.assertEqual(report["detail"], "INVALID_DISCOVERY_RECORD")

    def test_discovery_non_list_data_detail(self):
        script = [(200, LOGIN_OK_BODY), (200, json.dumps({"data": "not-a-list"}).encode())]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["stage"], "DISCOVERY")
        self.assertEqual(report["detail"], "INVALID_DISCOVERY_LIST")

    def test_duplicate_json_keys_in_login_response_are_malformed(self):
        raw = (
            b'{"errorCode": 0, "result": {"token": "tok-1"}, "errorCode": -1}'
        )
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], [(200, raw)])
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")
        self.assertEqual(report["stage"], "LOGIN")
        # Duplicate top-level keys are rejected by the JSON parse step itself
        # (object_pairs_hook), before error-code extraction ever runs.
        self.assertEqual(report["detail"], "INVALID_JSON")

    def test_conflicting_error_code_field_names_are_malformed(self):
        raw = json.dumps({"errorCode": 0, "error_code": -1, "result": {"token": "tok-1"}}).encode()
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], [(200, raw)])
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")
        self.assertEqual(report["stage"], "LOGIN")
        self.assertEqual(report["detail"], "CONFLICTING_CODES")

    def test_boolean_error_code_is_malformed_not_success(self):
        raw = json.dumps({"errorCode": False, "result": {"token": "tok-1"}}).encode()
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], [(200, raw)])
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")
        self.assertEqual(report["stage"], "LOGIN")
        self.assertEqual(report["detail"], "INVALID_CODE_TYPE")

    def test_invalid_json_body_detail(self):
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n")], [(200, b"not json at all")]
        )
        self.assertEqual(report["stage"], "LOGIN")
        self.assertEqual(report["detail"], "INVALID_JSON")

    def test_nonobject_json_body_detail(self):
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n")], [(200, b"[1,2,3]")]
        )
        self.assertEqual(report["stage"], "LOGIN")
        self.assertEqual(report["detail"], "NONOBJECT_JSON")

    def test_missing_auth_code_detail(self):
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n")],
            [(200, json.dumps({"result": {"token": "tok"}}).encode())],
        )
        self.assertEqual(report["stage"], "LOGIN")
        self.assertEqual(report["detail"], "MISSING_AUTH_CODE")

    def test_invalid_auth_result_detail(self):
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n")],
            [(200, json.dumps({"errorCode": 0, "result": "not-an-object"}).encode())],
        )
        self.assertEqual(report["stage"], "LOGIN")
        self.assertEqual(report["detail"], "INVALID_AUTH_RESULT")

    def test_conflicting_auth_fields_detail(self):
        raw = json.dumps(
            {"errorCode": 0, "result": {"token": "tok", "MFAProcessId": "proc"}}
        ).encode()
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], [(200, raw)])
        self.assertEqual(report["stage"], "LOGIN")
        self.assertEqual(report["detail"], "CONFLICTING_AUTH_FIELDS")

    def test_missing_auth_fields_detail(self):
        raw = json.dumps({"errorCode": 0, "result": {}}).encode()
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], [(200, raw)])
        self.assertEqual(report["stage"], "LOGIN")
        self.assertEqual(report["detail"], "MISSING_AUTH_FIELDS")

    def test_mfa_send_malformed_detail(self):
        script = [(200, MFA_REQUIRED_BODY), (200, b"not json")]
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n")], script
        )
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")
        self.assertEqual(report["stage"], "MFA_SEND")
        self.assertEqual(report["detail"], "INVALID_JSON")

    def test_mfa_send_negative_code_has_fixed_detail(self):
        script = [(200, MFA_REQUIRED_BODY), (200, json.dumps({"errorCode": -1}).encode())]
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2\n")], script
        )
        self.assertEqual(report["reason"], "MFA_FAILED")
        self.assertEqual(report["stage"], "MFA_SEND")
        self.assertEqual(report["detail"], "MFA_SEND_REJECTED")

    def test_secret_sentinels_absent_from_malformed_detail_report(self):
        raw = json.dumps({"errorCode": 0, "result": {"token": "tok", "MFAProcessId": "proc"}}).encode()
        report = self._run_with(
            [(0, "owner@example.com\n"), (0, "hunter2-secret-sentinel\n")], [(200, raw)]
        )
        self.assertNotIn("hunter2-secret-sentinel", json.dumps(report))
        self.assertNotIn("owner@example.com", json.dumps(report))

    def test_target_not_found_is_blocked_not_success(self):
        script = [(200, LOGIN_OK_BODY), (200, discovery_body(ZERO_C545D))]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "TARGET_NOT_FOUND")
        self.assertEqual(report["c545d_candidates"], 0)

    def test_target_ambiguous_is_blocked_not_success(self):
        script = [(200, LOGIN_OK_BODY), (200, discovery_body(TWO_C545D))]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "TARGET_AMBIGUOUS")
        self.assertEqual(report["c545d_candidates"], 2)

    def test_bad_pinned_ca_blocks_before_any_dialog(self):
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                mock.patch.object(probe, "CA_PATH", Path("/nonexistent/ft_cloud_probe_test.pem")), \
                mock.patch.object(subprocess, "run", TripwireSubprocessRun()), \
                mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            report = probe.login_check_command()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "CA_PIN_MISMATCH")

    def test_mfa_type_unsupported_stops_before_send(self):
        unsupported_body = json.dumps(
            {"errorCode": -20677, "result": {"MFAProcessId": "p", "supportedMFATypes": [99]}}
        ).encode()
        script = [(200, unsupported_body)]
        connections = []
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]), \
                patch_connection(script, connections):
            report = probe.login_check_command()
        self.assertEqual(report["reason"], "MFA_TYPE_UNSUPPORTED")
        self.assertEqual(len(connections), 1)

    def test_malformed_discovery_result_does_not_pass(self):
        script = [(200, LOGIN_OK_BODY), (200, json.dumps({"data": "not-a-list"}).encode())]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")

    def test_empty_response_without_token_is_not_pass(self):
        script = [(200, b"{}")]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")

    def test_discovery_401_is_auth_failed_not_pass(self):
        script = [(200, LOGIN_OK_BODY), (401, b"{}")]
        report = self._run_with([(0, "owner@example.com\n"), (0, "hunter2\n")], script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "AUTH_FAILED")

    def test_canceled_email_dialog_sends_no_request(self):
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(1, "")]), \
                mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            report = probe.login_check_command()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "CANCELED")

    def test_canceled_password_dialog_sends_no_request(self):
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (1, "")]), \
                mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            report = probe.login_check_command()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "CANCELED")

    def test_canceled_mfa_code_sends_no_submit_request(self):
        script = [(200, MFA_REQUIRED_BODY), (200, SEND_MFA_OK_BODY)]
        connections = []
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n"), (1, "")]), \
                patch_connection(script, connections):
            report = probe.login_check_command()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "CANCELED")
        self.assertEqual(len(connections), 2)

    def test_native_dialog_unavailable_blocks_before_any_prompt(self):
        with mock.patch.object(probe.sys, "platform", "linux"), \
                mock.patch.object(subprocess, "run", TripwireSubprocessRun()), \
                mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            report = probe.login_check_command()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "NATIVE_DIALOG_UNAVAILABLE")


class ProbeErrorRedactionTests(unittest.TestCase):
    def test_unknown_code_is_coerced(self):
        exc = probe.ProbeError("SOMETHING_NOT_IN_THE_SET")
        self.assertEqual(exc.code, "UNKNOWN_ERROR")

    def test_report_sanitizes_unknown_reason(self):
        report = probe._report("x", "BLOCKED", "NOT_A_REAL_CODE")
        self.assertEqual(report["reason"], "UNKNOWN_ERROR")

    def test_all_error_codes_are_uppercase_strings(self):
        for code in probe.ERROR_CODES:
            self.assertIsInstance(code, str)
            self.assertEqual(code, code.upper())

    def test_unknown_detail_is_sanitized_to_none(self):
        exc = probe.ProbeError("MALFORMED_RESPONSE", "NOT_A_REAL_DETAIL")
        self.assertIsNone(exc.detail)

    def test_known_detail_is_preserved(self):
        exc = probe.ProbeError("MALFORMED_RESPONSE", "INVALID_JSON")
        self.assertEqual(exc.detail, "INVALID_JSON")

    def test_report_omits_stage_and_detail_by_default(self):
        report = probe._report("x", "BLOCKED", "AUTH_FAILED")
        self.assertNotIn("stage", report)
        self.assertNotIn("detail", report)

    def test_report_sanitizes_unknown_stage_and_detail(self):
        report = probe._report(
            "x", "BLOCKED", "MALFORMED_RESPONSE", stage="NOT_A_STAGE", detail="NOT_A_DETAIL"
        )
        self.assertNotIn("stage", report)
        self.assertNotIn("detail", report)

    def test_all_detail_codes_are_uppercase_strings(self):
        for code in probe.DETAIL_CODES:
            self.assertIsInstance(code, str)
            self.assertEqual(code, code.upper())


class CliTests(unittest.TestCase):
    def test_unknown_command_does_not_echo_argument(self):
        code, out = run_cli(["totally-bogus-command"])
        self.assertEqual(code, 2)
        self.assertNotIn("totally-bogus-command", out)
        self.assertEqual(json.loads(out)["reason"], "INVALID_COMMAND")

    def test_unrecognized_extra_argument_does_not_echo_value(self):
        code, out = run_cli(["check", "--secret-looking-value=hunter2"])
        self.assertEqual(code, 2)
        self.assertNotIn("hunter2", out)

    def test_check_via_cli_exits_2(self):
        code, out = run_cli(["check"])
        self.assertEqual(code, 2)
        report = json.loads(out)
        self.assertEqual(report["command"], "check")

    def test_tls_check_via_cli_ok_exits_0(self):
        with patch_connection([None, None, None]):
            code, out = run_cli(["tls-check"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "OK")

    def test_login_check_via_cli_blocked_exits_2(self):
        with mock.patch.object(probe.sys, "platform", "linux"):
            code, out = run_cli(["login-check"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)["reason"], "NATIVE_DIALOG_UNAVAILABLE")

    def test_unexpected_internal_error_is_redacted(self):
        with mock.patch.object(probe, "check_command", side_effect=RuntimeError("leaky detail")):
            code, out = run_cli(["check"])
        self.assertEqual(code, 1)
        self.assertNotIn("leaky detail", out)
        self.assertEqual(json.loads(out)["reason"], "UNKNOWN_ERROR")


class AppleScriptLiteralTests(unittest.TestCase):
    def test_escapes_quotes_and_backslashes(self):
        literal = probe._as_applescript_literal('He said "hi" \\ there')
        self.assertEqual(literal, '"He said \\"hi\\" \\\\ there"')


class PoIndependentReviewTests(unittest.TestCase):
    def test_audited_aps1_metadata_allows_token_but_not_new_http_target(self):
        host = "n-aps1-wap.i.tplinkcloud.com"
        url = "https://" + host
        self.assertEqual(probe._validate_region_origin(url), host)
        body = json.dumps({"errorCode": "0", "result": {
            "token": "synthetic-token", "appServerUrlV2": url}}).encode()
        with mock.patch.object(probe, "_request", return_value=(200, body)):
            token = probe._submit_mfa(probe._Budget(), probe.ACCOUNT_HOST,
                                      "email", "term", "id", "code")
        self.assertEqual(token, "synthetic-token")
        with mock.patch.object(probe, "_open_connection") as connect:
            with self.assertRaises(probe.ProbeError):
                probe._request(probe._Budget(), host, "POST", "/api/v2/account/login", {}, b"{}")
            connect.assert_not_called()

    def test_region_diagnostic_does_not_trust_or_leak_origins(self):
        for region in ("euw1", "use1"):
            url = "https://n-" + region + "-wap.i.tplinkcloud.com"
            self.assertEqual(probe._region_detail(url), "REGION_" + region.upper() + "_ACCOUNT")
            self.assertIsNone(probe._validate_region_origin(url))
            body = json.dumps({"errorCode": 0, "result": {
                "token": "private-token", "appServerUrlV2": url}}).encode()
            with mock.patch.object(probe, "_request", return_value=(200, body)) as send:
                with self.assertRaises(probe.ProbeError) as caught:
                    probe._submit_mfa(probe._Budget(), probe.ACCOUNT_HOST, "email", "term", "id", "code")
            self.assertEqual(caught.exception.code, "UNSUPPORTED_REGION")
            self.assertEqual(caught.exception.detail, "REGION_" + region.upper() + "_ACCOUNT")
            self.assertEqual(send.call_count, 1)
        for value in (None, {}, "https://secret.example", "https://n-aps1-wap.i.tplinkcloud.com?token=secret"):
            self.assertEqual(probe._region_detail(value), "REGION_OTHER_OR_INVALID")

    def test_nested_account_error_cannot_hide_behind_outer_success(self):
        payload = {"errorCode": 0, "result": {"errorCode": -1, "token": "synthetic-token"}}
        body = json.dumps(payload).encode()
        budget = probe._Budget()
        with mock.patch.object(probe, "_request", return_value=(200, body)) as send:
            with self.assertRaises(probe.ProbeError) as cm:
                probe._login(budget, "synthetic@example.invalid", "synthetic-password")
        self.assertEqual(cm.exception.code, "AUTH_FAILED")
        self.assertEqual(send.call_count, 1)

    def test_nested_mfa_errors_stop_before_acceptance(self):
        body = json.dumps({"errorCode": 0, "result": {"errorCode": -1, "token": "synthetic"}}).encode()
        for fn, args in [
            (probe._send_mfa, ("synthetic@example.invalid", "terminal", "process")),
            (probe._submit_mfa, ("synthetic@example.invalid", "terminal", "process", "123456")),
        ]:
            with self.subTest(method=fn.__name__), mock.patch.object(probe, "_request", return_value=(200, body)):
                with self.assertRaises(probe.ProbeError) as cm:
                    fn(probe._Budget(), probe.ACCOUNT_HOST, *args)
                self.assertEqual(cm.exception.code, "MFA_FAILED")

    def test_inner_only_success_code_is_explicit_success(self):
        body = json.dumps({"result": {"errorCode": 0, "token": "synthetic"}}).encode()
        with mock.patch.object(probe, "_request", return_value=(200, body)):
            self.assertEqual(probe._login(probe._Budget(), "a", "b")["token"], "synthetic")

    def test_account_credentials_never_sent_to_media_host(self):
        with mock.patch.object(probe, "_open_connection") as connect:
            with self.assertRaises(probe.ProbeError):
                probe._request(probe._Budget(), probe.HOSTS[2], "POST", "/api/v2/account/login", {}, b"{}")
            connect.assert_not_called()

    def test_body_reader_uses_single_read_not_fill_until_full(self):
        class Response:
            def read(self, n):
                raise AssertionError("must not use fill-until-full HTTPResponse.read")
            def read1(self, n):
                return b""
        self.assertEqual(probe._bounded_read(probe._Budget(), Response()), b"")

    def test_missing_device_type_is_malformed_not_empty_inventory(self):
        body = json.dumps({"data": [{"model": "C545D", "thingName": "synthetic"}]}).encode()
        with mock.patch.object(probe, "_request", return_value=(200, body)):
            with self.assertRaises(probe.ProbeError) as cm:
                probe._discover(probe._Budget(), "token", "terminal")
        self.assertEqual(cm.exception.code, "MALFORMED_RESPONSE")

    def test_mfa_submit_unknown_origin_cannot_proceed_to_discovery(self):
        body = json.dumps({"errorCode": 0, "result": {"token": "synthetic", "appServerUrlV2": "https://unknown.example"}}).encode()
        with mock.patch.object(probe, "_request", return_value=(200, body)):
            with self.assertRaises(probe.ProbeError) as cm:
                probe._submit_mfa(probe._Budget(), probe.ACCOUNT_HOST, "email", "terminal", "process", "123456")
        self.assertEqual(cm.exception.code, "UNSUPPORTED_REGION")


def _name_digest(name):
    return hashlib.sha256(name.strip().casefold().encode("utf-8")).hexdigest()


EXAMPLE_NAME = "Example Test Camera"
EXAMPLE_DIGEST = _name_digest(EXAMPLE_NAME)


def camera(nickname=None, device_name=None, model="C210", thing_name="cam"):
    item = {"deviceType": "SMART.IPCAMERA", "model": model, "thingName": thing_name}
    if nickname is not None:
        item["nickname"] = nickname
    if device_name is not None:
        item["deviceName"] = device_name
    return item


class OwnerNameSelectorTests(unittest.TestCase):
    """OD-42: digest comparisons only; never assert on names/models/ids directly."""

    def _run(self, devices, digest=EXAMPLE_DIGEST, login_body=LOGIN_OK_BODY):
        script = [(200, login_body), (200, discovery_body(devices))]
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]), \
                patch_connection(script):
            return probe.login_check_command(target_name_sha256=digest)

    def test_none_digest_keeps_model_only_behavior(self):
        report = self._run([camera(nickname=EXAMPLE_NAME, model="C210")], digest=None)
        self.assertNotIn("target_name_matches", report)
        self.assertNotIn("selection_basis", report)
        self.assertNotIn("selected_model_kind", report)
        self.assertEqual(report["inventory_status"], "TARGET_NOT_FOUND")

    def test_invalid_digest_rejected_before_dialog_or_network(self):
        for bad in ("short", "g" * 64, "A" * 64, "", 123, EXAMPLE_DIGEST + "0"):
            with self.subTest(bad=bad), \
                    mock.patch.object(subprocess, "run", TripwireSubprocessRun()), \
                    mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
                report = probe.login_check_command(target_name_sha256=bad)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["reason"], "INVALID_INPUT")

    def test_plain_nickname_unique_other_model_is_cloud_inventory_only(self):
        report = self._run([camera(nickname=EXAMPLE_NAME, model="C210")])
        self.assertEqual(report["status"], "SUCCESS")
        self.assertEqual(report["inventory_status"], "CLOUD_INVENTORY_ONLY")
        self.assertEqual(report["target_name_matches"], 1)
        self.assertEqual(report["selection_basis"], "OWNER_NAME_EXACT")
        self.assertEqual(report["selected_model_kind"], "OTHER")

    def test_base64_nickname_is_decoded_and_matched(self):
        encoded = base64.b64encode(EXAMPLE_NAME.encode("utf-8")).decode("ascii")
        report = self._run([camera(nickname=encoded, model="C545D")])
        self.assertEqual(report["target_name_matches"], 1)
        self.assertEqual(report["selected_model_kind"], "EXACT")

    def test_missing_empty_nickname_falls_back_to_device_name(self):
        for nickname in (None, ""):
            with self.subTest(nickname=nickname):
                report = self._run([camera(nickname=nickname, device_name=EXAMPLE_NAME)])
            self.assertEqual(report["target_name_matches"], 1)

    def test_malformed_nickname_does_not_select_fallback_name(self):
        for nickname in (123, [], {}):
            with self.subTest(nickname=nickname):
                report = self._run([camera(nickname=nickname, device_name=EXAMPLE_NAME)])
                self.assertEqual(report["target_name_matches"], 0)

    def test_direct_discover_invalid_digest_stops_before_network(self):
        with mock.patch.object(probe, "_request") as request:
            with self.assertRaises(probe.ProbeError):
                probe._discover(probe._Budget(), "token", "terminal", "bad")
            request.assert_not_called()

    def test_mismatched_nickname_never_falls_back_to_device_name(self):
        report = self._run([camera(nickname="Totally Different Name", device_name=EXAMPLE_NAME)])
        self.assertEqual(report["target_name_matches"], 0)
        self.assertEqual(report["inventory_status"], "TARGET_NOT_FOUND")
        self.assertEqual(report["selected_model_kind"], "UNKNOWN")

    def test_duplicate_matching_names_are_ambiguous_not_first_selected(self):
        report = self._run([
            camera(nickname=EXAMPLE_NAME, model="C210", thing_name="cam-1"),
            camera(nickname=EXAMPLE_NAME, model="C545D", thing_name="cam-2"),
        ])
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["inventory_status"], "TARGET_AMBIGUOUS")
        self.assertEqual(report["target_name_matches"], 2)
        self.assertEqual(report["selected_model_kind"], "UNKNOWN")

    def test_zero_matches_is_target_not_found_regardless_of_model(self):
        report = self._run([camera(nickname="Other Camera", model="C545D")])
        self.assertEqual(report["inventory_status"], "TARGET_NOT_FOUND")
        self.assertEqual(report["target_name_matches"], 0)

    def test_report_never_contains_name_model_id_or_digest(self):
        report = self._run([camera(nickname=EXAMPLE_NAME, model="C210", thing_name="private-thing-id")])
        dumped = json.dumps(report)
        self.assertNotIn(EXAMPLE_NAME, dumped)
        self.assertNotIn("C210", dumped)
        self.assertNotIn("private-thing-id", dumped)
        self.assertNotIn(EXAMPLE_DIGEST, dumped)

    def test_existing_c545d_counts_preserved_alongside_name_selection(self):
        devices = [
            camera(nickname=EXAMPLE_NAME, model="C545D", thing_name="cam-1"),
            camera(nickname="Another Camera", model="C545D(UN)", thing_name="cam-2"),
        ]
        report = self._run(devices)
        self.assertEqual(report["c545d_candidates"], 1)
        self.assertEqual(report["c545d_model_variants"], 1)
        self.assertEqual(report["target_name_matches"], 1)


class SelectedCameraCallbackTests(unittest.TestCase):
    """OD-43: the minimal private selected-camera callback hook."""

    def _run(self, devices, digest=EXAMPLE_DIGEST, callback=None):
        script = [(200, LOGIN_OK_BODY), (200, discovery_body(devices))]
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]), \
                patch_connection(script):
            return probe.login_check_command(target_name_sha256=digest, on_selected_camera=callback)

    def test_callback_requires_digest_before_any_dialog_or_network(self):
        with mock.patch.object(subprocess, "run", TripwireSubprocessRun()), \
                mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            report = probe.login_check_command(target_name_sha256=None, on_selected_camera=lambda *a: {})
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "INVALID_INPUT")

    def test_non_callable_callback_is_rejected_before_any_dialog_or_network(self):
        with mock.patch.object(subprocess, "run", TripwireSubprocessRun()), \
                mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            report = probe.login_check_command(target_name_sha256=EXAMPLE_DIGEST, on_selected_camera="not-callable")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "INVALID_INPUT")

    def test_callback_invoked_only_for_unique_match(self):
        calls = []

        def callback(token, terminal_uuid, selected):
            calls.append((token, terminal_uuid, selected))
            return {"status": "SUCCESS", "probed": True}

        report = self._run([camera(nickname=EXAMPLE_NAME, model="C545D")], callback=callback)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "tok-1")
        self.assertEqual(calls[0][2]["model_kind"], "EXACT")
        self.assertEqual(report["sd_probe"], {"status": "SUCCESS", "probed": True})

    def test_callback_not_invoked_for_zero_matches(self):
        calls = []
        report = self._run(
            [camera(nickname="Different Name", model="C545D")],
            callback=lambda *a: calls.append(a),
        )
        self.assertEqual(calls, [])
        self.assertNotIn("sd_probe", report)
        self.assertEqual(report["inventory_status"], "TARGET_NOT_FOUND")

    def test_callback_not_invoked_for_ambiguous_matches(self):
        calls = []
        devices = [
            camera(nickname=EXAMPLE_NAME, model="C210", thing_name="cam-1"),
            camera(nickname=EXAMPLE_NAME, model="C545D", thing_name="cam-2"),
        ]
        report = self._run(devices, callback=lambda *a: calls.append(a))
        self.assertEqual(calls, [])
        self.assertNotIn("sd_probe", report)
        self.assertEqual(report["inventory_status"], "TARGET_AMBIGUOUS")

    def test_callback_exception_is_redacted_not_propagated(self):
        def callback(token, terminal_uuid, selected):
            raise RuntimeError("leaky internal detail")

        report = self._run([camera(nickname=EXAMPLE_NAME, model="C545D")], callback=callback)
        self.assertEqual(report["sd_probe"], {"status": "BLOCKED", "reason": "UNKNOWN_ERROR"})
        self.assertNotIn("leaky internal detail", json.dumps(report))

    def test_selected_never_leaks_raw_thing_name_into_report(self):
        calls = []

        def callback(token, terminal_uuid, selected):
            calls.append(selected)
            return {"status": "SUCCESS"}

        report = self._run(
            [camera(nickname=EXAMPLE_NAME, model="C545D", thing_name="private-thing-id")],
            callback=callback,
        )
        self.assertEqual(calls[0]["thing_name"], "private-thing-id")
        self.assertNotIn("private-thing-id", json.dumps(report))


class CanonicalAppServerTests(unittest.TestCase):
    def test_missing_app_server_is_accepted(self):
        self.assertTrue(probe._validate_canonical_app_server(None))

    def test_exact_canonical_origin_with_optional_slash_and_port_accepted(self):
        for suffix in ("", "/", ":443", ":443/"):
            self.assertTrue(probe._validate_canonical_app_server(probe.CANONICAL_APP_SERVER + suffix))

    def test_other_origin_is_rejected(self):
        self.assertFalse(probe._validate_canonical_app_server("https://evil.example.com"))
        self.assertFalse(probe._validate_canonical_app_server(probe.CANONICAL_APP_SERVER + "/extra"))
        self.assertFalse(probe._validate_canonical_app_server(123))

    def test_mismatched_app_server_on_matched_record_blocks_before_callback(self):
        devices = [
            {
                "deviceType": "SMART.IPCAMERA",
                "model": "C545D",
                "thingName": "cam-1",
                "nickname": EXAMPLE_NAME,
                "appServerUrlV2": "https://evil.example.com",
            }
        ]
        calls = []
        script = [(200, LOGIN_OK_BODY), (200, discovery_body(devices))]
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]), \
                patch_connection(script):
            report = probe.login_check_command(
                target_name_sha256=EXAMPLE_DIGEST, on_selected_camera=lambda *a: calls.append(a)
            )
        self.assertEqual(calls, [])
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "TARGET_SERVER_MISMATCH")

    def test_canonical_app_server_on_matched_record_is_accepted(self):
        devices = [
            {
                "deviceType": "SMART.IPCAMERA",
                "model": "C545D",
                "thingName": "cam-1",
                "nickname": EXAMPLE_NAME,
                "appServerUrlV2": probe.CANONICAL_APP_SERVER,
            }
        ]
        calls = []
        script = [(200, LOGIN_OK_BODY), (200, discovery_body(devices))]
        with mock.patch.object(probe.sys, "platform", "darwin"), \
                mock.patch.object(probe.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]), \
                patch_connection(script):
            report = probe.login_check_command(
                target_name_sha256=EXAMPLE_DIGEST,
                on_selected_camera=lambda *a: calls.append(a) or {"status": "SUCCESS"},
            )
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["sd_probe"], {"status": "SUCCESS"})


if __name__ == "__main__":
    unittest.main()
