"""Isolated restore FILE rehearsal of a previously verified M1 rollback bundle.

Never edits the active LaunchAgent, launches a process, replaces the running
collector or touches any financial account, evidence ledger or state dir.
This only reconstructs the backed-up plist/script in a NEW private folder.
It cannot certify restoring the real launchd job; that is a separate gate.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import plistlib
import re
import secrets
import stat

from scripts import m1_collector_release_prepare as backup

BUNDLE = re.compile(r"m1-[A-Za-z0-9_-]{4,64}\Z")
SOURCE_FILES = ("collector-before.plist", "collector-before.py")


def require(condition):
    backup.require(condition)


def rehearse(home, bundle_id, uid):
    require(type(bundle_id) is str and BUNDLE.fullmatch(bundle_id) is not None)
    base = backup.backup_base(home)
    # Bind source and destination to the same owner-only backup root.
    with backup.checked_directory(base, uid) as root_fd:
        source_fd = os.open(bundle_id, backup.DIRECTORY_FLAGS, dir_fd=root_fd)
        try:
            backup.checked_dir_metadata(os.fstat(source_fd), uid, leaf=True)
            proof = backup.verify_contents(source_fd, uid, bundle_id=bundle_id)
            require(proof["status"] == "ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY")
            originals = {
                name: backup.read_backup(source_fd, name, uid)
                for name in SOURCE_FILES
            }
            require(backup.source_blob(originals[SOURCE_FILES[1]])
                    == backup.GIT_BLOB)
            old = plistlib.loads(originals[SOURCE_FILES[0]])
            require(type(old) is dict and old.get("Label") == backup.LABEL)
        finally:
            os.close(source_fd)

        for _ in range(8):
            trial_id = "m1-drill-" + secrets.token_urlsafe(7)
            try:
                os.mkdir(trial_id, 0o700, dir_fd=root_fd)
                break
            except FileExistsError:
                continue
        else:
            require(False)

        drill_fd = os.open(trial_id, backup.DIRECTORY_FLAGS, dir_fd=root_fd)
        try:
            backup.checked_dir_metadata(os.fstat(drill_fd), uid, leaf=True)
            for name, data in originals.items():
                backup.write_backup(drill_fd, name, data, uid)
                require(sha256(backup.read_backup(drill_fd, name, uid)).digest()
                        == sha256(data).digest())
            restored = plistlib.loads(
                backup.read_backup(drill_fd, SOURCE_FILES[0], uid))
            require(restored == old)
            os.fsync(drill_fd)
        finally:
            os.close(drill_fd)
    return {
        "mode": "M1_ISOLATED_RESTORE_FILES_REHEARSAL_V1",
        "status": "RESTORE_FILES_RECONSTRUCTED_ISOLATED_NO_DEPLOY",
        "source_bundle_id": bundle_id,
        "isolated_drill_id": trial_id,
        "legacy_collector_git_blob_verified": True,
        "isolated_file_copy_rehearsal_completed": True,
        "actual_launchagent_restore_tested": False,
        "interpreter_binary_attested": False,
        "isolated_collector_executed": False,
        "launchagents_reloaded": False,
        "active_plist_modified": False,
        "financial_operations": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-bundle-id", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = rehearse(Path.home(), args.verify_bundle_id, os.getuid())
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        print("M1_ISOLATED_RESTORE_REHEARSAL_REJECTED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
