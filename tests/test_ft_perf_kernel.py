"""Adversarial parity tests for the experimental ft_perf_kernel helpers.

Compares tools.ft_perf_kernel against the unchanged production
tools.ft_count._decode_yolox / _letterbox blob code. Numpy-dependent
cases are skipped under a plain stdlib interpreter.
"""
import importlib.util
import unittest

from tools import ft_count
from tools import ft_perf_kernel as fpk

HAVE_NUMPY = importlib.util.find_spec("numpy") is not None


def _n_anchors(size):
    return sum((size // s) ** 2 for s in ft_count.STRIDES)


class ConstantsTests(unittest.TestCase):
    def test_constants_match_production(self):
        self.assertEqual(fpk.INPUT_SIZE, ft_count.INPUT_SIZE)
        self.assertEqual(fpk.STRIDES, ft_count.STRIDES)
        self.assertEqual(fpk.DET_SCORE_FLOOR, ft_count.DET_SCORE_FLOOR)


@unittest.skipUnless(HAVE_NUMPY, "numpy required for kernel parity tests")
class YoloXDecoderParityTests(unittest.TestCase):
    def setUp(self):
        import numpy as np

        self.np = np
        self.n = _n_anchors(ft_count.INPUT_SIZE)
        self.decoder = fpk.YoloXDecoder(np, size=ft_count.INPUT_SIZE)

    def _raw(self):
        np = self.np
        return np.zeros((1, self.n, 85), dtype=np.float32)

    def _assert_parity(self, raw, scale, conf_floor=None):
        np = self.np
        kwargs = {} if conf_floor is None else {"conf_floor": conf_floor}
        prod_input = raw.copy()
        want_boxes, want_scores = ft_count._decode_yolox(np, prod_input, scale, **kwargs)
        got_boxes, got_scores = self.decoder.decode(raw, scale, **kwargs)
        np.testing.assert_array_equal(got_boxes, want_boxes)
        np.testing.assert_array_equal(got_scores, want_scores)
        self.assertEqual(got_boxes.dtype, np.float32)
        self.assertEqual(got_scores.dtype, np.float32)
        self.assertEqual(got_boxes.shape, (want_scores.shape[0], 4))
        return got_boxes, got_scores

    def test_no_detections(self):
        raw = self._raw()
        boxes, scores = self._assert_parity(raw, 1.0)
        self.assertEqual(boxes.shape, (0, 4))
        self.assertEqual(scores.shape, (0,))

    def test_sparse_detections_across_stride_groups(self):
        np = self.np
        raw = self._raw()
        # One anchor in each of the three stride groups (8/16/32 -> 6400,1600,400).
        rows = [0, 3, 6399, 6400, 7999, 8000, 8399]
        for i, r in enumerate(rows):
            raw[0, r, 0] = 0.1 * i
            raw[0, r, 1] = -0.2 * i
            raw[0, r, 2] = 0.05 * i
            raw[0, r, 3] = -0.05 * i
            raw[0, r, 4] = 0.9
            raw[0, r, 5] = 0.9
        self._assert_parity(raw, 0.5)

    def test_all_detections_above_floor(self):
        np = self.np
        raw = self._raw()
        raw[0, :, 4] = 0.95
        raw[0, :, 5] = 0.95
        rng = np.random.RandomState(1234)
        raw[0, :, 0:4] = rng.uniform(-1.0, 1.0, size=(self.n, 4)).astype(np.float32)
        self._assert_parity(raw, 1.375)

    def test_threshold_edge_score_kept_at_exact_floor(self):
        raw = self._raw()
        # obj * person = 0.5 * 0.2 = 0.1 == DET_SCORE_FLOOR, must be kept (>=).
        raw[0, 42, 4] = 0.5
        raw[0, 42, 5] = 0.2
        boxes, scores = self._assert_parity(raw, 1.0)
        self.assertEqual(scores.shape, (1,))

    def test_threshold_edge_score_just_below_floor_dropped(self):
        raw = self._raw()
        raw[0, 42, 4] = 0.5
        raw[0, 42, 5] = 0.199999
        boxes, scores = self._assert_parity(raw, 1.0)
        self.assertEqual(scores.shape, (0,))

    def test_kept_row_order_matches_original_index_order(self):
        raw = self._raw()
        for r in (7000, 10, 123):
            raw[0, r, 4] = 0.8
            raw[0, r, 5] = 0.8
        boxes, scores = self._assert_parity(raw, 2.0)
        self.assertEqual(scores.shape, (3,))

    def test_random_mixed_detections_many_rows(self):
        np = self.np
        rng = np.random.RandomState(99)
        raw = self._raw()
        raw[0, :, 4] = rng.uniform(0.0, 1.0, size=self.n).astype(np.float32)
        raw[0, :, 5] = rng.uniform(0.0, 1.0, size=self.n).astype(np.float32)
        raw[0, :, 0:4] = rng.uniform(-2.0, 2.0, size=(self.n, 4)).astype(np.float32)
        self._assert_parity(raw, 0.731, conf_floor=0.1)

    def test_custom_conf_floor(self):
        raw = self._raw()
        # 0.5 * 0.5 = 0.25, below the 0.3 floor: dropped.
        raw[0, 5, 4] = 0.5
        raw[0, 5, 5] = 0.5
        # 0.6 * 0.6 = 0.36, above the 0.3 floor: kept.
        raw[0, 9, 4] = 0.6
        raw[0, 9, 5] = 0.6
        boxes, scores = self._assert_parity(raw, 1.0, conf_floor=0.3)
        self.assertEqual(scores.shape, (1,))

    def test_decoder_does_not_mutate_input(self):
        raw = self._raw()
        raw[0, 1, 4] = 0.9
        raw[0, 1, 5] = 0.9
        before = raw.copy()
        self.decoder.decode(raw, 1.0)
        self.np.testing.assert_array_equal(raw, before)

    def test_production_decode_mutates_its_input_unlike_kernel(self):
        # Documents the API difference: production mutates preds in place
        # because preds = output[0] is a view, not a copy.
        np = self.np
        raw = self._raw()
        raw[0, 2, 4] = 0.9
        raw[0, 2, 5] = 0.9
        before = raw.copy()
        ft_count._decode_yolox(np, raw, 1.0)
        self.assertFalse(np.array_equal(raw, before))

    def test_repeated_use_reuses_cached_anchor_arrays(self):
        grids_id = id(self.decoder._grids)
        strides_id = id(self.decoder._expanded_strides)
        raw = self._raw()
        raw[0, 0, 4] = 0.9
        raw[0, 0, 5] = 0.9
        for _ in range(3):
            self._assert_parity(raw, 1.0)
        self.assertEqual(id(self.decoder._grids), grids_id)
        self.assertEqual(id(self.decoder._expanded_strides), strides_id)

    def test_invalid_scale_rejected(self):
        raw = self._raw()
        for bad_scale in (0, -1.0, float("nan"), float("inf"), "1.0", None, True):
            with self.assertRaises(fpk.KernelValidationError):
                self.decoder.decode(raw, bad_scale)

    def test_invalid_conf_floor_rejected(self):
        raw = self._raw()
        for bad in (float("nan"), float("inf"), "0.1", None):
            with self.assertRaises(fpk.KernelValidationError):
                self.decoder.decode(raw, 1.0, conf_floor=bad)

    def test_invalid_shape_rejected(self):
        np = self.np
        with self.assertRaises(fpk.KernelValidationError):
            self.decoder.decode(np.zeros((self.n, 85), dtype=np.float32), 1.0)
        with self.assertRaises(fpk.KernelValidationError):
            self.decoder.decode(np.zeros((1, self.n, 84), dtype=np.float32), 1.0)
        with self.assertRaises(fpk.KernelValidationError):
            self.decoder.decode(np.zeros((1, self.n - 1, 85), dtype=np.float32), 1.0)

    def test_invalid_dtype_rejected(self):
        np = self.np
        with self.assertRaises(fpk.KernelValidationError):
            self.decoder.decode(np.zeros((1, self.n, 85), dtype=np.float64), 1.0)

    def test_nonfinite_input_rejected(self):
        np = self.np
        raw = self._raw()
        raw[0, 0, 0] = float("nan")
        with self.assertRaises(fpk.KernelValidationError):
            self.decoder.decode(raw, 1.0)
        raw2 = self._raw()
        raw2[0, 0, 4] = float("inf")
        with self.assertRaises(fpk.KernelValidationError):
            self.decoder.decode(raw2, 1.0)

    def test_coordinate_overflow_raises_instead_of_corrupting(self):
        np = self.np
        raw = self._raw()
        raw[0, 0, 4] = 1.0
        raw[0, 0, 5] = 1.0
        raw[0, 0, 2] = np.float32(np.finfo(np.float32).max)  # exp(.) overflows
        raw[0, 0, 3] = 0.0
        with self.assertRaises(fpk.KernelValidationError):
            self.decoder.decode(raw, 1.0)

    def test_non_ndarray_output_rejected(self):
        with self.assertRaises(fpk.KernelValidationError):
            self.decoder.decode([[0.0] * 85], 1.0)

    def test_score_overflow_rejected(self):
        np = self.np
        raw = self._raw()
        big = np.float32(np.finfo(np.float32).max)
        raw[0, 0, 4] = big
        raw[0, 0, 5] = big  # finite inputs, but obj * person_cls overflows.
        with self.assertRaises(fpk.KernelValidationError):
            self.decoder.decode(raw, 1.0)


@unittest.skipUnless(HAVE_NUMPY, "numpy required for decoder size validation tests")
class YoloXDecoderSizeValidationTests(unittest.TestCase):
    def setUp(self):
        import numpy as np

        self.np = np

    def test_valid_custom_size_accepted(self):
        decoder = fpk.YoloXDecoder(self.np, size=320)
        self.assertEqual(decoder.size, 320)

    def test_invalid_size_rejected(self):
        np = self.np
        for bad_size in (0, -32, 33, 31, 4128, True, False, 1.0, "640", None):
            with self.assertRaises(fpk.KernelValidationError):
                fpk.YoloXDecoder(np, size=bad_size)


@unittest.skipUnless(HAVE_NUMPY, "numpy required for blob parity tests")
class ContiguousBlobParityTests(unittest.TestCase):
    def setUp(self):
        import numpy as np

        self.np = np

    def _assert_parity(self, canvas):
        np = self.np
        want = canvas.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)
        got = fpk.contiguous_blob(np, canvas)
        np.testing.assert_array_equal(got, want)
        self.assertEqual(got.dtype, np.float32)
        self.assertEqual(got.shape, (1, 3, canvas.shape[0], canvas.shape[1]))
        self.assertTrue(got.flags["C_CONTIGUOUS"])
        return got

    def test_square_letterboxed_canvas(self):
        np = self.np
        canvas = np.full((640, 640, 3), 114, dtype=np.uint8)
        canvas[:300, :500] = np.arange(300 * 500 * 3, dtype=np.uint8).reshape(300, 500, 3)
        self._assert_parity(canvas)

    def test_odd_dimensions_canvas(self):
        np = self.np
        rng = np.random.RandomState(7)
        canvas = rng.randint(0, 256, size=(401, 777, 3)).astype(np.uint8)
        self._assert_parity(canvas)

    def test_does_not_mutate_canvas(self):
        np = self.np
        canvas = np.full((11, 13, 3), 42, dtype=np.uint8)
        before = canvas.copy()
        fpk.contiguous_blob(np, canvas)
        np.testing.assert_array_equal(canvas, before)

    def test_invalid_dtype_rejected(self):
        np = self.np
        canvas = np.zeros((4, 4, 3), dtype=np.float32)
        with self.assertRaises(fpk.KernelValidationError):
            fpk.contiguous_blob(np, canvas)

    def test_invalid_ndim_rejected(self):
        np = self.np
        canvas = np.zeros((4, 4), dtype=np.uint8)
        with self.assertRaises(fpk.KernelValidationError):
            fpk.contiguous_blob(np, canvas)

    def test_invalid_channel_count_rejected(self):
        np = self.np
        canvas = np.zeros((4, 4, 4), dtype=np.uint8)
        with self.assertRaises(fpk.KernelValidationError):
            fpk.contiguous_blob(np, canvas)

    def test_non_ndarray_rejected(self):
        with self.assertRaises(fpk.KernelValidationError):
            fpk.contiguous_blob(self.np, [[1, 2, 3]])

    def test_zero_height_or_width_rejected(self):
        np = self.np
        with self.assertRaises(fpk.KernelValidationError):
            fpk.contiguous_blob(np, np.zeros((0, 4, 3), dtype=np.uint8))
        with self.assertRaises(fpk.KernelValidationError):
            fpk.contiguous_blob(np, np.zeros((4, 0, 3), dtype=np.uint8))

    def test_noncontiguous_canvas_parity(self):
        np = self.np
        rng = np.random.RandomState(3)
        base = rng.randint(0, 256, size=(20, 30, 6)).astype(np.uint8)
        # Slice out every other channel group: a non-contiguous HWC view.
        canvas = base[:, :, ::2]
        self.assertFalse(canvas.flags["C_CONTIGUOUS"])
        self._assert_parity(canvas)

    def test_result_is_always_c_contiguous_even_when_input_is_not(self):
        np = self.np
        rng = np.random.RandomState(4)
        base = rng.randint(0, 256, size=(10, 10, 6)).astype(np.uint8)
        canvas = base[:, :, ::2]
        got = fpk.contiguous_blob(np, canvas)
        self.assertTrue(got.flags["C_CONTIGUOUS"])


if __name__ == "__main__":
    unittest.main()
