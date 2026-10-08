#!/usr/bin/env python3
"""FT-D0 OD-25: private local IPv4 input and offline connection-config check.

Python 3.9+ standard library only. This tool never opens a socket, resolves
a name, imports a camera library, or sends any credential anywhere. `check`
always reports BLOCKED: a well-formed local configuration file is never
evidence that the camera, route, or authentication works. `configure` writes
exactly one literal RFC1918 IPv4 address, entered twice with masked input,
to a fixed local file that git ignores, and reports only the local save
status, never a camera connection result.
"""
from __future__ import annotations

import argparse
import errno
import getpass
import ipaddress
import json
import os
import stat
import sys
import tempfile
import warnings
from pathlib import Path

SCHEMA_VERSION = 1
LENS_FIXED = "fixed"
MAX_CONFIG_BYTES = 4096
CONFIG_PATH = str(Path(__file__).resolve().parent.parent / "config.local.connection.json")

_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)

_RFC1918_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)

_USAGE_HINTS = {
    "UNRECOGNIZED_ARGUMENT": "unrecognized argument; values are not echoed",
    "INVALID_COMMAND": "unknown command; use configure or check",
    "MISSING_ARGUMENT": "a required argument is missing",
}


def parse_rfc1918_ipv4(text):
    """Return an ipaddress.IPv4Address for a literal, canonical RFC1918 input.

    Refuses names/URLs, IPv6, public/loopback/link-local/CGNAT addresses,
    and any input with embedded or surrounding whitespace. Returns None for
    anything that is not exactly such a literal.
    """
    if not isinstance(text, str) or text == "" or any(ch.isspace() for ch in text):
        return None
    try:
        addr = ipaddress.IPv4Address(text)
    except ValueError:
        return None
    if str(addr) != text:
        return None
    if not any(addr in network for network in _RFC1918_NETWORKS):
        return None
    return addr


def _result(command, status, reason=None, extra=None):
    report = {
        "tool": "ft_connect",
        "command": command,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reason": reason,
        "route": "NOT_TESTED",
        "auth": "NOT_TESTED",
        "download": "NOT_TESTED",
        "camera_requests": 0,
        "lens": "FIXED",
    }
    if extra:
        report.update(extra)
    return report


def prompt_rfc1918_ipv4_twice(prompt1, prompt2):
    """Collect the same literal RFC1918 IPv4 twice via masked input.

    getpass warnings (e.g. a fallback to visible input) are raised as errors
    rather than ever letting the value be echoed in plain text. Returns
    (text, None) on success or (None, reason) without ever returning or
    logging the entered value on failure.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            first = getpass.getpass(prompt1)
            second = getpass.getpass(prompt2)
        except getpass.GetPassWarning:
            return None, "MASKING_UNAVAILABLE"
    if first != second:
        return None, "MISMATCH"
    if parse_rfc1918_ipv4(first) is None:
        return None, "INVALID_INPUT"
    return first, None


def write_config_atomic(dest_path, camera_ipv4, lens=LENS_FIXED):
    """Create dest_path atomically with mode 0600; never overwrite or follow a symlink.

    Raises ValueError before creating any temp file if camera_ipv4/lens are
    not a valid config. A temp file is then created in the same directory,
    fsynced, then published by hard-linking it to dest_path. os.link() only
    succeeds when dest_path does not already exist (file or symlink), so an
    existing destination - including one created in a race right before this
    call - is never replaced or followed. The temp file descriptor and path
    are cleaned up on any setup/write/link failure. Returns True on success,
    False if dest_path already exists.
    """
    if parse_rfc1918_ipv4(camera_ipv4) is None or lens != LENS_FIXED:
        raise ValueError("refusing to write an invalid camera_ipv4/lens config")
    directory = os.path.dirname(dest_path) or "."
    payload = json.dumps(
        {"version": SCHEMA_VERSION, "camera_ipv4": camera_ipv4, "lens": lens},
        sort_keys=True,
    ) + "\n"
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".ft_connect-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as handle:
            os.fchmod(fd, 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp_path, dest_path)
        except FileExistsError:
            return False
        return True
    finally:
        try:
            os.close(fd)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _reject_duplicate_keys(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise ValueError("duplicate key in config JSON")
        seen.add(key)
    return dict(pairs)


def _validate_schema(data):
    if not isinstance(data, dict) or set(data.keys()) != {"version", "camera_ipv4", "lens"}:
        return None
    version = data["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != SCHEMA_VERSION:
        return None
    ipv4 = data["camera_ipv4"]
    if not isinstance(ipv4, str) or parse_rfc1918_ipv4(ipv4) is None:
        return None
    if data["lens"] != LENS_FIXED:
        return None
    return {"version": version, "camera_ipv4": ipv4, "lens": data["lens"]}


def read_config_safe(path):
    """Read a regular, owner-owned, mode 0600 config without following symlinks.

    Opens the parent directory and the final entry with O_NOFOLLOW so a
    symlinked config, a FIFO, or a directory is refused rather than followed
    or blocked on. The read is bounded to MAX_CONFIG_BYTES. Returns
    (data, None) or (None, reason) where reason is "MISSING" or "INVALID".
    """
    directory = os.path.dirname(path) or "."
    name = os.path.basename(path)
    try:
        dir_fd = os.open(directory, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW)
    except OSError as exc:
        return None, "MISSING" if exc.errno == errno.ENOENT else "INVALID"
    try:
        try:
            fd = os.open(name, os.O_RDONLY | _O_NOFOLLOW | _O_NONBLOCK, dir_fd=dir_fd)
        except OSError as exc:
            return None, "MISSING" if exc.errno == errno.ENOENT else "INVALID"
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                return None, "INVALID"
            if stat.S_IMODE(st.st_mode) != 0o600:
                return None, "INVALID"
            if st.st_uid != os.getuid():
                return None, "INVALID"
            if st.st_size > MAX_CONFIG_BYTES:
                return None, "INVALID"
            raw = os.read(fd, MAX_CONFIG_BYTES + 1)
        finally:
            os.close(fd)
    finally:
        os.close(dir_fd)
    if len(raw) > MAX_CONFIG_BYTES:
        return None, "INVALID"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "INVALID"
    try:
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ValueError:
        return None, "INVALID"
    validated = _validate_schema(data)
    if validated is None:
        return None, "INVALID"
    return validated, None


def configure_command(dest_path):
    """Run the interactive configure flow against an explicit destination path.

    Success reports local saved-config status only ("CONFIGURED"); this is
    never a camera connection result.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return _result("configure", "BLOCKED", "NOT_INTERACTIVE")
    try:
        ipv4, reason = prompt_rfc1918_ipv4_twice(
            "Camera IPv4 (RFC1918, masked): ", "Re-enter camera IPv4 (masked): "
        )
    except (EOFError, KeyboardInterrupt):
        return _result("configure", "BLOCKED", "INPUT_INTERRUPTED")
    if ipv4 is None:
        return _result("configure", "BLOCKED", reason)
    try:
        written = write_config_atomic(dest_path, ipv4, LENS_FIXED)
    except (EOFError, KeyboardInterrupt):
        return _result("configure", "BLOCKED", "INPUT_INTERRUPTED")
    except (OSError, ValueError):
        return _result("configure", "BLOCKED", "WRITE_FAILED")
    if not written:
        return _result("configure", "BLOCKED", "CONFIG_EXISTS")
    return _result("configure", "CONFIGURED")


def check_command(dest_path):
    """Run the offline check against an explicit config path. Never returns PASS.

    Always reports route/auth/download as NOT_TESTED and camera_requests 0,
    including when the config read itself fails unexpectedly; no exception
    detail or file content is ever included in the report.
    """
    try:
        data, reason = read_config_safe(dest_path)
    except Exception:
        data, reason = None, "INTERNAL_ERROR"
    if reason == "MISSING":
        endpoint = "missing"
    elif data is not None:
        endpoint = "configured"
    else:
        endpoint = "invalid"
    extra = {
        "endpoint": endpoint,
        "route": "NOT_TESTED",
        "auth": "NOT_TESTED",
        "download": "NOT_TESTED",
        "camera_requests": 0,
        "lens": "FIXED",
    }
    return _result("check", "BLOCKED", None, extra)


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


def _write_json(report):
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _usage_failure(reason):
    report = _result("usage", "REJECTED", reason, {"hint": _USAGE_HINTS[reason]})
    _write_json(report)
    return 2


def build_parser():
    parser = _QuietParser(
        prog="ft_connect.py",
        description="OD-25 private local IPv4 input and offline connection-config check.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_QuietParser)

    configure = subparsers.add_parser("configure", help="masked interactive RFC1918 IPv4 input")
    configure.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    check = subparsers.add_parser("check", help="offline config/schema check (never a connection PASS)")
    check.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv=None):
    raw = sys.argv[1:] if argv is None else argv
    try:
        argv = list(raw)
    except TypeError:
        return _usage_failure("INVALID_COMMAND")
    if not all(isinstance(item, str) and "\x00" not in item for item in argv):
        return _usage_failure("INVALID_COMMAND")
    try:
        args = build_parser().parse_args(argv)
    except _UsageError as exc:
        return _usage_failure(exc.reason)

    try:
        if args.command == "configure":
            report = configure_command(CONFIG_PATH)
            exit_code = 0 if report["status"] == "CONFIGURED" else 2
        else:
            report = check_command(CONFIG_PATH)
            exit_code = 2
    except (EOFError, KeyboardInterrupt):
        report = _result(args.command, "BLOCKED", "INPUT_INTERRUPTED")
        exit_code = 2
    except Exception:
        report = _result(
            args.command,
            "BLOCKED",
            "INTERNAL_ERROR",
            extra={
                "endpoint": "invalid",
                "route": "NOT_TESTED",
                "auth": "NOT_TESTED",
                "download": "NOT_TESTED",
                "camera_requests": 0,
                "lens": "FIXED",
            } if args.command == "check" else None,
        )
        exit_code = 2

    _write_json(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
