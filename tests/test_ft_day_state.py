"""Synthetic pinned-runtime exact resume; no camera, account or real footage."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.ft_state_codec import encode_tree,decode_tree,StateError
from tools import ft_day_state as state
from tools.ft_day_count import Engine,ObservationStream,FrameClock,config_digest
from tools.ft_day_summary import digest
from tests.test_ft_day import config

RUNTIME=all(importlib.util.find_spec(name) is not None for name in ('numpy','supervision'))


def make_engine(root, cfg=None):
    import numpy as np
    import supervision as sv
    engine=object.__new__(Engine)
    engine.np=np;engine.sv=sv;engine.root=Path(root);engine.config=cfg or config()
    engine.runtime_digest='f'*64;engine.reference_sha256='d'*64
    engine.clock=FrameClock();engine.stream=ObservationStream(engine.config['zones'])
    engine.reset(100)
    return engine


def synthetic_frame(engine, index):
    """New IDs, pending crossings, short occlusion/reacquisition and removal."""
    np=engine.np;t=100+round(index*.2,3);out=[]
    if index%5==0:engine.clock.begin(100+index//5,101+index//5,index==0)
    assert engine.clock.accept(t)
    for z in engine.config['zones']:
        if z['id']=='front_shop':
            xs=[.56,.55,.54,.52,.49,.47,.46,.45,.44,.43]
            x=xs[index] if index<len(xs) else .43 if index<20 else .57
            visible=index not in (12,13,14) and not 25<=index<48
            boxes=[[x*1000-60,375,x*1000+60,625]] if visible else []
            if 8<=index<22:boxes.append([670,575,790,825])
        else:
            x=[.95,.94,.93,.91,.89,.87,.85][min(index,6)]
            boxes=[[x*1000-30,400,x*1000+30,600]] if index<23 else []
        d=engine.sv.Detections(xyxy=np.asarray(boxes,dtype=np.float32).reshape((-1,4)),
            confidence=np.full(len(boxes),.9,dtype=np.float32),class_id=np.zeros(len(boxes),dtype=int))
        tracked=engine.trackers[z['id']].update_with_detections(d)
        for i in range(len(tracked)):
            b=tracked.xyxy[i]
            box=[round(float(v/1000),4) for v in b]
            p=[round(float((b[0]+b[2])/2000),4),round(float((b[1]+b[3])/2000),4)]
            out+=engine.stream.update(z['id'],int(tracked.tracker_id[i]),p,t,box,digest(index//5))
    return out


@unittest.skipUnless(RUNTIME,'optional pinned counting runtime unavailable')
class StateRuntimeTests(unittest.TestCase):
    def test_array_and_scalar_bytes_dtype_and_mutability_are_preserved(self):
        import numpy as np
        value=[np.array([[1.,2.],[3.,4.]],dtype=np.float64),np.float32(.9)]
        restored=decode_tree(json.loads(json.dumps(encode_tree(value,np))),np)
        self.assertEqual(restored[0].tobytes(),value[0].tobytes())
        self.assertEqual(type(restored[1]),np.float32)
        restored[0][0,0]=9
        for bad in (['array','<f8',[8,8],'AAAA'],['array','<f8',[999999999],'']):
            with self.assertRaises(StateError):decode_tree(bad,np)

    def test_multiple_restarts_preserve_ids_kalman_pending_crossings_and_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            baseline=make_engine(root);expected=[]
            for index in range(60):expected+=synthetic_frame(baseline,index)
            self.assertTrue(any(e['zone']=='front_shop' for e in expected))
            self.assertTrue(any(e['zone']=='water_side' for e in expected))
            for cuts in ({5},{10,15,25,30,45,50},set(range(5,60,5))):
                engine=make_engine(root);actual=[]
                for index in range(60):
                    if index in cuts:
                        encoded=json.loads(json.dumps(state.dump_engine(engine),allow_nan=False))
                        engine=make_engine(root);state.restore_engine(engine,encoded)
                    actual+=synthetic_frame(engine,index)
                self.assertEqual(actual,expected)
                self.assertEqual(state.dump_engine(engine),state.dump_engine(baseline))

    def test_immutable_snapshot_hash_runtime_source_and_corruption_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            e=make_engine(root)
            for i in range(5):synthetic_frame(e,i)
            cp=state.write_checkpoint(e,'a'*64,'b'*64)
            fresh=make_engine(root);state.load_checkpoint(fresh,cp)
            self.assertEqual(state.dump_engine(fresh),state.dump_engine(e))
            mismatch=make_engine(root);mismatch.runtime_digest='c'*64
            with self.assertRaises(StateError):state.load_checkpoint(mismatch,cp)
            path=state.checkpoint_path(root,cp['source_ref']);path.write_text('{}')
            with self.assertRaises(StateError):state.load_checkpoint(fresh,cp)

    def test_new_track_float32_mean_survives_a_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=make_engine(tmp);synthetic_frame(e,0)
            self.assertEqual(e.trackers['front_shop'].tracked_tracks[0].mean.dtype,e.np.float32)
            fresh=make_engine(tmp);state.restore_engine(fresh,state.dump_engine(e))
            self.assertEqual(state.dump_engine(fresh),state.dump_engine(e))

    def test_fully_covered_source_can_restore_without_new_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=make_engine(tmp)
            for i in range(5):synthetic_frame(e,i)
            e.clock.begin(100,101,False)
            self.assertFalse(e.clock.accept(100.8))
            fresh=make_engine(tmp);state.restore_engine(fresh,state.dump_engine(e))
            self.assertEqual(vars(fresh.clock),vars(e.clock))

    def test_malformed_shapes_fields_counter_times_and_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=make_engine(tmp)
            for i in range(5):synthetic_frame(e,i)
            raw=decode_tree(state.dump_engine(e),e.np)
            variants=[]
            bad=copy.deepcopy(raw);bad['clock']['last']=float('nan');variants.append(bad)
            bad=copy.deepcopy(raw);bad['trackers']['front_shop']['pool'][0]['mean']=e.np.zeros(7);variants.append(bad)
            bad=copy.deepcopy(raw);bad['trackers']['front_shop']['internal']=0;variants.append(bad)
            bad=copy.deepcopy(raw);bad['counters']['front_shop']['tracks'][1]['last_time']=-1;variants.append(bad)
            for bad in variants:
                with self.assertRaises((StateError,ValueError)):
                    state.restore_engine(make_engine(tmp),encode_tree(bad,e.np))


if __name__=='__main__':unittest.main()
