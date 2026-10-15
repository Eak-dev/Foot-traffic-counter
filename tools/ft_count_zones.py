#!/usr/bin/env python3
"""Two independent zone counting on top of the existing offline ft_count pipeline.

Each zone is counted by an independent :class:`tools.ft_count.CrossingCounter`
and tracker, run sequentially against the same validated input/model, via the
unmodified ``tools.ft_count._run_pipeline``. Reports are merged only after
both zone jobs succeed; zones are never summed into a total or unique-visitor
count because overlapping zones may count the same person independently.
All third-party imports stay deferred inside ``tools.ft_count._run_pipeline``
so this module imports and unit-tests cleanly under plain Python 3.9 stdlib.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from tools import ft_count
from tools.ft_count import ValidationError, _require

TOOL_NAME = "ft_count_zones"

MAX_CONFIG_BYTES = 64 * 1024
MAX_NAME_LEN = 60
TOTAL_TIME_BUDGET_S = 2400
TOTAL_OUTPUT_BUDGET_BYTES = 900 * 1024 * 1024

ZONE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _redact(_exc):
    return "internal error"


# --------------------------------------------------------------------------
# Config loading / validation
# --------------------------------------------------------------------------

def _config_sha256(cfg):
    blob = json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _zone_config_sha(zone):
    cfg = zone["config"]
    if zone.get("counter_mode") == "lanes":
        from tools import ft_lane_counter as lc
        definition = {"config": cfg, "lanes": zone["lanes"], "counter_mode": "lanes",
            "rules": [lc.ARM_CONSECUTIVE, lc.CONFIRM_CONSECUTIVE, lc.MIN_LANE_DISPLACEMENT,
                      lc.LANE_COOLDOWN_S, lc.IMPLAUSIBLE_STEP, lc.IMPLAUSIBLE_STEP_WINDOW_S]}
        if zone.get('track_quality'):
            from tools.ft_track_quality import policy
            definition['track_quality'] = policy()
        return _config_sha256(definition)
    return _config_sha256(cfg if zone.get("counter_mode", "line") == "line" else {"config": cfg, "counter_mode": "entries"})


def _candidate_digest(events):
    fields = ('lane_id','track_id','time_seconds','direction','evidence')
    records = [json.dumps({k:e[k] for k in fields},sort_keys=True,separators=(',',':')) for e in events]
    return _config_sha256(sorted(records))


def recount_lanes(zone, report, track_path):
    """Replay one shared detector/tracker stream through two front-shop gates."""
    from tools.ft_lane_counter import LaneCrossingCounter, validate_lanes
    validate_lanes(zone["lanes"], zone["config"])
    ft_count._outside_repo(track_path)
    st = os.lstat(track_path)
    _require(stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid() and not st.st_mode & 0o077, "private tracks required")
    _require(st.st_size <= ft_count.MAX_TRACKS_JSONL_BYTES, "track log too large")
    _require(report.get("config_sha256") in (_config_sha256(zone["config"]), _zone_config_sha(zone)), "lane config mismatch")
    tracks_sha = ft_count._file_sha256(track_path)
    if "tracks_sha256" in report:
        _require(report["tracks_sha256"] == tracks_sha, "track hash mismatch")
    counter = LaneCrossingCounter(zone["lanes"], zone["config"].get("deadband", ft_count.DEFAULT_DEADBAND))
    quality = None
    accepted, review = [], []
    if zone.get('track_quality'):
        from tools.ft_track_quality import TrackEvidence, VERSION, MAX_REVIEW_EVENTS
        _require(zone['track_quality'] == VERSION, 'invalid track quality mode')
        quality = TrackEvidence()
    frames, previous, previous_frame = 0, -1, -1
    with open(track_path) as fh:
        while True:
            line = fh.readline(1024 * 1024)
            if not line: break
            _require(line.endswith("\n"), "track row incomplete")
            row = json.loads(line)
            t, frame = row["time_seconds"], row["frame"]
            _require(type(t) in (int,float) and math.isfinite(t) and previous < t <= report["duration_seconds"], "invalid track clock")
            _require(abs(t - frames / report["sample_fps"]) <= .002, "track clock mismatch")
            _require(type(frame) is int and frame > previous_frame and (frames != 0 or frame == 0), "invalid frame clock")
            _require(isinstance(row["tracks"], list), "invalid track row")
            seen = set()
            for track in row["tracks"]:
                tid = track["track_id"]
                _require(isinstance(tid,(int,str)) and not isinstance(tid,bool) and tid not in seen, "duplicate/invalid track id")
                seen.add(tid)
                if quality:
                    quality.observe(tid, track['foot'], t, track.get('box'))
                before = len(counter.events)
                counter.update(tid, track["foot"], t)
                if quality:
                    for event in counter.events[before:]:
                        assessment = quality.assess(event)
                        if assessment['reasons']:
                            _require(len(review) < MAX_REVIEW_EVENTS, 'review queue capacity exceeded')
                            review.append({**event, 'review_reasons': assessment['reasons'],
                                           'quality_observations': assessment['observations']})
                        else:
                            accepted.append(event)
            previous, previous_frame = t, frame
            frames += 1
    _require(frames == report["frames_processed"], "lane track log incomplete")
    events = sorted(accepted if quality else counter.events, key=lambda e: e["time_seconds"])
    result = {**report, "counter_mode": "lanes", "config_sha256": _zone_config_sha(zone),
            "tracks_sha256": tracks_sha, "replay_anchor_precision_decimals": 4,
            "count": len(events), "events": events,
            "lane_counts": {lane['id']: sum(e['lane_id'] == lane['id'] for e in events) for lane in zone['lanes']},
            "direction_counts": {d:sum(e["direction"] == d for e in events) for d in ("forward","backward")}}
    if quality:
        from tools.ft_track_quality import policy
        result.update(track_quality_policy=policy(), candidate_count=counter.count,
                      candidate_lane_counts=counter.lane_counts, review_count=len(review),
                      review_events=sorted(review, key=lambda e:e['time_seconds']),
                      candidate_events_sha256=_candidate_digest(counter.events))
    else:
        for key in ('track_quality_policy','candidate_count','candidate_lane_counts','review_count',
                    'review_events','candidate_events_sha256'):
            result.pop(key,None)
    return result


def recount_entries(zone, report, track_path):
    """Use the exact persisted anchors; no second inference or geometry-only crop change."""
    from tools.ft_zone_entries import ZoneEntryCounter
    ft_count._outside_repo(track_path)
    st = os.lstat(track_path)
    _require(stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid() and not st.st_mode & 0o077, "private tracks required")
    _require(st.st_size <= ft_count.MAX_TRACKS_JSONL_BYTES, "track log too large")
    _require(report.get("config_sha256") in (_config_sha256(zone["config"]), _zone_config_sha(zone)), "entry config mismatch")
    counter = ZoneEntryCounter(zone["config"]["roi"], zone["config"].get("deadband", ft_count.DEFAULT_DEADBAND))
    frames, previous = 0, -1
    with open(track_path) as fh:
        while True:
            line = fh.readline(1024 * 1024)
            if not line: break
            _require(line.endswith("\n"), "track row incomplete")
            row = json.loads(line)
            t = row["time_seconds"]
            _require(type(t) in (int,float) and math.isfinite(t) and previous < t <= report["duration_seconds"], "invalid track clock")
            _require(abs(t - frames / report["sample_fps"]) <= .002, "track clock mismatch")
            previous = t
            for track in row["tracks"]:
                counter.update(track["track_id"], track["foot"], t)
            frames += 1
    _require(frames == report["frames_processed"], "entry track log incomplete")
    return {**report, "counter_mode": "entries", "config_sha256": _zone_config_sha(zone),
            "count": counter.count, "events": counter.events,
            "direction_counts": {"forward": counter.count, "backward": 0}}


def load_zones_config(path):
    ft_count._outside_repo(path)
    try:
        lst = os.lstat(path)
    except OSError:
        raise ValidationError("config not accessible")
    _require(not stat.S_ISLNK(lst.st_mode), "config must not be a symlink")
    _require(stat.S_ISREG(lst.st_mode), "config must be a regular file")
    _require(lst.st_uid == os.getuid() and not lst.st_mode & 0o077, "config must be owner-only")
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read(MAX_CONFIG_BYTES + 1)
    _require(len(raw) <= MAX_CONFIG_BYTES, "config too large")
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationError("config is not valid JSON")
    _require(isinstance(cfg, dict), "config must be a JSON object")
    validate_zones_config(cfg)
    return cfg


def validate_zones_config(cfg):
    _require(isinstance(cfg, dict), "config must be an object")
    _require(set(cfg) == {"zones"}, "unknown top-level field")
    zones = cfg.get("zones")
    _require(isinstance(zones, list) and len(zones) == 2, "zones must contain exactly two entries")

    ids, names, colors = set(), set(), set()
    sample_fps_values = set()
    for zone in zones:
        _require(isinstance(zone, dict), "zone must be an object")
        _require(set(zone) >= {"id", "name", "color", "config"} and set(zone) <= {"id", "name", "color", "config", "counter_mode", "lanes", "track_quality"}, "unknown zone field")

        _require(zone.get("counter_mode", "line") in ("line", "entries", "lanes"), "invalid counter mode")
        _require(("lanes" in zone) == (zone.get("counter_mode") == "lanes"), "lanes require lane mode")
        if 'track_quality' in zone:
            from tools.ft_track_quality import VERSION
            _require(zone.get('counter_mode') == 'lanes' and zone['track_quality'] == VERSION,
                     'invalid track quality mode')
        zid = zone.get("id")
        _require(isinstance(zid, str) and bool(ZONE_ID_RE.fullmatch(zid)), "invalid zone id")
        _require(zid not in ids, "duplicate zone id")
        ids.add(zid)

        name = zone.get("name")
        _require(
            isinstance(name, str) and 0 < len(name) <= MAX_NAME_LEN and name.strip() == name and all(ord(c) >= 32 for c in name),
            "invalid zone name",
        )
        _require(name not in names, "duplicate zone name")
        names.add(name)

        color = zone.get("color")
        _require(isinstance(color, str) and bool(COLOR_RE.fullmatch(color)), "invalid zone color")
        _require(color.lower() not in colors, "duplicate zone color")
        colors.add(color.lower())

        zcfg = zone.get("config")
        _require(isinstance(zcfg, dict), "zone config must be an object")
        ft_count.validate_config(zcfg)
        if zone.get("counter_mode") == "lanes":
            from tools.ft_lane_counter import validate_lanes
            validate_lanes(zone["lanes"], zcfg)
        sample_fps_values.add(zcfg.get("sample_fps", ft_count.DEFAULT_SAMPLE_FPS))

    _require(len(sample_fps_values) == 1, "zones must share the same sample_fps")


# --------------------------------------------------------------------------
# Per-zone pipeline invocation (reuses ft_count._run_pipeline unmodified)
# --------------------------------------------------------------------------

def _run_zone(zone, input_path, model_path, zone_output_dir, deadline_monotonic, output_budget_bytes=512 * 1024**2):
    args = SimpleNamespace(input=input_path, model=model_path, output=zone_output_dir, output_budget_bytes=output_budget_bytes)
    config_sha = _config_sha256(zone["config"])
    ft_count._run_pipeline(args, zone["config"], config_sha, deadline_monotonic)
    # Pipeline returns a stdout summary; its complete events live in the private report.
    with open(os.path.join(zone_output_dir, "report.json"), "r", encoding="utf-8") as fh:
        raw = fh.read(8 * 1024 * 1024 + 1)
    _require(len(raw) <= 8 * 1024 * 1024, "zone report too large")
    report = json.loads(raw)
    if zone.get("counter_mode", "line") in ("entries", "lanes"):
        recount = recount_lanes if zone["counter_mode"] == "lanes" else recount_entries
        report = recount(zone, report, os.path.join(zone_output_dir, "tracks.jsonl"))
        with open(os.path.join(zone_output_dir, "report.json"), "w", encoding="utf-8") as fh:
            json.dump(report, fh)
        # Single-zone annotation is the inference diagnostic, not the entry display.
        Path(zone_output_dir, "review.html").unlink()
        Path(zone_output_dir, "annotated.mp4").unlink()
    return report


# --------------------------------------------------------------------------
# Pure report merging (no media/network access)
# --------------------------------------------------------------------------

def merge_reports(zones, reports):
    _require(
        isinstance(zones, list) and isinstance(reports, list) and len(zones) == 2 and len(reports) == 2,
        "expected exactly two zone reports",
    )

    validate_zones_config({"zones": zones})
    for zone, report in zip(zones, reports):
        _require(isinstance(report, dict), "invalid zone report")
        _require(report.get("status") == "ok", "zone job did not complete successfully")

        for key in ("input_sha256", "model_sha256"):
            _require(isinstance(report.get(key), str) and re.fullmatch(r"[a-f0-9]{64}", report[key]) is not None, "invalid report hash")
        _require(type(report.get("frames_processed")) is int and report["frames_processed"] > 0, "invalid frame count")
        _require(type(report.get("sample_fps")) in (int, float) and math.isfinite(report["sample_fps"]) and 0 < report["sample_fps"] <= ft_count.MAX_SAMPLE_FPS, "invalid sample rate")
        _require(report.get("counter_mode", "line") == zone.get("counter_mode", "line"), "report counter mode mismatch")
        expected_sha = _zone_config_sha(zone)
        _require(report.get("config_sha256") == expected_sha, "zone config hash mismatch")

        duration = report.get("duration_seconds")
        _require(
            type(duration) in (int, float) and math.isfinite(duration) and 0 < duration <= ft_count.MAX_DURATION_S + ft_count.DURATION_TOLERANCE_S,
            "invalid zone duration",
        )

        events = report.get("events")
        _require(isinstance(events, list), "invalid zone events")
        count = report.get("count")
        _require(isinstance(count, int) and not isinstance(count, bool), "invalid zone count")
        _require(len(events) == count, "zone event count disagrees with reported count")

        direction_counts = report.get("direction_counts")
        _require(
            isinstance(direction_counts, dict) and set(direction_counts) == {"forward", "backward"} and all(type(v) is int and v >= 0 for v in direction_counts.values()),
            "invalid zone direction counts",
        )
        _require(sum(direction_counts.values()) == count, "zone direction totals disagree with count")

        max_t = duration + ft_count.DURATION_TOLERANCE_S
        for event in events:
            _require(isinstance(event, dict), "invalid zone event")
            t = event.get("time_seconds")
            _require(
                type(t) in (int, float) and math.isfinite(t) and 0 <= t <= max_t,
                "zone event timestamp out of range",
            )
            _require(event.get("direction") in ("forward", "backward"), "invalid zone event direction")

        for direction in ("forward", "backward"):
            _require(direction_counts[direction] == sum(e["direction"] == direction for e in events), "event directions disagree with totals")
        if zone.get("counter_mode") == "lanes":
            ids = {lane["id"] for lane in zone["lanes"]}
            lane_counts = report.get("lane_counts")
            _require(isinstance(lane_counts,dict) and set(lane_counts) == ids and all(type(v) is int and v >= 0 for v in lane_counts.values()), "invalid lane counts")
            _require(all(e.get("lane_id") in ids for e in events), "invalid event lane")
            _require(all(lane_counts[lid] == sum(e["lane_id"] == lid for e in events) for lid in ids), "lane count mismatch")
            if zone.get('track_quality'):
                from tools.ft_track_quality import policy, REASONS, MAX_REVIEW_EVENTS, HISTORY_UPDATES
                _require(report.get('track_quality_policy') == policy(), 'track quality policy mismatch')
                pending = report.get('review_events')
                pending_count = report.get('review_count')
                _require(isinstance(pending,list) and len(pending) <= MAX_REVIEW_EVENTS and type(pending_count) is int
                         and pending_count == len(pending), 'invalid review queue')
                candidate_count = report.get('candidate_count')
                candidate_lanes = report.get('candidate_lane_counts')
                _require(type(candidate_count) is int and candidate_count == count + pending_count,
                         'candidate count mismatch')
                _require(isinstance(candidate_lanes,dict) and set(candidate_lanes) == ids
                         and all(type(v) is int and v >= 0 for v in candidate_lanes.values()), 'invalid candidate lanes')
                for event in pending:
                    _require(isinstance(event,dict), 'invalid review event')
                    t = event.get('time_seconds')
                    reasons = event.get('review_reasons')
                    _require(type(t) in (int,float) and math.isfinite(t) and 0 <= t <= max_t
                             and event.get('lane_id') in ids and event.get('direction') in ('forward','backward'),
                             'invalid review event')
                    _require(isinstance(reasons,list) and reasons and all(isinstance(r,str) and r in REASONS for r in reasons)
                             and len(set(reasons)) == len(reasons), 'invalid review reasons')
                    _require(type(event.get('quality_observations')) is int and 1 <= event['quality_observations'] <= HISTORY_UPDATES,
                             'invalid quality observations')
                for event in events + pending:
                    _require(isinstance(event.get('track_id'),(int,str)) and not isinstance(event['track_id'],bool),
                             'invalid candidate track')
                    evidence = event.get('evidence')
                    _require(isinstance(evidence,dict) and set(evidence) == {'from','to'}
                             and all(ft_count._is_finite_point(p) and all(0 <= v <= 1 for v in p)
                                     for p in evidence.values()), 'invalid candidate evidence')
                _require(all(candidate_lanes[lid] == lane_counts[lid] + sum(e['lane_id'] == lid for e in pending)
                             for lid in ids), 'candidate lane mismatch')
                keys = [(e.get('lane_id'),str(e.get('track_id')),e['time_seconds']) for e in events + pending]
                _require(len(keys) == len(set(keys)), 'candidate duplicated between accepted/review')
                _require(report.get('candidate_events_sha256') == _candidate_digest(events + pending),
                         'candidate evidence digest mismatch')

    first, second = reports
    for key in ("input_sha256", "model_sha256", "duration_seconds", "sample_fps", "frames_processed"):
        _require(first.get(key) == second.get(key), "zone reports disagree on %s" % key)

    zones_out = []
    for zone, report in zip(zones, reports):
        zones_out.append(
            {
                "id": zone["id"],
                "name": zone["name"],
                "color": zone["color"],
                "counter_mode": zone.get("counter_mode", "line"),
                "count": report["count"],
                "direction_counts": report["direction_counts"],
                "events": report["events"],
                "config_sha256": report["config_sha256"],
            }
        )
        if zone.get("counter_mode") == "lanes":
            zones_out[-1]["lane_counts"] = report["lane_counts"]
            if zone.get('track_quality'):
                for key in ('track_quality_policy','candidate_count','candidate_lane_counts','review_count','review_events','candidate_events_sha256'):
                    zones_out[-1][key] = report[key]

    return {
        "schema_version": 2,
        "status": "ok",
        "input_sha256": first["input_sha256"],
        "model_sha256": first["model_sha256"],
        "parent_config_sha256": _config_sha256({"zones": zones}),
        "duration_seconds": first["duration_seconds"],
        "sample_fps": first["sample_fps"],
        "frames_processed": first["frames_processed"],
        "zones": zones_out,
        "full_day_complete": False,
        "accuracy_status": "NOT_EVALUATED",
    }


def _sanitize_stdout_report(merged):
    return {
        "status": merged.get("status", "ok"),
        "schema_version": merged.get("schema_version", 2),
        "input_sha256": merged.get("input_sha256"),
        "model_sha256": merged.get("model_sha256"),
        "parent_config_sha256": merged.get("parent_config_sha256"),
        "zones": [
            {
                "id": z["id"],
                "counter_mode": z.get("counter_mode", "line"),
                "name": z["name"],
                "color": z["color"],
                "count": z["count"],
                "direction_counts": z["direction_counts"],
                "config_sha256": z["config_sha256"],
                **({"lane_counts": z["lane_counts"]} if "lane_counts" in z else {}),
                **({"review_count": z["review_count"], "candidate_count": z["candidate_count"]} if "review_count" in z else {}),
            }
            for z in merged.get("zones", [])
        ],
        "accuracy_status": "NOT_EVALUATED",
        "full_day_complete": False,
    }


# --------------------------------------------------------------------------
# Offline Thai review page (no server, no external requests)
# --------------------------------------------------------------------------

def write_zones_page(root, zones, reports, combined=False):
    root_path = Path(root)
    ft_count._outside_repo(root_path)
    rst = root_path.stat()
    _require(rst.st_uid == os.getuid() and not rst.st_mode & 0o077, "private output required")

    validate_zones_config({"zones": zones})
    cards = []
    for zone, report in zip(zones, reports):
        safe_id = zone["id"]
        _require(bool(ZONE_ID_RE.fullmatch(safe_id)), "invalid zone id")
        video_rel = "counted-zones.mp4" if combined else "%s/annotated.mp4" % safe_id
        video_tag = "" if combined else '<video id="v-%s" controls preload="metadata" src="%s"></video>' % (safe_id, video_rel)
        rows = []
        for n, event in enumerate(report.get("events", []), 1):
            t = float(event["time_seconds"])
            direction = "เข้าโซน" if zone.get("counter_mode") == "entries" else html.escape(str(event["direction"]))
            if zone.get("counter_mode") == "lanes":
                lane_name = next(lane["name"] for lane in zone["lanes"] if lane["id"] == event["lane_id"])
                direction = html.escape(lane_name) + " · " + direction
            rows.append(
                '<tr><td>%d</td><td><button data-time="%.2f" data-zone="%s">%.1f วินาที</button></td>'
                '<td>%s</td></tr>' % (n, t, html.escape(safe_id), t, direction)
            )
        name = html.escape(zone["name"])
        method = "เดินเข้ากรอบจากด้านใดก็ได้ (ไม่รวมคนที่อยู่ในกรอบตั้งแต่เริ่มคลิป)" if zone.get("counter_mode") == "entries" else "เดินข้ามเส้นนับภายในกรอบ"
        if zone.get("counter_mode") == "lanes":
            method = "เดินข้ามเส้นในช่องใกล้หรือช่องไกล ยอดหน้าร้านแยกจากโซนข้างร้าน"
            method += " · " + " / ".join(html.escape(lane["name"])+": "+str(report["lane_counts"][lane["id"]])+" ครั้ง" for lane in zone["lanes"])
        review_html = ''
        if zone.get('track_quality'):
            method += ' · ยอดอัตโนมัติที่ผ่านเกณฑ์ความต่อเนื่อง ยังไม่ใช่ผลตรวจความแม่นยำครบคลิป'
            reason_labels = {'missing_anchor':'หลักฐานก่อนข้ามไม่ครบ', 'observation_gap':'ช่วงภาพติดตามขาด',
                             'box_shape_change':'ขนาดกรอบตัวคนเปลี่ยนฉับพลัน', 'center_jump':'ตำแหน่งติดตามกระโดด'}
            pending_rows = []
            for event in report['review_events']:
                t = float(event['time_seconds'])
                lane_name = next(lane['name'] for lane in zone['lanes'] if lane['id'] == event['lane_id'])
                explanation = ' / '.join(reason_labels[r] for r in event['review_reasons'])
                pending_rows.append('<tr><td><button data-time="%.2f" data-zone="%s">%.1f วินาที</button></td>'
                                    '<td>%s</td><td>%s</td></tr>' % (t,html.escape(safe_id),t,html.escape(lane_name),html.escape(explanation)))
            review_html = ('<h3>รอตรวจ %d จังหวะ · ยังไม่รวมในยอดอัตโนมัติ</h3>'
                           '<p>รายการนี้อาจเป็นคนเดินจริงหรือการติดตามคลาดเคลื่อน ไม่ใช่ยอดคนเพิ่มที่ยืนยันแล้ว</p>'
                           '<table><tr><th>เวลา</th><th>ช่อง</th><th>เหตุผล</th></tr>%s</table>') % (report['review_count'],''.join(pending_rows))
        color = html.escape(zone["color"])
        cards.append(
            '<section class="zone"><h2 style="color:%s">%s</h2>'
            '<div class="count">%d ครั้ง</div><p>%s</p>'
            '%s'
            '<table><tr><th>Event</th><th>Clip time</th><th>Direction</th></tr>%s</table>%s</section>'
            % (color, name, int(report["count"]), method, video_tag, "".join(rows),review_html)
        )

    page = (
        '<!doctype html><html lang="th"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; media-src \'self\'; '
        'style-src \'unsafe-inline\'; script-src \'unsafe-inline\'">'
        '<title>ผลนับคนแยกโซน</title><style>body{font-family:system-ui;max-width:1100px;margin:32px auto;'
        'padding:0 20px;color:#132c36;background:#edf3f4}h1{font-size:26px}.zone{background:#fff;padding:20px;'
        'border-radius:12px;margin-bottom:24px}.count{font-size:48px;font-weight:700}video{width:100%;'
        'background:#111;border-radius:12px}table{width:100%;border-collapse:collapse}td,th{padding:9px;'
        'border-bottom:1px solid #ccd9dd;text-align:left}button{padding:7px;border:1px solid #b8c9cb;'
        'border-radius:6px;background:white;cursor:pointer}</style>'
        '<h1>ผลนับคนเดินผ่าน · หลายโซน</h1>'
        '<p>แต่ละโซนนับอิสระจากกัน พื้นที่ที่ซ้อนทับอาจนับคนเดียวกันซ้ำในหลายโซน '
        'ตัวเลขนี้ไม่ใช่ผลรวมหรือจำนวนคนไม่ซ้ำทั้งหมด</p>'
    )
    page += "<p>ผลนับอัตโนมัติ ยังไม่ได้ตรวจความแม่นยำครบทั้งคลิปและทั้งสองโซน ไม่ใช่ยอดทั้งวัน</p>"
    if combined:
        page += '<video id="v-combined" controls preload="metadata" src="counted-zones.mp4"></video>'
    page += "".join(cards)
    page += (
        "<script>document.querySelectorAll('button[data-time]').forEach(b=>b.onclick=()=>{"
        "let v=document.getElementById('v-combined')||document.getElementById('v-'+b.dataset.zone);"
        "v.currentTime=Math.max(0,Number(b.dataset.time)-1);v.play()});</script></html>"
    )
    fd = ft_count._open_private(str(root_path / "review.html"))
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(page)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_arg_parser():
    p = argparse.ArgumentParser(prog="ft_count_zones")
    p.add_argument("--input", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--_network-sandbox", action="store_true", help=argparse.SUPPRESS)
    return p


def main(argv=None):
    deadline_total = time.monotonic() + TOTAL_TIME_BUDGET_S
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        if not args._network_sandbox:
            _require(sys.platform == "darwin" and os.path.isfile("/usr/bin/sandbox-exec"), "network sandbox required")
            command = [
                "/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)",
                sys.executable, "-m", "tools.ft_count_zones", "--_network-sandbox",
                "--input", args.input, "--model", args.model,
                "--config", args.config, "--output", args.output,
            ]
            return subprocess.call(command)

        import socket
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                probe.bind(("127.0.0.1", 0))
            finally:
                probe.close()
        except PermissionError:
            pass
        else:
            raise ValidationError("network sandbox not enforced")

        _require("://" not in args.input and not args.input.isdigit(), "input must be a local file path")
        ft_count._validate_input_file(args.input)
        ft_count._validate_model_file(args.model)
        zones_cfg = load_zones_config(args.config)
        zones = zones_cfg["zones"]

        root = ft_count._prepare_output_dir(args.output)
        os.umask(0o077)

        reports = []
        for zone in zones:
            remaining = deadline_total - time.monotonic()
            _require(remaining > 0, "job time budget exceeded")
            per_zone_deadline = min(deadline_total, time.monotonic() + ft_count.JOB_TIME_BUDGET_S)
            zone_dir = os.path.join(root, zone["id"])
            used = sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file())
            available = min(512 * 1024**2, TOTAL_OUTPUT_BUDGET_BYTES - 150 * 1024**2 - used)
            _require(available > 0, "combined output quota exhausted")
            report = _run_zone(zone, args.input, args.model, zone_dir, per_zone_deadline, available)
            total_bytes = sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file())
            _require(total_bytes <= TOTAL_OUTPUT_BUDGET_BYTES, "combined output quota exhausted")
            reports.append(report)

        merged = merge_reports(zones, reports)

        from tools.ft_zones_render import render_review
        render_review(args.input, root, zones, reports, deadline_total)
        total_bytes = sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file())
        _require(total_bytes <= TOTAL_OUTPUT_BUDGET_BYTES, "combined output quota exhausted")
        write_zones_page(root, zones, reports, combined=True)
        report_path = os.path.join(root, "report.json")
        rfd = ft_count._open_private(report_path)
        with os.fdopen(rfd, "w", encoding="utf-8") as fh:
            json.dump(merged, fh)

        print(json.dumps(_sanitize_stdout_report(merged)))
        return 0
    except ValidationError as exc:
        print(json.dumps({"status": "error", "message": str(exc), "exit_code": 2}))
        return 2
    except Exception as exc:  # noqa: BLE001 - must never leak details
        print(json.dumps({"status": "error", "message": _redact(exc), "exit_code": 1}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
