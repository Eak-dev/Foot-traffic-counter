"""Synthetic day, boundary, inventory and resumable-parent contracts; no camera."""
import copy
import csv
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from contextlib import redirect_stdout

from tools import ft_day_summary as ds,ft_day_acquire as da,ft_day_run as run,ft_sd_probe as sd
from tools.ft_day_count import ObservationStream,FrameClock,config_digest,worker_main,static_alignment_valid,LENS_POLICY,worker_failure_reason,source_duration_valid
from tools.ft_count import ValidationError
from tests import test_ft_lane_counter as lh

H='a'*64

def event(at,zone='front_shop',lane='near',status='accepted',salt=''):
    return dict(ref=ds.digest([at,zone,lane,status,salt]),at=at,zone=zone,lane=lane,status=status)

def clip(a=0,b=180,events=None,status='counted',salt=''):
    c=dict(ref=ds.digest([a,b,salt]),start=a,end=b,status=status,events=events or [])
    if status in ('counted','covered'):c.update(input_sha256='b'*64,config_sha256=H,clock_verified=True,lens_verified=True)
    return c

def ledger(clips=None,complete=True):
    return dict(schema_version=1,date='2026-10-12',timezone='+07:00',config_sha256=H,
                inventory_complete=complete,inventory_digest='c'*64,boundary_mode='continuous_state',clips=clips or [])

def config():
    a=lh.LaneIntegrationTests().make_zone();a['track_quality']='bbox_continuity_v1'
    b=dict(id='water_side',name='ข้างร้าน',color='#FF35EC',config=lh.base(),counter_mode='entries')
    return dict(zones=[a,b])

def box(p,h=.2):return [p[0]-.06,p[1]-h/2,p[0]+.06,p[1]+h/2]


class StaticLensAlignmentTests(unittest.TestCase):
    def test_night_alignment_requires_both_correlation_and_fixed_geometry(self):
        identity=[[1.,0.,0.],[0.,1.,0.]]
        self.assertTrue(static_alignment_valid(.8,identity))
        for score in (.74,float('nan'),float('inf'),True,1.1):self.assertFalse(static_alignment_valid(score,identity))
        for row,col,value in [(0,0,.95),(1,1,1.05),(0,1,.03),(1,0,.03),(0,2,20.),(1,2,-20.),(0,0,-1.)]:
            matrix=copy.deepcopy(identity);matrix[row][col]=value
            self.assertFalse(static_alignment_valid(.99,matrix))
        for bad in (None,[],[[1,0,0]],[[True,0,0],[0,1,0]],[[1,0,0],[0,1,float('nan')]]):
            self.assertFalse(static_alignment_valid(.99,bad))

    def test_short_download_allows_bounded_gop_tail_but_not_missing_footage(self):
        self.assertTrue(source_duration_valid(3,3.666667))
        self.assertTrue(source_duration_valid(3,2.94))
        for duration in (2.8,4.01,float('nan'),True):self.assertFalse(source_duration_valid(3,duration))
        self.assertTrue(source_duration_valid(86,85.999667))
        self.assertFalse(source_duration_valid(86,83.9))

    def test_worker_errors_are_specific_but_never_expose_runtime_text(self):
        self.assertEqual(worker_failure_reason(ValidationError('Fixed Lens ceiling verification failed')),'LENS_UNVERIFIED')
        self.assertEqual(worker_failure_reason(ValidationError('source duration does not match SD interval')),'CLOCK_UNVERIFIED')
        self.assertEqual(worker_failure_reason(RuntimeError('private-data-or-path')),'COUNT_VALIDATION_FAILED')

    def test_short_recording_is_explicit_and_native_download_only(self):
        from tools.ft_media_protocol import download_frame,control_frame,MediaError
        self.assertIn(b'"start_time":"1000"',download_frame(1,1000,1003,'synthetic',short_recording=True))
        for call in (lambda:download_frame(1,1000,1003,'synthetic'),lambda:control_frame(1,1000,1003),
                     lambda:download_frame(1,1000,1181,'synthetic',short_recording=True),
                     lambda:download_frame(1,1000,1000,'synthetic',short_recording=True),
                     lambda:download_frame(1,1000,1003,'synthetic',short_recording=1)):
            with self.assertRaises(MediaError):call()
        with self.assertRaises(run.media.SampleError):
            run.media._stream(None,None,None,None,None,None,None,None,mode='playback',short_recording=True)

    def test_lens_policy_changes_invalidate_daily_checkpoints(self):
        before=config_digest(config())
        with patch.dict(LENS_POLICY,min_score=.8):self.assertNotEqual(before,config_digest(config()))


class DailySummaryTests(unittest.TestCase):
    def test_half_open_periods_and_hour_boundaries(self):
        es=[event(t,salt=str(t)) for t in (0,21599.9,21600,39599.9,39600,53999.9,54000,86399.9)]
        data=ledger([clip(0,86400,es)])
        self.assertEqual([ds.query(data,a,b)['totals']['front'] for _,_,a,b in ds.PERIODS],[2,2,2,2])
        self.assertEqual(ds.query(data,39600,43200)['totals']['front'],1)
        self.assertTrue(ds.query(data)['full_day_complete'])
        self.assertEqual(ds.query(data)['accuracy_status'],'NOT_VERIFIED')

    def test_separate_zones_and_review_are_never_summed_as_unique_people(self):
        data=ledger([clip(events=[event(10),event(11,lane='far'),event(12,status='review'),event(13,'water_side',None)])])
        t=ds.query(data)['totals'];self.assertEqual((t['front'],t['near'],t['far'],t['front_review'],t['shop_side']),(2,1,1,1,1))
        self.assertNotIn('unique_people',t)

    def test_exact_duplicate_is_idempotent_and_conflict_fails(self):
        c=clip(events=[event(1)]);data=ledger([c,copy.deepcopy(c)])
        self.assertEqual(ds.query(data)['totals']['front'],1)
        data['clips'][1]['end']=181
        with self.assertRaises(ValidationError):ds.query(data)

    def test_overlap_uses_one_half_open_owner(self):
        data=ledger([clip(0,100,[event(99)]),clip(90,180,[event(99,salt='duplicate_view'),event(100),event(110)])])
        self.assertEqual(ds.query(data)['totals']['front'],3)

    def test_covered_requires_actual_counted_footage(self):
        with self.assertRaises(ValidationError):ds.query(ledger([clip(status='covered')]))
        self.assertTrue(ds.query(ledger([clip(0,180),clip(10,20,status='covered')]))['full_day_complete'])

    def test_partial_inventory_pending_and_unverified_never_become_full_day(self):
        for data in (ledger([clip()],False),ledger([clip(status='pending')]),ledger([dict(clip(),clock_verified=False)])):
            self.assertFalse(ds.query(data)['full_day_complete'])
        data=ledger([clip()]);data['boundary_mode']='unverified';self.assertFalse(ds.query(data)['full_day_complete'])

    def test_no_recording_gaps_are_unknown_even_after_complete_inventory(self):
        data=ledger([clip(36000,36180,[event(36001)])])
        q=ds.query(data,0,3600)
        self.assertEqual(q['data_status'],'NO_RECORDINGS')
        self.assertEqual(ds.visible(q,'front'),'—')
        self.assertIn('ไม่มีคลิปให้ยืนยัน',ds.status_text(q))
        self.assertFalse(q['complete_discovered_recordings'])
        self.assertEqual(q['gap_seconds'],3600)
        data['inventory_complete']=False
        q=ds.query(data,0,3600)
        self.assertEqual(q['data_status'],'PARTIAL_INVENTORY')
        self.assertEqual(ds.visible(q,'front'),'—')

    def test_empty_day_cannot_claim_full_day_complete(self):
        for complete in (False,True):
            q=ds.query(ledger(complete=complete))
            self.assertFalse(q['full_day_complete'])
            self.assertIsNone(q['original_day_complete'])
            self.assertEqual(ds.visible(q,'front'),'—')

    def test_union_coverage_separates_recorded_processed_pending_and_gaps(self):
        data=ledger([clip(0,100),clip(90,200,status='pending'),clip(300,400)])
        q=ds.query(data,50,350)
        self.assertEqual((q['expected_clips'],q['processed_clips'],q['unprocessed_clips']),(3,2,1))
        self.assertEqual((q['recorded_seconds'],q['processed_seconds'],q['unprocessed_recorded_seconds'],q['gap_seconds']),(200,100,100,100))
        self.assertFalse(q['full_day_complete'])
        self.assertEqual(q['original_day_coverage'],'NOT_VERIFIED')
        complete=ds.query(ledger([clip()]))
        self.assertTrue(complete['complete_discovered_recordings'])
        self.assertIsNone(complete['original_day_complete'])

    def test_csv_static_report_show_empty_hours_as_unknown_and_explicit_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            ds.write_reports(root,ledger([clip(36000,36180)]))
            rows=list(csv.DictReader((root/'summary.csv').read_text(encoding='utf-8-sig').splitlines()))
            row=next(r for r in rows if r['period']=='00:00–01:00')
            self.assertEqual((row['data_status'],row['front_auto'],row['shop_side']),('NO_RECORDINGS','—','—'))
            self.assertEqual((rows[0]['expected_clips'],rows[0]['processed_clips'],rows[0]['recorded_seconds']),('1','1','180'))
            self.assertEqual(rows[0]['original_day_coverage'],'NOT_VERIFIED')
            page=(root/'summary.html').read_text()
            self.assertIn('<td>00:00–01:00</td><td>—</td><td>—</td><td>—</td><td>ไม่มีคลิปให้ยืนยัน</td>',page)
            self.assertIn('id="coverage">คลิปที่พบ 1 · ประมวลผลแล้ว 1',page)

    def test_invalid_numbers_clock_and_config_are_rejected(self):
        for value in (True,float('nan'),float('inf'),-1,180):
            bad=event(1);bad['at']=value;data=ledger([clip(events=[bad])])
            with self.assertRaises(ValidationError):ds.query(data)
        data=ledger([clip()]);data['clips'][0]['config_sha256']='d'*64
        with self.assertRaises(ValidationError):ds.query(data)
        for args in ((1,1),(2,1),(True,100),(-1,100),(0,86401)):
            with self.assertRaises(ValidationError):ds.query(ledger(),*args)

    def test_custom_time_parsing(self):
        self.assertEqual(ds.parse_time('06:30'),23400);self.assertEqual(ds.parse_time('24:00',True),86400)
        for s in ('24:00','6:00','12:60','00:00:30','bad'):
            with self.assertRaises(ValidationError):ds.parse_time(s)

    def test_static_mobile_fallback_and_private_numeric_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            data=ledger([clip(39600,39780,[event(39601)])],False)
            ds.write_reports(root,data);page=(root/'summary.html').read_text();csv=(root/'summary.csv').read_text()
            self.assertIn('id="front">1<',page);self.assertIn('id="hours"><tr>',page)
            self.assertIn('บางส่วน',page);self.assertIn('PARTIAL_INVENTORY',csv);self.assertIn('—',csv)
            self.assertIn("connect-src 'none'",page);self.assertNotIn('input_sha256',page);self.assertNotIn('track_id',page)
            self.assertEqual((root/'summary.html').stat().st_mode&0o777,0o600)
            ds.atomic_write(root/'ledger.json',json.dumps(data));self.assertEqual(ds.read_ledger(root/'ledger.json'),data)
            bad=root/'bad.json';bad.write_text('{"schema_version":1,"schema_version":1}');bad.chmod(0o600)
            with self.assertRaises(ValidationError):ds.read_ledger(bad)

    def test_reports_refuse_symlink_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);target=root/'real';target.write_text('private')
            (root/'link').symlink_to(target)
            with self.assertRaises(ValidationError):ds.atomic_write(root/'link','new')
            self.assertEqual(target.read_text(),'private')


class InventoryTests(unittest.TestCase):
    def result(self,n=1,offset=0,channels=True):
        day,_=sd._day_bounds_utc(sd.FIXED_DATE,'+07:00')
        rows=[]
        for i in range(n):
            a=day+offset+i*180;v=dict(startTime=a,endTime=a+180,vedio_type=1)
            if channels:v['chn_times']={'1':{'event_start_time':a},'2':{'event_start_time':a}}
            rows.append({str(i):v})
        return {'playback':{'search_video_results':rows}}

    def test_source_lens_metadata_and_all_lengths_are_accounted_for(self):
        r=self.result();data=da.parse_page(r,sd.FIXED_DATE)
        self.assertEqual(data['clips'][0]['end'],180)
        del r['playback']['search_video_results'][0]['0']['chn_times']['1']
        self.assertEqual(da.parse_page(r,sd.FIXED_DATE)['clips'],[])
        with self.assertRaises(da.DayError):da.parse_page(self.result(channels=False),sd.FIXED_DATE)

    def test_midnight_straddling_recording_keeps_context_but_clips_day_ownership(self):
        page=da.parse_page(self.result(1,-100),sd.FIXED_DATE)
        self.assertEqual((page['clips'][0]['start'],page['clips'][0]['end']),(0,80))
        self.assertEqual(page['clips'][0]['capture_start'],-100)
        page=da.parse_page(self.result(1,86300),sd.FIXED_DATE)
        self.assertEqual((page['clips'][0]['end'],page['clips'][0]['capture_end']),(86400,86480))

    def test_nonfinite_or_bool_metadata_is_not_accepted(self):
        for field,value in [('startTime',True),('endTime',float('nan')),('vedio_type',False)]:
            r=self.result();r['playback']['search_video_results'][0]['0'][field]=value
            with self.assertRaises(da.DayError):da.parse_page(r,sd.FIXED_DATE)

    def test_paginated_terminal_page_and_stall_or_budget(self):
        page0=da.parse_page(self.result(20),sd.FIXED_DATE);page1=da.parse_page(self.result(1,3600),sd.FIXED_DATE)
        empty=da.parse_page(self.result(0),sd.FIXED_DATE)
        clips,_=da.collect_sweep(lambda i:[page0,page1,empty][i]);self.assertEqual(len(clips),21)
        with self.assertRaisesRegex(da.DayError,'STALLED_PAGE'):da.collect_sweep(lambda _:page0)
        with patch.object(da,'MAX_PAGES',1),self.assertRaisesRegex(da.DayError,'INCOMPLETE_INVENTORY'):
            da.collect_sweep(lambda _:page0)

    def test_short_middle_page_does_not_hide_later_full_or_late_pages(self):
        pages=[da.parse_page(self.result(n,offset),sd.FIXED_DATE)
               for n,offset in [(20,0),(18,3600),(20,7200),(6,80000),(0,0)]]
        visited=[]
        def fetch(index):visited.append(index);return pages[index]
        clips,proof=da.collect_sweep(fetch)
        self.assertEqual(visited,[0,1,2,3,4])
        self.assertEqual(len(clips),64)
        self.assertEqual(max(c['end'] for c in clips),81080)
        self.assertEqual(proof,da.collect_sweep(lambda i:pages[i])[1])

    def test_short_nonempty_pages_cannot_claim_terminal_at_page_budget(self):
        pages=[da.parse_page(self.result(18,0),sd.FIXED_DATE),
               da.parse_page(self.result(6,3600),sd.FIXED_DATE)]
        with patch.object(da,'MAX_PAGES',2),self.assertRaisesRegex(da.DayError,'INCOMPLETE_INVENTORY'):
            da.collect_sweep(lambda i:pages[i])

    def test_repeated_short_or_nonadjacent_nonempty_page_is_stalled(self):
        a=da.parse_page(self.result(18),sd.FIXED_DATE)
        b=da.parse_page(self.result(1,3600),sd.FIXED_DATE)
        for pages in ([a,a],[a,b,a]):
            with self.subTest(length=len(pages)),self.assertRaisesRegex(da.DayError,'STALLED_PAGE'):
                da.collect_sweep(lambda i:pages[i])

    def test_nonempty_pt_only_page_continues_to_later_fixed_recordings(self):
        pt=self.result(1)
        del pt['playback']['search_video_results'][0]['0']['chn_times']['1']
        pages=[da.parse_page(pt,sd.FIXED_DATE),
               da.parse_page(self.result(1,3600),sd.FIXED_DATE),
               da.parse_page(self.result(0),sd.FIXED_DATE)]
        clips,_=da.collect_sweep(lambda i:pages[i])
        self.assertEqual(len(clips),1);self.assertEqual(clips[0]['start'],3600)

    def test_readonly_page_shape_rejects_mutation_before_connection(self):
        req=sd._expected_requests('clip-day-page',sd.FIXED_DATE,7,1)
        self.assertEqual(req[0]['params']['playback']['search_video_with_utc']['start_index'],20)
        for page in (-1,200,True):
            with self.assertRaises(sd.SdError):sd._expected_requests('clip-day-page',sd.FIXED_DATE,7,page)
        bad=copy.deepcopy(req);bad[0]['params']['playback']['search_video_with_utc']['channel']=1
        with patch.object(sd,'_open_device_connection') as connect,self.assertRaises(sd.SdError):
            sd._device_request(Mock(),'token','terminal','synthetic',bad,'clip-day-page',sd.FIXED_DATE,7,page_index=1)
        connect.assert_not_called()

    def test_selected_day_getters_do_not_relax_legacy_probe_guards(self):
        date='20261014'
        req=sd._expected_requests('clip-day-page',date,7,0)
        sd._validate_requests(req,'clip-day-page',date,7,0)
        bounds=sd._day_bounds_utc(date,'+07:00')
        query=req[0]['params']['playback']['search_video_with_utc']
        self.assertEqual((query['start_time'],query['end_time']),(bounds[0],bounds[1]-1))
        for batch in ('day-metadata','day-calendar'):
            packet=sd._expected_requests(batch,date,None)
            sd._validate_requests(packet,batch,date,None)
        for invalid in ('20260230','2026-10-14','19991231',True):
            with self.assertRaises(sd.SdError):sd._expected_requests('clip-day-page',invalid,7,0)
        with self.assertRaises(sd.SdError):sd._expected_requests('clip-utc',date,7)

    def test_listing_deadline_and_fresh_transport_timeout(self):
        clock=Mock(side_effect=[0,10,10,100,100,1000]);budget=da.DayBudget(lambda:None,clock=clock)
        budget.use_request();self.assertEqual(budget.start,10)
        budget.use_request();self.assertEqual(budget.start,100)
        with self.assertRaises(da.DayError):budget.check_time()

    def test_contiguous_groups_include_overlap_but_not_real_gaps(self):
        cs=[dict(ref=ds.digest(i),start=a,end=b) for i,(a,b) in enumerate([(0,180),(170,200),(200,300),(310,400)])]
        gs=da.groups(cs);self.assertEqual([len(g['clips']) for g in gs],[3,1])

    def test_two_terminated_sweeps_must_match(self):
        def sender(budget,token,terminal,device,requests,batch,date,uid=None,page_index=None):
            budget.use_request();return (batch,page_index)
        def exercise(changed):
            sweep=[0]
            def parse(raw,methods):
                batch,page=raw
                if batch=='day-metadata':return dict(getDeviceInfo={},getTimezone={},getSdCardStatus={})
                if batch=='day-calendar':return dict(getUserID={},searchDateWithVideo={})
                if page==0:
                    sweep[0]+=1
                    return dict(searchVideoWithUTC=self.result(1,180 if changed and sweep[0]==2 else 0))
                return dict(searchVideoWithUTC=self.result(0))
            with patch.object(sd,'_device_request',side_effect=sender),patch.object(sd,'_parse_responses',side_effect=parse),patch.object(sd,'_read_device_model'),patch.object(sd,'_read_timezone_offset',return_value='+07:00'),patch.object(sd,'_read_sd_status',return_value='NORMAL'),patch.object(sd,'_read_calendar',return_value=True),patch.object(sd,'_read_user_id',return_value=7),patch.object(da.cloud,'_validate_canonical_app_server',return_value=True):
                return da.inventory('t','u',dict(model_kind='EXACT',thing_name='synthetic',app_server=None),lambda:None)
        info,_,_=exercise(False);self.assertEqual(info['requests'],6)
        with self.assertRaisesRegex(da.DayError,'UNSTABLE_INVENTORY'):exercise(True)

    def test_503_sources_survive_short_middle_pages_into_pending_ledger(self):
        pages=[];offset=0
        day,_=sd._day_bounds_utc(sd.FIXED_DATE,'+07:00')
        for n in [20,20,18]+[20]*22+[5]:
            page=self.result(n)
            for i,row in enumerate(page['playback']['search_video_results']):
                _,item=sd._single_index_entry(row);a=day+(offset+i)*160
                item.update(startTime=a,endTime=a+60,chn_times={'1':{'event_start_time':a},'2':{'event_start_time':a}})
            pages.append(page);offset+=n
        pages.append(self.result(0));visited=[]
        def sender(budget,token,terminal,device,requests,batch,date,uid=None,page_index=None):
            sd._validate_requests(requests,batch,date,uid,page_index)
            budget.use_request();return batch,page_index
        def parse(raw,methods):
            batch,index=raw
            if batch=='day-metadata':return dict(getDeviceInfo={},getTimezone={},getSdCardStatus={})
            if batch=='day-calendar':return dict(getUserID={},searchDateWithVideo={})
            visited.append(index);return dict(searchVideoWithUTC=pages[index])
        with patch.object(sd,'_device_request',side_effect=sender),patch.object(sd,'_parse_responses',side_effect=parse),patch.object(sd,'_read_device_model'),patch.object(sd,'_read_timezone_offset',return_value='+07:00'),patch.object(sd,'_read_sd_status',return_value='NORMAL'),patch.object(sd,'_read_calendar',return_value=True),patch.object(sd,'_read_user_id',return_value=7),patch.object(da.cloud,'_validate_canonical_app_server',return_value=True):
            info,_,_=da.inventory('t','u',dict(model_kind='EXACT',thing_name='synthetic',app_server=None),lambda:None)
        self.assertEqual(visited,list(range(len(pages)))*2)
        self.assertEqual(len(info['clips']),503)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            data=run.prepare_ledger(root,info,config(),sd.FIXED_DATE)
            q=ds.query(data)
            self.assertEqual((q['expected_clips'],q['processed_clips'],q['unprocessed_clips']),(503,0,503))
            self.assertFalse(q['full_day_complete'])


class ContinuousStateTests(unittest.TestCase):
    def test_crossing_spanning_two_files_and_clock_translation(self):
        for origin in (0,43118):
            stream=ObservationStream(config()['zones']);stream.reset(origin);out=[]
            for i,p in enumerate([[.55,.5],[.53,.5],[.48,.5],[.46,.5]]):
                out+=stream.update('front_shop',1,p,origin+i*.2,box(p),ds.digest('file1' if i<2 else 'file2'))
            self.assertEqual(len(out),1);self.assertEqual(out[0]['status'],'accepted');self.assertAlmostEqual(out[0]['at'],origin+.6)

    def test_true_recording_gap_resets_initial_occupancy(self):
        stream=ObservationStream(config()['zones'])
        for i,p in enumerate([[.55,.5],[.53,.5]]):stream.update('front_shop',1,p,i*.2,box(p),H)
        stream.reset(10)
        out=[]
        for i,p in enumerate([[.48,.5],[.46,.5]]):out+=stream.update('front_shop',1,p,10+i*.2,box(p),H)
        self.assertEqual(out,[])

    def test_overlap_frames_and_gap_boundary_are_explicit(self):
        c=FrameClock();c.begin(0,100,True)
        self.assertTrue(c.accept(99.8));c.begin(90,180,False)
        self.assertFalse(c.accept(99.8));self.assertFalse(c.accept(99.999));self.assertTrue(c.accept(100))
        with self.assertRaises(ValidationError):c.begin(181,200,False)
        c.begin(181,200,True);self.assertTrue(c.accept(181))

    def test_midnight_context_can_arm_a_crossing_before_zero(self):
        c=FrameClock();c.begin(-1,10,True);self.assertTrue(c.accept(-.4));self.assertTrue(c.accept(0))
        s=ObservationStream(config()['zones']);s.reset(-1);out=[]
        for t,p in [(-.4,[.55,.5]),(-.2,[.53,.5]),(0,[.48,.5]),(.2,[.46,.5])]:
            out+=s.update('front_shop',1,p,t,box(p),H)
        self.assertEqual(len(out),1);self.assertAlmostEqual(out[0]['at'],.2)

    def test_shape_switch_remains_review_across_a_file_boundary(self):
        s=ObservationStream(config()['zones']);out=[]
        for i,p in enumerate([[.55,.5],[.53,.5],[.48,.5],[.46,.5]]):
            out+=s.update('front_shop',1,p,i*.2,box(p,.4 if i<2 else .12),ds.digest(str(i//2)))
        self.assertEqual(out[0]['status'],'review');self.assertIn('box_shape_change',out[0]['review_reasons'])

    def test_worker_refuses_missing_network_sandbox_before_importing_runtime(self):
        with patch('tools.ft_day_count.socket.socket') as sock,patch('tools.ft_day_count.Engine') as engine:
            sock.return_value.bind.return_value=None
            with self.assertRaises(ValidationError):worker_main('no-root','no-config','no-model','no-ref')
            engine.assert_not_called()


def fake_checkpoint(root,message,cfg):
    import hashlib
    folder=Path(root)/'checkpoints';folder.mkdir(mode=0o700,exist_ok=True)
    data=dict(schema=1,source_ref=message['source_ref'],input_sha256=message['input_sha256'],
              runtime='f'*64,reference_sha256=run.REFERENCE_SHA256,config_sha256=config_digest(cfg),state=None)
    raw=json.dumps(data,separators=(',',':'))
    ds.atomic_write(folder/(message['source_ref']+'.json'),raw)
    return dict(source_ref=message['source_ref'],input_sha256=message['input_sha256'],
                runtime='f'*64,coverage_end=message['end'],sha256=hashlib.sha256(raw.encode()).hexdigest())


class ParentTransactionTests(unittest.TestCase):
    def setup_job(self,root):
        cfg=config();path=root/'config.json';path.write_text(json.dumps(cfg));path.chmod(0o600)
        sources=[dict(ref=ds.digest([a,b]),start=a,end=b) for a,b in [(0,10),(10,20),(30,40)]]
        info=dict(clips=sources,inventory_digest='c'*64);return cfg,path,info

    def test_run_resume_and_completed_group_idempotency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[]
            class FakeWorker:
                def __init__(self,*a):self.config_hash=config_digest(cfg);self.runtime='f'*64
                def count(self,m):
                    calls.append(m)
                    return dict(status='ok',frames=50,events=[event(m['start']+1,salt=m['source_ref'])],
                                input_sha256='b'*64,config_sha256=config_digest(cfg),clock_verified=True,lens_verified=True,
                                checkpoint=fake_checkpoint(root,m,cfg))
                def close(self):pass
            with patch.object(run,'inventory',return_value=(info,'synthetic',7)),patch.object(run.f,'_validate_input_file'),patch.object(run.f,'_file_sha256',return_value=run.REFERENCE_SHA256),patch.object(run,'download',return_value='b'*64),patch.object(run,'Worker',FakeWorker),patch.object(run,'check_space'),redirect_stdout(io.StringIO()):
                first=run.run_selected('t','u',{},lambda:None,root,path,'ref',1)
                self.assertEqual(first['status'],'PARTIAL')
                second=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
                self.assertEqual(second['status'],'SUCCESS');self.assertEqual(second['summary']['totals']['front'],3)
                self.assertEqual([m['reset'] for m in calls],[True,False,True])
                n=len(calls);third=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
                self.assertEqual(third['summary']['totals']['front'],3);self.assertEqual(len(calls),n)

    def test_checkpoint_rejects_configuration_or_inventory_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);cfg,path,info=self.setup_job(root)
            data=run.prepare_ledger(root,info,cfg,sd.FIXED_DATE);run.save(root,data)
            changed=copy.deepcopy(info);changed['inventory_digest']='d'*64
            with self.assertRaises(da.DayError):run.prepare_ledger(root,changed,cfg,sd.FIXED_DATE)
            cfg['zones'][0]['config']['deadband']=.02
            with self.assertRaises(da.DayError):run.prepare_ledger(root,info,cfg,sd.FIXED_DATE)

    def transaction_worker(self,root,cfg,calls):
        class FakeWorker:
            def __init__(self,*args):self.config_hash=config_digest(cfg);self.runtime='f'*64
            def count(self,m):
                calls.append(m)
                return dict(status='ok',frames=50,events=[event(m['start']+1,salt=m['source_ref'])],
                    input_sha256='b'*64,config_sha256=config_digest(cfg),clock_verified=True,lens_verified=True,
                    checkpoint=fake_checkpoint(root,m,cfg))
            def close(self):pass
        return FakeWorker

    def transaction_patches(self,root,cfg,info,calls):
        from contextlib import ExitStack
        stack=ExitStack()
        for target,kwargs in [('inventory',dict(return_value=(info,'synthetic',7))),
            ('download',dict(return_value='b'*64)),('check_space',{}),
            ('Worker',dict(new=self.transaction_worker(root,cfg,calls)))]:
            stack.enter_context(patch.object(run,target,**kwargs))
        stack.enter_context(patch.object(run.f,'_validate_input_file'))
        stack.enter_context(patch.object(run.f,'_file_sha256',return_value=run.REFERENCE_SHA256))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack

    def test_download_failure_reports_redacted_stage_without_committing_a_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[]
            with self.transaction_patches(root,cfg,info,calls), \
                 patch.object(run,'download',side_effect=run.media.SampleError('HTTP',503)):
                result=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
            self.assertEqual(result,dict(status='BLOCKED',reason='DAY_PROCESSING_FAILED',
                diagnostic=dict(stage='DOWNLOAD',kind='MEDIA',code='HTTP',http_status=503)))
            self.assertEqual(ds.read_ledger(root/'ledger.json')['cursor'],0)
            self.assertEqual(calls,[])

    def test_session_guard_error_reaches_the_existing_session_manager(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[]
            def expired():raise run.SessionError('EXPIRED')
            with self.transaction_patches(root,cfg,info,calls),self.assertRaises(run.SessionError) as caught:
                run.run_selected('t','u',{},expired,root,path,'ref',1000)
            self.assertEqual(caught.exception.code,'EXPIRED');self.assertEqual(calls,[])

    def test_report_failure_after_atomic_commit_keeps_the_new_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[];original=run.write_reports
            def reports(folder,data):
                if data['cursor']==1:raise OSError('simulated report interruption')
                return original(folder,data)
            with self.transaction_patches(root,cfg,info,calls):
                with patch.object(run,'write_reports',side_effect=reports):
                    result=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
                self.assertEqual(result['status'],'BLOCKED')
                committed=ds.read_ledger(root/'ledger.json')
                self.assertEqual(committed['cursor'],1)
                self.assertEqual(committed['clips'][0]['status'],'counted')
                result=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
                self.assertEqual(result['status'],'SUCCESS')
                self.assertEqual(len(calls),3)

    def test_uncommitted_snapshot_is_discarded_and_source_replayed_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[];original=run.atomic_write
            def write(path,text):
                if Path(path).name=='ledger.json' and json.loads(text)['cursor']==1:
                    raise OSError('simulated interruption before ledger replace')
                return original(path,text)
            with self.transaction_patches(root,cfg,info,calls):
                with patch.object(run,'atomic_write',side_effect=write):
                    first=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
                self.assertEqual(first['status'],'BLOCKED')
                self.assertEqual(ds.read_ledger(root/'ledger.json')['cursor'],0)
                self.assertEqual(len(list((root/'checkpoints').glob('*.json'))),1)
                final=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
                self.assertEqual(final['summary']['totals']['front'],3)
                self.assertEqual(len(calls),4)
                self.assertEqual(len(list((root/'checkpoints').glob('*.json'))),1)

    def test_missing_committed_snapshot_stops_before_another_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[]
            with self.transaction_patches(root,cfg,info,calls):
                run.run_selected('t','u',{},lambda:None,root,path,'ref',1)
                for p in (root/'checkpoints').iterdir():p.unlink()
                with patch.object(run,'download') as download:
                    result=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
                    self.assertEqual(result['reason'],'CHECKPOINT_MISMATCH');download.assert_not_called()

    def test_daytime_priority_changes_order_without_losing_night_or_group_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[]
            for c in info['clips'][1:]:c.update(start=c['start']+43200,end=c['end']+43200)
            with self.transaction_patches(root,cfg,info,calls):
                first=run.run_selected('t','u',{},lambda:None,root,path,'ref',1,daytime_first=True)
                self.assertEqual(first['status'],'PARTIAL')
                final=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000,daytime_first=True)
                self.assertEqual(final['status'],'SUCCESS')
                self.assertEqual([m['start'] for m in calls],[43210,43230,0])
                self.assertEqual([m['reset'] for m in calls],[True,True,True])
                self.assertEqual(final['summary']['totals']['front'],3)

    def test_job_lock_prevents_two_writers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            with run.job_lock(root):
                with self.assertRaises(BlockingIOError):
                    with run.job_lock(root):pass

    def test_worker_constructor_failure_closes_child(self):
        fake=Mock();fake.stdout=io.BytesIO();fake.stdin=io.BytesIO()
        with patch.object(run.subprocess,'Popen',return_value=fake),patch.object(run.selectors,'DefaultSelector'),patch.object(run.Worker,'receive',side_effect=da.DayError('WORKER_FAILED')),patch.object(run.Worker,'close') as close:
            with self.assertRaises(da.DayError):run.Worker('root','cfg','ref')
            close.assert_called_once()

    def test_worker_does_not_inherit_parent_credentials_in_environment(self):
        fake=Mock();fake.stdout=io.BytesIO();fake.stdin=io.BytesIO()
        with patch.dict(os.environ,{'TAPO_PASSWORD':'SYNTHETIC_PARENT_ONLY','OTHER_API_KEY':'SYNTHETIC_PARENT_ONLY'}), \
             patch.object(run.subprocess,'Popen',return_value=fake) as popen, \
             patch.object(run.selectors,'DefaultSelector'), \
             patch.object(run.Worker,'receive',return_value=dict(status='ready',config_sha256=H,runtime='f'*64)):
            worker=run.Worker('root','cfg','ref')
            self.assertNotIn('TAPO_PASSWORD',popen.call_args.kwargs['env'])
            self.assertNotIn('OTHER_API_KEY',popen.call_args.kwargs['env'])
            worker.close()

    def test_interrupted_atomic_temp_is_recovered_under_job_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            (root/'ledger.json').write_text('old-checkpoint');part=root/'ledger.json.part';part.write_text('incomplete');part.chmod(0o600)
            with run.job_lock(root):run.recover_parts(root)
            self.assertFalse(part.exists());self.assertEqual((root/'ledger.json').read_text(),'old-checkpoint')

    def test_download_refreshes_playback_uid_after_listing(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            def encode(args,**kwargs):
                self.assertEqual(args[args.index('-map')+1],'0:0')
                self.assertEqual(args[args.index('-c:v')+1],'copy')
                self.assertEqual(args[args.index('-bsf:v')+1],'filter_units=remove_types=6')
                Path(args[-1]).write_bytes(b'fixture');return SimpleNamespace(returncode=0)
            with patch.object(run,'check_space'),patch.object(run.media,'_private_root'),patch.object(sd,'_device_request'),patch.object(sd,'_parse_responses',return_value=dict(getUserID={},searchDateWithVideo={})),patch.object(sd,'_read_user_id',return_value=9),patch.object(sd,'_read_calendar',return_value=True),patch.object(run.media,'_negotiate',return_value=('synthetic','path','token')),patch.object(run.media,'_stream') as stream,patch.object(run.media,'_inspect',return_value=[dict(index=0,codec_name='h264')]),patch.object(run.subprocess,'run',side_effect=encode),patch.object(run.f,'_validate_input_file'),patch.object(run.f,'_file_sha256',return_value='b'*64):
                self.assertEqual(run.download('t','u','synthetic',7,dict(start=0,end=10),root,lambda:None),'b'*64)
                self.assertEqual(stream.call_args.args[3],9)

    def test_sei_removal_is_never_applied_to_hevc_or_an_unverified_lens(self):
        for videos,reason in (([dict(index=0,codec_name='hevc')],'UNSUPPORTED_SOURCE'),
                              ([dict(index=2,codec_name='h264')],'LENS_OR_CLOCK_UNVERIFIED'),
                              ([dict(index=0,codec_name='h264')]*2,'LENS_OR_CLOCK_UNVERIFIED')):
            with self.assertRaises(da.DayError) as raised:run.fixed_remux_filter(videos)
            self.assertEqual(raised.exception.code,reason)


COREML_REF='9'*64


class BackendIdentityTests(unittest.TestCase):
    def test_missing_day_ledger_cannot_adopt_or_delete_existing_offline_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();folder=root/'checkpoints';folder.mkdir(mode=0o700)
            saved=folder/('a'*64+'.json');saved.write_bytes(b'historical-state')
            with patch.object(run,'SessionManager') as manager,redirect_stdout(io.StringIO()):
                result=run.main(['--run','--root',str(root),'--date','20010101',
                    '--config','c','--reference','r','--backend','coreml','--reference-sha256',COREML_REF])
            self.assertEqual(result,2);manager.assert_not_called()
            self.assertFalse((root/'ledger.json').exists())
            self.assertEqual(saved.read_bytes(),b'historical-state')

    def test_partial_identity_and_linked_ledgers_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();cfg,path,info=self.setup_job(root)
            data=run.prepare_ledger(root,info,cfg,sd.FIXED_DATE)
            del data['count_backend'];del data['reference_sha256']
            run.save(root,data)
            with self.assertRaises(da.DayError):
                run.validate_existing_identity(root,'cpu',run.REFERENCE_SHA256)
            data=run.prepare_ledger(root/'unused',info,cfg,sd.FIXED_DATE)
            run.save(root,data);os.link(root/'ledger.json',root/'alias.json')
            with self.assertRaises(da.DayError):
                run.validate_existing_identity(root,'cpu',run.REFERENCE_SHA256)

    def test_bound_cursor_zero_runtime_mismatch_preserves_orphans_work_and_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();(root/'work').mkdir(mode=0o700);(root/'checkpoints').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[]
            data=run.prepare_ledger(root,info,cfg,sd.FIXED_DATE,'coreml',COREML_REF)
            data['count_runtime']='a'*64;run.save(root,data)
            for name in ('checkpoints/'+H+'.json','work/fixed.mp4','count-config.json','ledger.json.part'):
                ds.atomic_write(root/name,'retain-this')
            before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            wrong=self.worker_double(root,cfg,calls,runtime='b'*64,reference=COREML_REF)
            with self.patches(root,cfg,info,calls,wrong,reference=COREML_REF):
                result=run.run_selected('t','u',{},lambda:None,root,path,'ref',1,
                                        backend='coreml',expected_reference=COREML_REF)
            self.assertEqual(result['reason'],'CHECKPOINT_MISMATCH')
            self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def setup_job(self,root):
        cfg=config();path=root/'config.json';path.write_text(json.dumps(cfg));path.chmod(0o600)
        sources=[dict(ref=ds.digest([a,b]),start=a,end=b) for a,b in [(0,10),(10,20)]]
        info=dict(clips=sources,inventory_digest='c'*64);return cfg,path,info

    def worker_double(self,root,cfg,calls,runtime='f'*64,reference=run.REFERENCE_SHA256):
        class FakeWorker:
            def __init__(self,*a):self.config_hash=config_digest(cfg);self.runtime=runtime
            def count(self,m):
                calls.append(m)
                return dict(status='ok',frames=50,events=[event(m['start']+1,salt=m['source_ref'])],
                    input_sha256='b'*64,config_sha256=config_digest(cfg),clock_verified=True,lens_verified=True,
                    checkpoint=fake_checkpoint_runtime(root,m,cfg,runtime,reference))
            def close(self):pass
        return FakeWorker

    def patches(self,root,cfg,info,calls,worker,reference=run.REFERENCE_SHA256):
        from contextlib import ExitStack
        stack=ExitStack()
        for target,kwargs in [('inventory',dict(return_value=(info,'synthetic',7))),
            ('download',dict(return_value='b'*64)),('check_space',{}),('Worker',dict(new=worker))]:
            stack.enter_context(patch.object(run,target,**kwargs))
        stack.enter_context(patch.object(run.f,'_validate_input_file'))
        stack.enter_context(patch.object(run.f,'_file_sha256',return_value=reference))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack

    def test_worker_command_routes_module_and_environment_by_backend_and_opts_in_day_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            fake=Mock();fake.stdout=io.BytesIO();fake.stdin=io.BytesIO()
            with patch.object(run.subprocess,'Popen',return_value=fake) as popen, \
                 patch.object(run.selectors,'DefaultSelector'), \
                 patch.object(run.Worker,'receive',return_value=dict(status='ready',config_sha256=H,runtime='f'*64)):
                run.Worker(root,'cfg','ref').close()
                cmd=popen.call_args.args[0]
                self.assertIn(str(run.REPO/'.venv/ft-counting/bin/python'),cmd)
                self.assertIn('tools.ft_day_count',cmd);self.assertNotIn('--day-ledger',cmd)
            with patch.object(run.subprocess,'Popen',return_value=fake) as popen, \
                 patch.object(run.selectors,'DefaultSelector'), \
                 patch.object(run.Worker,'receive',return_value=dict(status='ready',config_sha256=H,runtime='f'*64)):
                run.Worker(root,'cfg','ref','coreml').close()
                cmd=popen.call_args.args[0]
                self.assertIn(str(run.REPO/'.venv/ft-accel/bin/python'),cmd)
                self.assertIn('tools.ft_day_count_accel',cmd)
                self.assertEqual(cmd[-1],'--day-ledger')

    def test_invalid_backend_or_reference_hash_is_rejected_before_any_spawn_network_or_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            with patch.object(run,'SessionManager') as manager,patch.object(run.subprocess,'Popen') as popen, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(run.main(['--run','--root',str(root),'--config','c','--reference','r',
                    '--date','20010101','--backend','coreml']),2)
                manager.assert_not_called();popen.assert_not_called()
                self.assertEqual(run.main(['--run','--root',str(root),'--config','c','--reference','r',
                    '--date','20010101','--backend','cpu','--reference-sha256','a'*64]),2)
                manager.assert_not_called();popen.assert_not_called()
            self.assertFalse((root/'ledger.json').exists())

    def test_cpu_default_ledger_binds_legacy_backend_and_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[]
            worker=self.worker_double(root,cfg,calls)
            with self.patches(root,cfg,info,calls,worker):
                run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
            data=ds.read_ledger(root/'ledger.json')
            self.assertEqual((data['count_backend'],data['reference_sha256'],data['count_runtime']),
                              ('cpu',run.REFERENCE_SHA256,'f'*64))

    def test_coreml_explicit_lineage_binds_runtime_and_reference_at_commit_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[]
            worker=self.worker_double(root,cfg,calls,runtime='a'*64,reference=COREML_REF)
            with self.patches(root,cfg,info,calls,worker,reference=COREML_REF):
                first=run.run_selected('t','u',{},lambda:None,root,path,'ref',1,
                    backend='coreml',expected_reference=COREML_REF)
                self.assertEqual(first['status'],'PARTIAL')
                second=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000,
                    backend='coreml',expected_reference=COREML_REF)
                self.assertEqual(second['status'],'SUCCESS')
            data=ds.read_ledger(root/'ledger.json')
            self.assertEqual((data['count_backend'],data['reference_sha256'],data['count_runtime']),
                              ('coreml',COREML_REF,'a'*64))

    def test_coreml_refuses_a_legacy_cpu_ledger_even_at_cursor_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);cfg,path,info=self.setup_job(root)
            legacy=run.prepare_ledger(root,info,cfg,sd.FIXED_DATE)
            for key in ('count_backend','reference_sha256','count_runtime'):del legacy[key]
            run.save(root,legacy)
            with self.assertRaises(da.DayError) as raised:
                run.prepare_ledger(root,info,cfg,sd.FIXED_DATE,backend='coreml',expected_reference=COREML_REF)
            self.assertEqual(raised.exception.code,'CHECKPOINT_MISMATCH')

    def test_backend_or_reference_or_runtime_mismatch_fails_preserving_ledger_and_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[]
            worker=self.worker_double(root,cfg,calls,runtime='a'*64,reference=COREML_REF)
            with self.patches(root,cfg,info,calls,worker,reference=COREML_REF):
                run.run_selected('t','u',{},lambda:None,root,path,'ref',1,backend='coreml',expected_reference=COREML_REF)
            committed=ds.read_ledger(root/'ledger.json')
            # Same persisted lineage, but the worker now reports a different runtime.
            mismatched=self.worker_double(root,cfg,calls,runtime='b'*64,reference=COREML_REF)
            with self.patches(root,cfg,info,calls,mismatched,reference=COREML_REF):
                result=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000,
                    backend='coreml',expected_reference=COREML_REF)
            self.assertEqual(result,dict(status='BLOCKED',reason='CHECKPOINT_MISMATCH'))
            self.assertEqual(ds.read_ledger(root/'ledger.json'),committed)
            self.assertEqual(len(list((root/'checkpoints').glob('*.json'))),1)
            # A ledger bound to one backend refuses a run requested with the other.
            with self.patches(root,cfg,info,calls,worker,reference=run.REFERENCE_SHA256):
                cpu_result=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
            self.assertEqual(cpu_result,dict(status='BLOCKED',reason='CHECKPOINT_MISMATCH'))
            self.assertEqual(ds.read_ledger(root/'ledger.json'),committed)

    def test_backend_mismatch_on_existing_root_is_rejected_before_session_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);cfg,path,info=self.setup_job(root)
            data=run.prepare_ledger(root,info,cfg,'20010101',backend='coreml',expected_reference=COREML_REF)
            run.save(root,data)
            part=root/'ledger.json.part';part.write_text('stale');part.chmod(0o600)
            with patch.object(run,'SessionManager') as manager,patch.object(run,'load_target',return_value=H), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(run.main(['--run','--root',str(root),'--config',str(path),'--reference','r',
                    '--date','20010101','--max-clips','1','--max-batches','1']),2)
            manager.assert_not_called();self.assertTrue(part.exists())

    def test_worker_startup_runtime_mismatch_closes_worker_without_touching_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            cfg,path,info=self.setup_job(root);calls=[]
            bound=self.worker_double(root,cfg,calls,runtime='a'*64)
            with self.patches(root,cfg,info,calls,bound):
                run.run_selected('t','u',{},lambda:None,root,path,'ref',1)
            self.assertEqual(len(list((root/'checkpoints').glob('*.json'))),1)
            closed=[]
            class ClosingWorker:
                def __init__(self,*a):self.config_hash=config_digest(cfg);self.runtime='b'*64
                def close(self):closed.append(True)
            with self.patches(root,cfg,info,calls,ClosingWorker):
                result=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
            self.assertEqual(result,dict(status='BLOCKED',reason='CHECKPOINT_MISMATCH'))
            self.assertEqual(closed,[True])
            self.assertEqual(ds.read_ledger(root/'ledger.json')['cursor'],1)


def fake_checkpoint_runtime(root,message,cfg,runtime,reference):
    import hashlib
    folder=Path(root)/'checkpoints';folder.mkdir(mode=0o700,exist_ok=True)
    data=dict(schema=1,source_ref=message['source_ref'],input_sha256=message['input_sha256'],
              runtime=runtime,reference_sha256=reference,
              config_sha256=config_digest(cfg),state=None)
    raw=json.dumps(data,separators=(',',':'))
    ds.atomic_write(folder/(message['source_ref']+'.json'),raw)
    return dict(source_ref=message['source_ref'],input_sha256=message['input_sha256'],
                runtime=runtime,coverage_end=message['end'],sha256=hashlib.sha256(raw.encode()).hexdigest())


class FailureDiagnosticTests(unittest.TestCase):
    def test_exception_messages_and_untrusted_attributes_never_become_diagnostics(self):
        secret='SYNTHETIC_PRIVATE_PATH_AND_PASSWORD'
        bad=run.media.SampleError('HTTP');bad.code=secret;bad.http_status=secret
        errors=[Exception(secret),ValidationError(secret),OSError(2,secret,secret),
                run.subprocess.TimeoutExpired([secret],1),bad]
        for exc in errors:
            result=run.failure_diagnostic(secret,exc)
            self.assertNotIn(secret,json.dumps(result));self.assertEqual(result['stage'],'UNKNOWN')
        self.assertEqual(run.failure_diagnostic('DOWNLOAD',bad),dict(stage='DOWNLOAD',kind='MEDIA',code='UNKNOWN'))
        bad.code=[];bad.http_status=True
        self.assertEqual(run.failure_diagnostic('DOWNLOAD',bad),dict(stage='DOWNLOAD',kind='MEDIA',code='UNKNOWN'))

    def test_sd_and_local_failure_types_are_distinct_and_bounded(self):
        result=run.failure_diagnostic('INVENTORY',sd.SdError('HTTP_ERROR',http_status=401))
        self.assertEqual(result['kind'],'SD');self.assertEqual(result['http_status'],401)
        self.assertIn(result['code'],sd.ERROR_CODES)
        self.assertEqual(run.failure_diagnostic('COMMIT',OSError(28,'private')),dict(stage='COMMIT',kind='IO',code='ERROR',errno=28))


class FiniteDriverTests(unittest.TestCase):
    def test_actual_batch_callback_forwards_backend_reference_on_each_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();calls=[]
            class Session:
                def command(self,action,target,**kwargs):
                    return dict(status='SUCCESS',callback=kwargs['on_selected_camera']('t','u',{},lambda:None))
            def batch(*args,**kwargs):
                calls.append(kwargs)
                return (dict(status='PARTIAL',reason='INVOCATION_BUDGET') if len(calls)==1
                        else dict(status='SUCCESS'))
            with patch.object(run,'SessionManager',return_value=Session()),patch.object(run,'load_target',return_value=H), \
                 patch.object(run,'check_space'),patch.object(run,'load_zones_config',return_value=config()), \
                 patch.object(run.f,'_validate_input_file'),patch.object(run.f,'_file_sha256',return_value=COREML_REF), \
                 patch.object(run,'run_selected',side_effect=batch),redirect_stdout(io.StringIO()):
                self.assertEqual(run.main(self.arguments(root,'--max-clips','1','--max-batches','2',
                    '--backend','coreml','--reference-sha256',COREML_REF)),0)
            self.assertEqual(len(calls),2)
            for call in calls:self.assertEqual((call['backend'],call['expected_reference']),('coreml',COREML_REF))

    def test_coreml_delivery_preserves_old_cpu_report_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();destination=root/'delivery'
            for name in ('summary.html','summary.csv'):ds.atomic_write(root/name,'cpu-result')
            run.deliver_reports(root,destination,'2001-01-01',False)
            for name in ('summary.html','summary.csv'):ds.atomic_write(root/name,'coreml-result')
            run.deliver_reports(root,destination,'2001-01-01',False,backend='coreml')
            self.assertEqual(len(list(destination.iterdir())),4)
            for path in destination.iterdir():
                self.assertEqual(path.read_text(),'coreml-result' if '-COREML-' in path.name else 'cpu-result')

    def arguments(self,root,*extra):
        return ['--run','--root',str(root),'--config','synthetic-config','--reference','synthetic-reference',
                '--date','20010101',*extra]

    def test_finite_batches_reuse_auth_and_stop_on_completion(self):
        reports=[dict(status='SUCCESS',callback=dict(status='PARTIAL',reason='INVOCATION_BUDGET')),
                 dict(status='SUCCESS',callback=dict(status='SUCCESS',summary=dict(full_day_complete=True)))]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            with patch.object(run,'SessionManager') as manager,patch.object(run,'load_target',return_value=H),patch.object(run,'check_space'),redirect_stdout(io.StringIO()):
                manager.return_value.command.side_effect=reports
                self.assertEqual(run.main(self.arguments(root,'--max-clips','1','--max-batches','3')),0)
                self.assertEqual(manager.return_value.command.call_count,2)
                self.assertTrue(all(c.args[0]=='use' for c in manager.return_value.command.call_args_list))
            self.assertFalse(json.loads((root/'job-status.json').read_text())['running'])

    def test_auth_or_source_errors_do_not_spin_or_prompt(self):
        for error in (dict(status='BLOCKED',reason='REAUTH_REQUIRED'),
                      dict(status='SUCCESS',callback=dict(status='BLOCKED',reason='LENS_UNVERIFIED'))):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(os.path.realpath(tmp));root.chmod(0o700)
                with patch.object(run,'SessionManager') as manager,patch.object(run,'load_target',return_value=H),patch.object(run,'check_space'),redirect_stdout(io.StringIO()):
                    manager.return_value.command.return_value=error
                    self.assertEqual(run.main(self.arguments(root,'--max-clips','1','--max-batches','3')),2)
                    self.assertEqual(manager.return_value.command.call_count,1)

    def test_terminal_status_preserves_safe_diagnostic_without_retry(self):
        detail=dict(stage='DOWNLOAD',kind='MEDIA',code='INCOMPLETE')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            with patch.object(run,'SessionManager') as manager,patch.object(run,'load_target',return_value=H), \
                 patch.object(run,'check_space'),redirect_stdout(io.StringIO()):
                manager.return_value.command.return_value=dict(status='SUCCESS',callback=dict(
                    status='BLOCKED',reason='DAY_PROCESSING_FAILED',diagnostic=detail))
                self.assertEqual(run.main(self.arguments(root,'--max-clips','1','--max-batches','3')),2)
                self.assertEqual(manager.return_value.command.call_count,1)
            status=json.loads((root/'job-status.json').read_text())
            self.assertFalse(status['running']);self.assertEqual(status['diagnostic'],detail)

    def test_media_window_product_limit_is_checked_before_session_use(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'SessionManager') as manager,redirect_stdout(io.StringIO()):
            self.assertEqual(run.main(self.arguments(Path(tmp),'--max-clips','1000','--max-batches','2')),2)
            manager.assert_not_called()

    def test_another_job_cannot_overwrite_active_status_or_clean_its_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700);(root/'work').mkdir(mode=0o700)
            status=root/'job-status.json';ds.atomic_write(status,'{"running":true,"pid":7}')
            media=root/'work/fixed.mp4';media.write_bytes(b'active-owner-work');media.chmod(0o600)
            with run.job_lock(root),redirect_stdout(io.StringIO()):
                self.assertEqual(run.main(self.arguments(root)),2)
            self.assertTrue(json.loads(status.read_text())['running'])
            self.assertEqual(media.read_bytes(),b'active-owner-work')

    def test_delivery_copies_only_numeric_reports_and_retains_partial_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            for name in ('summary.html','summary.csv'):ds.atomic_write(root/name,'numeric-example')
            ds.atomic_write(root/'ledger.json','private-provenance-not-for-delivery')
            destination=root/'delivery'
            run.deliver_reports(root,destination,'2001-01-01',False)
            self.assertEqual(sorted(p.suffix for p in destination.iterdir()),['.csv','.html'])
            self.assertTrue(all('PARTIAL' in p.name for p in destination.iterdir()))
