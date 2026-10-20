#!/usr/bin/env python3
"""FT-D0: offline-only Tapo relay/playback protocol helpers (synthetic).

Message shapes (relay discovery JSON fields, the multipart-style stream
header with ``X-Data-Window-Size``, and the playback ``get``/``stop``
control-frame envelope) are adapted from OnTapo at commit
a387f6abddb72f7e6eea72b374df5ad189da1f5f (relay.py/stream.py); see
docs/THIRD_PARTY_NOTICES.md. This module does not copy the upstream
client, open any socket, or send/receive anything: it only validates and
builds/parses byte strings supplied by the caller. No camera, cloud, SD,
or network access of any kind.
"""
from __future__ import annotations

import json
import re
from urllib.parse import unquote, urlsplit

__all__ = [
    "MediaError",
    "validate_relay",
    "control_frame",
    "control_reply",
]

_ERR_RELAY_ERRORCODE = "RELAY_ERRORCODE"
_ERR_RELAY_SHAPE = "RELAY_SHAPE"
_ERR_RELAY_URL = "RELAY_URL"
_ERR_RELAY_TOKEN = "RELAY_TOKEN"
_ERR_FRAME_PARAMS = "FRAME_PARAMS"
_ERR_REPLY_MALFORMED = "REPLY_MALFORMED"
_ERR_REPLY_REFUSED = "STREAM_REFUSED"
_ERR_REPLY_BUSY = "STREAM_BUSY"

_PRINTABLE_ASCII_RE = re.compile(r"^[\x20-\x7e]+$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_RELAY_SUFFIX = ".tplinkcloud.com"
_RELAY_ROOT = "tplinkcloud.com"


class MediaError(Exception):
    """Raised with a fixed enum ``code``; never echoes raw input."""

    def __init__(self, code: str):
        code = code if code in {"RELAY_ERRORCODE", "RELAY_SHAPE", "RELAY_URL", "RELAY_TOKEN", "FRAME_PARAMS", "REPLY_MALFORMED", "STREAM_REFUSED", "STREAM_BUSY"} else "REPLY_MALFORMED"
        super().__init__(code)
        self.code = code


def _is_printable_ascii(value: str, max_len: int) -> bool:
    if not isinstance(value, str) or not value or len(value) > max_len:
        return False
    return bool(_PRINTABLE_ASCII_RE.match(value))


def _check_duplicate_keys(pairs):
    seen = set()
    for key, _value in pairs:
        if key in seen:
            raise MediaError(_ERR_RELAY_SHAPE)
        seen.add(key)
    return dict(pairs)


def validate_relay(data):
    """Validate a decoded relay-discovery response.

    Returns ``(host, path, relay_token)``. Only ``relayUrl``/``relayToken``
    are ever used; ``relayIp``/CDN fields are ignored even if present.
    """
    if not isinstance(data, dict):
        raise MediaError(_ERR_RELAY_SHAPE)

    error_code = data.get("errorCode")
    if not ((type(error_code) is int and error_code == 0) or error_code == "0"):
        raise MediaError(_ERR_RELAY_ERRORCODE)

    result = data.get("result")
    if not isinstance(result, dict):
        raise MediaError(_ERR_RELAY_SHAPE)

    relay_url = result.get("relayUrl")
    relay_token = result.get("relayToken")
    if not isinstance(relay_url, str) or not isinstance(relay_token, str):
        raise MediaError(_ERR_RELAY_SHAPE)

    if not _is_printable_ascii(relay_url, 4096) or any(c.isspace() for c in relay_url):
        raise MediaError(_ERR_RELAY_URL)

    try:
        parts = urlsplit(relay_url)
        port = parts.port
    except ValueError:
        raise MediaError(_ERR_RELAY_URL)

    if parts.scheme != "https":
        raise MediaError(_ERR_RELAY_URL)
    if "@" in parts.netloc:
        raise MediaError(_ERR_RELAY_URL)
    if parts.fragment:
        raise MediaError(_ERR_RELAY_URL)
    if port not in (None, 443):
        raise MediaError(_ERR_RELAY_URL)

    host = parts.hostname
    if not host or len(host) > 253:
        raise MediaError(_ERR_RELAY_URL)
    host = host.lower()
    if host == _RELAY_ROOT or not host.endswith(_RELAY_SUFFIX):
        raise MediaError(_ERR_RELAY_URL)
    label_part = host[: -len(_RELAY_SUFFIX)]
    if not label_part or label_part.startswith(".") or label_part.endswith("."):
        raise MediaError(_ERR_RELAY_URL)
    labels = label_part.split(".")
    label_re = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
    for label in labels:
        if not label or not label_re.match(label):
            raise MediaError(_ERR_RELAY_URL)

    if parts.path != "/relayservice":
        raise MediaError(_ERR_RELAY_URL)

    if not parts.query:
        raise MediaError(_ERR_RELAY_URL)
    if _CONTROL_CHARS_RE.search(parts.query) or _CONTROL_CHARS_RE.search(
        unquote(parts.query)
    ):
        raise MediaError(_ERR_RELAY_URL)

    if not _is_printable_ascii(relay_token, 8192):
        raise MediaError(_ERR_RELAY_TOKEN)
    if any(ch.isspace() for ch in relay_token):
        raise MediaError(_ERR_RELAY_TOKEN)

    return host, parts.path + "?" + parts.query, relay_token


_MAX_UID = 2 ** 63 - 1
_MAX_TIME = 4102444800
_MIN_SPAN = 5
_MAX_SPAN = 180


def _validate_control_args(uid, start, end, stop, short_recording=False):
    if type(short_recording) is not bool:raise MediaError(_ERR_FRAME_PARAMS)
    if isinstance(uid, bool) or not isinstance(uid, int):
        raise MediaError(_ERR_FRAME_PARAMS)
    if uid <= 0 or uid > _MAX_UID:
        raise MediaError(_ERR_FRAME_PARAMS)
    for value in (start, end):
        if isinstance(value, bool) or not isinstance(value, int):
            raise MediaError(_ERR_FRAME_PARAMS)
    if not (0 < start < end <= _MAX_TIME):
        raise MediaError(_ERR_FRAME_PARAMS)
    span = end - start
    if not ((1 if short_recording else _MIN_SPAN) <= span <= _MAX_SPAN):
        raise MediaError(_ERR_FRAME_PARAMS)
    if not isinstance(stop, bool):
        raise MediaError(_ERR_FRAME_PARAMS)


def control_frame(uid, start, end, stop=False):
    """Build one playback ``get``/``stop`` control frame as bytes."""
    _validate_control_args(uid, start, end, stop)

    seq = 1000 + (start % 20000)
    if stop:
        seq += 1

    channels = [0, 1]
    if stop:
        params = {
            "method": "stop",
            "playback": {
                "client_id": uid,
                "channels": channels,
            },
        }
    else:
        params = {
            "method": "get",
            "playback": {
                "client_id": uid,
                "channels": channels,
                "scale": "1/1",
                "start_time": str(start),
                "end_time": str(end),
                "event_type": [1, 2],
            },
        }

    envelope = {
        "type": "request",
        "seq": seq,
        "params": params,
    }
    body = json.dumps(envelope, separators=(",", ":")).encode("ascii")
    header = (
        b"----client-stream-boundary--\r\n"
        b"Content-Type: application/json\r\n"
        b"X-Data-Window-Size: 40\r\n"
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n"
    )
    return header + body + b"\r\n"


def download_frame(uid, start, end, player_id, *, short_recording=False):
    """One native recorded-download request (pytapo3.4.26 packet contract).

    No live preview, recovery, alternate channel or automatic fallback.
    """
    _validate_control_args(uid, start, end, False, short_recording)
    if not isinstance(player_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', player_id):
        raise MediaError(_ERR_FRAME_PARAMS)
    obj = {'type':'request', 'seq':1, 'params':{'method':'get', 'download':{
        'client_id':uid, 'channels':[0], 'media_type':0, 'start_time':str(start),
        'end_time':str(end), 'player_id':player_id}}}
    body = json.dumps(obj, separators=(',', ':')).encode('ascii')
    return (b'----client-stream-boundary--\r\nContent-Type: application/json\r\n'
            b'X-Data-Window-Size: 40\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body + b'\r\n')


_MAX_REPLY_LEN = 65536
_ACK = "ACK"
_END = "END"
_END_METHODS = ("playback_done", "playfinished")


def _parse_strict_json(text: str):
    decoder = json.JSONDecoder(object_pairs_hook=_check_duplicate_keys, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    try:
        return decoder.decode(text)
    except (ValueError, MediaError):
        raise MediaError(_ERR_REPLY_MALFORMED)


def _coerce_error_code(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]{1,10}", value):
        return int(value)
    raise MediaError(_ERR_REPLY_MALFORMED)


def control_reply(payload: bytes) -> str:
    """Parse one playback reply frame; returns ``"ACK"`` or ``"END"``."""
    if not isinstance(payload, bytes) or not payload or len(payload) > _MAX_REPLY_LEN:
        raise MediaError(_ERR_REPLY_MALFORMED)

    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise MediaError(_ERR_REPLY_MALFORMED)

    envelope = _parse_strict_json(text)
    if not isinstance(envelope, dict):
        raise MediaError(_ERR_REPLY_MALFORMED)

    params = envelope.get("params")
    if params is not None and not isinstance(params, dict):
        raise MediaError(_ERR_REPLY_MALFORMED)

    error_code = None
    for obj in (envelope, params or {}):
        if "error_code" in obj:
            code = _coerce_error_code(obj["error_code"])
            if code != 0:
                raise MediaError(_ERR_REPLY_BUSY if code == -52405 else _ERR_REPLY_REFUSED)
            error_code = code
    if envelope.get("type") not in ("response", "notification"):
        raise MediaError(_ERR_REPLY_MALFORMED)

    # Vendor notification nests stream state beneath a payload object. Match
    # only its exact event and state fields, never substrings in arbitrary text.
    def finished_event(value, depth=0):
        if depth > 8 or not isinstance(value, dict):
            return False
        event = value.get('event_type', value.get('event', value.get('method')))
        if event == 'stream_status':
            if value.get('status') == 'finished' or value.get('stream_status') == 'finished':
                return True
            for key in ('params', 'data', 'stream_status'):
                state = value.get(key)
                if isinstance(state, dict) and (state.get('status') == 'finished' or state.get('stream_status') == 'finished'):
                    return True
        return any(finished_event(v, depth + 1) for v in value.values() if isinstance(v, dict))
    if finished_event(envelope):
        return _END

    stream_status = envelope.get("stream_status")
    if stream_status is None and isinstance(params, dict):
        stream_status = params.get("stream_status")
    if stream_status == "finished":
        return _END

    method_or_event = envelope.get("method") or envelope.get("event")
    if method_or_event is None and isinstance(params, dict):
        method_or_event = params.get("method") or params.get("event")
    if method_or_event in _END_METHODS:
        return _END

    msg_type = envelope.get("type")
    if msg_type == "notification":
        return _ACK
    if msg_type == "response" and error_code == 0:
        return _ACK

    raise MediaError(_ERR_REPLY_MALFORMED)
