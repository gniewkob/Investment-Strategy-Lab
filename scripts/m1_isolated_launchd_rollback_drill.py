"""Isolated launchd V2 -> V3 -> V2 rollback mechanism drill for macOS.

A SYNTHETIC '/bin/sleep' job uses a randomly generated label. This does NOT
test replacing the actual M1 collector, restoring its state, or the historical
evidence ledger. No production LaunchAgent, collector, supervisor, watchdog,
Python installation, credentials, wallets or finance operations are touched.

By default only prints the plan. Actual isolated test requires --run-isolated.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import secrets
import stat
import subprocess
import tempfile

LABEL_PREFIX = "pl.gniewkob.isl.m1-rollback-drill-"
LAUNCHCTL = "/bin/launchctl"
SLEEP = "/bin/sleep"
V2_SECONDS = "600"
V3_SECONDS = "601"


class DrillRejected(Exception):
    """Safe failure: report a fixed stage, never local command output."""


def command(argv):
    """Only fixed launchctl actions are passed here; no shell expansion."""
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, check=False, timeout=20,
            env={k: v for k, v in os.environ.items()
                 if not k.startswith(("DYLD_", "PYTHON"))},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DrillRejected("LAUNCHCTL_CALL_FAILED") from exc
    if result.returncode != 0 or len(result.stdout) > 128000:
        raise DrillRejected("LAUNCHCTL_CALL_FAILED")
    return result.stdout


def private_plist(folder, label, suffix, seconds):
    """Persist two different harmless job definitions; no external scripts."""
    if not (label.startswith(LABEL_PREFIX) and
            re.fullmatch(r"[0-9a-f]{16}", label[len(LABEL_PREFIX):])):
        raise DrillRejected("INVALID_SYNTHETIC_LABEL")
    if seconds not in (V2_SECONDS, V3_SECONDS):
        raise DrillRejected("INVALID_SYNTHETIC_PROGRAM")
    payload = {
        "Label": label, "Program": SLEEP,
        "ProgramArguments": [SLEEP, seconds],
        "RunAtLoad": True, "KeepAlive": False,
        "StandardOutPath": str(folder / "stdout.log"),
        "StandardErrorPath": str(folder / "stderr.log"),
    }
    target = folder / (suffix + ".plist")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(plistlib.dumps(payload, sort_keys=True))
        stream.flush()
        os.fsync(stream.fileno())
    if (stat.S_IMODE(target.stat().st_mode) != 0o600 or
            plistlib.loads(target.read_bytes()) != payload):
        raise DrillRejected("STAGED_PLIST_UNVERIFIED")
    return target


def verify_loaded(payload, label, seconds):
    """Require exact synthetic command and live PID in launchctl metadata."""
    if not isinstance(payload, str) or len(payload) > 128000:
        raise DrillRejected("UNKNOWN_LAUNCHCTL_FORMAT")
    lines = payload.splitlines()
    programs = [x.strip().partition(" = ")[2]
                for x in lines if x.strip().startswith("program = ")]
    starts = [i for i, x in enumerate(lines) if x.strip() == "arguments = {"]
    if programs != [SLEEP] or len(starts) != 1:
        raise DrillRejected("UNEXPECTED_LOADED_PROGRAM")
    start = starts[0]
    closing = next((i for i in range(start + 1, len(lines))
                    if lines[i].strip() == "}"), None)
    if closing is None:
        raise DrillRejected("UNKNOWN_LAUNCHCTL_FORMAT")
    args = [x.strip() for x in lines[start + 1:closing]]
    if args != [SLEEP, seconds]:
        raise DrillRejected("UNEXPECTED_LOADED_ARGUMENTS")
    match = re.search(r"^\s*pid = (\d+)\s*$", payload, re.MULTILINE)
    if match is None or int(match[1]) <= 1:
        raise DrillRejected("NO_SYNTHETIC_PROCESS")
    # The label is a fully random drill label; target is never read from plist.
    if not label.startswith(LABEL_PREFIX):
        raise DrillRejected("UNEXPECTED_DRILL_LABEL")


def rehearse(*, runner=command, uid=None, directory="/private/tmp"):
    """Only invoke launchctl for this new random label. Always attempt cleanup."""
    if uid is None:
        uid = os.getuid()
    if not isinstance(uid, int) or uid <= 0:
        raise DrillRejected("INVALID_GUI_UID")
    label = LABEL_PREFIX + secrets.token_hex(8)
    service = "gui/{}/{}".format(uid, label)
    domain = "gui/{}".format(uid)
    stage = "PRIVATE_STAGING"
    loaded = False
    cleaning_failed = False
    try:
        with tempfile.TemporaryDirectory(
            prefix="isl-m1-launchd-drill-", dir=directory
        ) as temp:
            folder = Path(temp)
            s = folder.lstat()
            if s.st_uid != uid or stat.S_IMODE(s.st_mode) != 0o700:
                raise DrillRejected("UNTRUSTED_PRIVATE_STAGING")
            v2 = private_plist(folder, label, "v2", V2_SECONDS)
            v3 = private_plist(folder, label, "v3", V3_SECONDS)

            stage = "BOOTSTRAP_V2"
            runner([LAUNCHCTL, "bootstrap", domain, str(v2)])
            loaded = True
            stage = "VERIFY_V2"
            verify_loaded(runner([LAUNCHCTL, "print", service]),
                          label, V2_SECONDS)

            stage = "BOOTOUT_V2"
            runner([LAUNCHCTL, "bootout", service])
            loaded = False
            stage = "BOOTSTRAP_V3"
            runner([LAUNCHCTL, "bootstrap", domain, str(v3)])
            loaded = True
            stage = "VERIFY_V3"
            verify_loaded(runner([LAUNCHCTL, "print", service]),
                          label, V3_SECONDS)

            # Deliberately simulate a failed V3 postflight (no actual crash).
            stage = "ROLLBACK_BOOTOUT_V3"
            runner([LAUNCHCTL, "bootout", service])
            loaded = False
            stage = "ROLLBACK_BOOTSTRAP_V2"
            runner([LAUNCHCTL, "bootstrap", domain, str(v2)])
            loaded = True
            stage = "VERIFY_ROLLBACK_V2"
            verify_loaded(runner([LAUNCHCTL, "print", service]),
                          label, V2_SECONDS)

            stage = "CLEANUP_V2"
            runner([LAUNCHCTL, "bootout", service])
            loaded = False
            stage = "DONE"
    except (DrillRejected, OSError, ValueError, subprocess.SubprocessError):
        raise DrillRejected(stage) from None
    finally:
        if loaded:
            try:
                runner([LAUNCHCTL, "bootout", service])
            except Exception:
                cleaning_failed = True
        if cleaning_failed:
            # Do not falsely claim that the synthetic job was unloaded.
            raise DrillRejected("SYNTHETIC_JOB_CLEANUP_UNVERIFIED")
    return {
        "mode": "M1_ISOLATED_LAUNCHD_MECHANISM_REHEARSAL_V1",
        "status": "SYNTHETIC_V2_RESTORED_AND_UNLOADED",
        "isolated_v2_v3_v2_cycle": True,
        "synthetic_postflight_failure_simulated": True,
        "active_collector_restore_tested": False,
        "production_launchagents_modified": False,
        "historical_evidence_modified": False,
        "financial_operations": 0,
        "g3_authorization": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-isolated", action="store_true")
    args = parser.parse_args(argv)
    if not args.run_isolated:
        print(json.dumps({
            "status": "PLAN_ONLY_NOT_EXECUTED",
            "synthetic_launchd_job_would_be_created": True,
            "production_launchagents_modified": False,
            "financial_operations": 0,
            "g3_authorization": False,
        }, sort_keys=True))
        return 0
    if platform.system() != "Darwin" or not Path(LAUNCHCTL).is_file():
        print("M1_ISOLATED_LAUNCHD_DRILL=REJECTED_WRONG_PLATFORM")
        print("M1_G3_AUTHORIZATION=NO")
        return 2
    try:
        result = rehearse()
        print(json.dumps(result, sort_keys=True))
        return 0
    except DrillRejected as exc:
        # Stage names are fixed within this source and contain no private data.
        print("M1_ISOLATED_LAUNCHD_DRILL=REJECTED")
        print("M1_FAILURE_STAGE=" + str(exc))
        print("M1_G3_AUTHORIZATION=NO")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
