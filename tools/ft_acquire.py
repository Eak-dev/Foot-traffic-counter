#!/usr/bin/env python3
"""FT-D0 OD-32: offline acquisition core (request guard, bounded listing,
bounded byte transfer, Fixed-lens manifest). Python 3.9+ standard library
only. This module never imports pytapo, never opens a socket, and never
reads real configuration or credentials.

Boundary this module does NOT cover (separate audited tasks before any
camera access): upstream `pytapo` constructor/transport/auth wiring, media
framing, interrupting a stalled synchronous callback/socket (a cooperative
deadline check only runs between discrete steps; a callback that blocks
forever inside a single call is not interrupted by it), and atomic
publication of real files to disk. `guarded_send` validates a request and
calls an injected `sender` callable; it is not connected to any installed
library or transport.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from datetime import datetime

FORBIDDEN_INDEX = 999999999
# Synthetic development-only ceilings, not a live-approved operational quota;
# any real limit must be set by a separately reviewed policy before camera use.
DEV_MAX_INDEX_CEILING = 50000
DEV_MAX_PAGE_SIZE_CEILING = 500
MAX_TREE_DEPTH_CEILING = 32
_MAX_TREE_NODES = 4096
ALLOWED_METHODS = frozenset(
    {"multipleRequest", "getUserID", "searchVideoOfDay", "searchVideoWithUTC"}
)
_REF_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


class RequestError(Exception):
    """Stable redacted code only; never carries the request/userID/exception text."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class CollectError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class CopyError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class ManifestError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _valid_ref(ref):
    return isinstance(ref, str) and _REF_RE.fullmatch(ref) is not None


def _finite_positive_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return False
    return value > 0


def _nonneg_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_date(text):
    if not isinstance(text, str) or len(text) != 8 or not text.isdigit():
        return False
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError:
        return False
    return True


def _valid_opaque_id(text):
    return isinstance(text, str) and 0 < len(text) <= 128 and all(32 < ord(c) < 127 for c in text)


def _scan_tree(value, remaining_depth, counter):
    """Single bounded pass: depth, node-count budget, setter/method, and type.

    counter is a one-element list used as a mutable node-visit tally shared
    across the whole recursive walk; it is checked against _MAX_TREE_NODES
    on every node visited (dict/list/scalar alike), so a huge list is caught
    at its first excess element rather than only after it has been fully
    walked once to count requests.
    """
    counter[0] += 1
    if counter[0] > _MAX_TREE_NODES:
        raise RequestError("TREE_TOO_LARGE")
    if remaining_depth < 0:
        raise RequestError("TREE_TOO_DEEP")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise RequestError("MALFORMED_TREE")
            if key == "method":
                if not isinstance(item, str) or item not in ALLOWED_METHODS:
                    raise RequestError("SETTER_BLOCKED")
            if key.lower().startswith(("set", "control")):
                raise RequestError("SETTER_BLOCKED")
            _scan_tree(item, remaining_depth - 1, counter)
    elif isinstance(value, list):
        for item in value:
            _scan_tree(item, remaining_depth - 1, counter)
    elif not isinstance(value, _JSON_SCALAR_TYPES):
        raise RequestError("MALFORMED_TREE")


def _validate_get_user_id(params):
    if params != {"system": {"get_user_id": "null"}}:
        raise RequestError("MALFORMED_GET_USER_ID")
    return {"method": "getUserID", "params": {"system": {"get_user_id": "null"}}}


def _validate_channel(channel):
    if not isinstance(channel, int) or isinstance(channel, bool) or channel != 0:
        raise RequestError("INVALID_CHANNEL")


def _validate_search_day(params, max_index, max_page_size):
    if not isinstance(params, dict) or set(params.keys()) != {"playback"}:
        raise RequestError("MALFORMED_SEARCH_DAY")
    playback = params["playback"]
    if not isinstance(playback, dict) or set(playback.keys()) != {"search_video_utility"}:
        raise RequestError("MALFORMED_SEARCH_DAY")
    util = playback["search_video_utility"]
    if not isinstance(util, dict) or set(util.keys()) != {
        "channel", "date", "id", "start_index", "end_index"
    }:
        raise RequestError("MALFORMED_SEARCH_DAY")
    _validate_channel(util["channel"])
    if not _valid_date(util["date"]):
        raise RequestError("INVALID_DATE")
    if not _valid_opaque_id(util["id"]):
        raise RequestError("INVALID_ID")
    start_index, end_index = util["start_index"], util["end_index"]
    if not _nonneg_int(start_index) or not _nonneg_int(end_index):
        raise RequestError("INVALID_INDEX")
    if start_index > end_index:
        raise RequestError("INVALID_INDEX_RANGE")
    if end_index >= FORBIDDEN_INDEX or end_index > max_index:
        raise RequestError("INDEX_OUT_OF_BOUNDS")
    if end_index - start_index + 1 > max_page_size:
        raise RequestError("PAGE_WIDTH_OUT_OF_BOUNDS")
    return {
        "method": "searchVideoOfDay",
        "params": {
            "playback": {
                "search_video_utility": {
                    "channel": 0,
                    "date": util["date"],
                    "id": util["id"],
                    "start_index": start_index,
                    "end_index": end_index,
                }
            }
        },
    }


def _validate_search_utc(params, max_index, max_time_range, max_page_size):
    if not isinstance(params, dict) or set(params.keys()) != {"playback"}:
        raise RequestError("MALFORMED_SEARCH_UTC")
    playback = params["playback"]
    if not isinstance(playback, dict) or set(playback.keys()) != {"search_video_with_utc"}:
        raise RequestError("MALFORMED_SEARCH_UTC")
    util = playback["search_video_with_utc"]
    if not isinstance(util, dict) or set(util.keys()) != {
        "channel", "id", "start_time", "end_time", "start_index", "end_index"
    }:
        raise RequestError("MALFORMED_SEARCH_UTC")
    _validate_channel(util["channel"])
    if not _valid_opaque_id(util["id"]):
        raise RequestError("INVALID_ID")
    start_time, end_time = util["start_time"], util["end_time"]
    if not _nonneg_int(start_time) or not _nonneg_int(end_time):
        raise RequestError("INVALID_TIME")
    if end_time <= start_time or (end_time - start_time) > max_time_range:
        raise RequestError("TIME_RANGE_OUT_OF_BOUNDS")
    start_index, end_index = util["start_index"], util["end_index"]
    if not _nonneg_int(start_index) or not _nonneg_int(end_index):
        raise RequestError("INVALID_INDEX")
    if start_index > end_index:
        raise RequestError("INVALID_INDEX_RANGE")
    if end_index >= FORBIDDEN_INDEX or end_index > max_index:
        raise RequestError("INDEX_OUT_OF_BOUNDS")
    if end_index - start_index + 1 > max_page_size:
        raise RequestError("PAGE_WIDTH_OUT_OF_BOUNDS")
    return {
        "method": "searchVideoWithUTC",
        "params": {
            "playback": {
                "search_video_with_utc": {
                    "channel": 0,
                    "id": util["id"],
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_index": start_index,
                    "end_index": end_index,
                }
            }
        },
    }


def _validate_leaf(leaf, max_index, max_time_range, max_page_size):
    if not isinstance(leaf, dict) or set(leaf.keys()) != {"method", "params"}:
        raise RequestError("MALFORMED_LEAF")
    method = leaf["method"]
    if method == "getUserID":
        return _validate_get_user_id(leaf["params"])
    if method == "searchVideoOfDay":
        return _validate_search_day(leaf["params"], max_index, max_page_size)
    if method == "searchVideoWithUTC":
        return _validate_search_utc(leaf["params"], max_index, max_time_range, max_page_size)
    raise RequestError("METHOD_NOT_ALLOWED")


def validate_sd_request(
    request, *, max_depth, max_requests, max_index, max_time_range, max_page_size
):
    """Validate one pinned multipleRequest/leaf SD shape; return a fresh normalized copy.

    Every bound (max_depth/max_requests/max_index/max_time_range/max_page_size)
    must be supplied explicitly by the caller; there is no implicit large
    default, so a caller cannot silently reuse an unbounded upstream default
    like 999999999 for page indexes, which is always rejected outright.
    max_index and max_page_size are additionally capped against conservative
    synthetic development ceilings (DEV_MAX_INDEX_CEILING/DEV_MAX_PAGE_SIZE_CEILING);
    those ceilings are development caps only, not a live-approved operational
    policy quota.
    """
    if (
        not isinstance(max_depth, int)
        or isinstance(max_depth, bool)
        or not (1 <= max_depth <= MAX_TREE_DEPTH_CEILING)
    ):
        raise RequestError("INVALID_LIMITS")
    if not isinstance(max_requests, int) or isinstance(max_requests, bool) or max_requests < 1:
        raise RequestError("INVALID_LIMITS")
    if (
        not _nonneg_int(max_index)
        or max_index >= FORBIDDEN_INDEX
        or max_index > DEV_MAX_INDEX_CEILING
    ):
        raise RequestError("INVALID_LIMITS")
    if not _finite_positive_number(max_time_range):
        raise RequestError("INVALID_LIMITS")
    if (
        not isinstance(max_page_size, int)
        or isinstance(max_page_size, bool)
        or not (1 <= max_page_size <= DEV_MAX_PAGE_SIZE_CEILING)
    ):
        raise RequestError("INVALID_LIMITS")

    _scan_tree(request, max_depth, [0])

    if not isinstance(request, dict) or set(request.keys()) != {"method", "params"}:
        raise RequestError("MALFORMED_REQUEST")
    if request["method"] != "multipleRequest":
        raise RequestError("METHOD_NOT_ALLOWED")
    params = request["params"]
    if not isinstance(params, dict) or set(params.keys()) != {"requests"}:
        raise RequestError("MALFORMED_REQUEST")
    requests = params["requests"]
    if not isinstance(requests, list) or not requests or len(requests) > max_requests:
        raise RequestError("REQUEST_COUNT_OUT_OF_BOUNDS")

    leaves = [
        _validate_leaf(leaf, max_index, max_time_range, max_page_size) for leaf in requests
    ]
    return {"method": "multipleRequest", "params": {"requests": leaves}}


def guarded_send(
    request, sender, *, max_depth, max_requests, max_index, max_time_range, max_page_size
):
    """Validate, then call sender(copy) with a defensive copy of the validated request.

    sender is never called when validation fails. The object passed to
    sender is a fresh deep copy so that any later mutation of a reference
    the caller still holds cannot retroactively inject a setter into what
    sender already received. Any exception raised by sender itself is
    replaced by a stable redacted RequestError; the original sender
    exception text/object is never propagated.
    """
    validated = validate_sd_request(
        request,
        max_depth=max_depth,
        max_requests=max_requests,
        max_index=max_index,
        max_time_range=max_time_range,
        max_page_size=max_page_size,
    )
    try:
        return sender(deepcopy(validated))
    except Exception:
        raise RequestError("SENDER_FAILED") from None


def _is_aware(ts):
    try:
        return isinstance(ts, datetime) and ts.tzinfo is not None and ts.utcoffset() is not None
    except Exception:
        return False


def _normalize_clip(raw, window_start, window_end):
    if not isinstance(raw, dict) or set(raw.keys()) != {"ref", "start", "end", "fixed_lens_proof"}:
        raise CollectError("MALFORMED_CLIP")
    ref = raw["ref"]
    if not _valid_ref(ref):
        raise CollectError("INVALID_REF")
    start, end = raw["start"], raw["end"]
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        raise CollectError("INVALID_TIME")
    if not _is_aware(start) or not _is_aware(end):
        raise CollectError("NAIVE_TIME")
    if end <= start:
        raise CollectError("INVALID_RANGE")
    if start < window_start or end > window_end:
        raise CollectError("OUT_OF_WINDOW")
    if raw["fixed_lens_proof"] is not True:
        raise CollectError("FIXED_LENS_UNPROVEN")
    return {"ref": ref, "start": start, "end": end, "fixed_lens_proof": True}


def _finite_nonneg_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return False
    return value >= 0


def _read_clock(clock, prev, error_cls):
    """Call clock(), redact any exception it raises, and validate the sample.

    Shared by collect_pages and copy_bounded so both callers get the same
    redaction and the same finite/non-bool/non-regressing checks; error_cls
    lets each caller get its own stable error type for the same codes.
    """
    try:
        value = clock()
    except Exception:
        raise error_cls("CLOCK_FAILED") from None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error_cls("INVALID_CLOCK")
    if value != value or value in (float("inf"), float("-inf")):
        raise error_cls("INVALID_CLOCK")
    if prev is not None and value < prev:
        raise error_cls("CLOCK_REGRESSION")
    return value


def collect_pages(
    fetch_page,
    *,
    page_size,
    max_pages,
    max_records,
    deadline_s,
    clock,
    window_start,
    window_end,
):
    """Bounded, idempotent pagination over an injected fetch_page(start_index, end_index).

    Stops on the first short/empty page. Raises MAX_PAGES_EXHAUSTED rather
    than silently declaring completeness when max_pages full pages are
    consumed without ever seeing a short page. Raises STALLED_PAGE if two
    consecutive FULL pages return the exact same set of refs (order-
    independent), so a fetch_page that never advances cannot be polled
    forever; a final short/terminating page repeating the previous page's
    refs is a legitimate overlap, not a stall. Any exception raised by
    fetch_page itself is replaced by a stable redacted CollectError; the
    original fetch_page exception text/object is never propagated.
    """
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size <= 0:
        raise CollectError("INVALID_LIMITS")
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages <= 0:
        raise CollectError("INVALID_LIMITS")
    if not isinstance(max_records, int) or isinstance(max_records, bool) or max_records <= 0:
        raise CollectError("INVALID_LIMITS")
    if not _finite_positive_number(deadline_s):
        raise CollectError("INVALID_LIMITS")
    for ts in (window_start, window_end):
        if not _is_aware(ts):
            raise CollectError("INVALID_WINDOW")
    if window_end <= window_start:
        raise CollectError("INVALID_WINDOW")

    last_clock = _read_clock(clock, None, CollectError)
    start_clock = last_clock
    records = {}
    order = []
    prev_full_refs = None
    page_index = 0
    while True:
        if page_index >= max_pages:
            raise CollectError("MAX_PAGES_EXHAUSTED")
        last_clock = _read_clock(clock, last_clock, CollectError)
        if last_clock - start_clock > deadline_s:
            raise CollectError("DEADLINE_EXCEEDED")
        start_index = page_index * page_size
        end_index = start_index + page_size - 1
        if end_index >= FORBIDDEN_INDEX:
            raise CollectError("INDEX_OUT_OF_BOUNDS")
        try:
            page = fetch_page(start_index, end_index)
        except Exception:
            raise CollectError("FETCH_FAILED") from None
        last_clock = _read_clock(clock, last_clock, CollectError)
        if last_clock - start_clock > deadline_s:
            raise CollectError("DEADLINE_EXCEEDED")
        if not isinstance(page, list):
            raise CollectError("INVALID_PAGE")
        if len(page) > page_size:
            raise CollectError("PAGE_OVERSIZED")

        refs_this_page = []
        for raw in page:
            clip = _normalize_clip(raw, window_start, window_end)
            refs_this_page.append(clip["ref"])
            existing = records.get(clip["ref"])
            if existing is not None:
                if existing != clip:
                    raise CollectError("REF_CONFLICT")
            else:
                records[clip["ref"]] = clip
                order.append(clip["ref"])
                if len(order) > max_records:
                    raise CollectError("MAX_RECORDS_EXCEEDED")
            last_clock = _read_clock(clock, last_clock, CollectError)
            if last_clock - start_clock > deadline_s:
                raise CollectError("DEADLINE_EXCEEDED")

        is_full_page = len(page) == page_size
        if is_full_page:
            refs_set = frozenset(refs_this_page)
            if refs_set and refs_set == prev_full_refs:
                raise CollectError("STALLED_PAGE")
            prev_full_refs = refs_set

        last_clock = _read_clock(clock, last_clock, CollectError)
        if last_clock - start_clock > deadline_s:
            raise CollectError("DEADLINE_EXCEEDED")

        if not is_full_page:
            return [records[ref] for ref in order]
        page_index += 1


def copy_bounded(chunks, sink, *, expected_length, max_bytes, deadline_s, clock):
    """Stream bytes from an injected iterable through a file-like sink, bounded.

    Checks the byte budget before each write and the cooperative deadline
    before pulling the next chunk, before writing it, after every partial
    write of a short write, and again after the source is exhausted (so a
    source that yields exactly expected_length bytes and only then advances
    the clock past the deadline on its closing StopIteration still fails
    rather than returning STAGED). A synchronous stalled chunk source or a
    sink.write() call that never returns cannot be interrupted by these
    checks: a cooperative deadline check only runs between discrete steps,
    never inside one blocking call; interrupting a truly stalled transport/
    socket requires a separately audited process or socket-level timeout,
    not this cooperative helper. Exceptions raised by iter(chunks), clock(),
    next(iterator), or sink.write() are all replaced by a stable redacted
    CopyError; none of their original text/object is ever propagated. Never
    returns a SUCCESS-shaped result on failure; the caller is responsible
    for any partial cleanup of sink.
    """
    if not isinstance(expected_length, int) or isinstance(expected_length, bool) or expected_length <= 0:
        raise CopyError("INVALID_LIMITS")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise CopyError("INVALID_LIMITS")
    if expected_length > max_bytes:
        raise CopyError("INVALID_LIMITS")
    if not _finite_positive_number(deadline_s):
        raise CopyError("INVALID_LIMITS")

    last_clock = _read_clock(clock, None, CopyError)
    start_clock = last_clock

    def check_deadline():
        nonlocal last_clock
        last_clock = _read_clock(clock, last_clock, CopyError)
        if last_clock - start_clock > deadline_s:
            raise CopyError("DEADLINE_EXCEEDED")

    try:
        iterator = iter(chunks)
    except Exception:
        raise CopyError("SOURCE_FAILED") from None

    hasher = hashlib.sha256()
    total = 0
    while True:
        check_deadline()
        try:
            chunk = next(iterator)
        except StopIteration:
            break
        except Exception:
            raise CopyError("SOURCE_FAILED") from None
        check_deadline()
        if not isinstance(chunk, bytes):
            raise CopyError("INVALID_CHUNK")
        if len(chunk) == 0:
            raise CopyError("EMPTY_CHUNK")
        if total + len(chunk) > max_bytes:
            raise CopyError("BUDGET_EXCEEDED")
        if total + len(chunk) > expected_length:
            raise CopyError("STREAM_OVERLONG")

        view = chunk
        while view:
            check_deadline()
            try:
                written = sink.write(view)
            except Exception:
                raise CopyError("SINK_FAILED") from None
            if (
                not isinstance(written, int)
                or isinstance(written, bool)
                or written <= 0
                or written > len(view)
            ):
                raise CopyError("SINK_FAILED")
            hasher.update(view[:written])
            total += written
            view = view[written:]
            check_deadline()

    check_deadline()
    if total != expected_length:
        raise CopyError("STREAM_TRUNCATED")
    return {"status": "STAGED", "bytes_written": total, "sha256": hasher.hexdigest()}


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_CONTAINERS = frozenset({"mp4", "mpegts"})


def _valid_staged_result(value):
    if not isinstance(value, dict) or set(value.keys()) != {"status", "bytes_written", "sha256"}:
        return False
    if value["status"] != "STAGED":
        return False
    bytes_written = value["bytes_written"]
    if not isinstance(bytes_written, int) or isinstance(bytes_written, bool) or bytes_written <= 0:
        return False
    sha256_hex = value["sha256"]
    if not isinstance(sha256_hex, str) or _SHA256_RE.fullmatch(sha256_hex) is None:
        return False
    return True


class Manifest:
    """In-memory, Fixed-lens-only clip manifest. No filesystem/database access.

    Never infers Fixed from a stream number; lens must already be the exact
    literal "FIXED" from a validated mapping the caller supplies, and
    fixed_mapping_verified/container_validated/duration_validated must all
    be explicitly True. Those three flags are trusted inputs from a
    separately audited validator this core does not implement; passing
    them True is a caller claim this method requires, not evidence that a
    real camera/file has already been checked. staged_result must be the
    exact dict copy_bounded returns on success; this method never accepts
    an independently supplied sha256/size. Dedup is idempotent only for an
    identical (ref, sha256, size_bytes, start, end, lens, container,
    duration_s) resubmission; a ref with conflicting bytes or conflicting
    timing/format metadata is rejected as REF_CONFLICT. Same bytes under
    different refs may be reported as duplicates, which is byte-identity
    only, not semantic/overlap video dedup.
    """

    def __init__(self):
        self._entries = {}

    def add_clip(
        self,
        *,
        ref,
        start,
        end,
        lens,
        container,
        duration_s,
        duration_tolerance_s,
        staged_result,
        fixed_mapping_verified,
        container_validated,
        duration_validated,
    ):
        if not _valid_ref(ref):
            raise ManifestError("INVALID_REF")
        for ts in (start, end):
            if not isinstance(ts, datetime) or ts.tzinfo is None:
                raise ManifestError("INVALID_TIME")
            try:
                offset = ts.utcoffset()
            except Exception:
                raise ManifestError("INVALID_TIME") from None
            if offset is None:
                raise ManifestError("INVALID_TIME")
        if end <= start:
            raise ManifestError("INVALID_RANGE")
        if lens != "FIXED":
            raise ManifestError("LENS_NOT_FIXED")
        if not isinstance(container, str) or container not in _ALLOWED_CONTAINERS:
            raise ManifestError("INVALID_CONTAINER")
        if not _finite_positive_number(duration_s):
            raise ManifestError("INVALID_DURATION")
        if not _finite_nonneg_number(duration_tolerance_s):
            raise ManifestError("INVALID_DURATION_TOLERANCE")
        if abs(duration_s - (end - start).total_seconds()) > duration_tolerance_s:
            raise ManifestError("DURATION_MISMATCH")
        if fixed_mapping_verified is not True:
            raise ManifestError("FIXED_LENS_UNVERIFIED")
        if container_validated is not True:
            raise ManifestError("CONTAINER_UNVALIDATED")
        if duration_validated is not True:
            raise ManifestError("DURATION_UNVALIDATED")
        if not _valid_staged_result(staged_result):
            raise ManifestError("INVALID_STAGED_RESULT")

        sha256_hex = staged_result["sha256"]
        size_bytes = staged_result["bytes_written"]

        entry = {
            "ref": ref,
            "start": start,
            "end": end,
            "sha256": sha256_hex,
            "size_bytes": size_bytes,
            "lens": "FIXED",
            "container": container,
            "duration_s": duration_s,
            "status": "STAGED",
        }
        existing = self._entries.get(ref)
        if existing is not None:
            if (
                existing["sha256"] == sha256_hex
                and existing["size_bytes"] == size_bytes
                and existing["start"] == start
                and existing["end"] == end
                and existing["lens"] == entry["lens"]
                and existing["container"] == container
                and existing["duration_s"] == duration_s
            ):
                return "DUPLICATE"
            raise ManifestError("REF_CONFLICT")
        self._entries[ref] = entry
        return "ADDED"

    def duplicate_byte_groups(self):
        """Refs sharing identical (sha256, size_bytes); byte-identity dedup only."""
        groups = {}
        for ref, entry in self._entries.items():
            key = (entry["sha256"], entry["size_bytes"])
            groups.setdefault(key, []).append(ref)
        return {key: sorted(refs) for key, refs in groups.items() if len(refs) > 1}

    def entries(self):
        """Defensive snapshot: fresh dicts, whitelisted serializable fields only."""
        snapshot = {
            ref: {
                "ref": entry["ref"],
                "start": entry["start"].isoformat(),
                "end": entry["end"].isoformat(),
                "sha256": entry["sha256"],
                "size": entry["size_bytes"],
                "lens": entry["lens"],
                "container": entry["container"],
                "duration": entry["duration_s"],
                "status": entry["status"],
            }
            for ref, entry in self._entries.items()
        }
        return deepcopy(snapshot)


def check_command():
    """Offline status only; always BLOCKED/NOT_TESTED. Never reads config, never contacts a camera."""
    return {
        "tool": "ft_acquire",
        "command": "check",
        "status": "BLOCKED",
        "route": "NOT_TESTED",
        "auth": "NOT_TESTED",
        "download": "NOT_TESTED",
        "camera_requests": 0,
        "backend_binding": "NOT_IMPLEMENTED",
    }


class _UsageError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _usage_reason(message):
    if message.startswith("unrecognized arguments"):
        return "UNRECOGNIZED_ARGUMENT"
    if message.startswith("the following arguments are required"):
        return "MISSING_ARGUMENT"
    return "INVALID_COMMAND"


class _QuietParser(argparse.ArgumentParser):
    """argparse echoes raw argv tokens in its error text; keep only a reason code."""

    def error(self, message):
        raise _UsageError(_usage_reason(message))


def build_parser():
    parser = _QuietParser(
        prog="ft_acquire.py",
        description="OD-32 offline acquisition core status (no live download command).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_QuietParser)
    subparsers.add_parser("check", help="offline status only; always BLOCKED/NOT_TESTED")
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
        _write_json({"tool": "ft_acquire", "command": "usage", "status": "REJECTED", "reason": "INVALID_COMMAND"})
        return 2
    try:
        build_parser().parse_args(argv)
    except _UsageError as exc:
        _write_json({"tool": "ft_acquire", "command": "usage", "status": "REJECTED", "reason": exc.reason})
        return 2
    _write_json(check_command())
    return 2


if __name__ == "__main__":
    sys.exit(main())
