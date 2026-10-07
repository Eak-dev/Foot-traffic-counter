#!/usr/bin/env python3
"""Local Claude Code launcher for scoped, reviewed development tasks.

Python 3.9+ standard library only. This never switches branches, commits,
pushes, or contacts GitHub. `--check` only inspects local state and never
calls the `claude` binary. `--task` additionally runs one pre-reviewed,
non-secret task through a restricted `claude` subprocess.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
import uuid

SCHEMA_VERSION = 1
MODE = "LOCAL_DEV_LAUNCHER"
DEFAULT_TIMEOUT_SECONDS = 600
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

CONFIG_RELPATH = (".claude", "workflow.local.json")
POLICY_RELPATH = (".claude", "dev-policy.json")
LOCK_RELPATH = (".claude", "dev.lock")
TASKS_RELPATH = (".claude", "tasks")
RESULTS_RELPATH = (".claude", "results")
CONFIG_KEYS = ("root", "branch", "model", "max_budget_usd")

PROTECTED_WRITE_EXACT = {"PROJECT_CONTROL.md", "tools/claude_dev.py"}
PROTECTED_WRITE_PREFIXES = (".git/", ".claude/", "data/", "reports/", "artifacts/", "secrets/")
PROTECTED_WRITE_PATTERNS = (".env*", "*.key", "credentials*.json", "service-account*.json")
SAFE_PATH_CHARS_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
UNITTEST_BASH_COMMAND = "python3 -m unittest discover -s tests -t . -v"


def _run_git(args, cwd):
    """Run git without a shell, read-only (GIT_OPTIONAL_LOCKS=0). Returns
    (exit_code, stdout) or (None, "")."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    try:
        proc = subprocess.run(
            ["git"] + list(args), cwd=cwd, capture_output=True, text=True, timeout=30, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return proc.returncode, proc.stdout


def _rev_parse(cwd, *args):
    code, out = _run_git(["rev-parse"] + list(args), cwd)
    return out.strip() if code == 0 else None


def _is_tracked(cwd, relparts):
    code, out = _run_git(["ls-files", "--", "/".join(relparts)], cwd)
    return code == 0 and out.strip() != ""


def _script_root():
    return os.path.realpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_config(script_root):
    """Load .claude/workflow.local.json. Never surfaces the path or raw errors."""
    claude_dir = os.path.join(script_root, CONFIG_RELPATH[0])
    if os.path.islink(claude_dir):
        return None, "CLAUDE_DIR_IS_SYMLINK"
    path = os.path.join(script_root, *CONFIG_RELPATH)
    if os.path.islink(path):
        return None, "CONFIG_IS_SYMLINK"
    if not os.path.isfile(path):
        return None, "CONFIG_MISSING"
    if _is_tracked(script_root, CONFIG_RELPATH):
        return None, "CONFIG_TRACKED_BY_GIT"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None, "CONFIG_MALFORMED"
    if not isinstance(data, dict) or any(key not in data for key in CONFIG_KEYS):
        return None, "CONFIG_INCOMPLETE"
    root, branch, model, budget = (data[k] for k in CONFIG_KEYS)
    if not isinstance(root, str) or not isinstance(branch, str) or not isinstance(model, str):
        return None, "CONFIG_INVALID_TYPE"
    if not isinstance(budget, (int, float)) or isinstance(budget, bool) or budget <= 0:
        return None, "CONFIG_INVALID_TYPE"
    if isinstance(budget, float) and (math.isnan(budget) or math.isinf(budget)):
        return None, "CONFIG_INVALID_TYPE"
    return data, None


def _resolve_configured_root(script_root, root_value):
    candidate = root_value if os.path.isabs(root_value) else os.path.join(script_root, root_value)
    return os.path.realpath(candidate)


def _validate_relpath(path, allow_protected):
    """Reject absolute paths, traversal, permission-rule metacharacters and
    (unless allowed) protected locations. Secret-like filenames are always
    rejected, even nested, regardless of allow_protected."""
    if not isinstance(path, str) or not path or "\x00" in path:
        return "PATH_INVALID"
    if os.path.isabs(path) or path.startswith("~"):
        return "PATH_NOT_RELATIVE"
    if not SAFE_PATH_CHARS_RE.fullmatch(path):
        return "PATH_UNSAFE_CHARS"
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "PATH_TRAVERSAL"
    if any(fnmatch.fnmatch(part, pattern) for part in parts for pattern in PROTECTED_WRITE_PATTERNS):
        return "PATH_PROTECTED"
    if allow_protected:
        return None
    if path in PROTECTED_WRITE_EXACT or path in {p[:-1] for p in PROTECTED_WRITE_PREFIXES} or any(path.startswith(p) for p in PROTECTED_WRITE_PREFIXES):
        return "PATH_PROTECTED"
    return None


def _has_symlink_ancestor_or_self(root, relpath):
    """True if relpath, or any directory component leading to it, is a
    symlink. Prevents hashing or editing through a symlink out of root."""
    current = root
    for part in relpath.split("/"):
        current = os.path.join(current, part)
        if os.path.islink(current):
            return True
    return False


def _status_entries(cwd):
    """Parse `git status --porcelain=v1 -z --untracked-files=all` so nested
    new files/dirs are reported individually, not collapsed to a dir name.
    A rename/copy is rejected, not parsed."""
    code, out = _run_git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd)
    if code != 0:
        return None, "GIT_STATUS_FAILED"
    tokens = out.split("\x00")
    if tokens and tokens[-1] == "":
        tokens.pop()
    entries = []
    for token in tokens:
        if len(token) < 4 or token[2] != " ":
            return None, "GIT_STATUS_UNEXPECTED_FORMAT"
        if "R" in token[:2] or "C" in token[:2]:
            return None, "DIRTY_TREE_RENAME_UNSUPPORTED"
        entries.append(token[3:])
    return entries, None


def _hash_file(root, relpath):
    """Never follow a symlink (file or ancestor dir) out of root to hash it."""
    if _has_symlink_ancestor_or_self(root, relpath):
        return None
    try:
        with open(os.path.join(root, *relpath.split("/")), "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def _report(command, status, reasons, **extra):
    report = {
        "tool": "claude_dev", "command": command, "schema_version": SCHEMA_VERSION,
        "mode": MODE, "status": status, "reasons": reasons,
    }
    report.update(extra)
    return report


def preflight(cwd, baseline, allow_dirty):
    """Read-only checks shared by --check and --task. Never calls claude."""
    reasons = []
    script_root = _script_root()
    canonical_cwd = os.path.realpath(cwd)
    git_root_raw = _rev_parse(cwd, "--show-toplevel")
    git_root = os.path.realpath(git_root_raw) if git_root_raw is not None else None
    config, config_reason = _load_config(script_root)
    branch = _rev_parse(cwd, "--abbrev-ref", "HEAD")
    head = _rev_parse(cwd, "HEAD")
    ctx = {"branch": branch, "head": head, "unexpected_dirty": []}

    if git_root is None:
        reasons.append("NOT_A_GIT_REPO")
    if config_reason:
        reasons.append(config_reason)
    if git_root is not None and config is not None:
        configured_root = _resolve_configured_root(script_root, config["root"])
        if not (canonical_cwd == script_root == git_root == configured_root):
            reasons.append("ROOT_MISMATCH")

    if branch is None or head is None:
        reasons.append("GIT_STATE_UNREADABLE")
    elif branch == "HEAD":
        reasons.append("DETACHED_HEAD")
    elif branch in ("main", "master"):
        reasons.append("PROTECTED_BRANCH")
    elif config is not None and branch != config["branch"]:
        reasons.append("BRANCH_MISMATCH")

    if baseline is not None:
        if not SHA_RE.match(baseline):
            reasons.append("BASELINE_INVALID_FORMAT")
        elif head is not None and baseline != head:
            reasons.append("BASELINE_MISMATCH")

    if any(_validate_relpath(path, allow_protected=True) for path in allow_dirty):
        reasons.append("ALLOW_DIRTY_PATH_INVALID")
    elif any(_has_symlink_ancestor_or_self(script_root, path) for path in allow_dirty):
        reasons.append("ALLOW_DIRTY_PATH_SYMLINK")

    if git_root is not None:
        dirty_paths, dirty_reason = _status_entries(cwd)
        if dirty_reason:
            reasons.append(dirty_reason)
        else:
            ctx["unexpected_dirty"] = sorted(set(dirty_paths) - set(allow_dirty))
            if ctx["unexpected_dirty"]:
                reasons.append("DIRTY_TREE_UNEXPECTED")

    ctx["lock_present"] = os.path.lexists(os.path.join(script_root, *LOCK_RELPATH))
    return reasons, ctx, config, script_root


def run_check(args):
    reasons, ctx, _config, _root = preflight(os.getcwd(), args.baseline, args.allow_dirty)
    status = "BLOCKED" if reasons else ("LOCKED" if ctx["lock_present"] else "READY")
    report = _report(
        "check", status, reasons, branch=ctx["branch"], head=ctx["head"],
        lock_present=ctx["lock_present"], unexpected_dirty=ctx["unexpected_dirty"],
    )
    return report, 0 if status == "READY" else 1


def _acquire_lock(script_root):
    path = os.path.join(script_root, *LOCK_RELPATH)
    try:
        os.mkdir(path)
    except FileExistsError:
        return None, "LOCK_PRESENT"
    except OSError:
        return None, "LOCK_FAILED"
    return path, None


def _release_lock(lock_path):
    if lock_path is not None:
        try:
            os.rmdir(lock_path)
        except OSError:
            pass


def _build_claude_args(model, budget, policy_path, write_paths):
    # Inline CLI settings use the task cwd as their anchor. Resolve filesystem
    # paths explicitly so moving the policy into .claude does not change scope.
    with open(policy_path, encoding="utf-8") as policy_file:
        policy = json.load(policy_file)
    if not isinstance(policy, dict):
        raise ValueError("invalid policy")
    root = os.path.dirname(os.path.dirname(policy_path))
    filesystem = policy.get("sandbox", {}).get("filesystem", {})
    for key in ("allowRead", "denyRead", "allowWrite", "denyWrite"):
        if key in filesystem:
            filesystem[key] = [
                item if item.startswith(("/", "~")) else os.path.join(root, item)
                for item in filesystem[key]
            ]
    allowed = ["Read", "Glob", "Grep"]
    allowed += ["Edit(%s)" % path for path in write_paths]
    allowed.append("Bash(%s)" % UNITTEST_BASH_COMMAND)
    return [
        "claude", "-p",
        "--model", model,
        "--effort", "medium",
        "--restricted",
        "--permission-mode", "dontAsk",
        "--permission-prompts", "none",
        "--tools", "Read,Glob,Grep,Write,Edit,Bash",
        "--allowedTools", ",".join(allowed),
        "--settings", json.dumps(policy),
        "--strict-mcp-config",
        "--mcp-config", "{\"mcpServers\":{}}",
        "--disable-slash-commands",
        "--no-chrome",
        "--no-session-persistence",
        "--max-budget-usd", str(budget),
        "--output-format", "json",
    ]


def _write_prompt(root, baseline, branch, write_paths, task_text):
    header = (
        "BASELINE_SHA: %s\nBRANCH: %s\nALLOWED_WRITE_PATHS:\n%s\n"
        "INSTRUCTION: You may read any non-secret project file for context "
        "(rules, docs, source). You may only EDIT the files listed in "
        "ALLOWED_WRITE_PATHS. Run tests only via exactly: %s\n---\n"
    ) % (baseline, branch, "\n".join("- %s" % p for p in write_paths), UNITTEST_BASH_COMMAND)
    tasks_dir = os.path.join(root, *TASKS_RELPATH)
    os.makedirs(tasks_dir, exist_ok=True)
    prompt_path = os.path.join(tasks_dir, "%s.prompt.txt" % uuid.uuid4().hex)
    with open(prompt_path, "w", encoding="utf-8") as handle:
        handle.write(header + task_text)
    return prompt_path


def _evaluate_result(child_exit, timed_out, result_obj):
    """Never trust the child's own narrative: require a well-formed dict
    with is_error exactly False, a non-empty string result, and no
    permission denials. Anything else (including {} or a bare list) fails."""
    if timed_out:
        return False, "TIMEOUT"
    if child_exit != 0:
        return False, "CHILD_NONZERO_EXIT"
    if not isinstance(result_obj, dict):
        return False, "RESULT_MISSING_OR_MALFORMED"
    if result_obj.get("is_error") is not False:
        return False, "RESULT_IS_ERROR"
    result_text = result_obj.get("result")
    if not isinstance(result_text, str) or not result_text.strip():
        return False, "RESULT_MISSING_OR_MALFORMED"
    if result_obj.get("permission_denials"):
        return False, "RESULT_PERMISSION_DENIALS"
    return True, None


def _supports_process_groups():
    return os.name == "posix" and hasattr(os, "setsid") and hasattr(os, "killpg") and hasattr(os, "getpgid")


def _terminate_process_group(proc):
    """The session leader PID is also its group ID, even after it exits.

    Always kill remaining group members after waiting for the leader: a
    successful wait does not prove a descendant respected SIGTERM.
    Timeout/interrupt callers retain the cooperative lock for PO audit,
    since manually detached descendants can escape a process group.
    """
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass
        if sig == signal.SIGTERM:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
    proc.wait(timeout=3)


def _run_child(claude_args, cwd, stdin_f, stdout_f, timeout):
    """Run the claude child in its own process group (POSIX session leader)
    so a timeout or interrupt can terminate every process it spawned, not
    just the leader, before the caller releases the lock. Returns
    (child_exit, timed_out)."""
    proc = subprocess.Popen(
        claude_args, cwd=cwd, stdin=stdin_f, stdout=stdout_f,
        stderr=subprocess.DEVNULL, start_new_session=True,
        env=dict(os.environ, CLAUDE_CODE_DISABLE_BACKGROUND_TASKS="1"),
    )
    try:
        return proc.wait(timeout=timeout), False
    except subprocess.TimeoutExpired:
        _terminate_process_group(proc)
        return None, True
    except KeyboardInterrupt:
        _terminate_process_group(proc)
        raise


def _postflight_reasons(script_root, before_branch, before_head, write_path, allow_dirty, pre_hashes):
    reasons = []
    if _rev_parse(script_root, "--abbrev-ref", "HEAD") != before_branch:
        reasons.append("POSTFLIGHT_BRANCH_CHANGED")
    if _rev_parse(script_root, "HEAD") != before_head:
        reasons.append("POSTFLIGHT_HEAD_CHANGED")
    after_entries, after_reason = _status_entries(script_root)
    if after_reason:
        reasons.append(after_reason)
    elif set(after_entries) - (set(write_path) | set(allow_dirty)):
        reasons.append("POSTFLIGHT_SCOPE_VIOLATION")
    for path, before in pre_hashes.items():
        if path not in write_path and _hash_file(script_root, path) != before:
            reasons.append("POSTFLIGHT_ALLOW_DIRTY_MODIFIED")
            break
    return reasons


def run_task(args):
    reasons, ctx, config, script_root = preflight(os.getcwd(), args.baseline, args.allow_dirty)
    if any(_validate_relpath(path, allow_protected=False) for path in args.write_path):
        reasons.append("WRITE_PATH_INVALID")
    elif any(_has_symlink_ancestor_or_self(script_root, path) for path in args.write_path):
        reasons.append("WRITE_PATH_SYMLINK")
    if reasons or ctx["lock_present"]:
        return _report("task", "BLOCKED", reasons or ["LOCK_PRESENT"],
                        branch=ctx["branch"], head=ctx["head"]), 1

    policy_path = os.path.join(script_root, *POLICY_RELPATH)
    if os.path.islink(policy_path) or not os.path.isfile(policy_path):
        return _report("task", "BLOCKED", ["POLICY_MISSING"]), 1

    if not _supports_process_groups():
        return _report("task", "BLOCKED", ["PROCESS_GROUP_UNSUPPORTED"]), 1

    lock_path, lock_reason = _acquire_lock(script_root)
    if lock_reason:
        return _report("task", "BLOCKED", [lock_reason]), 1

    release_ownership = True
    try:
        # Re-check preflight now that the lock is held, closing the race
        # where two launchers both pass preflight before either locks.
        reasons2, ctx2, config2, _root2 = preflight(os.getcwd(), args.baseline, args.allow_dirty)
        if reasons2:
            return _report("task", "BLOCKED", reasons2, branch=ctx2["branch"], head=ctx2["head"]), 1
        ctx, config = ctx2, config2

        dirty_paths, dirty_reason = _status_entries(script_root)
        if dirty_reason:
            return _report("task", "BLOCKED", [dirty_reason]), 1
        pre_hashes = {path: _hash_file(script_root, path) for path in dirty_paths}

        try:
            with open(args.task, "r", encoding="utf-8") as handle:
                task_text = handle.read()
        except (OSError, UnicodeError):
            return _report("task", "BLOCKED", ["TASK_FILE_UNREADABLE"]), 1

        prompt_path = _write_prompt(script_root, args.baseline, ctx["branch"], args.write_path, task_text)
        try:
            claude_args = _build_claude_args(config["model"], config["max_budget_usd"], policy_path, args.write_path)
        except (ValueError, TypeError, AttributeError):
            return _report("task", "BLOCKED", ["POLICY_INVALID"]), 1
        results_dir = os.path.join(script_root, *RESULTS_RELPATH)
        os.makedirs(results_dir, exist_ok=True)
        result_path = os.path.join(results_dir, "%s.json" % uuid.uuid4().hex)

        started = time.monotonic()
        try:
            with open(prompt_path, "rb") as stdin_f, open(result_path, "wb") as stdout_f:
                child_exit, timed_out = _run_child(claude_args, script_root, stdin_f, stdout_f, args.timeout)
        except OSError:
            # An OS error could happen after launch, during group cleanup.
            release_ownership = False
            return _report("task", "BLOCKED", ["CLAUDE_LAUNCH_OR_CLEANUP_FAILED"], lock_retained=True), 1
        except KeyboardInterrupt:
            release_ownership = False
            return _report("task", "BLOCKED", ["INTERRUPTED"], lock_retained=True), 130
        if timed_out:
            release_ownership = False
        duration_s = round(time.monotonic() - started, 1)

        try:
            with open(result_path, "r", encoding="utf-8") as handle:
                result_obj = json.loads(handle.read())
        except (OSError, ValueError):
            result_obj = None

        ok, fail_reason = _evaluate_result(child_exit, timed_out, result_obj)
        post_reasons = _postflight_reasons(
            script_root, ctx["branch"], ctx["head"], args.write_path, args.allow_dirty, pre_hashes
        )
        overall_ok = ok and not post_reasons
        if not isinstance(result_obj, dict):
            result_obj = {}
        report = _report(
            "task", "COMPLETED_LOCAL" if overall_ok else "FAILED",
            ([] if ok else [fail_reason]) + post_reasons,
            baseline=args.baseline, branch=ctx["branch"], child_exit=child_exit,
            timed_out=timed_out, lock_retained=not release_ownership, duration_s=duration_s, result_text=result_obj.get("result"),
            usage={
                "raw": result_obj.get("modelUsage") or result_obj.get("usage"),
                "note": "ESTIMATE_ONLY_NOT_BILLING_CONFIRMATION",
            },
        )
        return report, 0 if overall_ok else 3
    except OSError:
        return _report("task", "BLOCKED", ["TASK_RUN_IO_ERROR"]), 1
    finally:
        if release_ownership:
            _release_lock(lock_path)


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "error: INVALID_CLI_ARGUMENTS\n")


def build_parser():
    parser = _SafeParser(prog="claude_dev.py")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--task")
    parser.add_argument("--baseline")
    parser.add_argument("--allow-dirty", action="append", default=[], dest="allow_dirty")
    parser.add_argument("--write-path", action="append", default=[], dest="write_path")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv=None):
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.check == bool(args.task):
        sys.stderr.write("error: exactly one of --check or --task is required\n")
        return 2
    if args.task and not args.baseline:
        sys.stderr.write("error: --task requires --baseline\n")
        return 2
    if args.task and args.timeout <= 0:
        sys.stderr.write("error: --timeout must be greater than 0\n")
        return 2

    report, exit_code = run_check(args) if args.check else run_task(args)
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
