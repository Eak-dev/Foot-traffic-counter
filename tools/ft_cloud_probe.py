#!/usr/bin/env python3
"""FT-D0 OD-40: a runnable stdlib TP-Link/Tapo cloud-auth probe.

Protocol/signing details (login/MFA request shapes, header names, the
Content-MD5 + X-Authorization signature, and the discovery endpoint) are
adapted from OnTapo at commit a387f6abddb72f7e6eea72b374df5ad189da1f5f; see
docs/THIRD_PARTY_NOTICES.md. This is an unofficial interoperability probe,
not a vendor-endorsed client or a tested C545D downloader.

Three commands:

* ``check``       - fully offline readiness check (no socket, no dialog).
* ``tls-check``    - TLS handshake only to the three fixed cloud hosts; no
  HTTP request, no auth, no device payload.
* ``login-check``  - native macOS dialog collects the Owner's email,
  password and (if required) an emailed MFA code, signs and sends a cloud
  login, then lists the account's cameras through the cloud discovery
  endpoint and reports only a camera count and a C545D candidate count.

``login-check`` requires an Owner physically at this Mac to answer the
native dialog; it does NOT solve iPhone-only remote input, and finding a
C545D in the cloud inventory is CLOUD_INVENTORY_ONLY, not camera
authentication, SD listing, or a Fixed-lens PASS. Credentials and tokens
live only in process memory for the duration of one run: nothing is
persisted, refreshed, retried after a failure, or accepted from CLI
arguments, environment variables, files, or the Keychain. No device
passthrough, SD/media methods, or setters are ever sent.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.client
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.parse
import uuid
from pathlib import Path

TOOL_NAME = "ft_cloud_probe"

HOSTS = (
    "n-wap.i.tplinkcloud.com",
    "aps1-app-server.iot.i.tplinkcloud.com",
    "aps1-cipc-api.i.tplinkcloud.com",
)
ACCOUNT_HOST = HOSTS[0]
DISCOVERY_HOST = HOSTS[1]
PORT = 443

CA_PATH = Path(__file__).resolve().parent / "certs" / "tplink-cloud-root.pem"
CA_DER_SHA256 = "8d27224dac20c2db8a380e3103b4e383c481ee41b681908579aee416761da289"

MAX_REQUESTS = 6
MAX_RESPONSE_BYTES = 1 * 1024 * 1024
SOCKET_TIMEOUT_S = 10
TOTAL_BUDGET_S = 120
READ_CHUNK = 65536

OSASCRIPT_PATH = "/usr/bin/osascript"
DIALOG_TITLE = "Foot Traffic / Tapo login"
DIALOG_TIMEOUT_S = 120
MAX_SECRET_LEN = 256

APP_TYPE = "TP-Link_Tapo_Android"
APP_VERSION = "3.20.512"
_ALT_ACCESS_KEY = "e37525375f8845999bcc56d5e6faa76d"
_ALT_SECRET_KEY = "314bc6700b3140ca80bc655e527cb062"
_HARDCODED_TIMESTAMP = "9999999999"
MFA_EMAIL = 2

ERROR_CODES = frozenset(
    {
        "CANCELED",
        "TIMEOUT",
        "SUBPROCESS_ERROR",
        "INVALID_INPUT",
        "CA_PIN_MISMATCH",
        "TLS_ERROR",
        "CONNECT_ERROR",
        "TIME_BUDGET_EXCEEDED",
        "REQUEST_LIMIT_EXCEEDED",
        "PAYLOAD_TOO_LARGE",
        "MALFORMED_RESPONSE",
        "HTTP_ERROR",
        "AUTH_FAILED",
        "MFA_FAILED",
        "MFA_TYPE_UNSUPPORTED",
        "UNSUPPORTED_REGION",
        "DISCOVERY_FAILED",
        "NATIVE_DIALOG_UNAVAILABLE",
        "UNKNOWN_ERROR",
        "UNRECOGNIZED_ARGUMENT",
        "INVALID_COMMAND",
        "MISSING_ARGUMENT",
        "TARGET_NOT_FOUND",
        "TARGET_AMBIGUOUS",
    }
)


class ProbeError(Exception):
    """Carries only a fixed, pre-redacted code; never SDK/HTTP/exception text."""

    def __init__(self, code):
        code = code if code in ERROR_CODES else "UNKNOWN_ERROR"
        super().__init__(code)
        self.code = code


# -- CA pin + TLS context ---------------------------------------------------


_SINGLE_CERT_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----\s*([A-Za-z0-9+/=\s]+?)\s*-----END CERTIFICATE-----"
)


def _load_pinned_der():
    """Read the bundled PEM and verify its DER SHA256 before anything trusts it.

    The file must contain exactly one certificate block and nothing else
    (strict fullmatch): an appended second certificate, or any other
    trailing/leading non-whitespace content, is rejected outright rather
    than silently ignored.
    """
    try:
        text = CA_PATH.read_text(encoding="ascii")
    except (OSError, UnicodeDecodeError):
        raise ProbeError("CA_PIN_MISMATCH") from None
    match = _SINGLE_CERT_RE.fullmatch(text.strip())
    if not match:
        raise ProbeError("CA_PIN_MISMATCH")
    try:
        der = base64.b64decode("".join(match.group(1).split()), validate=True)
    except (ValueError, TypeError):
        raise ProbeError("CA_PIN_MISMATCH") from None
    if hashlib.sha256(der).hexdigest() != CA_DER_SHA256:
        raise ProbeError("CA_PIN_MISMATCH")
    return der


def _pinned_context():
    """A verify-enabled SSLContext trusting only the pinned root (process-local).

    The trust anchor is built solely from the already-verified DER bytes
    (re-encoded via ``ssl.DER_cert_to_PEM_cert``); the CA file is never
    reread from disk here, so an on-disk swap between the pin check and
    context creation (TOCTOU) cannot smuggle in an extra trusted root.
    """
    der = _load_pinned_der()
    pem = ssl.DER_cert_to_PEM_cert(der)
    try:
        context = ssl.create_default_context(cadata=pem)
    except (OSError, ssl.SSLError):
        raise ProbeError("TLS_ERROR") from None
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise ProbeError("TLS_ERROR")
    return context


# -- bounded, budgeted transport --------------------------------------------


class _Budget:
    """Cooperative request-count + wall-clock cap shared across one probe run."""

    def __init__(self):
        self.start = time.monotonic()
        self.requests = 0

    def check_time(self):
        if time.monotonic() >= self.start + TOTAL_BUDGET_S:
            raise ProbeError("TIME_BUDGET_EXCEEDED")

    def use_request(self):
        self.requests += 1
        if self.requests > MAX_REQUESTS:
            raise ProbeError("REQUEST_LIMIT_EXCEEDED")


def _bounded_read(budget, resp):
    """Read a response body under both the byte cap and the time budget.

    The cooperative time budget is checked before *and* after every chunk,
    including the terminating empty read (EOF), so a slow trickle of small
    chunks cannot outlast ``TOTAL_BUDGET_S`` just because the old check ran
    once after the whole body was already in hand. Each read asks for no
    more than ``min(READ_CHUNK, remaining_bytes + 1)`` bytes, so a response
    that is already at the cap only needs one extra byte to prove it is
    oversized rather than a full further chunk.
    """
    total = 0
    chunks = []
    while True:
        budget.check_time()
        remaining = MAX_RESPONSE_BYTES - total
        want = min(READ_CHUNK, remaining + 1)
        try:
            reader = getattr(resp, "read1", resp.read)
            chunk = reader(want)
        except socket.timeout:
            raise ProbeError("TIMEOUT") from None
        except (http.client.HTTPException, OSError):
            raise ProbeError("CONNECT_ERROR") from None
        budget.check_time()
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise ProbeError("PAYLOAD_TOO_LARGE")
        chunks.append(chunk)
    return b"".join(chunks)


# Fixed (host, method, path) combinations this tool will ever open a
# connection for; nothing here is derived from a URL, redirect, or proxy, so
# this module can never be driven to send to an arbitrary target.
_ACCOUNT_PATHS = frozenset(
    {
        "/api/v2/account/login",
        "/api/v2/account/getPushVC4TerminalMFA",
        "/api/v2/account/checkMFACodeAndLogin",
    }
)


def _validate_request_target(host, method, path):
    if host not in HOSTS:
        raise ProbeError("CONNECT_ERROR")
    if host == DISCOVERY_HOST:
        if method != "GET" or path != "/v2/things":
            raise ProbeError("CONNECT_ERROR")
    elif host != ACCOUNT_HOST or method != "POST" or path not in _ACCOUNT_PATHS:
        raise ProbeError("CONNECT_ERROR")


def _open_connection(budget, host):
    """Open an HTTPS connection with a socket timeout clamped to what is left
    of the total time budget (never more than SOCKET_TIMEOUT_S).

    This is a best-effort cap, not a hard wall-clock guarantee: a blocking
    DNS resolution or other syscall inside ``connect()``/``getresponse()``
    is not interruptible mid-call by this cooperative timeout alone.
    """
    context = _pinned_context()
    remaining = (budget.start + TOTAL_BUDGET_S) - time.monotonic()
    timeout = max(0.001, min(SOCKET_TIMEOUT_S, remaining))
    try:
        return http.client.HTTPSConnection(host, PORT, context=context, timeout=timeout)
    except (OSError, ssl.SSLError):
        raise ProbeError("CONNECT_ERROR") from None


def _tls_handshake_only(budget, host):
    """Connect-only to one host: TLS handshake, no HTTP request, no auth."""
    if host not in HOSTS:
        raise ProbeError("CONNECT_ERROR")
    budget.check_time()
    budget.use_request()
    conn = _open_connection(budget, host)
    try:
        conn.connect()
    except socket.timeout:
        raise ProbeError("TIMEOUT") from None
    except ssl.SSLError:
        raise ProbeError("TLS_ERROR") from None
    except OSError:
        raise ProbeError("CONNECT_ERROR") from None
    finally:
        conn.close()


def _request(budget, host, method, path, headers, body):
    """One bounded HTTPS request; never follows redirects or uses a proxy.

    The (host, method, path) combination is checked against a fixed
    allow-list before any connection is opened, so this cannot be driven
    into serving as an arbitrary sender for a caller-supplied URL.
    """
    _validate_request_target(host, method, path)
    budget.check_time()
    budget.use_request()
    conn = _open_connection(budget, host)
    try:
        try:
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
        except socket.timeout:
            raise ProbeError("TIMEOUT") from None
        except ssl.SSLError:
            raise ProbeError("TLS_ERROR") from None
        except OSError:
            raise ProbeError("CONNECT_ERROR") from None
        if resp.status in (301, 302, 303, 307, 308):
            raise ProbeError("HTTP_ERROR")
        data = _bounded_read(budget, resp)
        return resp.status, data
    finally:
        conn.close()


def _no_duplicate_keys(pairs):
    seen = set()
    obj = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError("duplicate JSON key")
        seen.add(key)
        obj[key] = value
    return obj


def _parse_json_object(data):
    """Parse one JSON object, rejecting duplicate keys in any nested object."""
    try:
        obj = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (ValueError, UnicodeDecodeError):
        raise ProbeError("MALFORMED_RESPONSE") from None
    if not isinstance(obj, dict):
        raise ProbeError("MALFORMED_RESPONSE")
    return obj


_ERROR_CODE_KEYS = ("errorCode", "error_code", "code")


def _extract_error_code(obj):
    """Read a numeric error/status code from the known field names.

    Returns ``(code, present)``. Booleans are rejected (bools are not valid
    integer success/error codes even though ``bool`` subclasses ``int`` in
    Python), and if more than one of the known field names is present they
    must agree or the response is treated as malformed/conflicting.
    """
    found = None
    present = False
    for key in _ERROR_CODE_KEYS:
        if key not in obj:
            continue
        value = obj[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ProbeError("MALFORMED_RESPONSE")
        if present and value != found:
            raise ProbeError("MALFORMED_RESPONSE")
        found = value
        present = True
    return (found if present else 0), present


def _account_error_code(obj):
    """Honor both the outer envelope and nested account result errors.

    Some account gateways wrap an inner error in an outer success. Neither
    location may hide an explicit failure behind a valid-looking token.
    """
    outer, has_outer = _extract_error_code(obj)
    result = obj.get("result")
    inner, has_inner = _extract_error_code(result) if isinstance(result, dict) else (0, False)
    if has_outer and outer != 0:
        if has_inner and inner not in (0, outer):
            raise ProbeError("MALFORMED_RESPONSE")
        return outer, True
    if has_inner:
        return inner, True
    return outer, has_outer


# -- app signing (ported from the pinned public source) ---------------------


def _new_terminal_uuid():
    return uuid.uuid4().hex.upper()


def _sign_login(path, body, nonce):
    content_md5 = base64.b64encode(hashlib.md5(body).digest()).decode()
    sign_str = f"{content_md5}\n{_HARDCODED_TIMESTAMP}\n{nonce}\n{path}"
    sig = hmac.new(_ALT_SECRET_KEY.encode(), sign_str.encode(), hashlib.sha1).hexdigest()
    x_auth = (
        f"Timestamp={_HARDCODED_TIMESTAMP}, Nonce={nonce}, "
        f"AccessKey={_ALT_ACCESS_KEY}, Signature={sig}"
    )
    return content_md5, x_auth


def _signed_headers(path, body):
    content_md5, x_auth = _sign_login(path, body, _new_terminal_uuid())
    return {
        "Content-Type": "application/json; charset=UTF-8",
        "Content-MD5": content_md5,
        "X-Authorization": x_auth,
        "User-Agent": f"TP-Link_Tapo_Android/{APP_VERSION}(backup;Android 15)",
    }


def _cloud_headers(token, terminal_uuid):
    return {
        "Authorization": "ut|" + token,
        "app-cid": f"app:{APP_TYPE}:{terminal_uuid}",
        "x-app-name": APP_TYPE,
        "x-app-version": APP_VERSION,
        "x-term-id": terminal_uuid,
        "x-ospf": "Android 15",
        "x-net-type": "wifi",
        "x-strict": "0",
        "x-locale": "en_US",
        "User-Agent": f"TP-Link_Tapo_Android/{APP_VERSION}(ontapo;Android 15)",
    }


def _validate_region_origin(url):
    """A strict exact https://<one-of-HOSTS> origin, or None (never guessed)."""
    if not isinstance(url, str) or not url:
        return None
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url):
        return None
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme != "https" or "@" in parsed.netloc:
        return None
    if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if port is not None and port != 443:
        return None
    host = parsed.hostname
    allowed = {"https://" + h + port + slash for h in HOSTS
               for port in ("", ":443") for slash in ("", "/")}
    return host if url in allowed else None


# -- login / MFA / discovery --------------------------------------------------


_REGION_REDIRECT_CODE = -20212
_MFA_REQUIRED_CODE = -20677


def _login(budget, email, password):
    """Sign and send the cloud login, accepting only explicit, non-conflicting
    success/challenge codes.

    Any other code (including a wrong-password error carrying no result at
    all) is AUTH_FAILED and is never retried. A region redirect stops as UNSUPPORTED_REGION until
    its account origin is independently audited. A negative/unknown code
    can never reach the token/MFA
    acceptance branches below even if the body also contains a
    valid-looking token.
    """
    terminal_uuid = _new_terminal_uuid()
    account_host = ACCOUNT_HOST
    body_obj = {
        "appType": APP_TYPE,
        "appVersion": APP_VERSION,
        "cloudUserName": email,
        "cloudPassword": password,
        "platform": "Android 15",
        "refreshTokenNeeded": False,
        "terminalUUID": terminal_uuid,
        "terminalName": "FootTrafficProbe",
        "terminalMeta": "ft_cloud_probe",
    }

    def attempt(host):
        path = "/api/v2/account/login"
        body = json.dumps(body_obj).encode("utf-8")
        status, data = _request(budget, host, "POST", path, _signed_headers(path, body), body)
        if status != 200:
            raise ProbeError("AUTH_FAILED")
        obj = _parse_json_object(data)
        code, code_present = _account_error_code(obj)
        result = obj.get("result")
        # appServerUrlV2 is validated on every result (token or MFA alike),
        # before any MFA send or discovery can proceed.
        if isinstance(result, dict) and "appServerUrlV2" in result:
            if _validate_region_origin(result.get("appServerUrlV2")) is None:
                raise ProbeError("UNSUPPORTED_REGION")
        return code, code_present, result

    code, code_present, result = attempt(account_host)

    if code == _REGION_REDIRECT_CODE:
        # No other account origin has been audited yet. Media/discovery
        # hosts are NOT account-login hosts. Stop, never resend credentials.
        raise ProbeError("UNSUPPORTED_REGION")

    if code == _MFA_REQUIRED_CODE:
        if not isinstance(result, dict) or result.get("token") is not None:
            raise ProbeError("MFA_FAILED")
        mfa_id = result.get("MFAProcessId")
        types_ = result.get("supportedMFATypes")
        if not isinstance(mfa_id, str) or not mfa_id or not isinstance(types_, list):
            raise ProbeError("MFA_FAILED")
        return {
            "token": None,
            "account_host": account_host,
            "terminal_uuid": terminal_uuid,
            "mfa": {"process_id": mfa_id, "types": types_},
        }

    if code == 0:
        if not code_present:
            # Absent code is never treated as an implicit success.
            raise ProbeError("MALFORMED_RESPONSE")
        if not isinstance(result, dict):
            raise ProbeError("MALFORMED_RESPONSE")
        token = result.get("token")
        mfa_id = result.get("MFAProcessId")
        if token is not None and mfa_id is not None:
            raise ProbeError("MALFORMED_RESPONSE")  # conflicting fields
        if isinstance(token, str) and token:
            return {
                "token": token,
                "account_host": account_host,
                "terminal_uuid": terminal_uuid,
                "mfa": None,
            }
        types_ = result.get("supportedMFATypes")
        if isinstance(mfa_id, str) and mfa_id and isinstance(types_, list):
            return {
                "token": None,
                "account_host": account_host,
                "terminal_uuid": terminal_uuid,
                "mfa": {"process_id": mfa_id, "types": types_},
            }
        raise ProbeError("MALFORMED_RESPONSE")

    # Any other explicit code (wrong password, unknown negative error, ...)
    # is a plain auth failure: never retried, never treated as a region
    # issue, and never inspected for a token even if one happens to be
    # present alongside it.
    raise ProbeError("AUTH_FAILED")


def _send_mfa(budget, account_host, email, terminal_uuid, mfa_id):
    path = "/api/v2/account/getPushVC4TerminalMFA"
    body_obj = {
        "appType": APP_TYPE,
        "cloudUserName": email,
        "MFAProcessId": mfa_id,
        "MFAType": MFA_EMAIL,
        "terminalUUID": terminal_uuid,
    }
    body = json.dumps(body_obj).encode("utf-8")
    status, data = _request(budget, account_host, "POST", path, _signed_headers(path, body), body)
    if status != 200:
        raise ProbeError("MFA_FAILED")
    if not data:
        raise ProbeError("MFA_FAILED")  # empty body is never treated as success
    obj = _parse_json_object(data)
    code, code_present = _account_error_code(obj)
    if not code_present or code != 0:
        raise ProbeError("MFA_FAILED")


def _submit_mfa(budget, account_host, email, terminal_uuid, mfa_id, code):
    path = "/api/v2/account/checkMFACodeAndLogin"
    body_obj = {
        "appType": APP_TYPE,
        "cloudUserName": email,
        "code": code,
        "MFAProcessId": mfa_id,
        "MFAType": MFA_EMAIL,
        "terminalUUID": terminal_uuid,
        "terminalName": "FootTrafficProbe",
        "refreshTokenNeeded": False,
    }
    body = json.dumps(body_obj).encode("utf-8")
    status, data = _request(budget, account_host, "POST", path, _signed_headers(path, body), body)
    if status != 200:
        raise ProbeError("MFA_FAILED")
    obj = _parse_json_object(data)
    code, code_present = _account_error_code(obj)
    if not code_present or code != 0:
        # A negative/unknown code never passes even if a token is also present.
        raise ProbeError("MFA_FAILED")
    result = obj.get("result")
    if not isinstance(result, dict):
        raise ProbeError("MFA_FAILED")
    if "appServerUrlV2" in result and _validate_region_origin(result["appServerUrlV2"]) is None:
        raise ProbeError("UNSUPPORTED_REGION")
    token = result.get("token")
    if not isinstance(token, str) or not token:
        raise ProbeError("MFA_FAILED")
    return token


def _discover(budget, token, terminal_uuid):
    """GET /v2/things on the fixed discovery host; cloud listing only, never camera API.

    A nonzero code alongside data is always a failure. A successful
    response may omit the code field entirely (per the upstream source),
    but the device-list schema is still fully validated: a camera record
    missing a valid, non-empty model or thingName is MALFORMED_RESPONSE,
    never silently dropped into a valid zero-count result.
    """
    status, data = _request(
        budget, DISCOVERY_HOST, "GET", "/v2/things", _cloud_headers(token, terminal_uuid), None
    )
    if status == 401:
        raise ProbeError("AUTH_FAILED")
    if status != 200:
        raise ProbeError("DISCOVERY_FAILED")
    obj = _parse_json_object(data)
    code, code_present = _extract_error_code(obj)
    if code_present and code != 0:
        raise ProbeError("DISCOVERY_FAILED")
    items = obj.get("data")
    if not isinstance(items, list):
        raise ProbeError("MALFORMED_RESPONSE")
    total = 0
    c545d = 0
    for item in items:
        if not isinstance(item, dict):
            raise ProbeError("MALFORMED_RESPONSE")
        if not isinstance(item.get("deviceType"), str) or not item["deviceType"].strip():
            raise ProbeError("MALFORMED_RESPONSE")
        if item.get("deviceType") != "SMART.IPCAMERA":
            continue
        thing_name = item.get("thingName")
        model = item.get("model")
        if not isinstance(thing_name, str) or not thing_name.strip():
            raise ProbeError("MALFORMED_RESPONSE")
        if not isinstance(model, str) or not model.strip():
            raise ProbeError("MALFORMED_RESPONSE")
        total += 1
        if model.strip().upper() == "C545D":
            c545d += 1
    return total, c545d


# -- native macOS dialog input ----------------------------------------------


def _as_applescript_literal(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _native_prompt(prompt_text):
    """One hidden-answer osascript dialog; the script text is always this constant.

    Returns (text, None) on an OK with non-empty, length-bounded input, or
    (None, reason) on cancel/timeout/empty/oversized input. Never prints or
    returns stderr/exception detail.
    """
    script_lines = [
        "set dlgResult to display dialog {prompt} default answer \"\" with title {title} "
        'with hidden answer buttons {{"Cancel", "OK"}} default button "OK"'.format(
            prompt=_as_applescript_literal(prompt_text),
            title=_as_applescript_literal(DIALOG_TITLE),
        ),
        "return text returned of dlgResult",
    ]
    args = [OSASCRIPT_PATH]
    for line in script_lines:
        args += ["-e", line]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=DIALOG_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    except KeyboardInterrupt:
        return None, "CANCELED"
    except OSError:
        return None, "SUBPROCESS_ERROR"
    if proc.returncode != 0:
        return None, "CANCELED"
    text = proc.stdout.rstrip("\n")
    if not (1 <= len(text) <= MAX_SECRET_LEN) or not text.strip():
        return None, "INVALID_INPUT"
    return text, None


# -- command implementations -------------------------------------------------


def _report(command, status, reason=None, extra=None):
    if reason is not None and reason not in ERROR_CODES:
        reason = "UNKNOWN_ERROR"
    report = {"tool": TOOL_NAME, "command": command, "status": status, "reason": reason}
    if extra:
        report.update(extra)
    return report


def check_command():
    """Fully offline: verifies the pinned CA and native-dialog availability only.

    An invalid pinned CA is reported as BLOCKED/CA_PIN_MISMATCH, distinct
    from the normal AUTH_INPUT_REQUIRED status used when the CA is fine and
    the tool is simply waiting on credentials it hasn't been given yet.
    """
    try:
        _load_pinned_der()
        ca_pin = "OK"
    except ProbeError:
        ca_pin = "MISMATCH"
    native_available = sys.platform == "darwin" and os.path.exists(OSASCRIPT_PATH)
    if ca_pin == "MISMATCH":
        status, reason = "BLOCKED", "CA_PIN_MISMATCH"
    else:
        status, reason = "AUTH_INPUT_REQUIRED", None
    return _report(
        "check",
        status,
        reason,
        {
            "ca_pin": ca_pin,
            "native_dialog": "AVAILABLE" if native_available else "UNAVAILABLE",
            "live_auth": "NOT_TESTED",
            "sd_download": "NOT_IMPLEMENTED",
        },
    )


def tls_check_command():
    """TLS handshake only, to the three fixed hosts; no HTTP/auth/device payload."""
    budget = _Budget()
    hosts_result = {}
    overall = "OK"
    for host in HOSTS:
        try:
            _tls_handshake_only(budget, host)
            hosts_result[host] = "OK"
        except ProbeError as exc:
            hosts_result[host] = exc.code
            overall = "FAILED"
    return _report(
        "tls-check",
        overall,
        None,
        {"hosts": hosts_result, "note": "TLS handshake only; no HTTP, auth, or device request sent"},
    )


def login_check_command():
    """Native-dialog login + optional email MFA, then cloud camera-inventory counts only."""
    if sys.platform != "darwin" or not os.path.exists(OSASCRIPT_PATH):
        return _report("login-check", "BLOCKED", "NATIVE_DIALOG_UNAVAILABLE")

    try:
        _load_pinned_der()
    except ProbeError as exc:
        return _report("login-check", "BLOCKED", exc.code)

    email, reason = _native_prompt("Tapo account email:")
    if email is None:
        return _report("login-check", "BLOCKED", reason)
    password, reason = _native_prompt("Tapo account password:")
    if password is None:
        return _report("login-check", "BLOCKED", reason)

    budget = _Budget()
    try:
        login_result = _login(budget, email, password)
    except ProbeError as exc:
        return _report("login-check", "BLOCKED", exc.code)
    finally:
        password = None  # noqa: F841 - best-effort drop; Python strings are immutable

    token = login_result["token"]
    account_host = login_result["account_host"]
    terminal_uuid = login_result["terminal_uuid"]

    if token is None:
        mfa = login_result["mfa"]
        if MFA_EMAIL not in mfa["types"]:
            return _report("login-check", "BLOCKED", "MFA_TYPE_UNSUPPORTED")
        try:
            _send_mfa(budget, account_host, email, terminal_uuid, mfa["process_id"])
        except ProbeError as exc:
            return _report("login-check", "BLOCKED", exc.code)
        code, reason = _native_prompt("Tapo email verification code:")
        if code is None:
            return _report("login-check", "BLOCKED", reason)
        try:
            token = _submit_mfa(budget, account_host, email, terminal_uuid, mfa["process_id"], code)
        except ProbeError as exc:
            return _report("login-check", "BLOCKED", exc.code)

    try:
        total, c545d = _discover(budget, token, terminal_uuid)
    except ProbeError as exc:
        return _report("login-check", "BLOCKED", exc.code)

    if c545d == 0:
        inventory_status = "TARGET_NOT_FOUND"
    elif c545d == 1:
        inventory_status = "CLOUD_INVENTORY_ONLY"
    else:
        inventory_status = "TARGET_AMBIGUOUS"
    extra = {
        "cameras_total": total,
        "c545d_candidates": c545d,
        "inventory_status": inventory_status,
        "note": "cloud account listing only; not camera auth, SD access, or a Fixed-lens PASS",
    }
    # Only a single cloud-listed candidate is CLOUD_INVENTORY_ONLY (never a
    # camera PASS); zero or multiple candidates must not report CLI
    # success/status SUCCESS.
    if inventory_status == "CLOUD_INVENTORY_ONLY":
        return _report("login-check", "SUCCESS", None, extra)
    return _report("login-check", "BLOCKED", inventory_status, extra)


# -- CLI ----------------------------------------------------------------------

_USAGE_HINTS = {
    "UNRECOGNIZED_ARGUMENT": "unrecognized argument; values are not echoed",
    "INVALID_COMMAND": "unknown command; use check, tls-check, or login-check",
    "MISSING_ARGUMENT": "a required argument is missing",
}


class _UsageError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _usage_reason(message):
    if message.startswith("unrecognized arguments"):
        return "UNRECOGNIZED_ARGUMENT"
    if "invalid choice" in message or "unknown parser" in message:
        return "INVALID_COMMAND"
    if message.startswith("the following arguments are required"):
        return "MISSING_ARGUMENT"
    return "INVALID_COMMAND"


class _QuietParser(argparse.ArgumentParser):
    """argparse echoes raw argv tokens in its error text; keep only a reason code."""

    def error(self, message):
        raise _UsageError(_usage_reason(message))


def build_parser():
    parser = _QuietParser(
        prog="ft_cloud_probe.py",
        description="OD-40 stdlib TP-Link/Tapo cloud-auth probe (no media/SD access).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_QuietParser)
    subparsers.add_parser("check", help="offline readiness check (no socket, no dialog)")
    subparsers.add_parser("tls-check", help="TLS handshake only to the three fixed cloud hosts")
    subparsers.add_parser("login-check", help="native dialog login + cloud camera inventory counts")
    return parser


def _write_json(report):
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main(argv=None):
    raw = sys.argv[1:] if argv is None else argv
    try:
        argv = list(raw)
    except TypeError:
        argv = None
    if argv is None or not all(isinstance(item, str) and "\x00" not in item for item in argv):
        report = _report("usage", "REJECTED", "INVALID_COMMAND", {"hint": _USAGE_HINTS["INVALID_COMMAND"]})
        _write_json(report)
        return 2
    try:
        args = build_parser().parse_args(argv)
    except _UsageError as exc:
        report = _report("usage", "REJECTED", exc.reason, {"hint": _USAGE_HINTS[exc.reason]})
        _write_json(report)
        return 2

    try:
        if args.command == "check":
            report = check_command()
            exit_code = 2
        elif args.command == "tls-check":
            report = tls_check_command()
            exit_code = 0 if report["status"] == "OK" else 1
        else:
            report = login_check_command()
            exit_code = 0 if report["status"] == "SUCCESS" else 2
    except KeyboardInterrupt:
        report = _report(args.command, "BLOCKED", "CANCELED")
        exit_code = 2
    except Exception:
        report = _report(args.command, "BLOCKED", "UNKNOWN_ERROR")
        exit_code = 1

    _write_json(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
