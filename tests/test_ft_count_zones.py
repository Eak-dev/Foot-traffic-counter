"""Pure/synthetic tests for tools.ft_count_zones: schema validation and
report merging. No media, model, or network access; stdlib only.
"""
import copy
import os
import stat
import tempfile
import unittest

from tools import ft_count, ft_count_zones


def make_zone_config(sample_fps=5):
    return {
        "fixed_lens_verified": True,
        "line": [[0.2, 0.5], [0.8, 0.5]],
        "roi": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        "sample_fps": sample_fps,
        "confidence": 0.25,
        "deadband": 0.015,
    }


def make_zones_config():
    return {
        "zones": [
            {
                "id": "entrance",
                "name": "ทางเข้าหลัก",
                "color": "#FF0000",
                "config": make_zone_config(),
            },
            {
                "id": "checkout",
                "name": "จุดคิดเงิน",
                "color": "#00FF00",
                "config": make_zone_config(),
            },
        ]
    }


def make_report(zone_cfg, count=2, events=None, direction_counts=None, duration=60.0,
                 sample_fps=5.0, frames=300, input_sha="a" * 64, model_sha="b" * 64):
    if events is None:
        events = [
            {"track_id": 1, "time_seconds": 1.0, "direction": "forward",
             "evidence": {"from": [0.5, 0.4], "to": [0.5, 0.6]}},
            {"track_id": 2, "time_seconds": 2.0, "direction": "backward",
             "evidence": {"from": [0.5, 0.6], "to": [0.5, 0.4]}},
        ]
    if direction_counts is None:
        direction_counts = {"forward": 1, "backward": 1}
    return {
        "status": "ok",
        "model_sha256": model_sha,
        "input_sha256": input_sha,
        "config_sha256": ft_count_zones._config_sha256(zone_cfg),
        "frames_processed": frames,
        "count": count,
        "direction_counts": direction_counts,
        "duration_seconds": duration,
        "sample_fps": sample_fps,
        "events": events,
        "accuracy_status": "NOT_EVALUATED",
        "full_day_complete": False,
        "exit_code": 0,
    }


class ZonesConfigValidationTests(unittest.TestCase):
    def test_valid_zones_config_passes(self):
        ft_count_zones.validate_zones_config(make_zones_config())

    def test_requires_exactly_two_zones(self):
        cfg = make_zones_config()
        cfg["zones"].append(copy.deepcopy(cfg["zones"][0]))
        cfg["zones"][2]["id"] = "third"
        cfg["zones"][2]["name"] = "สามเอ"
        cfg["zones"][2]["color"] = "#0000FF"
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_unknown_top_level_field(self):
        cfg = make_zones_config()
        cfg["extra"] = 1
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_unknown_zone_field(self):
        cfg = make_zones_config()
        cfg["zones"][0]["extra"] = 1
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_duplicate_ids(self):
        cfg = make_zones_config()
        cfg["zones"][1]["id"] = cfg["zones"][0]["id"]
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_duplicate_names(self):
        cfg = make_zones_config()
        cfg["zones"][1]["name"] = cfg["zones"][0]["name"]
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_duplicate_colors(self):
        cfg = make_zones_config()
        cfg["zones"][1]["color"] = cfg["zones"][0]["color"]
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_unsafe_zone_id(self):
        for bad_id in ["Entrance", "has space", "../etc", "ok/no", "", "UP"]:
            cfg = make_zones_config()
            cfg["zones"][0]["id"] = bad_id
            with self.assertRaises(ft_count.ValidationError):
                ft_count_zones.validate_zones_config(cfg)

    def test_rejects_overlong_name(self):
        cfg = make_zones_config()
        cfg["zones"][0]["name"] = "x" * 61
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_empty_name(self):
        cfg = make_zones_config()
        cfg["zones"][0]["name"] = ""
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_invalid_color_format(self):
        for bad_color in ["red", "#FFF", "#GGGGGG", "#12345", "#1234567"]:
            cfg = make_zones_config()
            cfg["zones"][0]["color"] = bad_color
            with self.assertRaises(ft_count.ValidationError):
                ft_count_zones.validate_zones_config(cfg)

    def test_rejects_mismatched_sample_fps(self):
        cfg = make_zones_config()
        cfg["zones"][1]["config"]["sample_fps"] = 10
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_invalid_zone_config_via_ft_count_validator(self):
        cfg = make_zones_config()
        cfg["zones"][0]["config"]["line"] = [[0.5, 0.5], [0.5, 0.5]]
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_nan_in_nested_zone_config(self):
        cfg = make_zones_config()
        cfg["zones"][0]["config"]["line"] = [[float("nan"), 0.5], [0.8, 0.5]]
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)

    def test_rejects_unknown_field_in_nested_zone_config(self):
        cfg = make_zones_config()
        cfg["zones"][0]["config"]["bogus"] = 1
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.validate_zones_config(cfg)


class LoadZonesConfigFileSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _write(self, name, text, mode=0o600):
        path = os.path.join(os.path.realpath(self.tmp.name), name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(path, mode)
        return path

    def test_rejects_symlink_config(self):
        import json as _json
        real = self._write("real.json", _json.dumps(make_zones_config()))
        link = os.path.join(os.path.realpath(self.tmp.name), "link.json")
        os.symlink(real, link)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.load_zones_config(link)

    def test_rejects_group_readable_config(self):
        import json as _json
        path = self._write("cfg.json", _json.dumps(make_zones_config()), mode=0o644)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.load_zones_config(path)

    def test_rejects_oversized_config(self):
        path = self._write("big.json", "x" * (ft_count_zones.MAX_CONFIG_BYTES + 1))
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.load_zones_config(path)

    def test_rejects_invalid_json(self):
        path = self._write("bad.json", "{not json")
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.load_zones_config(path)

    def test_loads_valid_config(self):
        import json as _json
        cfg = make_zones_config()
        path = self._write("ok.json", _json.dumps(cfg))
        loaded = ft_count_zones.load_zones_config(path)
        self.assertEqual(len(loaded["zones"]), 2)


class MergeReportsTests(unittest.TestCase):
    def setUp(self):
        self.zones = make_zones_config()["zones"]
        self.reports = [make_report(z["config"]) for z in self.zones]

    def test_merges_two_zone_reports_without_summed_total(self):
        merged = ft_count_zones.merge_reports(self.zones, self.reports)
        self.assertEqual(merged["schema_version"], 2)
        self.assertEqual(len(merged["zones"]), 2)
        self.assertEqual(merged["zones"][0]["count"], 2)
        self.assertEqual(merged["zones"][1]["count"], 2)
        for forbidden in ("total", "total_count", "unique_visitors", "combined_count", "sum"):
            self.assertNotIn(forbidden, merged)
        self.assertEqual(merged["full_day_complete"], False)
        self.assertEqual(merged["accuracy_status"], "NOT_EVALUATED")

    def test_independent_zone_counts_allow_overlap_double_counting(self):
        same_event = {"track_id": 99, "time_seconds": 5.0, "direction": "forward",
                      "evidence": {"from": [0.5, 0.4], "to": [0.5, 0.6]}}
        reports = [
            make_report(self.zones[0]["config"], count=1, events=[same_event],
                        direction_counts={"forward": 1, "backward": 0}),
            make_report(self.zones[1]["config"], count=1, events=[dict(same_event)],
                        direction_counts={"forward": 1, "backward": 0}),
        ]
        merged = ft_count_zones.merge_reports(self.zones, reports)
        self.assertEqual(merged["zones"][0]["count"], 1)
        self.assertEqual(merged["zones"][1]["count"], 1)

    def test_rejects_mismatched_input_hash(self):
        reports = list(self.reports)
        reports[1] = dict(reports[1], input_sha256="c" * 64)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_mismatched_model_hash(self):
        reports = list(self.reports)
        reports[1] = dict(reports[1], model_sha256="c" * 64)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_mismatched_duration(self):
        reports = list(self.reports)
        reports[1] = dict(reports[1], duration_seconds=61.0)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_mismatched_sample_fps(self):
        reports = list(self.reports)
        reports[1] = dict(reports[1], sample_fps=4.0)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_mismatched_frames_processed(self):
        reports = list(self.reports)
        reports[1] = dict(reports[1], frames_processed=301)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_config_hash_mismatch(self):
        reports = list(self.reports)
        reports[0] = dict(reports[0], config_sha256="0" * 64)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_count_event_disagreement(self):
        reports = list(self.reports)
        reports[0] = dict(reports[0], count=99)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_direction_counts_disagreeing_with_count(self):
        reports = list(self.reports)
        reports[0] = dict(reports[0], direction_counts={"forward": 5, "backward": 5})
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_unknown_direction_key(self):
        reports = list(self.reports)
        reports[0] = dict(reports[0], direction_counts={"forward": 1, "sideways": 1})
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_nan_event_timestamp(self):
        reports = list(self.reports)
        events = copy.deepcopy(reports[0]["events"])
        events[0]["time_seconds"] = float("nan")
        reports[0] = dict(reports[0], events=events)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_event_timestamp_beyond_duration(self):
        reports = list(self.reports)
        events = copy.deepcopy(reports[0]["events"])
        events[0]["time_seconds"] = reports[0]["duration_seconds"] + 100.0
        reports[0] = dict(reports[0], events=events)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_negative_event_timestamp(self):
        reports = list(self.reports)
        events = copy.deepcopy(reports[0]["events"])
        events[0]["time_seconds"] = -1.0
        reports[0] = dict(reports[0], events=events)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_invalid_event_direction(self):
        reports = list(self.reports)
        events = copy.deepcopy(reports[0]["events"])
        events[0]["direction"] = "sideways"
        reports[0] = dict(reports[0], events=events)
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_one_zone_failure_is_not_published(self):
        reports = list(self.reports)
        reports[1] = dict(reports[1], status="error")
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, reports)

    def test_rejects_wrong_zone_or_report_count(self):
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones[:1], self.reports[:1])
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(self.zones, self.reports + [self.reports[0]])


class ConfigShaTests(unittest.TestCase):
    def test_config_sha_stable_regardless_of_key_order(self):
        cfg_a = {"b": 2, "a": 1}
        cfg_b = {"a": 1, "b": 2}
        self.assertEqual(ft_count_zones._config_sha256(cfg_a), ft_count_zones._config_sha256(cfg_b))

    def test_config_sha_changes_with_value(self):
        cfg_a = {"a": 1}
        cfg_b = {"a": 2}
        self.assertNotEqual(ft_count_zones._config_sha256(cfg_a), ft_count_zones._config_sha256(cfg_b))


class SanitizeStdoutTests(unittest.TestCase):
    def test_sanitize_stdout_report_only_has_expected_keys(self):
        zones = make_zones_config()["zones"]
        reports = [make_report(z["config"]) for z in zones]
        merged = ft_count_zones.merge_reports(zones, reports)
        out = ft_count_zones._sanitize_stdout_report(merged)
        self.assertEqual(set(out), {
            "status", "schema_version", "input_sha256", "model_sha256",
            "parent_config_sha256", "zones", "accuracy_status", "full_day_complete",
        })
        for zone_out in out["zones"]:
            self.assertNotIn("events", zone_out)


class WriteZonesPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_writes_private_review_page_with_both_zones(self):
        real_tmp = os.path.realpath(self.tmp.name)
        out = os.path.join(real_tmp, "out")
        root = ft_count._prepare_output_dir(out)
        zones = make_zones_config()["zones"]
        reports = [make_report(z["config"]) for z in zones]
        ft_count_zones.write_zones_page(root, zones, reports)
        page_path = os.path.join(root, "review.html")
        mode = stat.S_IMODE(os.stat(page_path).st_mode)
        self.assertEqual(mode, 0o600)
        with open(page_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn(zones[0]["id"] + "/annotated.mp4", content)
        self.assertIn(zones[1]["id"] + "/annotated.mp4", content)
        self.assertIn("default-src 'none'", content)


class IntegrationRegressionTests(unittest.TestCase):
    def test_run_zone_loads_full_report_not_pipeline_summary(self):
        from unittest.mock import patch
        import json
        with tempfile.TemporaryDirectory() as tmp:
            zone = make_zones_config()['zones'][0]
            report = make_report(zone['config'])
            with open(os.path.join(tmp, 'report.json'), 'w') as f:
                json.dump(report, f)
            with patch.object(ft_count, '_run_pipeline', return_value={'count': report['count']}):
                loaded = ft_count_zones._run_zone(zone, 'synthetic', 'synthetic', tmp, 100)
            self.assertEqual(loaded['events'], report['events'])

    def test_newline_ids_and_colors_are_rejected(self):
        for key in ('id', 'color'):
            cfg = make_zones_config()
            cfg['zones'][0][key] += '\n'
            with self.assertRaises(ft_count.ValidationError):
                ft_count_zones.validate_zones_config(cfg)

    def test_per_direction_counts_must_match_events_not_just_total(self):
        zones = make_zones_config()['zones']
        reports = [make_report(z['config']) for z in zones]
        reports[0]['direction_counts'] = {'forward': 2, 'backward': 0}
        with self.assertRaises(ft_count.ValidationError):
            ft_count_zones.merge_reports(zones, reports)

    def test_matching_missing_or_malformed_hashes_are_rejected(self):
        zones = make_zones_config()['zones']
        for value in (None, '', 'a', 'z'*64):
            reports = [make_report(z['config'], input_sha=value) for z in zones]
            with self.assertRaises(ft_count.ValidationError):
                ft_count_zones.merge_reports(zones, reports)

    def test_renderer_rejects_unconfined_call_before_reading_media(self):
        from unittest.mock import patch, MagicMock
        from tools.ft_zones_render import render_review
        with patch('socket.socket', return_value=MagicMock()):
            with self.assertRaisesRegex(ft_count.ValidationError, 'network sandbox'):
                render_review('no-media', 'no-output', [], [], 1)

    def test_pipeline_failure_never_publishes_merged_report(self):
        from unittest.mock import patch, MagicMock
        from pathlib import Path
        cfg = make_zones_config()
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(os.path.realpath(tmp), 'out')
            sock = MagicMock()
            sock.bind.side_effect = PermissionError()
            with patch('socket.socket', return_value=sock), \
                 patch.object(ft_count, '_validate_input_file'), \
                 patch.object(ft_count, '_validate_model_file'), \
                 patch.object(ft_count_zones, 'load_zones_config', return_value=cfg), \
                 patch.object(ft_count_zones, '_run_zone', side_effect=ft_count.ValidationError('zone failed')):
                result = ft_count_zones.main(['--_network-sandbox','--input','synthetic','--model','synthetic','--config','synthetic','--output',root])
            self.assertEqual(result, 2)
            self.assertFalse((Path(root)/'report.json').exists())


class EntryModeIntegrationTests(unittest.TestCase):
    def test_entry_report_uses_mode_bound_hash_and_persisted_anchors(self):
        import json
        from pathlib import Path
        zone = make_zones_config()['zones'][1]
        zone['counter_mode'] = 'entries'
        zone['config']['roi'] = [[.2,.2],[.8,.2],[.8,.8],[.2,.8]]
        report = make_report(zone['config'], duration=1.2, frames=6)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(os.path.realpath(tmp))/'tracks.jsonl'
            with path.open('w') as f:
                for i,p in enumerate([(.1,.5)]*3+[(.4,.5)]*3):
                    f.write(json.dumps({'time_seconds':i/5,'tracks':[{'track_id':1,'foot':p}]})+'\n')
            path.chmod(0o600)
            counted = ft_count_zones.recount_entries(zone,report,path)
        self.assertEqual(counted['count'],1)
        self.assertEqual(counted['events'][0]['event_type'],'zone_entry')
        self.assertNotEqual(counted['config_sha256'],report['config_sha256'])
        self.assertEqual(counted['config_sha256'],ft_count_zones._zone_config_sha(zone))

    def test_invalid_counter_mode_rejected(self):
        cfg=make_zones_config();cfg['zones'][1]['counter_mode']='occupancy'
        with self.assertRaises(ft_count.ValidationError):ft_count_zones.validate_zones_config(cfg)

    def test_entry_mode_page_has_single_video_and_explicit_counting_meaning(self):
        from pathlib import Path
        zones=make_zones_config()['zones'];zones[1]['counter_mode']='entries'
        reports=[make_report(z['config']) for z in zones]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(os.path.realpath(tmp));root.chmod(0o700)
            ft_count_zones.write_zones_page(root,zones,reports,combined=True)
            page=(root/'review.html').read_text()
        self.assertEqual(page.count('<video '),1)
        self.assertIn('เดินเข้ากรอบจากด้านใดก็ได้',page)

if __name__ == '__main__':unittest.main()
