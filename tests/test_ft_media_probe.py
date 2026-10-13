"""Synthetic only: no Keychain, camera, DNS, media program or private files."""
import contextlib
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import ft_media_probe as m
from tools import ft_media_protocol as p


def packet(seconds, pid=256):
    v = int(seconds * 90000) % (1 << 33)
    pts = bytes([0x21 | ((v >> 29) & 14), (v >> 22) & 255,
                 ((v >> 14) & 254) | 1, (v >> 7) & 255, ((v << 1) & 254) | 1])
    data = bytes([0x47, 0x40 | (pid >> 8), pid & 255, 0x10])
    data += b'\x00\x00\x01\xe0\x00\x00\x80\x80\x05' + pts
    return data.ljust(188, b'\xff')


class Sock:
    def __init__(self, data):
        self.data, self.sent = io.BytesIO(data), []
        self.closed = False
    def recv(self, n):
        return self.data.read(n)
    def sendall(self, data):
        self.sent.append(data)
    def settimeout(self, _):
        pass
    def close(self):
        self.closed = True


def multipart(payload, ct=b'video/mp2t'):
    return b'----device-stream-boundary--\r\nContent-Type: ' + ct + b'\r\nContent-Length: ' + str(len(payload)).encode() + b'\r\n\r\n' + payload + b'\r\n'


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.budget = m.Budget(lambda: None)

    def test_bad_error_codes_and_port_are_redacted(self):
        base = {'errorCode': 0, 'result': {'relayUrl': 'https://relay.tplinkcloud.com/relayservice?r=secret', 'relayToken': 'synthetic'}}
        for code in (False, 0.0, None):
            with self.subTest(code=code), self.assertRaises(p.MediaError):
                p.validate_relay(dict(base, errorCode=code))
        base['result']['relayUrl'] = 'https://relay.tplinkcloud.com:secret/relayservice?r=x'
        with self.assertRaises(p.MediaError) as e:
            p.validate_relay(base)
        self.assertNotIn('secret', str(e.exception))

    def test_reply_conflict_and_false_not_success(self):
        for obj in ({'type': 'response', 'error_code': False},
                    {'type': 'response', 'error_code': 0.0},
                    {'type': 'notification', 'error_code': None},
                    {'type': 'response', 'error_code': 0, 'params': {'error_code': -1}},
                    {'type': 'bogus', 'stream_status': 'finished'}):
            with self.subTest(obj=obj), self.assertRaises(p.MediaError):
                p.control_reply(json.dumps(obj).encode())

    def test_nested_finished_notification_is_not_media_success(self):
        obj = {'type':'notification','params':{'event_type':'stream_status','data':{'status':'finished'}}}
        self.assertEqual(p.control_reply(json.dumps(obj).encode()),'END')
        self.assertEqual(p.control_reply(b'{"type":"notification","message":"stream_status finished"}'),'ACK')
        sock=Sock(b'HTTP/1.1 200 OK\r\n\r\n'+multipart(json.dumps(obj).encode(),b'application/json'))
        with patch.object(m,'_dial',return_value=sock),self.assertRaisesRegex(m.SampleError,'INCOMPLETE'):
            m._stream(('relay.tplinkcloud.com','/relayservice?r=x','token'),'uuid','track',1,100,110,io.BytesIO(),self.budget)

    def test_terminal_diagnostics_survive_zero_media_and_are_bounded(self):
        ack = {'type':'response', 'params':{'error_code':0,'session_id':'secret-session'}}
        end = {'type':'notification','params':{'event_type':'stream_status','status':'finished'}}
        wire = b'HTTP/1.1 200 OK\r\n\r\n'
        wire += multipart(json.dumps(ack).encode(), b'application/json') * 10
        wire += multipart(json.dumps(end).encode(), b'application/json')
        sock = Sock(wire)
        with patch.object(m,'_dial',return_value=sock), self.assertRaisesRegex(m.SampleError,'INCOMPLETE'):
            m._stream(('relay.tplinkcloud.com','/relayservice?r=x','token'),'uuid','track',1,100,110,io.BytesIO(),self.budget)
        self.assertEqual(len(self.budget.metrics['control_summaries']),8)
        self.assertIn('finished',self.budget.metrics['control_summaries'][-1]['markers'])
        self.assertIn('finished',self.budget.metrics['control_markers'])
        self.assertTrue(self.budget.metrics['playback_ack'])
        self.assertEqual(self.budget.metrics['media_bytes'],0)
        self.assertNotIn('secret-session',json.dumps(self.budget.metrics))

    def test_diagnostics_drop_unknown_text_and_numeric_identifiers(self):
        obj = {'type':'notification','params':{'event_type':'stream_status',
            'data':{'status':'finished','error_code':-52405,'session_id':987654,
                    'reason':'private-message','errorCode':True},
            'unknown':{'error_code':123456,'status':'playing'},
            'seq':543210,'url':'https://secret.example','token':'secret'},
            'private-key':{'status':'paused'}}
        summary = m._control_summary(obj)
        self.assertEqual(summary['error_codes'],[-52405])
        text = json.dumps(summary)
        for private in ('987654','543210','123456','private','secret','playing','paused'):
            self.assertNotIn(private,text)
        self.assertIn('finished',text)
        self.assertIn('has_session_id',text)

    def test_refusal_is_not_ack_but_has_redacted_code(self):
        data = {'type':'response','params':{'error_code':-52405}}
        sock=Sock(b'HTTP/1.1 200 OK\r\n\r\n'+multipart(json.dumps(data).encode(),b'application/json'))
        with patch.object(m,'_dial',return_value=sock),self.assertRaisesRegex(p.MediaError,'STREAM_BUSY'):
            m._stream(('relay.tplinkcloud.com','/relayservice?r=x','token'),'uuid','track',1,100,110,io.BytesIO(),self.budget)
        self.assertFalse(self.budget.metrics['playback_ack'])
        self.assertEqual(self.budget.metrics['control_summaries'][0]['error_codes'],[-52405])

    def test_diagnostic_depth_list_and_code_limits(self):
        obj = {'params':[{'error_code':n} for n in range(100)]}
        self.assertLessEqual(len(m._control_summary(obj)['error_codes']),16)
        obj = {'error_code':999999}
        for _ in range(10): obj={'params':obj}
        self.assertEqual(m._control_summary(obj)['error_codes'],[])
        for code in (True, '1234',1000001,-1000001):
            self.assertEqual(m._control_summary({'error_code':code})['error_codes'],[])

    def test_fresh_uid_after_listing_uses_four_bounded_requests(self):
        replies=[{'getDeviceInfo':{},'getTimezone':{},'getSdCardStatus':{}},
                 {'getUserID':{},'searchDateWithVideo':{}}, {'searchVideoWithUTC':{}},
                 {'getUserID':{},'searchDateWithVideo':{}}]
        def send(budget,*args):
            budget.use_request()
            return b'{}'
        with patch.object(m.sd,'_device_request',side_effect=send) as request, patch.object(m.sd,'_parse_responses',side_effect=replies), patch.object(m.sd,'_read_device_model'), patch.object(m.sd,'_read_timezone_offset',return_value='+07:00'), patch.object(m.sd,'_read_sd_status',return_value='NORMAL'), patch.object(m.sd,'_read_calendar',return_value=True), patch.object(m.sd,'_read_user_id',side_effect=[7,9]), patch.object(m.sd,'_fixed_intervals',return_value=([(100,110),(200,260)],2,0)):
            result=m._list_one('token','uuid',{'thing_name':'synthetic','model_kind':'EXACT','app_server':None},self.budget)
            self.assertEqual(result,('synthetic',9,100,110,4,2))
            self.assertEqual([c.args[5] for c in request.call_args_list],['metadata','calendar','clip-utc','calendar'])

    def test_no_lens1_candidate_is_rejected(self):
        replies=[{'getDeviceInfo':{},'getTimezone':{},'getSdCardStatus':{}},
                 {'getUserID':{},'searchDateWithVideo':{}}, {'searchVideoWithUTC':{}}]
        def send(budget,*args):
            budget.use_request()
            return b'{}'
        with patch.object(m.sd,'_device_request',side_effect=send), patch.object(m.sd,'_parse_responses',side_effect=replies), patch.object(m.sd,'_read_device_model'), patch.object(m.sd,'_read_timezone_offset',return_value='+07:00'), patch.object(m.sd,'_read_sd_status',return_value='NORMAL'), patch.object(m.sd,'_read_calendar',return_value=True), patch.object(m.sd,'_read_user_id',return_value=7), patch.object(m.sd,'_fixed_intervals',return_value=([],5,5)):
            with self.assertRaisesRegex(m.SampleError,'NO_ELIGIBLE_CLIP'):
                m._list_one('token','uuid',{'thing_name':'synthetic','model_kind':'EXACT','app_server':None},self.budget)

    def test_clock_fragmented_packets_and_independent_pids(self):
        c = m.VideoClock()
        data = packet(0) + packet(10) + packet(0, 257)
        c.update(data[:201]); c.update(data[201:])
        self.assertFalse(c.covers(8))
        c.update(packet(9, 257))
        self.assertTrue(c.covers(8))
        self.assertFalse(c.tail)

    def test_clock_wrap_and_invalid_sync(self):
        c = m.VideoClock()
        c.update(packet(((1 << 33) - 90000) / 90000) + packet(9))
        self.assertTrue(c.covers(9))
        with self.assertRaises(m.SampleError):
            c.update(b'x' * 188)

    def test_reader_duplicate_headers_and_large_line(self):
        for data in (b'A: 1\r\na: 2\r\n\r\n', b'x' * 9000 + b'\r\n'):
            with self.assertRaises(m.SampleError):
                m.Reader(Sock(data), self.budget).headers()

    def test_reader_wire_limit_and_lease(self):
        with patch.object(m, 'MAX_WIRE', 5), self.assertRaises(m.SampleError):
            m.Reader(Sock(b'123456'), self.budget).exact(6)
        guard = Mock(side_effect=RuntimeError('lease expired'))
        sock = Sock(b'abc')
        with self.assertRaises(RuntimeError):
            m.Reader(sock, m.Budget(guard)).exact(1)
        self.assertEqual(sock.data.tell(), 0)

    def test_first_media_wait_is_bounded_on_same_socket(self):
        now = [0.0]
        sock = Mock()
        def timeout(_):
            now[0] += 10
            raise socket.timeout()
        sock.recv.side_effect = timeout
        with patch.object(m.time, 'monotonic', side_effect=lambda: now[0]):
            reader = m.Reader(sock, m.Budget(lambda: None))
            with self.assertRaises(socket.timeout): reader.exact(1)
        self.assertEqual(sock.recv.call_count, 6)
        sock.sendall.assert_not_called()

    def test_initial_wait_rechecks_lease(self):
        guard = Mock(side_effect=[None, None, RuntimeError('expired')])
        sock = Mock()
        sock.recv.side_effect = socket.timeout()
        with self.assertRaises(RuntimeError):
            m.Reader(sock, m.Budget(guard)).exact(1)
        self.assertEqual(sock.recv.call_count, 1)

    def test_public_dns_guard_no_socket_for_private(self):
        with patch.object(socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]), patch.object(socket, 'socket') as sock:
            with self.assertRaises(m.SampleError):
                m._dial('relay.tplinkcloud.com', self.budget)
            sock.assert_not_called()

    def test_designated_ip_still_requires_vendor_hostname_tls(self):
        sock, tls, context = Mock(), Mock(), Mock()
        context.wrap_socket.return_value = tls
        with patch.object(socket, 'getaddrinfo') as dns, patch.object(socket, 'socket', return_value=sock), patch.object(m.cloud, '_pinned_context', return_value=context):
            self.assertIs(m._dial('relay.tplinkcloud.com', self.budget, '8.8.8.8'), tls)
            dns.assert_not_called()
            sock.connect.assert_called_once_with(('8.8.8.8', 443))
            context.wrap_socket.assert_called_once_with(sock, server_hostname='relay.tplinkcloud.com')
        for value in ('127.0.0.1', '10.0.0.1', '169.254.169.254', 'host.example', '8.8.8.8:443', 123):
            with patch.object(socket, 'socket') as create, self.assertRaises(m.SampleError):
                m._dial('relay.tplinkcloud.com', self.budget, value)
            create.assert_not_called()

    def test_stream_complete_packets_stop_and_no_preview(self):
        sock = Sock(b'HTTP/1.1 200 OK\r\n\r\n' + multipart(packet(0) + packet(12)))
        with patch.object(m, '_dial', return_value=sock), patch.object(m.shutil, 'disk_usage', return_value=Mock(free=m.RESERVE+10000)):
            out = io.BytesIO()
            self.assertEqual(m._stream(('relay.tplinkcloud.com','/relayservice?r=test','token'), 'uuid','track',1,100,110,out,self.budget),376)
        self.assertTrue(sock.closed)
        self.assertIn(b'r=test&retryTime=0',sock.sent[0])
        self.assertIn(b'"method":"stop"',sock.sent[-1])
        self.assertNotIn(b'preview',b''.join(sock.sent))

    def test_native_download_shape_and_close_no_playback_fallback(self):
        frame=p.download_frame(7,100,116,'test-uuid')
        head,body=frame.split(b'\r\n\r\n',1)
        self.assertIn(b'Content-Length: '+str(len(body)-2).encode(),head)
        obj=json.loads(body)
        self.assertEqual(obj['params'],{'method':'get','download':{'client_id':7,'channels':[0],'media_type':0,'start_time':'100','end_time':'116','player_id':'test-uuid'}})
        for bad in ('a\r\nb', '', True):
            with self.assertRaises(p.MediaError):p.download_frame(7,100,116,bad)
        sock=Sock(b'HTTP/1.1 200 OK\r\n\r\n'+multipart(packet(0)+packet(18)))
        with patch.object(m,'_dial',return_value=sock),patch.object(m.shutil,'disk_usage',return_value=Mock(free=m.RESERVE+10000)):
            m._stream(('relay.tplinkcloud.com','/relayservice?r=x','token'),'uuid','track',7,100,116,io.BytesIO(),self.budget,mode='download')
        self.assertEqual(len(sock.sent),1)
        self.assertNotIn(b'playback',sock.sent[0])
        self.assertTrue(sock.closed)

    def test_stream_refusal_incomplete_redirect_quota(self):
        cases = [b'HTTP/1.1 302 Found\r\n\r\n',
                 b'HTTP/1.1 200 OK\r\n\r\n'+multipart(b'{"type":"response","params":{"error_code":-52405}}',b'application/json'),
                 b'HTTP/1.1 200 OK\r\n\r\n'+multipart(packet(0)+packet(1)),
                 b'HTTP/1.1 200 OK\r\n\r\n----device-stream-boundary--\r\nContent-Type: video/mp2t\r\nContent-Length: 9000000\r\n\r\n']
        for data in cases:
            sock = Sock(data)
            with self.subTest(data=data[:24]), patch.object(m,'_dial',return_value=sock), patch.object(m.shutil,'disk_usage',return_value=Mock(free=m.RESERVE+10000)):
                with self.assertRaises((m.SampleError,p.MediaError)):
                    m._stream(('relay.tplinkcloud.com','/relayservice?r=x','token'),'uuid','track',1,100,110,io.BytesIO(),self.budget)
            self.assertTrue(sock.closed)

    def test_list_one_selects_shortest_validated_lens1_candidate(self):
        start, _ = m.sd._day_bounds_utc(m.sd.FIXED_DATE, '+07:00')
        data = {'playback': {'search_video_results': [
            {'a': {'startTime': start+1, 'endTime': start+61, 'vedio_type': 1,
                   'chn_times': {'1': {'event_start_time': start+41}}}},
            {'b': {'startTime': start+70, 'endTime': start+80, 'vedio_type': 1,
                   'chn_times': {'1': {'event_start_time': start+71}}}},
        ]}}
        replies = [{'getDeviceInfo': {}, 'getTimezone': {}, 'getSdCardStatus': {}},
                   {'getUserID': {}, 'searchDateWithVideo': {}}, {'searchVideoWithUTC': data},
                   {'getUserID': {}, 'searchDateWithVideo': {}}]

        def send(budget, *args):
            budget.use_request()
            return b'{}'
        with patch.object(m.sd, '_device_request', side_effect=send), patch.object(m.sd, '_parse_responses', side_effect=replies), patch.object(m.sd, '_read_device_model'), patch.object(m.sd, '_read_timezone_offset', return_value='+07:00'), patch.object(m.sd, '_read_sd_status', return_value='NORMAL'), patch.object(m.sd, '_read_calendar', return_value=True), patch.object(m.sd, '_read_user_id', side_effect=[7, 9]):
            result = m._list_one('token', 'uuid', {'thing_name': 'synthetic', 'model_kind': 'EXACT', 'app_server': None}, self.budget)
        self.assertEqual(result, ('synthetic', 9, start+71, start+80, 4, 2))

    def test_inspection_each_video_duration_required(self):
        data={'streams':[{'index':0,'codec_type':'video','codec_name':'h264','width':720,'height':480,'duration':'10'}]}
        with patch.object(m.subprocess,'run',return_value=Mock(returncode=0,stdout=json.dumps(data).encode())) as run:
            self.assertEqual(len(m._inspect(Path('/synthetic/sample.part'),10,self.budget)),1)
            self.assertIn('file',run.call_args.args[0])
        data['streams'].append(dict(data['streams'][0],index=1,duration='2'))
        with patch.object(m.subprocess,'run',return_value=Mock(returncode=0,stdout=json.dumps(data).encode())),self.assertRaises(m.SampleError):
            m._inspect(Path('/synthetic/sample.part'),10,self.budget)

    def test_failed_trial_removes_part_and_no_publication(self):
        with tempfile.TemporaryDirectory() as d, patch.object(m,'ROOT',Path(d)), patch.object(m,'_private_root'), patch.object(m,'_list_one',return_value=('dev',1,100,110,3,2)), patch.object(m,'_negotiate',return_value=('host','path','token')), patch.object(m,'_stream',side_effect=m.SampleError('QUOTA')) as stream:
            r=m._run_sample('secret','uuid',{},lambda:None)
            self.assertEqual(r['reason'],'QUOTA')
            self.assertEqual(list(Path(d).iterdir()),[])
            self.assertNotIn('secret',json.dumps(r))
            self.assertEqual(r['transfer_mode'],'PLAYBACK')
            self.assertTrue(r['lens_metadata_selected'])
            self.assertEqual(r['fixed_candidate_count'],2)
            self.assertEqual(stream.call_args.kwargs['mode'],'playback')

    def test_negotiate_requests_known_playback_stream_type(self):
        class Resp:
            status = 200
            def read(self, n):
                return b''
        conn = Mock()
        conn.getresponse.return_value = Resp()
        with patch.object(m.http.client, 'HTTPSConnection', return_value=conn), patch.object(m.cloud, '_bounded_read', return_value=json.dumps({'errorCode': 0, 'result': {'relayUrl': 'https://relay.tplinkcloud.com/relayservice?r=x', 'relayToken': 'tok'}}).encode()):
            m._negotiate('token', 'uuid', 'synthetic', 'track', self.budget)
        body = json.loads(conn.request.call_args.kwargs['body'])
        self.assertEqual(body['streamType'], 1)

    def test_private_staging_rejects_symlink_and_preserves_recent_sample(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'sample'; root.mkdir(mode=0o700)
            with patch.object(m,'ROOT',root):
                (root/'sample.ts').symlink_to('/nonexistent')
                with self.assertRaises(m.SampleError):m._private_root()
                (root/'sample.ts').unlink()
                f=root/'sample.ts';f.write_bytes(b'keep');f.chmod(0o600)
                with self.assertRaises(m.SampleError):m._private_root()
                self.assertEqual(f.read_bytes(),b'keep')
