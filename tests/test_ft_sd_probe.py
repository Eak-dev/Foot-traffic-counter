"""Tests for tools/ft_sd_probe.py.

Every network, dialog, and clock dependency here is a synthetic fake or a
monkeypatched stdlib call; nothing in this file opens a real socket, spawns
a real osascript dialog, or contacts tplinkcloud.com. Run from the
repository root:
python3 -m unittest discover -s tests -t . -v
"""
import http.client
import json
import socket
import ssl
import subprocess
import time
import unittest
from unittest import mock

from tools import ft_cloud_probe as cloud
from tools import ft_sd_probe as sd


class TripwireHTTPSConnection:
    def __init__(self, *args, **kwargs):
        raise AssertionError("no real network access is permitted in ft_sd_probe tests")


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
        chunk = self._body[self._offset:self._offset + n] if n is not None and n >= 0 else self._body[self._offset:]
        self._offset += len(chunk)
        return chunk


def make_fake_connection_class(script, connections=None):
    class FakeConnection:
        def __init__(self, host, port, context=None, timeout=None):
            self.host = host
            self.port = port
            self.closed = False
            self.sent = []
            if connections is not None:
                connections.append(self)

        def connect(self):
            pass

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
    state = {"answers": list(answers)}

    def fake_run(args, capture_output, text, timeout):
        returncode, stdout = state["answers"].pop(0)
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")

    return mock.patch.object(subprocess, "run", side_effect=fake_run)


LOGIN_OK_BODY = json.dumps({"errorCode": 0, "result": {"token": "tok-1"}}).encode()
DATE = "20261012"


def camera(nickname, model="C545D(UN)", thing_name="selected-device-id"):
    return {
        "deviceType": "SMART.IPCAMERA",
        "model": model,
        "thingName": thing_name,
        "nickname": nickname,
    }


def discovery_body(cameras):
    return json.dumps({"data": cameras}).encode()


def _digest(name):
    import hashlib

    return hashlib.sha256(name.strip().casefold().encode("utf-8")).hexdigest()


NAME = "Example Shop Camera"
DIGEST = _digest(NAME)


def envelope(responses, outer_code=0):
    return json.dumps(
        {
            "error_code": outer_code,
            "outputParams": {
                "responseData": {
                    "error_code": 0,
                    "result": {"responses": responses},
                }
            },
        }
    ).encode()


def resp(method, result=None, code=0):
    entry = {"method": method, "error_code": code}
    if result is not None:
        entry["result"] = result
    return entry


METADATA_OK = envelope(
    [
        resp("getDeviceInfo", {"device_info": {"basic_info": {"device_model": "C545D(UN)"}}}),
        resp("getTimezone", {"system": {"basic": {"timezone": "UTC+07:00"}}}),
        resp(
            "getSdCardStatus",
            {"harddisk_manage": {"hd_info": [{"slot1": {"detect_status": "normal"}}]}},
        ),
    ]
)

CAPABILITY_OK = envelope(
    [
        resp(
            "getAppComponentList",
            {"app_component": {"app_component_list": [{"name": "sdCard"}, {"name": "ptz"}]}},
        ),
        resp("getStreamCapability", {"local_stream_type": {"main": 1}}),
        resp("getVideoCapability", {"main": {}, "minor": {}}),
    ]
)

CALENDAR_OK = envelope(
    [
        resp("getUserID", {"user_id": "12345"}),
        resp(
            "searchDateWithVideo",
            {"playback": {"search_results": [{"0": {"date": DATE}}]}},
        ),
    ]
)


def clip_entries(n, day_start):
    return [
        {str(i): {"startTime": day_start + i * 60, "endTime": day_start + i * 60 + 30, "vedio_type": 1}}
        for i in range(n)
    ]


def _day_start_utc(date="20261012", offset_hours=7):
    import datetime

    midnight = datetime.datetime.strptime(date, "%Y%m%d").replace(tzinfo=datetime.timezone.utc)
    return int(midnight.timestamp()) - offset_hours * 3600


CLIP_OK = envelope([resp("searchVideoOfDay", {"playback": {"search_video_results": clip_entries(15, _day_start_utc())}})])


def run_login_with_device(device_script, devices=None, digest=DIGEST, date=DATE):
    devices = devices if devices is not None else [camera(NAME)]
    login_script = [(200, LOGIN_OK_BODY), (200, discovery_body(devices))]
    connections = []
    with mock.patch.object(cloud.sys, "platform", "darwin"), \
            mock.patch.object(cloud.os.path, "exists", return_value=True), \
            patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]), \
            patch_connection(login_script + device_script, connections):
        report = sd.run(digest, date=date)
    return report, connections


class ValidationTests(unittest.TestCase):
    def test_device_id_rejects_path_traversal_and_special_characters(self):
        for bad in ("a/b", "a%2e", "a.b", "../etc", "has space", "a?x=1", "a" * 129, "", None, 123):
            with self.subTest(bad=bad):
                with self.assertRaises(sd.SdError) as ctx:
                    sd._validate_device_id(bad)
                self.assertEqual(ctx.exception.code, "INVALID_INPUT")

    def test_device_id_accepts_ascii_alnum_dash_underscore(self):
        self.assertEqual(sd._validate_device_id("abc-DEF_123"), "abc-DEF_123")

    def test_date_rejects_malformed_or_impossible_calendar_dates(self):
        for bad in ("2026-10-12", "202610121", "2026121", "20261332", "", None, 20261012):
            with self.subTest(bad=bad):
                with self.assertRaises(sd.SdError) as ctx:
                    sd._validate_date(bad)
                self.assertEqual(ctx.exception.code, "INVALID_INPUT")

    def test_date_accepts_exact_valid_calendar_date(self):
        self.assertEqual(sd._validate_date("20261012"), "20261012")


class RunGatingTests(unittest.TestCase):
    def test_none_digest_rejected_before_dialog_or_network(self):
        with mock.patch.object(subprocess, "run", TripwireSubprocessRun()), \
                mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            report = sd.run(None)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "INVALID_INPUT")

    def test_invalid_digest_rejected_before_dialog_or_network(self):
        with mock.patch.object(subprocess, "run", TripwireSubprocessRun()), \
                mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            report = sd.run("not-a-digest")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "INVALID_INPUT")

    def test_invalid_date_rejected_before_digest_dialog_or_network(self):
        with mock.patch.object(subprocess, "run", TripwireSubprocessRun()), \
                mock.patch.object(http.client, "HTTPSConnection", TripwireHTTPSConnection):
            report = sd.run(DIGEST, date="bad-date")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "INVALID_INPUT")

    def test_callback_not_invoked_for_zero_matches(self):
        report, connections = run_login_with_device([], devices=[camera("Totally Different Name")])
        self.assertEqual(report["inventory_status"], "TARGET_NOT_FOUND")
        self.assertEqual(len(connections), 2)  # login + discovery only, no device calls
        self.assertNotIn("device_model_kind", report)

    def test_callback_not_invoked_for_duplicate_matches(self):
        devices = [camera(NAME, thing_name="d1"), camera(NAME, thing_name="d2")]
        report, connections = run_login_with_device([], devices=devices)
        self.assertEqual(report["inventory_status"], "TARGET_AMBIGUOUS")
        self.assertEqual(len(connections), 2)
        self.assertNotIn("device_model_kind", report)


class EndToEndTests(unittest.TestCase):
    def test_full_metadata_calendar_and_first_page_clip_listing(self):
        device_script = [
            (200, METADATA_OK),
            (200, CAPABILITY_OK),
            (200, CALENDAR_OK),
            (200, CLIP_OK),
        ]
        report, connections = run_login_with_device(device_script)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertEqual(report["device_model_kind"], "VARIANT")
        self.assertEqual(report["timezone_offset"], "+07:00")
        self.assertEqual(report["sd_status"], "NORMAL")
        self.assertTrue(report["calendar_has_requested_date"])
        self.assertEqual(report["clip_count"], 15)
        self.assertEqual(report["list_scope"], "FIRST_PAGE_ONLY")
        self.assertIn("UNKNOWN", report["fixed_mapping"])
        self.assertEqual(len(connections), 2 + 4)  # login+discovery, then exactly 4 device batches

    def test_exact_request_shapes_are_sent_for_each_batch(self):
        device_script = [
            (200, METADATA_OK),
            (200, CAPABILITY_OK),
            (200, CALENDAR_OK),
            (200, CLIP_OK),
        ]
        report, connections = run_login_with_device(device_script)
        self.assertEqual(report["status"], "SUCCESS")
        device_conns = connections[2:]
        bodies = [json.loads(c.sent[0][2]) for c in device_conns]
        self.assertEqual(
            bodies[0]["inputParams"]["requestData"]["params"]["requests"],
            sd._metadata_requests(),
        )
        self.assertEqual(
            bodies[1]["inputParams"]["requestData"]["params"]["requests"],
            sd._capability_requests(),
        )
        self.assertEqual(
            bodies[2]["inputParams"]["requestData"]["params"]["requests"],
            sd._calendar_requests(DATE),
        )
        self.assertEqual(
            bodies[3]["inputParams"]["requestData"]["params"]["requests"],
            sd._clip_requests(DATE, 12345),
        )
        for conn in device_conns:
            self.assertEqual(conn.sent[0][0], "POST")
            self.assertEqual(conn.sent[0][1], "/v1/things/selected-device-id/services-sync")

    def test_capability_batch_failure_leaves_unknown_but_listing_continues(self):
        device_script = [
            (200, METADATA_OK),
            socket.timeout(),
            (200, CALENDAR_OK),
            (200, CLIP_OK),
        ]
        report, connections = run_login_with_device(device_script)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertIsNone(report["capabilities"]["has_sd_card_component"])
        self.assertIsNone(report["capabilities"]["component_count"])
        self.assertEqual(report["clip_count"], 15)
        self.assertTrue(connections[3].closed)

    def test_capability_partial_rejection_reports_unknown_for_that_key(self):
        capability_partial = envelope(
            [
                resp("getAppComponentList", code=-1),
                resp("getStreamCapability", {"ok": 1}),
                resp("getVideoCapability", {"ok": 1}),
            ]
        )
        device_script = [
            (200, METADATA_OK),
            (200, capability_partial),
            (200, CALENDAR_OK),
            (200, CLIP_OK),
        ]
        report, _ = run_login_with_device(device_script)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertIsNone(report["capabilities"]["component_count"])
        self.assertIsNone(report["capabilities"]["stream_capability_present"])

    def test_identity_mismatch_stops_before_calendar(self):
        mismatched_metadata = envelope(
            [
                resp("getDeviceInfo", {"device_info": {"basic_info": {"device_model": "C210"}}}),
                resp("getTimezone", {"system": {"basic": {"timezone": "UTC+07:00"}}}),
                resp("getSdCardStatus", {"harddisk_manage": {"hd_info": []}}),
            ]
        )
        device_script = [(200, mismatched_metadata)]
        report, connections = run_login_with_device(device_script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "IDENTITY_MISMATCH")
        self.assertEqual(len(connections), 2 + 1)
        self.assertNotIn("clip_count", report)

    def test_calendar_missing_requested_date_skips_clip_batch(self):
        calendar_without_date = envelope(
            [
                resp("getUserID", {"user_id": "12345"}),
                resp("searchDateWithVideo", {"playback": {"search_results": []}}),
            ]
        )
        device_script = [(200, METADATA_OK), (200, CAPABILITY_OK), (200, calendar_without_date)]
        report, connections = run_login_with_device(device_script)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertFalse(report["calendar_has_requested_date"])
        self.assertEqual(report["clip_count"], 0)
        self.assertEqual(report["list_scope"], "NO_CLIPS")
        self.assertEqual(len(connections), 2 + 3)  # no fourth device request sent

    def test_missing_user_id_skips_clip_batch(self):
        calendar_without_uid = envelope(
            [
                resp("getUserID", {"system": {"get_user_id": {}}}),
                resp("searchDateWithVideo", {"playback": {"search_results": [{"0": {"date": DATE}}]}}),
            ]
        )
        device_script = [(200, METADATA_OK), (200, CAPABILITY_OK), (200, calendar_without_uid)]
        report, connections = run_login_with_device(device_script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertNotIn("clip_count", report)
        self.assertEqual(len(connections), 2 + 3)

    def test_21_entries_rejected(self):
        oversized_clip = envelope(
            [resp("searchVideoOfDay", {"playback": {"search_video_results": clip_entries(21, _day_start_utc())}})]
        )
        device_script = [(200, METADATA_OK), (200, CAPABILITY_OK), (200, CALENDAR_OK), (200, oversized_clip)]
        report, _ = run_login_with_device(device_script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")
        self.assertNotIn("clip_count", report)

    def test_out_of_day_clip_timestamp_rejected(self):
        bad_start = _day_start_utc() - 3600
        out_of_range = envelope(
            [resp("searchVideoOfDay", {
                "playback": {"search_video_results": [
                    {"0": {"startTime": bad_start, "endTime": bad_start + 30, "vedio_type": 1}}
                ]}
            })]
        )
        device_script = [(200, METADATA_OK), (200, CAPABILITY_OK), (200, CALENDAR_OK), (200, out_of_range)]
        report, _ = run_login_with_device(device_script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")

    def test_duplicate_method_in_responses_rejected(self):
        duplicated = envelope(
            [resp("getDeviceInfo", {}), resp("getDeviceInfo", {}), resp("getTimezone", {}), resp("getSdCardStatus", {})]
        )
        device_script = [(200, duplicated)]
        report, _ = run_login_with_device(device_script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")

    def test_unknown_method_in_responses_rejected(self):
        unknown = envelope(
            [resp("getDeviceInfo", {}), resp("getTimezone", {}), resp("setDeviceAlias", {})]
        )
        device_script = [(200, unknown)]
        report, _ = run_login_with_device(device_script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")

    def test_missing_method_count_mismatch_rejected(self):
        missing = envelope([resp("getDeviceInfo", {}), resp("getTimezone", {})])
        device_script = [(200, missing)]
        report, _ = run_login_with_device(device_script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")

    def test_outer_error_code_fails_whole_batch(self):
        failing = envelope([], outer_code=-1)
        device_script = [(200, failing)]
        report, _ = run_login_with_device(device_script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "REQUEST_FAILED")

    def test_responsedata_as_json_string_is_parsed_through_dup_rejecting_parser(self):
        inner = {"error_code": 0, "result": {"responses": [
            resp("getDeviceInfo", {"device_info": {"basic_info": {"device_model": "C545D(UN)"}}}),
            resp("getTimezone", {"system": {"basic": {"timezone": "UTC+07:00"}}}),
            resp("getSdCardStatus", {"harddisk_manage": {"hd_info": []}}),
        ]}}
        stringified = json.dumps(
            {"error_code": 0, "outputParams": {"responseData": json.dumps(inner)}}
        ).encode()
        device_script = [(200, stringified), (200, CAPABILITY_OK), (200, CALENDAR_OK), (200, CLIP_OK)]
        report, _ = run_login_with_device(device_script)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertEqual(report["sd_status"], "NO_CARD")

    def test_duplicate_keys_inside_responsedata_string_rejected(self):
        raw_inner = b'{"error_code": 0, "result": {"responses": []}, "error_code": -1}'
        stringified = json.dumps(
            {"error_code": 0, "outputParams": {"responseData": raw_inner.decode()}}
        ).encode()
        device_script = [(200, stringified)]
        report, _ = run_login_with_device(device_script)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MALFORMED_RESPONSE")

    def test_scope_id_injection_attempt_is_rejected_before_any_device_connection(self):
        devices = [camera(NAME, thing_name="../etc/passwd")]
        login_script = [(200, LOGIN_OK_BODY), (200, discovery_body(devices))]
        with mock.patch.object(cloud.sys, "platform", "darwin"), \
                mock.patch.object(cloud.os.path, "exists", return_value=True), \
                patch_dialog([(0, "owner@example.com\n"), (0, "hunter2\n")]):
            connections = []
            with patch_connection(login_script, connections):
                report = sd.run(DIGEST, date=DATE)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "INVALID_INPUT")
        self.assertEqual(len(connections), 2)

    def test_timeout_and_oversized_response_close_the_connection(self):
        for script in ([socket.timeout()], [(200, b"a" * (cloud.MAX_RESPONSE_BYTES + 1))]):
            with self.subTest(script=script):
                connections = []
                report, conns = run_login_with_device(list(script))
                self.assertEqual(report["status"], "BLOCKED")
        device_script = [socket.timeout()]
        report, connections = run_login_with_device(device_script)
        self.assertTrue(connections[-1].closed)

    def test_report_never_leaks_raw_device_id_or_model_string(self):
        device_script = [(200, METADATA_OK), (200, CAPABILITY_OK), (200, CALENDAR_OK), (200, CLIP_OK)]
        report, _ = run_login_with_device(device_script)
        dumped = json.dumps(report)
        self.assertNotIn("selected-device-id", dumped)
        self.assertNotIn("C545D(UN)", dumped)
        self.assertNotIn("12345", dumped)

    def test_fixed_mapping_is_always_unknown_never_a_claimed_fixed_channel(self):
        device_script = [(200, METADATA_OK), (200, CAPABILITY_OK), (200, CALENDAR_OK), (200, CLIP_OK)]
        report, _ = run_login_with_device(device_script)
        self.assertIn("UNKNOWN", report["fixed_mapping"])
        self.assertNotEqual(report["list_scope"], "COMPLETE")

    def test_device_requests_never_exceed_four(self):
        device_script = [(200, METADATA_OK), (200, CAPABILITY_OK), (200, CALENDAR_OK), (200, CLIP_OK)]
        report, connections = run_login_with_device(device_script)
        self.assertLessEqual(len(connections) - 2, sd.MAX_DEVICE_REQUESTS)
        self.assertEqual(report["requests_used"], 4)


class BudgetTests(unittest.TestCase):
    def test_device_budget_caps_requests(self):
        budget = sd._DeviceBudget()
        for _ in range(sd.MAX_DEVICE_REQUESTS):
            budget.use_request()
        with self.assertRaises(sd.SdError) as ctx:
            budget.use_request()
        self.assertEqual(ctx.exception.code, "REQUEST_LIMIT_EXCEEDED")

    def test_device_budget_time_cap(self):
        budget = sd._DeviceBudget()
        with mock.patch.object(time, "monotonic", return_value=budget.start + sd.DEVICE_BUDGET_S + 1):
            with self.assertRaises(sd.SdError) as ctx:
                budget.check_time()
        self.assertEqual(ctx.exception.code, "TIME_BUDGET_EXCEEDED")


if __name__ == "__main__":
    unittest.main()

class PORegressionTests(unittest.TestCase):
    def test_getter_guard_rejects_mutations_before_network(self):
        import copy
        cases = []
        base = sd._clip_requests(DATE, 42)
        for field, value in (("channel",1), ("channel",False), ("end_index",20), ("end_index",19.0), ("start_index",1), ("date","20261011"), ("id",True)):
            changed = copy.deepcopy(base)
            changed[0]["params"]["playback"]["search_video_utility"][field] = value
            cases.append(changed)
        cases += [[{"method":"setPrivacyMode","params":{}}], base + base]
        changed = copy.deepcopy(base)
        changed[0]["params"]["setPrivacyMode"] = {}
        cases.append(changed)
        with mock.patch.object(sd, "_open_device_connection") as opener:
            for req in cases:
                with self.subTest(request=req), self.assertRaises(sd.SdError):
                    sd._device_request(sd._DeviceBudget(), "t", "u", "cam1", req, "clip", DATE, 42)
            opener.assert_not_called()

    def test_direct_probe_date_and_origin_guards(self):
        selected = {"thing_name":"cam1", "model_kind":"VARIANT"}
        with mock.patch.object(sd, "_device_request") as sender:
            for date, server in (("20261011",None), (DATE,"https://evil.example")):
                result=sd.probe_selected_device("t","u",dict(selected,app_server=server),date)
                self.assertEqual(result["status"],"BLOCKED")
            sender.assert_not_called()

    def test_canonical_uid_bounds(self):
        for value in (1,"42",2**63-1,str(2**63-1)):
            self.assertEqual(sd._read_user_id({"user_id":value}),int(value))
        for value in (True,0,-1,1.0,"01","+1"," 1",str(2**63),2**63):
            self.assertIsNone(sd._read_user_id({"user_id":value}))

    def test_real_index_schema_duplicate_and_outside_date(self):
        self.assertTrue(sd._read_calendar({"playback":{"search_results":[{"0":{"date":DATE}}]}},DATE))
        for rows in ([{"index":{"date":DATE}}], [{"0":{"date":DATE}},{"0":{"date":DATE}}], [{"0":{"date":"20261011"}}], [{"0":{"date":DATE},"1":{"date":DATE}}]):
            with self.assertRaises(sd.SdError):
                sd._read_calendar({"playback":{"search_results":rows}},DATE)
        entry=clip_entries(1,_day_start_utc())[0]
        with self.assertRaises(sd.SdError):
            sd._read_clips({"playback":{"search_video_results":[entry,entry]}},"+07:00",DATE)

    def test_exact_metadata_matches_variant_inventory(self):
        meta=METADATA_OK.replace(b'C545D(UN)',b'C545D')
        report, _=run_login_with_device([(200,meta),(200,CAPABILITY_OK),(200,CALENDAR_OK),(200,CLIP_OK)])
        self.assertEqual(report["status"],"SUCCESS")
        self.assertEqual(report["device_model_kind"],"EXACT")

    def test_unknown_timezone_stops_before_clip_request(self):
        meta=METADATA_OK.replace(b'UTC+07:00',b'unknown')
        report, conns=run_login_with_device([(200,meta),(200,CAPABILITY_OK),(200,CALENDAR_OK)])
        self.assertEqual(report["status"],"BLOCKED")
        self.assertEqual(report["stage"],"CLIPS")
        self.assertEqual(report["requests_used"],3)
        self.assertEqual(len(conns),5)

    def test_schema_unknowns_stay_unknown(self):
        self.assertEqual(sd._read_sd_status({"harddisk_manage":{"hd_info":[{"hd_info_1":{"detect_status":[]}}]}}),"UNKNOWN")
        caps=sd._read_capabilities({"app_component":{"app_component_list":[{}]}},{"unexpected":1},{"unexpected":1})
        self.assertTrue(all(v is None for v in caps.values()))
        self.assertIsNone(sd._read_timezone_offset({"system":{"basic":{"timezone":"UTC+14:45"}}}))

    def test_no_card_calendar_empty_is_not_full_day_completeness(self):
        calendar=envelope([resp("getUserID",{"user_id":42}),resp("searchDateWithVideo",{"playback":{"search_results":[]}})])
        report,_=run_login_with_device([(200,METADATA_OK),(200,CAPABILITY_OK),(200,calendar)])
        self.assertEqual(report["clip_count"],0)
        self.assertEqual(report["list_scope"],"NO_CLIPS")
        self.assertEqual(report["fixed_mapping"],"UNKNOWN")

    def test_transport_redirect_close_and_budget_expiry(self):
        for status in (301,302,303,307,308,401,500):
            report, conns=run_login_with_device([(status,b'')])
            self.assertEqual(report["reason"],"HTTP_ERROR")
            self.assertEqual(report["stage"],"METADATA")
            self.assertTrue(conns[-1].closed)
        budget=sd._DeviceBudget()
        fake=mock.Mock()
        fake.getresponse.return_value=FakeResponse(200,b'{}')
        with mock.patch.object(sd,"_open_device_connection",return_value=fake), mock.patch.object(budget,"check_time",side_effect=[None,None,sd.SdError("TIME_BUDGET_EXCEEDED")]):
            with self.assertRaises(sd.SdError):
                sd._device_request(budget,"t","u","cam",sd._metadata_requests(),"metadata",DATE)
        self.assertTrue(fake.close.called)
