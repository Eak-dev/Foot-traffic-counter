import contextlib
import copy
import io
import json
import math
import os
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import ft_count, ft_count_zones, ft_day_count
from tools import ft_perf
from tools.ft_perf import compare_events, event_totals, _decode, sample_time, _verify_network_denied


def e(at, zone='front_shop', lane='near', status='accepted'):
    return dict(at=at, zone=zone, lane=lane, status=status)


class ComparisonTests(unittest.TestCase):
    def test_shuffled_and_input_immutable(self):
        a = [e(1), e(2), e(3, 'water_side', None)]
        before = copy.deepcopy(a)
        r = compare_events(a, list(reversed(a)))
        self.assertTrue(r['compatible'])
        self.assertEqual(r['matched'], 3)
        self.assertEqual(a, before)
        self.assertEqual(r['accuracy_status'], 'NOT_VERIFIED')

    def test_duplicate_is_not_matched_twice(self):
        r = compare_events([e(1), e(1.1)], [e(1)])
        self.assertEqual((r['matched'], r['missing'], r['extra']), (1, 1, 0))
        self.assertFalse(r['compatible'])

    def test_same_totals_but_different_times_fail(self):
        r = compare_events([e(1)], [e(10)])
        self.assertEqual(r['reference'], r['candidate'])
        self.assertFalse(r['compatible'])

    def test_lane_zone_status_are_distinct(self):
        for changed in (e(1, lane='far'), e(1, status='review'), e(1, 'water_side', None)):
            r = compare_events([e(1)], [changed])
            self.assertEqual((r['missing'], r['extra']), (1, 1))

    def test_exact_tolerance_and_late_extra(self):
        r = compare_events([e(1), e(2)], [e(.6), e(2.4), e(4)])
        self.assertEqual((r['matched'], r['missing'], r['extra']), (2, 0, 1))
        self.assertEqual(r['max_time_delta'], .4)

    def test_invalid_times_and_shapes(self):
        for at in (math.nan, math.inf, -1, True, '1'):
            with self.assertRaises(ValueError):
                compare_events([e(at)], [])
        for events in (None, {}, [None], [e(1, lane=None)], [e(1, 'water_side', 'near')]):
            with self.assertRaises(ValueError):
                event_totals(events)
        for tol in (True, -1, math.nan, 3):
            with self.assertRaises(ValueError):
                compare_events([], [], tol)

    def test_empty_and_water_review_totals(self):
        self.assertTrue(compare_events([], [])['compatible'])
        self.assertEqual(event_totals([e(1, 'water_side', None, 'review')])['shop_side_review'], 1)

    def test_fractional_fps_does_not_include_rounded_endpoint(self):
        self.assertEqual(sample_time(297, 15.000111111934162, 20), 19.8)
        self.assertIsNone(sample_time(300, 15.000111111934162, 20))

    def test_worker_refuses_unrestricted_network_before_inference(self):
        sock = Mock()
        with patch('socket.socket', return_value=sock):
            with self.assertRaisesRegex(ValueError, 'sandbox not enforced'):
                _verify_network_denied()
        sock.close.assert_called_once()
        sock = Mock()
        sock.bind.side_effect = PermissionError()
        with patch('socket.socket', return_value=sock):
            _verify_network_denied()
        sock.close.assert_called_once()


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'isolated numerical runtime required')
class DecodeTests(unittest.TestCase):
    def test_640_decoder_matches_current_backend_without_mutation(self):
        import numpy as np
        from tools import ft_count
        raw = np.zeros((1, 8400, 85), dtype=np.float32)
        raw[0, 0, 4:6] = [.9, .8]
        raw[0, 7000, 4:6] = [.7, .8]
        original = raw.copy()
        boxes, scores = _decode(np, raw, .5, 640)
        expected_boxes, expected_scores = ft_count._decode_yolox(np, raw.copy(), .5)
        np.testing.assert_allclose(boxes, expected_boxes)
        np.testing.assert_allclose(scores, expected_scores)
        np.testing.assert_array_equal(raw, original)

    def test_416_contract_and_invalid_outputs(self):
        import numpy as np
        raw = np.zeros((1, 3549, 85), dtype=np.float32)
        raw[0, 0, 4:6] = [.9, .8]
        boxes, scores = _decode(np, raw, 1, 416)
        np.testing.assert_allclose(boxes, [[-4, -4, 4, 4]])
        self.assertAlmostEqual(float(scores[0]), .72, places=5)
        with self.assertRaises(ValueError):
            _decode(np, raw, 1, 640)
        raw[0, 10, 0] = np.nan
        with self.assertRaises(ValueError):
            _decode(np, raw, 1, 416)


HAVE_RUNTIME = all(importlib.util.find_spec(name) for name in ('numpy', 'cv2', 'supervision'))


@unittest.skipUnless(HAVE_RUNTIME, 'numpy/cv2/supervision required for the batch frame-hook loop')
class RunBatchDetectorHookTests(unittest.TestCase):
    """Exercises tools.ft_perf._run's per-frame batch_detector hook with a
    mocked Engine/VideoCapture; no real media, model or network access.
    """

    def setUp(self):
        import cv2
        import numpy as np
        import supervision as sv
        self.np, self.cv, self.sv = np, cv2, sv
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / 'out'
        self.updates = []
        self.events_log = []

    def _zones(self):
        return [dict(id='front', config=dict(crop=[0, 0, .5, 1], sample_fps=5, anchor='center')),
                dict(id='side', config=dict(crop=[.5, 0, 1, 1], sample_fps=5))]

    def _detections(self, n, score=.9):
        np = self.np
        boxes = np.tile(np.array([[1., 1., 5., 5.]], dtype=np.float32), (n, 1))
        return self.sv.Detections(xyxy=boxes, confidence=np.full(n, score, dtype=np.float32),
                                   class_id=np.zeros(n, dtype=int))

    def _invoke(self, cfg, batch_detector, frame_count=4, seconds=1.0, fps=5.0):
        np, cv, sv = self.np, self.cv, self.sv
        images = [np.full((20, 20, 3), i, dtype=np.uint8) for i in range(frame_count)]
        updates, events_log = self.updates, self.events_log

        class FakeCapture:
            def __init__(self):
                self.index = 0

            def get(self, prop):
                if prop == cv.CAP_PROP_FPS:
                    return fps
                if prop == cv.CAP_PROP_FRAME_COUNT:
                    return float(frame_count)
                raise AssertionError('unexpected capture property')

            def grab(self):
                ok = self.index < frame_count
                self.index += 1
                return ok

            def read(self):
                if self.index >= frame_count:
                    return False, None
                image = images[self.index]
                self.index += 1
                return True, image

            def release(self):
                pass

        class FakeTracker:
            def __init__(self, zone_id):
                self.zone_id = zone_id

            def update_with_detections(self, detections):
                n = len(detections.xyxy)
                updates.append((self.zone_id, n))
                return SimpleNamespace(xyxy=detections.xyxy, tracker_id=list(range(1, n + 1)))

        class FakeStream:
            def update(self, zid, track_id, point, t, box, source_ref):
                events_log.append((zid, track_id, t, point, box))
                return []

        class FakeEngine:
            def __init__(self, root, config, model, reference):
                self.cv, self.np, self.sv = cv, np, sv
                self.root = Path(root)
                self.config = config
                batch_size = 2 if batch_detector else 1
                self.net = SimpleNamespace(get_inputs=lambda: [SimpleNamespace(shape=[batch_size, 3, 640, 640])])
                self.input_name = 'images'
                self.runtime_digest = '0' * 64
                self.reference_sha256 = '1' * 64
                self.stream = FakeStream()
                self.trackers = {z['id']: FakeTracker(z['id']) for z in config['zones']}

            def reset(self, origin):
                pass

            def verify_lens(self, image):
                return True

            def detect(self, image, config):
                return sv.Detections.empty()

        args = SimpleNamespace(candidate='baseline', input='input.mp4', config='zones.json',
                               reference='reference.jpg', output=str(self.output), seconds=seconds)

        original_stat = Path.stat
        def model_stat(path, *args, **kwargs):
            if path.name == 'yolox_s.onnx':
                return SimpleNamespace(st_size=1)
            return original_stat(path, *args, **kwargs)

        with patch.object(ft_perf, '_verify_network_denied', return_value=None), \
                patch.object(ft_count, '_outside_repo', return_value=None), \
                patch.object(ft_count, '_validate_input_file', return_value=None), \
                patch.object(ft_count, '_file_sha256', return_value=ft_perf.MODELS['baseline'][1]), \
                patch.object(ft_count_zones, 'load_zones_config', return_value=cfg), \
                patch.object(ft_day_count, 'Engine', FakeEngine), \
                patch.object(Path, 'is_file', return_value=True), \
                patch.object(Path, 'is_symlink', return_value=False), \
                patch.object(Path, 'stat', model_stat), \
                patch.object(cv, 'VideoCapture', return_value=FakeCapture()), \
                patch.dict(sys.modules, {'onnxruntime': SimpleNamespace(
                    InferenceSession=Mock(), SessionOptions=Mock())}):
            with contextlib.redirect_stdout(io.StringIO()):
                ft_perf._run(args, batch_detector=batch_detector)
        return json.loads((self.output / 'experiment.json').read_text())

    def test_batch_detector_called_once_per_frame_before_tracker_updates(self):
        zones = self._zones()
        received = []

        def batch_detector(engine, image, zs):
            self.assertEqual(len(self.updates), 2 * len(received))
            self.assertEqual(int(image[0, 0, 0]), len(received))
            received.append([z['id'] for z in zs])
            return [self._detections(1), self._detections(2)]

        report = self._invoke(dict(zones=zones), batch_detector)

        self.assertEqual(report['frames'], 4)
        self.assertEqual(report['inference_calls'], 4)
        self.assertEqual(report['inference_images'], 8)
        self.assertEqual(report['candidate'], 'baseline')
        self.assertEqual(report['reference_sha256'], '1' * 64)
        self.assertEqual(received, [['front', 'side']] * 4)
        # Zones mapped back by cfg['zones'] order: front gets 1 box, side gets 2,
        # in that exact order, once per frame -> trackers updated in config order.
        self.assertEqual(self.updates, [('front', 1), ('side', 2)] * 4)
        self.assertEqual([event[2] for event in self.events_log],
                         [at for at in (0, .2, .4, .6) for _ in range(3)])
        for zone, _, _, point, box in self.events_log:
            self.assertEqual(point, [.15, .15 if zone == 'front' else .25])
            self.assertEqual(box, [.05, .05, .25, .25])

    def test_default_single_image_path_accounting_and_empty_updates(self):
        report = self._invoke(dict(zones=self._zones()), None)
        self.assertEqual((report['frames'], report['inference_calls'], report['inference_images']),
                         (4, 8, 8))
        self.assertEqual(self.updates, [('front', 0), ('side', 0)] * 4)

    def test_fractional_clock_and_empty_second_zone(self):
        indices = []
        def batch_detector(engine, image, zs):
            indices.append(int(image[0, 0, 0]))
            return [self._detections(1), self._detections(0)]
        report = self._invoke(dict(zones=self._zones()), batch_detector,
                              frame_count=9, seconds=.4, fps=15.000111111934162)
        self.assertEqual(indices, [0, 3])
        self.assertEqual(report['frames'], 2)
        self.assertEqual([e[2] for e in self.events_log], [0, .2])
        self.assertEqual(self.updates, [('front', 1), ('side', 0)] * 2)

    def test_reversed_zone_config_maps_results_back_by_order_not_position(self):
        zones = list(reversed(self._zones()))  # [side, front]

        def batch_detector(engine, image, zs):
            return [self._detections(1), self._detections(2)]

        self._invoke(dict(zones=zones), batch_detector)
        # First result (n=1) now belongs to "side" (zones[0]), second (n=2) to "front".
        self.assertEqual(self.updates, [('side', 1), ('front', 2)] * 4)

    def test_callback_exception_yields_zero_updates_for_that_frame(self):
        def failing_detector(engine, image, zs):
            raise RuntimeError('boom')

        with self.assertRaisesRegex(RuntimeError, 'boom'):
            self._invoke(dict(zones=self._zones()), failing_detector)
        self.assertEqual(self.updates, [])

    def test_malformed_second_result_type_yields_zero_updates_for_that_frame(self):
        def malformed_detector(engine, image, zs):
            return [self._detections(1), {'not': 'a Detections instance'}]

        with self.assertRaisesRegex(ValueError, 'must return Detections'):
            self._invoke(dict(zones=self._zones()), malformed_detector)
        self.assertEqual(self.updates, [])

    def test_nan_in_second_result_yields_zero_updates_for_that_frame(self):
        def nan_detector(engine, image, zs):
            bad = self._detections(1)
            bad.confidence[0] = self.np.nan
            return [self._detections(1), bad]

        with self.assertRaisesRegex(ValueError, 'invalid batch detections'):
            self._invoke(dict(zones=self._zones()), nan_detector)
        self.assertEqual(self.updates, [])


if __name__ == '__main__':
    unittest.main()
