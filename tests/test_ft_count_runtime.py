"""Optional dependency-contract tests; stdlib suite skips without runtime."""
import importlib.util
import unittest
import os
import tempfile

HAVE = all(importlib.util.find_spec(x) for x in ('numpy','cv2','supervision'))

@unittest.skipUnless(HAVE, 'isolated counting runtime required')
class RuntimeContracts(unittest.TestCase):
    def test_decode_and_letterbox(self):
        import numpy as np
        import cv2
        from tools import ft_count as f
        image=np.full((400,800,3),[7,23,91],dtype=np.uint8)
        canvas,scale=f._letterbox(cv2,np,image)
        self.assertEqual(canvas.shape,(640,640,3))
        self.assertEqual(canvas[0,0].tolist(),[7,23,91])
        self.assertEqual(canvas[-1,-1].tolist(),[114,114,114])
        raw=np.zeros((1,8400,85),dtype=np.float32)
        raw[0,0,4]=.9;raw[0,0,5]=.8
        boxes,scores=f._decode_yolox(np,raw,scale)
        np.testing.assert_allclose(boxes,[[-5,-5,5,5]])
        self.assertAlmostEqual(float(scores[0]),.72,places=5)

    def test_bytetrack_passage_and_stationary_negative(self):
        import numpy as np
        from tools.ft_count import CrossingCounter
        with tempfile.TemporaryDirectory() as td:
            os.environ['MPLCONFIGDIR']=td
            import supervision as sv
            tr=sv.ByteTrack(track_activation_threshold=.05,minimum_matching_threshold=.99,lost_track_buffer=90,frame_rate=5,minimum_consecutive_frames=1)
            counter=CrossingCounter([[.5,.1],[.5,.9]],deadband=.012)
            for i in range(30):
                x=.2+i*.02
                boxes=np.array([[x*1000,100,x*1000+70,350],[820,600,900,900]],dtype=float)
                tracked=tr.update_with_detections(sv.Detections(xyxy=boxes,confidence=np.array([.8,.8]),class_id=np.zeros(2,dtype=int)))
                for b,tid in zip(tracked.xyxy,tracked.tracker_id): counter.update(int(tid),(float((b[0]+b[2])/2000),float((b[1]+b[3])/2000)),i*.2)
            self.assertEqual(counter.count,1)
