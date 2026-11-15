"""Tests for tools/ft_connect.py.

All configs here are synthetic temp files, never the real project
config.local.connection.json. No network, no camera, no process ever makes
a real connection. Run from the repository root:
python3 -m unittest discover -s tests -t . -v
"""
import contextlib
import getpass
import io
import json
import os
import shutil
import socket
import stat
import tempfile
import unittest
from unittest import mock

from tools import ft_connect


def run_cli(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ft_connect.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class TripwireSocket:
    """Fails the test if anything tries to open a network connection."""

    def __call__(self, *args, **kwargs):
        raise AssertionError("no network access is permitted in ft_connect")


class ParseRfc1918Ipv4Tests(unittest.TestCase):
    def test_accepts_rfc1918_bounds(self):
        for text in (
            "10.0.0.0", "10.255.255.255",
            "172.16.0.0", "172.31.255.255",
            "192.168.0.0", "192.168.255.255",
        ):
            self.assertIsNotNone(ft_connect.parse_rfc1918_ipv4(text), text)

    def test_rejects_non_private_and_non_literal_inputs(self):
        bad = [
            "8.8.8.8",            # public
            "127.0.0.1",          # loopback
            "169.254.1.1",        # link-local
            "100.64.0.1",         # CGNAT
            "172.32.0.1",         # just outside RFC1918 172 block
            "192.167.0.1",        # just outside RFC1918 192 block
            "::1",                # IPv6
            "fe80::1",            # IPv6 link-local
            "camera.local",       # hostname
            "http://192.168.1.1", # URL
            " 10.0.0.1",          # leading whitespace
            "10.0.0.1 ",          # trailing whitespace
            "10.0. 0.1",          # embedded whitespace
            "010.0.0.1",          # non-canonical leading zero
            "10.0.0.1\n",         # embedded newline
            "",                   # empty
            "not-an-ip",
        ]
        for text in bad:
            self.assertIsNone(ft_connect.parse_rfc1918_ipv4(text), text)

    def test_rejects_non_string(self):
        self.assertIsNone(ft_connect.parse_rfc1918_ipv4(None))
        self.assertIsNone(ft_connect.parse_rfc1918_ipv4(12345))


class PromptTwiceTests(unittest.TestCase):
    def test_matching_valid_input_succeeds(self):
        with mock.patch.object(getpass, "getpass", side_effect=["10.1.2.3", "10.1.2.3"]):
            value, reason = ft_connect.prompt_rfc1918_ipv4_twice("a", "b")
        self.assertEqual(value, "10.1.2.3")
        self.assertIsNone(reason)

    def test_mismatch_is_rejected(self):
        with mock.patch.object(getpass, "getpass", side_effect=["10.1.2.3", "10.1.2.4"]):
            value, reason = ft_connect.prompt_rfc1918_ipv4_twice("a", "b")
        self.assertIsNone(value)
        self.assertEqual(reason, "MISMATCH")

    def test_non_rfc1918_input_is_rejected(self):
        with mock.patch.object(getpass, "getpass", side_effect=["8.8.8.8", "8.8.8.8"]):
            value, reason = ft_connect.prompt_rfc1918_ipv4_twice("a", "b")
        self.assertIsNone(value)
        self.assertEqual(reason, "INVALID_INPUT")

    def test_getpass_warning_never_falls_back_to_plaintext(self):
        def _raise_warning(prompt=""):
            raise getpass.GetPassWarning("no tty")

        with mock.patch.object(getpass, "getpass", side_effect=_raise_warning):
            value, reason = ft_connect.prompt_rfc1918_ipv4_twice("a", "b")
        self.assertIsNone(value)
        self.assertEqual(reason, "MASKING_UNAVAILABLE")

    def test_eof_propagates_for_clean_abort(self):
        with mock.patch.object(getpass, "getpass", side_effect=EOFError()):
            with self.assertRaises(EOFError):
                ft_connect.prompt_rfc1918_ipv4_twice("a", "b")

    def test_keyboard_interrupt_propagates_for_clean_abort(self):
        with mock.patch.object(getpass, "getpass", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                ft_connect.prompt_rfc1918_ipv4_twice("a", "b")


class WriteConfigAtomicTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.dest = os.path.join(self.tmpdir, "config.local.connection.json")

    def test_writes_mode_0600_with_expected_schema(self):
        ok = ft_connect.write_config_atomic(self.dest, "10.0.0.5")
        self.assertTrue(ok)
        st = os.stat(self.dest)
        self.assertEqual(stat.S_IMODE(st.st_mode), 0o600)
        with open(self.dest, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data, {"version": 1, "camera_ipv4": "10.0.0.5", "lens": "fixed"})

    def test_no_temp_file_left_behind_on_success(self):
        ft_connect.write_config_atomic(self.dest, "10.0.0.5")
        self.assertEqual(os.listdir(self.tmpdir), ["config.local.connection.json"])

    def test_refuses_invalid_ipv4_before_creating_temp_file(self):
        with self.assertRaises(ValueError):
            ft_connect.write_config_atomic(self.dest, "8.8.8.8")
        self.assertEqual(os.listdir(self.tmpdir), [])
        self.assertFalse(os.path.exists(self.dest))

    def test_refuses_non_fixed_lens_before_creating_temp_file(self):
        with self.assertRaises(ValueError):
            ft_connect.write_config_atomic(self.dest, "10.0.0.5", lens="pt")
        self.assertEqual(os.listdir(self.tmpdir), [])

    def test_closes_fd_and_leaves_no_temp_file_when_fchmod_fails(self):
        with mock.patch.object(ft_connect.os, "fchmod", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                ft_connect.write_config_atomic(self.dest, "10.0.0.5")
        self.assertEqual(os.listdir(self.tmpdir), [])
        self.assertFalse(os.path.exists(self.dest))

    def test_no_temp_file_left_behind_when_link_fails_unexpectedly(self):
        with mock.patch.object(ft_connect.os, "link", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                ft_connect.write_config_atomic(self.dest, "10.0.0.5")
        self.assertEqual(os.listdir(self.tmpdir), [])

    def test_does_not_overwrite_existing_regular_file(self):
        with open(self.dest, "w", encoding="utf-8") as handle:
            handle.write("original\n")
        os.chmod(self.dest, 0o600)
        ok = ft_connect.write_config_atomic(self.dest, "10.0.0.9")
        self.assertFalse(ok)
        with open(self.dest, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "original\n")

    def test_no_temp_file_left_behind_on_existing_destination(self):
        with open(self.dest, "w", encoding="utf-8") as handle:
            handle.write("original\n")
        ft_connect.write_config_atomic(self.dest, "10.0.0.9")
        self.assertEqual(os.listdir(self.tmpdir), ["config.local.connection.json"])

    def test_does_not_follow_or_overwrite_symlinked_destination(self):
        target = os.path.join(self.tmpdir, "elsewhere.json")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("untouched\n")
        os.symlink(target, self.dest)
        ok = ft_connect.write_config_atomic(self.dest, "10.0.0.9")
        self.assertFalse(ok)
        self.assertTrue(os.path.islink(self.dest))
        with open(target, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "untouched\n")

    def test_race_destination_created_just_before_link_is_not_overwritten(self):
        real_link = os.link

        def racing_link(src, dst):
            with open(dst, "w", encoding="utf-8") as handle:
                handle.write("raced\n")
            return real_link(src, dst)

        with mock.patch.object(os, "link", side_effect=racing_link):
            ok = ft_connect.write_config_atomic(self.dest, "10.0.0.9")
        self.assertFalse(ok)
        with open(self.dest, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "raced\n")


class ReadConfigSafeTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.path = os.path.join(self.tmpdir, "config.local.connection.json")

    def _write_raw(self, raw_bytes, mode=0o600):
        with open(self.path, "wb") as handle:
            handle.write(raw_bytes)
        os.chmod(self.path, mode)

    def test_missing_file_is_reported_as_missing(self):
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "MISSING")

    def test_valid_config_round_trips(self):
        ft_connect.write_config_atomic(self.path, "192.168.1.1")
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(reason)
        self.assertEqual(data, {"version": 1, "camera_ipv4": "192.168.1.1", "lens": "fixed"})

    def test_rejects_directory(self):
        os.mkdir(self.path)
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_symlink(self):
        target = os.path.join(self.tmpdir, "target.json")
        ft_connect.write_config_atomic(target, "10.0.0.1")
        os.symlink(target, self.path)
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "mkfifo not available on this platform")
    def test_rejects_fifo(self):
        os.mkfifo(self.path, 0o600)
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_permissive_mode(self):
        self._write_raw(b'{"version": 1, "camera_ipv4": "10.0.0.1", "lens": "fixed"}', mode=0o644)
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_wrong_owner(self):
        ft_connect.write_config_atomic(self.path, "10.0.0.1")
        with mock.patch.object(ft_connect.os, "getuid", return_value=os.getuid() + 1):
            data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_invalid_utf8(self):
        self._write_raw(b"\xff\xfe\x00not-utf8")
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_oversized_file(self):
        padding = b" " * (ft_connect.MAX_CONFIG_BYTES + 1)
        self._write_raw(b'{"version": 1, "camera_ipv4": "10.0.0.1", "lens": "fixed"}' + padding)
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_bad_json(self):
        self._write_raw(b"{not json")
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_unknown_keys(self):
        self._write_raw(
            b'{"version": 1, "camera_ipv4": "10.0.0.1", "lens": "fixed", "extra": "x"}'
        )
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_bool_version(self):
        self._write_raw(b'{"version": true, "camera_ipv4": "10.0.0.1", "lens": "fixed"}')
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_wrong_version_number(self):
        self._write_raw(b'{"version": 2, "camera_ipv4": "10.0.0.1", "lens": "fixed"}')
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_non_rfc1918_ipv4(self):
        self._write_raw(b'{"version": 1, "camera_ipv4": "8.8.8.8", "lens": "fixed"}')
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_non_fixed_lens(self):
        self._write_raw(b'{"version": 1, "camera_ipv4": "10.0.0.1", "lens": "pt"}')
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_type_confusion_on_ipv4_field(self):
        self._write_raw(b'{"version": 1, "camera_ipv4": 167772161, "lens": "fixed"}')
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_rejects_duplicate_json_keys_instead_of_taking_last_value(self):
        self._write_raw(
            b'{"version": 1, "camera_ipv4": "10.0.0.1", "lens": "fixed",'
            b' "camera_ipv4": "10.0.0.2"}'
        )
        data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")

    def test_missing_parent_directory_is_missing_not_invalid(self):
        path = os.path.join(self.tmpdir, "no-such-dir", "config.local.connection.json")
        data, reason = ft_connect.read_config_safe(path)
        self.assertIsNone(data)
        self.assertEqual(reason, "MISSING")

    def test_parent_open_error_other_than_enoent_is_invalid(self):
        real_open = os.open

        def raise_eacces(path, flags, *args, **kwargs):
            if path == self.tmpdir:
                raise OSError(13, "Permission denied")
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(ft_connect.os, "open", side_effect=raise_eacces):
            data, reason = ft_connect.read_config_safe(self.path)
        self.assertIsNone(data)
        self.assertEqual(reason, "INVALID")


class ConfigureCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.dest = os.path.join(self.tmpdir, "config.local.connection.json")

    def _run(self, isatty=True, getpass_values=("10.0.0.1", "10.0.0.1")):
        with mock.patch("sys.stdin") as fake_stdin, mock.patch("sys.stdout") as fake_stdout:
            fake_stdin.isatty.return_value = isatty
            fake_stdout.isatty.return_value = isatty
            with mock.patch.object(getpass, "getpass", side_effect=list(getpass_values)):
                return ft_connect.configure_command(self.dest)

    def test_requires_interactive_tty(self):
        report = self._run(isatty=False)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "NOT_INTERACTIVE")
        self.assertFalse(os.path.exists(self.dest))

    def test_success_writes_config_and_never_leaks_value(self):
        report = self._run()
        self.assertEqual(report, {
            "tool": "ft_connect", "command": "configure",
            "schema_version": 1, "status": "CONFIGURED", "reason": None,
            "route": "NOT_TESTED", "auth": "NOT_TESTED",
            "download": "NOT_TESTED", "camera_requests": 0, "lens": "FIXED",
        })
        self.assertTrue(os.path.exists(self.dest))

    def test_mismatch_does_not_write_config(self):
        report = self._run(getpass_values=("10.0.0.1", "10.0.0.2"))
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "MISMATCH")
        self.assertFalse(os.path.exists(self.dest))

    def test_eof_aborts_cleanly_without_writing(self):
        with mock.patch("sys.stdin") as fake_stdin, mock.patch("sys.stdout") as fake_stdout:
            fake_stdin.isatty.return_value = True
            fake_stdout.isatty.return_value = True
            with mock.patch.object(getpass, "getpass", side_effect=EOFError()):
                report = ft_connect.configure_command(self.dest)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "INPUT_INTERRUPTED")
        self.assertFalse(os.path.exists(self.dest))

    def test_keyboard_interrupt_aborts_cleanly_without_writing(self):
        with mock.patch("sys.stdin") as fake_stdin, mock.patch("sys.stdout") as fake_stdout:
            fake_stdin.isatty.return_value = True
            fake_stdout.isatty.return_value = True
            with mock.patch.object(getpass, "getpass", side_effect=KeyboardInterrupt()):
                report = ft_connect.configure_command(self.dest)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "INPUT_INTERRUPTED")
        self.assertFalse(os.path.exists(self.dest))

    def test_existing_destination_is_never_overwritten(self):
        with open(self.dest, "w", encoding="utf-8") as handle:
            handle.write("original\n")
        report = self._run()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "CONFIG_EXISTS")
        with open(self.dest, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "original\n")

    def test_report_never_contains_entered_ip(self):
        report = self._run(getpass_values=("10.9.8.7", "10.9.8.7"))
        self.assertNotIn("10.9.8.7", json.dumps(report))

    def test_no_network_access_during_configure(self):
        with mock.patch.object(socket, "socket", TripwireSocket()):
            report = self._run()
        self.assertEqual(report["status"], "CONFIGURED")

    def test_write_failure_is_reported_cleanly_without_traceback(self):
        sentinel = "SENTINEL-SECRET-DO-NOT-LEAK"
        with mock.patch.object(
            ft_connect, "write_config_atomic", side_effect=OSError(sentinel)
        ):
            report = self._run()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "WRITE_FAILED")
        self.assertNotIn(sentinel, json.dumps(report))
        self.assertFalse(os.path.exists(self.dest))

    def test_keyboard_interrupt_during_write_aborts_cleanly(self):
        with mock.patch.object(
            ft_connect, "write_config_atomic", side_effect=KeyboardInterrupt()
        ):
            report = self._run()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason"], "INPUT_INTERRUPTED")
        self.assertFalse(os.path.exists(self.dest))


class CheckCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.dest = os.path.join(self.tmpdir, "config.local.connection.json")

    def test_missing_config_is_blocked(self):
        report = ft_connect.check_command(self.dest)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["endpoint"], "missing")
        self._assert_not_tested_fields(report)

    def test_invalid_config_is_blocked(self):
        with open(self.dest, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        os.chmod(self.dest, 0o600)
        report = ft_connect.check_command(self.dest)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["endpoint"], "invalid")
        self._assert_not_tested_fields(report)

    def test_valid_config_is_still_blocked_never_pass(self):
        ft_connect.write_config_atomic(self.dest, "10.0.0.1")
        report = ft_connect.check_command(self.dest)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["endpoint"], "configured")
        self._assert_not_tested_fields(report)

    def test_report_never_contains_ip_or_path(self):
        ft_connect.write_config_atomic(self.dest, "10.0.0.1")
        report = ft_connect.check_command(self.dest)
        rendered = json.dumps(report)
        self.assertNotIn("10.0.0.1", rendered)
        self.assertNotIn(self.tmpdir, rendered)

    def test_unexpected_read_error_is_blocked_with_full_redacted_fields(self):
        sentinel = "SENTINEL-SECRET-DO-NOT-LEAK"
        with mock.patch.object(
            ft_connect, "read_config_safe", side_effect=OSError(sentinel)
        ):
            report = ft_connect.check_command(self.dest)
        self.assertEqual(report["status"], "BLOCKED")
        self._assert_not_tested_fields(report)
        self.assertNotIn(sentinel, json.dumps(report))

    def test_no_network_access_during_check(self):
        ft_connect.write_config_atomic(self.dest, "10.0.0.1")
        with mock.patch.object(socket, "socket", TripwireSocket()):
            report = ft_connect.check_command(self.dest)
        self.assertEqual(report["endpoint"], "configured")

    def _assert_not_tested_fields(self, report):
        self.assertEqual(report["route"], "NOT_TESTED")
        self.assertEqual(report["auth"], "NOT_TESTED")
        self.assertEqual(report["download"], "NOT_TESTED")
        self.assertEqual(report["camera_requests"], 0)
        self.assertEqual(report["lens"], "FIXED")


class CliTests(unittest.TestCase):
    def test_configure_main_saves_and_returns_zero_with_redacted_json(self):
        class InteractiveOutput(io.StringIO):
            def isatty(self):
                return True

        out = InteractiveOutput()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "config.local.connection.json")
            with mock.patch.object(ft_connect, "CONFIG_PATH", dest), \
                    mock.patch("sys.stdin.isatty", return_value=True), \
                    mock.patch.object(getpass, "getpass", side_effect=["10.23.45.67"] * 2), \
                    contextlib.redirect_stdout(out):
                code = ft_connect.main(["configure"])
            self.assertTrue(os.path.exists(dest))
        self.assertEqual(code, 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report["status"], "CONFIGURED")
        self.assertEqual(report["route"], "NOT_TESTED")
        self.assertNotIn("10.23.45.67", out.getvalue())
        self.assertNotIn(tmpdir, out.getvalue())

    def test_interrupt_during_check_has_no_traceback(self):
        with mock.patch.object(ft_connect, "read_config_safe", side_effect=KeyboardInterrupt()):
            code, out, err = run_cli(["check"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)["reason"], "INPUT_INTERRUPTED")
        self.assertEqual(json.loads(out)["camera_requests"], 0)
        self.assertEqual(err, "")

    def test_help_exits_zero(self):
        code, out, err = run_cli(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("configure", out)
        self.assertIn("check", out)

    def test_unrecognized_argument_is_rejected_without_echo(self):
        code, out, err = run_cli(["configure", "--camera-ip=10.0.0.1"])
        self.assertEqual(code, 2)
        self.assertNotIn("10.0.0.1", err)
        self.assertNotIn("10.0.0.1", out)

    def test_no_command_is_rejected(self):
        code, out, err = run_cli([])
        self.assertEqual(code, 2)

    def test_unknown_command_is_rejected(self):
        code, out, err = run_cli(["launch"])
        self.assertEqual(code, 2)
        self.assertNotIn("launch", err)
        self.assertNotIn("launch", out)

    def test_usage_error_is_json_by_default(self):
        code, out, err = run_cli(["bogus"])
        self.assertEqual(code, 2)
        report = json.loads(out)
        self.assertEqual(report["status"], "REJECTED")
        self.assertNotIn("bogus", json.dumps(report))

    def test_check_output_is_json_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(ft_connect, "CONFIG_PATH", os.path.join(tmpdir, "config.local.connection.json")):
                code, out, err = run_cli(["check"])
        self.assertEqual(code, 2)
        report = json.loads(out)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["route"], "NOT_TESTED")

    def test_check_io_failure_exits_cleanly_with_fully_redacted_output(self):
        sentinel = "SENTINEL-SECRET-DO-NOT-LEAK/private/path"
        with mock.patch.object(ft_connect, "read_config_safe", side_effect=OSError(sentinel)):
            code, out, err = run_cli(["check"])
        self.assertEqual(code, 2)
        self.assertNotIn(sentinel, out)
        self.assertNotIn(sentinel, err)
        report = json.loads(out)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["route"], "NOT_TESTED")
        self.assertEqual(report["auth"], "NOT_TESTED")
        self.assertEqual(report["download"], "NOT_TESTED")
        self.assertEqual(report["camera_requests"], 0)


if __name__ == "__main__":
    unittest.main()
