"""Tests for tools/ft_acquire.py.

Everything here is synthetic: fake sender/fetch_page/sink/clock callables.
No pytapo import, no socket, no real file, no real camera. Run from the
repository root: python3 -m unittest discover -s tests -t . -v
"""
import contextlib
import io
import socket
import sys
import unittest
from datetime import datetime, timedelta, timezone

from tools import ft_acquire


def run_cli(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ft_acquire.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class TripwireSocket:
    def __call__(self, *args, **kwargs):
        raise AssertionError("no network access is permitted in ft_acquire")


class SenderSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, request):
        self.calls.append(request)
        return {"ok": True}


def valid_get_user_id():
    return {"method": "getUserID", "params": {"system": {"get_user_id": "null"}}}


def valid_search_day(start_index=0, end_index=9):
    return {
        "method": "searchVideoOfDay",
        "params": {
            "playback": {
                "search_video_utility": {
                    "channel": 0,
                    "date": "20261008",
                    "id": "req-1",
                    "start_index": start_index,
                    "end_index": end_index,
                }
            }
        },
    }


def valid_search_utc(start_index=0, end_index=9, start_time=1000, end_time=2000):
    return {
        "method": "searchVideoWithUTC",
        "params": {
            "playback": {
                "search_video_with_utc": {
                    "channel": 0,
                    "id": "req-2",
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_index": start_index,
                    "end_index": end_index,
                }
            }
        },
    }


def wrap(*leaves):
    return {"method": "multipleRequest", "params": {"requests": list(leaves)}}


LIMITS = dict(max_depth=8, max_requests=8, max_index=1000, max_time_range=10000, max_page_size=50)


class ValidateSdRequestTests(unittest.TestCase):
    def test_accepts_pinned_shapes(self):
        req = wrap(valid_get_user_id(), valid_search_day(), valid_search_utc())
        validated = ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(validated["method"], "multipleRequest")
        self.assertEqual(len(validated["params"]["requests"]), 3)

    def test_rejects_bare_leaf_without_wrapper(self):
        with self.assertRaises(ft_acquire.RequestError):
            ft_acquire.validate_sd_request(valid_get_user_id(), **LIMITS)

    def test_rejects_unknown_top_method(self):
        req = {"method": "setCruise", "params": {"requests": [valid_get_user_id()]}}
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "SETTER_BLOCKED")

    def test_rejects_nested_setter_anywhere(self):
        req = wrap(valid_get_user_id())
        req["params"]["requests"][0]["params"]["system"]["setCruiseEnable"] = False
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "SETTER_BLOCKED")

    def test_rejects_control_child_key(self):
        req = wrap(valid_get_user_id())
        req["params"]["requests"][0]["params"]["controlChild"] = {"x": 1}
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "SETTER_BLOCKED")

    def test_rejects_unknown_extra_key(self):
        req = wrap(valid_get_user_id())
        req["params"]["requests"][0]["extra"] = "x"
        with self.assertRaises(ft_acquire.RequestError):
            ft_acquire.validate_sd_request(req, **LIMITS)

    def test_rejects_unknown_nested_params_key(self):
        req = wrap(valid_search_day())
        leaf = req["params"]["requests"][0]
        leaf["params"]["playback"]["search_video_utility"]["extra"] = 1
        with self.assertRaises(ft_acquire.RequestError):
            ft_acquire.validate_sd_request(req, **LIMITS)

    def test_rejects_malformed_wrapper_requests_not_list(self):
        req = {"method": "multipleRequest", "params": {"requests": valid_get_user_id()}}
        with self.assertRaises(ft_acquire.RequestError):
            ft_acquire.validate_sd_request(req, **LIMITS)

    def test_rejects_empty_requests(self):
        req = wrap()
        with self.assertRaises(ft_acquire.RequestError):
            ft_acquire.validate_sd_request(req, **LIMITS)

    def test_rejects_too_many_requests(self):
        req = wrap(*[valid_get_user_id() for _ in range(5)])
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(
                req, max_depth=8, max_requests=2, max_index=1000, max_time_range=10000, max_page_size=50
            )
        self.assertEqual(ctx.exception.code, "REQUEST_COUNT_OUT_OF_BOUNDS")

    def test_rejects_tree_too_deep(self):
        req = wrap(valid_get_user_id())
        nested = {}
        node = nested
        for _ in range(20):
            node["next"] = {}
            node = node["next"]
        req["params"]["requests"][0]["params"]["system"]["deep"] = nested
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "TREE_TOO_DEEP")

    def test_rejects_non_calendar_date(self):
        req = wrap(valid_search_day())
        req["params"]["requests"][0]["params"]["playback"]["search_video_utility"]["date"] = "20261332"
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "INVALID_DATE")

    def test_rejects_float_zero_channel(self):
        req = wrap(valid_search_day())
        req["params"]["requests"][0]["params"]["playback"]["search_video_utility"]["channel"] = 0.0
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "INVALID_CHANNEL")

    def test_rejects_bool_index(self):
        req = wrap(valid_search_day())
        req["params"]["requests"][0]["params"]["playback"]["search_video_utility"]["start_index"] = True
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "INVALID_INDEX")

    def test_rejects_default999999999_index(self):
        req = wrap(valid_search_day(start_index=0, end_index=999999999))
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "INDEX_OUT_OF_BOUNDS")

    def test_rejects_index_above_explicit_max(self):
        req = wrap(valid_search_day(start_index=0, end_index=2000))
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "INDEX_OUT_OF_BOUNDS")

    def test_rejects_utc_time_range_over_bound(self):
        req = wrap(valid_search_utc(start_time=0, end_time=20000))
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "TIME_RANGE_OUT_OF_BOUNDS")

    def test_rejects_utc_time_not_int(self):
        req = wrap(valid_search_utc())
        req["params"]["requests"][0]["params"]["playback"]["search_video_with_utc"]["start_time"] = "1000"
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "INVALID_TIME")

    def test_rejects_invalid_limits(self):
        req = wrap(valid_get_user_id())
        bad_limits = [
            dict(LIMITS, max_depth=0),
            dict(LIMITS, max_depth=33),
            dict(LIMITS, max_requests=0),
            dict(LIMITS, max_index=-1),
            dict(LIMITS, max_index=ft_acquire.FORBIDDEN_INDEX),
            dict(LIMITS, max_index=ft_acquire.DEV_MAX_INDEX_CEILING + 1),
            dict(LIMITS, max_time_range=0),
            dict(LIMITS, max_page_size=0),
            dict(LIMITS, max_page_size=True),
            dict(LIMITS, max_page_size=ft_acquire.DEV_MAX_PAGE_SIZE_CEILING + 1),
        ]
        for kwargs in bad_limits:
            with self.assertRaises(ft_acquire.RequestError) as ctx:
                ft_acquire.validate_sd_request(req, **kwargs)
            self.assertEqual(ctx.exception.code, "INVALID_LIMITS")

    def test_rejects_method_list_without_crashing(self):
        req = wrap(valid_get_user_id())
        req["params"]["requests"][0]["method"] = []
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "SETTER_BLOCKED")

    def test_rejects_non_json_leaf_value(self):
        req = wrap(valid_get_user_id())
        req["params"]["requests"][0]["params"]["system"]["weird"] = object()
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "MALFORMED_TREE")

    def test_rejects_oversized_node_count_before_full_scan(self):
        req = wrap(valid_get_user_id())
        req["params"]["requests"][0]["params"]["system"]["huge"] = list(range(10000))
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "TREE_TOO_LARGE")

    def test_rejects_page_width_over_bound(self):
        req = wrap(valid_search_day(start_index=0, end_index=60))
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "PAGE_WIDTH_OUT_OF_BOUNDS")

    def test_rejects_utc_page_width_over_bound(self):
        req = wrap(valid_search_utc(start_index=0, end_index=60))
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.validate_sd_request(req, **LIMITS)
        self.assertEqual(ctx.exception.code, "PAGE_WIDTH_OUT_OF_BOUNDS")

    def test_mutation_isolation_after_validation(self):
        req = wrap(valid_get_user_id())
        validated = ft_acquire.validate_sd_request(req, **LIMITS)
        req["params"]["requests"][0]["method"] = "setCruise"
        self.assertEqual(validated["params"]["requests"][0]["method"], "getUserID")


class GuardedSendTests(unittest.TestCase):
    def test_valid_request_reaches_sender_once(self):
        spy = SenderSpy()
        req = wrap(valid_get_user_id())
        ft_acquire.guarded_send(req, spy, **LIMITS)
        self.assertEqual(len(spy.calls), 1)
        self.assertEqual(spy.calls[0]["method"], "multipleRequest")

    def test_sender_never_called_on_nested_setter(self):
        spy = SenderSpy()
        req = wrap(valid_get_user_id())
        req["params"]["requests"][0]["params"]["system"]["setCruise"] = False
        with self.assertRaises(ft_acquire.RequestError):
            ft_acquire.guarded_send(req, spy, **LIMITS)
        self.assertEqual(spy.calls, [])

    def test_sender_never_called_on_recovery_setter_shape(self):
        spy = SenderSpy()
        req = {"method": "setCruise", "params": {"enable": False}}
        with self.assertRaises(ft_acquire.RequestError):
            ft_acquire.guarded_send(req, spy, **LIMITS)
        self.assertEqual(spy.calls, [])

    def test_sender_never_called_on_malformed_wrapper(self):
        spy = SenderSpy()
        req = {"method": "multipleRequest", "params": {"requests": "not-a-list"}}
        with self.assertRaises(ft_acquire.RequestError):
            ft_acquire.guarded_send(req, spy, **LIMITS)
        self.assertEqual(spy.calls, [])

    def test_sender_never_called_on_shape_injection(self):
        spy = SenderSpy()
        req = wrap(valid_search_day())
        req["params"]["requests"][0]["params"]["playback"]["search_video_utility"]["id"] = ""
        with self.assertRaises(ft_acquire.RequestError):
            ft_acquire.guarded_send(req, spy, **LIMITS)
        self.assertEqual(spy.calls, [])

    def test_sender_receives_independent_copy(self):
        spy = SenderSpy()
        req = wrap(valid_get_user_id())
        ft_acquire.guarded_send(req, spy, **LIMITS)
        sent = spy.calls[0]
        sent["params"]["requests"][0]["method"] = "setCruise"
        spy2 = SenderSpy()
        ft_acquire.guarded_send(req, spy2, **LIMITS)
        self.assertEqual(spy2.calls[0]["params"]["requests"][0]["method"], "getUserID")

    def test_sender_failure_redacted(self):
        def failing_sender(request):
            raise RuntimeError("secret backend trace")

        req = wrap(valid_get_user_id())
        with self.assertRaises(ft_acquire.RequestError) as ctx:
            ft_acquire.guarded_send(req, failing_sender, **LIMITS)
        self.assertEqual(ctx.exception.code, "SENDER_FAILED")
        self.assertNotIn("secret backend trace", str(ctx.exception))

    def test_no_socket_access(self):
        original = socket.socket
        socket.socket = TripwireSocket()
        try:
            spy = SenderSpy()
            req = wrap(valid_get_user_id())
            ft_acquire.guarded_send(req, spy, **LIMITS)
            self.assertEqual(len(spy.calls), 1)
        finally:
            socket.socket = original


WINDOW_START = datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 10, 9, 0, 0, tzinfo=timezone.utc)


def clip(ref, minute):
    start = WINDOW_START + timedelta(minutes=minute)
    return {"ref": ref, "start": start, "end": start + timedelta(seconds=30), "fixed_lens_proof": True}


class CollectPagesTests(unittest.TestCase):
    def setUp(self):
        self.clock_value = [0.0]

    def clock(self):
        return self.clock_value[0]

    def test_stops_on_short_page(self):
        pages = [[clip("a", 1), clip("b", 2)], [clip("c", 3)]]

        def fetch_page(start_index, end_index):
            return pages.pop(0)

        result = ft_acquire.collect_pages(
            fetch_page, page_size=2, max_pages=10, max_records=100, deadline_s=60,
            clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
        )
        self.assertEqual([c["ref"] for c in result], ["a", "b", "c"])

    def test_stops_on_empty_page(self):
        pages = [[clip("a", 1)], []]

        def fetch_page(start_index, end_index):
            return pages.pop(0)

        result = ft_acquire.collect_pages(
            fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
            clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
        )
        self.assertEqual([c["ref"] for c in result], ["a"])

    def test_max_pages_exhausted_fails_visibly(self):
        def fetch_page(start_index, end_index):
            return [clip(f"r{start_index}", start_index + 1), clip(f"r{start_index + 1}", start_index + 2)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=2, max_pages=3, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "MAX_PAGES_EXHAUSTED")

    def test_rejects_oversized_page(self):
        def fetch_page(start_index, end_index):
            return [clip("a", 1), clip("b", 2), clip("c", 3)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=2, max_pages=5, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "PAGE_OVERSIZED")

    def test_stalled_identical_pages_rejected(self):
        def fetch_page(start_index, end_index):
            return [clip("a", 1), clip("b", 2)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=2, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "STALLED_PAGE")

    def test_stalled_reordered_full_page_rejected(self):
        def fetch_page(start_index, end_index):
            return [clip("b", 2), clip("a", 1)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=2, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "STALLED_PAGE")

    def test_short_final_page_repeating_prior_refs_reordered_allowed(self):
        pages = [[clip("a", 1), clip("b", 2), clip("c", 3)], [clip("b", 2), clip("a", 1)]]

        def fetch_page(start_index, end_index):
            return pages.pop(0)

        result = ft_acquire.collect_pages(
            fetch_page, page_size=3, max_pages=10, max_records=100, deadline_s=60,
            clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
        )
        self.assertEqual([c["ref"] for c in result], ["a", "b", "c"])

    def test_dedup_identical_repeat_is_allowed_before_short_page(self):
        pages = [[clip("a", 1), clip("b", 2)], [clip("a", 1)]]

        def fetch_page(start_index, end_index):
            return pages.pop(0)

        result = ft_acquire.collect_pages(
            fetch_page, page_size=2, max_pages=10, max_records=100, deadline_s=60,
            clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
        )
        self.assertEqual([c["ref"] for c in result], ["a", "b"])

    def test_conflicting_duplicate_ref_rejected(self):
        conflicting_start = WINDOW_START + timedelta(minutes=5)
        conflicting = dict(
            clip("a", 1), start=conflicting_start, end=conflicting_start + timedelta(seconds=30)
        )
        pages = [[clip("a", 1)], [conflicting]]

        def fetch_page(start_index, end_index):
            return pages.pop(0)

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=1, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "REF_CONFLICT")

    def test_rejects_out_of_window_clip(self):
        def fetch_page(start_index, end_index):
            return [clip("a", -10)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "OUT_OF_WINDOW")

    def test_rejects_naive_datetime(self):
        def fetch_page(start_index, end_index):
            return [{"ref": "a", "start": datetime(2026, 10, 8, 1), "end": datetime(2026, 10, 8, 1, 1),
                      "fixed_lens_proof": True}]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "NAIVE_TIME")

    def test_rejects_pseudo_tzinfo_with_none_offset(self):
        import datetime as dt_module

        class FakeTzinfo(dt_module.tzinfo):
            def utcoffset(self, _dt):
                return None

            def dst(self, _dt):
                return None

            def tzname(self, _dt):
                return "FAKE"

        def fetch_page(start_index, end_index):
            start = dt_module.datetime(2026, 10, 8, 1, tzinfo=FakeTzinfo())
            end = dt_module.datetime(2026, 10, 8, 1, 1, tzinfo=FakeTzinfo())
            return [{"ref": "a", "start": start, "end": end, "fixed_lens_proof": True}]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "NAIVE_TIME")

    def test_fetch_page_exception_redacted(self):
        def fetch_page(start_index, end_index):
            raise RuntimeError("secret backend trace")

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "FETCH_FAILED")
        self.assertNotIn("secret backend trace", str(ctx.exception))

    def test_window_timezone_exception_redacted_before_fetch(self):
        import datetime as dt_module

        class BrokenTimezone(dt_module.tzinfo):
            def utcoffset(self, _dt):
                raise RuntimeError("synthetic-private-timezone-detail")

        start = datetime(2026, 10, 8, tzinfo=BrokenTimezone())
        calls = []
        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                lambda a, b: calls.append((a, b)), page_size=1, max_pages=1,
                max_records=1, deadline_s=1, clock=self.clock,
                window_start=start, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "INVALID_WINDOW")
        self.assertNotIn("synthetic-private", str(ctx.exception))
        self.assertEqual(calls, [])

    def test_clock_regression_rejected(self):
        clock_values = [0.0, 5.0, 1.0]

        def clock():
            return clock_values.pop(0)

        def fetch_page(start_index, end_index):
            return [clip("a", 1)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "CLOCK_REGRESSION")

    def test_clock_exception_redacted(self):
        def boom_clock():
            raise RuntimeError("secret backend trace")

        def fetch_page(start_index, end_index):
            return [clip("a", 1)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=boom_clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "CLOCK_FAILED")
        self.assertNotIn("secret backend trace", str(ctx.exception))

    def test_clock_nan_rejected(self):
        def clock():
            return float("nan")

        def fetch_page(start_index, end_index):
            return [clip("a", 1)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "INVALID_CLOCK")

    def test_clock_bool_rejected(self):
        def clock():
            return True

        def fetch_page(start_index, end_index):
            return [clip("a", 1)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "INVALID_CLOCK")

    def test_deadline_checked_per_record(self):
        state = {"n": 0}

        def clock_with_jump():
            state["n"] += 1
            return 0.0 if state["n"] <= 2 else 100.0

        def fetch_page(start_index, end_index):
            return [clip("a", 1), clip("b", 2)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=1,
                clock=clock_with_jump, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "DEADLINE_EXCEEDED")

    def test_rejects_filename_like_ref(self):
        def fetch_page(start_index, end_index):
            return [{"ref": "../etc/passwd", "start": WINDOW_START + timedelta(minutes=1),
                      "end": WINDOW_START + timedelta(minutes=1, seconds=1), "fixed_lens_proof": True}]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "INVALID_REF")

    def test_rejects_unproven_fixed_lens(self):
        def fetch_page(start_index, end_index):
            return [dict(clip("a", 1), fixed_lens_proof=False)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "FIXED_LENS_UNPROVEN")

    def test_max_records_exceeded(self):
        def fetch_page(start_index, end_index):
            return [clip("a", 1), clip("b", 2)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=1, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "MAX_RECORDS_EXCEEDED")

    def test_deadline_exceeded(self):
        def fetch_page(start_index, end_index):
            self.clock_value[0] += 100
            return [clip("a", 1)]

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=1,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "DEADLINE_EXCEEDED")

    def test_no_before_after_page_hooks_supported(self):
        def fetch_page(start_index, end_index):
            return [clip("a", 1)]

        with self.assertRaises(TypeError):
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
                before_page=lambda idx: None,
            )

    def test_pagination_rejects_approach_to_forbidden_index(self):
        def fetch_page(start_index, end_index):
            raise AssertionError("fetch_page must not be called once the forbidden index is approached")

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=ft_acquire.FORBIDDEN_INDEX + 1, max_pages=1, max_records=100,
                deadline_s=60, clock=self.clock, window_start=WINDOW_START, window_end=WINDOW_END,
            )
        self.assertEqual(ctx.exception.code, "INDEX_OUT_OF_BOUNDS")

    def test_invalid_window_rejected(self):
        def fetch_page(start_index, end_index):
            return []

        with self.assertRaises(ft_acquire.CollectError) as ctx:
            ft_acquire.collect_pages(
                fetch_page, page_size=5, max_pages=10, max_records=100, deadline_s=60,
                clock=self.clock, window_start=WINDOW_END, window_end=WINDOW_START,
            )
        self.assertEqual(ctx.exception.code, "INVALID_WINDOW")


class FakeSink:
    def __init__(self, short_write_bytes=None, fail=False):
        self.data = bytearray()
        self.short_write_bytes = short_write_bytes
        self.fail = fail

    def write(self, chunk):
        if self.fail:
            raise OSError("synthetic backend failure detail that must never be echoed")
        n = len(chunk) if self.short_write_bytes is None else min(self.short_write_bytes, len(chunk))
        self.data.extend(chunk[:n])
        return n


class CopyBoundedTests(unittest.TestCase):
    def setUp(self):
        self.clock_value = [0.0]

    def clock(self):
        return self.clock_value[0]

    def test_exact_boundary_success(self):
        sink = FakeSink()
        chunks = [b"abc", b"de"]
        result = ft_acquire.copy_bounded(
            iter(chunks), sink, expected_length=5, max_bytes=5, deadline_s=60, clock=self.clock
        )
        self.assertEqual(result["status"], "STAGED")
        self.assertEqual(result["bytes_written"], 5)
        self.assertEqual(bytes(sink.data), b"abcde")
        import hashlib
        self.assertEqual(result["sha256"], hashlib.sha256(b"abcde").hexdigest())

    def test_rejects_empty_stream(self):
        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(iter([]), sink, expected_length=5, max_bytes=5, deadline_s=60, clock=self.clock)
        self.assertEqual(ctx.exception.code, "STREAM_TRUNCATED")

    def test_rejects_truncated_stream(self):
        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab"]), sink, expected_length=5, max_bytes=5, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "STREAM_TRUNCATED")

    def test_rejects_overlong_stream(self):
        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab", b"cdef"]), sink, expected_length=4, max_bytes=100, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "STREAM_OVERLONG")

    def test_budget_checked_before_write(self):
        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"abcdef"]), sink, expected_length=3, max_bytes=3, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "BUDGET_EXCEEDED")
        self.assertEqual(bytes(sink.data), b"")

    def test_rejects_invalid_limits(self):
        sink = FakeSink()
        for kwargs in (
            dict(expected_length=0, max_bytes=5, deadline_s=60),
            dict(expected_length=5, max_bytes=0, deadline_s=60),
            dict(expected_length=True, max_bytes=5, deadline_s=60),
            dict(expected_length=5, max_bytes=5, deadline_s=float("nan")),
            dict(expected_length=5, max_bytes=5, deadline_s=float("inf")),
            dict(expected_length=5, max_bytes=5, deadline_s=True),
            dict(expected_length=5, max_bytes=3, deadline_s=60),
        ):
            with self.assertRaises(ft_acquire.CopyError) as ctx:
                ft_acquire.copy_bounded(iter([b"ab"]), sink, clock=self.clock, **kwargs)
            self.assertEqual(ctx.exception.code, "INVALID_LIMITS")

    def test_short_write_handled(self):
        sink = FakeSink(short_write_bytes=1)
        result = ft_acquire.copy_bounded(
            iter([b"abc"]), sink, expected_length=3, max_bytes=3, deadline_s=60, clock=self.clock
        )
        self.assertEqual(result["bytes_written"], 3)
        self.assertEqual(bytes(sink.data), b"abc")

    def test_sink_failure_redacted(self):
        sink = FakeSink(fail=True)
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"abc"]), sink, expected_length=3, max_bytes=3, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "SINK_FAILED")
        self.assertNotIn("synthetic backend failure detail", str(ctx.exception))

    def test_deadline_exceeded_on_last_chunk_stall(self):
        class SlowSource:
            def __init__(self, outer):
                self.outer = outer
                self.sent_first = False

            def __iter__(self):
                return self

            def __next__(self):
                if not self.sent_first:
                    self.sent_first = True
                    return b"ab"
                self.outer.clock_value[0] += 100
                return b"cd"

        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                SlowSource(self), sink, expected_length=4, max_bytes=4, deadline_s=1, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "DEADLINE_EXCEEDED")

    def test_clock_jump_during_pull_detected_before_write(self):
        state = {"n": 0}

        def chunks():
            while True:
                state["n"] += 1
                self.clock_value[0] += 100
                yield b"ab"

        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                chunks(), sink, expected_length=4, max_bytes=4, deadline_s=1, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "DEADLINE_EXCEEDED")
        self.assertEqual(bytes(sink.data), b"")

    def test_invalid_chunk_type_rejected(self):
        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter(["not-bytes"]), sink, expected_length=5, max_bytes=5, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "INVALID_CHUNK")

    def test_source_exception_redacted(self):
        def chunks():
            raise RuntimeError("secret backend trace")
            yield b""  # pragma: no cover

        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                chunks(), sink, expected_length=5, max_bytes=5, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "SOURCE_FAILED")
        self.assertNotIn("secret backend trace", str(ctx.exception))

    def test_eof_then_clock_jump_past_deadline_rejected(self):
        class EofJumpSource:
            def __init__(self, outer):
                self.outer = outer
                self.sent = False

            def __iter__(self):
                return self

            def __next__(self):
                if not self.sent:
                    self.sent = True
                    return b"abcd"
                self.outer.clock_value[0] += 100
                raise StopIteration

        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                EofJumpSource(self), sink, expected_length=4, max_bytes=4, deadline_s=1, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "DEADLINE_EXCEEDED")

    def test_timeout_during_first_short_write_stops_before_second_write(self):
        class JumpAfterFirstWriteSink:
            def __init__(self, outer):
                self.outer = outer
                self.writes = []

            def write(self, chunk):
                self.writes.append(bytes(chunk))
                self.outer.clock_value[0] += 100
                return 1

        sink = JumpAfterFirstWriteSink(self)
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"abc"]), sink, expected_length=3, max_bytes=3, deadline_s=1, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "DEADLINE_EXCEEDED")
        self.assertEqual(len(sink.writes), 1)

    def test_iter_exception_redacted(self):
        class BoomIterable:
            def __iter__(self):
                raise RuntimeError("secret backend trace")

        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                BoomIterable(), sink, expected_length=4, max_bytes=4, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "SOURCE_FAILED")
        self.assertNotIn("secret backend trace", str(ctx.exception))

    def test_clock_exception_redacted(self):
        def boom_clock():
            raise RuntimeError("secret backend trace")

        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab"]), sink, expected_length=2, max_bytes=2, deadline_s=60, clock=boom_clock
            )
        self.assertEqual(ctx.exception.code, "CLOCK_FAILED")
        self.assertNotIn("secret backend trace", str(ctx.exception))

    def test_clock_nan_rejected(self):
        def clock():
            return float("nan")

        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab"]), sink, expected_length=2, max_bytes=2, deadline_s=60, clock=clock
            )
        self.assertEqual(ctx.exception.code, "INVALID_CLOCK")

    def test_clock_inf_rejected(self):
        def clock():
            return float("inf")

        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab"]), sink, expected_length=2, max_bytes=2, deadline_s=60, clock=clock
            )
        self.assertEqual(ctx.exception.code, "INVALID_CLOCK")

    def test_clock_bool_rejected(self):
        def clock():
            return True

        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab"]), sink, expected_length=2, max_bytes=2, deadline_s=60, clock=clock
            )
        self.assertEqual(ctx.exception.code, "INVALID_CLOCK")

    def test_clock_regression_rejected(self):
        values = [0.0, 5.0, 1.0]

        def clock():
            return values.pop(0)

        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab", b"cd"]), sink, expected_length=4, max_bytes=4, deadline_s=60, clock=clock
            )
        self.assertEqual(ctx.exception.code, "CLOCK_REGRESSION")

    def test_rejects_empty_chunk(self):
        sink = FakeSink()
        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"", b"ab"]), sink, expected_length=2, max_bytes=2, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "EMPTY_CHUNK")

    def test_rejects_sink_returning_none(self):
        class NoneSink:
            def write(self, chunk):
                return None

        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab"]), NoneSink(), expected_length=2, max_bytes=2, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "SINK_FAILED")

    def test_rejects_sink_returning_bool(self):
        class BoolSink:
            def write(self, chunk):
                return True

        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab"]), BoolSink(), expected_length=2, max_bytes=2, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "SINK_FAILED")

    def test_rejects_sink_returning_zero(self):
        class ZeroSink:
            def write(self, chunk):
                return 0

        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab"]), ZeroSink(), expected_length=2, max_bytes=2, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "SINK_FAILED")

    def test_rejects_sink_returning_negative(self):
        class NegativeSink:
            def write(self, chunk):
                return -1

        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab"]), NegativeSink(), expected_length=2, max_bytes=2, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "SINK_FAILED")

    def test_rejects_sink_returning_overlong(self):
        class OverlongSink:
            def write(self, chunk):
                return len(chunk) + 1

        with self.assertRaises(ft_acquire.CopyError) as ctx:
            ft_acquire.copy_bounded(
                iter([b"ab"]), OverlongSink(), expected_length=2, max_bytes=2, deadline_s=60, clock=self.clock
            )
        self.assertEqual(ctx.exception.code, "SINK_FAILED")

    def test_no_real_file_io(self):
        import builtins
        original_open = builtins.open

        def tripwire_open(*args, **kwargs):
            raise AssertionError("copy_bounded must not open real files")

        builtins.open = tripwire_open
        try:
            sink = FakeSink()
            ft_acquire.copy_bounded(
                iter([b"ab"]), sink, expected_length=2, max_bytes=2, deadline_s=60, clock=self.clock
            )
        finally:
            builtins.open = original_open


def staged(sha=None, size=1000):
    return {"status": "STAGED", "bytes_written": size, "sha256": sha or "a" * 64}


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.start = WINDOW_START
        self.end = WINDOW_START + timedelta(minutes=3)
        self.sha = "a" * 64

    def _add(self, manifest, ref="clip-1", sha=None, size=1000, start=None, end=None,
              lens="FIXED", container="mp4", duration_s=180.0, duration_tolerance_s=0.0,
              fixed_mapping_verified=True, container_validated=True, duration_validated=True):
        return manifest.add_clip(
            ref=ref,
            start=start if start is not None else self.start,
            end=end if end is not None else self.end,
            lens=lens,
            container=container,
            duration_s=duration_s,
            duration_tolerance_s=duration_tolerance_s,
            staged_result=staged(sha=sha, size=size),
            fixed_mapping_verified=fixed_mapping_verified,
            container_validated=container_validated,
            duration_validated=duration_validated,
        )

    def test_accepts_fixed_lens_entry(self):
        manifest = ft_acquire.Manifest()
        status = self._add(manifest)
        self.assertEqual(status, "ADDED")
        entries = manifest.entries()
        self.assertIn("clip-1", entries)
        entry = entries["clip-1"]
        self.assertEqual(entry["status"], "STAGED")
        self.assertEqual(entry["size"], 1000)
        self.assertEqual(entry["duration"], 180.0)
        self.assertEqual(entry["start"], self.start.isoformat())

    def test_malformed_container_type_is_redacted(self):
        for container in (["mp4"], {"synthetic-private": "mp4"}, None, True):
            with self.subTest(container_type=type(container).__name__):
                with self.assertRaises(ft_acquire.ManifestError) as ctx:
                    self._add(ft_acquire.Manifest(), container=container)
                self.assertEqual(ctx.exception.code, "INVALID_CONTAINER")
                self.assertNotIn("synthetic-private", str(ctx.exception))

    def test_rejects_pt_lens(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, lens="PT")
        self.assertEqual(ctx.exception.code, "LENS_NOT_FIXED")

    def test_rejects_unknown_lens(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, lens="UNKNOWN")
        self.assertEqual(ctx.exception.code, "LENS_NOT_FIXED")

    def test_rejects_naive_timezone(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, start=datetime(2026, 10, 8))
        self.assertEqual(ctx.exception.code, "INVALID_TIME")

    def test_rejects_pseudo_tzinfo_raising_on_utcoffset(self):
        import datetime as dt_module

        class BoomTzinfo(dt_module.tzinfo):
            def utcoffset(self, _dt):
                raise RuntimeError("secret backend trace")

            def dst(self, _dt):
                return None

            def tzname(self, _dt):
                return "BOOM"

        manifest = ft_acquire.Manifest()
        bad_start = dt_module.datetime(2026, 10, 8, 0, 0, tzinfo=BoomTzinfo())
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, start=bad_start)
        self.assertEqual(ctx.exception.code, "INVALID_TIME")
        self.assertNotIn("secret backend trace", str(ctx.exception))

    def test_rejects_malformed_sha(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, sha="not-a-sha")
        self.assertEqual(ctx.exception.code, "INVALID_STAGED_RESULT")

    def test_rejects_sha_with_trailing_newline(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, sha="a" * 64 + "\n")
        self.assertEqual(ctx.exception.code, "INVALID_STAGED_RESULT")

    def test_rejects_invalid_size(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, size=0)
        self.assertEqual(ctx.exception.code, "INVALID_STAGED_RESULT")

    def test_rejects_missing_staged_result_key(self):
        manifest = ft_acquire.Manifest()
        bad = staged()
        del bad["status"]
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            manifest.add_clip(
                ref="clip-1", start=self.start, end=self.end, lens="FIXED", container="mp4",
                duration_s=180.0, duration_tolerance_s=0.0, staged_result=bad,
                fixed_mapping_verified=True, container_validated=True, duration_validated=True,
            )
        self.assertEqual(ctx.exception.code, "INVALID_STAGED_RESULT")

    def test_rejects_staged_result_not_staged(self):
        manifest = ft_acquire.Manifest()
        bad = staged()
        bad["status"] = "FAIL"
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            manifest.add_clip(
                ref="clip-1", start=self.start, end=self.end, lens="FIXED", container="mp4",
                duration_s=180.0, duration_tolerance_s=0.0, staged_result=bad,
                fixed_mapping_verified=True, container_validated=True, duration_validated=True,
            )
        self.assertEqual(ctx.exception.code, "INVALID_STAGED_RESULT")

    def test_rejects_staged_result_extra_key(self):
        manifest = ft_acquire.Manifest()
        bad = staged()
        bad["extra"] = "x"
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            manifest.add_clip(
                ref="clip-1", start=self.start, end=self.end, lens="FIXED", container="mp4",
                duration_s=180.0, duration_tolerance_s=0.0, staged_result=bad,
                fixed_mapping_verified=True, container_validated=True, duration_validated=True,
            )
        self.assertEqual(ctx.exception.code, "INVALID_STAGED_RESULT")

    def test_rejects_invalid_duration(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, duration_s=float("nan"))
        self.assertEqual(ctx.exception.code, "INVALID_DURATION")

    def test_rejects_invalid_container(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, container="/etc/passwd")
        self.assertEqual(ctx.exception.code, "INVALID_CONTAINER")

    def test_rejects_duration_mismatch_beyond_tolerance(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, duration_s=500.0, duration_tolerance_s=0.0)
        self.assertEqual(ctx.exception.code, "DURATION_MISMATCH")

    def test_accepts_duration_within_tolerance(self):
        manifest = ft_acquire.Manifest()
        status = self._add(manifest, duration_s=181.0, duration_tolerance_s=2.0)
        self.assertEqual(status, "ADDED")

    def test_rejects_unverified_fixed_mapping(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, fixed_mapping_verified=False)
        self.assertEqual(ctx.exception.code, "FIXED_LENS_UNVERIFIED")

    def test_rejects_truthy_non_true_fixed_mapping(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, fixed_mapping_verified=1)
        self.assertEqual(ctx.exception.code, "FIXED_LENS_UNVERIFIED")

    def test_rejects_unvalidated_container(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, container_validated=False)
        self.assertEqual(ctx.exception.code, "CONTAINER_UNVALIDATED")

    def test_rejects_unvalidated_duration(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, duration_validated=False)
        self.assertEqual(ctx.exception.code, "DURATION_UNVALIDATED")

    def test_rejects_path_like_ref(self):
        manifest = ft_acquire.Manifest()
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, ref="/etc/passwd")
        self.assertEqual(ctx.exception.code, "INVALID_REF")

    def test_idempotent_duplicate_same_bytes_and_metadata(self):
        manifest = ft_acquire.Manifest()
        self._add(manifest)
        status = self._add(manifest)
        self.assertEqual(status, "DUPLICATE")
        self.assertEqual(len(manifest.entries()), 1)

    def test_conflicting_ref_rejected_on_different_bytes(self):
        manifest = ft_acquire.Manifest()
        self._add(manifest)
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, sha="b" * 64)
        self.assertEqual(ctx.exception.code, "REF_CONFLICT")

    def test_conflicting_ref_rejected_on_same_bytes_different_timing(self):
        manifest = ft_acquire.Manifest()
        self._add(manifest)
        other_start = self.start + timedelta(minutes=1)
        other_end = self.end + timedelta(minutes=1)
        with self.assertRaises(ft_acquire.ManifestError) as ctx:
            self._add(manifest, start=other_start, end=other_end, duration_s=180.0)
        self.assertEqual(ctx.exception.code, "REF_CONFLICT")

    def test_same_bytes_different_refs_recorded_as_duplicate_group(self):
        manifest = ft_acquire.Manifest()
        self._add(manifest, ref="clip-1")
        self._add(manifest, ref="clip-2")
        groups = manifest.duplicate_byte_groups()
        self.assertEqual(list(groups.values()), [["clip-1", "clip-2"]])

    def test_entries_snapshot_is_defensive_copy(self):
        manifest = ft_acquire.Manifest()
        self._add(manifest)
        entries = manifest.entries()
        entries["clip-1"]["sha256"] = "tampered"
        entries["clip-1"]["status"] = "TAMPERED"
        fresh = manifest.entries()
        self.assertEqual(fresh["clip-1"]["sha256"], self.sha)
        self.assertEqual(fresh["clip-1"]["status"], "STAGED")

    def test_no_filesystem_access(self):
        manifest = ft_acquire.Manifest()
        import builtins
        original_open = builtins.open

        def tripwire_open(*args, **kwargs):
            raise AssertionError("Manifest must not touch the filesystem")

        builtins.open = tripwire_open
        try:
            self._add(manifest)
        finally:
            builtins.open = original_open


class CheckCommandTests(unittest.TestCase):
    def test_check_reports_blocked_and_not_implemented(self):
        report = ft_acquire.check_command()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["route"], "NOT_TESTED")
        self.assertEqual(report["auth"], "NOT_TESTED")
        self.assertEqual(report["download"], "NOT_TESTED")
        self.assertEqual(report["camera_requests"], 0)
        self.assertEqual(report["backend_binding"], "NOT_IMPLEMENTED")

    def test_check_never_imports_pytapo_or_touches_socket(self):
        original = socket.socket
        socket.socket = TripwireSocket()
        try:
            code, out, _ = run_cli(["check"])
        finally:
            socket.socket = original
        self.assertEqual(code, 2)
        self.assertNotIn("pytapo", sys.modules)
        self.assertIn("BLOCKED", out)

    def test_default_invocation_no_args_is_usage_error(self):
        code, out, _ = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("REJECTED", out)

    def test_unknown_command_redacted(self):
        code, out, _ = run_cli(["download", "--target", "secret-ip-192.0.2.5"])
        self.assertEqual(code, 2)
        self.assertNotIn("secret-ip", out)
        self.assertNotIn("download", out)

    def test_unrecognized_argument_redacted(self):
        code, out, _ = run_cli(["check", "--leak=topsecretvalue"])
        self.assertEqual(code, 2)
        self.assertNotIn("topsecretvalue", out)

    def test_nul_argument_rejected(self):
        code, out, _ = run_cli(["check\x00"])
        self.assertEqual(code, 2)
        self.assertIn("REJECTED", out)


if __name__ == "__main__":
    unittest.main()
