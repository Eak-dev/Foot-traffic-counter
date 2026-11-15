"""OD-46: one bounded SD sample over the vendor relay; never live preview.

Protocol adapted from pinned MIT OnTapo; see THIRD_PARTY_NOTICES.md.
Only the session manager supplies selected identity and a live lease guard.
Public reports contain no account/device identifiers, relay URLs or paths.
"""
import contextlib
import hashlib
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import stat
import subprocess
import time

from tools import ft_cloud_probe as cloud
from tools import ft_sd_probe as sd
from tools.ft_media_protocol import MediaError, validate_relay, control_frame, control_reply, download_frame

MAX_BYTES = 100 * 1024 * 1024
MAX_PART = 8 * 1024 * 1024
MAX_WIRE = MAX_BYTES + 1024 * 1024
SECONDS = 300
RESERVE = 10 * 1024**3
RELAY_HOST = "aps1-cipc-api.i.tplinkcloud.com"
# One native-download/recorded-relay sample is verified. Each further trial
# remains PO-scoped; this flag does not start or authorize batch acquisition.
LIVE_TRIAL_ENABLED = False
TRANSFER_MODE = "download"
LIST_WINDOW = "day"  # PO may select the exact reviewed noon window
CLIP_SELECTION = "shortest"  # PO-scoped experiment only; default media remains HOLD
ROOT = Path('/private/tmp') / ('ft-sd-sample-' + str(os.getuid()))
FFPROBE = Path(__file__).resolve().parent.parent / '.venv/ft-media-bin/ffprobe'


class SampleError(Exception):
    def __init__(self, code, http_status=None):
        allowed = {'TIMEOUT', 'QUOTA', 'DISK_SPACE', 'STORAGE', 'SAMPLE_EXISTS',
            'NO_ELIGIBLE_CLIP', 'IDENTITY', 'HTTP', 'TLS', 'CONNECT', 'PROTOCOL',
            'INCOMPLETE', 'VALIDATION', 'PUBLIC_ENDPOINT_REQUIRED', 'PREREQUISITE'}
        self.code = code if code in allowed else 'PROTOCOL'
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        super().__init__(self.code)


class Budget:
    def __init__(self, guard):
        self.start = time.monotonic()
        self.guard = guard
        self.metrics = {'media_phase': 'NOT_STARTED', 'wire_bytes': 0, 'media_bytes': 0,
                        'control_parts': 0, 'video_parts': 0, 'playback_ack': False}

    def check_time(self):
        self.guard()
        if time.monotonic() - self.start >= SECONDS:
            raise SampleError('TIMEOUT')

    def timeout(self):
        self.check_time()
        return max(.001, min(10, self.start + SECONDS - time.monotonic()))


def _private_root():
    try:
        ROOT.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = ROOT.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise SampleError('STORAGE')
    if any(p.is_symlink() for p in ROOT.parents):
        raise SampleError('STORAGE')
    # Only our fixed sample artifacts; never recursively remove user directories.
    for name in ('sample.ts', 'sample.part', 'fixed.mp4'):
        p = ROOT / name
        if p.exists() or p.is_symlink():
            st = p.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1 or st.st_mode & 0o077:
                raise SampleError('STORAGE')
            if time.time() - st.st_mtime < 86400:
                raise SampleError('SAMPLE_EXISTS')
            p.unlink()
    if shutil.disk_usage(ROOT).free < RESERVE + MAX_BYTES:
        raise SampleError('DISK_SPACE')
    if not FFPROBE.is_file() or not os.access(FFPROBE, os.X_OK):
        raise SampleError('PREREQUISITE')


def _select_fixed_interval(candidates):
    # Already validated, unique and shortest-first by sd._fixed_intervals.
    if CLIP_SELECTION == 'nearest_noon':
        if LIST_WINDOW != 'noon' or not candidates:
            raise SampleError('NO_ELIGIBLE_CLIP')
        day, _ = sd._day_bounds_utc(sd.FIXED_DATE, '+07:00')
        noon = day + 12*3600
        return min(candidates, key=lambda x: (0 if x[0] <= noon < x[1] else min(abs(x[0]-noon), abs(x[1]-noon)), x[0]))
    if CLIP_SELECTION not in ('shortest', 'second_shortest'):
        raise SampleError('NO_ELIGIBLE_CLIP')
    index = 1 if CLIP_SELECTION == 'second_shortest' else 0
    if len(candidates) <= index:
        raise SampleError('NO_ELIGIBLE_CLIP')
    return candidates[index]


def _list_one(token, terminal, selected, budget):
    if not isinstance(selected, dict) or selected.get('model_kind') not in ('EXACT', 'VARIANT'):
        raise SampleError('IDENTITY')
    if not cloud._validate_canonical_app_server(selected.get('app_server')):
        raise SampleError('IDENTITY')
    device = sd._validate_device_id(selected.get('thing_name'))
    db = sd._DeviceBudget(session_guard=budget.check_time)

    def send(batch, uid=None):
        reqs = sd._expected_requests(batch, sd.FIXED_DATE, uid)
        raw = sd._device_request(db, token, terminal, device, reqs, batch, sd.FIXED_DATE, uid)
        return sd._parse_responses(raw, {r['method'] for r in reqs})

    meta = send('metadata')
    sd._read_device_model(meta['getDeviceInfo'], selected['model_kind'])
    tz = sd._read_timezone_offset(meta['getTimezone'])
    if tz != '+07:00' or sd._read_sd_status(meta['getSdCardStatus']) != 'NORMAL':
        raise SampleError('IDENTITY')
    cal = send('calendar')
    uid = sd._read_user_id(cal['getUserID'])
    if uid is None or not sd._read_calendar(cal['searchDateWithVideo'], sd.FIXED_DATE):
        raise SampleError('NO_ELIGIBLE_CLIP')
    if LIST_WINDOW not in ('day', 'noon'):
        raise SampleError('NO_ELIGIBLE_CLIP')
    clips = send('clip-noon' if LIST_WINDOW == 'noon' else 'clip-utc', uid)
    candidates, _rows, _missing = sd._fixed_intervals(clips['searchVideoWithUTC'])
    if LIST_WINDOW == 'noon':
        day, _ = sd._day_bounds_utc(sd.FIXED_DATE, '+07:00')
        candidates = [(s, e) for s, e in candidates if s < day + 12*3600 + 5*60 and e > day + 11*3600 + 55*60]
    if not candidates:
        raise SampleError('NO_ELIGIBLE_CLIP')
    start, end = _select_fixed_interval(candidates)
    # Pinned Camera.download obtains a fresh playback UID after search_day.
    # Reuse the already-reviewed calendar/getUserID envelope, still <=4 calls.
    fresh = send('calendar')
    playback_uid = sd._read_user_id(fresh['getUserID'])
    if playback_uid is None:
        raise SampleError('IDENTITY')
    budget.metrics['fresh_playback_uid'] = True
    budget.metrics['playback_uid_changed'] = playback_uid != uid
    return device, playback_uid, start, end, db.requests, len(candidates)


def _negotiate(token, terminal, device, track, budget):
    # Fixed request, no generic caller-supplied command or endpoint.
    body = json.dumps({'cloudType': 2,
        'customParams': '{"audio_config":{"encode_type":"G711ulaw","sample_rate":"16"}}',
        'dataTimeoutCount': 0, 'deviceId': sd._validate_device_id(device),
        'deviceType': 'SMART.IPCAMERA', 'playerId': terminal, 'preConnection': 0,
        'resolution': 'HD', 'rootCaVer': '1', 'streamType': 1, 'trackId': track}).encode()
    headers = {'Authorization': token, 'X-Client-Id': terminal, 'X-Source': 'tapo-app',
        'X-Brand': 'TPLINK', 'X-Ca-Type': 'cloud-self', 'X-Request-Signature': 'OnTapo',
        'Content-Type': 'application/json; charset=UTF-8',
        'User-Agent': 'Tapo_APP/ontapo/' + cloud.APP_VERSION + '_Android/Android 15'}
    conn = http.client.HTTPSConnection(RELAY_HOST, 443, context=cloud._pinned_context(), timeout=budget.timeout())
    try:
        conn.request('POST', '/v2/relay/request', body=body, headers=headers)
        budget.check_time()
        resp = conn.getresponse()
        raw = cloud._bounded_read(budget, resp)
        if resp.status != 200:
            raise SampleError('HTTP', resp.status)
        data = cloud._parse_json_object(raw)
        relay = validate_relay(data)
        ip = data['result'].get('relayIp')
        if ip:
            _public_ip(ip)
        return relay + (ip or None,)
    finally:
        conn.close()


def _public_ip(value):
    try:
        if not isinstance(value, str) or not ipaddress.ip_address(value).is_global:
            raise ValueError()
        return ipaddress.ip_address(value)
    except ValueError:
        raise SampleError('PUBLIC_ENDPOINT_REQUIRED') from None


def _dial(host, budget, relay_ip=None):
    # DNS resolved once and validated before connecting to the numeric address.
    # SNI/certificate hostname still use the negotiated vendor hostname.
    budget.metrics['media_phase'] = 'DNS'
    budget.check_time()
    if relay_ip is not None:
        ip = _public_ip(relay_ip)
        family = socket.AF_INET6 if ip.version == 6 else socket.AF_INET
        addresses = [(family, socket.SOCK_STREAM, 0, '',
                      (str(ip), 443, 0, 0) if ip.version == 6 else (str(ip), 443))]
    else:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    budget.check_time()
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise SampleError('PUBLIC_ENDPOINT_REQUIRED')
    family, kind, proto, _, address = addresses[0]
    sock = socket.socket(family, kind, proto)
    wrapped = None
    try:
        budget.metrics['media_phase'] = 'CONNECT'
        sock.settimeout(budget.timeout())
        sock.connect(address)
        budget.metrics['media_phase'] = 'TLS_HANDSHAKE'
        wrapped = cloud._pinned_context().wrap_socket(sock, server_hostname=host)
        budget.check_time()
        return wrapped
    except BaseException:
        if wrapped is not None:
            wrapped.close()
        sock.close()
        raise


class Reader:
    def __init__(self, sock, budget):
        self.sock, self.budget, self.buffer, self.total = sock, budget, bytearray(), 0
        self.last_data = time.monotonic()

    def _fill(self):
        self.sock.settimeout(self.budget.timeout())
        while True:
            self.sock.settimeout(self.budget.timeout())
            try:
                chunk = self.sock.recv(min(65536, MAX_WIRE - self.total + 1))
                break
            except socket.timeout:
                self.budget.check_time()
                # Read-wait on this same socket, not another playback request.
                idle_limit = 60 if self.budget.metrics['media_bytes'] == 0 else 12
                if time.monotonic() - self.last_data >= idle_limit:
                    raise
        self.last_data = time.monotonic()
        self.budget.check_time()
        self.total += len(chunk)
        self.budget.metrics['wire_bytes'] = self.total
        if self.total > MAX_WIRE:
            raise SampleError('QUOTA')
        if not chunk:
            raise SampleError('INCOMPLETE')
        self.buffer.extend(chunk)

    def line(self):
        while True:
            pos = self.buffer.find(b'\n')
            if pos >= 0:
                if pos > 8192:
                    raise SampleError('PROTOCOL')
                line = bytes(self.buffer[:pos+1])
                del self.buffer[:pos+1]
                return line.rstrip(b'\r\n')
            if len(self.buffer) > 8192:
                raise SampleError('PROTOCOL')
            self._fill()

    def exact(self, n):
        if type(n) is not int or not 0 <= n <= MAX_PART:
            raise SampleError('QUOTA')
        while len(self.buffer) < n:
            self._fill()
        data = bytes(self.buffer[:n])
        del self.buffer[:n]
        return data

    def headers(self):
        headers, size = {}, 0
        for _ in range(64):
            line = self.line()
            size += len(line)
            if size > 32768:
                raise SampleError('PROTOCOL')
            if not line:
                return headers
            key, sep, val = line.partition(b':')
            key = key.lower()
            if not sep or not re.fullmatch(rb'[a-z0-9-]+', key) or key in headers:
                raise SampleError('PROTOCOL')
            headers[key] = val.strip()
        raise SampleError('PROTOCOL')


class VideoClock:
    """Keep video PTS separately by PID, including split TS packets and rollover."""
    def __init__(self):
        self.tail = b''
        self.clocks = {}

    def update(self, data):
        data = self.tail + data
        stop = len(data) - len(data) % 188
        self.tail = data[stop:]
        for i in range(0, stop, 188):
            p = data[i:i+188]
            if p[0] != 0x47 or p[1] & 0x80 or p[3] & 0xc0:
                raise SampleError('PROTOCOL')
            mode = (p[3] >> 4) & 3
            if not p[1] & 0x40 or mode not in (1, 3):
                continue
            off = 4 if mode == 1 else 5 + p[4]
            if off + 14 > 188 or p[off:off+3] != b'\x00\x00\x01' or not 0xe0 <= p[off+3] <= 0xef:
                continue
            if not p[off+7] & 0x80 or p[off+8] < 5:
                continue
            v = p[off+9:off+14]
            if not all(v[x] & 1 for x in (0, 2, 4)):
                raise SampleError('PROTOCOL')
            pts = ((v[0] & 14) << 29) | (v[1] << 22) | ((v[2] & 254) << 14) | (v[3] << 7) | (v[4] >> 1)
            pid = ((p[1] & 31) << 8) | p[2]
            first, span = self.clocks.get(pid, (pts, 0))
            delta = (pts - first) % (1 << 33)
            if delta < 90000 * 3600:
                self.clocks[pid] = (first, max(span, delta))

    def covers(self, seconds):
        return bool(self.clocks) and all(v[1] / 90000 >= seconds for v in self.clocks.values())


# Known common diagnostic vocabulary for status/reason; never arbitrary text.
_IDENTIFIER_VOCAB = {'finished', 'playing', 'stopped', 'no_data', 'no_video',
                      'error', 'normal', 'ok', 'success', 'timeout'}
_IDENTIFIER_RE = re.compile(r'[a-z]+(?:_[a-z]+)*')
_MAX_IDENTIFIERS = 16


# Diagnostics admit only fixed protocol containers/values. Unknown subtrees,
# arbitrary text, sequence/session IDs, timestamps and credentials are dropped.
def _control_summary(obj):
    markers, codes, identifiers, total = set(), set(), {}, [0]
    containers = {'params', 'data', 'result', 'playback', 'download', 'stream_status'}
    enums = {'playing', 'finished', 'stopped', 'paused', 'success', 'error',
             'no_data', 'idle', 'stream_status', 'response', 'notification'}
    def visit(value, depth=0):
        if depth > 8:
            return
        if isinstance(value, list):
            for item in value[:20]:
                visit(item, depth+1)
        elif isinstance(value, dict):
            if value.get('event_type') == 'channel_lens_mask_info' and value.get('enabled') in ('on', 'off'):
                markers.add('lens_mask_' + value['enabled'])
            for key, val in value.items():
                if key in ('session_id', 'playback', 'download', 'event_type', 'stream_status'):
                    markers.add('has_' + key)
                if key in ('type', 'method', 'event_type', 'status', 'stream_status') and isinstance(val, str) and val in enums:
                    markers.add(val)
                if key in ('error_code', 'errorCode') and type(val) is int and -1000000 <= val <= 1000000:
                    if len(codes) < 16:
                        codes.add(val)
                if (key in ('event_type', 'status', 'reason') and isinstance(val, str)
                        and total[0] < _MAX_IDENTIFIERS and 3 <= len(val) <= 48
                        and _IDENTIFIER_RE.fullmatch(val)
                        and ((key == 'event_type' and '_' in val)
                             or (key != 'event_type' and val in _IDENTIFIER_VOCAB))):
                    bucket = identifiers.setdefault(key, set())
                    if val not in bucket:
                        bucket.add(val)
                        total[0] += 1
                if key in containers:
                    visit(val, depth+1)
    visit(obj)
    return {'markers': sorted(markers), 'error_codes': sorted(codes),
            'protocol_identifiers': {k: sorted(v) for k, v in identifiers.items()}}


def _stream(relay, terminal, track, uid, start, end, out, budget, mode='playback', *, short_recording=False):
    if type(short_recording) is not bool or (short_recording and mode!='download'):
        raise SampleError('PROTOCOL')
    if mode not in ('playback', 'download'):
        raise SampleError('PROTOCOL')
    host, path, relay_token = relay[:3]
    relay_ip = relay[3] if len(relay) == 4 else None
    head = (f'POST {path}&retryTime=0 HTTP/1.1\r\nHost: {host}\r\n'
        'User-Agent: Client=TP-Link_Tapo_Android Android 3.20.512/1.3\r\nAccept: */*\r\n'
        'Keep-Relay: 3600\r\nContent-Type: multipart/mixed;boundary=--client-stream-boundary--\r\n'
        'Content-Length: 9223372036854775807\r\n'
        f'X-token: {relay_token}\r\nX-Client-Model: OnTapo\r\nX-Client-UUID: {terminal}\r\n'
        f'X-Track-Id: {track}\r\nX-Redirect-Times: 0\r\nX-Pull-Mode: 2\r\n'
        'X-Compete: 1\r\nX-Version: 2.0\r\nX-Arrive-Latency: 200\r\n\r\n').encode('ascii')
    budget.metrics['negotiated_ip_used'] = relay_ip is not None
    sock = _dial(host, budget, relay_ip)
    written, clock = 0, VideoClock()
    started = False
    try:
        budget.metrics['media_phase'] = 'SEND_PLAYBACK'
        sock.settimeout(budget.timeout())
        frame = (download_frame(uid,start,end,terminal,short_recording=True) if short_recording else
                 download_frame(uid,start,end,terminal) if mode=='download' else control_frame(uid,start,end))
        sock.sendall(head + frame)
        started = True
        reader = Reader(sock, budget)
        budget.metrics['media_phase'] = 'RESPONSE_HEAD'
        line = reader.line()
        match = re.fullmatch(rb'HTTP/1\.[01] ([0-9]{3})(?: .*)?', line)
        if not match:
            raise SampleError('PROTOCOL')
        status = int(match[1])
        hdr = reader.headers()
        if status != 200:
            raise SampleError('HTTP', status)
        if b'transfer-encoding' in hdr or b'content-encoding' in hdr:
            raise SampleError('PROTOCOL')
        for _ in range(10000):
            budget.metrics['media_phase'] = 'PART_HEADER'
            budget.check_time()
            line = reader.line()
            if not line:
                line = reader.line()
            if line not in (b'--device-stream-boundary--', b'----device-stream-boundary--'):
                raise SampleError('PROTOCOL')
            hdr = reader.headers()
            length = hdr.get(b'content-length', b'')
            if not re.fullmatch(rb'[0-9]{1,8}', length):
                raise SampleError('PROTOCOL')
            n = int(length)
            ct = hdr.get(b'content-type', b'').split(b';')[0].lower()
            if ct not in (b'video/mp2t', b'application/json'):
                raise SampleError('PROTOCOL')
            if n > MAX_PART or (ct == b'application/json' and n > 65536) or written + n > MAX_BYTES:
                raise SampleError('QUOTA')
            try:
                budget.metrics['media_phase'] = 'PART_BODY'
                payload = reader.exact(n)
            except (socket.timeout, SampleError):
                raise  # a partial part never proves completion
            if ct == b'video/mp2t':
                budget.metrics['video_parts'] += 1
                if shutil.disk_usage(ROOT).free < RESERVE + n:
                    raise SampleError('DISK_SPACE')
                clock.update(payload)
                out.write(payload)
                written += n
                budget.metrics['media_bytes'] = written
                if clock.covers(end - start + 2):
                    return written
            else:
                budget.metrics['control_parts'] += 1
                # Fixed protocol markers only, computed BEFORE any terminal
                # END/INCOMPLETE decision, so redacted diagnostics survive
                # even a zero-media terminal notification. Never dump an
                # arbitrary reply: only known path names/status enum values,
                # bounded integer error codes and presence booleans are kept.
                obj = cloud._parse_json_object(payload)
                summary = _control_summary(obj)
                parts = budget.metrics.setdefault('control_summaries', [])
                if len(parts) == 8:
                    parts.pop()  # preserve first seven plus latest terminal part
                parts.append(summary)
                markers = set(budget.metrics.get('control_markers', []))
                markers.update(summary['markers'])
                budget.metrics['control_markers'] = sorted(markers)
                identifiers = budget.metrics.setdefault('control_identifiers', {})
                total = sum(len(v) for v in identifiers.values())
                for ikey, ivals in summary['protocol_identifiers'].items():
                    bucket = set(identifiers.get(ikey, []))
                    for ival in ivals:
                        if ival in bucket:
                            continue
                        if total >= _MAX_IDENTIFIERS:
                            break
                        bucket.add(ival)
                        total += 1
                    identifiers[ikey] = sorted(bucket)
                reply = control_reply(payload)
                if obj.get('type') == 'response':
                    budget.metrics['control_ack'] = True
                    budget.metrics[mode + '_ack'] = True
                if reply == 'END':
                    if not clock.covers(end - start - 2) or clock.tail:
                        raise SampleError('INCOMPLETE')
                    return written
        raise SampleError('QUOTA')
    except (socket.timeout, SampleError) as exc:
        # Idle/EOF after complete packets may end a playback stream, but only
        # measured video PTS plus subsequent ffprobe validation can accept it.
        if (isinstance(exc, socket.timeout) or exc.code == 'INCOMPLETE') and clock.covers(end-start-2) and not clock.tail:
            return written
        raise
    finally:
        if started and mode == 'playback':
            with contextlib.suppress(Exception):
                sock.settimeout(budget.timeout())
                sock.sendall(control_frame(uid, start, end, stop=True))
        sock.close()


def _inspect(path, duration, budget):
    budget.check_time()
    args = [str(FFPROBE), '-v', 'error', '-protocol_whitelist', 'file', '-f', 'mpegts',
        '-show_entries', 'stream=index,codec_type,codec_name,width,height,duration:format=duration',
        '-of', 'json', str(path)]
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                       timeout=min(30, max(.001, budget.start+SECONDS-time.monotonic())))
    budget.check_time()
    if p.returncode or len(p.stdout) > 65536:
        raise SampleError('VALIDATION')
    data = cloud._parse_json_object(p.stdout)
    videos = [v for v in data.get('streams', []) if v.get('codec_type') == 'video']
    if not 1 <= len(videos) <= 2:
        raise SampleError('VALIDATION')
    public = []
    for v in videos:
        span = float(v.get('duration', 'nan'))
        if not math.isfinite(span) or not duration - 2 <= span <= duration + 10:
            raise SampleError('INCOMPLETE')
        if v.get('codec_name') not in ('h264', 'hevc'):
            raise SampleError('VALIDATION')
        public.append({k: v[k] for k in ('index', 'codec_name', 'width', 'height')})
        public[-1]['duration_seconds'] = round(span, 3)
    return public


def sample_selected_device(token, terminal, selected, session_guard):
    if not LIVE_TRIAL_ENABLED:
        return {'status': 'BLOCKED', 'reason': 'MEDIA_TRIAL_NOT_ENABLED',
                'fixed_mapping': 'UNKNOWN', 'media_complete': False}
    return _run_sample(token, terminal, selected, session_guard)


def _run_sample(token, terminal, selected, session_guard):
    budget, stage, written = Budget(session_guard), 'PREFLIGHT', 0
    part, created = ROOT / 'sample.part', False
    facts = {'fixed_mapping': 'UNKNOWN', 'media_complete': False, 'transfer_mode': TRANSFER_MODE.upper(), 'relay_stream_type': 1}
    try:
        budget.check_time()
        if TRANSFER_MODE not in ('playback', 'download'):
            raise SampleError('PROTOCOL')
        _private_root()
        stage = 'LIST'
        device, uid, start, end, count, candidate_count = _list_one(token, terminal, selected, budget)
        facts.update(device_requests=count, requested_seconds=end-start,
                     lens_metadata_selected=True, fixed_candidate_count=candidate_count,
                     clip_selection=CLIP_SELECTION)
        track = 'backup-' + device + '-' + str(start)
        stage = 'RELAY'
        relay = _negotiate(token, terminal, device, track, budget)
        stage = 'MEDIA'
        fd = os.open(str(part), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        created = True
        with os.fdopen(fd, 'wb') as out:
            written = _stream(relay, terminal, track, uid, start, end, out, budget, mode=TRANSFER_MODE)
            out.flush()
            os.fsync(out.fileno())
        stage = 'VALIDATE'
        tracks = _inspect(part, end-start, budget)
        digest = hashlib.sha256()
        with part.open('rb') as stream:
            for block in iter(lambda: stream.read(65536), b''):
                budget.check_time()
                digest.update(block)
        # Hard-link provides atomic no-overwrite publication on the same volume.
        budget.check_time()
        os.link(part, ROOT / 'sample.ts', follow_symlinks=False)
        part.unlink()
        created = False
        return dict(facts, status='SUCCESS', bytes_written=written, sha256=digest.hexdigest(),
                    media_complete=True, video_tracks=tracks, fixed_mapping='PENDING_VISUAL_VERIFICATION')
    except (SampleError, MediaError, sd.SdError, cloud.ProbeError) as exc:
        result = dict(facts, status='BLOCKED', stage=stage, reason=exc.code, **budget.metrics)
        if getattr(exc, 'http_status', None) is not None:
            result['http_status'] = exc.http_status
        return result
    except ssl.SSLError:
        return dict(facts, status='BLOCKED', stage=stage, reason='TLS', **budget.metrics)
    except (socket.timeout, subprocess.TimeoutExpired):
        return dict(facts, status='BLOCKED', stage=stage, reason='TIMEOUT', **budget.metrics)
    except OSError:
        return dict(facts, status='BLOCKED', stage=stage, reason='IO_ERROR', **budget.metrics)
    finally:
        if created:
            with contextlib.suppress(OSError):
                part.unlink()
