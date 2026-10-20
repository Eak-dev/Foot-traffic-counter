"""Offline, opt-in acceleration experiments with the original YOLOX-s model.

No day-job/checkpoint interface is provided. Backend and kernel are independent
variables. All inference runs in a fresh macOS process with networking denied.
Synthetic timing is not evidence of counting accuracy or full-day throughput.
"""
from __future__ import annotations

import argparse
from collections import Counter
import contextlib
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

from tools import ft_perf
from tools.ft_perf_kernel import YoloXDecoder, contiguous_blob
from tools.ft_perf_metrics import summarize_resource

BACKENDS = ("ort", "coreml", "coreml_nn", "openvino")
KERNELS = ("legacy", "cached")
STAGES = ("prepare", "blob", "model", "decode", "nms", "detections")


def compare_exact_events(reference, candidate):
    """Compare event semantics including review reasons; not human accuracy."""
    result = ft_perf.compare_events(reference, candidate, tolerance=0)
    def signatures(events):
        signatures = Counter()
        for event in events:
            reasons = event.get("review_reasons", [])
            if (not isinstance(reasons, list) or len(reasons) > 50 or
                    any(not isinstance(v, str) or not 0 < len(v) <= 128 for v in reasons)):
                raise ValueError("invalid review reasons")
            signatures[(event["zone"], event.get("lane"), event["status"],
                        float(event["at"]), tuple(sorted(reasons)))] += 1
        return signatures
    left, right = signatures(reference), signatures(candidate)
    result["semantic_missing"] = sum((left - right).values())
    result["semantic_extra"] = sum((right - left).values())
    result["review_reasons_compared"] = True
    result["compatible"] = result["compatible"] and left == right
    return result


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def latency_summary(values):
    if not values:
        return dict(calls=0, seconds=0.0)
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("invalid timing")
    ordered = sorted(values)
    return dict(calls=len(values), seconds=round(sum(values), 6),
                mean_ms=round(statistics.mean(values) * 1000, 4),
                p50_ms=round(statistics.median(values) * 1000, 4),
                p95_ms=round(ordered[math.ceil(.95 * len(values)) - 1] * 1000, 4),
                first_ms=round(values[0] * 1000, 4),
                subsequent_mean_ms=(round(statistics.mean(values[1:]) * 1000, 4)
                                    if len(values) > 1 else None))


class Stages:
    def __init__(self):
        self.values = {}

    def add(self, zone, stage, elapsed):
        if stage not in STAGES or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("invalid stage sample")
        values = self.values.setdefault((zone, stage), [])
        if len(values) >= 2000:
            raise ValueError("stage sample quota exceeded")
        values.append(elapsed)

    def report(self):
        return {zone: {stage: latency_summary(values)
                       for (z, stage), values in self.values.items() if z == zone}
                for zone in sorted({z for z, _ in self.values})}

    def total(self):
        return sum(sum(v) for v in self.values.values())


class OpenVinoSession:
    """Synchronous, owned-output adapter for the baseline Engine contract."""
    columns = 85
    batch_size = 1

    def __init__(self, model, threads, columns=85, batch_size=1):
        if os.environ.get("CI", "").lower() != "true":
            raise ValueError("process-local telemetry opt-out required")
        import openvino as ov
        from openvino.tools.ovc import telemetry
        if telemetry.consent is not False or telemetry.sender.queue_size:
            raise ValueError("telemetry opt-out not enforced")
        self.core = ov.Core()
        self.columns = columns
        self.batch_size = batch_size
        self.options = dict(INFERENCE_PRECISION_HINT="f32",
                            EXECUTION_MODE_HINT="ACCURACY",
                            INFERENCE_NUM_THREADS=threads, NUM_STREAMS=1)
        self.compiled = self.core.compile_model(self.core.read_model(str(model)),
                                               "CPU", self.options)
        if len(self.compiled.inputs) != 1 or len(self.compiled.outputs) != 1:
            raise ValueError("unexpected model ports")
        self.port = self.compiled.input(0)
        self.output = self.compiled.output(0)
        if (list(self.port.shape) != [batch_size, 3, 640, 640] or
                list(self.output.shape) != [batch_size, 8400, columns]):
            raise ValueError("unexpected OpenVINO shape")
        if self.port.element_type != ov.Type.f32 or self.output.element_type != ov.Type.f32:
            raise ValueError("unexpected OpenVINO type")
        self.name = self.port.get_any_name()
        self.request = self.compiled.create_infer_request()
        self.resolved = {key: str(self.compiled.get_property(key)) for key in self.options}
        self.resolved["EXECUTION_DEVICES"] = list(self.compiled.get_property("EXECUTION_DEVICES"))

    def get_inputs(self):
        return [SimpleNamespace(name=self.name, shape=[self.batch_size, 3, 640, 640])]

    def run(self, output_names, feeds):
        import numpy as np
        if output_names is not None or set(feeds) != {self.name}:
            raise ValueError("unexpected inference request")
        blob = feeds[self.name]
        if blob.dtype != np.float32 or blob.shape != (self.batch_size, 3, 640, 640):
            raise ValueError("unexpected input tensor")
        # Legacy decoder mutates its output; do not alias InferRequest storage.
        raw = self.request.infer({0: blob}, share_inputs=True,
                                 share_outputs=False)[self.output]
        if raw.shape != (self.batch_size, 8400, self.columns) or raw.dtype != np.float32 or not np.isfinite(raw).all():
            raise ValueError("invalid OpenVINO result")
        return [raw]


class PersonOutputSession:
    """Restore unused class columns as zero for the unchanged person decoder."""
    def __init__(self, inner, batch_size=1):
        self.inner = inner
        self.batch_size = batch_size

    def get_inputs(self):
        return self.inner.get_inputs()

    def run(self, names, feeds):
        import numpy as np
        result = self.inner.run(names, feeds)
        if len(result) != 1 or result[0].shape != (self.batch_size, 8400, 6) or result[0].dtype != np.float32:
            raise ValueError("invalid projected output")
        if not np.isfinite(result[0]).all():
            raise ValueError("nonfinite projected output")
        expanded = np.zeros((self.batch_size, 8400, 85), dtype=np.float32)
        expanded[:, :, :6] = result[0]
        return [expanded]


def publish_derived(serialized, cache):
    """Publish complete content-addressed bytes without overwriting a cache."""
    from tools.ft_count import _file_sha256
    derived_sha = hashlib.sha256(serialized).hexdigest()
    destination = cache / ("derived-" + derived_sha + ".onnx")
    def verify():
        if destination.is_symlink() or not destination.is_file() or _file_sha256(destination) != derived_sha:
            raise ValueError("derived model cache mismatch")
    if destination.exists() or destination.is_symlink():
        verify()
        return destination, derived_sha
    fd, temp_name = tempfile.mkstemp(prefix=".derived-", suffix=".tmp", dir=cache)
    temporary = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(serialized)
            out.flush()
            os.fsync(out.fileno())
        if _file_sha256(temporary) != derived_sha:
            raise ValueError("derived model write mismatch")
        try:
            os.link(temporary, destination)
        except FileExistsError:
            verify()
    finally:
        temporary.unlink(missing_ok=True)
    return destination, derived_sha


def derived_model(model, cache, person_output, batch_size):
    import onnx
    from tools.ft_perf_projection import project_person_output, make_two_crop_batch
    from tools.ft_count import _file_sha256
    source_sha = _file_sha256(model)
    if source_sha != ft_perf.MODELS["baseline"][1]:
        raise ValueError("projection requires pinned original model")
    original = onnx.load(str(model), load_external_data=False)
    projected = (make_two_crop_batch(onnx, original, person_output=person_output) if batch_size == 2
                 else project_person_output(onnx, original))
    serialized = projected.SerializeToString()
    destination, derived_sha = publish_derived(serialized, cache)
    return destination, dict(transform=("two_crop_batch_v1" if batch_size == 2 else "single_crop_v1"),
                             person_output=person_output, original_sha256=source_sha,
                             derived_sha256=derived_sha, output_columns=6 if person_output else 85,
                             batch_size=batch_size,
                             adapter="zero-fill unused columns6:85" if person_output else "none",
                             onnx_version=onnx.__version__)


def create_session(backend, model, threads, cache, factory=None, person_output=False, batch_size=1):
    if backend not in BACKENDS or threads not in (1, 2, 4, 8) or batch_size not in (1, 2):
        raise ValueError("invalid backend options")
    provenance = None
    if person_output or batch_size == 2:
        model, provenance = derived_model(model, cache, person_output, batch_size)
    session, info = native_session(backend, model, threads, cache, factory,
                                   columns=6 if person_output else 85, batch_size=batch_size)
    info.update(batch_size=batch_size, output_columns=6 if person_output else 85)
    if provenance:
        info["derivation"] = provenance
    return (PersonOutputSession(session, batch_size) if person_output else session), info


def native_session(backend, model, threads, cache, factory, columns, batch_size):
    if backend == "openvino":
        session = OpenVinoSession(model, threads, columns, batch_size)
        return session, dict(name=backend, device="CPU", requested=session.options,
                             resolved=session.resolved, version=importlib.metadata.version("openvino"))
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.log_severity_level = 4
    factory = factory or ort.InferenceSession
    info = dict(name=backend, threads=threads, version=ort.__version__)
    if backend in ("coreml", "coreml_nn"):
        if "CoreMLExecutionProvider" not in ort.get_available_providers():
            raise ValueError("CoreML unavailable")
        settings = dict(ModelFormat="NeuralNetwork" if backend == "coreml_nn" else "MLProgram",
                        MLComputeUnits="CPUAndGPU",
                        RequireStaticInputShapes="1", AllowLowPrecisionAccumulationOnGPU="0")
        from tools.ft_count import _file_sha256
        key = digest_json(dict(model=_file_sha256(model), options=settings,
                               ort=ort.__version__, os=platform.mac_ver()[0]))
        settings["ModelCacheDirectory"] = str(cache / ("coreml-" + key))
        session = factory(str(model), sess_options=options,
                          providers=[("CoreMLExecutionProvider", settings), "CPUExecutionProvider"])
        session.disable_fallback()
        if "CoreMLExecutionProvider" not in session.get_providers():
            raise ValueError("CoreML creation fallback")
        info.update(options={k: v for k, v in settings.items() if k != "ModelCacheDirectory"},
                    cache_identity=key, registered_providers=session.get_providers(),
                    gpu_operator_coverage="NOT_MEASURED")
        if backend == "coreml_nn":
            info["precision_caveat"] = "NeuralNetwork GPU intermediates may be float16; not an exact-FP32 claim"
    else:
        session = factory(str(model), sess_options=options, providers=["CPUExecutionProvider"])
        info["registered_providers"] = session.get_providers()
    return session, info


def measured_detect(engine, image, cfg, kernel, decoder, stages, zone):
    """Same operations/order as Engine.detect; measure disjoint intervals."""
    from tools import ft_count as f
    cv, np = engine.cv, engine.np
    stamp = time.perf_counter()
    h, w = image.shape[:2]
    crop = cfg.get("crop", [0, 0, 1, 1])
    x, y, x2, y2 = int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)
    rgb = cv.cvtColor(image[y:y2, x:x2], cv.COLOR_BGR2RGB)
    canvas, scale = f._letterbox(cv, np, rgb)
    now = time.perf_counter(); stages.add(zone, "prepare", now - stamp); stamp = time.perf_counter()
    blob = (contiguous_blob(np, canvas) if kernel == "cached" else
            canvas.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32))
    now = time.perf_counter(); stages.add(zone, "blob", now - stamp); stamp = time.perf_counter()
    raw = engine.net.run(None, {engine.input_name: blob})[0]
    now = time.perf_counter(); stages.add(zone, "model", now - stamp); stamp = time.perf_counter()
    boxes, scores = (decoder.decode(raw, scale) if kernel == "cached" else
                     f._decode_yolox(np, raw, scale))
    now = time.perf_counter(); stages.add(zone, "decode", now - stamp); stamp = time.perf_counter()
    boxes[:, [0, 2]] += x
    boxes[:, [1, 3]] += y
    if len(boxes):
        boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, w)
        boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, h)
        ids = cv.dnn.NMSBoxes(np.column_stack((boxes[:, :2], boxes[:, 2:] - boxes[:, :2])).tolist(),
                              scores.tolist(), f.DET_SCORE_FLOOR, f.NMS_IOU)
        ids = np.array(ids).reshape(-1) if len(ids) else np.array([], dtype=int)
        boxes, scores = boxes[ids], scores[ids]
    now = time.perf_counter(); stages.add(zone, "nms", now - stamp); stamp = time.perf_counter()
    result = engine.sv.Detections(xyxy=boxes.astype(np.float32), confidence=scores.astype(np.float32),
                                   class_id=np.zeros(len(boxes), dtype=int))
    stages.add(zone, "detections", time.perf_counter() - stamp)
    return result


def identity(backend, kernel):
    repo = Path(__file__).resolve().parent.parent
    versions = {}
    for name in ("numpy", "onnxruntime", "opencv-python", "opencv-python-headless",
                 "supervision", "openvino", "onnx", "ml_dtypes"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    value = dict(backend=backend, kernel=kernel, model_sha256=ft_perf.MODELS["baseline"][1],
                 python=platform.python_version(),
                 machine=platform.machine(), os=platform.mac_ver()[0], packages=versions,
                 imported_cv2_version=getattr(sys.modules.get("cv2"), "__version__", None),
                 sources={name: hashlib.sha256((repo / "tools" / name).read_bytes()).hexdigest()
                          for name in ("ft_perf_accel.py", "ft_perf_kernel.py", "ft_perf_projection.py", "ft_perf.py",
                                       "ft_perf_metrics.py", "ft_count.py", "ft_day_count.py",
                                       "ft_day_state.py", "ft_state_codec.py", "ft_count_zones.py",
                                       "ft_lane_counter.py", "ft_track_quality.py", "ft_zone_entries.py",
                                       "ft_day_run.py", "ft_day_acquire.py")})
    return value, digest_json(value)


def run_worker(args):
    ft_perf._verify_network_denied()  # Before imports, model/media reads or caches.
    if args.batch_size != 1 and not args.synthetic:
        raise ValueError("batch2 is synthetic-only until video integration is validated")
    args.source_snapshot = identity({}, args.kernel)[0]["sources"]
    # OpenVINO/OVC honors disable_in_ci=True. No persistent consent-file changes.
    os.environ["CI"] = "true"
    from tools import ft_count as f, ft_day_count, ft_day_summary
    f._outside_repo(args.output)
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        raise ValueError("fresh output directory required")
    os.umask(0o077)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    cache = output.parent / "accel-cache"
    cache.mkdir(mode=0o700, exist_ok=True)
    if cache.is_symlink() or cache.stat().st_uid != os.getuid() or cache.stat().st_mode & 0o077:
        raise ValueError("private cache required")
    os.environ["MPLCONFIGDIR"] = str(cache)
    started = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_SELF)
    load_before = os.getloadavg()
    repo = Path(__file__).resolve().parent.parent
    model = repo / ".venv/ft-models/yolox_s.onnx"
    if model.is_symlink() or not model.is_file() or f._file_sha256(model) != ft_perf.MODELS["baseline"][1]:
        raise ValueError("pinned model identity mismatch")
    if args.synthetic:
        output.mkdir(mode=0o700)
        return run_synthetic(args, model, cache, started, before, load_before)
    from tools.ft_count_zones import load_zones_config
    cfg = load_zones_config(args.config)
    if any(z["config"].get("sample_fps", 5) != 5 for z in cfg["zones"]):
        raise ValueError("unchanged 5fps required")
    import supervision  # Load shared font cache before ft_perf sets its per-run path.
    import onnxruntime as ort
    factory, original_engine = ort.InferenceSession, ft_day_count.Engine
    writer = ft_day_summary.atomic_write
    stages = Stages()
    backend = {}

    class CandidateEngine(original_engine):
        def __init__(self, *a, **kw):
            def selected_session(requested, sess_options, providers):
                if Path(requested).resolve() != model.resolve():
                    raise ValueError("unexpected constructor model")
                result, info = create_session(args.backend, model, args.threads, cache, factory,
                                             person_output=args.person_output)
                backend.update(info)
                return result
            ort.InferenceSession = selected_session
            try:
                super().__init__(*a, **kw)
            finally:
                ort.InferenceSession = factory
            if self.net.get_inputs()[0].shape != [1, 3, 640, 640]:
                raise ValueError("unexpected input shape")
            self.cv.setNumThreads(args.threads)
            self.decoder = YoloXDecoder(self.np)
            self.zone_ids = {id(z["config"]): z["id"] for z in self.config["zones"]}

        def detect(self, image, zcfg):
            return measured_detect(self, image, zcfg, args.kernel, self.decoder,
                                   stages, self.zone_ids[id(zcfg)])

    def save_report(path, content):
        value = json.loads(content)
        value.update(stage_timings=stages.report(),
                     residual_seconds=round(max(0, value["elapsed_seconds"] - stages.total()), 6),
                     residual_includes="video decoding, lens verification, tracking, counters, loop and timer overhead")
        value["baseline_runtime_sha256"] = value.pop("runtime_sha256")
        enrich(value, args, backend, started, before, load_before)
        writer(path, json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n")

    ft_day_count.Engine = CandidateEngine
    ft_day_summary.atomic_write = save_report
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            ft_perf._run(SimpleNamespace(candidate="baseline", input=args.input, config=args.config,
                                        reference=args.reference, output=args.output, seconds=args.seconds))
        value = json.loads((output / "experiment.json").read_text())
        print(json.dumps({k: value[k] for k in ("candidate", "frames", "elapsed_seconds", "totals",
                                              "whole_worker", "stage_timings")}), flush=True)
    finally:
        ft_day_count.Engine = original_engine
        ort.InferenceSession = factory
        ft_day_summary.atomic_write = writer


def enrich(value, args, backend, started, before, load_before):
    elapsed = time.monotonic() - started
    after = resource.getrusage(resource.RUSAGE_SELF)
    source, _ = identity(backend, args.kernel)
    if source["sources"] != args.source_snapshot:
        raise ValueError("experiment source changed during execution")
    source["baseline_runtime_sha256"] = value.get("baseline_runtime_sha256")
    digest = digest_json(source)
    value.update(candidate=args.backend + "-" + args.kernel + ("-person6" if args.person_output else ""),
                 backend=backend, kernel=args.kernel, batch_size=args.batch_size,
                 network_denied=True, experiment_only=True, production_eligible=False,
                 checkpoint_compatible=False, accuracy_status="NOT_VERIFIED",
                 experiment_identity=source, experiment_runtime_sha256=digest,
                 resource_interval="before runtime imports through processing; excludes identity/report serialization",
                 model_timing_scope="synchronous backend call, including output copy and adapter validation",
                 whole_worker=summarize_resource(elapsed,
                      after.ru_utime - before.ru_utime, after.ru_stime - before.ru_stime,
                      after.ru_maxrss, os.cpu_count() or 1),
                 system_load_before=load_before, system_load_after=os.getloadavg())


def run_synthetic(args, model, cache, started, before, load_before):
    import numpy as np
    from tools import ft_count as f
    from tools.ft_day_summary import atomic_write
    session, backend = create_session(args.backend, model, args.threads, cache,
                                     person_output=args.person_output, batch_size=args.batch_size)
    decoder = YoloXDecoder(np)
    rng = np.random.RandomState(70)
    checker = ((np.indices((640, 640)).sum(axis=0) // 32 % 2) * 255).astype(np.uint8)
    canvases = [np.full((640, 640, 3), 114, dtype=np.uint8),
                np.repeat(checker[:, :, None], 3, axis=2),
                rng.randint(0, 256, (640, 640, 3)).astype(np.uint8)]
    timings, blobs, decoded, snapshots, kept_rows = [], [], [], [], []
    name = session.get_inputs()[0].name
    output = Path(args.output)
    def make_blob(index):
        parts = []
        for j in range(args.batch_size):
            canvas = canvases[(index * args.batch_size + j) % len(canvases)]
            parts.append(contiguous_blob(np, canvas) if args.kernel == "cached" else
                         canvas.transpose(2, 0, 1)[None].astype(np.float32))
        return parts[0] if args.batch_size == 1 else np.concatenate(parts, axis=0)
    warmup_started = time.monotonic()
    for _ in range(3):
        session.run(None, {name: make_blob(0)})
    warmup_seconds = time.monotonic() - warmup_started
    proc_before = resource.getrusage(resource.RUSAGE_SELF)
    processing_started = time.monotonic()
    for index in range(args.iterations):
        stamp = time.perf_counter()
        blob = make_blob(index)
        blobs.append(time.perf_counter() - stamp)
        stamp = time.perf_counter()
        raw = session.run(None, {name: blob})[0]
        timings.append(time.perf_counter() - stamp)
        if index < 3:
            snapshots.append(raw.copy())
        stamp = time.perf_counter()
        per_item_kept = []
        for j in range(args.batch_size):
            boxes, scores = (decoder.decode(raw[j:j+1], 1.0) if args.kernel == "cached" else
                             f._decode_yolox(np, raw[j:j+1], 1.0))
            per_item_kept.append(len(scores))
        decoded.append(time.perf_counter() - stamp)
        if index < 3:
            kept_rows.append(per_item_kept)
    processing_seconds = time.monotonic() - processing_started
    proc_after = resource.getrusage(resource.RUSAGE_SELF)
    value = dict(schema_version=1, synthetic_only=True, model_sha256=f._file_sha256(model),
                 iterations=args.iterations, warmup_calls=3, warmup_seconds=round(warmup_seconds, 6),
                 synthetic_images=args.iterations * args.batch_size,
                 pattern_order="item=(batch_index*batch_size+item_index)%3; padding114, checkerboard, seeded_noise",
                 first_three_batches_kept_rows=kept_rows,
                 per_image_model_ms=round(statistics.mean(timings) * 1000 / args.batch_size, 4),
                 synthetic_images_per_second=round(args.iterations * args.batch_size / processing_seconds, 4),
                 processing_seconds=round(processing_seconds, 6),
                 processing_cpu_core_seconds=round(proc_after.ru_utime + proc_after.ru_stime -
                                                   proc_before.ru_utime - proc_before.ru_stime, 6),
                 latency=dict(model=latency_summary(timings), blob=latency_summary(blobs),
                              decode=latency_summary(decoded)))
    enrich(value, args, backend, started, before, load_before)
    for index, raw in enumerate(snapshots):
        np.save(output / ("synthetic-output-" + str(index) + ".npy"), raw, allow_pickle=False)
    atomic_write(output / "experiment.json", json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n")
    print(json.dumps({k: value[k] for k in ("candidate", "synthetic_only", "latency", "whole_worker")}),
          flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=BACKENDS, required=True)
    parser.add_argument("--kernel", choices=KERNELS, default="legacy")
    parser.add_argument("--person-output", action="store_true",
                        help="derive a separate model outputting only coords/objectness/person")
    parser.add_argument("--batch-size", type=int, choices=(1, 2), default=1,
                        help="batch2 currently available only for synthetic screening")
    parser.add_argument("--threads", type=int, choices=(1, 2, 4, 8), default=4)
    parser.add_argument("--output", required=True)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--iterations", type=int, choices=range(3, 61), default=12)
    parser.add_argument("--seconds", type=int, choices=range(1, 181), default=180)
    for key in ("input", "config", "reference"):
        parser.add_argument("--" + key)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.synthetic and not all((args.input, args.config, args.reference)):
        parser.error("video mode requires input, config and reference")
    if args.synthetic and any((args.input, args.config, args.reference)):
        parser.error("synthetic mode does not accept media/config arguments")
    if args.batch_size != 1 and not args.synthetic:
        parser.error("batch2 is synthetic-only until video integration is validated")
    if args.worker:
        try:
            run_worker(args)
            return 0
        except Exception as exc:
            print(json.dumps(dict(status="BLOCKED", reason="OFFLINE_ACCELERATION_FAILED",
                                  kind=type(exc).__name__)), flush=True)
            return 1
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        parser.error("macOS deny-network sandbox required")
    command = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)",
               sys.executable, "-m", "tools.ft_perf_accel",
               *(sys.argv[1:] if argv is None else argv), "--worker"]
    try:
        return subprocess.call(command, timeout=600 if args.synthetic else 1900)
    except subprocess.TimeoutExpired:
        print(json.dumps(dict(status="BLOCKED", reason="ACCELERATION_TIMEOUT")), flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
