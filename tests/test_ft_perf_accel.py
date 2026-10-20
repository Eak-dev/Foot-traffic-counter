"""Control-boundary and exact detector parity for opt-in acceleration."""
import importlib.util
import contextlib
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import ft_perf_accel as accel


class AccelControlTests(unittest.TestCase):
    def test_worker_denies_before_any_path_or_model_read(self):
        with patch.object(accel.ft_perf, "_verify_network_denied", side_effect=ValueError("denied")):
            with self.assertRaisesRegex(ValueError, "denied"):
                accel.run_worker(SimpleNamespace())

    def test_worker_rejects_batch2_video_before_model_access(self):
        with patch.object(accel.ft_perf, "_verify_network_denied", return_value=None):
            with self.assertRaisesRegex(ValueError, "synthetic-only"):
                accel.run_worker(SimpleNamespace(batch_size=2, synthetic=False))

    def test_cache_publication_is_complete_and_never_overwrites_corruption(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, sha = accel.publish_derived(b"synthetic-model", root)
            self.assertEqual(path.read_bytes(), b"synthetic-model")
            self.assertEqual(len(sha), 64)
            self.assertEqual(accel.publish_derived(b"synthetic-model", root)[0], path)
            path.write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "cache mismatch"):
                accel.publish_derived(b"synthetic-model", root)
            self.assertEqual(path.read_bytes(), b"corrupted")
            self.assertFalse(list(root.glob("*.tmp")))

    def test_failed_publication_cleans_temporary_file(self):
        with TemporaryDirectory() as tmp, patch.object(accel.os, "link", side_effect=OSError("test")):
            with self.assertRaises(OSError):
                accel.publish_derived(b"synthetic-model", Path(tmp))
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_changed_source_cannot_receive_success_identity(self):
        with patch.object(accel, "identity", return_value=({"sources": {"module": "changed"}}, "unused")):
            with self.assertRaisesRegex(ValueError, "source changed"):
                accel.enrich({}, SimpleNamespace(kernel="cached", source_snapshot={}), {},
                             accel.time.monotonic(), accel.resource.getrusage(accel.resource.RUSAGE_SELF), ())

    def test_openvino_requires_process_local_opt_out_before_import(self):
        with patch.dict(os.environ, {"CI": "false"}):
            with self.assertRaisesRegex(ValueError, "telemetry"):
                accel.OpenVinoSession("not-a-model", 4)

    def test_latency_empty_and_percentiles(self):
        self.assertEqual(accel.latency_summary([]), dict(calls=0, seconds=0.0))
        result = accel.latency_summary([.003, .001, .002])
        self.assertEqual(result["calls"], 3)
        self.assertEqual(result["p50_ms"], 2)
        self.assertEqual(result["p95_ms"], 3)
        self.assertEqual(result["first_ms"], 3)
        self.assertEqual(result["subsequent_mean_ms"], 1.5)
        for value in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                accel.latency_summary([value])

    def test_stage_quota_and_separate_zone_measurement(self):
        stages = accel.Stages()
        stages.add("front", "model", .2)
        stages.add("side", "prepare", .01)
        self.assertEqual(stages.report()["front"]["model"]["calls"], 1)
        self.assertAlmostEqual(stages.total(), .21)
        for _ in range(1999):
            stages.add("front", "model", .1)
        with self.assertRaises(ValueError):
            stages.add("front", "model", .1)

    def test_identity_changes_with_kernel_or_backend_options(self):
        first, d1 = accel.identity({"name": "ort", "threads": 4}, "legacy")
        self.assertEqual(d1, accel.digest_json(first))
        self.assertNotEqual(d1, accel.identity({"name": "ort", "threads": 2}, "legacy")[1])
        self.assertNotEqual(d1, accel.identity({"name": "ort", "threads": 4}, "cached")[1])
        self.assertIn("ft_perf_kernel.py", first["sources"])

    def test_synthetic_rejects_private_media_arguments(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            accel.main(["--backend", "ort", "--synthetic", "--output", "unused", "--input", "private"])

    def test_video_requires_all_paths(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            accel.main(["--backend", "ort", "--output", "unused"])

    def test_parent_uses_deny_network_and_bounded_timeout(self):
        with patch.object(accel.sys, "platform", "darwin"), \
                patch.object(Path, "is_file", return_value=True), \
                patch.object(accel.subprocess, "call", return_value=0) as child:
            self.assertEqual(accel.main(["--backend", "ort", "--synthetic", "--output", "unused"]), 0)
        command = child.call_args.args[0]
        self.assertEqual(command[0], "/usr/bin/sandbox-exec")
        self.assertIn("(deny network*)", command[2])
        self.assertEqual(command[-1], "--worker")
        self.assertEqual(child.call_args.kwargs["timeout"], 600)

    def test_equal_totals_do_not_hide_review_reason_changes_or_duplicates(self):
        event = dict(zone="front_shop", lane="near", status="review", at=1.2,
                     review_reasons=["too_short"])
        changed = dict(event, review_reasons=["low_confidence"])
        self.assertFalse(accel.compare_exact_events([event], [changed])["compatible"])
        self.assertFalse(accel.compare_exact_events([event, event], [event])["compatible"])
        self.assertTrue(accel.compare_exact_events([event], [dict(event)])["compatible"])
        with self.assertRaises(ValueError):
            accel.compare_exact_events([event], [dict(event, review_reasons="unexpected")])


HAVE_RUNTIME = all(importlib.util.find_spec(name) for name in ("numpy", "cv2", "supervision"))


@unittest.skipUnless(HAVE_RUNTIME, "numpy/cv2/supervision required for detector parity")
class DetectorParityTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        import cv2
        import supervision as sv
        self.np, self.cv, self.sv = np, cv2, sv

    def test_profiled_legacy_and_cached_match_original_nms_and_crop(self):
        from tools.ft_day_count import Engine
        np = self.np
        rng = np.random.RandomState(701)
        image = rng.randint(0, 256, (419, 733, 3)).astype(np.uint8)
        raw = np.zeros((1, 8400, 85), dtype=np.float32)
        # Overlapping/threshold-edge boxes plus all three stride groups.
        for row, x, score in ((10, .1, .8), (11, -.9, .7), (6399, .1, .1),
                              (6402, .4, .9), (8100, -.2, .15)):
            raw[0, row, :4] = [x, .2, 2, 2]
            raw[0, row, 4:6] = [1, score]
        engine = SimpleNamespace(cv=self.cv, np=np, sv=self.sv, input_name="images")
        blobs = []
        def infer(names, feed):
            blobs.append(feed["images"].copy())
            return [raw.copy()]
        engine.net = SimpleNamespace(run=infer)
        for cfg in ({}, {"crop": [.13, .17, .91, .88]}):
            expected = Engine.detect(engine, image, cfg)
            for kernel in accel.KERNELS:
                stages = accel.Stages()
                actual = accel.measured_detect(engine, image, cfg, kernel,
                                               accel.YoloXDecoder(np), stages, "front")
                np.testing.assert_array_equal(expected.xyxy, actual.xyxy)
                np.testing.assert_array_equal(expected.confidence, actual.confidence)
                np.testing.assert_array_equal(expected.class_id, actual.class_id)
                np.testing.assert_array_equal(blobs[-1], blobs[-2])
                self.assertEqual(set(stages.report()["front"]), set(accel.STAGES))

    def test_openvino_adapter_requests_owned_output(self):
        np = self.np
        session = object.__new__(accel.OpenVinoSession)
        session.name, session.output = "images", "output"
        internal = np.zeros((1, 8400, 85), dtype=np.float32)
        def infer(feeds, *, share_inputs, share_outputs):
            self.assertTrue(share_inputs)
            self.assertFalse(share_outputs)
            return {"output": internal.copy()}
        session.request = SimpleNamespace(infer=infer)
        blob = np.zeros((1, 3, 640, 640), dtype=np.float32)
        first = session.run(None, {"images": blob})[0]
        first.fill(42)
        self.assertFalse(session.run(None, {"images": blob})[0].any())
        with self.assertRaises(ValueError):
            session.run(None, {"wrong": blob})
        with self.assertRaises(ValueError):
            session.run(None, {"images": blob.astype(np.float64)})

    def test_projection_adapter_preserves_all_used_columns_and_owns_output(self):
        np = self.np
        raw = np.arange(8400 * 6, dtype=np.float32).reshape(1, 8400, 6)
        inner = SimpleNamespace(run=lambda *a: [raw], get_inputs=lambda: ["input"])
        adapter = accel.PersonOutputSession(inner)
        self.assertEqual(adapter.get_inputs(), ["input"])
        restored = adapter.run(None, {})[0]
        np.testing.assert_array_equal(restored[:, :, :6], raw)
        self.assertFalse(restored[:, :, 6:].any())
        restored.fill(-1)
        self.assertEqual(float(raw[0, 0, 0]), 0)


if __name__ == "__main__":
    unittest.main()
