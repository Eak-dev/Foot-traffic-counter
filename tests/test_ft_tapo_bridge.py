"""Tests for tools/ft_tapo_bridge.py.

Everything here is synthetic: a hand-authored fake SDK class (never the
real pytapo), a fake sender, and a fake clock. No pytapo import, no
socket, no real camera. Run from the repository root:
python3 -m unittest discover -s tests -t . -v
"""
import math
import unittest

from tools import ft_tapo_bridge as bridge_mod

DEFAULT_LIMITS = dict(max_calls=6, deadline_s=10.0, max_index=1000, max_time_range=100000, max_page_size=50)
SYNTHETIC_DAY_RESULTS = [{"alarm_type": 0, "channel": 0, "endRelative": 10, "id": "clip-1", "startRelative": 0}]
SYNTHETIC_UTC_RESULTS = [{"alarm_type": 0, "channel": 0, "endTime": 20, "id": "clip-2", "startTime": 10}]


def make_clock(start=1000.0, step=1.0):
    state = {"value": start - step}

    def clock():
        state["value"] += step
        return state["value"]

    return clock


# --- hand-authored fake SDK (never copied from upstream) -------------------

class FakeSDK:
    """Minimal stand-in exercising the same self.* surface as the four
    pinned upstream methods, written independently for this test."""

    def getUserID(self):
        self.logger.debugLog("getUserID")
        if self.userID is not False:
            return self.userID
        request = {
            "method": "multipleRequest",
            "params": {"requests": [{"method": "getUserID", "params": {"system": {"get_user_id": "null"}}}]},
        }
        response = self.performRequest(request)
        leaf = response["result"]["responses"][0]
        if leaf.get("error_code", 0) != 0:
            raise Exception(self.getErrorMessage(leaf.get("error_code")))
        self.userID = leaf["result"]["user_id"]
        return self.userID

    def executeFunction(self, method, params):
        self.logger.debugLog("executeFunction", method)
        request = {"method": "multipleRequest", "params": {"requests": [{"method": method, "params": params}]}}
        response = self.performRequest(request)
        leaf = response["result"]["responses"][0]
        error_code = leaf.get("error_code", 0)
        if error_code == -64303:
            try:
                self.setCruise(False)
            except Exception:
                pass
            return self.performRequest(request)["result"]["responses"][0].get("result")
        if error_code != 0:
            raise Exception(self.getErrorMessage(error_code))
        return leaf.get("result")

    def getRecordings(self, date, startIndex=0, endIndex=999999999):
        if self.childID is not None:
            raise Exception("child devices not supported in this fake")
        self.getUserID()
        params = {
            "playback": {
                "search_video_utility": {
                    "channel": 0, "date": date, "id": "A",
                    "start_index": startIndex, "end_index": endIndex,
                }
            }
        }
        result = self.executeFunction("searchVideoOfDay", params)
        return result["playback"]["search_video_results"]

    def getRecordingsUTC(self, startTime, endTime, startIndex=0, endIndex=999999999):
        if self.childID is not None:
            raise Exception("child devices not supported in this fake")
        self.getUserID()
        params = {
            "playback": {
                "search_video_with_utc": {
                    "channel": 0, "id": "A",
                    "start_time": startTime, "end_time": endTime,
                    "start_index": startIndex, "end_index": endIndex,
                }
            }
        }
        result = self.executeFunction("searchVideoWithUTC", params)
        return result["playback"]["search_video_results"]


class FakeSDKRepeatListing(FakeSDK):
    def getRecordings(self, date, startIndex=0, endIndex=999999999):
        self.getUserID()
        params = {
            "playback": {
                "search_video_utility": {
                    "channel": 0, "date": date, "id": "A",
                    "start_index": startIndex, "end_index": endIndex,
                }
            }
        }
        self.executeFunction("searchVideoOfDay", params)
        result = self.executeFunction("searchVideoOfDay", params)
        return result["playback"]["search_video_results"]


class FakeSDKWidenScope(FakeSDK):
    def getRecordings(self, date, startIndex=0, endIndex=999999999):
        self.getUserID()
        params = {
            "playback": {
                "search_video_utility": {
                    "channel": 0, "date": date, "id": "A",
                    "start_index": startIndex, "end_index": endIndex,
                }
            }
        }
        self.executeFunction("searchVideoOfDay", params)
        wider = {
            "playback": {
                "search_video_utility": {
                    "channel": 0, "date": date, "id": "A",
                    "start_index": startIndex, "end_index": endIndex + 1,
                }
            }
        }
        result = self.executeFunction("searchVideoOfDay", wider)
        return result["playback"]["search_video_results"]


class FakeSDKRepeatUserID(FakeSDK):
    def getRecordings(self, date, startIndex=0, endIndex=999999999):
        self.getUserID()
        self.userID = False
        self.getUserID()
        return SYNTHETIC_DAY_RESULTS


class FakeSDKNoRequest(FakeSDK):
    def getRecordings(self, date, startIndex=0, endIndex=999999999):
        return list(SYNTHETIC_DAY_RESULTS)


class FakeSDKReentrant(FakeSDK):
    def getRecordings(self, date, startIndex=0, endIndex=999999999):
        self.getUserID()
        try:
            self._bridge.list_day(date, startIndex, endIndex - startIndex + 1)
        except bridge_mod.BridgeError:
            pass
        params = {
            "playback": {
                "search_video_utility": {
                    "channel": 0, "date": date, "id": "A",
                    "start_index": startIndex, "end_index": endIndex,
                }
            }
        }
        result = self.executeFunction("searchVideoOfDay", params)
        return result["playback"]["search_video_results"]


class _CustomMeta(type):
    def __getattribute__(cls, name):
        if name not in ("__mro__", "__dict__", "__name__"):
            raise AssertionError("bridge touched metaclass attribute %r" % name)
        return type.__getattribute__(cls, name)


class FakeSDKMissingMethod:
    def getUserID(self):
        return False

    def getRecordings(self, date, startIndex=0, endIndex=999999999):
        return []

    def getRecordingsUTC(self, startTime, endTime, startIndex=0, endIndex=999999999):
        return []
    # executeFunction intentionally missing


class FakeSDKNonFunctionAttr(FakeSDK):
    executeFunction = staticmethod(lambda method, params: None)


# --- sender helpers ----------------------------------------------------

def make_sender(user_id="synthetic-id", day_results=None, utc_results=None, include_method=False, hooks=None):
    day_results = SYNTHETIC_DAY_RESULTS if day_results is None else day_results
    utc_results = SYNTHETIC_UTC_RESULTS if utc_results is None else utc_results
    calls = {"count": 0}
    hooks = hooks or {}

    def sender(request):
        calls["count"] += 1
        leaf = request["params"]["requests"][0]
        method = leaf["method"]
        if method in hooks:
            return hooks[method](leaf, calls["count"])
        if method == "getUserID":
            body = {"error_code": 0, "result": {"user_id": user_id}}
        elif method == "searchVideoOfDay":
            body = {"error_code": 0, "result": {"playback": {"search_video_results": day_results}}}
        elif method == "searchVideoWithUTC":
            body = {"error_code": 0, "result": {"playback": {"search_video_results": utc_results}}}
        else:
            raise AssertionError("unexpected method %s" % method)
        if include_method:
            body["method"] = method
        return {"result": {"responses": [body]}}

    sender.calls = calls
    return sender


def make_bridge(sdk_class=FakeSDK, sender=None, clock=None, **overrides):
    limits = dict(DEFAULT_LIMITS)
    limits.update(overrides)
    sender = sender or make_sender()
    clock = clock or make_clock()
    return bridge_mod.Bridge(sdk_class, sender, clock, **limits), sender, clock


# --- tests ---------------------------------------------------------------

class SuccessPathTests(unittest.TestCase):
    def test_list_day_and_list_utc_success(self):
        bridge, sender, _ = make_bridge()
        day = bridge.list_day("20261008", 0, 10)
        self.assertEqual(day, SYNTHETIC_DAY_RESULTS)
        utc = bridge.list_utc(10, 20, 0, 10)
        self.assertEqual(utc, SYNTHETIC_UTC_RESULTS)
        self.assertFalse(bridge._failed)
        self.assertGreater(sender.calls["count"], 0)

    def test_user_id_is_cached_across_calls(self):
        sender = make_sender()
        bridge, sender, _ = make_bridge(sender=sender)
        bridge.list_day("20261008", 0, 10)
        calls_after_first = sender.calls["count"]
        bridge.list_day("20261008", 0, 10)
        calls_after_second = sender.calls["count"]
        # second call must not re-send getUserID (cached on the facade)
        self.assertEqual(calls_after_second - calls_after_first, 1)

    def test_optional_matching_method_field_accepted(self):
        bridge, _, _ = make_bridge(sender=make_sender(include_method=True))
        self.assertEqual(bridge.list_day("20261008", 0, 10), SYNTHETIC_DAY_RESULTS)


class ConstructorTripwireTests(unittest.TestCase):
    def test_constructor_never_calls_sdk_init_or_new(self):
        events = []

        class Tripwire:
            def __new__(cls, *a, **k):
                events.append("new")
                return super().__new__(cls)

            def __init__(self, *a, **k):
                events.append("init")

            def __init_subclass__(cls, **k):
                events.append("init_subclass")
                super().__init_subclass__(**k)

            def getUserID(self):
                return False

            def getRecordings(self, date, startIndex=0, endIndex=999999999):
                return []

            def getRecordingsUTC(self, startTime, endTime, startIndex=0, endIndex=999999999):
                return []

            def executeFunction(self, method, params):
                return None

        make_bridge(sdk_class=Tripwire)
        self.assertEqual(events, [])


class LoggerSilenceTests(unittest.TestCase):
    def test_logger_debug_log_is_silent_and_returns_none(self):
        bridge, _, _ = make_bridge()
        self.assertIsNone(bridge._facade.logger.debugLog("anything", key="value"))


class ConstructorLimitTests(unittest.TestCase):
    def test_invalid_deadline_values_rejected_without_sender_call(self):
        sender = make_sender()
        for bad in (float("nan"), float("inf"), float("-inf"), 0, -1.0, True, False, "5"):
            with self.subTest(deadline_s=bad):
                with self.assertRaises(bridge_mod.BridgeError):
                    make_bridge(sender=sender, deadline_s=bad)
        self.assertEqual(sender.calls["count"], 0)

    def test_invalid_max_calls_rejected(self):
        sender = make_sender()
        for bad in (0, -1, True, False, 1.5, "3", 10_000_000):
            with self.subTest(max_calls=bad):
                with self.assertRaises(bridge_mod.BridgeError):
                    make_bridge(sender=sender, max_calls=bad)
        self.assertEqual(sender.calls["count"], 0)

    def test_invalid_index_time_page_bounds_rejected(self):
        sender = make_sender()
        bad_limits = [
            dict(max_index=-1), dict(max_index=10 ** 9), dict(max_index=1.5), dict(max_index=True),
            dict(max_time_range=0), dict(max_time_range=float("nan")), dict(max_time_range=-5),
            dict(max_page_size=0), dict(max_page_size=-1), dict(max_page_size=True), dict(max_page_size=10 ** 6),
        ]
        for overrides in bad_limits:
            with self.subTest(**overrides):
                with self.assertRaises(bridge_mod.BridgeError):
                    make_bridge(sender=sender, **overrides)
        self.assertEqual(sender.calls["count"], 0)

    def test_non_callable_sender_or_clock_rejected(self):
        with self.assertRaises(bridge_mod.BridgeError):
            bridge_mod.Bridge(FakeSDK, "not-callable", make_clock(), **DEFAULT_LIMITS)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge_mod.Bridge(FakeSDK, make_sender(), "not-callable", **DEFAULT_LIMITS)


class InvalidSdkClassTests(unittest.TestCase):
    def test_non_class_sdk_rejected(self):
        for bad in (None, 42, "FakeSDK", FakeSDK(), lambda: None):
            with self.subTest(sdk=bad):
                with self.assertRaises(bridge_mod.BridgeError):
                    make_bridge(sdk_class=bad)

    def test_custom_metaclass_rejected_without_touching_mro(self):
        MetaSdk = _CustomMeta("MetaSdk", (), {
            "getUserID": lambda self: False,
            "getRecordings": lambda self, date, startIndex=0, endIndex=999999999: [],
            "getRecordingsUTC": lambda self, startTime, endTime, startIndex=0, endIndex=999999999: [],
            "executeFunction": lambda self, method, params: None,
        })
        with self.assertRaises(bridge_mod.BridgeError):
            make_bridge(sdk_class=MetaSdk)

    def test_missing_pinned_method_rejected(self):
        with self.assertRaises(bridge_mod.BridgeError):
            make_bridge(sdk_class=FakeSDKMissingMethod)

    def test_non_function_attribute_rejected(self):
        with self.assertRaises(bridge_mod.BridgeError):
            make_bridge(sdk_class=FakeSDKNonFunctionAttr)


class ScopeAndRetryTests(unittest.TestCase):
    def test_repeated_listing_request_poisons(self):
        bridge, sender, _ = make_bridge(sdk_class=FakeSDKRepeatListing)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)

    def test_scope_widening_rejected(self):
        bridge, _, _ = make_bridge(sdk_class=FakeSDKWidenScope)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)

    def test_repeated_get_user_id_poisons(self):
        bridge, _, _ = make_bridge(sdk_class=FakeSDKRepeatUserID)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)

    def test_no_request_sent_denied(self):
        bridge, sender, _ = make_bridge(sdk_class=FakeSDKNoRequest)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)

    def test_reentrant_listing_denied_and_cannot_reset_budget(self):
        bridge, sender, _ = make_bridge(sdk_class=FakeSDKReentrant, max_calls=6)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)
        calls_at_failure = sender.calls["count"]
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_utc(1, 2, 0, 10)
        self.assertEqual(sender.calls["count"], calls_at_failure)

    def test_recovery_setter_denial_latches_and_blocks_further_sends(self):
        attempts = {"count": 0}

        def recovery_hook(_leaf, _n):
            attempts["count"] += 1
            return {"result": {"responses": [{"error_code": -64303}]}}

        sender = make_sender(hooks={"searchVideoOfDay": recovery_hook})
        bridge, sender, _ = make_bridge(sdk_class=FakeSDK, sender=sender)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)
        # exactly one real send reached the listing method before the denial latched
        self.assertEqual(attempts["count"], 1)
        calls_after_failure = sender.calls["count"]
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertEqual(sender.calls["count"], calls_after_failure)

    def test_failure_latches_across_later_public_calls(self):
        bridge, sender, _ = make_bridge(sdk_class=FakeSDKNoRequest)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        calls_at_failure = sender.calls["count"]
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261009", 0, 10)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_utc(1, 2, 0, 10)
        self.assertEqual(sender.calls["count"], calls_at_failure)


class InvalidPublicArgsTests(unittest.TestCase):
    def test_invalid_list_day_args_rejected_without_poison_or_sends(self):
        sender = make_sender()
        bridge, sender, _ = make_bridge(sender=sender)
        for start_index, page_size in ((-1, 10), (0, 0), (True, 10), (0, True), (1.5, 10)):
            with self.subTest(start_index=start_index, page_size=page_size):
                with self.assertRaises(bridge_mod.BridgeError):
                    bridge.list_day("20261008", start_index, page_size)
                self.assertFalse(bridge._failed)
        self.assertEqual(sender.calls["count"], 0)
        # bridge still usable afterwards, proving no poisoning occurred
        self.assertEqual(bridge.list_day("20261008", 0, 10), SYNTHETIC_DAY_RESULTS)

    def test_out_of_bound_index_or_page_size_rejected_without_poison(self):
        bridge, sender, _ = make_bridge(max_index=5, max_page_size=3)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 100)
        self.assertFalse(bridge._failed)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertFalse(bridge._failed)


class ClockAndBudgetTests(unittest.TestCase):
    def test_clock_failure_at_start_poisons(self):
        def bad_clock():
            raise RuntimeError("clock secret boom")

        bridge, sender, _ = make_bridge(clock=bad_clock)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)
        self.assertEqual(sender.calls["count"], 0)

    def test_clock_regression_after_last_call_poisons(self):
        values = iter([100.0, 101.0, 50.0])

        def clock():
            return next(values)

        bridge, sender, _ = make_bridge(clock=clock)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)

    def test_call_budget_exceeded_poisons(self):
        bridge, sender, _ = make_bridge(max_calls=1)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)

    def test_sender_exception_is_redacted(self):
        def exploding_sender(_request):
            raise RuntimeError("super-secret-credential-xyz")

        bridge, _, _ = make_bridge(sender=exploding_sender)
        with self.assertRaises(bridge_mod.BridgeError) as ctx:
            bridge.list_day("20261008", 0, 10)
        self.assertNotIn("secret", str(ctx.exception))
        self.assertNotIn("secret", repr(ctx.exception.args))


class MalformedEnvelopeTests(unittest.TestCase):
    def test_malformed_sdk_output_permanently_stops_bridge(self):
        class BadOutput(FakeSDK):
            def getRecordings(self, *args):
                FakeSDK.getRecordings(self, *args)
                return [object()]

        bridge, sender, _ = make_bridge(sdk_class=BadOutput)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        count = sender.calls["count"]
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)
        self.assertEqual(sender.calls["count"], count)

    def test_sdk_cannot_swallow_malformed_reply_and_send_again(self):
        class SwallowBadReply(FakeSDK):
            def getRecordings(self, *args):
                try:
                    self.getUserID()
                except bridge_mod.BridgeError:
                    pass
                return FakeSDK.getRecordings(self, *args)

        sender = make_sender(hooks={"getUserID": lambda leaf, n: {
            "result": {"responses": [{"error_code": 0, "result": {"user_id": object()}}]}
        }})
        bridge, _, _ = make_bridge(sdk_class=SwallowBadReply, sender=sender)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)
        self.assertEqual(sender.calls["count"], 1)

    def test_non_json_method_rejected_before_copy_hook(self):
        copy_hooks = []

        class HookedMethod(str):
            def __deepcopy__(self, memo):
                copy_hooks.append(True)
                raise RuntimeError("synthetic-private-copy-detail")

        sender = make_sender(hooks={"searchVideoOfDay": lambda leaf, n: {
            "result": {"responses": [{"method": HookedMethod("searchVideoOfDay"),
                "error_code": 0, "result": {"playback": {"search_video_results": []}}}]}
        }})
        bridge, _, _ = make_bridge(sender=sender)
        with self.assertRaises(bridge_mod.BridgeError) as ctx:
            bridge.list_day("20261008", 0, 10)
        self.assertTrue(bridge._failed)
        self.assertEqual(copy_hooks, [])
        self.assertNotIn("synthetic-private", str(ctx.exception))

    def _bridge_with_hook(self, hook):
        sender = make_sender(hooks={"searchVideoOfDay": hook})
        return make_bridge(sender=sender)

    def test_malformed_envelope_shapes_rejected(self):
        bad_envelopes = [
            lambda leaf, n: {"unexpected": True},
            lambda leaf, n: {"result": {"responses": []}},
            lambda leaf, n: {"result": {"responses": "not-a-list"}},
            lambda leaf, n: {"result": {"responses": [{"error_code": 0, "unknown_field": 1}]}},
            lambda leaf, n: {"result": {"responses": [{"error_code": True}]}},
            lambda leaf, n: {"result": {"responses": [{"error_code": None}]}},
            lambda leaf, n: {"result": {"responses": [{"error_code": 0.5}]}},
            lambda leaf, n: {"result": {"responses": [{"error_code": 0, "method": 5}]}},
            lambda leaf, n: {"result": {"responses": [{"error_code": 0, "method": "searchVideoWithUTC"}]}},
        ]
        for hook in bad_envelopes:
            with self.subTest(hook=hook):
                bridge, _, _ = self._bridge_with_hook(hook)
                with self.assertRaises(bridge_mod.BridgeError):
                    bridge.list_day("20261008", 0, 10)
                self.assertTrue(bridge._failed)

    def test_malformed_result_tree_rejected(self):
        class _DictSubclass(dict):
            pass

        bad_results = [
            lambda leaf, n: {"result": {"responses": [{"error_code": 0, "result": {
                "playback": {"search_video_results": [{"x": float("nan")}]}}}]}},
            lambda leaf, n: {"result": {"responses": [{"error_code": 0, "result": {
                "playback": {"search_video_results": [{"x": float("inf")}]}}}]}},
            lambda leaf, n: {"result": {"responses": [{"error_code": 0, "result": {
                "playback": {"search_video_results": [{"x": object()}]}}}]}},
            lambda leaf, n: {"result": {"responses": [{"error_code": 0, "result": {
                "playback": {"search_video_results": _DictSubclass(a=1)}}}]}},
            lambda leaf, n: {"result": {"responses": [{"error_code": 0, "result": {
                "playback": {"search_video_results": [{"x": i} for i in range(100)]}}}]}},
        ]
        for hook in bad_results:
            with self.subTest(hook=hook):
                bridge, _, _ = self._bridge_with_hook(hook)
                with self.assertRaises(bridge_mod.BridgeError):
                    bridge.list_day("20261008", 0, 10)
                self.assertTrue(bridge._failed)

    def test_oversized_listing_rejected(self):
        oversized = [{"id": "c%d" % i} for i in range(5)]
        bridge, _, _ = make_bridge(sender=make_sender(day_results=oversized), max_page_size=50)
        with self.assertRaises(bridge_mod.BridgeError):
            bridge.list_day("20261008", 0, 2)
        self.assertTrue(bridge._failed)


class DeepCopyTests(unittest.TestCase):
    def test_source_request_mutation_cannot_widen_validated_scope(self):
        from unittest.mock import patch
        raw_requests = []

        class CapturedRequestSDK(FakeSDK):
            def executeFunction(self, method, params):
                request = {"method": "multipleRequest", "params": {
                    "requests": [{"method": method, "params": params}]}}
                raw_requests.append(request)
                return self.performRequest(request)["result"]["responses"][0]["result"]

        def record_seen_date(leaf, n):
            date = leaf["params"]["playback"]["search_video_utility"]["date"]
            return {"result": {"responses": [{"error_code": 0, "result": {
                "playback": {"search_video_results": [{"date_seen": date}]}
            }}]}}

        sender = make_sender(hooks={"searchVideoOfDay": record_seen_date})
        guarded_send = bridge_mod.ft_acquire.guarded_send

        def mutate_source_then_send(request, *args, **kwargs):
            if raw_requests:
                raw_requests[-1]["params"]["requests"][0]["params"]["playback"]["search_video_utility"]["date"] = "20261009"
            return guarded_send(request, *args, **kwargs)

        bridge, _, _ = make_bridge(sdk_class=CapturedRequestSDK, sender=sender)
        with patch.object(bridge_mod.ft_acquire, "guarded_send", side_effect=mutate_source_then_send):
            result = bridge.list_day("20261008", 0, 10)
        self.assertEqual(result, [{"date_seen": "20261008"}])

    def test_returned_listing_is_independent_of_sender_storage(self):
        shared_results = [{"id": "clip-1", "nested": {"value": 1}}]
        bridge, _, _ = make_bridge(sender=make_sender(day_results=shared_results))
        returned = bridge.list_day("20261008", 0, 10)
        shared_results[0]["nested"]["value"] = 999
        shared_results.append({"id": "clip-injected"})
        self.assertEqual(returned, [{"id": "clip-1", "nested": {"value": 1}}])

    def test_caller_mutation_of_returned_listing_does_not_alias_internal_state(self):
        bridge, sender, _ = make_bridge()
        returned_first = bridge.list_day("20261008", 0, 10)
        returned_first.append({"id": "mutated-by-caller"})
        returned_first[0]["nested-injection"] = True
        returned_second = bridge.list_day("20261008", 0, 10)
        self.assertEqual(returned_second, SYNTHETIC_DAY_RESULTS)


if __name__ == "__main__":
    unittest.main()
