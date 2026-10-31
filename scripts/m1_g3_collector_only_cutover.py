"""M1 G3 narrowly scoped macOS collector-only cutover with automatic rollback.

Default is non-mutating plan. Requires explicit --execute-collector-only.
Never touches supervisor/watchdog jobs, wallet, exchange, or old evidence.
Not a replacement for independent operator review and host-side validation.
"""
from __future__ import annotations

import argparse
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import stat
import subprocess
import tempfile

from scripts import m1_collector_release_prepare as backup
from scripts import m1_predeploy_readiness as preflight

CANDIDATE = "ded973833407532ca6095c50577fbdd046cd536c"
LEGACY_RUNTIME = "93038ca62edff39492f9b8ddb68d890e3e6e5c45"
V3_BUNDLE = "m1-2mLN75Z6aQ"
LABEL = preflight.LABEL_COLLECTOR
LAUNCHCTL = "/bin/launchctl"


class CutoverRejected(Exception):
    pass


def require(condition):
    if not condition:
        raise CutoverRejected("PRECONDITION_REJECTED")


def job(args):
    """Never accept a shell expression or a non-collector service target."""
    uid = os.getuid()
    domain = f"gui/{uid}"
    service = f"{domain}/{LABEL}"
    is_bootout = args == ["bootout", service]
    is_bootstrap = (len(args) == 3 and args[:2] == ["bootstrap", domain]
                    and args[2] == str(Path.home() / "Library"
                                       / "LaunchAgents" / (LABEL + ".plist")))
    require(is_bootout or is_bootstrap)
    try:
        proc = subprocess.run([LAUNCHCTL, *args], check=False,
                              capture_output=True, timeout=20)
        require(proc.returncode == 0)
    except (OSError, subprocess.SubprocessError):
        raise CutoverRejected("LAUNCHCTL_REJECTED") from None


def current_loaded():
    try:
        proc = subprocess.run(
            [LAUNCHCTL, "print", f"gui/{os.getuid()}/{LABEL}"],
            check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def safe_live_file(path, uid, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        s = os.fstat(stream.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid == uid
                and not s.st_mode & 0o022
                and 0 < s.st_size <= limit)
        payload = stream.read(limit + 1)
        require(len(payload) == s.st_size)
        return payload, stat.S_IMODE(s.st_mode)


def disk_stage(path, payload, mode):
    """Place new bytes beside their destination before any service change."""
    require(type(payload) is bytes and 0 < len(payload) <= 400_000)
    require(mode in (0o600, 0o644, 0o640))
    fd, name = tempfile.mkstemp(prefix=".isl-g3-pending-", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        fd = -1
        actual, actual_mode = safe_live_file(Path(name), os.getuid(), 400_000)
        require(actual == payload and actual_mode == mode)
        return Path(name)
    except Exception:
        if fd >= 0:
            os.close(fd)
        Path(name).unlink(missing_ok=True)
        raise


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def install(path, staged):
    os.replace(staged, path)
    sync_dir(path.parent)


def read_proven_bundle(home, uid):
    proof = backup.verify(backup.backup_base(home) / V3_BUNDLE, uid)
    require(proof["status"] == "ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY"
            and proof["staged_isolated_collector_code_verified"] is True
            and proof["old_supervisor_sha"] == LEGACY_RUNTIME)
    with backup.checked_directory(backup.backup_base(home), uid) as root:
        fd = os.open(V3_BUNDLE, backup.DIRECTORY_FLAGS, dir_fd=root)
        try:
            backup.checked_dir_metadata(os.fstat(fd), uid, leaf=True)
            return {name: backup.read_backup(fd, name, uid)
                    for name in backup.FILES_UPGRADE}
        finally:
            os.close(fd)


def before_cutover(home, uid):
    result = preflight.check(CANDIDATE, collector_phase="legacy-before",
                             home=home, uid=uid)
    require(result["status"] == "LEGACY_COLLECTOR_BASELINE_VERIFIED_NO_DEPLOY"
            and result["current_on_disk_runtime_sha"] == LEGACY_RUNTIME
            and result["loaded_collector_executable_arguments_attested"]
            and result["financial_operations"] == 0)
    originals = read_proven_bundle(home, uid)
    plist_path = home / "Library" / "LaunchAgents" / (LABEL + ".plist")
    old_plist = plistlib.loads(originals["collector-before.plist"])
    new_plist = plistlib.loads(originals["collector-isolated-staged.plist"])
    backup.assert_only_isolation_change(old_plist, new_plist)
    require(old_plist["Label"] == LABEL
            and new_plist["Label"] == LABEL
            and old_plist["StartInterval"] == new_plist["StartInterval"] == 60)
    oldargs = old_plist["ProgramArguments"]
    newargs = new_plist["ProgramArguments"]
    require(len(oldargs) >= 4 and newargs == [oldargs[0], "-I", *oldargs[1:]])
    script_path = Path(oldargs[1])
    require(script_path.is_absolute() and script_path.name.endswith(".py"))
    live_plist, plist_mode = safe_live_file(plist_path, uid, 64000)
    live_code, code_mode = safe_live_file(script_path, uid, 400000)
    require(live_plist == originals["collector-before.plist"]
            and live_code == originals["collector-before.py"]
            and backup.source_blob(live_code) == backup.GIT_BLOB
            and backup.source_blob(originals["collector-isolated-staged.py"])
                  == backup.NEW_GIT_BLOB)
    # No linked helper source or non-current collector path is ever targeted.
    require(script_path.parent.is_dir() and plist_path.parent.is_dir())
    require(plist_mode in (0o600, 0o644, 0o640)
            and code_mode in (0o600, 0o644, 0o640))
    return (script_path, plist_path, originals, code_mode, plist_mode)


def rollback(script, plist, originals, modes, *, service_loaded):
    """Attempt to return only the collector to its exact backed-up V2 bytes."""
    # A rejected bootstrap may leave no registered service. Only bootout
    # when the random-access launchd inventory confirms a loaded job.
    if current_loaded():
        job(["bootout", f"gui/{os.getuid()}/{LABEL}"])
    old_code = disk_stage(script, originals["collector-before.py"], modes[0])
    old_plist = disk_stage(plist, originals["collector-before.plist"], modes[1])
    try:
        install(script, old_code)
        install(plist, old_plist)
    finally:
        old_code.unlink(missing_ok=True)
        old_plist.unlink(missing_ok=True)
    job(["bootstrap", f"gui/{os.getuid()}", str(plist)])
    verified = preflight.check(CANDIDATE, collector_phase="legacy-before")
    require(verified["status"] == "LEGACY_COLLECTOR_BASELINE_VERIFIED_NO_DEPLOY")
    return True


def execute():
    uid = os.getuid()
    require(platform.system() == "Darwin" and uid > 0
            and os.geteuid() == uid and Path(LAUNCHCTL).is_file())
    home = Path.home()
    # Owner-private file lock, separate from the historical ledger.
    root = backup.backup_base(home)
    with backup.checked_directory(root, uid) as rootfd:
        fd = os.open("g3-collector-only.lock",
                     os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600,
                     dir_fd=rootfd)
        try:
            st = os.fstat(fd)
            require(st.st_uid == uid and stat.S_ISREG(st.st_mode)
                    and not st.st_mode & 0o077)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            script, plist, b, script_mode, plist_mode = before_cutover(home, uid)
            staged_script = disk_stage(script, b["collector-isolated-staged.py"],
                                       script_mode)
            try:
                staged_plist = disk_stage(plist,
                                          b["collector-isolated-staged.plist"],
                                          plist_mode)
            except Exception:
                staged_script.unlink(missing_ok=True)
                raise
            stopped = False
            attempted_bootstrap = False
            try:
                # Repeat source/file baseline before job is stopped.
                before_cutover(home, uid)
                job(["bootout", f"gui/{uid}/{LABEL}"])
                stopped = True
                install(script, staged_script)
                install(plist, staged_plist)
                require(backup.source_blob(safe_live_file(script, uid, 400000)[0])
                        == backup.NEW_GIT_BLOB)
                attempted_bootstrap = True
                job(["bootstrap", f"gui/{uid}", str(plist)])
                result = preflight.check(
                    CANDIDATE, collector_phase="isolated-after",
                    home=home, uid=uid)
                require(result["status"] ==
                        "ISOLATED_COLLECTOR_METADATA_VERIFIED_NOT_RUNTIME_ATTESTED"
                        and result["loaded_collector_executable_arguments_attested"]
                        and result["financial_operations"] == 0)
                return {
                    "status": "G3_COLLECTOR_ONLY_CUTOVER_AND_G4_METADATA_PASS",
                    "candidate_sha": CANDIDATE,
                    "rollback_bundle_id": V3_BUNDLE,
                    "g4_natural_cycles_confirmed": False,
                    "g5_24h_completed": False,
                    "production_supervisor_or_watchdog_modified": False,
                    "financial_operations": 0,
                }
            except Exception:
                if stopped:
                    try:
                        rollback(script, plist, b,
                                 (script_mode, plist_mode),
                                 service_loaded=attempted_bootstrap)
                    except Exception:
                        raise CutoverRejected("ROLLBACK_UNVERIFIED_MANUAL_RECOVERY") from None
                    raise CutoverRejected("G3_FAILED_V2_ROLLBACK_VERIFIED") from None
                raise CutoverRejected("G3_STOP_REJECTED_NO_FILE_CHANGE") from None
            finally:
                staged_script.unlink(missing_ok=True)
                staged_plist.unlink(missing_ok=True)
        finally:
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-collector-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_collector_only:
        print(json.dumps({
            "status": "G3_PLAN_ONLY_NO_HOST_CHANGE",
            "candidate_sha": CANDIDATE,
            "bundle_id": V3_BUNDLE,
            "collector_label": LABEL,
            "g3_executed": False,
            "financial_operations": 0,
        }, sort_keys=True))
        return 0
    try:
        print(json.dumps(execute(), sort_keys=True))
        return 0
    except Exception as exc:
        # Do not leak private absolute paths, launchctl stdout or credentials.
        msg = str(exc) if isinstance(exc, CutoverRejected) else "G3_REJECTED"
        print("M1_G3_RESULT=" + msg)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
