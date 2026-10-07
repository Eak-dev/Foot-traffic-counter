"""Tests for tools/claude_dev.py.

Git state is exercised with real, throwaway git trees under tempfile (no
network, no installs). The `claude` binary itself is never started: only
calls whose argv starts with "git" are passed through to the real
subprocess.run; calls for "claude" are scripted by the test. Run from the
repository root:  python3 -m unittest discover -s tests -t . -v
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import claude_dev

ZERO_SHA = "0" * 40


def _git(cwd, *args):
    result = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), result.stderr))
    return result.stdout


def _init_repo(root, branch):
    """Init a throwaway repo. .claude/ is gitignored so launcher-internal
    config/lock/task files never show up as unexpected dirty state."""
    _git(root, "init", "-q")
    _git(root, "checkout", "-q", "-b", branch)
    with open(os.path.join(root, "README.md"), "w", encoding="utf-8") as handle:
        handle.write("init\n")
    with open(os.path.join(root, ".gitignore"), "w", encoding="utf-8") as handle:
        handle.write(".claude/\n")
    _git(root, "add", "README.md", ".gitignore")
    _git(root, "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-q", "-m", "init")
    return _git(root, "rev-parse", "HEAD").strip()


def _write_config(root, branch, model="claude-sonnet-5", budget=6):
    claude_dir = os.path.join(root, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    with open(os.path.join(claude_dir, "workflow.local.json"), "w", encoding="utf-8") as handle:
        json.dump({"root": root, "branch": branch, "model": model, "max_budget_usd": budget}, handle)


def _write_policy(root):
    with open(os.path.join(root, ".claude", "dev-policy.json"), "w", encoding="utf-8") as handle:
        handle.write("{}")


@contextlib.contextmanager
def synthetic_repo(branch="claude/test-branch", write_config=True, write_policy=True):
    root = os.path.realpath(tempfile.mkdtemp(prefix="claude_dev_test_"))
    old_cwd = os.getcwd()
    try:
        head = _init_repo(root, branch)
        if write_config:
            _write_config(root, branch)
        if write_policy:
            os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
            _write_policy(root)
        os.chdir(root)
        real_popen = subprocess.Popen
        def no_live_claude(args, *popen_args, **kwargs):
            if args and os.path.basename(str(args[0])) == "claude":
                raise AssertionError("Unit tests must never start a real Claude process")
            return real_popen(args, *popen_args, **kwargs)
        with mock.patch.object(claude_dev, "_script_root", return_value=root), \
             mock.patch.object(claude_dev.subprocess, "Popen", side_effect=no_live_claude):
            yield root, head
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(root, ignore_errors=True)


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = claude_dev.main(argv)
    return code, out.getvalue(), err.getvalue()


def _patched_claude(exit_code=0, stdout_bytes=b"", raises_timeout=False, on_call=None):
    """Script the dedicated child-execution helper directly; git calls are
    untouched real subprocess.run calls."""
    def fake_run_child(claude_args, cwd, stdin_f, stdout_f, timeout):
        if on_call is not None:
            on_call()
        if raises_timeout:
            return None, True
        stdout_f.write(stdout_bytes)
        return exit_code, False

    return mock.patch.object(claude_dev, "_run_child", side_effect=fake_run_child)


def _success_bytes(result_text="done"):
    return json.dumps({"is_error": False, "permission_denials": [], "result": result_text}).encode("utf-8")


class ValidateRelpathTests(unittest.TestCase):
    def test_accepts_plain_relative_path(self):
        self.assertIsNone(claude_dev._validate_relpath("docs/STATUS.md", allow_protected=False))

    def test_rejects_absolute_and_traversal(self):
        for path in ("/etc/passwd", "~/x", "a/../b", "../escape", "a/./b", ""):
            with self.subTest(path=path):
                self.assertIsNotNone(claude_dev._validate_relpath(path, allow_protected=False))

    def test_rejects_protected_exact_and_prefixes(self):
        for path in ("PROJECT_CONTROL.md", "tools/claude_dev.py", ".git/config",
                     ".claude/workflow.local.json", "data/x.json", "secrets/a"):
            with self.subTest(path=path):
                self.assertEqual(claude_dev._validate_relpath(path, allow_protected=False), "PATH_PROTECTED")

    def test_rejects_secret_like_filenames(self):
        for path in (".env", "service.key", "credentials.json", "service-account-1.json", ".env.local"):
            with self.subTest(path=path):
                self.assertEqual(claude_dev._validate_relpath(path, allow_protected=False), "PATH_PROTECTED")

    def test_rejects_nested_secret_like_paths(self):
        for path in ("sub/.env.local", "a/.env/b", "nested/dir/credentials.prod.json"):
            with self.subTest(path=path):
                self.assertEqual(claude_dev._validate_relpath(path, allow_protected=False), "PATH_PROTECTED")
                self.assertEqual(claude_dev._validate_relpath(path, allow_protected=True), "PATH_PROTECTED")

    def test_rejects_permission_rule_metacharacters(self):
        for path in ("a*.txt", "a?.txt", "a[b].txt", "a(b).txt", "a,b.txt", "a b.txt", "a\\b.txt", "a\tb.txt"):
            with self.subTest(path=path):
                self.assertEqual(claude_dev._validate_relpath(path, allow_protected=False), "PATH_UNSAFE_CHARS")

    def test_accepts_simple_ascii_filename_grammar(self):
        for path in ("docs/STATUS.md", "a-b_c.1.txt", "dir/sub-dir/file_name.py"):
            with self.subTest(path=path):
                self.assertIsNone(claude_dev._validate_relpath(path, allow_protected=False))

    def test_allow_protected_skips_protected_check_but_not_traversal(self):
        self.assertIsNone(claude_dev._validate_relpath("PROJECT_CONTROL.md", allow_protected=True))
        self.assertIsNotNone(claude_dev._validate_relpath("../x", allow_protected=True))


class SymlinkAncestorTests(unittest.TestCase):
    def test_detects_symlink_at_leaf_and_ancestor(self):
        root = os.path.realpath(tempfile.mkdtemp(prefix="claude_dev_test_"))
        try:
            with open(os.path.join(root, "real.txt"), "w", encoding="utf-8") as handle:
                handle.write("x\n")
            os.symlink(os.path.join(root, "real.txt"), os.path.join(root, "link.txt"))
            os.makedirs(os.path.join(root, "realdir"))
            os.symlink(os.path.join(root, "realdir"), os.path.join(root, "linkdir"))
            self.assertTrue(claude_dev._has_symlink_ancestor_or_self(root, "link.txt"))
            self.assertTrue(claude_dev._has_symlink_ancestor_or_self(root, "linkdir/file.txt"))
            self.assertFalse(claude_dev._has_symlink_ancestor_or_self(root, "real.txt"))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_hash_file_refuses_to_follow_symlink(self):
        root = os.path.realpath(tempfile.mkdtemp(prefix="claude_dev_test_"))
        try:
            outside = os.path.realpath(tempfile.mkdtemp(prefix="claude_dev_test_outside_"))
            try:
                with open(os.path.join(outside, "secret.txt"), "w", encoding="utf-8") as handle:
                    handle.write("outside-secret\n")
                os.symlink(os.path.join(outside, "secret.txt"), os.path.join(root, "link.txt"))
                self.assertIsNone(claude_dev._hash_file(root, "link.txt"))
            finally:
                shutil.rmtree(outside, ignore_errors=True)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class StatusEntriesTests(unittest.TestCase):
    def test_reports_untracked_and_modified(self):
        with synthetic_repo() as (root, _head):
            with open(os.path.join(root, "README.md"), "a", encoding="utf-8") as handle:
                handle.write("more\n")
            with open(os.path.join(root, "new.txt"), "w", encoding="utf-8") as handle:
                handle.write("x\n")
            entries, reason = claude_dev._status_entries(root)
            self.assertIsNone(reason)
            self.assertEqual(set(entries), {"README.md", "new.txt"})

    def test_rename_is_rejected_not_parsed(self):
        with synthetic_repo() as (root, _head):
            _git(root, "mv", "README.md", "RENAMED.md")
            entries, reason = claude_dev._status_entries(root)
            self.assertIsNone(entries)
            self.assertEqual(reason, "DIRTY_TREE_RENAME_UNSUPPORTED")


class PreflightTests(unittest.TestCase):
    def test_clean_repo_on_configured_branch_is_ready(self):
        with synthetic_repo(branch="claude/ok") as (root, head):
            reasons, ctx, config, script_root = claude_dev.preflight(root, head, [])
            self.assertEqual(reasons, [])
            self.assertEqual(ctx["branch"], "claude/ok")
            self.assertEqual(script_root, root)
            self.assertIsNotNone(config)

    def test_not_a_git_repo(self):
        root = os.path.realpath(tempfile.mkdtemp(prefix="claude_dev_test_"))
        try:
            with mock.patch.object(claude_dev, "_script_root", return_value=root):
                reasons, _ctx, _config, _root = claude_dev.preflight(root, None, [])
            self.assertIn("NOT_A_GIT_REPO", reasons)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_protected_branch_rejected(self):
        with synthetic_repo(branch="main") as (root, head):
            reasons, _ctx, _config, _root = claude_dev.preflight(root, head, [])
            self.assertIn("PROTECTED_BRANCH", reasons)

    def test_branch_mismatch_rejected(self):
        with synthetic_repo(branch="claude/actual") as (root, head):
            _write_config(root, "claude/expected")
            reasons, _ctx, _config, _root = claude_dev.preflight(root, head, [])
            self.assertIn("BRANCH_MISMATCH", reasons)

    def test_detached_head_rejected(self):
        with synthetic_repo() as (root, head):
            _git(root, "checkout", "-q", head)
            reasons, _ctx, _config, _root = claude_dev.preflight(root, head, [])
            self.assertIn("DETACHED_HEAD", reasons)

    def test_baseline_mismatch_and_bad_format(self):
        with synthetic_repo() as (root, head):
            reasons, _ctx, _config, _root = claude_dev.preflight(root, ZERO_SHA, [])
            self.assertIn("BASELINE_MISMATCH", reasons)
            reasons, _ctx, _config, _root = claude_dev.preflight(root, "not-a-sha", [])
            self.assertIn("BASELINE_INVALID_FORMAT", reasons)

    def test_root_mismatch_when_cwd_is_a_different_repo(self):
        with synthetic_repo(branch="claude/a") as (root_a, _head_a):
            other = os.path.realpath(tempfile.mkdtemp(prefix="claude_dev_test_other_"))
            try:
                _init_repo(other, "claude/a")
                with mock.patch.object(claude_dev, "_script_root", return_value=root_a):
                    reasons, _ctx, _config, _root = claude_dev.preflight(other, None, [])
                self.assertIn("ROOT_MISMATCH", reasons)
            finally:
                shutil.rmtree(other, ignore_errors=True)

    def test_unexpected_dirty_tree_blocked_unless_acknowledged(self):
        with synthetic_repo() as (root, head):
            with open(os.path.join(root, "README.md"), "a", encoding="utf-8") as handle:
                handle.write("dirty\n")
            reasons, ctx, _config, _root = claude_dev.preflight(root, head, [])
            self.assertIn("DIRTY_TREE_UNEXPECTED", reasons)
            self.assertEqual(ctx["unexpected_dirty"], ["README.md"])

            reasons, _ctx, _config, _root = claude_dev.preflight(root, head, ["README.md"])
            self.assertNotIn("DIRTY_TREE_UNEXPECTED", reasons)

    def test_config_missing_reported(self):
        with synthetic_repo(write_config=False) as (root, head):
            reasons, _ctx, config, _root = claude_dev.preflight(root, head, [])
            self.assertIn("CONFIG_MISSING", reasons)
            self.assertIsNone(config)

    def test_config_tracked_by_git_is_rejected(self):
        with synthetic_repo() as (root, head):
            _git(root, "add", "-f", ".claude/workflow.local.json")
            _git(root, "-c", "user.name=T", "-c", "user.email=t@example.com",
                 "commit", "-q", "-m", "track config")
            reasons, _ctx, config, _root = claude_dev.preflight(root, head, [])
            self.assertIn("CONFIG_TRACKED_BY_GIT", reasons)
            self.assertIsNone(config)

    def test_config_nan_or_infinite_budget_rejected(self):
        with synthetic_repo() as (root, head):
            for token in ("NaN", "Infinity", "-Infinity"):
                with self.subTest(token=token):
                    payload = (
                        '{"root": %s, "branch": %s, "model": "claude-sonnet-5", "max_budget_usd": %s}'
                        % (json.dumps(root), json.dumps("claude/test-branch"), token)
                    )
                    with open(os.path.join(root, ".claude", "workflow.local.json"), "w",
                              encoding="utf-8") as handle:
                        handle.write(payload)
                    reasons, _ctx, config, _root = claude_dev.preflight(root, head, [])
                    self.assertIn("CONFIG_INVALID_TYPE", reasons)
                    self.assertIsNone(config)

    def test_claude_dir_symlink_config_rejected(self):
        with synthetic_repo(write_config=False, write_policy=False) as (root, head):
            real_claude_dir = os.path.join(root, "real_claude_dir")
            os.makedirs(real_claude_dir)
            os.symlink(real_claude_dir, os.path.join(root, ".claude"))
            reasons, _ctx, config, _root = claude_dev.preflight(root, head, [])
            self.assertIn("CLAUDE_DIR_IS_SYMLINK", reasons)
            self.assertIsNone(config)

    def test_allow_dirty_symlink_path_rejected(self):
        with synthetic_repo() as (root, head):
            with open(os.path.join(root, "real.txt"), "w", encoding="utf-8") as handle:
                handle.write("x\n")
            os.symlink(os.path.join(root, "real.txt"), os.path.join(root, "link.txt"))
            reasons, _ctx, _config, _root = claude_dev.preflight(root, head, ["link.txt"])
            self.assertIn("ALLOW_DIRTY_PATH_SYMLINK", reasons)

    def test_untracked_nested_directory_reported_individually(self):
        with synthetic_repo() as (root, head):
            nested = os.path.join(root, "newdir", "sub")
            os.makedirs(nested)
            with open(os.path.join(nested, "file.txt"), "w", encoding="utf-8") as handle:
                handle.write("x\n")
            entries, reason = claude_dev._status_entries(root)
            self.assertIsNone(reason)
            self.assertIn("newdir/sub/file.txt", entries)
            self.assertNotIn("newdir/", entries)


class CheckCommandTests(unittest.TestCase):
    def test_ready_when_clean(self):
        with synthetic_repo() as (root, head):
            code, out, _err = run_cli(["--check", "--baseline", head])
            report = json.loads(out)
            self.assertEqual(report["status"], "READY")
            self.assertEqual(code, 0)

    def test_locked_when_lock_dir_present(self):
        with synthetic_repo() as (root, _head):
            os.makedirs(os.path.join(root, ".claude", "dev.lock"))
            code, out, _err = run_cli(["--check"])
            report = json.loads(out)
            self.assertEqual(report["status"], "LOCKED")
            self.assertNotEqual(code, 0)

    def test_locked_when_lock_path_is_a_plain_file(self):
        with synthetic_repo() as (root, _head):
            with open(os.path.join(root, ".claude", "dev.lock"), "w", encoding="utf-8") as handle:
                handle.write("stale\n")
            code, out, _err = run_cli(["--check"])
            report = json.loads(out)
            self.assertEqual(report["status"], "LOCKED")
            self.assertNotEqual(code, 0)

    def test_locked_when_lock_path_is_a_dangling_symlink(self):
        with synthetic_repo() as (root, _head):
            os.symlink(os.path.join(root, "nowhere"), os.path.join(root, ".claude", "dev.lock"))
            code, out, _err = run_cli(["--check"])
            report = json.loads(out)
            self.assertEqual(report["status"], "LOCKED")
            self.assertNotEqual(code, 0)


class LockTests(unittest.TestCase):
    def test_existing_lock_blocks_a_second_launcher(self):
        with synthetic_repo() as (root, head):
            lock_dir = os.path.join(root, ".claude", "dev.lock")
            os.makedirs(lock_dir)
            task_path = _write_task(root, "no-op")
            code, out, _err = run_cli([
                "--task", task_path, "--baseline", head, "--write-path", "README.md",
            ])
            report = json.loads(out)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("LOCK_PRESENT", report["reasons"])
            self.assertNotEqual(code, 0)

    def test_stale_lock_is_never_auto_removed(self):
        with synthetic_repo() as (root, head):
            lock_dir = os.path.join(root, ".claude", "dev.lock")
            os.makedirs(lock_dir)
            task_path = _write_task(root, "no-op")
            run_cli(["--task", task_path, "--baseline", head, "--write-path", "README.md"])
            self.assertTrue(os.path.isdir(lock_dir))

    def test_lock_is_released_after_a_successful_run(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            with _patched_claude(exit_code=0, stdout_bytes=_success_bytes()):
                run_cli(["--task", task_path, "--baseline", head, "--write-path", "README.md"])
            self.assertFalse(os.path.isdir(os.path.join(root, ".claude", "dev.lock")))

    def test_lock_is_retained_on_timeout_until_po_audits_descendants(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            with _patched_claude(raises_timeout=True):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md", "--timeout", "1",
                ])
            report = json.loads(out)
            self.assertTrue(report["timed_out"])
            self.assertIn("TIMEOUT", report["reasons"])
            self.assertNotEqual(code, 0)
            self.assertTrue(os.path.isdir(os.path.join(root, ".claude", "dev.lock")))


def _write_task(root, text):
    path = os.path.join(root, ".claude", "tasks")
    os.makedirs(path, exist_ok=True)
    task_path = os.path.join(path, "task.txt")
    with open(task_path, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    return task_path


class RunTaskResultValidationTests(unittest.TestCase):
    def test_success_result_passes(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            with _patched_claude(exit_code=0, stdout_bytes=_success_bytes("ok")):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "COMPLETED_LOCAL")
            self.assertEqual(report["result_text"], "ok")
            self.assertEqual(code, 0)

    def test_nonzero_child_exit_fails_even_with_success_looking_json(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            with _patched_claude(exit_code=1, stdout_bytes=_success_bytes("ok")):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("CHILD_NONZERO_EXIT", report["reasons"])
            self.assertNotEqual(code, 0)

    def test_is_error_true_fails(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            payload = json.dumps({"is_error": True, "permission_denials": [], "result": "ok"}).encode("utf-8")
            with _patched_claude(exit_code=0, stdout_bytes=payload):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("RESULT_IS_ERROR", report["reasons"])
            self.assertNotEqual(code, 0)

    def test_permission_denials_fail(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            payload = json.dumps(
                {"is_error": False, "permission_denials": ["Bash(rm -rf /)"], "result": "ok"}
            ).encode("utf-8")
            with _patched_claude(exit_code=0, stdout_bytes=payload):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("RESULT_PERMISSION_DENIALS", report["reasons"])
            self.assertNotEqual(code, 0)

    def test_malformed_result_fails(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            with _patched_claude(exit_code=0, stdout_bytes=b"not json"):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("RESULT_MISSING_OR_MALFORMED", report["reasons"])
            self.assertNotEqual(code, 0)

    def test_empty_dict_result_is_rejected(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            with _patched_claude(exit_code=0, stdout_bytes=b"{}"):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("RESULT_IS_ERROR", report["reasons"])
            self.assertNotEqual(code, 0)

    def test_json_list_result_is_rejected_safely(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            with _patched_claude(exit_code=0, stdout_bytes=b"[1, 2, 3]"):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("RESULT_MISSING_OR_MALFORMED", report["reasons"])
            self.assertIsNone(report["result_text"])
            self.assertNotEqual(code, 0)

    def test_missing_is_error_key_is_rejected(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            payload = json.dumps({"permission_denials": [], "result": "ok"}).encode("utf-8")
            with _patched_claude(exit_code=0, stdout_bytes=payload):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("RESULT_IS_ERROR", report["reasons"])
            self.assertNotEqual(code, 0)

    def test_empty_string_result_is_rejected(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            payload = json.dumps({"is_error": False, "permission_denials": [], "result": ""}).encode("utf-8")
            with _patched_claude(exit_code=0, stdout_bytes=payload):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("RESULT_MISSING_OR_MALFORMED", report["reasons"])
            self.assertNotEqual(code, 0)

    def test_non_string_result_is_rejected(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            payload = json.dumps({"is_error": False, "permission_denials": [], "result": 123}).encode("utf-8")
            with _patched_claude(exit_code=0, stdout_bytes=payload):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("RESULT_MISSING_OR_MALFORMED", report["reasons"])
            self.assertNotEqual(code, 0)


class ProtectedWritePathTests(unittest.TestCase):
    def test_protected_write_path_blocks_before_any_claude_call(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            called = []
            with _patched_claude(exit_code=0, stdout_bytes=_success_bytes(), on_call=lambda: called.append(1)):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "PROJECT_CONTROL.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("WRITE_PATH_INVALID", report["reasons"])
            self.assertEqual(called, [])
            self.assertNotEqual(code, 0)


class PostflightScopeTests(unittest.TestCase):
    def test_edit_within_write_path_passes(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")

            def edit_in_scope():
                with open(os.path.join(root, "README.md"), "a", encoding="utf-8") as handle:
                    handle.write("edited\n")

            with _patched_claude(exit_code=0, stdout_bytes=_success_bytes(), on_call=edit_in_scope):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "COMPLETED_LOCAL")
            self.assertEqual(code, 0)

    def test_edit_outside_write_path_fails_scope_check(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")

            def edit_out_of_scope():
                with open(os.path.join(root, "unexpected.txt"), "w", encoding="utf-8") as handle:
                    handle.write("surprise\n")

            with _patched_claude(exit_code=0, stdout_bytes=_success_bytes(), on_call=edit_out_of_scope):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("POSTFLIGHT_SCOPE_VIOLATION", report["reasons"])
            self.assertNotEqual(code, 0)
            # Edits are preserved; the launcher never auto-cleans the tree.
            self.assertTrue(os.path.isfile(os.path.join(root, "unexpected.txt")))

    def test_modifying_an_allow_dirty_file_outside_scope_fails(self):
        with synthetic_repo() as (root, head):
            with open(os.path.join(root, "README.md"), "a", encoding="utf-8") as handle:
                handle.write("pre-existing dirty\n")
            task_path = _write_task(root, "no-op")

            def touch_allow_dirty_file():
                with open(os.path.join(root, "README.md"), "a", encoding="utf-8") as handle:
                    handle.write("unauthorized\n")

            with _patched_claude(exit_code=0, stdout_bytes=_success_bytes(), on_call=touch_allow_dirty_file):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head,
                    "--write-path", "docs/STATUS.md", "--allow-dirty", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "FAILED")
            self.assertIn("POSTFLIGHT_ALLOW_DIRTY_MODIFIED", report["reasons"])
            self.assertNotEqual(code, 0)


class UsageTests(unittest.TestCase):
    def test_check_and_task_together_is_rejected(self):
        code, _out, err = run_cli(["--check", "--task", "x", "--baseline", ZERO_SHA])
        self.assertEqual(code, 2)
        self.assertIn("exactly one", err)

    def test_task_without_baseline_is_rejected(self):
        code, _out, err = run_cli(["--task", "x"])
        self.assertEqual(code, 2)
        self.assertIn("--baseline", err)

    def test_non_positive_timeout_is_rejected_without_traceback(self):
        for bad_timeout in ("0", "-1"):
            with self.subTest(bad_timeout=bad_timeout):
                code, _out, err = run_cli(
                    ["--task", "x", "--baseline", ZERO_SHA, "--timeout", bad_timeout]
                )
                self.assertEqual(code, 2)
                self.assertIn("--timeout", err)


class WritePathSymlinkTests(unittest.TestCase):
    def test_write_path_through_symlink_is_blocked(self):
        with synthetic_repo() as (root, head):
            os.symlink(os.path.join(root, "README.md"), os.path.join(root, "link.md"))
            task_path = _write_task(root, "no-op")
            called = []
            with _patched_claude(exit_code=0, stdout_bytes=_success_bytes(), on_call=lambda: called.append(1)):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "link.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("WRITE_PATH_SYMLINK", report["reasons"])
            self.assertEqual(called, [])
            self.assertNotEqual(code, 0)


class PostLockRaceTests(unittest.TestCase):
    def test_dirty_tree_introduced_after_initial_preflight_is_caught_post_lock(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")

            real_acquire_lock = claude_dev._acquire_lock

            def acquire_then_dirty(script_root):
                lock_path, reason = real_acquire_lock(script_root)
                if lock_path is not None:
                    with open(os.path.join(script_root, "race.txt"), "w", encoding="utf-8") as handle:
                        handle.write("introduced-after-first-preflight\n")
                return lock_path, reason

            with mock.patch.object(claude_dev, "_acquire_lock", side_effect=acquire_then_dirty):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("DIRTY_TREE_UNEXPECTED", report["reasons"])
            self.assertNotEqual(code, 0)
            self.assertFalse(os.path.isdir(os.path.join(root, ".claude", "dev.lock")))


class ChildProcessGroupTests(unittest.TestCase):
    def test_timeout_terminates_whole_process_group_before_lock_release(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")

            fake_proc = mock.Mock()
            fake_proc.pid = 4242
            fake_proc.wait.side_effect = [
                subprocess.TimeoutExpired(cmd="claude", timeout=1),
                subprocess.TimeoutExpired(cmd="claude", timeout=5),
                0,
                0,
            ]
            killpg_calls = []
            real_popen = subprocess.Popen

            def fake_popen(args, **kwargs):
                if args[:1] == ["git"]:
                    return real_popen(args, **kwargs)
                return fake_proc

            with mock.patch.object(claude_dev.subprocess, "Popen", side_effect=fake_popen) as popen_mock, \
                 mock.patch.object(claude_dev.os, "getpgid", return_value=4242), \
                 mock.patch.object(
                     claude_dev.os, "killpg",
                     side_effect=lambda pgid, sig: killpg_calls.append((pgid, sig)),
                 ):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md", "--timeout", "1",
                ])

            claude_calls = [c for c in popen_mock.call_args_list if c.args[0][:1] != ["git"]]
            self.assertEqual(len(claude_calls), 1)
            self.assertTrue(claude_calls[0].kwargs.get("start_new_session"))
            self.assertEqual(
                killpg_calls,
                [(4242, claude_dev.signal.SIGTERM), (4242, claude_dev.signal.SIGKILL)],
            )
            report = json.loads(out)
            self.assertTrue(report["timed_out"])
            self.assertIn("TIMEOUT", report["reasons"])
            self.assertNotEqual(code, 0)
            self.assertTrue(os.path.isdir(os.path.join(root, ".claude", "dev.lock")))

    def test_unsupported_process_group_platform_blocks_before_launch(self):
        with synthetic_repo() as (root, head):
            task_path = _write_task(root, "no-op")
            called = []
            with mock.patch.object(claude_dev, "_supports_process_groups", return_value=False), \
                 _patched_claude(exit_code=0, stdout_bytes=_success_bytes(), on_call=lambda: called.append(1)):
                code, out, _err = run_cli([
                    "--task", task_path, "--baseline", head, "--write-path", "README.md",
                ])
            report = json.loads(out)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("PROCESS_GROUP_UNSUPPORTED", report["reasons"])
            self.assertEqual(called, [])
            self.assertNotEqual(code, 0)


class IndependentReviewRegressionTests(unittest.TestCase):
    def test_final_newline_does_not_expand_a_permission_path(self):
        self.assertEqual(claude_dev._validate_relpath("docs/STATUS.md\n", False), "PATH_UNSAFE_CHARS")

    def test_unit_test_tripwire_blocks_an_unmocked_live_claude(self):
        with synthetic_repo():
            with self.assertRaisesRegex(AssertionError, "never start a real Claude"):
                subprocess.Popen(["claude", "-p", "this must never leave the test process"])

    def test_exited_leader_does_not_leave_sigterm_ignoring_group_members(self):
        proc = mock.Mock(pid=4242)
        proc.wait.return_value = 0
        with mock.patch.object(claude_dev.os, "killpg") as kill:
            claude_dev._terminate_process_group(proc)
        self.assertEqual(kill.call_args_list, [
            mock.call(4242, claude_dev.signal.SIGTERM),
            mock.call(4242, claude_dev.signal.SIGKILL),
        ])

    def test_interrupt_terminates_group_before_returning(self):
        proc = mock.Mock(pid=4242)
        proc.wait.side_effect = [KeyboardInterrupt(), 0, 0]
        with mock.patch.object(claude_dev.subprocess, "Popen", return_value=proc) as start, \
             mock.patch.object(claude_dev.os, "killpg") as kill:
            with self.assertRaises(KeyboardInterrupt):
                claude_dev._run_child(["claude"], ".", None, None, 1)
        self.assertTrue(start.call_args.kwargs["start_new_session"])
        self.assertEqual(start.call_args.kwargs["env"]["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"], "1")
        self.assertEqual(kill.call_args_list[-1], mock.call(4242, claude_dev.signal.SIGKILL))


class PolicyAndOutputTests(unittest.TestCase):
    def test_policy_filesystem_paths_are_anchored_to_canonical_root(self):
        with synthetic_repo() as (root, _head):
            policy_path = os.path.join(root, ".claude", "dev-policy.json")
            with open(policy_path, "w") as f:
                json.dump({"sandbox": {"filesystem": {"denyWrite": [".git", "PROJECT_CONTROL.md"], "denyRead": ["~/.ssh"]}}}, f)
            args = claude_dev._build_claude_args("claude-sonnet-5", 1, policy_path, ["README.md"])
            policy = json.loads(args[args.index("--settings") + 1])
            self.assertEqual(policy["sandbox"]["filesystem"]["denyWrite"], [os.path.join(root, ".git"), os.path.join(root, "PROJECT_CONTROL.md")])
            self.assertEqual(policy["sandbox"]["filesystem"]["denyRead"], ["~/.ssh"])

    def test_invalid_cli_arguments_do_not_echo_sensitive_values(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as exc:
            claude_dev.main(["--unknown", "private-path-or-token"])
        self.assertEqual(exc.exception.code, 2)
        self.assertNotIn("private-path-or-token", err.getvalue())
        self.assertIn("INVALID_CLI_ARGUMENTS", err.getvalue())


if __name__ == "__main__":
    unittest.main()
