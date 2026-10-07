#!/usr/bin/env python3
"""FT-D0 preparation tool: read-only `doctor` and local `inventory`.

Python 3.9+ standard library only. This is PREPARATION ONLY:
it is not a camera downloader, does not decode video, and never writes
to the directories it inspects. A `doctor` exit code of 0 means the
preparation checks passed; it never means live-ready.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import math
import os
import platform
import shutil
import stat
import sys

SCHEMA_VERSION = 1
MODE = "PREPARATION_ONLY"
DEFAULT_MIN_FREE_GIB = 10.0
THRESHOLD_SOURCE = "PROPOSED_NOT_OWNER_APPROVED"
CHUNK_SIZE = 1024 * 1024
CLIP_SUFFIX = ".mp4"
GIB = 1024 ** 3
INFO_EXECUTABLES = ("git", "gh", "claude", "python3")
NOT_REQUIRED_EXECUTABLES = ("ffprobe", "tailscale")

_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_IDENTITY_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
_ROOT_OPEN_REASONS = {
    errno.ENOENT: "INPUT_MISSING",
    errno.ELOOP: "INPUT_IS_SYMLINK",
    errno.ENOTDIR: "INPUT_NOT_DIRECTORY",
}
_USAGE_HINTS = {
    "UNRECOGNIZED_ARGUMENT": "unrecognized argument; values are not echoed",
    "INVALID_COMMAND": "unknown command; use doctor or inventory",
    "MISSING_ARGUMENT": "a required argument is missing",
    "INVALID_MIN_FREE_GIB": "--min-free-gib must be a finite number greater than 0",
    "INVALID_ARGUMENT": "invalid argument value",
    "INVALID_ARGV": "arguments must be text without NUL characters",
}


def parse_positive_finite(text):
    """argparse type: accept only finite numbers greater than zero."""
    try:
        value = float(text)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("must be a number")
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than 0")
    return value


def check_python(version_info):
    ok = tuple(version_info[:2]) >= (3, 9)
    return {
        "status": "PASS" if ok else "BLOCKED",
        "version": "%d.%d.%d" % tuple(version_info[:3]),
    }


def disk_result(free_bytes, min_free_gib):
    enough = free_bytes / GIB >= min_free_gib
    return {
        "status": "PASS" if enough else "BLOCKED",
        "reason": None if enough else "DISK_BELOW_THRESHOLD",
        "free_gib": round(free_bytes / GIB, 2),
        "min_free_gib": min_free_gib,
        "threshold_source": THRESHOLD_SOURCE,
    }


def check_disk(disk_path, min_free_gib):
    """Read-only free-space check. Never reports the path itself."""
    if not isinstance(disk_path, str) or "\x00" in disk_path or not os.path.isdir(disk_path):
        reason = "DISK_PATH_INVALID"
    else:
        try:
            return disk_result(shutil.disk_usage(disk_path).free, min_free_gib)
        except OSError:
            reason = "DISK_CHECK_ERROR"
    return {
        "status": "BLOCKED",
        "reason": reason,
        "free_gib": None,
        "min_free_gib": min_free_gib,
        "threshold_source": THRESHOLD_SOURCE,
    }


def build_doctor_report(python_info, os_info, disk, executables):
    reasons = []
    if python_info["status"] != "PASS":
        reasons.append("PYTHON_TOO_OLD")
    if disk["status"] != "PASS":
        reasons.append(disk["reason"])
    return {
        "tool": "ft_data",
        "command": "doctor",
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "preparation": {
            "status": "BLOCKED" if reasons else "PASS",
            "reasons": reasons,
        },
        "live_ready": False,
        "live_ready_basis": "CAMERA_ROUTE_CREDENTIALS_STORAGE_POLICY_UNKNOWN",
        "checks": {"python": python_info, "os": os_info, "disk": disk},
        "executables": executables,
        "camera": {
            "status": "UNKNOWN",
            "model": "UNKNOWN",
            "firmware": "UNKNOWN",
            "route": "UNKNOWN",
            "credentials": "UNKNOWN_NOT_CHECKED",
        },
        "not_required_for_d0": ["ffprobe", "ml", "google_sheets", "cloud", "tailscale"],
    }


def collect_doctor(disk_path, min_free_gib, which=None):
    """Read-only checks. Executables are only located on PATH, never run."""
    which = which or shutil.which
    os_info = {
        "status": "INFO",
        "system": platform.system(),
        "machine": platform.machine(),
        "mac_version": platform.mac_ver()[0] or None,
    }
    executables = {}
    for name in INFO_EXECUTABLES:
        executables[name] = {
            "status": "INFO",
            "present": which(name) is not None,
            "functional": "UNKNOWN_NOT_CHECKED",
        }
    for name in NOT_REQUIRED_EXECUTABLES:
        executables[name] = {
            "status": "NOT_REQUIRED_FOR_D0",
            "present": which(name) is not None,
            "functional": "UNKNOWN_NOT_CHECKED",
        }
    return build_doctor_report(
        check_python(sys.version_info),
        os_info,
        check_disk(disk_path, min_free_gib),
        executables,
    )


def _new_counters():
    return {
        "unreadable": 0,
        "changed": 0,
        "unreadable_dirs": 0,
        "symlink_skipped": 0,
        "non_regular_skipped": 0,
        "other_files_ignored": 0,
    }


def _as_text_path(value):
    """Return value as a NUL-free str path, or None if it is not one."""
    try:
        text = os.fspath(value)
    except TypeError:
        return None
    if not isinstance(text, str) or "\x00" in text:
        return None
    return text


def _normalize_root(text):
    """Drop '.' segments and repeated or trailing separators; refuse '..'.

    'X/.' and 'X/' name the same entry as 'X', so removing them leaves the
    selected entry as the final component that O_NOFOLLOW checks. 'X/..'
    depends on what X resolves to through symlinks, so it is refused rather
    than resolved lexically.
    """
    parts = text.split(os.sep)
    if ".." in parts:
        return None
    kept = [part for part in parts if part not in ("", ".")]
    if text.startswith(os.sep):
        return os.sep + os.sep.join(kept)
    return os.sep.join(kept) or os.curdir


def _same_file_state(current, expected):
    """True when two stat results describe the same, unchanged inode state."""
    return all(getattr(current, field, None) == getattr(expected, field, None) for field in _IDENTITY_FIELDS)


def _open_dir_at(dir_fd, name):
    """Open a directory entry without following a final symlink.

    dir_fd=None opens name as a path; used only for the filesystem root.
    Raises OSError: ELOOP for a symlink, ENOTDIR for a non-directory.
    O_DIRECTORY is not passed because ELOOP vs ENOTDIR ordering for a symlink
    differs between Unix systems; the fstat type check is what decides here.
    """
    fd = os.open(name, os.O_RDONLY | _O_NOFOLLOW | _O_NONBLOCK, dir_fd=dir_fd)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(errno.ENOTDIR, "not a directory")
    except Exception:
        os.close(fd)
        raise
    return fd


def _open_root(text):
    """Open the selected root without following its final entry.

    Returns (fd, None) or (None, reason). Parent components may be symlinks
    (platform aliases such as macOS /tmp). Only the selected entry is opened
    with O_NOFOLLOW, so a symlink root is refused in any spelling.
    """
    path = _normalize_root(text)
    if path is None:
        return None, "INPUT_AMBIGUOUS_PATH"
    parent, name = os.path.split(path)
    try:
        if not name:
            return _open_dir_at(None, path), None
        parent_fd = os.open(parent or os.curdir, os.O_RDONLY | _O_DIRECTORY)
        try:
            return _open_dir_at(parent_fd, name), None
        finally:
            os.close(parent_fd)
    except OSError as exc:
        return None, _ROOT_OPEN_REASONS.get(exc.errno, "INPUT_UNREADABLE")


def _hash_clip(dir_fd, name, expected):
    """Stream SHA256 of one regular file, or refuse it if it changed while read.

    Reads at most the size seen when the file was opened, so a file that keeps
    growing cannot stall the scan. The open descriptor and the directory entry
    are compared with the expected stat before and after reading. This narrows
    the window in which a change can go unnoticed. It is not an atomic
    filesystem snapshot.
    Returns ((digest, size), None) or (None, "CHANGED" | "UNREADABLE").
    """
    try:
        fd = os.open(name, os.O_RDONLY | _O_NOFOLLOW | _O_NONBLOCK, dir_fd=dir_fd)
    except OSError as exc:
        return None, "CHANGED" if exc.errno in (errno.ELOOP, errno.ENOENT) else "UNREADABLE"
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or not _same_file_state(opened, expected):
            return None, "CHANGED"
        limit = opened.st_size
        digest = hashlib.sha256()
        size = 0
        while size < limit:
            chunk = os.read(fd, min(CHUNK_SIZE, limit - size))
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        if size != limit or not _same_file_state(os.fstat(fd), opened):
            return None, "CHANGED"
        current = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        if not _same_file_state(current, opened):
            return None, "CHANGED"
        return (digest.hexdigest(), size), None
    except OSError:
        return None, "UNREADABLE"
    finally:
        os.close(fd)


def _scan_subdirectory(parent_fd, name, expected, counters, records):
    """Recurse into a subdirectory only if the entry is still the same directory."""
    try:
        fd = _open_dir_at(parent_fd, name)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR, errno.ENOENT):
            counters["changed"] += 1
        else:
            counters["unreadable_dirs"] += 1
        return
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
            counters["changed"] += 1
            return
        _scan_directory(fd, counters, records)
    finally:
        os.close(fd)


def _scan_directory(dir_fd, counters, records):
    """Hash regular .mp4 files in one directory, anchored at dir_fd.

    Symlinks are counted and never followed. Subdirectories are reopened with
    O_NOFOLLOW relative to this descriptor, so an entry swapped for a link
    after listing is refused rather than followed.
    """
    listing = []
    try:
        with os.scandir(dir_fd) as iterator:
            for entry in iterator:
                try:
                    listing.append((entry.name, entry.stat(follow_symlinks=False)))
                except OSError:
                    counters["unreadable"] += 1
    except OSError:
        counters["unreadable_dirs"] += 1
        return
    for name, st in listing:
        mode = st.st_mode
        if stat.S_ISLNK(mode):
            counters["symlink_skipped"] += 1
        elif stat.S_ISDIR(mode):
            _scan_subdirectory(dir_fd, name, st, counters, records)
        elif not name.lower().endswith(CLIP_SUFFIX):
            counters["other_files_ignored"] += 1
        elif stat.S_ISREG(mode):
            result, error = _hash_clip(dir_fd, name, st)
            if error == "CHANGED":
                counters["changed"] += 1
            elif error:
                counters["unreadable"] += 1
            else:
                digest, size = result
                records.append({"sha256": digest, "size_bytes": size})
        else:
            counters["non_regular_skipped"] += 1


def _duplicate_groups(records):
    by_hash = {}
    for record in records:
        by_hash.setdefault(record["sha256"], []).append(record)
    groups = []
    for digest in sorted(by_hash):
        members = by_hash[digest]
        if len(members) < 2:
            continue
        group_id = "G%04d" % (len(groups) + 1)
        for member in members:
            member["duplicate_group"] = group_id
        groups.append({
            "group_id": group_id,
            "size_bytes": members[0]["size_bytes"],
            "file_ids": [member["file_id"] for member in members],
        })
    return groups


def _inventory_report(status, reason, files, groups, counters):
    return {
        "tool": "ft_data",
        "command": "inventory",
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "status": status,
        "reason": reason,
        "source_catalog_completeness": "UNKNOWN",
        "complete_day": False,
        "time_source_policy": "UNKNOWN_NOT_INFERRED_FROM_NAME_OR_MTIME",
        "summary": {
            "clips_hashed": len(files),
            "total_bytes": sum(item["size_bytes"] for item in files),
            "empty_clips": sum(1 for item in files if item["size_bytes"] == 0),
            "duplicate_groups": len(groups),
            "duplicate_clips": sum(len(group["file_ids"]) for group in groups),
            "unreadable_clips": counters["unreadable"],
            "changed_during_scan": counters["changed"],
            "unreadable_dirs": counters["unreadable_dirs"],
            "symlinks_skipped": counters["symlink_skipped"],
            "non_regular_skipped": counters["non_regular_skipped"],
            "other_files_ignored": counters["other_files_ignored"],
        },
        "duplicate_groups": groups,
        "files": files,
    }


def scan_inventory(root):
    """Hash regular .mp4 files under root. Event time is never inferred.

    Boundary: the selected root and every entry below it are opened relative
    to a descriptor and never followed when they are symlinks. Parent path
    components are not checked, so platform aliases such as macOS /tmp work.
    This is not a sandbox for the whole filesystem.
    """
    counters = _new_counters()
    if root is None:
        return _inventory_report("REJECTED", "INPUT_MISSING", [], [], counters)
    text = _as_text_path(root)
    if text is None:
        return _inventory_report("REJECTED", "INPUT_INVALID", [], [], counters)
    if not text:
        return _inventory_report("REJECTED", "INPUT_MISSING", [], [], counters)

    root_fd, reason = _open_root(text)
    if reason:
        return _inventory_report("REJECTED", reason, [], [], counters)
    records = []
    try:
        _scan_directory(root_fd, counters, records)
    finally:
        os.close(root_fd)

    records.sort(key=lambda record: (record["sha256"], record["size_bytes"]))
    for index, record in enumerate(records, 1):
        record["file_id"] = "F%04d" % index
        record["event_start"] = None
        record["time_source"] = "UNKNOWN"
        record["duplicate_group"] = None
    groups = _duplicate_groups(records)

    incomplete = counters["unreadable"] or counters["changed"] or counters["unreadable_dirs"]
    status = "INCOMPLETE" if incomplete else "OK"
    return _inventory_report(status, None, records, groups, counters)


def _format_text(report):
    if report["command"] == "doctor":
        lines = [
            "preparation: %s" % report["preparation"]["status"],
            "reasons: %s" % (", ".join(report["preparation"]["reasons"]) or "none"),
            "live_ready: false (%s)" % report["live_ready_basis"],
            "python: %s" % report["checks"]["python"]["status"],
            "disk: %s free_gib=%s min_free_gib=%s" % (
                report["checks"]["disk"]["status"],
                report["checks"]["disk"]["free_gib"],
                report["checks"]["disk"]["min_free_gib"],
            ),
        ]
        for name, item in sorted(report["executables"].items()):
            lines.append("executable %s: present=%s" % (name, item["present"]))
        lines.append("camera: UNKNOWN (not checked in FT-D0)")
        return "\n".join(lines) + "\n"
    summary = report["summary"]
    lines = [
        "status: %s%s" % (report["status"], " (%s)" % report["reason"] if report["reason"] else ""),
        "clips_hashed: %d" % summary["clips_hashed"],
        "total_bytes: %d" % summary["total_bytes"],
        "duplicate_groups: %d" % summary["duplicate_groups"],
        "unreadable_clips: %d" % summary["unreadable_clips"],
        "symlinks_skipped: %d" % summary["symlinks_skipped"],
        "source_catalog_completeness: UNKNOWN",
        "complete_day: false",
        "event_start: UNKNOWN for all clips",
    ]
    return "\n".join(lines) + "\n"


class _UsageError(Exception):
    """Carries a fixed reason code. argparse's own message is never kept."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _usage_reason(message):
    """Map an argparse message to a fixed code. The text itself is discarded."""
    if message.startswith("unrecognized arguments"):
        return "UNRECOGNIZED_ARGUMENT"
    if "invalid choice" in message or "unknown parser" in message:
        return "INVALID_COMMAND"
    if message.startswith("the following arguments are required"):
        return "MISSING_ARGUMENT"
    if message.startswith("argument --min-free-gib"):
        return "INVALID_MIN_FREE_GIB"
    return "INVALID_ARGUMENT"


class _QuietParser(argparse.ArgumentParser):
    """argparse echoes raw argv tokens in its error text; keep only a reason code."""

    def error(self, message):
        raise _UsageError(_usage_reason(message))


def _usage_failure(reason, json_requested):
    """Print a fixed usage error. argv values are never echoed."""
    hint = _USAGE_HINTS[reason]
    if json_requested:
        report = {
            "tool": "ft_data",
            "command": "usage",
            "schema_version": SCHEMA_VERSION,
            "mode": MODE,
            "status": "REJECTED",
            "reason": reason,
            "hint": hint,
        }
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    else:
        sys.stderr.write("error: %s: %s (run with -h for usage)\n" % (reason, hint))
    return 2


def build_parser():
    parser = _QuietParser(
        prog="ft_data.py",
        description="FT-D0 preparation tools: read-only checks and local clip inventory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_QuietParser)

    doctor = subparsers.add_parser("doctor", help="read-only local preparation checks")
    doctor.add_argument("--json", action="store_true", help="print JSON")
    doctor.add_argument(
        "--min-free-gib",
        type=parse_positive_finite,
        default=DEFAULT_MIN_FREE_GIB,
        help="proposed free-space threshold in GiB (default: %(default)s)",
    )
    doctor.add_argument("--disk-path", default=".", help="directory whose free space is checked")

    inventory = subparsers.add_parser("inventory", help="hash .mp4 files in an explicit directory")
    inventory.add_argument("directory", help="directory to scan (a symlink root is refused)")
    inventory.add_argument("--json", action="store_true", help="print JSON")
    return parser


def main(argv=None):
    raw = sys.argv[1:] if argv is None else argv
    try:
        argv = list(raw)
    except TypeError:
        return _usage_failure("INVALID_ARGV", json_requested=False)
    if not all(isinstance(item, str) and "\x00" not in item for item in argv):
        return _usage_failure("INVALID_ARGV", json_requested=False)
    try:
        args = build_parser().parse_args(argv)
    except _UsageError as exc:
        return _usage_failure(exc.reason, json_requested="--json" in argv)
    if args.command == "doctor":
        report = collect_doctor(args.disk_path, args.min_free_gib)
        exit_code = 0 if report["preparation"]["status"] == "PASS" else 1
    else:
        report = scan_inventory(args.directory)
        exit_code = 0 if report["status"] == "OK" else 1
    if args.json:
        output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    else:
        output = _format_text(report)
    sys.stdout.write(output)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
