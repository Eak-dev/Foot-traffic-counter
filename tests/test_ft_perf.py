import copy
import math
import importlib.util
import unittest
from unittest.mock import Mock, patch

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


if __name__ == '__main__':
    unittest.main()
