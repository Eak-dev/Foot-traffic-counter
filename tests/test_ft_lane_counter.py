"""Synthetic two-lane motion and integration regressions; no media/network."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from tools import ft_count, ft_count_zones
from tools.ft_lane_counter import LaneCrossingCounter, validate_lanes


def lanes():
    roi=[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]
    return [dict(id='near',name='ใกล้',color='#1261FF',roi=roi,line=[[.5,.2],[.5,.8]]),
            dict(id='far',name='ไกล',color='#19ED34',roi=roi,line=[[.5,.2],[.5,.8]])]


def base():
    return dict(fixed_lens_verified=True,roi=lanes()[0]['roi'],line=lanes()[0]['line'],sample_fps=5,confidence=.05,deadband=.008,crop=[0,0,1,1],anchor='center')


class LaneMotionTests(unittest.TestCase):
    def test_right_to_left_and_overlap_counts_one_passage(self):
        c=LaneCrossingCounter(lanes(),.008)
        for i,x in enumerate([.56,.55,.52,.49,.47]):c.update(1,[x,.5],i*.2)
        self.assertEqual(c.count,1);self.assertEqual(c.lane_counts,{'near':1,'far':0})
        self.assertEqual(c.events[0]['direction'],'forward')

    def test_fresh_short_track_before_gate_is_not_lost(self):
        # Recorded-pattern regression: first seen just outside the deadband,
        # then two opposite observations. No private coordinates/identifiers.
        c=LaneCrossingCounter(lanes(),.008)
        for i,p in enumerate([[.509,.55],[.489,.51],[.481,.50]]):c.update(1,p,i*.2)
        self.assertEqual(c.count,1);self.assertEqual(c.events[0]['time_seconds'],.4)
        self.assertEqual(c.events[0]['evidence']['to'],[.481,.50])

    def test_slow_cross_uses_confirmed_displacement(self):
        c=LaneCrossingCounter(lanes(),.008)
        for i,x in enumerate([.509,.499,.491,.478]):c.update(1,[x,.5],i*.2)
        self.assertEqual(c.count,1)

    def test_seated_jitter_and_initial_presence_do_not_count(self):
        c=LaneCrossingCounter(lanes(),.008)
        for i,x in enumerate([.500,.502,.495,.503]*4):c.update(1,[x,.5],i*.2)
        for i in range(15):c.update(2,[.65,.6],i*.2)
        self.assertEqual(c.count,0)

    def test_single_opposite_glitch_is_not_a_crossing(self):
        c=LaneCrossingCounter(lanes(),.008)
        for i,x in enumerate([.55,.54,.47,.54,.53]):c.update(1,[x,.5],i*.2)
        self.assertEqual(c.count,0)

    def test_abrupt_step_and_gap_cannot_join_a_crossing(self):
        for points in [[(.7,0),(.69,.2),(.3,.4),(.29,.6)],[(.55,0),(.54,.2),(.46,3),(.45,3.2)]]:
            c=LaneCrossingCounter(lanes(),.008)
            for x,t in points:c.update(1,[x,.5],t)
            self.assertEqual(c.count,0)

    def test_finite_gate_bypass_does_not_count(self):
        c=LaneCrossingCounter(lanes(),.008)
        for i,x in enumerate([.56,.54,.51,.48,.46]):c.update(1,[x,.85],i*.2)
        self.assertEqual(c.count,0)

    def test_two_simultaneous_tracks_are_not_deduplicated(self):
        c=LaneCrossingCounter(lanes(),.008)
        for i,x in enumerate([.55,.53,.48,.46]):
            for tid,y in [(1,.4),(2,.6)]:c.update(tid,[x,y],i*.2)
        self.assertEqual(c.count,2)

    def test_roi_exit_does_not_clear_passage_cooldown(self):
        c=LaneCrossingCounter(lanes(),.008)
        for t,p in [(0,[.55,.5]),(.2,[.53,.5]),(.4,[.48,.5]),(.6,[.46,.5]),(.8,[.05,.5]),(1,[.45,.5]),(1.2,[.52,.5]),(1.4,[.54,.5])]:c.update(1,p,t)
        self.assertEqual(c.count,1)
        for t,x in [(3,.53),(3.2,.47),(3.4,.45)]:c.update(1,[x,.5],t)
        self.assertEqual(c.count,2)

    def test_oblique_gate_and_far_lane(self):
        ls=lanes();ls[0]['roi']=[[.1,.1],[.4,.1],[.4,.9],[.1,.9]];ls[0]['line']=[[.25,.2],[.25,.8]]
        ls[1]['line']=[[.5,.2],[.7,.8]]
        c=LaneCrossingCounter(ls,.008)
        for i,x in enumerate([.67,.65,.62,.58,.55]):c.update(1,[x,.5],i*.2)
        self.assertEqual(c.lane_counts,{'near':0,'far':1})

    def test_invalid_clock_point_and_bool(self):
        for tid,p,t in [(True,[.5,.5],0),(1,[float('nan'),.5],0),(1,[.5,.5],True),(1,[1.1,.5],0)]:
            with self.assertRaises(ft_count.ValidationError):LaneCrossingCounter(lanes()).update(tid,p,t)
        c=LaneCrossingCounter(lanes());c.update(1,[.5,.5],1)
        with self.assertRaises(ft_count.ValidationError):c.update(1,[.5,.5],.5)

    def test_track_memory_is_bounded(self):
        from unittest.mock import patch
        with patch('tools.ft_lane_counter.MAX_RETAINED_TRACKS',4):
            c=LaneCrossingCounter(lanes())
            for tid in range(10):c.update(tid,[.55,.5],tid*.1)
            self.assertLessEqual(len(c._tracks),4)


class LaneConfigTests(unittest.TestCase):
    def test_valid_config_and_crop_bound(self):
        validate_lanes(lanes(),base())
        cfg=base();cfg['crop']=[.2,.2,.8,.8]
        with self.assertRaises(ft_count.ValidationError):validate_lanes(lanes(),cfg)

    def test_unknown_bad_color_and_duplicate_ids(self):
        for mutation in ['unknown','color','duplicate','nan']:
            ls=lanes()
            if mutation=='unknown':ls[0]['unexpected']=1
            if mutation=='color':ls[0]['color']='#12'
            if mutation=='duplicate':ls[1]['id']=ls[0]['id']
            if mutation=='nan':ls[0]['line'][0][0]=float('nan')
            with self.assertRaises(ft_count.ValidationError):validate_lanes(ls,base())

    def test_thin_concave_notch_cannot_be_skipped_by_gate_sampling(self):
        ls=lanes();ls[0]['roi']=[[.1,.1],[.9,.1],[.9,.9],[.5002,.9],[.5002,.4],[.5,.4],[.5,.9],[.1,.9]]
        ls[0]['line']=[[.2,.5],[.8,.5]]
        with self.assertRaises(ft_count.ValidationError):validate_lanes(ls,base())


class LaneIntegrationTests(unittest.TestCase):
    def make_zone(self):
        return dict(id='front_shop',name='หน้าร้าน',color='#20BFFF',config=base(),lanes=lanes(),counter_mode='lanes')

    def test_hash_binds_lane_gate_and_counter_mode(self):
        z=self.make_zone();h=ft_count_zones._zone_config_sha(z)
        z['lanes'][1]['line'][0][0]=.51
        self.assertNotEqual(h,ft_count_zones._zone_config_sha(z))
        self.assertNotEqual(h,ft_count_zones._config_sha256(z['config']))

    def test_replay_report_lane_counts_and_corrupt_clock(self):
        z=self.make_zone();r=dict(config_sha256=ft_count_zones._config_sha256(z['config']),duration_seconds=1,frames_processed=4,sample_fps=5)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(os.path.realpath(tmp))/'tracks.jsonl'
            rows=[dict(frame=i*3,time_seconds=i/5,tracks=[dict(track_id=1,foot=[x,.5])]) for i,x in enumerate([.55,.53,.48,.46])]
            p.write_text(''.join(json.dumps(row)+'\n' for row in rows));p.chmod(0o600)
            out=ft_count_zones.recount_lanes(z,r,p)
            self.assertEqual(out['count'],1);self.assertEqual(out['lane_counts'],{'near':1,'far':0})
            rows[2]['time_seconds']=.3;p.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaises(ft_count.ValidationError):ft_count_zones.recount_lanes(z,r,p)

    def test_merge_rejects_forged_subtotals_and_legacy_still_works(self):
        from tests.test_ft_count_zones import make_zones_config,make_report
        zs=make_zones_config()['zones'];zs[0]=self.make_zone()
        rs=[make_report(z['config']) for z in zs]
        rs[0].update(counter_mode='lanes',config_sha256=ft_count_zones._zone_config_sha(zs[0]),lane_counts={'near':2,'far':0})
        for e in rs[0]['events']:e['lane_id']='near'
        merged=ft_count_zones.merge_reports(zs,rs)
        self.assertEqual(merged['zones'][0]['lane_counts']['near'],2)
        rs[0]['lane_counts']['far']=1
        with self.assertRaises(ft_count.ValidationError):ft_count_zones.merge_reports(zs,rs)

class LanePresentationTests(unittest.TestCase):
    def test_page_and_pipeline_use_shared_lane_report(self):
        from unittest.mock import patch
        from tests.test_ft_count_zones import make_report
        z=LaneIntegrationTests().make_zone()
        other=dict(id='side',name='ข้างร้าน',color='#FF35EC',config=base())
        r=make_report(z['config']);r.update(duration_seconds=1,frames_processed=4,sample_fps=5)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            rows=[dict(frame=i*3,time_seconds=i/5,tracks=[dict(track_id=1,foot=[x,.5])]) for i,x in enumerate([.55,.53,.48,.46])]
            (root/'tracks.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows));(root/'tracks.jsonl').chmod(0o600)
            (root/'report.json').write_text(json.dumps(r))
            (root/'review.html').write_text('old diagnostic')
            (root/'annotated.mp4').write_bytes(b'synthetic')
            with patch.object(ft_count,'_run_pipeline',return_value={'count':0}):
                loaded=ft_count_zones._run_zone(z,'synthetic','synthetic',root,100)
            self.assertEqual(loaded['count'],1)
            self.assertFalse((root/'annotated.mp4').exists())
            self.assertFalse((root/'review.html').exists())
            other_report=make_report(other['config'])
            ft_count_zones.write_zones_page(root,[z,other],[loaded,other_report],combined=True)
            page=(root/'review.html').read_text()
            self.assertIn('ใกล้: 1',page);self.assertIn('ไกล: 0',page)
            self.assertEqual(page.count('<video '),1)

    def test_lanes_cannot_be_silently_ignored_in_legacy_mode(self):
        from tests.test_ft_count_zones import make_zones_config
        cfg=make_zones_config();cfg['zones'][0]['lanes']=lanes()
        with self.assertRaises(ft_count.ValidationError):ft_count_zones.validate_zones_config(cfg)

if __name__=='__main__':unittest.main()
