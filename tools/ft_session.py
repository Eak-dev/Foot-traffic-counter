"""Local Keychain-backed Tapo lease. Public reports never contain credentials.

Run as ``python3 -m tools.ft_session status|start|use|sd-check|fixed-check|media-check|refresh-check|forget``.
Only explicit start opens private native input. No daemon or automatic login.
"""
import contextlib
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

from tools import ft_cloud_probe as cloud

LEASE_SECONDS = 172800
APP_DIR = Path.home() / ".local/share/foot-traffic-counter"
HELPER = APP_DIR / "bin/ft-keychain"
ERRORS = frozenset({
    "REAUTH_REQUIRED", "EXPIRED", "CLOCK_ROLLBACK", "INVALID_SESSION",
    "TARGET_MISMATCH", "SESSION_LOCKED", "STORE_DENIED", "STORE_ERROR",
    "HELPER_UNAVAILABLE", "SESSION_BUSY", "INVALID_INPUT", "UNKNOWN_ERROR",
    "REVISION_CONFLICT",
}) | cloud.ERROR_CODES
FIELDS = frozenset({"schema_version", "token", "refresh_token", "terminal_uuid",
    "issued_at", "hard_expires_at", "last_seen", "target_digest", "device_digest",
    "account_host", "revision"})
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class SessionError(Exception):
    def __init__(self, code):
        self.code = code if code in ERRORS else "UNKNOWN_ERROR"
        super().__init__(self.code)


def _json(data):
    try:
        return json.loads(data, object_pairs_hook=cloud._no_duplicate_keys,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, cloud.ProbeError):
        raise SessionError("INVALID_SESSION") from None


def _private_path(path, directory=False):
    try:
        info = path.lstat()
        valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if not valid_type or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise SessionError("STORE_DENIED")
        # Reject symlink ancestors, without traversing their contents.
        if any(p.is_symlink() for p in path.parents):
            raise SessionError("STORE_DENIED")
    except OSError:
        raise SessionError("HELPER_UNAVAILABLE") from None


class KeychainStore:
    """Fixed namespace; all secret input/output stays in private parent pipes."""
    def __init__(self, account="session-v1"):
        if account not in ("session-v1", "selftest-v1"):
            raise SessionError("INVALID_INPUT")
        self.account = account

    def _call(self, op, value=None):
        _private_path(APP_DIR, True)
        _private_path(HELPER.parent, True)
        _private_path(HELPER)
        request = {"op": op, "account": self.account}
        if op == "store":
            request["value"] = value
        try:
            raw = json.dumps(request, allow_nan=False, separators=(",", ":")).encode()
            if len(raw) > 65536:
                raise SessionError("INVALID_SESSION")
            proc = subprocess.run([str(HELPER)], input=raw, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=15,
                env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"})
        except (OSError, ValueError, subprocess.SubprocessError):
            raise SessionError("STORE_ERROR") from None
        if proc.returncode or len(proc.stdout) > 65536:
            raise SessionError("STORE_ERROR")
        result = _json(proc.stdout)
        if not isinstance(result, dict):
            raise SessionError("STORE_ERROR")
        status = result.get("status")
        if status == "MISSING" and op == "load":
            return None
        if status != "OK":
            raise SessionError(status if status in {"SESSION_LOCKED", "STORE_DENIED"} else "STORE_ERROR")
        return result.get("value")

    def load(self):
        return self._call("load")

    def save(self, value):
        self._call("store", value)

    def delete(self):
        self._call("delete")


@contextlib.contextmanager
def session_lock():
    _private_path(APP_DIR, True)
    fd = None
    try:
        fd = os.open(str(APP_DIR / "session.lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise SessionError("STORE_DENIED")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SessionError("SESSION_BUSY") from None
        yield
    except OSError:
        raise SessionError("STORE_ERROR") from None
    finally:
        if fd is not None:
            os.close(fd)


def _text(value, optional=False, max_length=8192):
    return (optional and value is None) or (
        isinstance(value, str) and 1 <= len(value) <= max_length
        and all(33 <= ord(c) <= 126 for c in value))


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate(record, target=None):
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise SessionError("INVALID_SESSION")
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise SessionError("INVALID_SESSION")
    if type(record["revision"]) is not int or not 1 <= record["revision"] <= 2**53:
        raise SessionError("INVALID_SESSION")
    if not _text(record["token"]) or not _text(record["refresh_token"], optional=True):
        raise SessionError("INVALID_SESSION")
    if not _text(record["terminal_uuid"], max_length=128) or record["account_host"] != cloud.ACCOUNT_HOST:
        raise SessionError("INVALID_SESSION")
    if any(not isinstance(record[k], str) or not DIGEST.fullmatch(record[k]) for k in ("target_digest", "device_digest")):
        raise SessionError("INVALID_SESSION")
    if target is not None and record["target_digest"] != target:
        raise SessionError("TARGET_MISMATCH")
    if any(not _number(record[k]) for k in ("issued_at", "hard_expires_at", "last_seen")):
        raise SessionError("INVALID_SESSION")
    if record["hard_expires_at"] != record["issued_at"] + LEASE_SECONDS or not record["issued_at"] <= record["last_seen"] < record["hard_expires_at"]:
        raise SessionError("INVALID_SESSION")
    return record


class Lease:
    def __init__(self, record, wall, mono):
        self.record, self.wall, self.mono = record, wall, mono
        self.initial_wall, self.initial_mono = wall(), mono()
        self.previous_wall = record["last_seen"]
        self.check()

    def check(self):
        now, elapsed = self.wall(), self.mono() - self.initial_mono
        if not _number(now) or elapsed < 0 or now < self.previous_wall:
            raise SessionError("CLOCK_ROLLBACK")
        if max(now, self.initial_wall + elapsed) >= self.record["hard_expires_at"]:
            raise SessionError("EXPIRED")
        self.previous_wall = now
        return now


class GuardBudget(cloud._Budget):
    def __init__(self, lease):
        super().__init__()
        self.lease = lease

    def check_time(self):
        self.lease.check()
        super().check_time()


class SessionManager:
    def __init__(self, store=None, wall=time.time, mono=time.monotonic, lock=session_lock):
        self.store = store if store is not None else KeychainStore()
        self.wall, self.mono, self.lock = wall, mono, lock
        self.stage = None

    def _save(self, record, expected_revision):
        validate(record)
        previous = self.store.load()
        actual = previous.get("revision") if isinstance(previous, dict) else None
        if actual != expected_revision:
            raise SessionError("REVISION_CONFLICT")
        self.store.save(record)
        if self.store.load() != record:
            raise SessionError("STORE_ERROR")

    def _touch(self, record, lease):
        revision = record["revision"]
        record["last_seen"] = lease.check()
        record["revision"] += 1
        self._save(record, revision)

    def _selected(self, budget, record):
        found = cloud._discover(budget, record["token"], record["terminal_uuid"], record["target_digest"])
        if found[3] != 1 or not isinstance(found[5], dict) or found[4] not in ("EXACT", "VARIANT"):
            raise SessionError("TARGET_MISMATCH")
        selected = found[5]
        if not cloud._validate_canonical_app_server(selected.get("app_server")):
            raise SessionError("TARGET_MISMATCH")
        device = selected.get("thing_name")
        if not isinstance(device, str) or not device or len(device) > 1024:
            raise SessionError("TARGET_MISMATCH")
        digest = hashlib.sha256(device.encode()).hexdigest()
        if record["device_digest"] and digest != record["device_digest"]:
            raise SessionError("TARGET_MISMATCH")
        return selected, digest

    def _refresh(self, budget, record, lease):
        if record["refresh_token"] is None:
            self.store.delete()
            raise SessionError("REAUTH_REQUIRED")
        lease.check()
        try:
            result = cloud._refresh(budget, record["refresh_token"], record["terminal_uuid"])
        except cloud.ProbeError as exc:
            if exc.detail == "AUTH_INVALID_HTTP401":
                self.store.delete()
                raise SessionError("REAUTH_REQUIRED") from None
            raise
        lease.check()
        updated = copy.deepcopy(record)
        updated.update(token=result.get("token"), refresh_token=result.get("refresh_token"))
        validate(updated)
        updated["last_seen"] = lease.check()
        updated["revision"] += 1
        self._save(updated, record["revision"])
        record.update(updated)

    def _input(self, prompt, stage, timeout_s=cloud.DIALOG_TIMEOUT_S):
        """Retry only a locally invalid field, never credentials rejected by Tapo."""
        self.stage = stage
        began = self.mono()
        for attempt in range(3):
            remaining = timeout_s - (self.mono() - began)
            if remaining <= 0:
                raise SessionError("TIMEOUT")
            label = prompt if attempt == 0 else "Please fill this field (1-256 characters). " + prompt
            value, reason = cloud._native_prompt(label, timeout_s=remaining)
            if value is not None:
                return value
            if reason != "INVALID_INPUT":
                raise SessionError(reason)
        raise SessionError("INVALID_INPUT")

    def _start(self, target):
        # Refuse an existing item: use/forget is explicit, no repeated login by default.
        if self.store.load() is not None:
            raise SessionError("SESSION_BUSY")
        cloud._load_pinned_der()
        email = self._input("Tapo account email (start 48-hour session):", "EMAIL_INPUT")
        password = self._input("Tapo account password (not saved):", "PASSWORD_INPUT")
        budget = cloud._Budget()
        try:
            self.stage = "LOGIN"
            auth = cloud._login(budget, email, password, refresh_token_needed=True)
            if auth["token"] is None:
                mfa = auth["mfa"]
                if cloud.MFA_EMAIL not in mfa["types"]:
                    raise SessionError("MFA_TYPE_UNSUPPORTED")
                self.stage = "MFA_SEND"
                cloud._send_mfa(budget, auth["account_host"], email, auth["terminal_uuid"], password)
                password = None
                code = self._input("Tapo email verification code:", "OTP_INPUT", timeout_s=cloud.TOTAL_BUDGET_S)
                self.stage = "MFA_SUBMIT"
                result = cloud._submit_mfa(budget, auth["account_host"], email, auth["terminal_uuid"], mfa["process_id"], code, refresh_token_needed=True)
                auth.update(result)
                code = None
        finally:
            password, email = None, None
        issued = self.wall()
        record = {"schema_version": 1, "token": auth["token"], "refresh_token": auth.get("refresh_token") or None,
            "terminal_uuid": auth["terminal_uuid"], "issued_at": issued, "last_seen": issued,
            "hard_expires_at": issued + LEASE_SECONDS, "target_digest": target,
            "device_digest": "", "account_host": cloud.ACCOUNT_HOST, "revision": 1}
        # Validate credentials before discovery without inventing a selected device.
        validate(dict(record, device_digest="0" * 64))
        lease = Lease(record, self.wall, self.mono)
        guarded = GuardBudget(lease)
        guarded.start, guarded.requests = budget.start, budget.requests
        self.stage = "DISCOVERY"
        _, record["device_digest"] = self._selected(guarded, record)
        record["last_seen"] = lease.check()
        self.stage = "SESSION_STORE"
        self._save(record, None)
        return self._public(record, "SESSION_CREATED", lease)

    def _public(self, record, state, lease):
        now = lease.check()
        return {"status": "SUCCESS", "session_state": state,
            "remaining_seconds": max(0, int(record["hard_expires_at"] - now)),
            "expires_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record["hard_expires_at"])),
            "refresh_available": record["refresh_token"] is not None}

    def command(self, command, target=None, on_selected_camera=None, callback_with_guard=False):
        self.stage = None
        if type(callback_with_guard) is not bool:
            return {"status":"BLOCKED","reason":"INVALID_INPUT"}
        if command not in {"status", "start", "use", "refresh-check", "forget", "sd-check", "media-check", "fixed-check"}:
            return {"status": "BLOCKED", "reason": "INVALID_INPUT"}
        if command in {"start", "use", "refresh-check", "sd-check", "media-check", "fixed-check"} and (not isinstance(target, str) or not DIGEST.fullmatch(target)):
            return {"status": "BLOCKED", "reason": "INVALID_INPUT"}
        if command == "media-check":
            from tools.ft_media_probe import LIVE_TRIAL_ENABLED
            if not LIVE_TRIAL_ENABLED:
                return {"status": "BLOCKED", "reason": "MEDIA_TRIAL_NOT_ENABLED"}
        try:
            with self.lock():
                try:
                    if command == "forget":
                        self.store.delete()
                        return {"status": "SUCCESS", "session_state": "FORGOTTEN"}
                    if command == "start":
                        return self._start(target)
                    record = self.store.load()
                    if record is None:
                        raise SessionError("REAUTH_REQUIRED")
                    validate(record, target)
                    lease = Lease(record, self.wall, self.mono)
                    self._touch(record, lease)
                    if command == "status":
                        return self._public(record, "ACTIVE", lease)
                    budget = GuardBudget(lease)
                    refreshed = False
                    if command == "refresh-check":
                        self._refresh(budget, record, lease)
                        refreshed = True
                    try:
                        selected, _ = self._selected(budget, record)
                    except cloud.ProbeError as exc:
                        if exc.detail != "AUTH_INVALID_HTTP401":
                            raise
                        if refreshed:
                            self.store.delete()
                            raise SessionError("REAUTH_REQUIRED") from None
                        self._refresh(budget, record, lease)
                        refreshed = True
                        try:
                            selected, _ = self._selected(budget, record)
                        except cloud.ProbeError as retry_exc:
                            if retry_exc.detail == "AUTH_INVALID_HTTP401":
                                self.store.delete()
                                raise SessionError("REAUTH_REQUIRED") from None
                            raise
                    self._touch(record, lease)
                    extra = {}
                    lease.check()
                    if command == "sd-check":
                        from tools.ft_sd_probe import probe_selected_device
                        extra["sd_probe"] = probe_selected_device(record["token"], record["terminal_uuid"], selected,
                            "20261012", session_guard=lease.check)
                    elif command == "fixed-check":
                        from tools.ft_sd_probe import probe_fixed_metadata
                        extra["sd_probe"] = probe_fixed_metadata(record["token"], record["terminal_uuid"], selected,
                            session_guard=lease.check)
                    elif command == "media-check":
                        from tools.ft_media_probe import sample_selected_device
                        extra["media_probe"] = sample_selected_device(record["token"], record["terminal_uuid"], selected,
                            session_guard=lease.check)
                    elif on_selected_camera is not None:
                        if callback_with_guard:
                            extra["callback"] = on_selected_camera(record["token"], record["terminal_uuid"], selected, lease.check)
                        else:
                            extra["callback"] = on_selected_camera(record["token"], record["terminal_uuid"], selected)
                    self._touch(record, lease)
                    result = self._public(record, "REFRESHED" if refreshed else "REUSED", lease)
                    result.update(extra)
                    result["auth_requests"] = budget.requests
                    if extra.get("sd_probe", {}).get("status") == "BLOCKED":
                        result["status"] = "BLOCKED"
                        result["reason"] = "SD_PROBE_BLOCKED"
                    if extra.get("media_probe", {}).get("status") == "BLOCKED":
                        result["status"] = "BLOCKED"
                        result["reason"] = "MEDIA_PROBE_BLOCKED"
                    return result
                except SessionError as exc:
                    if exc.code == "EXPIRED":
                        try:
                            self.store.delete()
                        except SessionError:
                            return {"status": "BLOCKED", "reason": "EXPIRED", "cleanup_pending": True}
                    raise
        except (SessionError, cloud.ProbeError) as exc:
            result = {"status": "BLOCKED", "reason": exc.code}
            if self.stage in cloud.STAGES | {"SESSION_STORE"}:
                result["stage"] = self.stage
            if getattr(exc, "detail", None) in cloud.DETAIL_CODES:
                result["detail"] = exc.detail
            return result
        except Exception:
            return {"status": "BLOCKED", "reason": "UNKNOWN_ERROR"}


def load_target():
    path = Path(__file__).resolve().parent.parent / "config.local.cloud-target.json"
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise SessionError("INVALID_INPUT")
            data = stream.read(1025)
        if len(data) > 1024:
            raise SessionError("INVALID_INPUT")
        obj = _json(data)
        if not isinstance(obj, dict) or set(obj) != {"schema_version", "name_sha256", "lens"} or type(obj["schema_version"]) is not int or obj["schema_version"] != 1 or obj["lens"] != "FIXED":
            raise SessionError("INVALID_INPUT")
        if not isinstance(obj["name_sha256"], str) or not DIGEST.fullmatch(obj["name_sha256"]):
            raise SessionError("INVALID_INPUT")
        return obj["name_sha256"]
    except OSError:
        raise SessionError("INVALID_INPUT") from None


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) != 1 or args[0] not in {"status", "start", "use", "sd-check", "media-check", "fixed-check", "refresh-check", "forget"}:
            raise SessionError("INVALID_INPUT")
        target = load_target() if args[0] not in {"status", "forget"} else None
        report = SessionManager().command(args[0], target)
    except SessionError as exc:
        report = {"status": "BLOCKED", "reason": exc.code}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "SUCCESS" else 2


if __name__ == "__main__":
    sys.exit(main())
