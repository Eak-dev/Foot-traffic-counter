#!/usr/bin/env python3
"""Two finite-gate front-shop lane corridors sharing one track stream.

Pure stdlib, offline, no detector/inference. Reuses :mod:`tools.ft_count`
geometry helpers and config validation; adds a second, independent gate
("lane") so a near and a far walking corridor can each be measured from the
same (track_id, footpoint, time) stream while a single same-track cooldown
reduces duplicate same-track gate events near a shared edge. Temporary IDs
are not person identities; ID switches remain a limitation.
"""
from __future__ import annotations

import math
import re

from tools import ft_count
from tools.ft_count import (
    ValidationError,
    _require,
    _is_finite_point,
    _point_in_polygon,
    _segments_intersect,
    _side_of_line,
    CrossingCounter,
    MAX_RETAINED_TRACKS,
    MAX_TRACK_GAP_S,
    DEFAULT_DEADBAND,
)

TOOL_NAME = "ft_lane_counter"

LANE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_NAME_LEN = 60

# LaneCrossingCounter tuning (per-lane hysteresis / anti-jitter).
ARM_CONSECUTIVE = 1
CONFIRM_CONSECUTIVE = 2
MIN_LANE_DISPLACEMENT = 0.025
LANE_COOLDOWN_S = 2.0
IMPLAUSIBLE_STEP = 0.12
IMPLAUSIBLE_STEP_WINDOW_S = 0.4


# --------------------------------------------------------------------------
# Lane config validation
# --------------------------------------------------------------------------

def _distance_point_to_polygon_boundary(point, polygon):
    x, y = point
    best = math.inf
    n = len(polygon)
    for i in range(n):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        if length2 < 1e-18:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length2))
        px, py = ax + t * dx, ay + t * dy
        best = min(best, math.hypot(x - px, y - py))
    return best


def _point_in_or_on_polygon(point, polygon, eps=1e-6):
    if _point_in_polygon(point, polygon):
        return True
    return _distance_point_to_polygon_boundary(point, polygon) <= eps


def _gate_within_polygon(line, polygon):
    """Check all edge-intersection intervals, including arbitrarily thin notches."""
    a, b = line
    d = (b[0]-a[0], b[1]-a[1])
    cross = lambda u, v: u[0]*v[1]-u[1]*v[0]
    cuts = [0.0, 1.0]
    for p, q in zip(polygon, polygon[1:]+polygon[:1]):
        e = (q[0]-p[0], q[1]-p[1])
        z = (p[0]-a[0], p[1]-a[1])
        den = cross(d, e)
        if abs(den) > 1e-15:
            t, u = cross(z, e)/den, cross(z, d)/den
            if -1e-12 <= t <= 1+1e-12 and -1e-12 <= u <= 1+1e-12:
                cuts.append(max(0.0,min(1.0,t)))
        elif abs(cross(z,d)) < 1e-12:
            size = d[0]*d[0]+d[1]*d[1]
            for v in (p,q):
                t = ((v[0]-a[0])*d[0]+(v[1]-a[1])*d[1])/size
                if 0 <= t <= 1: cuts.append(t)
    cuts = sorted(set(cuts))
    for t in cuts+[(x+y)/2 for x,y in zip(cuts,cuts[1:])]:
        if not _point_in_or_on_polygon((a[0]+t*d[0],a[1]+t*d[1]),polygon,eps=1e-10):
            return False
    return True


def validate_lanes(lanes, base_config):
    """Validate exactly two lane objects sharing one base detector config.

    Each lane is {id, name, color, roi, line}. ``roi``/``line`` are validated
    with ``ft_count.validate_config`` against ``base_config`` (with roi/line
    replaced), plus: every polygon vertex lies inside the base crop, and the
    entire gate segment lies inside or on the polygon (refusing an ambiguous
    gate that would cross outside its own lane).
    """
    _require(isinstance(base_config, dict), "base_config must be an object")
    _require(isinstance(lanes, list) and len(lanes) == 2, "lanes must contain exactly two lane objects")

    ids, names, colors = set(), set(), set()
    for lane in lanes:
        _require(isinstance(lane, dict), "lane must be an object")
        _require(set(lane) == {"id", "name", "color", "roi", "line"}, "unknown lane field")

        lid = lane.get("id")
        _require(isinstance(lid, str) and bool(LANE_ID_RE.fullmatch(lid)), "invalid lane id")
        _require(lid not in ids, "duplicate lane id")
        ids.add(lid)

        name = lane.get("name")
        _require(
            isinstance(name, str)
            and 0 < len(name) <= MAX_NAME_LEN
            and name.strip() == name
            and all(ord(c) >= 32 for c in name),
            "invalid lane name",
        )
        _require(name not in names, "duplicate lane name")
        names.add(name)

        color = lane.get("color")
        _require(isinstance(color, str) and bool(COLOR_RE.fullmatch(color)), "invalid lane color")
        _require(color.lower() not in colors, "duplicate lane color")
        colors.add(color.lower())

        roi = lane.get("roi")
        line = lane.get("line")
        cfg = dict(base_config)
        cfg["roi"] = roi
        cfg["line"] = line
        ft_count.validate_config(cfg)

        crop = cfg.get("crop", [0, 0, 1, 1])
        for p in roi:
            _require(
                crop[0] <= p[0] <= crop[2] and crop[1] <= p[1] <= crop[3],
                "lane polygon vertex outside crop",
            )

        _require(_gate_within_polygon(line, roi), "lane gate must lie inside its polygon")

    return lanes


# --------------------------------------------------------------------------
# LaneCrossingCounter core
# --------------------------------------------------------------------------

def _fresh_lane_state():
    return {
        "armed_side": None,
        "anchor": None,
        "run_side": None,
        "run_count": 0,
        "pending_side": None,
        "pending_count": 0,
    }


class LaneCrossingCounter:
    """Counts passages across two finite gates sharing one track stream.

    Each lane keeps its own ROI-gated hysteresis state per track (1
    stable-side observation to arm, then 2 consecutive
    opposite-stable-side observations to confirm a crossing whose evidence
    must properly intersect that lane's finite gate). A single same-track
    cooldown is shared across both lanes so one real passage near a shared
    gate edge is not double-counted; it does not suppress other track ids.
    """

    def __init__(self, lanes, deadband=0.012):
        _require(isinstance(lanes, list) and len(lanes) == 2, "lanes must contain exactly two lane objects")
        self.lanes = []
        ids = set()
        for lane in lanes:
            _require(
                isinstance(lane, dict) and set(lane) >= {"id", "roi", "line"},
                "invalid lane object",
            )
            lid = lane["id"]
            _require(isinstance(lid, str) and bool(LANE_ID_RE.fullmatch(lid)), "invalid lane id")
            _require(lid not in ids, "duplicate lane id")
            ids.add(lid)
            # Reuse CrossingCounter's geometry validation (finite/normalized
            # line and roi, non-degenerate, non-self-intersecting, deadband).
            CrossingCounter(lane["line"], lane["roi"], deadband)
            self.lanes.append({
                "id": lid,
                "roi": [tuple(p) for p in lane["roi"]],
                "line": (tuple(lane["line"][0]), tuple(lane["line"][1])),
            })
        self.deadband = deadband
        self._tracks = {}
        self.events = []
        self.count = 0
        self.lane_counts = {lane["id"]: 0 for lane in self.lanes}

    def _signed_side(self, point, line):
        d = _side_of_line(line[0], line[1], point) / math.dist(*line)
        if abs(d) < self.deadband:
            return 0
        return 1 if d > 0 else -1

    def update(self, track_id, point, time_seconds):
        if not isinstance(track_id, (int, str)) or isinstance(track_id, bool):
            raise ValidationError("invalid track id")
        if type(time_seconds) not in (int, float) or not math.isfinite(time_seconds) or time_seconds < 0:
            raise ValidationError("time_seconds must be finite and nonnegative")
        if not _is_finite_point(point) or any(not 0 <= c <= 1 for c in point):
            raise ValidationError("footpoint must be normalized and finite")

        self._evict_stale(time_seconds)

        st = self._tracks.get(track_id)
        if st is not None and time_seconds <= st["last_time"]:
            raise ValidationError("track times must increase")

        if st is None:
            st = {
                "last_time": time_seconds,
                "last_point": tuple(point),
                "last_cross_time": -math.inf,
                "lanes": {lane["id"]: _fresh_lane_state() for lane in self.lanes},
            }
            self._tracks[track_id] = st
        else:
            gap = time_seconds - st["last_time"]
            jump = math.dist(st["last_point"], point)
            if gap > MAX_TRACK_GAP_S or (gap <= IMPLAUSIBLE_STEP_WINDOW_S and jump > IMPLAUSIBLE_STEP):
                st["lanes"] = {lane["id"]: _fresh_lane_state() for lane in self.lanes}
            st["last_time"] = time_seconds
            st["last_point"] = tuple(point)

        for lane in self.lanes:
            if not _point_in_polygon(point, lane["roi"]):
                st["lanes"][lane["id"]] = _fresh_lane_state()
                continue
            side = self._signed_side(point, lane["line"])
            self._process_lane(lane, st["lanes"][lane["id"]], side, point, time_seconds, st, track_id)

        self._bound_tracks()

    def _process_lane(self, lane, ls, side, point, t, st, track_id):
        if side == 0:
            return  # deadband: preserve armed anchor and pending progress
        if ls["armed_side"] is None:
            if ls["run_side"] == side:
                ls["run_count"] += 1
            else:
                ls["run_side"] = side
                ls["run_count"] = 1
            if ls["run_count"] >= ARM_CONSECUTIVE:
                ls["armed_side"] = side
                ls["anchor"] = tuple(point)
                ls["run_side"] = None
                ls["run_count"] = 0
            return
        if side == ls["armed_side"]:
            ls["anchor"] = tuple(point)
            ls["pending_side"] = None
            ls["pending_count"] = 0
            return
        # candidate opposite-side evidence
        if ls["pending_side"] == side:
            ls["pending_count"] += 1
        else:
            ls["pending_side"] = side
            ls["pending_count"] = 1
        if ls["pending_count"] >= CONFIRM_CONSECUTIVE:
            anchor = ls["anchor"]
            evidence_to = tuple(point)
            evidence_time = t
            if (
                math.dist(anchor, evidence_to) >= MIN_LANE_DISPLACEMENT
                and _segments_intersect(anchor, evidence_to, lane["line"][0], lane["line"][1])
                and evidence_time - st["last_cross_time"] >= LANE_COOLDOWN_S
            ):
                self.events.append({
                    "lane_id": lane["id"],
                    "track_id": track_id,
                    "time_seconds": evidence_time,
                    "direction": "forward" if side > 0 else "backward",
                    "evidence": {"from": list(anchor), "to": list(evidence_to)},
                })
                self.lane_counts[lane["id"]] += 1
                self.count += 1
                st["last_cross_time"] = evidence_time
            ls["armed_side"] = side
            ls["anchor"] = tuple(point)
            ls["pending_side"] = None
            ls["pending_count"] = 0

    def _evict_stale(self, now):
        stale = [tid for tid, s in self._tracks.items() if now - s["last_time"] > MAX_TRACK_GAP_S * 5]
        for tid in stale:
            del self._tracks[tid]

    def _bound_tracks(self):
        if len(self._tracks) <= MAX_RETAINED_TRACKS:
            return
        oldest = sorted(self._tracks.items(), key=lambda kv: kv[1]["last_time"])
        for tid, _ in oldest[: len(self._tracks) - MAX_RETAINED_TRACKS]:
            del self._tracks[tid]
