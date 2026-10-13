"""Tests for tools.ft_count: pure-Python CrossingCounter core and config/file
validation. Runs under plain Python 3.9 stdlib; no third-party imports here.
"""
import os
import stat
import tempfile
import unittest

from tools import ft_count


def make_counter(deadband=0.015):
    # Horizontal line at y=0.5 spanning x in [0.2, 0.8]; ROI covers most of frame.
    line = [[0.2, 0.5], [0.8, 0.5]]
    roi = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    return ft_count.CrossingCounter(line, roi=roi, deadband=deadband)


class CrossingCounterCoreTests(unittest.TestCase):
    def test_crossing_top_to_bottom_counts(self):
        c = make_counter()
        t = 0.0
        for y in (0.2, 0.3, 0.4, 0.6, 0.7, 0.8):
            c.update("t1", (0.5, y), t)
            t += 0.2
        self.assertEqual(c.count, 1)
        self.assertEqual(c.events[0]["direction"], "forward")  # positive side

    def test_crossing_bottom_to_top_counts_opposite_direction(self):
        c = make_counter()
        t = 0.0
        for y in (0.8, 0.7, 0.6, 0.4, 0.3, 0.2):
            c.update("t1", (0.5, y), t)
            t += 0.2
        self.assertEqual(c.count, 1)
        self.assertEqual(c.events[0]["direction"], "backward")

    def test_stationary_track_never_crosses(self):
        c = make_counter()
        t = 0.0
        for _ in range(10):
            c.update("t1", (0.5, 0.5 + 0.001), t)
            t += 0.1
        self.assertEqual(c.count, 0)

    def test_jitter_near_line_does_not_cross(self):
        c = make_counter(deadband=0.02)
        t = 0.0
        # Oscillate tightly within the deadband around the line -- no genuine crossing.
        for y in (0.49, 0.505, 0.495, 0.51, 0.49, 0.5):
            c.update("t1", (0.5, y), t)
            t += 0.1
        self.assertEqual(c.count, 0)

    def test_seated_box_jitter_negative(self):
        c = make_counter()
        t = 0.0
        # A seated person: footpoint wobbles a tiny amount, always one side.
        ys = [0.3, 0.301, 0.299, 0.302, 0.298, 0.3, 0.301]
        for y in ys:
            c.update("seated1", (0.5, y), t)
            t += 0.3
        self.assertEqual(c.count, 0)

    def test_segment_endpoint_exclusion(self):
        c = make_counter()
        # Path touches exactly at the line's endpoint x but outside segment span,
        # should not be treated as crossing the finite segment.
        c.update("t1", (0.1, 0.4), 0.0)
        c.update("t1", (0.1, 0.6), 0.2)
        c.update("t1", (0.1, 0.4), 0.4)
        c.update("t1", (0.1, 0.6), 0.6)
        self.assertEqual(c.count, 0)

    def test_gap_then_new_track_id_no_false_cross(self):
        c = make_counter()
        c.update("t1", (0.5, 0.3), 0.0)
        c.update("t1", (0.5, 0.35), 0.2)
        # New, unrelated track appearing on the other side: must not count as a cross.
        c.update("t2", (0.5, 0.7), 5.0)
        self.assertEqual(c.count, 0)

    def test_large_time_gap_on_same_track_does_not_fake_cross(self):
        c = make_counter()
        c.update("t1", (0.5, 0.3), 0.0)
        c.update("t1", (0.5, 0.35), 0.2)
        # Same id reappears far later on the other side (e.g. tracker reuse after
        # occlusion) -- treated as a fresh sighting, not a genuine observed cross.
        c.update("t1", (0.5, 0.7), 30.0)
        self.assertEqual(c.count, 0)

    def test_roi_exclusion_blocks_crossing_outside_roi(self):
        line = [[0.2, 0.5], [0.8, 0.5]]
        roi = [[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]]  # left half only
        c = ft_count.CrossingCounter(line, roi=roi)
        t = 0.0
        # Crossing happens at x=0.6, within the line's span but outside the ROI.
        for y in (0.3, 0.4, 0.6, 0.7):
            c.update("t1", (0.6, y), t)
            t += 0.2
        self.assertEqual(c.count, 0)

    def test_roi_inclusion_allows_crossing_inside_roi(self):
        line = [[0.2, 0.5], [0.8, 0.5]]
        roi = [[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]]  # left half only
        c = ft_count.CrossingCounter(line, roi=roi)
        t = 0.0
        for y in (0.3, 0.4, 0.6, 0.7):
            c.update("t1", (0.3, y), t)
            t += 0.2
        self.assertEqual(c.count, 1)

    def test_same_track_reverse_cross_after_cooldown_allowed(self):
        c = make_counter()
        t = 0.0
        for y in (0.2, 0.3, 0.4, 0.6, 0.7, 0.8):
            c.update("t1", (0.5, y), t)
            t += 0.3
        self.assertEqual(c.count, 1)
        # Walk back the other way after the cooldown has elapsed: genuine re-cross.
        for y in (0.8, 0.7, 0.6, 0.4, 0.3, 0.2):
            c.update("t1", (0.5, y), t)
            t += 0.3
        self.assertEqual(c.count, 2)
        self.assertEqual(c.events[1]["direction"], "backward")

    def test_finite_validation_rejects_nan_point(self):
        c = make_counter()
        with self.assertRaises(ft_count.ValidationError):
            c.update("t1", (float("nan"), 0.5), 0.0)

    def test_finite_validation_rejects_nan_time(self):
        c = make_counter()
        with self.assertRaises(ft_count.ValidationError):
            c.update("t1", (0.5, 0.5), float("inf"))

    def test_degenerate_line_rejected(self):
        with self.assertRaises(ft_count.ValidationError):
            ft_count.CrossingCounter([[0.5, 0.5], [0.5, 0.5]])

    def test_degenerate_roi_rejected(self):
        with self.assertRaises(ft_count.ValidationError):
            ft_count.CrossingCounter(
                [[0.2, 0.5], [0.8, 0.5]], roi=[[0.1, 0.1], [0.1, 0.1], [0.1, 0.1]]
            )

    def test_bounded_track_state_evicts_old_tracks(self):
        c = make_counter()
        for i in range(ft_count.MAX_RETAINED_TRACKS + 50):
            c.update("track-%d" % i, (0.5, 0.1), float(i))
        self.assertLessEqual(len(c._tracks), ft_count.MAX_RETAINED_TRACKS)


class ConfigValidationTests(unittest.TestCase):
    def valid_config(self):
        return {
            "fixed_lens_verified": True,
            "line": [[0.2, 0.5], [0.8, 0.5]],
            "roi": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "sample_fps": 5,
            "confidence": 0.25,
            "deadband": 0.015,
        }

    def test_valid_config_passes(self):
        ft_count.validate_config(self.valid_config())

    def test_requires_fixed_lens_verified_true(self):
        cfg = self.valid_config()
        cfg["fixed_lens_verified"] = False
        with self.assertRaises(ft_count.ValidationError):
            ft_count.validate_config(cfg)

    def test_rejects_missing_fixed_lens_verified(self):
        cfg = self.valid_config()
        del cfg["fixed_lens_verified"]
        with self.assertRaises(ft_count.ValidationError):
            ft_count.validate_config(cfg)

    def test_rejects_degenerate_line(self):
        cfg = self.valid_config()
        cfg["line"] = [[0.5, 0.5], [0.5, 0.5]]
        with self.assertRaises(ft_count.ValidationError):
            ft_count.validate_config(cfg)

    def test_rejects_degenerate_roi(self):
        cfg = self.valid_config()
        cfg["roi"] = [[0.1, 0.1], [0.1, 0.1], [0.1, 0.1]]
        with self.assertRaises(ft_count.ValidationError):
            ft_count.validate_config(cfg)

    def test_rejects_out_of_range_coordinates(self):
        cfg = self.valid_config()
        cfg["line"] = [[-0.1, 0.5], [0.8, 0.5]]
        with self.assertRaises(ft_count.ValidationError):
            ft_count.validate_config(cfg)

    def test_rejects_sample_fps_above_max(self):
        cfg = self.valid_config()
        cfg["sample_fps"] = 20
        with self.assertRaises(ft_count.ValidationError):
            ft_count.validate_config(cfg)

    def test_rejects_non_finite_values(self):
        cfg = self.valid_config()
        cfg["line"] = [[float("nan"), 0.5], [0.8, 0.5]]
        with self.assertRaises(ft_count.ValidationError):
            ft_count.validate_config(cfg)

    def test_rejects_roi_with_too_few_points(self):
        cfg = self.valid_config()
        cfg["roi"] = [[0.1, 0.1], [0.2, 0.2]]
        with self.assertRaises(ft_count.ValidationError):
            ft_count.validate_config(cfg)


class FileSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_rejects_symlink_input(self):
        real = os.path.join(os.path.realpath(self.tmp.name), "real.mp4")
        with open(real, "wb") as fh:
            fh.write(b"x" * 10)
        link = os.path.join(os.path.realpath(self.tmp.name), "link.mp4")
        os.symlink(real, link)
        with self.assertRaises(ft_count.ValidationError):
            ft_count._validate_input_file(link)

    def test_rejects_oversized_input(self):
        big = os.path.join(os.path.realpath(self.tmp.name), "big.mp4")
        with open(big, "wb") as fh:
            fh.truncate(ft_count.MAX_INPUT_BYTES + 1)
        with self.assertRaises(ft_count.ValidationError):
            ft_count._validate_input_file(big)

    def test_rejects_empty_input(self):
        empty = os.path.join(os.path.realpath(self.tmp.name), "empty.mp4")
        open(empty, "wb").close()
        with self.assertRaises(ft_count.ValidationError):
            ft_count._validate_input_file(empty)

    def test_accepts_regular_owner_file(self):
        ok = os.path.join(os.path.realpath(self.tmp.name), "ok.mp4")
        with open(ok, "wb") as fh:
            fh.write(b"x" * 100)
        os.chmod(ok, 0o600)
        ft_count._validate_input_file(ok)  # must not raise

    def test_model_hash_mismatch_rejected(self):
        model = os.path.join(os.path.realpath(self.tmp.name), "model.onnx")
        with open(model, "wb") as fh:
            fh.write(b"not the real model")
        with self.assertRaises(ft_count.ValidationError):
            ft_count._validate_model_file(model)

    def test_output_dir_created_private_and_rejects_existing(self):
        out = os.path.join(os.path.realpath(self.tmp.name), "out")
        result = ft_count._prepare_output_dir(out)
        mode = stat.S_IMODE(os.stat(result).st_mode)
        self.assertEqual(mode, 0o700)
        with self.assertRaises(ft_count.ValidationError):
            ft_count._prepare_output_dir(out)

    def test_open_private_sets_0600(self):
        out = os.path.join(os.path.realpath(self.tmp.name), "artifact.bin")
        fd = ft_count._open_private(out)
        os.close(fd)
        mode = stat.S_IMODE(os.stat(out).st_mode)
        self.assertEqual(mode, 0o600)

    def test_load_config_rejects_symlink(self):
        real = os.path.join(os.path.realpath(self.tmp.name), "real.json")
        with open(real, "w", encoding="utf-8") as fh:
            fh.write("{}")
        link = os.path.join(os.path.realpath(self.tmp.name), "link.json")
        os.symlink(real, link)
        with self.assertRaises(ft_count.ValidationError):
            ft_count.load_config(link)


class StdoutSanitizationTests(unittest.TestCase):
    def test_sanitize_stdout_report_only_has_expected_keys(self):
        report = {
            "status": "ok",
            "model_sha256": "a" * 64,
            "input_sha256": "b" * 64,
            "config_sha256": "c" * 64,
            "frames_processed": 42,
            "count": 3,
            "events": [{"track_id": 1}],
            "exit_code": 0,
        }
        out = ft_count._sanitize_stdout_report(report)
        self.assertNotIn("events", out)
        self.assertEqual(out["accuracy_status"], "NOT_EVALUATED")
        self.assertEqual(out["full_day_complete"], False)
        self.assertEqual(out["count"], 3)


if __name__ == "__main__":
    unittest.main()

class RegressionTests(unittest.TestCase):
    def test_gradual_cross_through_deadband(self):
        c=make_counter()
        for i,y in enumerate([.4,.46,.49,.5,.51,.54,.57]): c.update(1,(.5,y),i*.2)
        self.assertEqual(c.count,1)
    def test_roi_reentry_does_not_bridge(self):
        c=ft_count.CrossingCounter([[.2,.5],[.8,.5]],[[.2,.2],[.8,.2],[.8,.8],[.2,.8]])
        for i,p in enumerate([(.5,.3),(.5,.35),(.9,.6),(.5,.7)]): c.update(1,p,i*.2)
        self.assertEqual(c.count,0)
    def test_private_media_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            p=os.path.join(os.path.realpath(td),'input.mp4')
            with open(p,'wb') as f: f.write(b'fake')
            os.chmod(p,0o644)
            with self.assertRaises(ft_count.ValidationError): ft_count._validate_input_file(p)

class SchemaRegressionTests(unittest.TestCase):
    def test_invalid_numeric_and_self_intersection(self):
        for band in [True,float('nan'),-.1]:
            with self.assertRaises(ft_count.ValidationError): ft_count.CrossingCounter([[0,.5],[1,.5]],deadband=band)
        with self.assertRaises(ft_count.ValidationError):
            ft_count.CrossingCounter([[0,.5],[1,.5]],[[0,0],[1,1],[0,1],[.7,0]])
    def test_same_timestamp_rejected(self):
        c=make_counter();c.update(1,(.5,.4),1)
        with self.assertRaises(ft_count.ValidationError):c.update(1,(.5,.6),1)

    def test_very_slow_cross_preserves_anchor_through_deadband(self):
        c=make_counter()
        for i in range(201):c.update(1,(.5,.4+i*.001),i*.1)
        self.assertEqual(c.count,1)
