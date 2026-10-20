import importlib.util
import unittest
from tools.ft_perf_compare import nanodet_decode, nanodet_input, run_worker
from unittest.mock import patch


class SandboxTests(unittest.TestCase):
    def test_unrestricted_worker_fails_before_any_model_or_path_use(self):
        with patch('tools.ft_perf_compare.ft_perf._verify_network_denied', side_effect=ValueError('sandbox')):
            with self.assertRaisesRegex(ValueError, 'sandbox'):
                run_worker(None)


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'isolated numerical runtime required')
class NanoDetTests(unittest.TestCase):
    def outputs(self):
        import numpy as np
        result = []
        for side in (52, 26, 13):
            result.extend([np.zeros((1, side**2, 80), dtype=np.float32),
                           np.zeros((1, side**2, 32), dtype=np.float32)])
        return result

    def test_output_order_independent_stable_softmax_and_person_class(self):
        import numpy as np
        values = self.outputs()
        values[0][0, 100, 0] = .75
        values[1][:] = 10000  # stable softmax, uniform eight-bin distribution.
        boxes, scores = nanodet_decode(np, list(reversed(values)))
        self.assertEqual(len(boxes), 3549)
        self.assertAlmostEqual(float(scores[100]), .75)
        # Anchor at (100%52,100//52)*8+3.5, distances mean3.5*8.
        np.testing.assert_allclose(boxes[100], [359.5, 0, 415.5, 39.5])

    def test_reject_missing_duplicate_or_nonfinite_heads(self):
        import numpy as np
        values = self.outputs()
        for bad in (values[:-1], [values[0]] * 6):
            with self.assertRaises(ValueError):
                nanodet_decode(np, bad)
        values[1][0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            nanodet_decode(np, values)

    def test_vendor_variant_keeps_all_classes_and_top1000_per_level(self):
        import numpy as np
        values = self.outputs()
        values[0][0, 2600, 7] = .9
        values[0][0, 2599, 0] = .8
        boxes, scores = nanodet_decode(np, values, person_only=False)
        self.assertEqual(boxes.shape, (1000 + 676 + 169, 4))
        self.assertEqual(scores.shape, (1000 + 676 + 169, 80))
        self.assertEqual(int(scores[0].argmax()), 7)
        self.assertAlmostEqual(float(scores[1, 0]), .8)

    @unittest.skipUnless(importlib.util.find_spec('cv2'), 'isolated OpenCV runtime required')
    def test_centered_black_letterbox_rgb_and_mean_std(self):
        import cv2
        import numpy as np
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        image[:] = [10, 20, 30]
        blob, metadata = nanodet_input(cv2, np, image)
        self.assertEqual(metadata, (104, 0, 208, 416))
        np.testing.assert_allclose(blob[0, :, 104, 0],
            (np.array([30, 20, 10]) - [103.53, 116.28, 123.675]) / [57.375, 57.12, 58.395], rtol=1e-6)
        np.testing.assert_allclose(blob[0, :, 0, 0],
            -np.array([103.53, 116.28, 123.675]) / [57.375, 57.12, 58.395], rtol=1e-6)
