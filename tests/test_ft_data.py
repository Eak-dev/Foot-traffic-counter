"""Tests for tools/ft_data.py.

All media here is synthetic bytes, not playable camera video. Run from the
repository root:  python3 -m unittest discover -s tests -t . -v
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from tools import ft_data

GIB = 1024 ** 3
FAKE_CLIP = b"SYNTHETIC-NOT-A-VIDEO-" * 64
SMALL_CLIP = b"S" * 32


def run_cli(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ft_data.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fake_which(found):
    def _which(name):
        return "/opt/fake/%s" % name if name in found else None
    return _which


def append_bytes(path, data):
    with open(path, "ab") as handle:
        handle.write(data)


def run_on_read(target_count, action):
    """Callback for _patched_read that runs action once, on read number target_count."""
    return lambda count: action() if count == target_count else None


class ParsePositiveFiniteTests(unittest.TestCase):
    def test_accepts_positive_finite(self):
        self.assertEqual(ft_data.parse_positive_finite("10"), 10.0)
        self.assertEqual(ft_data.parse_positive_finite("0.5"), 0.5)

    def test_rejects_invalid_budgets(self):
        for text in ("0", "-1", "nan", "NaN", "inf", "-inf", "1e400", "abc", ""):
            with self.subTest(text=text):
                with self.assertRaises(argparse.ArgumentTypeError):
                    ft_data.parse_positive_finite(text)

    def test_cli_rejects_invalid_budget_with_exit_2(self):
        for text in ("nan", "-5", "inf"):
            with self.subTest(text=text):
                code, out, err = run_cli(["doctor", "--min-free-gib", text])
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("finite", err)
                self.assertIn("INVALID_MIN_FREE_GIB", err)


class DoctorTests(unittest.TestCase):
    def test_report_fields_and_live_ready_false(self):
        python_info = {"status": "PASS", "version": "3.9.6"}
        disk = ft_data.disk_result(20 * GIB, 10.0)
        executables = {"git": {"status": "INFO", "present": True, "functional": "UNKNOWN_NOT_CHECKED"}}
        report = ft_data.build_doctor_report(python_info, {"status": "INFO"}, disk, executables)
        self.assertEqual(report["preparation"], {"status": "PASS", "reasons": []})
        self.assertIs(report["live_ready"], False)
        self.assertEqual(report["camera"]["status"], "UNKNOWN")
        self.assertEqual(report["camera"]["credentials"], "UNKNOWN_NOT_CHECKED")
        self.assertEqual(report["mode"], "PREPARATION_ONLY")
        self.assertIn("ffprobe", report["not_required_for_d0"])

    def test_old_python_blocks_preparation(self):
        python_info = ft_data.check_python((3, 8, 18))
        self.assertEqual(python_info["status"], "BLOCKED")
        disk = ft_data.disk_result(20 * GIB, 10.0)
        report = ft_data.build_doctor_report(python_info, {}, disk, {})
        self.assertEqual(report["preparation"]["status"], "BLOCKED")
        self.assertIn("PYTHON_TOO_OLD", report["preparation"]["reasons"])

    def test_check_python_accepts_39(self):
        self.assertEqual(ft_data.check_python((3, 9, 6))["status"], "PASS")
        self.assertEqual(ft_data.check_python((3, 9, 6))["version"], "3.9.6")

    def test_disk_below_threshold_blocks(self):
        disk = ft_data.disk_result(5 * GIB, 10.0)
        self.assertEqual(disk["status"], "BLOCKED")
        self.assertEqual(disk["reason"], "DISK_BELOW_THRESHOLD")
        self.assertEqual(disk["threshold_source"], "PROPOSED_NOT_OWNER_APPROVED")

    def test_collect_doctor_real_directory_passes_with_tiny_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = ft_data.collect_doctor(tmp, 0.000001, which=fake_which({"git"}))
        self.assertEqual(report["preparation"]["status"], "PASS")
        self.assertIsInstance(report["checks"]["disk"]["free_gib"], float)
        self.assertTrue(report["executables"]["git"]["present"])
        self.assertFalse(report["executables"]["gh"]["present"])
        self.assertEqual(report["executables"]["ffprobe"]["status"], "NOT_REQUIRED_FOR_D0")
        self.assertEqual(report["executables"]["gh"]["functional"], "UNKNOWN_NOT_CHECKED")
        self.assertIs(report["live_ready"], False)

    def test_which_is_only_used_for_presence_names(self):
        seen = []

        def recording_which(name):
            seen.append(name)
            return None

        ft_data.collect_doctor(".", 0.000001, which=recording_which)
        self.assertEqual(sorted(seen), sorted(ft_data.INFO_EXECUTABLES + ft_data.NOT_REQUIRED_EXECUTABLES))

    def test_missing_disk_path_is_blocked_and_not_echoed(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "does-not-exist")
            code, out, _ = run_cli(["doctor", "--json", "--disk-path", missing])
        self.assertEqual(code, 1)
        report = json.loads(out)
        self.assertIn("DISK_PATH_INVALID", report["preparation"]["reasons"])
        self.assertNotIn(tmp, out)
        self.assertIs(report["live_ready"], False)

    def test_file_as_disk_path_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = os.path.join(tmp, "plain.txt")
            with open(file_path, "wb") as handle:
                handle.write(b"x")
            code, out, _ = run_cli(["doctor", "--json", "--disk-path", file_path])
        self.assertEqual(code, 1)
        self.assertIn("DISK_PATH_INVALID", out)

    def test_cli_json_has_no_absolute_paths_or_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(ft_data.shutil, "which", fake_which({"claude"})):
                code, out, _ = run_cli(["doctor", "--json", "--disk-path", tmp, "--min-free-gib", "0.000001"])
        self.assertEqual(code, 0)
        self.assertNotIn(tmp, out)
        self.assertNotIn(os.path.expanduser("~"), out)
        self.assertEqual(json.loads(out)["preparation"]["status"], "PASS")

    def test_cli_text_output_states_live_ready_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run_cli(["doctor", "--disk-path", tmp, "--min-free-gib", "0.000001"])
        self.assertEqual(code, 0)
        self.assertIn("live_ready: false", out)
        self.assertIn("camera: UNKNOWN", out)

    def test_embedded_nul_disk_path_is_blocked_without_echo(self):
        report = ft_data.collect_doctor("bad\x00CANARY_DISK_VALUE", 0.000001, which=fake_which(set()))
        self.assertEqual(report["checks"]["disk"]["reason"], "DISK_PATH_INVALID")
        self.assertIs(report["live_ready"], False)
        self.assertNotIn("CANARY_DISK_VALUE", json.dumps(report))


class _ClipTreeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self._tmp.name, "clips")
        os.mkdir(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, relative, data):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def make_symlink(self, target, link):
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported here")
        return link


class InventoryTests(_ClipTreeTestCase):
    def test_single_clip_hash_size_and_unknown_event_time(self):
        self.write("a.mp4", FAKE_CLIP)
        report = ft_data.scan_inventory(self.root)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(len(report["files"]), 1)
        record = report["files"][0]
        self.assertEqual(record["sha256"], sha(FAKE_CLIP))
        self.assertEqual(record["size_bytes"], len(FAKE_CLIP))
        self.assertIsNone(record["event_start"])
        self.assertEqual(record["time_source"], "UNKNOWN")
        self.assertEqual(report["source_catalog_completeness"], "UNKNOWN")
        self.assertIs(report["complete_day"], False)

    def test_duplicate_bytes_under_different_names_and_folders(self):
        self.write("one.mp4", FAKE_CLIP)
        self.write("sub/two.mp4", FAKE_CLIP)
        report = ft_data.scan_inventory(self.root)
        self.assertEqual(report["summary"]["duplicate_groups"], 1)
        self.assertEqual(report["summary"]["duplicate_clips"], 2)
        group = report["duplicate_groups"][0]
        self.assertEqual(len(group["file_ids"]), 2)
        for record in report["files"]:
            self.assertEqual(record["duplicate_group"], group["group_id"])

    def test_different_bytes_have_no_duplicate_group(self):
        self.write("one.mp4", FAKE_CLIP)
        self.write("two.mp4", FAKE_CLIP + b"!")
        report = ft_data.scan_inventory(self.root)
        self.assertEqual(report["summary"]["duplicate_groups"], 0)
        self.assertEqual(len({record["sha256"] for record in report["files"]}), 2)

    def test_empty_clip_is_counted_not_failed(self):
        self.write("empty.mp4", b"")
        report = ft_data.scan_inventory(self.root)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["summary"]["empty_clips"], 1)
        self.assertEqual(report["files"][0]["sha256"], sha(b""))
        self.assertEqual(report["files"][0]["size_bytes"], 0)

    def test_only_mp4_suffix_is_read_case_insensitive(self):
        self.write("upper.MP4", FAKE_CLIP)
        self.write("notes.txt", b"not a clip")
        self.write("other.mov", FAKE_CLIP)
        report = ft_data.scan_inventory(self.root)
        self.assertEqual(len(report["files"]), 1)
        self.assertEqual(report["summary"]["other_files_ignored"], 2)

    def test_large_clip_hashed_in_chunks(self):
        data = b"x" * (ft_data.CHUNK_SIZE * 2 + 17)
        self.write("big.mp4", data)
        report = ft_data.scan_inventory(self.root)
        self.assertEqual(report["files"][0]["sha256"], sha(data))
        self.assertEqual(report["files"][0]["size_bytes"], len(data))

    def test_missing_input_is_rejected(self):
        missing = os.path.join(self._tmp.name, "nope")
        report = ft_data.scan_inventory(missing)
        self.assertEqual(report["status"], "REJECTED")
        self.assertEqual(report["reason"], "INPUT_MISSING")
        self.assertEqual(report["files"], [])

    def test_empty_string_input_is_rejected_not_cwd(self):
        report = ft_data.scan_inventory("")
        self.assertEqual(report["reason"], "INPUT_MISSING")

    def test_file_input_is_not_a_directory(self):
        file_path = self.write("plain.mp4", FAKE_CLIP)
        report = ft_data.scan_inventory(file_path)
        self.assertEqual(report["status"], "REJECTED")
        self.assertEqual(report["reason"], "INPUT_NOT_DIRECTORY")

    def test_root_symlink_is_rejected_and_nothing_read(self):
        self.write("a.mp4", FAKE_CLIP)
        link = self.make_symlink(self.root, os.path.join(self._tmp.name, "link"))
        report = ft_data.scan_inventory(link)
        self.assertEqual(report["status"], "REJECTED")
        self.assertEqual(report["reason"], "INPUT_IS_SYMLINK")
        self.assertEqual(report["files"], [])

    def test_root_symlink_with_trailing_slash_is_rejected(self):
        link = self.make_symlink(self.root, os.path.join(self._tmp.name, "link2"))
        report = ft_data.scan_inventory(link + os.sep)
        self.assertEqual(report["reason"], "INPUT_IS_SYMLINK")

    def test_symlink_entries_are_not_followed(self):
        outside = os.path.join(self._tmp.name, "outside")
        os.mkdir(outside)
        outside_clip = os.path.join(outside, "outside.mp4")
        with open(outside_clip, "wb") as handle:
            handle.write(b"OUTSIDE-SYNTHETIC")
        self.write("real.mp4", FAKE_CLIP)
        self.make_symlink(outside_clip, os.path.join(self.root, "linked_file.mp4"))
        self.make_symlink(outside, os.path.join(self.root, "linked_dir"))
        report = ft_data.scan_inventory(self.root)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(len(report["files"]), 1)
        self.assertEqual(report["files"][0]["sha256"], sha(FAKE_CLIP))
        self.assertEqual(report["summary"]["symlinks_skipped"], 2)
        self.assertNotIn(sha(b"OUTSIDE-SYNTHETIC"), json.dumps(report))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO not supported")
    def test_fifo_named_like_a_clip_is_skipped_without_hanging(self):
        self.write("real.mp4", FAKE_CLIP)
        os.mkfifo(os.path.join(self.root, "pipe.mp4"))
        report = ft_data.scan_inventory(self.root)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(len(report["files"]), 1)
        self.assertEqual(report["summary"]["non_regular_skipped"], 1)

    def test_event_time_is_unknown_regardless_of_name_or_mtime(self):
        path = self.write("20261006_0930_entrance.mp4", FAKE_CLIP)
        os.utime(path, (1600000000, 1600000000))
        report = ft_data.scan_inventory(self.root)
        record = report["files"][0]
        self.assertIsNone(record["event_start"])
        self.assertEqual(record["time_source"], "UNKNOWN")
        self.assertEqual(report["time_source_policy"], "UNKNOWN_NOT_INFERRED_FROM_NAME_OR_MTIME")

    @unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() != 0, "permissions not enforced for root")
    def test_unreadable_clip_marks_incomplete_without_raw_error(self):
        path = self.write("locked.mp4", FAKE_CLIP)
        os.chmod(path, 0)
        try:
            report = ft_data.scan_inventory(self.root)
        finally:
            # Restore before tearDown removes the temp tree; addCleanup would run too late.
            os.chmod(path, 0o600)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["summary"]["unreadable_clips"], 1)
        self.assertNotIn("Permission", json.dumps(report))

    def test_scan_is_read_only_and_deterministic(self):
        self.write("a.mp4", FAKE_CLIP)
        self.write("b.mp4", FAKE_CLIP)
        before = sorted(os.path.join(dp, name) for dp, dns, fns in os.walk(self.root) for name in dns + fns)
        first = json.dumps(ft_data.scan_inventory(self.root), sort_keys=True)
        second = json.dumps(ft_data.scan_inventory(self.root), sort_keys=True)
        after = sorted(os.path.join(dp, name) for dp, dns, fns in os.walk(self.root) for name in dns + fns)
        self.assertEqual(first, second)
        self.assertEqual(before, after)

    def test_json_output_hides_paths_and_filenames(self):
        self.write("secret_camera_name_123.mp4", FAKE_CLIP)
        code, out, _ = run_cli(["inventory", self.root, "--json"])
        self.assertEqual(code, 0)
        self.assertNotIn(self.root, out)
        self.assertNotIn(self._tmp.name, out)
        self.assertNotIn("secret_camera_name_123", out)
        report = json.loads(out)
        self.assertEqual(report["files"][0]["file_id"], "F0001")

    def test_cli_missing_input_exit_1_without_path_echo(self):
        missing = os.path.join(self._tmp.name, "gone")
        code, out, _ = run_cli(["inventory", missing, "--json"])
        self.assertEqual(code, 1)
        self.assertNotIn(missing, out)
        self.assertIn("INPUT_MISSING", out)

    def test_cli_text_output_states_unknown_completeness(self):
        self.write("a.mp4", FAKE_CLIP)
        code, out, _ = run_cli(["inventory", self.root])
        self.assertEqual(code, 0)
        self.assertIn("source_catalog_completeness: UNKNOWN", out)
        self.assertIn("complete_day: false", out)
        self.assertNotIn(self.root, out)


class RootBoundaryTests(_ClipTreeTestCase):
    def test_root_symlink_with_dot_suffix_is_rejected_and_nothing_read(self):
        self.write("a.mp4", FAKE_CLIP)
        link = self.make_symlink(self.root, os.path.join(self._tmp.name, "dotlink"))
        for suffix in (os.sep + ".", os.sep + "." + os.sep, os.sep + os.sep, os.sep + "." + os.sep + "."):
            with self.subTest(suffix=suffix):
                report = ft_data.scan_inventory(link + suffix)
                self.assertEqual(report["status"], "REJECTED")
                self.assertEqual(report["reason"], "INPUT_IS_SYMLINK")
                self.assertEqual(report["files"], [])
                self.assertNotIn(sha(FAKE_CLIP), json.dumps(report))

    def test_real_root_with_dot_suffix_is_scanned(self):
        self.write("a.mp4", FAKE_CLIP)
        report = ft_data.scan_inventory(self.root + os.sep + ".")
        self.assertEqual(report["status"], "OK")
        self.assertEqual(len(report["files"]), 1)

    def test_dotdot_root_is_refused_as_ambiguous(self):
        self.write("a.mp4", FAKE_CLIP)
        for text in (os.path.join(self.root, ".."), os.path.join(self.root, "..", "clips")):
            with self.subTest(text=text):
                report = ft_data.scan_inventory(text)
                self.assertEqual(report["status"], "REJECTED")
                self.assertEqual(report["reason"], "INPUT_AMBIGUOUS_PATH")
                self.assertEqual(report["files"], [])

    def test_directory_replaced_by_link_before_open_is_not_followed(self):
        self.write("real.mp4", FAKE_CLIP)
        self.write("sub/inner.mp4", b"INNER-SYNTHETIC")
        outside = os.path.join(self._tmp.name, "outside")
        os.mkdir(outside)
        with open(os.path.join(outside, "outside.mp4"), "wb") as handle:
            handle.write(b"OUTSIDE-SYNTHETIC")
        real_open_dir = ft_data._open_dir_at

        def swap_then_open(dir_fd, name):
            # Deterministic race: after the listing lstat, before the subdirectory open.
            if name == "sub":
                shutil.rmtree(os.path.join(self.root, "sub"))
                os.symlink(outside, os.path.join(self.root, "sub"))
            return real_open_dir(dir_fd, name)

        with mock.patch.object(ft_data, "_open_dir_at", side_effect=swap_then_open):
            report = ft_data.scan_inventory(self.root)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["summary"]["changed_during_scan"], 1)
        self.assertEqual([record["sha256"] for record in report["files"]], [sha(FAKE_CLIP)])
        text = json.dumps(report)
        self.assertNotIn(sha(b"OUTSIDE-SYNTHETIC"), text)
        self.assertNotIn(sha(b"INNER-SYNTHETIC"), text)

    def test_embedded_nul_root_is_rejected_without_echo(self):
        report = ft_data.scan_inventory("bad\x00CANARY_NUL_PATH")
        self.assertEqual(report["status"], "REJECTED")
        self.assertEqual(report["reason"], "INPUT_INVALID")
        self.assertNotIn("CANARY_NUL_PATH", json.dumps(report))

    def test_non_text_and_none_roots_are_rejected(self):
        self.assertEqual(ft_data.scan_inventory(b"/tmp/x")["reason"], "INPUT_INVALID")
        self.assertEqual(ft_data.scan_inventory(None)["reason"], "INPUT_MISSING")


class StableReadTests(_ClipTreeTestCase):
    def _patched_read(self, on_read):
        """Patch os.read; on_read(call_number) runs after each real read.

        Returns (calls, patcher). Build the patcher before entering it so the
        wrapper captures the real os.read.
        """
        real_read = os.read
        calls = []

        def read_and_react(fd, n):
            calls.append(n)
            data = real_read(fd, n)
            on_read(len(calls))
            return data

        return calls, mock.patch.object(ft_data.os, "read", side_effect=read_and_react)

    def assert_changed_without_record(self, report, forbidden):
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["summary"]["changed_during_scan"], 1)
        self.assertEqual(report["files"], [])
        text = json.dumps(report)
        for data in forbidden:
            self.assertNotIn(sha(data), text)

    def test_stable_file_still_hashes_normally(self):
        self.write("steady.mp4", SMALL_CLIP)
        report = ft_data.scan_inventory(self.root)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["files"][0]["sha256"], sha(SMALL_CLIP))

    def test_file_growing_during_read_is_changed_not_hashed(self):
        path = self.write("grow.mp4", SMALL_CLIP)
        _, patcher = self._patched_read(run_on_read(1, lambda: append_bytes(path, b"A" * 16)))
        with patcher:
            report = ft_data.scan_inventory(self.root)
        self.assert_changed_without_record(report, [SMALL_CLIP, SMALL_CLIP + b"A" * 16])

    def test_continuously_growing_file_read_is_bounded_by_initial_size(self):
        path = self.write("endless.mp4", SMALL_CLIP)
        calls, patcher = self._patched_read(lambda count: append_bytes(path, b"A" * 16))
        with patcher:
            report = ft_data.scan_inventory(self.root)
        self.assertLessEqual(len(calls), 2)
        self.assertTrue(all(n <= len(SMALL_CLIP) for n in calls))
        self.assert_changed_without_record(report, [])

    def test_file_truncated_during_read_is_changed(self):
        path = self.write("shrink.mp4", SMALL_CLIP)

        def truncate():
            with open(path, "r+b") as handle:
                handle.truncate(8)

        _, patcher = self._patched_read(run_on_read(1, truncate))
        with patcher:
            report = ft_data.scan_inventory(self.root)
        self.assert_changed_without_record(report, [SMALL_CLIP, SMALL_CLIP[:8]])

    def test_metadata_change_during_read_is_changed(self):
        path = self.write("touched.mp4", SMALL_CLIP)
        _, patcher = self._patched_read(run_on_read(1, lambda: os.utime(path, (1600000000, 1600000000))))
        with patcher:
            report = ft_data.scan_inventory(self.root)
        self.assert_changed_without_record(report, [SMALL_CLIP])

    def test_entry_replaced_during_read_is_changed(self):
        path = self.write("swap.mp4", SMALL_CLIP)
        replacement = os.path.join(self._tmp.name, "replacement.bin")
        with open(replacement, "wb") as handle:
            handle.write(b"B" * 32)
        _, patcher = self._patched_read(run_on_read(1, lambda: os.replace(replacement, path)))
        with patcher:
            report = ft_data.scan_inventory(self.root)
        self.assert_changed_without_record(report, [SMALL_CLIP, b"B" * 32])


class CliRedactionTests(unittest.TestCase):
    """argparse echoes argv in its own errors; these cases must never reflect values."""

    def test_unknown_option_and_value_are_not_echoed(self):
        code, out, err = run_cli(["doctor", "--UNKNOWN-ARG", "CANARY_PRIVATE_VALUE"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("UNRECOGNIZED_ARGUMENT", err)
        self.assertNotIn("CANARY_PRIVATE_VALUE", err)
        self.assertNotIn("UNKNOWN-ARG", err)

    def test_json_usage_error_is_structured_and_redacted(self):
        code, out, err = run_cli(["doctor", "--json", "--token", "CANARY_TOKEN_VALUE"])
        self.assertEqual(code, 2)
        self.assertNotIn("CANARY_TOKEN_VALUE", out + err)
        report = json.loads(out)
        self.assertEqual(report["status"], "REJECTED")
        self.assertEqual(report["reason"], "UNRECOGNIZED_ARGUMENT")

    def test_inventory_unknown_option_is_redacted(self):
        code, out, err = run_cli(["inventory", "CANARY_PATH_VALUE", "--json", "--UNKNOWN-ARG", "x"])
        self.assertEqual(code, 2)
        self.assertNotIn("CANARY_PATH_VALUE", out + err)
        self.assertEqual(json.loads(out)["reason"], "UNRECOGNIZED_ARGUMENT")

    def test_invalid_command_is_redacted(self):
        code, out, err = run_cli(["CANARY_COMMAND_VALUE"])
        self.assertEqual(code, 2)
        self.assertIn("INVALID_COMMAND", err)
        self.assertNotIn("CANARY_COMMAND_VALUE", out + err)

    def test_budget_value_is_redacted(self):
        code, out, err = run_cli(["doctor", "--min-free-gib", "CANARY_BUDGET_VALUE"])
        self.assertEqual(code, 2)
        self.assertIn("INVALID_MIN_FREE_GIB", err)
        self.assertNotIn("CANARY_BUDGET_VALUE", out + err)

    def test_argv_with_nul_or_non_text_is_usage_error(self):
        code, _, err = run_cli(["doctor", "CANARY_NUL_VALUE\x00"])
        self.assertEqual(code, 2)
        self.assertIn("INVALID_ARGV", err)
        self.assertNotIn("CANARY_NUL_VALUE", err)

        code, _, err = run_cli(["doctor", b"CANARY_BYTES_VALUE"])
        self.assertEqual(code, 2)
        self.assertIn("INVALID_ARGV", err)
        self.assertNotIn("CANARY_BYTES_VALUE", err)


class SanitizedErrorTests(unittest.TestCase):
    def test_os_error_text_never_reaches_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(ft_data.os, "scandir", side_effect=OSError("/private/secret/path leaked")):
                report = ft_data.scan_inventory(tmp)
        text = json.dumps(report)
        self.assertNotIn("secret", text)
        self.assertEqual(report["summary"]["unreadable_dirs"], 1)
        self.assertEqual(report["status"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
