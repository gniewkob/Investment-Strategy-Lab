"""M1 predeployment audit for existing macOS LaunchAgents.

Read-only; never restarts services, writes files, contacts providers, or
exports private paths, credentials, identifiers, holdings or addresses.

This check is a predeployment METADATA gate. It cannot prove that the
already-running Python process has reloaded the on-disk Git checkout.
"""
from __future__ import annotations

import argparse
from hashlib import sha1, sha256
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess

from scripts import portfolio_release_canary as canary

LABEL_PORTFOLIO = "pl.gniewkob.isl.portfolio"
LABEL_HEALTH = "pl.gniewkob.isl.portfolio-health"
LABEL_COLLECTOR = "pl.gniewkob.isl.acceptance"
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
# Reviewed collector v2, Git blob at deployment PR #81 head 3122b571b0e5...
APPROVED_COLLECTOR_GIT_BLOB = "41a8ca1e40af5697f6661b5e158bc205b4fe48ff"


class PreflightRejected(ValueError):
    pass


def require(condition):
    if not condition:
        raise PreflightRejected("M1_PREDEPLOY_READONLY_REJECTED")


def read_launchagent(home, label, uid):
    path = Path(home) / "Library" / "LaunchAgents" / (label + ".plist")
    entry = path.lstat()
    require(stat.S_ISREG(entry.st_mode) and entry.st_uid == uid
            and not entry.st_mode & 0o022 and entry.st_size <= 64_000)
    with path.open("rb") as stream:
        config = plistlib.load(stream)
    require(isinstance(config, dict))
    return config


def option(arguments, flag):
    require(type(arguments) is list and all(type(arg) is str for arg in arguments))
    matched = []
    for i, arg in enumerate(arguments):
        if arg == flag:
            require(i + 1 < len(arguments))
            matched.append(arguments[i + 1])
        elif arg.startswith(flag + "="):
            matched.append(arg[len(flag) + 1:])
    require(len(matched) == 1 and bool(matched[0]))
    return matched[0]


def assert_trusted_git_checkout(root, uid):
    """Fail closed before running Git against a configurable local checkout.

    Never execute repo-defined filters, fsmonitor or hooks to attest a SHA.
    We accept a normal standalone owner-controlled .git directory only.
    A worktree or non-standard repository needs separate review.
    """
    root = Path(root)
    require(root.is_absolute())
    for path in (root, root / ".git"):
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == uid
                and not (info.st_mode & 0o022))
    config = root / ".git" / "config"
    fd = os.open(config, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == uid
                and not (info.st_mode & 0o022)
                and 0 < info.st_size <= 64_000)
        raw = stream.read(64_001)
    require(len(raw) == info.st_size)
    try:
        source = raw.decode("utf-8").lower()
    except UnicodeDecodeError:
        raise PreflightRejected("M1_PREDEPLOY_READONLY_REJECTED") from None
    # Forbid repository-supplied executable entrypoints and config includes.
    # The clean filter driver name can be arbitrary, so disabling only one
    # known filter is NOT sufficient.
    forbidden_section = re.compile(
        r'^\s*\[\s*(?:filter|diff|hook|include|includeif)(?:[\s.\]]|$)',
        flags=re.MULTILINE)
    forbidden_setting = re.compile(
        r'^\s*(?:fsmonitor|hookspath|excludesfile|attributesfile|worktree|'
        r'alternaterefscommand|sshcommand)\s*=',
        flags=re.MULTILINE)
    require(forbidden_section.search(source) is None
            and forbidden_setting.search(source) is None)


def command(*args, cwd=None):
    try:
        if args and args[0] == "git":
            # Absolute system Git; remove inherited Git configuration/env.
            # -c overrides repo fsmonitor and hook paths. --no-optional-locks
            # avoids refreshing or writing the existing runtime index.
            clean_env = {k: v for k, v in os.environ.items()
                         if not k.startswith("GIT_")}
            clean_env.update({
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_ATTR_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            })
            argv = ("/usr/bin/git", "--no-optional-locks",
                    "-c", "core.fsmonitor=false",
                    "-c", "core.hooksPath=/dev/null",
                    "-c", "core.untrackedCache=false",
                    "-c", "core.attributesFile=/dev/null",
                    "-c", "core.excludesFile=/dev/null",
                    "-c", "submodule.recurse=false", *args[1:])
            result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                    timeout=8, check=False, env=clean_env)
        else:
            result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                                    timeout=8, check=False)
    except (OSError, subprocess.SubprocessError):
        raise PreflightRejected("M1_PREDEPLOY_READONLY_REJECTED") from None
    require(result.returncode == 0 and len(result.stdout) < 128_000)
    return result.stdout.strip()


def loaded_collector_arguments(payload):
    """Parse one recognized launchctl-print argument block, never log its text.

    Unknown launcher formats fail closed. The result is compared with the
    already validated plist; neither the arguments nor paths are reported.
    """
    require(type(payload) is str and len(payload) <= 128_000)
    lines = payload.splitlines()
    program_rows = [line.strip().partition(" = ")[2] for line in lines
                    if line.strip().startswith("program = ")]
    require(len(program_rows) == 1 and bool(program_rows[0]))
    openers = [i for i, line in enumerate(lines)
               if line.strip() == "arguments = {"]
    require(len(openers) == 1)
    start = openers[0]
    enders = [i for i in range(start + 1, len(lines))
              if lines[i].strip() == "}"]
    require(bool(enders))
    end = enders[0]
    tokens = [line.strip() for line in lines[start + 1:end]]
    require(bool(tokens) and all(bool(x) and not any(
        ord(ch) < 32 for ch in x) for x in tokens))
    return program_rows[0], tokens


def verified_collector_entrypoint(arguments, *, approved_source=None, uid=None):
    """Require Python isolated mode and an exact approved collector source.

    -I ignores PYTHON* environment variables, user site packages, and
    script-directory import resolution. This prevents an untrusted argparse
    (or another stdlib module) next to the copied file or in PYTHONPATH.
    No code execution, provider access, state write, or service restart.
    """
    require(type(arguments) is list and all(type(a) is str for a in arguments))
    require(len(arguments) >= 3 and Path(arguments[0]).is_absolute())
    exe = Path(arguments[0]).name.lower()
    require(re.fullmatch(r"(?:python(?:3(?:\.\d+)?)?|pypy(?:3(?:\.\d+)?)?)", exe) is not None)
    # A source hash proves only this script, not its imports. The -I
    # interpreter flag must precede the script. All other interpreter
    # modes (including bare script, -m, -c, or extra flags) fail closed.
    require(arguments[1] == "-I" and arguments[2].endswith(".py"))
    script = Path(arguments[2])
    require(script.is_absolute())
    if uid is None:
        uid = os.getuid()
    src = Path(approved_source or Path(__file__).resolve().parent /
               "unattended_acceptance.py")
    # Read only the audited source file, after rejecting symlink/path tricks.
    def trusted_bytes(path):
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            # Do not leak private script paths in low-level exceptions.
            raise PreflightRejected("M1_PREDEPLOY_READONLY_REJECTED") from None
        with os.fdopen(fd, "rb") as stream:
            st = os.fstat(stream.fileno())
            require(stat.S_ISREG(st.st_mode) and st.st_uid == uid
                    and not (st.st_mode & 0o022)
                    and 10_000 <= st.st_size <= 200_000)
            raw = stream.read(200_001)
        require(len(raw) == st.st_size and len(raw) <= 200_000)
        return raw

    approved = trusted_bytes(src)
    signature = sha1(b"blob " + str(len(approved)).encode("ascii") +
                     b"\x00" + approved).hexdigest()
    require(signature == APPROVED_COLLECTOR_GIT_BLOB)
    deployed = trusted_bytes(script)
    require(sha256(deployed).digest() == sha256(approved).digest())
    return "REVIEWED_ISOLATED_COPIED_PYTHON_SCRIPT"


def check(expected, *, home=None, uid=None, reader=read_launchagent,
          command_fn=command, probe=None, now=None, stage=None):
    """Inspect metadata of the existing job; no mutation or financial access."""
    def step(code):
        if stage is not None:
            stage(code)

    step("VALIDATE_EXPECTED_SHA")
    require(type(expected) is str and SHA_RE.fullmatch(expected) is not None)
    if uid is None:
        uid = os.getuid()
    if home is None:
        home = Path.home()
    if now is None:
        now = datetime.now(timezone.utc)
    if probe is None:
        probe = canary.inspect
    step("READ_LAUNCHAGENT_DEFINITIONS")
    configs = {label: reader(home, label, uid) for label in
               (LABEL_PORTFOLIO, LABEL_HEALTH, LABEL_COLLECTOR)}

    step("CHECK_SUPERVISOR_DEFINITION")
    supervisor = configs[LABEL_PORTFOLIO]
    watchdog = configs[LABEL_HEALTH]
    collector = configs[LABEL_COLLECTOR]
    args = supervisor.get("ProgramArguments")
    require(type(args) is list and all(type(x) is str for x in args))
    require("scripts.autonomous_portfolio" in args
            and "--enable-live-read" in args and "--once" not in args)
    config_file = option(args, "--config")
    require(Path(config_file).is_absolute())

    active_root = supervisor.get("WorkingDirectory")
    require(type(active_root) is str and Path(active_root).is_absolute()
            and supervisor.get("KeepAlive") is True
            and supervisor.get("RunAtLoad") is True)
    # Four independent gates distinguish a genuine drift in launchd
    # definitions from an overly strict expectation about CLI layout.
    # Never echo the actual ProgramArguments: they may contain local paths.
    watchdog_args = watchdog.get("ProgramArguments")
    collector_args = collector.get("ProgramArguments")
    step("CHECK_WATCHDOG_COMMAND")
    require(type(watchdog_args) is list
            and all(type(arg) is str for arg in watchdog_args)
            and "--check-health" in watchdog_args)
    step("CHECK_WATCHDOG_INTERVAL")
    require(type(watchdog.get("StartInterval")) is int
            and watchdog["StartInterval"] == 300)
    step("CHECK_COLLECTOR_COMMAND")
    require(type(collector_args) is list and all(type(arg) is str
            for arg in collector_args))
    step("CHECK_COLLECTOR_EXECUTABLE")
    # LaunchAgent Program overrides ProgramArguments[0] when supplied.
    # A mismatched explicit Program would make the collector execute
    # something other than the code whose bytes were attested.
    if "Program" in collector:
        require(type(collector["Program"]) is str
                and collector["Program"] == collector_args[0])
    step("CHECK_COLLECTOR_CODE_IDENTITY")
    collector_mode = verified_collector_entrypoint(collector_args, uid=uid)
    step("CHECK_COLLECTOR_INTERVAL")
    require(type(collector.get("StartInterval")) is int
            and collector["StartInterval"] == 60)

    # 'launchctl print' proves loaded service metadata, not how old Python
    # bytecode or modules in an existing running process were initialized.
    step("CHECK_SUPERVISOR_LAUNCHCTL")
    loaded = command_fn("launchctl", "print", f"gui/{uid}/{LABEL_PORTFOLIO}")
    match = re.search(r"^\s*pid = (\d+)$", loaded, flags=re.MULTILINE)
    require(match is not None and int(match[1]) > 1)
    directory = re.search(r"^\s*working directory = (.+)$",
                          loaded, flags=re.MULTILINE)
    require(directory is not None and directory[1] == active_root)
    step("CHECK_SUPERVISOR_PROCESS")
    cmd = command_fn("ps", "-p", match[1], "-o", "command=")
    require(re.search(r"-m\s+scripts\.autonomous_portfolio(?:\s|$)", cmd) is not None
            and "--once" not in cmd)
    step("CHECK_LOADED_PERIODIC_SCHEDULES")
    loaded_health = command_fn("launchctl", "print", f"gui/{uid}/{LABEL_HEALTH}")
    loaded_collector = command_fn("launchctl", "print", f"gui/{uid}/{LABEL_COLLECTOR}")
    require("run interval = 300 seconds" in loaded_health
            and "run interval = 60 seconds" in loaded_collector)
    step("CHECK_LOADED_COLLECTOR_COMMAND")
    # Reading an on-disk plist is NOT proof that launchd has reloaded it.
    loaded_program, loaded_arguments = loaded_collector_arguments(loaded_collector)
    require(loaded_program == collector_args[0]
            and loaded_arguments == collector_args)

    step("CHECK_EXISTING_RUNTIME_GIT")
    # Synthetic injected command functions in tests never invoke real Git.
    # Production CLI uses the guarded system command only.
    if command_fn is command:
        assert_trusted_git_checkout(active_root, uid)
    current = command_fn("git", "-C", active_root, "rev-parse", "--verify", "HEAD")
    require(SHA_RE.fullmatch(current) is not None)
    current_clean = (command_fn("git", "-C", active_root, "status",
                                "--porcelain", "--untracked-files=all",
                                "--ignore-submodules=all") == "")
    require(current_clean)

    # Check the collector's read-only scope before trusting its evidence.
    step("CHECK_COLLECTOR_EXPECTED_SHA")
    collector_state = option(collector_args, "--state-directory")
    collector_output = option(collector_args, "--output")
    collector_expected = option(collector_args, "--expected-commit")
    collector_runtime = option(collector_args, "--runtime")
    require(len(collector_args) == 11
            and Path(collector_state).is_absolute()
            and Path(collector_output).is_absolute()
            and Path(collector_runtime).is_absolute()
            and Path(collector_runtime) == Path(active_root)
            and SHA_RE.fullmatch(collector_expected) is not None)
    require(collector_expected == current)

    # The already-existing private configuration is consumed by the
    # existing canary, whose outputs contain no private fields.
    step("CHECK_CANDIDATE_RELEASE_CANARY")
    result = probe(config_file, expected, "before", now)
    require(result.get("result") == "READY_FOR_CONTROLLED_READ_ONLY_CANARY"
            and result.get("source_commit_matches_clean_checkout") is True
            and result.get("private_config_permissions_valid") is True
            and result.get("financial_operations") == 0
            and result.get("network_requests") == 0
            and result.get("credentials_opened") is False)
    # Matching private state path without emitting its value:
    # only canary's input inspection opens config; this separate script
    # does not open keys, wallets, local checkpoints or private reports.
    return {
        "mode": "M1_PREDEPLOY_READONLY_V1",
        "status": "READY_FOR_RELEASE_REVIEW_NOT_DEPLOYED",
        "candidate_sha": expected,
        "current_on_disk_runtime_sha": current,
        "active_daemon_pid_present": True,
        "loaded_supervisor_metadata_matches_plist": True,
        "active_process_command_matches_supervisor": True,
        "loaded_periodic_health_and_collector": True,
        "loaded_collector_executable_arguments_attested": True,
        "collector_expected_sha_matches_existing_runtime": True,
        "collector_runtime_path_matches_supervisor": True,
        "collector_entrypoint_verified": collector_mode,
        "collector_isolated_python_imports": True,
        "current_runtime_checkout_clean": True,
        "candidate_private_release_canary": "PASS",
        "candidate_is_active_on_disk_revision": current == expected,
        "active_process_code_in_memory_attested": False,
        "current_collector_state_directory_verified_against_config": False,
        "rollback_backup_created": False,
        "financial_operations": 0,
        "files_changed": 0,
        "services_restarted": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args(argv)
    failure_stage = ["VALIDATE_EXPECTED_SHA"]

    def note(code):
        # Codes come only from fixed source-code literals, never user data.
        failure_stage[0] = code

    try:
        output = check(args.expected_commit, stage=note)
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        # Never echo untrusted OS / provider exceptions or private paths.
        print("M1_PREDEPLOY_READONLY_REJECTED")
        print("M1_FAILURE_STAGE=" + failure_stage[0])
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
