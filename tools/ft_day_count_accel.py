"""Opt-in local CoreML day-counting worker reusing the pinned CPU pipeline.

This module never changes ``tools.ft_day_count``/``tools.ft_day_state``: it
adds a subclass that replaces only the inference session with a two-zone
batch-2 CoreML session from ``tools.ft_perf_accel``, delegating every other
behavior (lens verification, clock, trackers, counters, checkpoint codec,
deny-network/private-root checks, stdin/JSON protocol) to the unmodified
``Engine``/``worker_main``. Only ``--worker`` imports image/inference
libraries, same as the CPU worker; this module itself stays stdlib-importable
so it can be imported for control-boundary tests without optional deps.

Offline operation rejects day ledgers by default. The explicit ``--day-ledger``
mode accepts only a matching CoreML ledger/reference/config/resume lineage.
There is no CPU fallback. CPU and accelerated checkpoints bind to different
``runtime_digest`` values and must reject each other.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from tools import ft_count as f
from tools import ft_day_count
from tools.ft_day_count import Engine as CPUEngine
from tools.ft_perf_accel import Stages, create_session, identity, measured_batch_detect
from tools.ft_perf_kernel import YoloXDecoder
from tools.ft_state_codec import StateError
from tools.ft_day_state import runtime_digest as cpu_runtime_digest

POLICY_VERSION = "coreml_worker_day_lineage_v2"


def _canonical_digest(cpu_runtime_digest, identity_value, reference_sha256, wrapper_sha256):
    value = dict(policy_version=POLICY_VERSION, base_runtime=cpu_runtime_digest,
                 identity=identity_value, reference_sha256=reference_sha256,
                 wrapper_sha256=wrapper_sha256)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _wrapper_source_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _validate_detections(detections, np, sv):
    f._require(isinstance(detections, sv.Detections), "invalid detection result type")
    xyxy = detections.xyxy
    f._require(isinstance(xyxy, np.ndarray) and xyxy.dtype == np.float32 and xyxy.ndim == 2
               and xyxy.shape[1] == 4, "invalid detection boxes")
    f._require(bool(np.isfinite(xyxy).all()), "non-finite detection boxes")
    count = xyxy.shape[0]
    confidence = detections.confidence
    f._require(isinstance(confidence, np.ndarray) and confidence.dtype == np.float32
               and confidence.shape == (count,), "invalid detection confidence")
    f._require(bool(np.isfinite(confidence).all()), "non-finite detection confidence")
    f._require(bool(((confidence >= 0) & (confidence <= 1)).all()), "detection confidence out of range")
    class_id = detections.class_id
    f._require(isinstance(class_id, np.ndarray) and class_id.shape == (count,), "invalid detection class ids")
    f._require(count == 0 or bool((class_id == 0).all()), "unexpected non-person class id")


def _private_cache_dir(root):
    cache = Path(root) / "coreml-cache"
    f._require(not cache.is_symlink(), "cache must not be a symlink")
    cache.mkdir(mode=0o700, exist_ok=True)
    s = cache.lstat()
    f._require(stat.S_ISDIR(s.st_mode) and s.st_uid == os.getuid() and not s.st_mode & 0o077,
               "private cache root required")
    return cache


def _require_offline_lineage(root, resume):
    """Never attach this offline worker to a day ledger or overwrite a snapshot."""
    f._require(not os.path.lexists(Path(root) / "ledger.json"), "offline root must not contain a day ledger")
    folder = Path(root) / "checkpoints"
    try:
        saved = folder.lstat()
    except FileNotFoundError:
        return
    f._require(stat.S_ISDIR(saved.st_mode) and saved.st_uid == os.getuid()
               and not saved.st_mode & 0o077, "private checkpoint directory required")
    if resume is None:
        f._require(next(folder.iterdir(), None) is None, "existing checkpoints require explicit resume")


def _require_new_checkpoint_source(root, message):
    source = message.get("source_ref") if isinstance(message, dict) else None
    f._require(type(source) is str and len(source) == 64
               and all(c in "0123456789abcdef" for c in source), "invalid source digest")
    f._require(not os.path.lexists(Path(root) / "checkpoints" / (source + ".json")),
               "source checkpoint already exists")


def _require_day_lineage(root, config, reference, resume):
    """Read-only ledger proof before creating a cache or loading inference."""
    from tools.ft_day_run import prepare_ledger, validate_existing_identity
    from tools.ft_day_acquire import DayError
    from tools.ft_day_summary import read_ledger
    try:
        reference_hash = f._file_sha256(reference)
        validate_existing_identity(root, "coreml", reference_hash, config=config)
        data = read_ledger(Path(root) / "ledger.json")
        # Reuse the driver's complete prefix/group/checkpoint checks without
        # inventing a new inventory, mutating it, or opening the camera.
        info = dict(clips=data["clips"], inventory_digest=data["inventory_digest"])
        prepare_ledger(root, info, config, data["date"].replace("-", ""),
                       backend="coreml", expected_reference=reference_hash)
        if data["checkpoint"] != resume:
            raise StateError("resume must equal the committed day checkpoint")
        folder = Path(root) / "checkpoints"
        if os.path.lexists(folder):
            saved = folder.lstat()
            if (not stat.S_ISDIR(saved.st_mode) or saved.st_uid != os.getuid()
                    or saved.st_mode & 0o077):
                raise StateError("private checkpoint directory required")
        # Orphans at cursor zero are left intact here. The driver may prune
        # them only after the live worker has accepted the bound runtime.
        return data.get("count_runtime")
    except (DayError, f.ValidationError, OSError, ValueError, KeyError, TypeError):
        raise StateError("day ledger identity mismatch") from None


class AcceleratedEngine(CPUEngine):
    """Same validated pipeline/checkpoint codec; one CoreML two-zone batch net.

    ``detect`` is still called once per configured zone per frame by the
    inherited ``process`` loop, unchanged. The first configured zone's call
    computes and validates both zones' results with one shared
    ``measured_batch_detect`` call, returns its own result, and holds the
    second zone's result for the immediately following call with the same
    image object and the same second zone config object. No process/clock/
    tracker loop code is copied from the base Engine.
    """

    def __init__(self, root, config, model, reference, cache):
        super().__init__(root, config, model, reference)
        zones = config["zones"]
        f._require(len(zones) == 2 and zones[0]["id"] != zones[1]["id"], "exactly two unique zones required")
        self._zones = zones
        self._zone_configs = (zones[0]["config"], zones[1]["config"])
        f._require(self._zone_configs[0] is not self._zone_configs[1], "zone config objects must be distinct")
        f._require(all(type(z["config"].get("sample_fps", 5)) in (int, float)
                       and z["config"].get("sample_fps", 5) == 5 for z in zones),
                   "accelerated worker requires 5 fps")
        session, backend_info = create_session("coreml", model, 4, cache, person_output=True,
                                               batch_size=2, precision="fp32")
        self.net = session
        self.input_name = self.net.get_inputs()[0].name
        self._backend_info = copy.deepcopy(backend_info)
        self._decoder = YoloXDecoder(self.np)
        self._stages = Stages()
        self._pending = None
        self._cpu_runtime_digest = self.runtime_digest
        current, _ = identity(self._backend_info, "cached")
        self._identity_baseline = copy.deepcopy(current)
        self._wrapper_sha256 = _wrapper_source_sha256()
        self.runtime_digest = _canonical_digest(self._cpu_runtime_digest, self._identity_baseline,
                                                self.reference_sha256, self._wrapper_sha256)

    def _assert_frozen_identity(self):
        current, _ = identity(self._backend_info, "cached")
        f._require(current == self._identity_baseline, "acceleration identity or source changed")
        f._require(_wrapper_source_sha256() == self._wrapper_sha256, "acceleration wrapper source changed")
        f._require(cpu_runtime_digest() == self._cpu_runtime_digest, "base counting runtime changed")

    def reset(self, origin):
        self._pending = None
        super().reset(origin)

    def detect(self, image, cfg):
        try:
            return self._detect_pair(image, cfg)
        except Exception:
            self._pending = None
            raise

    def _detect_pair(self, image, cfg):
        if cfg is self._zone_configs[0]:
            f._require(self._pending is None, "pending two-zone cache not consumed before a new frame")
            results = measured_batch_detect(self, image, self._zones, "cached", self._decoder, self._stages)
            f._require(isinstance(results, list) and len(results) == 2, "batch detector must return two results")
            for detections in results:
                _validate_detections(detections, self.np, self.sv)
            self._pending = (image, self._zone_configs[1], results[1])
            return results[0]
        if cfg is self._zone_configs[1]:
            pending = self._pending
            self._pending = None
            f._require(pending is not None, "second zone detect called without a pending first-zone result")
            pending_image, pending_cfg, pending_detections = pending
            f._require(pending_image is image and pending_cfg is cfg,
                       "second zone result does not match the cached first-zone frame")
            return pending_detections
        raise f.ValidationError("unknown zone config for the accelerated two-zone cache")

    def process(self, message):
        f._require(self._pending is None, "ephemeral two-zone cache must be empty before processing")
        self._assert_frozen_identity()
        _require_new_checkpoint_source(self.root, message)
        # Timing samples are diagnostic only, never checkpoint state. Bound
        # memory/quota per <=180-second source instead of accumulating all day.
        self._stages = Stages()
        try:
            result = super().process(message)
        except Exception:
            self._pending = None
            raise
        f._require(self._pending is None, "ephemeral two-zone cache must be empty after processing")
        self._assert_frozen_identity()
        return result


def worker_main(root, config, model, reference, resume=None, day_ledger=False):
    original_engine = ft_day_count.Engine

    def bound_engine(root_, config_, model_, reference_):
        runtime = None
        if day_ledger:
            runtime = _require_day_lineage(root_, config_, reference_, resume)
        else:
            _require_offline_lineage(root_, resume)
        engine = AcceleratedEngine(root_, config_, model_, reference_, _private_cache_dir(root_))
        if runtime is not None and runtime != engine.runtime_digest:
            raise StateError("day runtime identity mismatch")
        return engine

    ft_day_count.Engine = bound_engine
    try:
        return ft_day_count.worker_main(root, config, model, reference, resume)
    finally:
        ft_day_count.Engine = original_engine


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--resume-json", default=None)
    parser.add_argument("--day-ledger", action="store_true")
    args = parser.parse_args(argv)
    try:
        options = {"day_ledger": True} if args.day_ledger else {}
        return worker_main(args.root, args.config, args.model, args.reference,
                           json.loads(args.resume_json) if args.resume_json else None, **options)
    except StateError:
        print('{"status":"blocked","reason":"CHECKPOINT_MISMATCH"}', flush=True)
        return 2
    except Exception:
        print('{"status":"blocked","reason":"WORKER_START_FAILED"}', flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
