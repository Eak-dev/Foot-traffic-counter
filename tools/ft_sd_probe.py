#!/usr/bin/env python3
"""FT-D0 OD-43: a bounded, read-only SD metadata/listing probe.

This module never downloads media and never sends a setter. It reuses the
pinned transport primitives (``_open_connection``, ``_bounded_read``,
``_cloud_headers``, the duplicate-key-rejecting JSON parser) and the fixed
account-login/discovery flow from :mod:`tools.ft_cloud_probe`; see
docs/THIRD_PARTY_NOTICES.md for the pinned public passthrough packet shape
(OnTapo commit a387f6abddb72f7e6eea72b374df5ad189da1f5f, MIT).

Entry point: ``run(target_name_sha256, date='20261012')``. It validates the
digest and the exact calendar date before any dialog or network call, logs
in through the existing native-dialog cloud flow, and -- only for a single
exact owner-name match -- sends at most four bounded passthrough requests to
the already-selected device id: metadata, optional capability, calendar/user,
and (only if identity/user/date all check out) one bounded first-page clip
listing. Every output field is a fixed enum/count/boolean; no raw IDs, names,
model strings, timestamps, or replies are ever reported.
"""
from __future__ import annotations

import datetime
import http.client
import json
import re
import socket
import ssl
import time

from tools import ft_cloud_probe as cloud

TOOL_NAME = "ft_sd_probe"

MAX_DEVICE_REQUESTS = 4
DEVICE_BUDGET_S = 90
MAX_CLIP_ENTRIES = 20
MAX_APP_COMPONENTS = 50

# Every entrypoint is hard-bound to this single date; nothing else is ever
# accepted, in this tool or in the fixed request templates it builds.
FIXED_DATE = "20261012"

STAGES = frozenset({"METADATA", "CAPABILITY", "CALENDAR", "CLIPS"})

ERROR_CODES = frozenset(
    {
        "INVALID_INPUT",
        "TIMEOUT",
        "TLS_ERROR",
        "CONNECT_ERROR",
        "HTTP_ERROR",
        "PAYLOAD_TOO_LARGE",
        "TIME_BUDGET_EXCEEDED",
        "REQUEST_LIMIT_EXCEEDED",
        "MALFORMED_RESPONSE",
        "REQUEST_FAILED",
        "IDENTITY_MISMATCH",
        "NOT_SELECTED",
        "UNKNOWN_ERROR",
    }
)

_DATE_RE = re.compile(r"[0-9]{8}")
_DEVICE_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
_TIMEZONE_RE = re.compile(r"UTC([+-])(\d{2}):(\d{2})")
_DECIMAL_UID_RE = re.compile(r"[1-9][0-9]{0,18}")

_SD_STATUS_VALUES = frozenset({"normal", "unformatted", "offline", "abnormal"})


SD_DETAILS = frozenset({"ENVELOPE_FORMAT", "CALENDAR_RESULT", "CALENDAR_LIST", "ROW_SHAPE", "ROW_LABEL", "ROW_DUPLICATE", "DATE_FORMAT", "DATE_OUTSIDE_REQUEST", "USER_ID_INVALID", "TIMEZONE_UNKNOWN"})


class SdError(Exception):
    """Carries only a fixed, pre-redacted code; never raw exception/body text."""

    def __init__(self, code, http_status=None, gateway_reason=None, detail=None):
        self.detail = detail if detail in SD_DETAILS else None
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        self.gateway_reason = gateway_reason if gateway_reason in ("MODEL_SCHEMA_CHECK_FAILED", "HTTP_REDIRECT", "UNCLASSIFIED") else None
        code = code if code in ERROR_CODES else "UNKNOWN_ERROR"
        super().__init__(code)
        self.code = code


# -- device-scoped budget ----------------------------------------------------


class _DeviceBudget:
    """A separate, smaller cooperative budget for the device/SD requests.

    Only ``start``/``check_time``/``use_request`` are read by the reused
    cloud transport helpers, so this stands in for ``ft_cloud_probe._Budget``
    without sharing its (larger) module-level constants.
    """

    def __init__(self, session_guard=None):
        self.start = time.monotonic()
        self.requests = 0
        self.session_guard = session_guard

    def check_time(self):
        if self.session_guard is not None:
            self.session_guard()
        if time.monotonic() >= self.start + DEVICE_BUDGET_S:
            raise SdError("TIME_BUDGET_EXCEEDED")

    def use_request(self):
        self.requests += 1
        if self.requests > MAX_DEVICE_REQUESTS:
            raise SdError("REQUEST_LIMIT_EXCEEDED")


# -- validated input ----------------------------------------------------------


def _validate_date(date):
    if date != FIXED_DATE:
        raise SdError("INVALID_INPUT")
    return date


def _validate_device_id(device_id):
    if not isinstance(device_id, str) or not _DEVICE_ID_RE.fullmatch(device_id):
        raise SdError("INVALID_INPUT")
    return device_id


# -- transport: one fixed (host, POST, path) shape only ----------------------


def _device_path(device_id):
    return "/v1/things/" + _validate_device_id(device_id) + "/services-sync"


def _build_envelope(requests):
    body_obj = {
        "inputParams": {
            "requestData": {
                "method": "multipleRequest",
                "params": {"requests": requests},
            }
        },
        "serviceId": "passthrough",
    }
    return json.dumps(body_obj).encode("utf-8")


def _canonical_eq(a, b):
    """Strict structural equality: bools never match ints, dict key sets
    must match exactly, lists compare elementwise and in order."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a.keys()) == set(b.keys()) and all(_canonical_eq(v, b[k]) for k, v in a.items())
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_canonical_eq(x, y) for x, y in zip(a, b))
    if type(a) is not type(b):
        return False
    return a == b


def _expected_requests(batch, date, user_id):
    if batch == "metadata":
        return _metadata_requests()
    if batch == "capability":
        return _capability_requests()
    if batch == "calendar":
        return _calendar_requests(date)
    if batch == "clip":
        return _clip_requests(date, user_id)
    if batch == "clip-utc":
        return _clip_utc_requests(date, user_id)
    raise SdError("INVALID_INPUT")


def _validate_requests(requests, batch, date, user_id):
    """Reject anything that is not byte-for-byte one of the four fixed
    getter templates, before any connection is opened.

    No setter, no nested/extra key, no extra param, and no channel/index/
    date deviation can pass: the comparison is against the exact template
    this module itself builds, using canonical (bool-excluded) equality.
    """
    if date != FIXED_DATE:
        raise SdError("INVALID_INPUT")
    if batch in ("clip", "clip-utc"):
        if isinstance(user_id, bool) or not isinstance(user_id, int) or not (0 < user_id <= 2**63 - 1):
            raise SdError("INVALID_INPUT")
    expected = _expected_requests(batch, date, user_id)
    if not _canonical_eq(requests, expected):
        raise SdError("INVALID_INPUT")


def _open_device_connection(budget):
    """A connection to the fixed discovery host with its timeout clamped to
    this (smaller) device budget, not the larger cloud-module constant.

    Checked both before and after the blocking connect() call so a slow
    DNS/TLS handshake cannot silently outlast the device budget.
    """
    budget.check_time()
    try:
        context = cloud._pinned_context()
    except cloud.ProbeError as exc:
        raise SdError(exc.code) from None
    remaining = (budget.start + DEVICE_BUDGET_S) - time.monotonic()
    timeout = max(0.001, min(10, remaining))
    try:
        conn = http.client.HTTPSConnection(cloud.DISCOVERY_HOST, cloud.PORT, context=context, timeout=timeout)
    except (OSError, ssl.SSLError):
        raise SdError("CONNECT_ERROR") from None
    try:
        budget.check_time()
    except SdError:
        conn.close()
        raise
    return conn


def _device_request(budget, token, terminal_uuid, device_id, requests, batch, date, user_id=None):
    """One bounded passthrough POST; closes the socket on every exit path.

    ``requests`` is validated against the exact fixed getter template for
    ``batch`` before any budget use or connection is opened, so invalid
    input can never make a connection.
    """
    device_id = _validate_device_id(device_id)
    _validate_requests(requests, batch, date, user_id)
    path = _device_path(device_id)
    body = _build_envelope(requests)
    budget.check_time()
    budget.use_request()
    conn = _open_device_connection(budget)
    try:
        try:
            headers = cloud._cloud_headers(token, terminal_uuid)
            headers["Content-Type"] = "application/json; charset=UTF-8"
            conn.request("POST", path, body=body, headers=headers)
            budget.check_time()
            resp = conn.getresponse()
            budget.check_time()
        except socket.timeout:
            raise SdError("TIMEOUT") from None
        except ssl.SSLError:
            raise SdError("TLS_ERROR") from None
        except (OSError, http.client.HTTPException):
            raise SdError("CONNECT_ERROR") from None
        if resp.status in (301, 302, 303, 307, 308):
            raise SdError("HTTP_ERROR", resp.status, "HTTP_REDIRECT")
        try:
            data = cloud._bounded_read(budget, resp)
        except cloud.ProbeError as exc:
            raise SdError(exc.code) from None
        if resp.status != 200:
            classification = "UNCLASSIFIED"
            try:
                obj = cloud._parse_json_object(data)
                if any(isinstance(obj.get(k), str) and "MODEL_SCHEMA_CHECK_FAILED" in obj[k] for k in ("message", "msg")):
                    classification = "MODEL_SCHEMA_CHECK_FAILED"
            except cloud.ProbeError:
                pass
            raise SdError("HTTP_ERROR", resp.status, classification)
        return data
    finally:
        conn.close()


# -- passthrough envelope parsing --------------------------------------------


def _extract_code(obj):
    try:
        return cloud._extract_error_code(obj)
    except cloud.ProbeError:
        raise SdError("MALFORMED_RESPONSE") from None


def _parse_json_object(data):
    try:
        return cloud._parse_json_object(data)
    except cloud.ProbeError:
        raise SdError("MALFORMED_RESPONSE") from None


def _parse_responses(data, expected_methods, lenient_methods=frozenset()):
    """Validate the exact set of expected per-method responses.

    Unknown or duplicate method names, a missing per-method code, or a
    missing method from ``expected_methods`` are all rejected as malformed.
    A nonzero per-method code is a hard failure unless that method is
    listed in ``lenient_methods`` (the optional capability batch), in which
    case its result is reported as absent rather than aborting the batch.
    """
    obj = _parse_json_object(data)
    outer_code, outer_present = _extract_code(obj)
    if outer_present and outer_code != 0:
        raise SdError("REQUEST_FAILED")
    output = obj.get("outputParams")
    if not isinstance(output, dict):
        raise SdError("MALFORMED_RESPONSE")
    response_data = output.get("responseData")
    if isinstance(response_data, str):
        response_data = _parse_json_object(response_data.encode("utf-8"))
    if not isinstance(response_data, dict):
        raise SdError("MALFORMED_RESPONSE")
    rd_code, rd_present = _extract_code(response_data)
    if rd_present and rd_code != 0:
        raise SdError("REQUEST_FAILED")
    result = response_data.get("result")
    if not isinstance(result, dict):
        raise SdError("MALFORMED_RESPONSE")
    responses = result.get("responses")
    if not isinstance(responses, list):
        raise SdError("MALFORMED_RESPONSE")
    seen = set()
    by_method = {}
    for entry in responses:
        if not isinstance(entry, dict):
            raise SdError("MALFORMED_RESPONSE")
        method = entry.get("method")
        if not isinstance(method, str) or method not in expected_methods or method in seen:
            raise SdError("MALFORMED_RESPONSE")
        seen.add(method)
        code, present = _extract_code(entry)
        if not present:
            raise SdError("MALFORMED_RESPONSE")
        if code != 0 and method not in lenient_methods:
            raise SdError("REQUEST_FAILED")
        by_method[method] = entry.get("result") if code == 0 else None
    if seen != set(expected_methods):
        raise SdError("MALFORMED_RESPONSE")
    return by_method


# -- fixed-shape result readers ----------------------------------------------


def _read_device_model(result, expected_model_kind):
    if not isinstance(result, dict):
        raise SdError("MALFORMED_RESPONSE")
    info = result.get("device_info")
    basic = info.get("basic_info") if isinstance(info, dict) else None
    model = basic.get("device_model") if isinstance(basic, dict) else None
    if not isinstance(model, str) or not model.strip():
        raise SdError("MALFORMED_RESPONSE")
    kind = cloud._c545d_model_kind(model)
    if kind not in ("EXACT", "VARIANT") or expected_model_kind not in ("EXACT", "VARIANT"):
        raise SdError("IDENTITY_MISMATCH")
    return kind


def _read_timezone_offset(result):
    if not isinstance(result, dict):
        return None
    system = result.get("system")
    basic = system.get("basic") if isinstance(system, dict) else None
    tz = basic.get("timezone") if isinstance(basic, dict) else None
    if not isinstance(tz, str):
        return None
    match = _TIMEZONE_RE.fullmatch(tz)
    if not match:
        return None
    sign, hours, minutes = match.group(1), int(match.group(2)), int(match.group(3))
    if hours > 14 or minutes not in (0, 15, 30, 45) or (hours == 14 and minutes != 0):
        return None
    return f"{sign}{hours:02d}:{minutes:02d}"


def _read_sd_status(result):
    if not isinstance(result, dict):
        return "UNKNOWN"
    manage = result.get("harddisk_manage")
    hd_info = manage.get("hd_info") if isinstance(manage, dict) else None
    if not isinstance(hd_info, list):
        return "UNKNOWN"
    if not hd_info:
        return "NO_CARD"
    statuses = []
    for slot in hd_info:
        if not isinstance(slot, dict):
            return "UNKNOWN"
        for value in slot.values():
            status = value.get("detect_status") if isinstance(value, dict) else None
            statuses.append(status if isinstance(status, str) and status in _SD_STATUS_VALUES else "unknown")
    if "normal" in statuses:
        return "NORMAL"
    if "abnormal" in statuses:
        return "ABNORMAL"
    if "offline" in statuses:
        return "OFFLINE"
    if "unformatted" in statuses:
        return "UNFORMATTED"
    return "UNKNOWN"


def _read_capabilities(app_component_result, stream_result, video_result):
    caps = {
        "has_sd_card_component": None,
        "has_ptz_component": None,
        "component_count": None,
        "stream_capability_present": None,
        "video_capability_present": None,
    }
    if isinstance(app_component_result, dict):
        comp = app_component_result.get("app_component")
        listing = comp.get("app_component_list") if isinstance(comp, dict) else None
        if (
            isinstance(listing, list)
            and len(listing) <= MAX_APP_COMPONENTS
            and all(
                isinstance(item, dict) and isinstance(item.get("name"), str) and item.get("name")
                for item in listing
            )
        ):
            names = {item["name"] for item in listing}
            caps["has_sd_card_component"] = "sdCard" in names
            caps["has_ptz_component"] = "ptz" in names
            caps["component_count"] = len(listing)
    if isinstance(stream_result, dict):
        stream_capability = stream_result.get("stream_capability")
        if isinstance(stream_capability, dict):
            caps["stream_capability_present"] = bool(stream_capability)
    if isinstance(video_result, dict):
        video_capability = video_result.get("video_capability")
        if isinstance(video_capability, dict):
            caps["video_capability_present"] = bool(video_capability)
    return caps


def _read_user_id(result):
    """``getUserID`` replies with ``result={"user_id": <id>}`` directly
    (see pinned OnTapo ``_user_id``); there is no ``system`` wrapper."""
    if not isinstance(result, dict):
        return None
    candidate = result.get("user_id", result.get("userId"))
    if isinstance(candidate, bool):
        return None
    if isinstance(candidate, int) and 0 < candidate <= 2**63 - 1:
        return candidate
    if isinstance(candidate, str) and _DECIMAL_UID_RE.fullmatch(candidate):
        return int(candidate) if int(candidate) <= 2**63 - 1 else None
    return None


def _single_index_entry(entry):
    """Opaque row labels are not protocol indices or output. Upstream iterates
    mapping values; require one bounded nonempty label and validate its value.
    """
    if not isinstance(entry, dict) or len(entry) != 1:
        raise SdError("MALFORMED_RESPONSE", detail="ROW_SHAPE")
    (key, value), = entry.items()
    if not isinstance(key, str) or not (1 <= len(key) <= 128):
        raise SdError("MALFORMED_RESPONSE", detail="ROW_LABEL")
    return key, value


def _read_calendar(result, requested_date):
    if not isinstance(result, dict):
        raise SdError("MALFORMED_RESPONSE", detail="CALENDAR_RESULT")
    playback = result.get("playback")
    entries = playback.get("search_results") if isinstance(playback, dict) else None
    if not isinstance(entries, list):
        raise SdError("MALFORMED_RESPONSE", detail="CALENDAR_LIST")
    seen_keys = set()
    dates = set()
    for entry in entries:
        key, value = _single_index_entry(entry)
        if key in seen_keys:
            raise SdError("MALFORMED_RESPONSE", detail="ROW_DUPLICATE")
        seen_keys.add(key)
        date = value.get("date") if isinstance(value, dict) else None
        if not isinstance(date, str) or not _DATE_RE.fullmatch(date):
            raise SdError("MALFORMED_RESPONSE", detail="DATE_FORMAT")
        try:
            datetime.datetime.strptime(date, "%Y%m%d")
        except ValueError:
            raise SdError("MALFORMED_RESPONSE", detail="DATE_FORMAT") from None
        dates.add(date)
    return requested_date in dates


_MAX_EPOCH_S = 4102444800  # 2100-01-01T00:00:00Z


def _day_bounds_utc(date, tz_offset):
    sign, hours, minutes = tz_offset[0], int(tz_offset[1:3]), int(tz_offset[4:6])
    offset_s = (hours * 3600 + minutes * 60) * (1 if sign == "+" else -1)
    midnight_local = datetime.datetime.strptime(date, "%Y%m%d").replace(tzinfo=datetime.timezone.utc)
    start_utc = int(midnight_local.timestamp()) - offset_s
    return start_utc, start_utc + 86400


def _read_clips(result, tz_offset, date):
    if not isinstance(result, dict):
        raise SdError("MALFORMED_RESPONSE")
    playback = result.get("playback")
    entries = playback.get("search_video_results") if isinstance(playback, dict) else None
    if not isinstance(entries, list) or len(entries) > MAX_CLIP_ENTRIES:
        raise SdError("MALFORMED_RESPONSE")
    if not entries:
        return 0, "NO_CLIPS"
    if not isinstance(tz_offset, str):
        raise SdError("MALFORMED_RESPONSE")
    day_start, day_end = _day_bounds_utc(date, tz_offset)
    seen_keys = set()
    for entry in entries:
        key, index = _single_index_entry(entry)
        if key in seen_keys:
            raise SdError("MALFORMED_RESPONSE")
        seen_keys.add(key)
        if not isinstance(index, dict):
            raise SdError("MALFORMED_RESPONSE")
        start = index.get("startTime")
        end = index.get("endTime")
        vtype = index.get("vedio_type")
        if (
            isinstance(start, bool) or isinstance(end, bool) or isinstance(vtype, bool)
            or not isinstance(start, int) or not isinstance(end, int) or not isinstance(vtype, int)
        ):
            raise SdError("MALFORMED_RESPONSE")
        if not (0 < start < end <= _MAX_EPOCH_S):
            raise SdError("MALFORMED_RESPONSE")
        if not (day_start <= start < day_end) or end > day_end:
            raise SdError("MALFORMED_RESPONSE")
    return len(entries), "FIRST_PAGE_ONLY"


# -- fixed getter/params shapes (pinned public passthrough packet) ----------


def _metadata_requests():
    return [
        {"method": "getDeviceInfo", "params": {"device_info": {"name": ["basic_info"]}}},
        {"method": "getTimezone", "params": {"system": {"name": "basic"}}},
        {"method": "getSdCardStatus", "params": {"harddisk_manage": {"table": ["hd_info"]}}},
    ]


def _capability_requests():
    return [
        {"method": "getAppComponentList", "params": {"app_component": {"name": ["app_component_list"]}}},
        {"method": "getStreamCapability", "params": {"stream_capability": {"local_stream_type": {}}}},
        {"method": "getVideoCapability", "params": {"video_capability": {"name": ["main", "minor"]}}},
    ]


def _calendar_requests(date):
    return [
        {"method": "getUserID", "params": {"system": {"get_user_id": "null"}}},
        {
            "method": "searchDateWithVideo",
            "params": {
                "playback": {
                    "search_year_utility": {"channel": [0], "start_date": date, "end_date": date}
                }
            },
        },
    ]


def _clip_requests(date, user_id):
    return [
        {
            "method": "searchVideoOfDay",
            "params": {
                "playback": {
                    "search_video_utility": {
                        "channel": 0,
                        "date": date,
                        "start_index": 0,
                        "end_index": MAX_CLIP_ENTRIES - 1,
                        "id": user_id,
                    }
                }
            },
        }
    ]


def _clip_utc_requests(date, user_id):
    """Pinned pytapo3.4.26 request shape; exact day and first20 rows only."""
    _validate_date(date)
    start, end = _day_bounds_utc(date, '+07:00')
    return [{'method':'searchVideoWithUTC', 'params':{'playback':{
        'search_video_with_utc':{'channel':0, 'id':user_id, 'start_index':0,
            'end_index':MAX_CLIP_ENTRIES-1, 'start_time':start, 'end_time':end-1}}}}]


def _fixed_intervals(result):
    """Strict source-backed C545D lens metadata. Never infer from row order."""
    if not isinstance(result, dict) or not isinstance(result.get('playback'), dict):
        raise SdError('MALFORMED_RESPONSE')
    rows = result['playback'].get('search_video_results')
    if not isinstance(rows, list) or len(rows) > MAX_CLIP_ENTRIES:
        raise SdError('MALFORMED_RESPONSE')
    start_day, end_day = _day_bounds_utc(FIXED_DATE, '+07:00')
    candidates, labels, missing = set(), set(), 0
    for row in rows:
        label, item = _single_index_entry(row)
        if label in labels or not isinstance(item, dict):
            raise SdError('MALFORMED_RESPONSE')
        labels.add(label)
        start, end, kind = item.get('startTime'), item.get('endTime'), item.get('vedio_type')
        if type(start) is not int or type(end) is not int or not start_day <= start < end <= end_day:
            raise SdError('MALFORMED_RESPONSE')
        if not ((type(kind) is int and kind in (1,2)) or (isinstance(kind,str) and kind in ('1','2'))):
            raise SdError('MALFORMED_RESPONSE')
        channels = item.get('chn_times')
        if channels is None:
            missing += 1
            continue
        if not isinstance(channels, dict) or not channels or not set(channels) <= {'1','2'}:
            raise SdError('MALFORMED_RESPONSE')
        for lens, timing in channels.items():
            if not isinstance(timing, dict):
                raise SdError('MALFORMED_RESPONSE')
            lens_start = timing.get('event_start_time')
            if type(lens_start) is not int or not start <= lens_start < end:
                raise SdError('MALFORMED_RESPONSE')
            if lens == '1' and 5 <= end-lens_start <= 180:
                candidates.add((lens_start,end))
    return sorted(candidates, key=lambda x:(x[1]-x[0],x[0])), len(rows), missing


def probe_fixed_metadata(token, terminal_uuid, selected, session_guard=None):
    """Three readonly requests; public report contains counts, never times/IDs."""
    budget = _DeviceBudget(session_guard=session_guard)
    facts = {'fixed_mapping':'UNVERIFIED', 'media_downloaded':False}
    stage = 'METADATA'
    try:
        if not isinstance(selected,dict) or selected.get('model_kind') not in ('EXACT','VARIANT') or not cloud._validate_canonical_app_server(selected.get('app_server')):
            raise SdError('IDENTITY_MISMATCH')
        device = _validate_device_id(selected.get('thing_name'))
        def send(batch, uid=None):
            reqs = _expected_requests(batch,FIXED_DATE,uid)
            raw = _device_request(budget,token,terminal_uuid,device,reqs,batch,FIXED_DATE,uid)
            return _parse_responses(raw,{r['method'] for r in reqs})
        meta=send('metadata')
        _read_device_model(meta['getDeviceInfo'],selected['model_kind'])
        if _read_timezone_offset(meta['getTimezone']) != '+07:00' or _read_sd_status(meta['getSdCardStatus']) != 'NORMAL':
            raise SdError('IDENTITY_MISMATCH')
        stage='CALENDAR'
        cal=send('calendar')
        uid=_read_user_id(cal['getUserID'])
        if uid is None or not _read_calendar(cal['searchDateWithVideo'],FIXED_DATE):
            raise SdError('MALFORMED_RESPONSE')
        stage='CLIPS'
        response=send('clip-utc',uid)
        candidates,count,missing=_fixed_intervals(response['searchVideoWithUTC'])
        facts.update(clip_count=count,rows_without_lens_metadata=missing,fixed_candidate_count=len(candidates),
                     lens1_metadata_present=bool(candidates),list_scope='FIRST_PAGE_ONLY')
        if candidates:
            facts['shortest_candidate_seconds']=candidates[0][1]-candidates[0][0]
        return _report('SUCCESS',extra=dict(facts,requests_used=budget.requests))
    except (SdError,cloud.ProbeError) as exc:
        if getattr(exc,'http_status',None) is not None: facts['http_status']=exc.http_status
        return _report('BLOCKED',exc.code,dict(facts,requests_used=budget.requests),stage)


# -- orchestration ------------------------------------------------------------


def _report(status, reason=None, extra=None, stage=None):
    if reason is not None and reason not in ERROR_CODES:
        reason = "UNKNOWN_ERROR"
    if stage is not None and stage not in STAGES:
        stage = None
    report = {"tool": TOOL_NAME, "status": status, "reason": reason}
    if stage is not None:
        report["stage"] = stage
    if extra:
        report.update(extra)
    return report


def probe_selected_device(token, terminal_uuid, selected, date, session_guard=None):
    """Read four fixed batches from the unique selected C545D, in memory only."""
    facts = {"fixed_mapping": "UNKNOWN"}
    try:
        _validate_date(date)
        if not isinstance(selected, dict):
            raise SdError("NOT_SELECTED")
        device_id = _validate_device_id(selected.get("thing_name"))
        expected_kind = selected.get("model_kind")
        if expected_kind not in ("EXACT", "VARIANT"):
            raise SdError("IDENTITY_MISMATCH")
        if not cloud._validate_canonical_app_server(selected.get("app_server")):
            raise SdError("INVALID_INPUT")
    except SdError as exc:
        return _report("BLOCKED", exc.code, dict(facts, requests_used=0))
    budget = _DeviceBudget(session_guard=session_guard)
    stage = "METADATA"

    def send(batch, uid=None):
        if session_guard is not None:
            session_guard()
        requests = _expected_requests(batch, date, uid)
        raw = _device_request(budget, token, terminal_uuid, device_id, requests, batch, date, uid)
        methods = {r["method"] for r in requests}
        try:
            return _parse_responses(raw, methods, methods if batch == "capability" else frozenset())
        except SdError as exc:
            if exc.code == "MALFORMED_RESPONSE":
                exc.detail = "ENVELOPE_FORMAT"
            raise

    try:
        data = send("metadata")
        facts["device_model_kind"] = _read_device_model(data["getDeviceInfo"], expected_kind)
        facts["timezone_offset"] = _read_timezone_offset(data["getTimezone"])
        facts["sd_status"] = _read_sd_status(data["getSdCardStatus"])
        stage = "CAPABILITY"
        facts["capabilities"] = _read_capabilities(None, None, None)
        try:
            data = send("capability")
            facts["capabilities"] = _read_capabilities(
                data["getAppComponentList"], data["getStreamCapability"], data["getVideoCapability"])
        except SdError as exc:
            if exc.code in ("TIME_BUDGET_EXCEEDED", "REQUEST_LIMIT_EXCEEDED"):
                raise
            facts["capability_reason"] = exc.code
        stage = "CALENDAR"
        data = send("calendar")
        uid = _read_user_id(data["getUserID"])
        facts["user_id_valid"] = uid is not None
        has_date = _read_calendar(data["searchDateWithVideo"], date)
        facts["calendar_has_requested_date"] = has_date
        rows = data["searchDateWithVideo"]["playback"]["search_results"]
        outside_count = sum(next(iter(row.values()))["date"] != date for row in rows)
        facts["calendar_other_dates_count"] = outside_count
        if not has_date:
            facts.update(clip_count=0, list_scope="NO_MATCHING_DATE" if outside_count else "NO_CLIPS")
        else:
            if uid is None:
                raise SdError("MALFORMED_RESPONSE", detail="USER_ID_INVALID")
            stage = "CLIPS"
            if facts["timezone_offset"] is None:
                raise SdError("MALFORMED_RESPONSE", detail="TIMEZONE_UNKNOWN")
            data = send("clip", uid)
            count, scope = _read_clips(data["searchVideoOfDay"], facts["timezone_offset"], date)
            facts.update(clip_count=count, list_scope=scope)
    except (SdError, cloud.ProbeError) as exc:
        if getattr(exc, "detail", None) in SD_DETAILS:
            facts["detail"] = exc.detail
        if getattr(exc, "http_status", None) is not None:
            facts["http_status"] = exc.http_status
        if getattr(exc, "gateway_reason", None) is not None:
            facts["gateway_reason"] = exc.gateway_reason
        return _report("BLOCKED", exc.code, dict(facts, requests_used=budget.requests), stage)
    except Exception:
        return _report("BLOCKED", "UNKNOWN_ERROR", dict(facts, requests_used=budget.requests), stage)
    return _report("SUCCESS", extra=dict(facts, requests_used=budget.requests))


def run(target_name_sha256, date="20261012"):
    """Validate inputs, then login + name-select + probe through one flow.

    Both the digest and the exact date are validated before any dialog or
    network call. The native-dialog login/MFA/discovery flow is entirely
    reused from :mod:`tools.ft_cloud_probe`; ``probe_selected_device`` is
    invoked only for a single exact owner-name match.
    """
    try:
        date = _validate_date(date)
    except SdError as exc:
        return _report("BLOCKED", exc.code)
    try:
        cloud._validate_target_name_digest(target_name_sha256)
    except cloud.ProbeError:
        return _report("BLOCKED", "INVALID_INPUT")
    if target_name_sha256 is None:
        return _report("BLOCKED", "INVALID_INPUT")

    def callback(token, terminal_uuid, selected):
        return probe_selected_device(token, terminal_uuid, selected, date)

    login_report = cloud.login_check_command(
        target_name_sha256=target_name_sha256, on_selected_camera=callback
    )
    sd_report = login_report.get("sd_probe")
    report = {
        "tool": TOOL_NAME,
        "cloud_status": login_report.get("status"),
        "cloud_reason": login_report.get("reason"),
        "cloud_stage": login_report.get("stage"),
        "cloud_detail": login_report.get("detail"),
        "inventory_status": login_report.get("inventory_status"),
    }
    if sd_report is not None:
        report.update({k: v for k, v in sd_report.items() if k not in ("tool",)})
        report["status"] = sd_report.get("status")
        report["reason"] = sd_report.get("reason")
    else:
        report["status"] = "BLOCKED"
        report["reason"] = (
            login_report.get("reason")
            if login_report.get("status") != "SUCCESS"
            else "NOT_SELECTED"
        )
    return report
