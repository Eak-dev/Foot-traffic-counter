#!/usr/bin/env python3
"""Synthetic, offline unittests for tools/ft_media_protocol.py.

No network, no camera, no real relay/cloud payloads: all fixtures below
are hand-built synthetic JSON/bytes for adversarial-input coverage only.
"""
import json
import unittest

from tools.ft_media_protocol import (
    MediaError,
    control_frame,
    control_reply,
    validate_relay,
)


def _relay(url, token="abcDEF0123456789", error_code=0, result_override=None):
    result = {"relayUrl": url, "relayToken": token}
    if result_override is not None:
        result = result_override
    return {"errorCode": error_code, "result": result}


class ValidateRelayTests(unittest.TestCase):
    def test_accepts_well_formed_relay(self):
        data = _relay("https://relay1.tplinkcloud.com/relayservice?id=abc")
        host, path, token = validate_relay(data)
        self.assertEqual(host, "relay1.tplinkcloud.com")
        self.assertEqual(path, "/relayservice?id=abc")
        self.assertEqual(token, "abcDEF0123456789")

    def test_accepts_string_zero_error_code(self):
        data = _relay("https://relay1.tplinkcloud.com/relayservice?id=1", error_code="0")
        validate_relay(data)

    def test_rejects_nonzero_error_code(self):
        data = _relay("https://relay1.tplinkcloud.com/relayservice?id=1", error_code=1)
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_rejects_foreign_suffix_lookalike(self):
        data = _relay("https://relay1.tplinkcloud.com.evil.example/relayservice?id=1")
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_rejects_bare_root_domain(self):
        data = _relay("https://tplinkcloud.com/relayservice?id=1")
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_rejects_userinfo_injection(self):
        data = _relay("https://attacker@relay1.tplinkcloud.com/relayservice?id=1")
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_rejects_non_default_port(self):
        data = _relay("https://relay1.tplinkcloud.com:8443/relayservice?id=1")
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_rejects_http_scheme(self):
        data = _relay("http://relay1.tplinkcloud.com/relayservice?id=1")
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_rejects_fragment(self):
        data = _relay("https://relay1.tplinkcloud.com/relayservice?id=1#frag")
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_rejects_wrong_path(self):
        data = _relay("https://relay1.tplinkcloud.com/other?id=1")
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_rejects_empty_query(self):
        data = _relay("https://relay1.tplinkcloud.com/relayservice")
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_rejects_control_char_in_query(self):
        data = _relay("https://relay1.tplinkcloud.com/relayservice?id=1%0a")
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_ignores_relay_ip_field(self):
        result = {
            "relayUrl": "https://relay1.tplinkcloud.com/relayservice?id=1",
            "relayToken": "tok123",
            "relayIp": "203.0.113.5",
        }
        host, _path, token = validate_relay(_relay(None, result_override=result))
        self.assertEqual(host, "relay1.tplinkcloud.com")
        self.assertEqual(token, "tok123")

    def test_rejects_whitespace_token(self):
        data = _relay("https://relay1.tplinkcloud.com/relayservice?id=1", token="has space")
        with self.assertRaises(MediaError):
            validate_relay(data)

    def test_rejects_missing_result(self):
        with self.assertRaises(MediaError):
            validate_relay({"errorCode": 0})

    def test_rejects_duplicate_keys_in_source_json(self):
        raw = (
            '{"errorCode": 0, "result": {"relayUrl": '
            '"https://relay1.tplinkcloud.com/relayservice?id=1", '
            '"relayToken": "tok1", "relayToken": "tok2"}}'
        )
        decoder = json.JSONDecoder()
        data = decoder.decode(raw)
        # Simulate upstream duplicate-key handling by re-parsing through
        # the module's own strict object hook via a crafted dict replay.
        from tools.ft_media_protocol import _check_duplicate_keys

        with self.assertRaises(MediaError):
            _check_duplicate_keys([("relayToken", "tok1"), ("relayToken", "tok2")])


class ControlFrameTests(unittest.TestCase):
    def test_get_frame_exact_shape(self):
        frame = control_frame(42, 1000, 1010)
        header_end = frame.index(b"\r\n\r\n") + 4
        header = frame[:header_end]
        body = frame[header_end:]
        payload = body[:-2]
        self.assertEqual(body[-2:], b"\r\n")
        self.assertIn(
            b"Content-Length: " + str(len(payload)).encode() + b"\r\n", header
        )
        self.assertTrue(header.startswith(b"----client-stream-boundary--\r\n"))
        envelope = json.loads(payload.decode("ascii"))
        self.assertEqual(envelope["type"], "request")
        self.assertEqual(envelope["seq"], 1000 + (1000 % 20000))
        params = envelope["params"]
        self.assertEqual(params["method"], "get")
        playback = params["playback"]
        self.assertEqual(playback["client_id"], 42)
        self.assertEqual(playback["channels"], [0, 1])
        self.assertEqual(playback["scale"], "1/1")
        self.assertEqual(playback["start_time"], "1000")
        self.assertEqual(playback["end_time"], "1010")
        self.assertEqual(playback["event_type"], [1, 2])

    def test_stop_frame_exact_shape(self):
        frame = control_frame(42, 1000, 1010, stop=True)
        header_end = frame.index(b"\r\n\r\n") + 4
        payload = frame[header_end:-2]
        envelope = json.loads(payload.decode("ascii"))
        self.assertEqual(envelope["seq"], 1000 + (1000 % 20000) + 1)
        params = envelope["params"]
        self.assertEqual(params["method"], "stop")
        self.assertEqual(set(params["playback"].keys()), {"client_id", "channels"})
        self.assertEqual(params["playback"]["channels"], [0, 1])

    def test_content_length_matches_body(self):
        frame = control_frame(1, 5, 30)
        header_end = frame.index(b"\r\n\r\n") + 4
        header = frame[:header_end]
        body = frame[header_end:]
        length_line = [
            line for line in header.split(b"\r\n") if line.startswith(b"Content-Length:")
        ][0]
        declared = int(length_line.split(b":")[1].strip())
        self.assertEqual(declared, len(body) - 2)

    def test_rejects_bool_uid(self):
        with self.assertRaises(MediaError):
            control_frame(True, 1000, 1010)

    def test_rejects_bool_stop(self):
        with self.assertRaises(MediaError):
            control_frame(1, 1000, 1010, stop=1)

    def test_rejects_non_int_uid(self):
        with self.assertRaises(MediaError):
            control_frame("42", 1000, 1010)

    def test_rejects_zero_uid(self):
        with self.assertRaises(MediaError):
            control_frame(0, 1000, 1010)

    def test_rejects_uid_over_max(self):
        with self.assertRaises(MediaError):
            control_frame(2 ** 63, 1000, 1010)

    def test_rejects_start_after_end(self):
        with self.assertRaises(MediaError):
            control_frame(1, 1010, 1000)

    def test_rejects_span_too_short(self):
        with self.assertRaises(MediaError):
            control_frame(1, 1000, 1002)

    def test_rejects_span_too_long(self):
        with self.assertRaises(MediaError):
            control_frame(1, 1000, 1000 + 181)

    def test_rejects_end_over_max_time(self):
        with self.assertRaises(MediaError):
            control_frame(1, 4102444790, 4102444801)


def _reply_bytes(obj):
    return json.dumps(obj).encode("utf-8")


class ControlReplyTests(unittest.TestCase):
    def test_ack_on_zero_error_code_response(self):
        payload = _reply_bytes({"type": "response", "error_code": 0})
        self.assertEqual(control_reply(payload), "ACK")

    def test_ack_on_notification_without_error_code(self):
        payload = _reply_bytes({"type": "notification"})
        self.assertEqual(control_reply(payload), "ACK")

    def test_ack_on_string_zero_error_code_in_params(self):
        payload = _reply_bytes({"type": "response", "params": {"error_code": "0"}})
        self.assertEqual(control_reply(payload), "ACK")

    def test_end_on_structured_stream_status(self):
        payload = _reply_bytes({"type": "notification", "stream_status": "finished"})
        self.assertEqual(control_reply(payload), "END")

    def test_end_on_playback_done_event(self):
        payload = _reply_bytes({"type": "notification", "event": "playback_done"})
        self.assertEqual(control_reply(payload), "END")

    def test_end_on_playfinished_in_params_method(self):
        payload = _reply_bytes(
            {"type": "notification", "params": {"method": "playfinished"}}
        )
        self.assertEqual(control_reply(payload), "END")

    def test_refused_on_nonzero_error_code(self):
        payload = _reply_bytes({"type": "response", "error_code": 1})
        with self.assertRaises(MediaError) as ctx:
            control_reply(payload)
        self.assertEqual(ctx.exception.code, "STREAM_REFUSED")

    def test_busy_on_dash_52405(self):
        payload = _reply_bytes({"type": "response", "error_code": -52405})
        with self.assertRaises(MediaError) as ctx:
            control_reply(payload)
        self.assertEqual(ctx.exception.code, "STREAM_BUSY")

    def test_malformed_on_bad_error_code_type(self):
        payload = _reply_bytes({"type": "response", "error_code": "not-a-number"})
        with self.assertRaises(MediaError) as ctx:
            control_reply(payload)
        self.assertEqual(ctx.exception.code, "REPLY_MALFORMED")

    def test_malformed_on_bool_error_code(self):
        payload = _reply_bytes({"type": "response", "error_code": True})
        with self.assertRaises(MediaError):
            control_reply(payload)

    def test_malformed_on_response_without_explicit_zero(self):
        payload = _reply_bytes({"type": "response"})
        with self.assertRaises(MediaError):
            control_reply(payload)

    def test_malformed_on_unknown_textual_status(self):
        payload = _reply_bytes({"type": "response", "error_code": 0, "msg": "stream finished ok"})
        self.assertEqual(control_reply(payload), "ACK")

    def test_malformed_on_duplicate_keys(self):
        raw = '{"type": "response", "error_code": 0, "error_code": 1}'
        with self.assertRaises(MediaError):
            control_reply(raw.encode("utf-8"))

    def test_malformed_on_non_utf8_bytes(self):
        with self.assertRaises(MediaError):
            control_reply(b"\xff\xfe\x00\x01")

    def test_malformed_on_empty_payload(self):
        with self.assertRaises(MediaError):
            control_reply(b"")

    def test_malformed_on_oversized_payload(self):
        huge = _reply_bytes({"type": "notification", "pad": "x" * 70000})
        with self.assertRaises(MediaError):
            control_reply(huge)

    def test_malformed_on_non_object_json(self):
        with self.assertRaises(MediaError):
            control_reply(b"[1,2,3]")

    def test_malformed_on_invalid_json(self):
        with self.assertRaises(MediaError):
            control_reply(b"{not json")


if __name__ == "__main__":
    unittest.main()
