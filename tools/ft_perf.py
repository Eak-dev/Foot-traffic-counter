"""Opt-in offline detector experiments; never a day-job execution backend.

Stdlib comparison imports without the optional inference runtime. The CLI
re-executes inference under the same macOS deny-network boundary as ft_count.
Reports contain timings/events only and must stay outside the repository.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

MODELS = {
    'baseline': ('yolox_s.onnx', 'c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063', 640),
    'joint': ('yolox_s.onnx', 'c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063', 640),
    'nano': ('yolox_nano.onnx', 'c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d', 416),
    'nano_tiles': ('yolox_nano.onnx', 'c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d', 416),
    'tiny': ('yolox_tiny.onnx', '427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7', 416),
    'int8': ('object_detection_yolox_2022nov_int8.onnx', '01a3b0f400b30bc1e45230e991b2e499ab42622485a330021947333fbaf03935', 640),
    'int8bq': ('object_detection_yolox_2022nov_int8bq.onnx', 'dcaae0aaa2fea4167f89235ee340eb869d3707b25712218d4c7ce921ac90e2ba', 640),
}


def _events(events):
    if not isinstance(events, list) or len(events) > 10000:
        raise ValueError('invalid events')
    groups = defaultdict(list)
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('invalid event')
        zone, lane, status, at = (event.get(k) for k in ('zone', 'lane', 'status', 'at'))
        if (zone not in ('front_shop', 'water_side') or
                status not in ('accepted', 'review') or
                (zone == 'front_shop' and lane not in ('near', 'far')) or
                (zone == 'water_side' and lane is not None) or
                type(at) not in (int, float) or not math.isfinite(at) or at < 0):
            raise ValueError('invalid event fields')
        groups[(zone, lane, status)].append(float(at))
    return {key: sorted(value) for key, value in groups.items()}


def event_totals(events):
    groups = _events(events)
    return {
        'near': len(groups.get(('front_shop', 'near', 'accepted'), [])),
        'far': len(groups.get(('front_shop', 'far', 'accepted'), [])),
        'front': sum(len(v) for (z, _, s), v in groups.items() if z == 'front_shop' and s == 'accepted'),
        'front_review': sum(len(v) for (z, _, s), v in groups.items() if z == 'front_shop' and s == 'review'),
        'shop_side': len(groups.get(('water_side', None, 'accepted'), [])),
        'shop_side_review': len(groups.get(('water_side', None, 'review'), [])),
    }


def compare_events(reference, candidate, tolerance=0.4):
    """One-to-one sorted matching by zone/lane/status/time, not aggregate equality.

    Compatibility is with the reference algorithm, NOT human accuracy proof.
    """
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or not 0 <= tolerance <= 2:
        raise ValueError('invalid tolerance')
    a, b = _events(reference), _events(candidate)
    matched = missing = extra = 0
    max_delta = 0.0
    for key in a.keys() | b.keys():
        left, right = a.get(key, []), b.get(key, [])
        i = j = 0
        while i < len(left) and j < len(right):
            delta = right[j] - left[i]
            if abs(delta) <= tolerance + 1e-9:
                matched += 1
                max_delta = max(max_delta, abs(delta))
                i += 1
                j += 1
            elif delta < 0:
                extra += 1
                j += 1
            else:
                missing += 1
                i += 1
        missing += len(left) - i
        extra += len(right) - j
    return dict(reference=event_totals(reference), candidate=event_totals(candidate),
                matched=matched, missing=missing, extra=extra,
                max_time_delta=round(max_delta, 6), compatible=missing == extra == 0,
                accuracy_status='NOT_VERIFIED')


def sample_time(index, fps, end):
    """Match day-worker half-open ownership even with fractional source fps."""
    at = round(index / fps, 3)
    return at if at < end else None


def _decode(np, raw, scale, size):
    """YOLOX raw output contract, person class only, independent of model size."""
    grid, strides = [], []
    for stride in (8, 16, 32):
        x, y = np.meshgrid(np.arange(size // stride), np.arange(size // stride))
        grid.append(np.stack((x, y), 2).reshape(-1, 2))
        strides.append(np.full(((size // stride) ** 2, 1), stride))
    values = raw[0].copy()
    if values.shape != (sum(len(g) for g in grid), 85) or not np.isfinite(values).all():
        raise ValueError('candidate output contract mismatch')
    values[:, :2] = (values[:, :2] + np.concatenate(grid)) * np.concatenate(strides)
    values[:, 2:4] = np.exp(values[:, 2:4]) * np.concatenate(strides)
    scores = values[:, 4] * values[:, 5]
    keep = scores >= .1
    values, scores = values[keep], scores[keep]
    boxes = np.column_stack((values[:, :2] - values[:, 2:4] / 2,
                             values[:, :2] + values[:, 2:4] / 2)) / scale
    if not np.isfinite(boxes).all():
        raise ValueError('nonfinite candidate boxes')
    return boxes, scores


def _verify_network_denied():
    import socket
    probe = socket.socket()
    try:
        try:
            probe.bind(('127.0.0.1', 0))
        except PermissionError:
            return
        raise ValueError('network sandbox not enforced')
    finally:
        probe.close()


def _run(args, *, batch_detector=None):
    """``batch_detector``, if given, replaces per-zone detection for one frame.

    It must be ``callback(engine, image, cfg['zones']) -> [Detections, Detections]``,
    called at most once per valid sampled frame, after the lens/sample_time
    checks and before any tracker update for that frame. Results are mapped
    back to zones by the order of the ``cfg['zones']`` list passed to the
    callback (so a reversed zone order in config is handled automatically).
    Only the ``baseline`` candidate with exactly 2 unique zones may use this.
    """
    _verify_network_denied()  # Also reject direct use of the private worker flag.
    from tools import ft_count as f
    from tools.ft_count_zones import load_zones_config
    from tools.ft_day_count import Engine, config_digest
    from tools.ft_day_summary import atomic_write
    import onnxruntime as ort

    root = Path(args.output)
    f._outside_repo(root)
    if root.exists():
        raise ValueError('use a new experiment output directory')
    f._validate_input_file(args.input)
    f._validate_input_file(args.reference)
    cfg = load_zones_config(args.config)
    if any(z['config'].get('sample_fps', 5) != 5 for z in cfg['zones']):
        raise ValueError('experiments require unchanged 5fps')
    zone_ids = [z['id'] for z in cfg['zones']]
    if batch_detector is not None:
        if not callable(batch_detector):
            raise ValueError('batch detector must be callable')
        if args.candidate != 'baseline':
            raise ValueError('batch detector requires the baseline candidate')
        if len(zone_ids) != 2 or len(set(zone_ids)) != 2:
            raise ValueError('batch detector requires exactly 2 unique zones')
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    os.umask(0o077)
    os.environ['MPLCONFIGDIR'] = str(root / 'cache')
    repo = Path(__file__).resolve().parent.parent
    name, expected, size = MODELS[args.candidate]
    model = repo / '.venv/ft-models' / name
    if model.is_symlink() or not model.is_file() or model.stat().st_size > 40 * 1024**2:
        raise ValueError('invalid candidate model file')
    model_hash = f._file_sha256(model)
    if model_hash != expected:
        raise ValueError('candidate model hash mismatch')
    begin = time.monotonic()
    engine = Engine(root, cfg, repo / '.venv/ft-models/yolox_s.onnx', args.reference)
    if args.candidate not in ('baseline', 'joint'):
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        engine.net = ort.InferenceSession(str(model), sess_options=options, providers=['CPUExecutionProvider'])
        engine.input_name = engine.net.get_inputs()[0].name
    expected_shape = [2, 3, size, size] if batch_detector is not None else [1, 3, size, size]
    if engine.net.get_inputs()[0].shape != expected_shape:
        raise ValueError('candidate input contract mismatch')
    setup_s = time.monotonic() - begin
    cv, np, sv = engine.cv, engine.np, engine.sv
    inference_s = 0.0
    calls = 0
    images = 0

    def detect(image, zcfg):
        nonlocal inference_s, calls, images
        start = time.monotonic()
        if args.candidate in ('baseline', 'joint', 'int8', 'int8bq'):
            detections = engine.detect(image, zcfg)
            calls += 1
            images += 1
        else:
            h, w = image.shape[:2]
            crop = zcfg.get('crop', [0, 0, 1, 1])
            regions = [crop]
            if args.candidate == 'nano_tiles':
                cw, ch = crop[2] - crop[0], crop[3] - crop[1]
                regions = [[crop[0] + x * .4 * cw, crop[1] + y * .4 * ch,
                            crop[0] + (x * .4 + .6) * cw, crop[1] + (y * .4 + .6) * ch]
                           for y in (0, 1) for x in (0, 1)]
            all_boxes, all_scores = [], []
            for region in regions:
                x, y, x2, y2 = int(region[0] * w), int(region[1] * h), int(region[2] * w), int(region[3] * h)
                part = image[y:y2, x:x2]
                scale = min(size / part.shape[0], size / part.shape[1])
                nh, nw = int(part.shape[0] * scale), int(part.shape[1] * scale)
                canvas = np.full((size, size, 3), 114, dtype=np.uint8)
                canvas[:nh, :nw] = cv.resize(part, (nw, nh), interpolation=cv.INTER_LINEAR)
                # Published Nano/Tiny assets use current upstream raw BGR,
                # not the historical tag's legacy RGB/ImageNet preprocessing.
                blob = np.ascontiguousarray(canvas.transpose(2, 0, 1)[None], dtype=np.float32)
                boxes, scores = _decode(np, engine.net.run(None, {engine.input_name: blob})[0], scale, size)
                calls += 1
                images += 1
                boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]] + x, 0, w)
                boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]] + y, 0, h)
                all_boxes.append(boxes)
                all_scores.append(scores)
            boxes, scores = np.concatenate(all_boxes), np.concatenate(all_scores)
            if len(boxes):
                ids = cv.dnn.NMSBoxes(np.column_stack((boxes[:, :2], boxes[:, 2:] - boxes[:, :2])).tolist(),
                                     scores.tolist(), f.DET_SCORE_FLOOR, f.NMS_IOU)
                ids = np.array(ids).reshape(-1) if len(ids) else np.array([], dtype=int)
                boxes, scores = boxes[ids], scores[ids]
            detections = sv.Detections(xyxy=boxes.astype(np.float32), confidence=scores.astype(np.float32),
                                       class_id=np.zeros(len(boxes), dtype=int))
        inference_s += time.monotonic() - start
        return detections

    crops = [z['config'].get('crop', [0, 0, 1, 1]) for z in cfg['zones']]
    union = [min(c[0] for c in crops), min(c[1] for c in crops),
             max(c[2] for c in crops), max(c[3] for c in crops)]
    source_hash = f._file_sha256(args.input)
    cap = cv.VideoCapture(str(args.input))
    events = []
    frames = 0
    start = time.monotonic()
    try:
        fps = cap.get(cv.CAP_PROP_FPS)
        count = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
        if not .1 < fps <= 120 or not 0 < count / fps <= 182:
            raise ValueError('invalid source clock')
        limit = min(count, int(math.ceil(args.seconds * fps)))
        stride = max(1, int(round(fps / 5)))
        engine.reset(0)
        for index in range(limit):
            if time.monotonic() - start > 1800:
                raise ValueError('experiment deadline exceeded')
            if index % stride:
                if not cap.grab():
                    raise ValueError('incomplete source decode')
                continue
            ok, image = cap.read()
            if not ok:
                raise ValueError('incomplete source decode')
            if index == 0 and not engine.verify_lens(image):
                raise ValueError('Fixed Lens verification failed')
            at = sample_time(index, fps, min(args.seconds, count / fps))
            if at is None:
                break
            h, w = image.shape[:2]
            zone_detections = None
            shared = None
            if batch_detector is not None:
                hook_start = time.monotonic()
                results = batch_detector(engine, image, cfg['zones'])
                inference_s += time.monotonic() - hook_start
                calls += 1
                images += 2
                if not isinstance(results, list) or len(results) != 2:
                    raise ValueError('batch detector must return exactly 2 detections')
                for result in results:
                    if not isinstance(result, sv.Detections):
                        raise ValueError('batch detector must return Detections')
                    n = len(result.xyxy)
                    if (result.xyxy.shape != (n, 4) or result.confidence is None
                            or result.confidence.shape != (n,)
                            or result.class_id is None or result.class_id.shape != (n,)
                            or not np.isfinite(result.xyxy).all()
                            or not np.isfinite(result.confidence).all()
                            or not ((result.confidence >= 0) & (result.confidence <= 1)).all()
                            or not (result.class_id == 0).all()):
                        raise ValueError('invalid batch detections')
                zone_detections = dict(zip(zone_ids, results))
            else:
                shared = detect(image, {'crop': union}) if args.candidate == 'joint' else None
            for zone in cfg['zones']:
                if zone_detections is not None:
                    detections = zone_detections[zone['id']]
                elif shared is None:
                    detections = detect(image, zone['config'])
                else:
                    c = zone['config'].get('crop', [0, 0, 1, 1])
                    centers = (shared.xyxy[:, :2] + shared.xyxy[:, 2:]) / 2
                    mask = ((centers[:, 0] >= c[0] * w) & (centers[:, 0] < c[2] * w) &
                            (centers[:, 1] >= c[1] * h) & (centers[:, 1] < c[3] * h))
                    detections = shared[mask]
                tracked = engine.trackers[zone['id']].update_with_detections(detections)
                for box, track_id in zip(tracked.xyxy, tracked.tracker_id):
                    if track_id is None:
                        continue
                    normalized = [round(float(v), 4) for v in (box[0] / w, box[1] / h, box[2] / w, box[3] / h)]
                    point = [round(float((box[0] + box[2]) / 2 / w), 4),
                             round(float(((box[1] + box[3]) / 2 if zone['config'].get('anchor') == 'center' else box[3]) / h), 4)]
                    events.extend(engine.stream.update(zone['id'], int(track_id), point, at, normalized, source_hash))
                    if len(events) > 10000:
                        raise ValueError('experiment event quota exceeded')
            frames += 1
    finally:
        cap.release()
    elapsed = time.monotonic() - start
    report = dict(schema_version=1, experiment_only=True, production_eligible=False,
                  accuracy_status='NOT_VERIFIED', candidate=args.candidate, model_sha256=model_hash,
                  preprocessing='upstream_raw_bgr' if args.candidate in ('nano', 'nano_tiles', 'tiny') else 'pinned_zoo_rgb',
                  input_sha256=source_hash, config_sha256=config_digest(cfg), runtime_sha256=engine.runtime_digest,
                  reference_sha256=engine.reference_sha256,
                  seconds=min(args.seconds, count / fps), frames=frames, inference_calls=calls,
                  inference_images=images,
                  setup_seconds=round(setup_s, 6), elapsed_seconds=round(elapsed, 6),
                  inference_seconds=round(inference_s, 6), totals=event_totals(events), events=events)
    atomic_write(root / 'experiment.json', json.dumps(report, allow_nan=False, separators=(',', ':')) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'events'}, allow_nan=False), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', choices=tuple(MODELS), required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--reference', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--seconds', type=int, default=180, choices=range(1, 181))
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.worker:
        if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').is_file():
            parser.error('macOS deny-network sandbox required')
        command = ['/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny network*)',
                   sys.executable, '-m', 'tools.ft_perf', *(sys.argv[1:] if argv is None else argv), '--worker']
        return subprocess.call(command, timeout=1900)
    try:
        _run(args)
        return 0
    except Exception as exc:
        print(json.dumps(dict(status='BLOCKED', reason='OFFLINE_EXPERIMENT_FAILED', kind=type(exc).__name__)), flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
