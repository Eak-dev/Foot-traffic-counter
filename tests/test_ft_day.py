"""Synthetic day, boundary, inventory and resumable-parent contracts; no camera."""
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from contextlib import redirect_stdout

from tools import ft_day_summary as ds,ft_day_acquire as da,ft_day_run as run,ft_sd_probe as sd
from tools.ft_day_count import ObservationStream,FrameClock,config_digest,worker_main
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

    def test_no_recording_gaps_are_zero_only_after_complete_inventory(self):
        data=ledger([clip(36000,36180,[event(36001)])])
        self.assertEqual(ds.query(data,0,3600)['totals']['front'],0)
        self.assertFalse(ds.query(data,0,3600)['counts_are_partial'])
        data['inventory_complete']=False
        self.assertEqual(ds.visible(ds.query(data,0,3600),'front'),'—')

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
        clips,_=da.collect_sweep(lambda i:[page0,page1][i]);self.assertEqual(len(clips),21)
        with self.assertRaisesRegex(da.DayError,'STALLED_PAGE'):da.collect_sweep(lambda _:page0)
        with patch.object(da,'MAX_PAGES',1),self.assertRaisesRegex(da.DayError,'INCOMPLETE_INVENTORY'):
            da.collect_sweep(lambda _:page0)

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
                sweep[0]+=1
                return dict(searchVideoWithUTC=self.result(1,180 if changed and sweep[0]==2 else 0))
            with patch.object(sd,'_device_request',side_effect=sender),patch.object(sd,'_parse_responses',side_effect=parse),patch.object(sd,'_read_device_model'),patch.object(sd,'_read_timezone_offset',return_value='+07:00'),patch.object(sd,'_read_sd_status',return_value='NORMAL'),patch.object(sd,'_read_calendar',return_value=True),patch.object(sd,'_read_user_id',return_value=7),patch.object(da.cloud,'_validate_canonical_app_server',return_value=True):
                return da.inventory('t','u',dict(model_kind='EXACT',thing_name='synthetic',app_server=None),lambda:None)
        info,_,_=exercise(False);self.assertEqual(info['requests'],4)
        with self.assertRaisesRegex(da.DayError,'UNSTABLE_INVENTORY'):exercise(True)


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
                def __init__(self,*a):pass
                def count(self,m):
                    calls.append(m)
                    return dict(status='ok',frames=50,events=[event(m['start']+1,salt=m['source_ref'])],
                                input_sha256='b'*64,config_sha256=config_digest(cfg),clock_verified=True,lens_verified=True)
                def close(self):pass
            with patch.object(run,'inventory',return_value=(info,'synthetic',7)),patch.object(run.f,'_validate_input_file'),patch.object(run.f,'_file_sha256',return_value=run.REFERENCE_SHA256),patch.object(run,'download',return_value='b'*64),patch.object(run,'Worker',FakeWorker),patch.object(run,'check_space'),redirect_stdout(io.StringIO()):
                first=run.run_selected('t','u',{},lambda:None,root,path,'ref',1)
                self.assertEqual(first['status'],'PARTIAL')
                second=run.run_selected('t','u',{},lambda:None,root,path,'ref',1000)
                self.assertEqual(second['status'],'SUCCESS');self.assertEqual(second['summary']['totals']['front'],3)
                self.assertEqual([m['reset'] for m in calls],[True,True,False,True])
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
            def encode(args,**kwargs):Path(args[-1]).write_bytes(b'fixture');return SimpleNamespace(returncode=0)
            with patch.object(run,'check_space'),patch.object(run.media,'_private_root'),patch.object(sd,'_device_request'),patch.object(sd,'_parse_responses',return_value=dict(getUserID={},searchDateWithVideo={})),patch.object(sd,'_read_user_id',return_value=9),patch.object(sd,'_read_calendar',return_value=True),patch.object(run.media,'_negotiate',return_value=('synthetic','path','token')),patch.object(run.media,'_stream') as stream,patch.object(run.media,'_inspect',return_value=[dict(index=0)]),patch.object(run.subprocess,'run',side_effect=encode),patch.object(run.f,'_validate_input_file'),patch.object(run.f,'_file_sha256',return_value='b'*64):
                self.assertEqual(run.download('t','u','synthetic',7,dict(start=0,end=10),root,lambda:None),'b'*64)
                self.assertEqual(stream.call_args.args[3],9)
