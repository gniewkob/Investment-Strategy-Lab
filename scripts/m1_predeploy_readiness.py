"""M1 predeployment audit for existing macOS LaunchAgents.

Read-only; never restarts services, writes files, contacts providers, or
exports private paths, credentials, identifiers, holdings or addresses.

This check is a predeployment METADATA gate. It cannot prove that the
already-running Python process has reloaded the on-disk Git checkout.
"""
from __future__ import annotations

import argparse
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


def command(*args, cwd=None):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                                timeout=8, check=False)
    except (OSError, subprocess.SubprocessError):
        raise PreflightRejected("M1_PREDEPLOY_READONLY_REJECTED") from None
    require(result.returncode == 0 and len(result.stdout) < 128_000)
    return result.stdout.strip()


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
    step("CHECK_WATCHDOG_COLLECTOR_DEFINITIONS")
    watchdog_args = watchdog.get("ProgramArguments")
    collector_args = collector.get("ProgramArguments")
    require(type(watchdog_args) is list and "--check-health" in watchdog_args
            and watchdog.get("StartInterval") == 300
            and type(collector_args) is list
            and "scripts.unattended_acceptance" in collector_args
            and collector.get("StartInterval") == 60)

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

    step("CHECK_EXISTING_RUNTIME_GIT")
    current = command_fn("git", "-C", active_root, "rev-parse", "--verify", "HEAD")
    require(SHA_RE.fullmatch(current) is not None)
    current_clean = (command_fn("git", "-C", active_root, "status",
                                "--porcelain", "--untracked-files=all") == "")
    require(current_clean)

    # Check the collector's read-only scope before trusting its evidence.
    step("CHECK_COLLECTOR_EXPECTED_SHA")
    collector_state = option(collector_args, "--state-directory")
    collector_output = option(collector_args, "--output")
    collector_expected = option(collector_args, "--expected-commit")
    require(Path(collector_state).is_absolute()
            and Path(collector_output).is_absolute()
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
        "collector_expected_sha_matches_existing_runtime": True,
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
