"""Control-boundary and two-zone cache tests for the opt-in CoreML worker.

No actual media/model/camera access; the heavy Engine.__init__ path (cv2/
numpy/onnxruntime/supervision/CoreML) is never exercised here. Real-media
paired validation is PO's responsibility after the frozen benchmark ends.
"""
import hashlib
import importlib.util
import json
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import ft_day_count_accel as accel
from tools import ft_day_count
from tools.ft_count import ValidationError


class FakeDetections(SimpleNamespace):
    pass


def make_engine(zone_configs=None):
    engine = object.__new__(accel.AcceleratedEngine)
    cfg_a, cfg_b = zone_configs or ({"crop": [0, 0, 1, 1]}, {"crop": [.5, 0, 1, 1]})
    engine._zones = [dict(id="front", config=cfg_a), dict(id="side", config=cfg_b)]
    engine._zone_configs = (cfg_a, cfg_b)
    engine._decoder = Mock()
    engine._stages = Mock()
    engine._pending = None
    engine.sv = SimpleNamespace(Detections=FakeDetections)
    return engine


class AcceleratedDigestTests(unittest.TestCase):
    def test_canonical_digest_changes_with_any_component(self):
        base = accel._canonical_digest("cpu", {"a": 1}, "ref" * 16, "wrap" * 16)
        self.assertEqual(len(base), 64)
        self.assertNotEqual(base, accel._canonical_digest("other-cpu", {"a": 1}, "ref" * 16, "wrap" * 16))
        self.assertNotEqual(base, accel._canonical_digest("cpu", {"a": 2}, "ref" * 16, "wrap" * 16))
        self.assertNotEqual(base, accel._canonical_digest("cpu", {"a": 1}, "f" * 64, "wrap" * 16))
        self.assertNotEqual(base, accel._canonical_digest("cpu", {"a": 1}, "ref" * 16, "other" * 16))

    def test_wrapper_source_hash_matches_actual_file(self):
        expected = hashlib.sha256(Path(accel.__file__).read_bytes()).hexdigest()
        self.assertEqual(accel._wrapper_source_sha256(), expected)

    def test_constructor_binds_derivation_options_and_copies_metadata(self):
        def initialize(engine, root, config, model, reference):
            engine.runtime_digest = "cpu-baseline"
            engine.reference_sha256 = "r" * 64
            engine.np = Mock()

        backend = {"name": "coreml", "options": {"MLComputeUnits": "CPUAndGPU"},
                   "derivation": {"derived_sha256": "a" * 64}}
        session = Mock()
        session.get_inputs.return_value = [SimpleNamespace(name="images")]
        config = {"zones": [{"id": "front", "config": {}}, {"id": "side", "config": {}}]}
        with patch.object(accel.CPUEngine, "__init__", autospec=True, side_effect=initialize), \
                patch.object(accel, "create_session", return_value=(session, backend)), \
                patch.object(accel, "YoloXDecoder"):
            first = accel.AcceleratedEngine("r", config, "m", "ref", "cache")
            first_digest = first.runtime_digest
            backend["derivation"]["derived_sha256"] = "b" * 64
            second = accel.AcceleratedEngine("r", config, "m", "ref", "cache")
            backend["options"]["MLComputeUnits"] = "CPUOnly"
            third = accel.AcceleratedEngine("r", config, "m", "ref", "cache")
        self.assertNotEqual(first_digest, second.runtime_digest)
        self.assertNotEqual(second.runtime_digest, third.runtime_digest)
        self.assertEqual(first._identity_baseline["backend"]["derivation"]["derived_sha256"], "a" * 64)
        self.assertEqual(first._backend_info["options"]["MLComputeUnits"], "CPUAndGPU")

    def test_nonfive_sample_rate_rejected_before_acceleration_session(self):
        config = {"zones": [{"id": "front", "config": {"sample_fps": 2}},
                            {"id": "side", "config": {"sample_fps": 2}}]}
        with patch.object(accel.CPUEngine, "__init__", return_value=None), \
                patch.object(accel, "create_session") as session:
            with self.assertRaisesRegex(ValidationError, "5 fps"):
                accel.AcceleratedEngine("r", config, "m", "ref", "cache")
        session.assert_not_called()


class PrivateCacheDirTests(unittest.TestCase):
    def test_creates_private_mode_directory(self):
        with TemporaryDirectory() as tmp:
            cache = accel._private_cache_dir(tmp)
            self.assertTrue(cache.is_dir())
            self.assertEqual(stat.S_IMODE(cache.stat().st_mode), 0o700)
            self.assertEqual(accel._private_cache_dir(tmp), cache)

    def test_rejects_symlinked_cache_path(self):
        with TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            real.mkdir()
            link = Path(tmp) / "coreml-cache"
            link.symlink_to(real)
            with self.assertRaisesRegex(ValidationError, "symlink"):
                accel._private_cache_dir(tmp)


class OfflineLineageTests(unittest.TestCase):
    def test_fresh_and_empty_checkpoint_root_are_allowed(self):
        with TemporaryDirectory() as tmp:
            accel._require_offline_lineage(tmp, None)
            (Path(tmp) / "checkpoints").mkdir(mode=0o700)
            accel._require_offline_lineage(tmp, None)

    def test_nonempty_checkpoint_root_requires_explicit_resume(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp) / "checkpoints"
            folder.mkdir(mode=0o700)
            saved = folder / "existing.json"
            saved.write_text("must remain untouched")
            with self.assertRaisesRegex(ValidationError, "explicit resume"):
                accel._require_offline_lineage(tmp, None)
            self.assertEqual(saved.read_text(), "must remain untouched")
            # {} is an explicit descriptor and is left to strict load_checkpoint.
            accel._require_offline_lineage(tmp, {})

    def test_day_ledger_presence_rejected_even_with_resume(self):
        with TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.json"
            ledger.write_text("must not be opened")
            with self.assertRaisesRegex(ValidationError, "day ledger"):
                accel._require_offline_lineage(tmp, {"source_ref": "a" * 64})

    def test_broken_ledger_symlink_is_rejected(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "ledger.json").symlink_to(Path(tmp) / "missing")
            with self.assertRaisesRegex(ValidationError, "day ledger"):
                accel._require_offline_lineage(tmp, None)

    def test_checkpoint_symlink_is_not_followed(self):
        with TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            real.mkdir(mode=0o700)
            (Path(tmp) / "checkpoints").symlink_to(real)
            with self.assertRaisesRegex(ValidationError, "private checkpoint"):
                accel._require_offline_lineage(tmp, None)


class WorkerBindingTests(unittest.TestCase):
    def test_binds_accelerated_engine_during_call_and_restores_after_success(self):
        original = ft_day_count.Engine
        seen = {}

        def fake_worker_main(root, config, model, reference, resume=None):
            seen["engine"] = ft_day_count.Engine
            return 0

        with patch.object(ft_day_count, "worker_main", side_effect=fake_worker_main):
            result = accel.worker_main("root", "config", "model", "reference")
        self.assertEqual(result, 0)
        self.assertIsNot(seen["engine"], original)
        self.assertIs(ft_day_count.Engine, original)

    def test_restores_binding_even_if_worker_main_raises(self):
        original = ft_day_count.Engine
        with patch.object(ft_day_count, "worker_main", side_effect=ValueError("boom")):
            with self.assertRaisesRegex(ValueError, "boom"):
                accel.worker_main("root", "config", "model", "reference")
        self.assertIs(ft_day_count.Engine, original)

    def test_bound_engine_builds_private_cache_from_validated_root(self):
        captured = {}

        def fake_worker_main(root, config, model, reference, resume=None):
            with patch.object(accel, "AcceleratedEngine") as fake_engine:
                ft_day_count.Engine(root, config, model, reference)
                captured["args"] = fake_engine.call_args
            return 0

        with patch.object(ft_day_count, "worker_main", side_effect=fake_worker_main), \
                patch.object(accel, "_private_cache_dir", return_value=Path("cache-dir")) as cache_dir:
            accel.worker_main("private-root", "config", "model", "reference")
        cache_dir.assert_called_once_with("private-root")
        self.assertEqual(captured["args"].args, ("private-root", "config", "model", "reference", Path("cache-dir")))


HAVE_NUMPY = importlib.util.find_spec("numpy") is not None


@unittest.skipUnless(HAVE_NUMPY, "numpy required for detection array validation")
class TwoZoneCacheTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.np = np

    def make_detections(self, count=1):
        np = self.np
        return FakeDetections(xyxy=np.zeros((count, 4), dtype=np.float32),
                               confidence=np.full((count,), .5, dtype=np.float32),
                               class_id=np.zeros((count,), dtype=np.int64 if count else np.int64))

    def test_first_zone_call_validates_both_and_caches_second_before_returning_first(self):
        engine = make_engine()
        engine.np = self.np
        first, second = self.make_detections(1), self.make_detections(2)
        image = self.np.zeros((4, 4, 3), dtype=self.np.uint8)
        with patch.object(accel, "measured_batch_detect", return_value=[first, second]) as batch:
            result = accel.AcceleratedEngine.detect(engine, image, engine._zone_configs[0])
        batch.assert_called_once_with(engine, image, engine._zones, "cached", engine._decoder, engine._stages)
        self.assertIs(result, first)
        self.assertEqual(engine._pending, (image, engine._zone_configs[1], second))

    def test_second_zone_call_consumes_matching_pending_and_clears(self):
        engine = make_engine()
        engine.np = self.np
        image = self.np.zeros((2, 2, 3), dtype=self.np.uint8)
        cached = self.make_detections(3)
        engine._pending = (image, engine._zone_configs[1], cached)
        result = accel.AcceleratedEngine.detect(engine, image, engine._zone_configs[1])
        self.assertIs(result, cached)
        self.assertIsNone(engine._pending)

    def test_second_zone_call_without_pending_is_rejected(self):
        engine = make_engine()
        engine.np = self.np
        image = self.np.zeros((2, 2, 3), dtype=self.np.uint8)
        with self.assertRaisesRegex(ValidationError, "without a pending"):
            accel.AcceleratedEngine.detect(engine, image, engine._zone_configs[1])

    def test_repeated_first_zone_call_without_consuming_pending_is_rejected(self):
        engine = make_engine()
        engine.np = self.np
        image = self.np.zeros((2, 2, 3), dtype=self.np.uint8)
        engine._pending = (image, engine._zone_configs[1], self.make_detections(1))
        with patch.object(accel, "measured_batch_detect") as batch:
            with self.assertRaisesRegex(ValidationError, "not consumed"):
                accel.AcceleratedEngine.detect(engine, image, engine._zone_configs[0])
            batch.assert_not_called()

    def test_second_call_with_different_image_object_is_rejected_and_clears_pending(self):
        engine = make_engine()
        engine.np = self.np
        pending_image = self.np.zeros((2, 2, 3), dtype=self.np.uint8)
        other_image = self.np.zeros((2, 2, 3), dtype=self.np.uint8)
        engine._pending = (pending_image, engine._zone_configs[1], self.make_detections(1))
        with self.assertRaisesRegex(ValidationError, "does not match"):
            accel.AcceleratedEngine.detect(engine, other_image, engine._zone_configs[1])
        self.assertIsNone(engine._pending)

    def test_second_call_with_wrong_config_object_is_rejected(self):
        engine = make_engine()
        engine.np = self.np
        image = self.np.zeros((2, 2, 3), dtype=self.np.uint8)
        engine._pending = (image, engine._zone_configs[1], self.make_detections(1))
        with self.assertRaisesRegex(ValidationError, "unknown zone config"):
            accel.AcceleratedEngine.detect(engine, image, {"crop": [0, 0, 1, 1]})
        self.assertIsNone(engine._pending)

    def test_invalid_second_detection_is_rejected_before_caching(self):
        engine = make_engine()
        engine.np = self.np
        image = self.np.zeros((2, 2, 3), dtype=self.np.uint8)
        bad = self.make_detections(1)
        bad.confidence[0] = 1.5
        with patch.object(accel, "measured_batch_detect", return_value=[self.make_detections(1), bad]):
            with self.assertRaisesRegex(ValidationError, "out of range"):
                accel.AcceleratedEngine.detect(engine, image, engine._zone_configs[0])
        self.assertIsNone(engine._pending)

    def test_forged_result_with_valid_arrays_is_not_accepted(self):
        engine = make_engine()
        engine.np = self.np
        valid = self.make_detections()
        forged = SimpleNamespace(**vars(valid))
        with patch.object(accel, "measured_batch_detect", return_value=[valid, forged]):
            with self.assertRaisesRegex(ValidationError, "result type"):
                engine.detect(self.np.zeros((2, 2, 3), dtype=self.np.uint8), engine._zone_configs[0])
        self.assertIsNone(engine._pending)

    def test_invalid_first_detection_is_rejected_before_caching(self):
        engine = make_engine()
        engine.np = self.np
        image = self.np.zeros((2, 2, 3), dtype=self.np.uint8)
        bad = self.make_detections(1)
        bad.class_id[0] = 2
        with patch.object(accel, "measured_batch_detect", return_value=[bad, self.make_detections(1)]):
            with self.assertRaisesRegex(ValidationError, "unexpected non-person class"):
                accel.AcceleratedEngine.detect(engine, image, engine._zone_configs[0])
        self.assertIsNone(engine._pending)

    def test_empty_detections_are_valid(self):
        engine = make_engine()
        engine.np = self.np
        image = self.np.zeros((2, 2, 3), dtype=self.np.uint8)
        empty_a, empty_b = self.make_detections(0), self.make_detections(0)
        with patch.object(accel, "measured_batch_detect", return_value=[empty_a, empty_b]):
            result = accel.AcceleratedEngine.detect(engine, image, engine._zone_configs[0])
        self.assertIs(result, empty_a)
        second = accel.AcceleratedEngine.detect(engine, image, engine._zone_configs[1])
        self.assertIs(second, empty_b)
        self.assertIsNone(engine._pending)

    def test_reset_clears_pending_cache(self):
        engine = make_engine()
        engine.np = self.np
        image = self.np.zeros((2, 2, 3), dtype=self.np.uint8)
        engine._pending = (image, engine._zone_configs[1], self.make_detections(1))
        with patch.object(accel.CPUEngine, "reset", autospec=True) as base_reset:
            accel.AcceleratedEngine.reset(engine, 0)
        base_reset.assert_called_once_with(engine, 0)
        self.assertIsNone(engine._pending)


class ProcessIdentityRecheckTests(unittest.TestCase):
    def setUp(self):
        self.cpu_patch = patch.object(accel, "cpu_runtime_digest", return_value="cpu-baseline")
        self.cpu_digest = self.cpu_patch.start()
        self.addCleanup(self.cpu_patch.stop)

    def make_engine_with_identity(self):
        engine = make_engine()
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        engine.root = Path(folder.name)
        engine._backend_info = {"name": "coreml", "derivation": {"derived_sha256": "a" * 64}}
        engine._identity_baseline, _ = accel.identity(engine._backend_info, "cached")
        engine._identity_baseline = json.loads(json.dumps(engine._identity_baseline))
        engine._cpu_runtime_digest = "cpu-baseline"
        engine._wrapper_sha256 = accel._wrapper_source_sha256()
        return engine

    def test_rejects_start_with_nonempty_pending_cache(self):
        engine = self.make_engine_with_identity()
        engine._pending = ("stale",)
        with patch.object(accel.CPUEngine, "process", autospec=True) as base_process:
            with self.assertRaisesRegex(ValidationError, "before processing"):
                accel.AcceleratedEngine.process(engine, {"source_ref": "a" * 64})
            base_process.assert_not_called()

    def test_rejects_changed_identity_before_calling_base_process(self):
        engine = self.make_engine_with_identity()
        with patch.object(accel, "identity", return_value=({"changed": True}, "x")) as changed_identity, \
                patch.object(accel.CPUEngine, "process", autospec=True) as base_process:
            with self.assertRaisesRegex(ValidationError, "identity or source changed"):
                accel.AcceleratedEngine.process(engine, {"source_ref": "a" * 64})
            base_process.assert_not_called()
        changed_identity.assert_called_once()

    def test_rejects_changed_identity_detected_after_success_before_returning(self):
        engine = self.make_engine_with_identity()
        baseline = engine._identity_baseline
        responses = iter([(baseline, "x"), ({"changed": True}, "y")])
        with patch.object(accel, "identity", side_effect=lambda *a: next(responses)), \
                patch.object(accel.CPUEngine, "process", autospec=True, return_value={"status": "ok"}) as base_process:
            with self.assertRaisesRegex(ValidationError, "identity or source changed"):
                accel.AcceleratedEngine.process(engine, {"source_ref": "a" * 64})
        base_process.assert_called_once_with(engine, {"source_ref": "a" * 64})

    def test_failure_clears_pending_cache_and_never_returns_success(self):
        engine = self.make_engine_with_identity()
        engine._pending = None
        with patch.object(accel.CPUEngine, "process", autospec=True, side_effect=ValueError("decode failed")):
            with self.assertRaisesRegex(ValueError, "decode failed"):
                accel.AcceleratedEngine.process(engine, {"source_ref": "a" * 64})
        self.assertIsNone(engine._pending)

    def test_rejects_nonempty_pending_cache_left_after_base_process_success(self):
        engine = self.make_engine_with_identity()

        def leaves_pending(self_engine, message):
            self_engine._pending = ("leftover",)
            return {"status": "ok"}

        with patch.object(accel.CPUEngine, "process", autospec=True, side_effect=leaves_pending):
            with self.assertRaisesRegex(ValidationError, "after processing"):
                accel.AcceleratedEngine.process(engine, {"source_ref": "a" * 64})

    def test_success_returns_base_result_with_cache_empty(self):
        engine = self.make_engine_with_identity()
        with patch.object(accel.CPUEngine, "process", autospec=True, return_value={"status": "ok", "frames": 1}) as base_process:
            result = accel.AcceleratedEngine.process(engine, {"source_ref": "a" * 64})
        base_process.assert_called_once_with(engine, {"source_ref": "a" * 64})
        self.assertEqual(result, {"status": "ok", "frames": 1})
        self.assertIsNone(engine._pending)

    def test_backend_mutation_is_rejected_before_processing(self):
        engine = self.make_engine_with_identity()
        engine._backend_info["derivation"]["derived_sha256"] = "b" * 64
        with patch.object(accel.CPUEngine, "process", autospec=True) as process:
            with self.assertRaisesRegex(ValidationError, "identity or source changed"):
                engine.process({"source_ref": "a" * 64})
        process.assert_not_called()

    def test_cpu_runtime_change_before_clip_rejects_without_processing(self):
        engine = self.make_engine_with_identity()
        self.cpu_digest.return_value = "changed"
        with patch.object(accel.CPUEngine, "process", autospec=True) as process:
            with self.assertRaisesRegex(ValidationError, "base counting runtime changed"):
                engine.process({"source_ref": "a" * 64})
        process.assert_not_called()

    def test_cpu_runtime_change_after_clip_never_returns_success(self):
        engine = self.make_engine_with_identity()
        self.cpu_digest.side_effect = ["cpu-baseline", "changed"]
        with patch.object(accel.CPUEngine, "process", autospec=True, return_value={"status": "ok"}):
            with self.assertRaisesRegex(ValidationError, "base counting runtime changed"):
                engine.process({"source_ref": "a" * 64})

    def test_timing_quota_does_not_accumulate_across_clips(self):
        engine = self.make_engine_with_identity()

        def one_clip(engine, message):
            for _ in range(900):
                engine._stages.add("shared", "model", .01)
            return {"status": "ok", "frames": 900}

        with patch.object(accel.CPUEngine, "process", autospec=True, side_effect=one_clip):
            for _ in range(3):
                self.assertEqual(engine.process({"source_ref": "a" * 64})["frames"], 900)
        self.assertEqual(len(engine._stages.values[("shared", "model")]), 900)

    def test_preexisting_source_is_rejected_without_advancing_state(self):
        engine = self.make_engine_with_identity()
        folder = engine.root / "checkpoints"
        folder.mkdir(mode=0o700)
        saved = folder / ("a" * 64 + ".json")
        saved.write_bytes(b"retained checkpoint")
        with patch.object(accel.CPUEngine, "process", autospec=True) as process:
            with self.assertRaisesRegex(ValidationError, "checkpoint already exists"):
                engine.process({"source_ref": "a" * 64})
        process.assert_not_called()
        self.assertEqual(saved.read_bytes(), b"retained checkpoint")

    def test_same_process_cannot_reuse_committed_source(self):
        engine = self.make_engine_with_identity()
        message = {"source_ref": "a" * 64}
        with patch.object(accel.CPUEngine, "process", autospec=True, return_value={"status": "ok"}) as process:
            self.assertEqual(engine.process(message), {"status": "ok"})
            folder = engine.root / "checkpoints"
            folder.mkdir(mode=0o700)
            saved = folder / ("a" * 64 + ".json")
            saved.write_bytes(b"first commit")
            with self.assertRaisesRegex(ValidationError, "checkpoint already exists"):
                engine.process(message)
            process.assert_called_once_with(engine, message)
        self.assertEqual(saved.read_bytes(), b"first commit")

    def test_source_ref_is_validated_before_path_lookup(self):
        engine = self.make_engine_with_identity()
        with patch.object(accel.os.path, "lexists") as lookup, \
                patch.object(accel.CPUEngine, "process", autospec=True) as process:
            for message in ({}, {"source_ref": "../escape"}, {"source_ref": "A" * 64}, None):
                with self.assertRaisesRegex(ValidationError, "invalid source digest"):
                    engine.process(message)
        lookup.assert_not_called()
        process.assert_not_called()


class CliTests(unittest.TestCase):
    def test_worker_opt_in_is_required(self):
        with patch.object(accel, "worker_main") as worker, patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                accel.main(["--root", "r", "--config", "c", "--model", "m", "--reference", "ref"])
        worker.assert_not_called()

    def test_parses_same_required_flags_as_cpu_worker_and_forwards_resume(self):
        with patch.object(accel, "worker_main", return_value=0) as worker:
            code = accel.main(["--worker", "--root", "r", "--config", "c", "--model", "m",
                               "--reference", "ref", "--resume-json", json.dumps({"a": 1})])
        self.assertEqual(code, 0)
        worker.assert_called_once_with("r", "c", "m", "ref", {"a": 1})

    def test_missing_required_flag_exits_nonzero_before_worker_main(self):
        with patch.object(accel, "worker_main") as worker, patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                accel.main(["--root", "r", "--config", "c", "--model", "m"])
        worker.assert_not_called()

    def test_checkpoint_mismatch_reports_dedicated_enum(self):
        with patch.object(accel, "worker_main", side_effect=accel.StateError("bad")), \
                patch("builtins.print") as fake_print:
            code = accel.main(["--worker", "--root", "r", "--config", "c", "--model", "m", "--reference", "ref"])
        self.assertEqual(code, 2)
        self.assertIn("CHECKPOINT_MISMATCH", fake_print.call_args.args[0])

    def test_generic_failure_reports_worker_start_failed(self):
        with patch.object(accel, "worker_main", side_effect=ValueError("boom")), \
                patch("builtins.print") as fake_print:
            code = accel.main(["--worker", "--root", "r", "--config", "c", "--model", "m", "--reference", "ref"])
        self.assertEqual(code, 2)
        self.assertIn("WORKER_START_FAILED", fake_print.call_args.args[0])

    def test_resume_json_is_forwarded_to_cpu_worker_main(self):
        captured = {}

        def fake_worker_main(root, config, model, reference, resume=None):
            captured["resume"] = resume
            return 0

        resume_payload = {"source_ref": "a" * 64}
        with patch.object(ft_day_count, "worker_main", side_effect=fake_worker_main):
            self.assertEqual(
                accel.worker_main("root", "config", "model", "reference", resume=resume_payload), 0)
        self.assertEqual(captured["resume"], resume_payload)

    def test_ledger_root_is_rejected_before_cache_or_engine_construction(self):
        original = ft_day_count.Engine
        with TemporaryDirectory() as folder:
            (Path(folder) / "ledger.json").write_bytes(b"do not read")

            def construct(root, config, model, reference, resume=None):
                return ft_day_count.Engine(root, config, model, reference)

            with patch.object(ft_day_count, "worker_main", side_effect=construct), \
                    patch.object(accel, "_private_cache_dir") as cache, \
                    patch.object(accel, "AcceleratedEngine") as engine:
                with self.assertRaisesRegex(ValidationError, "day ledger"):
                    accel.worker_main(folder, "config", "model", "reference")
            cache.assert_not_called()
            engine.assert_not_called()
            self.assertIs(ft_day_count.Engine, original)


if __name__ == "__main__":
    unittest.main()
