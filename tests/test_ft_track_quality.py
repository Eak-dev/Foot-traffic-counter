"""Continuity regressions using synthetic boxes only, no media or network."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import ft_count_zones as zones
from tools.ft_count import ValidationError
from tools.ft_track_quality import TrackEvidence, VERSION, policy
from tests import test_ft_lane_counter as lane_helpers
base = lane_helpers.base


def box(p, w=.12, h=.2):
    return [p[0]-w/2,p[1]-h/2,p[0]+w/2,p[1]+h/2]


def event(tid, start, end, t):
    return dict(lane_id='near',track_id=tid,time_seconds=t,direction='forward',
                evidence={'from':start,'to':end})


class EvidenceTests(unittest.TestCase):
    def test_continuous_crossing_and_different_people_keep_evidence_separate(self):
        q=TrackEvidence()
        for i,p in enumerate([[.56,.5],[.53,.5],[.48,.5],[.46,.5]]):
            for tid in (1,2):q.observe(tid,p,i*.2,box(p))
        for tid in (1,2):
            self.assertEqual(q.assess(event(tid,[.53,.5],[.46,.5],.6))['reasons'],[])

    def test_size_switch_is_reviewed_instead_of_confirmed_as_motion(self):
        q=TrackEvidence()
        q.observe(1,[.54,.5],0,box([.54,.5],h=.4))
        q.observe(1,[.48,.5],.2,box([.48,.5],h=.12))
        q.observe(1,[.46,.5],.4,box([.46,.5],h=.12))
        self.assertIn('box_shape_change',q.assess(event(1,[.54,.5],[.46,.5],.4))['reasons'])

    def test_exact_short_time_boundary_has_float_tolerance(self):
        q=TrackEvidence()
        for t,p in [(147.599,[.55,.5]),(147.999,[.40,.5]),(148.199,[.39,.5])]:
            q.observe(1,p,t,box(p))
        self.assertGreater(147.999-147.599,.4)
        self.assertIn('center_jump',q.assess(event(1,[.55,.5],[.39,.5],148.199))['reasons'])

    def test_normal_perspective_size_change_is_not_a_discontinuity(self):
        q=TrackEvidence()
        for i,p in enumerate([[.55,.5],[.48,.5],[.46,.5]]):q.observe(1,p,i*.2,box(p,h=.2+i*.01))
        self.assertEqual(q.assess(event(1,[.55,.5],[.46,.5],.4))['reasons'],[])

    def test_missing_anchor_and_gap_stay_uncertain(self):
        q=TrackEvidence();q.observe(1,[.55,.5],0,box([.55,.5]))
        q.observe(1,[.46,.5],3,box([.46,.5]))
        self.assertIn('observation_gap',q.assess(event(1,[.55,.5],[.46,.5],3))['reasons'])
        q.observe(1,[.45,.5],7,box([.45,.5]))
        self.assertIn('missing_anchor',q.assess(event(1,[.55,.5],[.45,.5],7))['reasons'])

    def test_bad_boxes_and_clock_fail_closed(self):
        for b in (None,[.3,.3,.3,.7],[.7,.3,.3,.7],[True,.3,.7,.7],[.3,float('nan'),.7,.7],[.3,.3,1.1,.7],[.1,.1,.2,.2]):
            with self.assertRaises(ValidationError):TrackEvidence().observe(1,[.5,.5],0,b)
        q=TrackEvidence();q.observe(1,[.5,.5],1,box([.5,.5]))
        with self.assertRaises(ValidationError):q.observe(1,[.5,.5],1,box([.5,.5]))
        with self.assertRaises(ValidationError):q.assess(event(1,[.55,.5],[.46,.5],2))

    def test_history_and_track_memory_are_bounded(self):
        with patch('tools.ft_track_quality.MAX_TRACKS',3),patch('tools.ft_track_quality.HISTORY_UPDATES',4):
            q=TrackEvidence()
            for i in range(10):q.observe(i,[.5,.5],i*.1,box([.5,.5]))
            self.assertEqual(len(q.histories),3)
            for i in range(10):q.observe(9,[.5,.5],1+i*.1,box([.5,.5]))
            self.assertEqual(len(q.histories[9]),4)


class QualityReplayTests(unittest.TestCase):
    def make(self, root, distorted=False):
        z=lane_helpers.LaneIntegrationTests().make_zone();z['track_quality']=VERSION
        r=dict(status='ok',input_sha256='a'*64,model_sha256='b'*64,
               config_sha256=zones._config_sha256(z['config']),duration_seconds=1,frames_processed=4,sample_fps=5)
        rows=[]
        for i,x in enumerate([.55,.53,.48,.46]):
            p=[x,.5];h=.4 if distorted and i<2 else .12
            rows.append(dict(frame=i*3,time_seconds=i/5,tracks=[dict(track_id=1,foot=p,box=box(p,h=h))]))
        p=root/'tracks.jsonl';p.write_text(''.join(json.dumps(row)+'\n' for row in rows));p.chmod(0o600)
        return z,r,p

    def test_quality_is_opt_in_hash_bound_and_requires_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));z,r,p=self.make(root)
            old=copy.deepcopy(z);del old['track_quality']
            self.assertNotEqual(zones._zone_config_sha(z),zones._zone_config_sha(old))
            rows=[json.loads(line) for line in p.read_text().splitlines()]
            for row in rows:del row['tracks'][0]['box']
            p.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaises(ValidationError):zones.recount_lanes(z,r,p)
            self.assertEqual(zones.recount_lanes(old,r,p)['count'],1)

    def test_every_candidate_is_accepted_or_reviewed_and_page_explains_it(self):
        from tests.test_ft_count_zones import make_report
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            z,r,p=self.make(root,distorted=True);out=zones.recount_lanes(z,r,p)
            self.assertEqual((out['candidate_count'],out['count'],out['review_count']),(1,0,1))
            self.assertEqual(out['review_events'][0]['review_reasons'],['box_shape_change'])
            side=dict(id='side',name='ข้างร้าน',color='#FF35EC',config=base())
            sr=make_report(side['config']);sr.update(duration_seconds=1,frames_processed=4,sample_fps=5,count=0,events=[],direction_counts={'forward':0,'backward':0})
            merged=zones.merge_reports([z,side],[out,sr])
            self.assertEqual(merged['zones'][0]['review_count'],1)
            zones.write_zones_page(root,[z,side],[out,sr],combined=True)
            page=(root/'review.html').read_text()
            self.assertIn('รอตรวจ 1 จังหวะ',page)
            self.assertIn('ขนาดกรอบตัวคนเปลี่ยนฉับพลัน',page)
            self.assertIn('data-time="0.60"',page)
            self.assertEqual(page.count('<video '),1)
            for field,value in [('candidate_count',2),('review_count',0),('track_quality_policy',{})]:
                bad=copy.deepcopy(out);bad[field]=value
                with self.assertRaises(ValidationError):zones.merge_reports([z,side],[bad,sr])
            for field,value in [('time_seconds',float('nan')),('review_reasons',['invented']),('quality_observations',True)]:
                bad=copy.deepcopy(out);bad['review_events'][0][field]=value
                with self.assertRaises(ValidationError):zones.merge_reports([z,side],[bad,sr])

    def test_unchanged_boxes_preserve_the_actual_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            z,r,p=self.make(Path(os.path.realpath(tmp)));out=zones.recount_lanes(z,r,p)
            self.assertEqual((out['count'],out['review_count']),(1,0))
            self.assertEqual(out['lane_counts'],{'near':1,'far':0})
            self.assertEqual(out['track_quality_policy'],policy())

    def test_quality_cannot_be_applied_to_other_modes_or_unknown_versions(self):
        from tests.test_ft_count_zones import make_zones_config
        c=make_zones_config();c['zones'][0]['track_quality']=VERSION
        with self.assertRaises(ValidationError):zones.validate_zones_config(c)
        c['zones'][0]=lane_helpers.LaneIntegrationTests().make_zone();c['zones'][0]['track_quality']='unknown'
        with self.assertRaises(ValidationError):zones.validate_zones_config(c)
