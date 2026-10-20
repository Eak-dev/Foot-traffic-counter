"""OD69 standalone same-clip benchmark, never a production/day-job backend.

Reuses pinned Engine tracking/counters through ft_perf's loop. A scoped
constructor adapter substitutes the hash-checked detector only inside this
fresh deny-network process. No model downloads or checkpoint loading.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from types import SimpleNamespace

from tools import ft_perf
from tools.ft_perf_metrics import summarize_resource

NANODET = ('object_detection_nanodet_2022nov.onnx',
           '4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186', 416)
CANDIDATES = ('baseline', 'coreml', 'nano', 'tiny', 'nanodet', 'nanodet_native')


def nanodet_decode(np, outputs, person_only=True):
    """Actual pinned ONNX: three class/regression levels, order-independent.

    Person-only mode prevents other classes suppressing a person. The vendor
    mode preserves all classes and its per-level top1000 for downstream NMS.
    """
    if len(outputs) != 6:
        raise ValueError('NanoDet output count mismatch')
    levels = {}
    for value in outputs:
        if value.ndim != 3 or value.shape[0] != 1 or not np.isfinite(value).all():
            raise ValueError('NanoDet nonfinite/invalid tensor')
        n, width = value.shape[1:]
        if n not in (2704, 676, 169) or width not in (80, 32) or (n, width) in levels:
            raise ValueError('NanoDet tensor contract mismatch')
        levels[(n, width)] = value[0]
    boxes, scores = [], []
    for stride in (8, 16, 32):
        side = 416 // stride
        n = side**2
        if (n, 80) not in levels or (n, 32) not in levels:
            raise ValueError('NanoDet missing level')
        x, y = np.meshgrid(np.arange(side), np.arange(side))
        anchors = np.column_stack((x.ravel(), y.ravel())) * stride + .5 * (stride - 1)
        logits = levels[(n, 32)].reshape(n, 4, 8)
        probs = np.exp(logits - logits.max(axis=2, keepdims=True))
        probs /= probs.sum(axis=2, keepdims=True)
        distance = (probs @ np.arange(8)) * stride
        box = np.column_stack((anchors - distance[:, :2], anchors + distance[:, 2:]))
        box = np.clip(box, 0, 416)
        cls = levels[(n, 80)]
        if not person_only and n > 1000:
            top = cls.max(axis=1).argsort()[::-1][:1000]
            box, cls = box[top], cls[top]
        boxes.append(box)
        scores.append(cls[:, 0] if person_only else cls)
    return np.concatenate(boxes), np.concatenate(scores)


def nanodet_input(cv, np, image):
    h, w = image.shape[:2]
    scale = min(416 / h, 416 / w)
    nh, nw = int(h * scale), int(w * scale)
    top, left = (416 - nh) // 2, (416 - nw) // 2
    canvas = np.zeros((416, 416, 3), dtype=np.uint8)
    rgb = cv.cvtColor(image, cv.COLOR_BGR2RGB)
    canvas[top:top + nh, left:left + nw] = cv.resize(rgb, (nw, nh), interpolation=cv.INTER_AREA)
    values = (canvas.astype(np.float32) - np.array([103.53, 116.28, 123.675], dtype=np.float32))
    values /= np.array([57.375, 57.12, 58.395], dtype=np.float32)
    return np.ascontiguousarray(values.transpose(2, 0, 1)[None]), (top, left, nh, nw)


def run_worker(args):
    ft_perf._verify_network_denied()  # Fail closed before inference imports.
    from tools import ft_count as f, ft_day_count, ft_day_summary
    from tools.ft_count_zones import load_zones_config
    f._outside_repo(args.output)
    output = Path(args.output)
    if output.exists():
        raise ValueError('fresh output directory required')
    os.umask(0o077)
    cache = output.parent / 'shared-cache'
    cache.mkdir(mode=0o700, exist_ok=True)
    if cache.is_symlink() or cache.stat().st_mode & 0o077:
        raise ValueError('private shared cache required')
    os.environ['MPLCONFIGDIR'] = str(cache)
    started = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_SELF)
    load_before = os.getloadavg()
    import supervision  # Equal font-cache policy for every fresh worker.
    import onnxruntime as ort
    cfg = load_zones_config(args.config)
    if any(z['config'].get('sample_fps', 5) != 5 for z in cfg['zones']):
        raise ValueError('unchanged 5fps required')
    repo = Path(__file__).resolve().parent.parent
    spec = (NANODET if args.candidate.startswith('nanodet') else
            ft_perf.MODELS['baseline' if args.candidate == 'coreml' else args.candidate])
    name, expected, size = spec
    model = repo / '.venv/ft-models' / name
    if model.is_symlink() or not model.is_file() or f._file_sha256(model) != expected:
        raise ValueError('candidate model identity mismatch')
    backend = dict(provider='CPUExecutionProvider', threads=args.threads)
    if args.candidate == 'coreml':
        backend.update(provider='CoreMLExecutionProvider', ModelFormat='MLProgram',
                       MLComputeUnits='CPUAndGPU', RequireStaticInputShapes='1',
                       AllowLowPrecisionAccumulationOnGPU='0')
    factory, original_engine = ort.InferenceSession, ft_day_count.Engine

    class CandidateEngine(original_engine):
        def __init__(self, *a, **kw):
            def selected_session(requested, sess_options, providers):
                if Path(requested).resolve() != (repo / '.venv/ft-models/yolox_s.onnx').resolve():
                    raise ValueError('unexpected baseline constructor model')
                sess_options.log_severity_level = 4
                sess_options.intra_op_num_threads = args.threads
                if args.candidate == 'coreml':
                    if 'CoreMLExecutionProvider' not in ort.get_available_providers():
                        raise ValueError('CoreML provider unavailable')
                    options = {k: v for k, v in backend.items() if k not in ('provider', 'threads')}
                    options['ModelCacheDirectory'] = str(cache / ('mlprogram-' + expected[:16]))
                    result = factory(str(model), sess_options=sess_options,
                                     providers=[('CoreMLExecutionProvider', options), 'CPUExecutionProvider'])
                    result.disable_fallback()
                    if 'CoreMLExecutionProvider' not in result.get_providers():
                        raise ValueError('CoreML session creation fell back')
                    backend['registered_providers'] = result.get_providers()
                    return result
                return factory(str(model), sess_options=sess_options, providers=['CPUExecutionProvider'])
            ort.InferenceSession = selected_session
            try:
                super().__init__(*a, **kw)
            finally:
                ort.InferenceSession = factory
            if self.net.get_inputs()[0].shape != [1, 3, size, size]:
                raise ValueError('candidate input shape mismatch')
            self.cv.setNumThreads(args.threads)
            self.bench_calls = 0
            self.bench_started = time.monotonic()

        def detect(self, image, zcfg):
            self.bench_calls += 1
            if self.bench_calls % 200 == 0:
                writer(self.root / 'progress.json', json.dumps(dict(candidate=args.candidate,
                    started_detector_calls=self.bench_calls,
                    processing_seconds=round(time.monotonic() - self.bench_started, 3))) + '\n')
            if args.candidate in ('baseline', 'coreml'):
                return super().detect(image, zcfg)
            cv, np = self.cv, self.np
            h, w = image.shape[:2]
            c = zcfg.get('crop', [0, 0, 1, 1])
            x, y, x2, y2 = int(c[0] * w), int(c[1] * h), int(c[2] * w), int(c[3] * h)
            part = image[y:y2, x:x2]
            native = args.candidate == 'nanodet_native'
            if args.candidate.startswith('nanodet'):
                blob, (top, left, nh, nw) = nanodet_input(cv, np, part)
                boxes, scores = nanodet_decode(np, self.net.run(None, {self.input_name: blob}), person_only=not native)
                if native:
                    classes, confidences = scores.argmax(axis=1), scores.max(axis=1)
                    ids = cv.dnn.NMSBoxes(np.column_stack((boxes[:, :2], boxes[:, 2:] - boxes[:, :2])).tolist(),
                                          confidences.tolist(), .35, .6)
                    ids = np.asarray(ids, dtype=int).reshape(-1)
                    ids = ids[classes[ids] == 0]
                    boxes, scores = boxes[ids], confidences[ids]
                boxes[:, [0, 2]] = (boxes[:, [0, 2]] - left) * part.shape[1] / nw
                boxes[:, [1, 3]] = (boxes[:, [1, 3]] - top) * part.shape[0] / nh
            else:
                scale = min(size / part.shape[0], size / part.shape[1])
                nh, nw = int(part.shape[0] * scale), int(part.shape[1] * scale)
                canvas = np.full((size, size, 3), 114, dtype=np.uint8)
                canvas[:nh, :nw] = cv.resize(part, (nw, nh), interpolation=cv.INTER_LINEAR)
                blob = np.ascontiguousarray(canvas.transpose(2, 0, 1)[None], dtype=np.float32)
                boxes, scores = ft_perf._decode(np, self.net.run(None, {self.input_name: blob})[0], scale, size)
            # Common person score floor/NMS. NanoDet removes centered padding;
            # YOLOX preserves the existing full-image clipping convention.
            keep = scores >= f.DET_SCORE_FLOOR
            boxes, scores = boxes[keep], scores[keep]
            if args.candidate.startswith('nanodet'):
                boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, part.shape[1]) + x
                boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, part.shape[0]) + y
            else:
                boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]] + x, 0, w)
                boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]] + y, 0, h)
            if len(boxes) and not native:
                ids = cv.dnn.NMSBoxes(np.column_stack((boxes[:, :2], boxes[:, 2:] - boxes[:, :2])).tolist(),
                                      scores.tolist(), f.DET_SCORE_FLOOR, f.NMS_IOU)
                ids = np.asarray(ids, dtype=int).reshape(-1)
                boxes, scores = boxes[ids], scores[ids]
            return self.sv.Detections(xyxy=boxes.astype(np.float32), confidence=scores.astype(np.float32),
                                      class_id=np.zeros(len(boxes), dtype=int))

    # Keep ft_perf's unchanged half-open frame loop; only this fresh process is adapted.
    ft_day_count.Engine = CandidateEngine
    old_spec = ft_perf.MODELS['baseline']
    ft_perf.MODELS['baseline'] = spec
    writer = ft_day_summary.atomic_write
    def save_report(path, content):
        value = json.loads(content)
        after = resource.getrusage(resource.RUSAGE_SELF)
        value.update(candidate=args.candidate, backend=backend, network_denied=True,
                     preprocessing=('upstream_raw_bgr' if args.candidate in ('nano', 'tiny') else
                                    'nanodet_vendor_rgb_centered_black_mean_std' if args.candidate.startswith('nanodet') else 'pinned_zoo_rgb'),
                     whole_worker=summarize_resource(time.monotonic() - started,
                         after.ru_utime - before.ru_utime, after.ru_stime - before.ru_stime,
                         after.ru_maxrss, os.cpu_count() or 1),
                     system_load_before=load_before, system_load_after=os.getloadavg(),
                     nanodet_policy=('vendor_top1000_allclass_score_0.35_nms_0.6_then_person;float_unletterbox' if args.candidate == 'nanodet_native' else
                                     'vendor_input_distance_decoder_unletterbox_crop_clamp;person_only;common_score_0.1_nms_0.5' if args.candidate == 'nanodet' else None),
                     experiment_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     experiment_sources_sha256={name: hashlib.sha256((repo / 'tools' / name).read_bytes()).hexdigest()
                         for name in ('ft_perf_compare.py', 'ft_perf_metrics.py', 'ft_perf.py')},
                     production_eligible=False, accuracy_status='NOT_VERIFIED')
        writer(path, json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n')
    ft_day_summary.atomic_write = save_report
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            ft_perf._run(SimpleNamespace(candidate='baseline', input=args.input, config=args.config,
                reference=args.reference, output=args.output, seconds=args.seconds))
        result = json.loads((output / 'experiment.json').read_text())
        print(json.dumps({k: result[k] for k in ('candidate', 'frames', 'elapsed_seconds', 'totals', 'whole_worker')}, allow_nan=False), flush=True)
    finally:
        ft_day_summary.atomic_write = writer
        ft_day_count.Engine = original_engine
        ft_perf.MODELS['baseline'] = old_spec


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', choices=CANDIDATES, required=True)
    for key in ('input', 'config', 'reference', 'output'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--seconds', type=int, choices=range(1, 181), default=180)
    parser.add_argument('--threads', type=int, choices=(1, 2, 4), default=4)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        try:
            run_worker(args)
            return 0
        except Exception as exc:
            print(json.dumps(dict(status='BLOCKED', kind=type(exc).__name__, reason='OFFLINE_COMPARISON_FAILED')), flush=True)
            return 1
    if sys.platform != 'darwin':
        parser.error('Darwin resource units/network sandbox required')
    command = ['/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny network*)',
               sys.executable, '-m', 'tools.ft_perf_compare', *(sys.argv[1:] if argv is None else argv), '--worker']
    try:
        start = time.monotonic()
        status = subprocess.call(command, timeout=1200)
        if status == 0:
            report_path = Path(args.output) / 'experiment.json'
            value = json.loads(report_path.read_text())
            value['launch_to_exit_seconds'] = round(time.monotonic() - start, 6)
            value['resource_interval'] = 'worker before runtime imports to report write; RSS is lifetime peak'
            from tools.ft_day_summary import atomic_write
            atomic_write(report_path, json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n')
        return status
    except subprocess.TimeoutExpired:
        print(json.dumps(dict(status='BLOCKED', reason='COMPARISON_TIMEOUT')), flush=True)
        return 2


if __name__ == '__main__':
    sys.exit(main())
