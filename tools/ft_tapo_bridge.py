#!/usr/bin/env python3
"""FT-D0 OD-33: offline listing control-method bridge (no live SDK).

Pinned source reference: JurajNyiri/pytapo 3.4.26,
a2f0fbd1fa4f4fc79e9fb5df4e9893ca55a3ba8c (audited statically, never
imported/installed/executed here); caller-injected SDK class identity is
caller trust, not cryptographic proof of that version. Never imports
pytapo, opens a socket, instantiates/subclasses the injected class, or
reads real configuration/credentials. Selectively binds four already-
audited plain SDK functions onto a private, attribute-locked facade so
upstream `self.performRequest(...)`/`self.setCruise(...)` resolve to our
guard/denial instead of any real transport/recovery code. The cooperative
deadline below only runs between discrete steps; it cannot interrupt a
single call that blocks forever inside the injected SDK/sender.
"""
from __future__ import annotations

import types
from copy import deepcopy

from tools import ft_acquire

_BOUND_METHOD_NAMES = ("getUserID", "getRecordings", "getRecordingsUTC", "executeFunction")
_MAX_DEPTH = 8
_MAX_LEAVES = 1
_PLACEHOLDER_ID = "A"
_MAX_RESULT_NODES = 4096
_DEV_MAX_CALLS_CEILING = 1000
_ALLOWED_SCALAR_TYPES = (str, int, bool, type(None))
_SAFE_PREFLIGHT_REQUEST = {
    "method": "multipleRequest",
    "params": {"requests": [{"method": "getUserID", "params": {"system": {"get_user_id": "null"}}}]},
}


class BridgeError(Exception):
    """Stable redacted code only; never carries SDK/callback/exception text."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _finite_positive_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return False
    return value > 0


def _redacted_error_message(*_args, **_kwargs):
    return "ERROR"


def _make_deny_set_cruise(bridge):
    def _deny_set_cruise(*_args, **_kwargs):
        bridge._poison()
        raise BridgeError("RECOVERY_SETTER_DENIED")

    return _deny_set_cruise


class _SilentLogger:
    """Stand-in for the SDK's logger; never prints/stores anything."""

    __slots__ = ()

    def debugLog(self, *_args, **_kwargs):
        return None


_SILENT_LOGGER = _SilentLogger()


def _resolve_class_function(sdk_class, name):
    """Find `name` by walking __mro__.__dict__ only; never triggers a descriptor."""
    if type(sdk_class) is not type:
        raise BridgeError("INVALID_SDK_CLASS")
    for klass in sdk_class.__mro__:
        if name in klass.__dict__:
            value = klass.__dict__[name]
            if type(value) is not types.FunctionType:
                raise BridgeError("INVALID_SDK_METHOD")
            return value
    raise BridgeError("MISSING_SDK_METHOD")


class _Facade:
    """Attribute-locked stand-in for a real SDK instance; never constructed by the SDK."""

    __slots__ = (
        "_bridge", "userID", "childID", "getUserID", "getRecordings", "getRecordingsUTC",
        "executeFunction", "performRequest", "setCruise", "getErrorMessage", "logger",
    )


def _build_facade(sdk_class, bridge):
    if type(sdk_class) is not type:
        raise BridgeError("INVALID_SDK_CLASS")
    facade = _Facade()
    facade._bridge = bridge
    facade.userID = False
    facade.childID = None
    facade.performRequest = bridge._perform_request
    facade.setCruise = _make_deny_set_cruise(bridge)
    facade.getErrorMessage = _redacted_error_message
    facade.logger = _SILENT_LOGGER
    for name in _BOUND_METHOD_NAMES:
        setattr(facade, name, types.MethodType(_resolve_class_function(sdk_class, name), facade))
    return facade


def _scan_result_tree(value, depth, counter):
    """Bound depth/node-count of a sender-supplied result tree before any further use."""
    counter[0] += 1
    if counter[0] > _MAX_RESULT_NODES or depth < 0:
        raise BridgeError("MALFORMED_RESULT")
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise BridgeError("MALFORMED_RESULT")
            _scan_result_tree(item, depth - 1, counter)
    elif type(value) is list:
        for item in value:
            _scan_result_tree(item, depth - 1, counter)
    elif type(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise BridgeError("MALFORMED_RESULT")
    elif type(value) not in _ALLOWED_SCALAR_TYPES:
        raise BridgeError("MALFORMED_RESULT")


def _listing_fields_without_id(method, params):
    key = "search_video_utility" if method == "searchVideoOfDay" else "search_video_with_utc"
    return {k: v for k, v in params["playback"][key].items() if k != "id"}


def _read_clock(clock, prev):
    try:
        value = clock()
    except Exception:
        raise BridgeError("CLOCK_FAILED") from None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BridgeError("INVALID_CLOCK")
    if value != value or value in (float("inf"), float("-inf")):
        raise BridgeError("INVALID_CLOCK")
    if prev is not None and value < prev:
        raise BridgeError("CLOCK_REGRESSION")
    return value


def _valid_listing_result(result):
    key = "search_video_results"
    if type(result) is not dict or set(result.keys()) != {"playback"}:
        return None
    playback = result["playback"]
    if type(playback) is not dict or set(playback.keys()) != {key}:
        return None
    results = playback[key]
    return results if type(results) is list else None


class Bridge:
    """Offline listing control-method bridge; see docs/TAPO_BRIDGE_GUIDE.md."""

    def __init__(
        self, sdk_class, sender, clock, *,
        max_calls, deadline_s, max_index, max_time_range, max_page_size,
    ):
        if not callable(sender) or not callable(clock):
            raise BridgeError("INVALID_LIMITS")
        if (
            not isinstance(max_calls, int) or isinstance(max_calls, bool)
            or not (1 <= max_calls <= _DEV_MAX_CALLS_CEILING)
        ):
            raise BridgeError("INVALID_LIMITS")
        if not _finite_positive_number(deadline_s):
            raise BridgeError("INVALID_LIMITS")
        try:
            ft_acquire.validate_sd_request(
                _SAFE_PREFLIGHT_REQUEST, max_depth=_MAX_DEPTH, max_requests=_MAX_LEAVES,
                max_index=max_index, max_time_range=max_time_range, max_page_size=max_page_size,
            )
        except ft_acquire.RequestError:
            raise BridgeError("INVALID_LIMITS") from None
        if type(sdk_class) is not type:
            raise BridgeError("INVALID_SDK_CLASS")
        self._sender = sender
        self._clock = clock
        self._max_calls = max_calls
        self._deadline_s = deadline_s
        self._max_index = max_index
        self._max_time_range = max_time_range
        self._max_page_size = max_page_size
        self._failed = False
        self._scope = None
        self._facade = _build_facade(sdk_class, self)

    def _poison(self):
        self._failed = True

    def _check_deadline(self, scope):
        try:
            clock_value = _read_clock(self._clock, scope["last_clock"])
        except BridgeError:
            self._poison()
            raise
        scope["last_clock"] = clock_value
        if clock_value - scope["start_clock"] > self._deadline_s:
            self._poison()
            raise BridgeError("DEADLINE_EXCEEDED")

    def _perform_request(self, request):
        """Bound onto the facade as `performRequest`; the real recovery/send chokepoint."""
        if self._failed:
            raise BridgeError("BRIDGE_FAILED")
        scope = self._scope
        if scope is None:
            self._poison()
            raise BridgeError("NO_ACTIVE_OPERATION")
        scope["calls"] += 1
        if scope["calls"] > self._max_calls:
            self._poison()
            raise BridgeError("CALL_BUDGET_EXCEEDED")
        self._check_deadline(scope)
        try:
            validated = ft_acquire.validate_sd_request(
                request, max_depth=_MAX_DEPTH, max_requests=_MAX_LEAVES,
                max_index=self._max_index, max_time_range=self._max_time_range,
                max_page_size=self._max_page_size,
            )
        except ft_acquire.RequestError:
            self._poison()
            raise BridgeError("GUARD_REJECTED") from None
        leaf = validated["params"]["requests"][0]
        method = leaf["method"]
        if method == "getUserID":
            if scope["seen_get_user_id"]:
                self._poison()
                raise BridgeError("REPEATED_GET_USER_ID")
            scope["seen_get_user_id"] = True
        elif method == scope["listing_method"] and (
            _listing_fields_without_id(method, leaf["params"]) == scope["listing_fields"]
        ):
            if scope["seen_listing"]:
                self._poison()
                raise BridgeError("REPEATED_LISTING_REQUEST")
            scope["seen_listing"] = True
        else:
            self._poison()
            raise BridgeError("SCOPE_VIOLATION")

        try:
            response = ft_acquire.guarded_send(
                validated, self._sender,
                max_depth=_MAX_DEPTH, max_requests=_MAX_LEAVES,
                max_index=self._max_index, max_time_range=self._max_time_range,
                max_page_size=self._max_page_size,
            )
        except ft_acquire.RequestError:
            self._poison()
            raise BridgeError("SENDER_FAILED") from None
        self._check_deadline(scope)
        try:
            return self._validate_envelope(response, method, scope)
        except Exception:
            self._poison()
            raise BridgeError("MALFORMED_ENVELOPE") from None

    def _validate_envelope(self, response, method, scope):
        """Bounded plain-dict envelope check; caps listing count to the requested page_size."""
        if type(response) is not dict or set(response.keys()) != {"result"}:
            self._poison()
            raise BridgeError("MALFORMED_ENVELOPE")
        outer = response["result"]
        if type(outer) is not dict or set(outer.keys()) != {"responses"}:
            self._poison()
            raise BridgeError("MALFORMED_ENVELOPE")
        responses = outer["responses"]
        if type(responses) is not list or len(responses) != _MAX_LEAVES:
            self._poison()
            raise BridgeError("MALFORMED_ENVELOPE")
        leaf_response = responses[0]
        allowed_keys = {"error_code", "result", "method"}
        if type(leaf_response) is not dict or not set(leaf_response.keys()) <= allowed_keys:
            self._poison()
            raise BridgeError("MALFORMED_ENVELOPE")
        if "method" in leaf_response:
            if not isinstance(leaf_response["method"], str) or leaf_response["method"] != method:
                self._poison()
                raise BridgeError("MALFORMED_ENVELOPE")
        error_code = leaf_response.get("error_code")
        if "error_code" in leaf_response and type(error_code) is not int:
            self._poison()
            raise BridgeError("MALFORMED_ENVELOPE")
        if "result" in leaf_response:
            _scan_result_tree(leaf_response["result"], _MAX_DEPTH, [0])
            if method != "getUserID":
                results = _valid_listing_result(leaf_response["result"])
                if results is None or len(results) > scope["page_size"]:
                    self._poison()
                    raise BridgeError("LISTING_OVERSIZED" if results is not None else "MALFORMED_RESULT")
        _scan_result_tree(response, _MAX_DEPTH + 5, [0])
        return deepcopy(response)

    def _run_listing(self, listing_method, start_index, page_size, build_leaf_params, call_sdk):
        """Shared preflight/scope/call/finish path for list_day and list_utc."""
        if self._failed:
            raise BridgeError("BRIDGE_FAILED")
        if self._scope is not None:
            self._poison()
            raise BridgeError("REENTRANT_LISTING")
        if (
            not isinstance(start_index, int) or isinstance(start_index, bool) or start_index < 0
            or not isinstance(page_size, int) or isinstance(page_size, bool) or page_size < 1
        ):
            raise BridgeError("INVALID_ARGUMENTS")
        end_index = start_index + page_size - 1
        leaf_params = build_leaf_params(end_index)
        preflight = {
            "method": "multipleRequest",
            "params": {"requests": [{"method": listing_method, "params": leaf_params}]},
        }
        try:
            ft_acquire.validate_sd_request(
                preflight, max_depth=_MAX_DEPTH, max_requests=_MAX_LEAVES,
                max_index=self._max_index, max_time_range=self._max_time_range,
                max_page_size=self._max_page_size,
            )
        except ft_acquire.RequestError:
            raise BridgeError("INVALID_ARGUMENTS") from None

        try:
            start_clock = _read_clock(self._clock, None)
        except BridgeError:
            self._poison()
            raise

        self._scope = {
            "listing_method": listing_method,
            "listing_fields": _listing_fields_without_id(listing_method, leaf_params),
            "page_size": page_size,
            "calls": 0,
            "seen_get_user_id": False,
            "seen_listing": False,
            "start_clock": start_clock,
            "last_clock": start_clock,
        }
        try:
            raw_list = call_sdk(end_index)
        except BridgeError:
            self._poison()
            raise
        except Exception:
            self._poison()
            raise BridgeError("SDK_CALL_FAILED") from None

        scope = self._scope
        self._scope = None
        self._check_deadline(scope)
        if self._failed or not scope["seen_listing"]:
            self._poison()
            raise BridgeError("NO_LISTING_REQUEST_SENT")
        if type(raw_list) is not list or len(raw_list) > page_size:
            self._poison()
            raise BridgeError("MALFORMED_RESULT")
        try:
            _scan_result_tree(raw_list, _MAX_DEPTH, [0])
            return deepcopy(raw_list)
        except Exception:
            self._poison()
            raise BridgeError("MALFORMED_RESULT") from None

    def list_day(self, date, start_index, page_size):
        """Return a bounded, defensively-copied raw listing for one day/page.

        Not a finished public manifest: an internal bounded raw-record list
        for a future normalizer step.
        """
        def build_leaf_params(end_index):
            return {
                "playback": {
                    "search_video_utility": {
                        "channel": 0, "date": date, "id": _PLACEHOLDER_ID,
                        "start_index": start_index, "end_index": end_index,
                    }
                }
            }

        return self._run_listing(
            "searchVideoOfDay", start_index, page_size, build_leaf_params,
            lambda end_index: self._facade.getRecordings(date, start_index, end_index),
        )

    def list_utc(self, start_time, end_time, start_index, page_size):
        """Return a bounded, defensively-copied raw listing for one UTC window/page."""
        def build_leaf_params(end_index):
            return {
                "playback": {
                    "search_video_with_utc": {
                        "channel": 0, "id": _PLACEHOLDER_ID,
                        "start_time": start_time, "end_time": end_time,
                        "start_index": start_index, "end_index": end_index,
                    }
                }
            }

        return self._run_listing(
            "searchVideoWithUTC", start_index, page_size, build_leaf_params,
            lambda end_index: self._facade.getRecordingsUTC(start_time, end_time, start_index, end_index),
        )
