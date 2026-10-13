#!/usr/bin/env python3
"""Offline people-passage counter (local-only, no network).

Pure-stdlib CLI shell plus a pure-Python :class:`CrossingCounter` core that
counts line passages from (track_id, normalized footpoint, time) updates.
All third-party imports (cv2, numpy, supervision, onnxruntime) are deferred into
``_run_pipeline`` so this module imports and unit-tests cleanly under plain
Python 3.9 stdlib with no extra packages installed.

Model contract (pinned, independent re-implementation, not copied code):
opencv/opencv_zoo @ 47534e27c9851bb1128ccc0102f1145e27f23f98,
models/object_detection_yolox, YOLOX_s 640x640, Apache-2.0. See
docs/THIRD_PARTY_NOTICES.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import shutil
import subprocess
from pathlib import Path
import sys
import time

TOOL_NAME = "ft_count"

MODEL_SHA256 = (
    "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"
)

MAX_INPUT_BYTES = 100 * 1024 * 1024
MAX_DURATION_S = 180
DURATION_TOLERANCE_S = 2
MAX_SAMPLE_FPS = 15
DEFAULT_SAMPLE_FPS = 5
DEFAULT_CONFIDENCE = 0.25
DEFAULT_DEADBAND = 0.015
JOB_TIME_BUDGET_S = 1200
MAX_TRACKS_JSONL_BYTES = 64 * 1024 * 1024

DET_SCORE_FLOOR = 0.1
NMS_IOU = 0.5
INPUT_SIZE = 640
STRIDES = (8, 16, 32)

# CrossingCounter tuning (hysteresis / anti-jitter).
MIN_TRACK_AGE_UPDATES = 3
MIN_DISPLACEMENT = 0.01
CROSS_COOLDOWN_S = 1.0
MAX_TRACK_GAP_S = 2.0
MAX_RETAINED_TRACKS = 500


class ValidationError(Exception):
    """Raised for any input/config/schema/geometry problem. Message is safe to print."""


def _redact(_exc: BaseException) -> str:
    return "internal error"


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def _is_finite_point(p):
    return (
        isinstance(p, (list, tuple))
        and len(p) == 2
        and all(type(c) in (int, float) and math.isfinite(c) for c in p)
    )


def _side_of_line(a, b, p):
    """Signed area / cross product sign: which side of segment a->b point p is on."""
    ax, ay = a
    bx, by = b
    px, py = p
    return (bx - ax) * (py - ay) - (by - ay) * (px - ax)


def _segments_intersect(p1, p2, p3, p4):
    """True if segment p1-p2 (track path) properly crosses segment p3-p4 (the line)."""
    d1 = _side_of_line(p3, p4, p1)
    d2 = _side_of_line(p3, p4, p2)
    d3 = _side_of_line(p1, p2, p3)
    d4 = _side_of_line(p1, p2, p4)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True
    return False


def _point_in_polygon(point, polygon):
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and (
            x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-15) + x1
        ):
            inside = not inside
    return inside


def _polygon_area2(polygon):
    area = 0.0
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area


# --------------------------------------------------------------------------
# CrossingCounter core (pure Python, no third-party deps)
# --------------------------------------------------------------------------

class CrossingCounter:
    """Counts line passages from a stream of (track_id, footpoint, time) updates.

    The selected bbox anchor (bottom-center or center) is normalized in [0, 1]^2. Only updates whose point
    falls inside ``roi`` (if given) are considered. A crossing is counted
    only once genuine stable-side evidence exists on both sides of the line,
    the track is old/displaced enough, and (per track) a cooldown has
    elapsed since its last counted crossing, so re-crosses after hysteresis
    are allowed but jitter at the line is not.
    """

    def __init__(self, line, roi=None, deadband=DEFAULT_DEADBAND):
        if not (isinstance(line, (list, tuple)) and len(line) == 2):
            raise ValidationError("line must have exactly two points")
        a, b = line
        if not (_is_finite_point(a) and _is_finite_point(b)):
            raise ValidationError("line endpoints must be finite [x, y] pairs")
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-9:
            raise ValidationError("line is degenerate (zero length)")
        if roi is not None:
            if not (isinstance(roi, (list, tuple)) and len(roi) >= 3):
                raise ValidationError("roi must be a polygon with at least 3 points")
            for p in roi:
                if not _is_finite_point(p):
                    raise ValidationError("roi vertices must be finite [x, y] pairs")
            if abs(_polygon_area2(roi)) < 1e-9:
                raise ValidationError("roi polygon is degenerate (zero area)")
        if any(not 0 <= v <= 1 for p in line for v in p):
            raise ValidationError("line must be normalized")
        if type(deadband) not in (int, float) or not math.isfinite(deadband) or not 0 <= deadband <= .2:
            raise ValidationError("invalid deadband")
        if roi is not None:
            if len(roi) > 32 or len(set(map(tuple, roi))) != len(roi) or any(not 0 <= v <= 1 for p in roi for v in p):
                raise ValidationError("invalid roi")
            for i in range(len(roi)):
                for j in range(i+1, len(roi)):
                    if j == i+1 or (i == 0 and j == len(roi)-1): continue
                    if _segments_intersect(roi[i], roi[(i+1)%len(roi)], roi[j], roi[(j+1)%len(roi)]):
                        raise ValidationError("self-intersecting roi")
        self.line = (tuple(a), tuple(b))
        self.roi = [tuple(p) for p in roi] if roi is not None else None
        self.deadband = deadband
        self._tracks = {}
        self.events = []
        self.count = 0

    def _in_roi(self, point):
        if self.roi is None:
            return True
        return _point_in_polygon(point, self.roi)

    def _signed_side(self, point):
        d = _side_of_line(self.line[0], self.line[1], point) / math.dist(*self.line)
        if abs(d) < self.deadband:
            return 0
        return 1 if d > 0 else -1

    def update(self, track_id, point, time_seconds):
        if not _is_finite_point(point) or any(not 0 <= c <= 1 for c in point):
            raise ValidationError("footpoint must be normalized and finite")
        if type(time_seconds) not in (int, float) or not math.isfinite(time_seconds) or time_seconds < 0:
            raise ValidationError("time_seconds must be finite and nonnegative")
        if not isinstance(track_id, (int, str)) or isinstance(track_id, bool):
            raise ValidationError("invalid track id")
        self._evict_stale(time_seconds)
        st = self._tracks.get(track_id)
        if st and time_seconds <= st['last_time']:
            raise ValidationError("track times must increase")
        if not self._in_roi(point):
            self._tracks.pop(track_id, None)
            return
        side = self._signed_side(point)
        if st is None or time_seconds - st['last_time'] > MAX_TRACK_GAP_S:
            self._tracks[track_id] = {'last_time': time_seconds, 'anchor': point,
                'side': side, 'updates': 1, 'last_cross_time': -math.inf}
            self._bound_tracks()
            return
        st['updates'] += 1
        st['last_time'] = time_seconds
        if side == 0:
            return  # preserve last confirmed point across the hysteresis band
        old_side, anchor = st['side'], st['anchor']
        if old_side and side != old_side and st['updates'] >= MIN_TRACK_AGE_UPDATES:
            if (math.dist(anchor, point) >= MIN_DISPLACEMENT
                    and _segments_intersect(anchor, point, *self.line)
                    and time_seconds - st['last_cross_time'] >= CROSS_COOLDOWN_S):
                self.count += 1
                self.events.append({'track_id': track_id, 'time_seconds': time_seconds,
                    'direction': 'forward' if side > 0 else 'backward',
                    'evidence': {'from': list(anchor), 'to': list(point)}})
                st['last_cross_time'] = time_seconds
        st['side'], st['anchor'] = side, point
        self._bound_tracks()

    def _evict_stale(self, now):
        stale = [
            tid for tid, s in self._tracks.items() if now - s["last_time"] > MAX_TRACK_GAP_S * 5
        ]
        for tid in stale:
            del self._tracks[tid]

    def _bound_tracks(self):
        if len(self._tracks) <= MAX_RETAINED_TRACKS:
            return
        oldest = sorted(self._tracks.items(), key=lambda kv: kv[1]["last_time"])
        for tid, _ in oldest[: len(self._tracks) - MAX_RETAINED_TRACKS]:
            del self._tracks[tid]


# --------------------------------------------------------------------------
# Config / schema validation
# --------------------------------------------------------------------------

def _require(cond, msg):
    if not cond:
        raise ValidationError(msg)


def load_config(path):
    try:
        st = os.lstat(path)
    except OSError:
        raise ValidationError("config not accessible")
    _require(stat.S_ISREG(st.st_mode), "config must be a regular file")
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read(65537)
        _require(len(raw) <= 65536, "config too large")
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationError("config is not valid JSON")
    _require(isinstance(cfg, dict), "config must be a JSON object")
    validate_config(cfg)
    return cfg


def validate_config(cfg):
    _require(set(cfg) <= {"fixed_lens_verified", "line", "roi", "sample_fps", "confidence", "deadband", "crop", "anchor"}, "unknown config field")
    _require(cfg.get("fixed_lens_verified") is True, "fixed_lens_verified must be true")

    _require(cfg.get('anchor', 'bottom_center') in ('bottom_center', 'center'), 'invalid anchor')
    crop = cfg.get('crop', [0, 0, 1, 1])
    _require(isinstance(crop, list) and len(crop) == 4 and all(type(x) in (int,float) and math.isfinite(x) and 0 <= x <= 1 for x in crop), "invalid crop")
    _require(crop[2]-crop[0] >= .1 and crop[3]-crop[1] >= .1, "crop too small")
    line = cfg.get("line")
    _require(isinstance(line, list) and len(line) == 2, "line must be [[x,y],[x,y]]")
    for p in line:
        _require(_is_finite_point(p), "line points must be finite [x, y]")
        for c in p:
            _require(0.0 <= c <= 1.0, "line coordinates must be normalized in [0,1]")
    a, b = line
    _require(math.hypot(b[0] - a[0], b[1] - a[1]) >= 1e-6, "line is degenerate")

    roi = cfg.get("roi")
    _require(
        isinstance(roi, list) and 3 <= len(roi) <= 32, "roi must be a polygon with >= 3 points"
    )
    for p in roi:
        _require(_is_finite_point(p), "roi points must be finite [x, y]")
        for c in p:
            _require(0.0 <= c <= 1.0, "roi coordinates must be normalized in [0,1]")
    _require(abs(_polygon_area2(roi)) >= 1e-6, "roi is degenerate")

    CrossingCounter(line, roi, cfg.get("deadband", DEFAULT_DEADBAND))

    sample_fps = cfg.get("sample_fps", DEFAULT_SAMPLE_FPS)
    _require(
        type(sample_fps) in (int, float) and 0 < sample_fps <= MAX_SAMPLE_FPS,
        "sample_fps out of range",
    )

    confidence = cfg.get("confidence", DEFAULT_CONFIDENCE)
    _require(
        type(confidence) in (int, float) and 0.0 < confidence <= 1.0,
        "confidence out of range",
    )

    deadband = cfg.get("deadband", DEFAULT_DEADBAND)
    _require(
        type(deadband) in (int, float) and 0.0 <= deadband <= 0.2,
        "deadband out of range",
    )


# --------------------------------------------------------------------------
# File safety helpers
# --------------------------------------------------------------------------

def _validate_input_file(path):
    try:
        lst = os.lstat(path)
    except OSError:
        raise ValidationError("input not accessible")
    _require(not stat.S_ISLNK(lst.st_mode), "input must not be a symlink")
    _require(stat.S_ISREG(lst.st_mode), "input must be a regular file")
    _require(lst.st_uid == os.getuid() and not lst.st_mode & 0o077, "input must be owner-only")
    _outside_repo(path)
    _require(lst.st_size <= MAX_INPUT_BYTES, "input exceeds size cap")
    _require(lst.st_size > 0, "input is empty")


def _validate_model_file(path):
    try:
        lst = os.lstat(path)
    except OSError:
        raise ValidationError("model not accessible")
    _require(not stat.S_ISLNK(lst.st_mode), "model must not be a symlink")
    _require(stat.S_ISREG(lst.st_mode), "model must be a regular file")
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    hexd = digest.hexdigest()
    _require(hexd == MODEL_SHA256, "model hash mismatch")
    return hexd


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _outside_repo(path):
    p = Path(os.path.abspath(path))
    root = Path(__file__).resolve().parent.parent
    _require(p != root and root not in p.parents, "media must stay outside repo")
    _require(not any(x.is_symlink() for x in (p, *p.parents)), "symlink path refused")


def _prepare_output_dir(path):
    _outside_repo(path)
    if os.path.lexists(path):
        raise ValidationError("output directory must not already exist")
    parent = os.path.dirname(os.path.abspath(path)) or "."
    if os.path.islink(parent):
        raise ValidationError("output parent must not be a symlink")
    old_umask = os.umask(0o077)
    try:
        os.mkdir(path, 0o700)
    finally:
        os.umask(old_umask)
    return os.path.abspath(path)


def _open_private(path):
    old_umask = os.umask(0o077)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    finally:
        os.umask(old_umask)
    return fd


# --------------------------------------------------------------------------
# YOLOX decode (pure numpy, used only inside _run_pipeline)
# --------------------------------------------------------------------------

def _decode_yolox(np_module, output, scale, conf_floor=DET_SCORE_FLOOR):
    """Decode raw [1, N, 85] YOLOX output into person boxes (x1,y1,x2,y2,score)."""
    np = np_module
    preds = output[0]
    grids = []
    expanded_strides = []
    hsizes = [INPUT_SIZE // s for s in STRIDES]
    wsizes = [INPUT_SIZE // s for s in STRIDES]
    for hsize, wsize, stride in zip(hsizes, wsizes, STRIDES):
        xv, yv = np.meshgrid(np.arange(wsize), np.arange(hsize))
        grid = np.stack((xv, yv), 2).reshape(1, -1, 2)
        grids.append(grid)
        shape = grid.shape[:2]
        expanded_strides.append(np.full((*shape, 1), stride))

    grids = np.concatenate(grids, 1)
    expanded_strides = np.concatenate(expanded_strides, 1)
    preds = preds[np.newaxis, ...]
    preds[..., :2] = (preds[..., :2] + grids) * expanded_strides
    preds[..., 2:4] = np.exp(preds[..., 2:4]) * expanded_strides

    preds = preds[0]
    obj = preds[:, 4]
    person_cls = preds[:, 5]
    scores = obj * person_cls
    keep = scores >= conf_floor
    boxes_cxcywh = preds[keep, :4]
    scores = scores[keep]

    cx, cy, w, h = (
        boxes_cxcywh[:, 0],
        boxes_cxcywh[:, 1],
        boxes_cxcywh[:, 2],
        boxes_cxcywh[:, 3],
    )
    x1 = (cx - w / 2) / scale
    y1 = (cy - h / 2) / scale
    x2 = (cx + w / 2) / scale
    y2 = (cy + h / 2) / scale
    boxes = np.stack([x1, y1, x2, y2], axis=1)
    return boxes, scores


def _letterbox(cv2_module, np_module, frame, size=INPUT_SIZE):
    cv2 = cv2_module
    np = np_module
    h, w = frame.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[:nh, :nw] = resized
    return canvas, scale


def _sanitize_stdout_report(report):
    return {
        "status": report.get("status", "ok"),
        "model_sha256": report.get("model_sha256"),
        "input_sha256": report.get("input_sha256"),
        "config_sha256": report.get("config_sha256"),
        "frames_processed": report.get("frames_processed", 0),
        "count": report.get("count", 0),
        "accuracy_status": "NOT_EVALUATED",
        "full_day_complete": False,
        "exit_code": report.get("exit_code", 0),
    }


def _run_pipeline(args, cfg, config_sha, deadline_monotonic):
    """Runs the full cv2/numpy/supervision pipeline. Imported lazily."""
    out_dir = _prepare_output_dir(args.output)
    os.umask(0o077)
    os.environ["MPLCONFIGDIR"] = out_dir

    import cv2
    import numpy as np
    import supervision as sv
    import onnxruntime as ort

    cv2.setNumThreads(4)

    model_sha = _validate_model_file(args.model)
    input_sha = _file_sha256(args.input)

    cap = cv2.VideoCapture(args.input)
    try:
        if not cap.isOpened():
            raise ValidationError("input could not be opened")

        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        _require(fps > 0.1, "could not determine input fps")
        _require(frame_count > 0, "could not determine input frame count")
        duration = frame_count / fps
        _require(
            duration <= MAX_DURATION_S + DURATION_TOLERANCE_S,
            "input duration exceeds cap",
        )

        sample_fps = min(cfg.get("sample_fps", DEFAULT_SAMPLE_FPS), MAX_SAMPLE_FPS)
        stride = max(1, int(round(fps / sample_fps)))
        confidence = cfg.get("confidence", DEFAULT_CONFIDENCE)
        deadband = cfg.get("deadband", DEFAULT_DEADBAND)

        counter = CrossingCounter(cfg["line"], roi=cfg["roi"], deadband=deadband)
        tracker = sv.ByteTrack(
            track_activation_threshold=confidence,
            lost_track_buffer=90,
            minimum_matching_threshold=0.99,
            frame_rate=max(1, int(round(fps / stride))),
            minimum_consecutive_frames=1,
        )

        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        net = ort.InferenceSession(args.model, sess_options=options, providers=['CPUExecutionProvider'])
        input_name = net.get_inputs()[0].name

        annotated_path = os.path.join(out_dir, "annotated.mp4")
        tracks_path = os.path.join(out_dir, "tracks.jsonl")
        tracks_fd = _open_private(tracks_path)
        tracks_file = os.fdopen(tracks_fd, "w", encoding="utf-8")
        tracks_bytes_written = 0

        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(annotated_path, fourcc, fps / stride, (src_w, src_h))
        _require(writer.isOpened(), "video writer failed")
        try:
            os.chmod(annotated_path, 0o600)
        except OSError:
            pass

        frames_processed = 0
        frame_index = -1
        last_decoded_ok = True
        while True:
            if time.monotonic() > deadline_monotonic:
                raise ValidationError("job time budget exceeded")
            ok, frame = cap.read()
            if not ok:
                last_decoded_ok = frame_index + 1 >= frame_count - 1
                break
            frame_index += 1
            _require(frame_index <= math.ceil(frame_count) + 2, "unexpected extra frames")
            if frame_index % 30 == 0:
                _require(shutil.disk_usage(out_dir).free >= 10 * 1024**3, "disk reserve exhausted")
                _require(sum(p.stat().st_size for p in Path(out_dir).iterdir() if p.is_file()) <= 512 * 1024**2, "output quota exhausted")
            if frame_index % stride != 0:
                continue

            crop = cfg.get('crop', [0,0,1,1])
            cx1, cy1 = int(crop[0]*src_w), int(crop[1]*src_h)
            cx2, cy2 = int(crop[2]*src_w), int(crop[3]*src_h)
            rgb = cv2.cvtColor(frame[cy1:cy2,cx1:cx2], cv2.COLOR_BGR2RGB)
            canvas, scale = _letterbox(cv2, np, rgb)
            blob = canvas.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)
            output = net.run(None, {input_name: blob})[0]
            boxes, scores = _decode_yolox(np, output, scale)
            boxes[:, [0,2]] += cx1
            boxes[:, [1,3]] += cy1

            h, w = frame.shape[:2]
            if boxes.shape[0]:
                boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, w)
                boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, h)
                idxs = cv2.dnn.NMSBoxes(
                    np.column_stack((boxes[:, :2], boxes[:, 2:] - boxes[:, :2])).tolist(), scores.tolist(), DET_SCORE_FLOOR, NMS_IOU
                )
                idxs = np.array(idxs).reshape(-1) if len(idxs) else np.array([], dtype=int)
                boxes = boxes[idxs]
                scores = scores[idxs]

            detections = sv.Detections(
                xyxy=boxes.astype(np.float32) if boxes.shape[0] else np.zeros((0, 4), dtype=np.float32),
                confidence=scores.astype(np.float32) if scores.shape[0] else np.zeros((0,), dtype=np.float32),
                class_id=np.zeros((boxes.shape[0],), dtype=int),
            )
            tracked = tracker.update_with_detections(detections)
            frame_time = frame_index / fps

            frame_rows = []
            for i in range(len(tracked)):
                tid = tracked.tracker_id[i]
                if tid is None:
                    continue
                x1, y1, x2, y2 = tracked.xyxy[i]
                foot = (float((x1 + x2) / 2.0 / w), float(((y1+y2)/2 if cfg.get("anchor") == "center" else y2) / h))
                counter.update(int(tid), foot, frame_time)
                cv2.circle(frame, (int(foot[0]*w),int(foot[1]*h)),5,(0,200,255),-1)
                frame_rows.append(
                    {
                        "track_id": int(tid),
                        "box": [round(float(v), 4) for v in (x1 / w, y1 / h, x2 / w, y2 / h)],
                        "foot": [round(foot[0], 4), round(foot[1], 4)],
                        "confidence": round(float(tracked.confidence[i]), 4),
                    }
                )
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 200, 0), 2)
                cv2.putText(
                    frame, str(int(tid)), (int(x1), max(0, int(y1) - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 0), 2,
                )

            row = json.dumps({"frame": frame_index, "time_seconds": round(frame_time, 3), "tracks": frame_rows, "detections": [{"box": [float(b[0]/w),float(b[1]/h),float(b[2]/w),float(b[3]/h)], "confidence": float(sc)} for b,sc in zip(boxes,scores)]})
            if tracks_bytes_written + len(row) + 1 <= MAX_TRACKS_JSONL_BYTES:
                tracks_file.write(row + "\n")
                tracks_bytes_written += len(row) + 1
            else:
                raise ValidationError("track log quota exhausted")

            roi_px = [(int(p[0] * w), int(p[1] * h)) for p in cfg["roi"]]
            line_px = [(int(p[0] * w), int(p[1] * h)) for p in cfg["line"]]
            cv2.polylines(frame, [np.array(roi_px)], True, (255, 160, 0), 2)
            cv2.line(frame, line_px[0], line_px[1], (0, 0, 255), 2)
            cv2.rectangle(frame, (w-700,10), (w-10,125), (20,20,20), -1)
            cv2.putText(frame, "Passages: %d" % counter.count, (w-675,60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255,255,255), 3)
            cv2.putText(frame, "PILOT / line crossings", (w-675,105),
                        cv2.FONT_HERSHEY_SIMPLEX, .9, (200,220,255), 2)
            writer.write(frame)
            frames_processed += 1

        tracks_file.close()
        writer.release()
        _require(last_decoded_ok, "input decode did not complete fully")
        _require(frames_processed > 0, "no frames processed")
    finally:
        cap.release()
        if "writer" in locals(): writer.release()
        if "tracks_file" in locals(): tracks_file.close()

    report = {
        "status": "ok",
        "model_sha256": model_sha,
        "input_sha256": input_sha,
        "config_sha256": config_sha,
        "frames_processed": frames_processed,
        "count": counter.count,
        "direction_counts": {d: sum(e["direction"] == d for e in counter.events) for d in ("forward", "backward")},
        "duration_seconds": duration,
        "sample_fps": fps / stride,
        "accuracy_status": "NOT_EVALUATED",
        "full_day_complete": False,
        "exit_code": 0,
    }
    report_path = os.path.join(out_dir, "report.json")
    rfd = _open_private(report_path)
    with os.fdopen(rfd, "w", encoding="utf-8") as fh:
        json.dump(
            {**report, "events": counter.events},
            fh,
        )
    from tools.ft_count_report import write_page
    write_page(out_dir, {**report, "events": counter.events})
    return report


def build_arg_parser():
    p = argparse.ArgumentParser(prog="ft_count")
    p.add_argument("--input", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--_network-sandbox", action="store_true", help=argparse.SUPPRESS)
    return p


def main(argv=None):
    deadline = time.monotonic() + JOB_TIME_BUDGET_S
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        if not args._network_sandbox:
            _require(sys.platform == "darwin" and os.path.isfile('/usr/bin/sandbox-exec'), "network sandbox required")
            command = ['/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny network*)',
                       sys.executable, '-m', 'tools.ft_count', '--_network-sandbox',
                       '--input', args.input, '--model', args.model, '--config', args.config, '--output', args.output]
            return subprocess.call(command)
        # Verify enforcement even if someone supplies the private flag directly.
        import socket
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try: probe.bind(('127.0.0.1', 0))
            finally: probe.close()
        except PermissionError:
            pass
        else:
            raise ValidationError("network sandbox not enforced")
        _require("://" not in args.input and not args.input.isdigit(), "input must be a local file path")
        _validate_input_file(args.input)
        cfg = load_config(args.config)
        config_sha = _file_sha256(args.config)
        report = _run_pipeline(args, cfg, config_sha, deadline)
        print(json.dumps(_sanitize_stdout_report(report)))
        return 0
    except ValidationError as exc:
        print(json.dumps({"status": "error", "message": str(exc), "exit_code": 2}))
        return 2
    except Exception as exc:  # noqa: BLE001 - must never leak details
        print(json.dumps({"status": "error", "message": _redact(exc), "exit_code": 1}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
