"""Create and verify an owner-only rollback bundle for the existing M1 collector.

This is the PREPARE gate. It does not edit launchd, the collector plist,
the private evidence journal, the supervisor, watchdog, wallets or databases.
Only creates a new private, uniquely named backup directory.

The isolated (-I) definition is staged in the backup folder, NOT installed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import tempfile

from scripts import m1_predeploy_readiness as preflight

GIT_BLOB = preflight.APPROVED_COLLECTOR_GIT_BLOB
SHA = re.compile(r"[0-9a-f]{40}\Z")
LABEL = preflight.LABEL_COLLECTOR
FILES = ("collector-before.plist", "collector-before.py",
         "collector-isolated-staged.plist")


def require(condition):
    if not condition:
        raise ValueError("M1_COLLECTOR_ROLLBACK_PREPARE_REJECTED")


def private_read(path, uid, *, limit=200_000):
    """Read a bounded, owned non-symlink file with no group/world access."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        s = os.fstat(stream.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid == uid
                and not (s.st_mode & 0o077) and 0 < s.st_size <= limit)
        data = stream.read(limit + 1)
    require(len(data) == s.st_size)
    return data


def secure_folder(folder, uid):
    s = Path(folder).lstat()
    require(stat.S_ISDIR(s.st_mode) and s.st_uid == uid
            and not (s.st_mode & 0o077))


def write_new(path, payload, uid):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    require(private_read(path, uid, limit=400_000) == payload)


def source_blob(content):
    return sha1(b"blob " + str(len(content)).encode("ascii")
                + b"\x00" + content).hexdigest()


def plan(home, expected_runtime_sha, uid, *, commands=None, check_help=None):
    require(type(expected_runtime_sha) is str
            and SHA.fullmatch(expected_runtime_sha) is not None)
    if commands is None:
        commands = preflight.command
    if check_help is None:
        check_help = run_isolated_help

    home = Path(home)
    plist_path = home / "Library" / "LaunchAgents" / (LABEL + ".plist")
    s = plist_path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_uid == uid
            and not s.st_mode & 0o077 and 0 < s.st_size <= 64_000)
    old_bytes = private_read(plist_path, uid, limit=64_000)
    definition = plistlib.loads(old_bytes)
    require(type(definition) is dict and definition.get("StartInterval") == 60)
    argv = definition.get("ProgramArguments")
    require(type(argv) is list and len(argv) == 10
            and all(type(a) is str for a in argv))
    require(Path(argv[0]).is_absolute()
            and re.fullmatch(r"python(?:3(?:\.\d+)?)?", Path(argv[0]).name))
    require(Path(argv[1]).is_absolute() and argv[1].endswith(".py"))
    require("-I" not in argv and "-m" not in argv and "-c" not in argv)
    require(definition.get("Program", argv[0]) == argv[0])

    parent_dir = Path(__file__).resolve().parent
    reference = private_read(parent_dir / "unattended_acceptance.py", uid)
    require(source_blob(reference) == GIT_BLOB)
    approved = private_read(argv[1], uid)
    require(sha256(reference).digest() == sha256(approved).digest())

    supervisor = preflight.read_launchagent(home, preflight.LABEL_PORTFOLIO, uid)
    active_root = supervisor.get("WorkingDirectory")
    require(type(active_root) is str and Path(active_root).is_absolute())
    require(preflight.option(argv, "--runtime") == active_root)
    require(Path(preflight.option(argv, "--state-directory")).is_absolute())
    require(Path(preflight.option(argv, "--output")).is_absolute())
    require(preflight.option(argv, "--expected-commit") == expected_runtime_sha)
    require(commands("git", "-C", active_root, "rev-parse", "HEAD") ==
            expected_runtime_sha)
    require(commands("git", "-C", active_root, "status",
                     "--porcelain", "--untracked-files=all") == "")

    # Existing launchd must still be the OLD (non-isolated) definition.
    loaded = commands("launchctl", "print", f"gui/{uid}/{LABEL}")
    require("run interval = 60 seconds" in loaded)
    loaded_program, loaded_argv = preflight.loaded_collector_arguments(loaded)
    require(loaded_program == argv[0] and loaded_argv == argv)

    staged = dict(definition)
    staged["ProgramArguments"] = [argv[0], "-I"] + argv[1:]
    require(len(staged["ProgramArguments"]) == 11)
    # Test only --help, which is handled by argparse before record().
    require(check_help([argv[0], "-I", argv[1], "--help"]))

    staged_bytes = plistlib.dumps(staged, sort_keys=True)
    assert_only_isolation_change(definition, plistlib.loads(staged_bytes))
    return (old_bytes, approved, staged_bytes, expected_runtime_sha)


def run_isolated_help(argv):
    try:
        result = subprocess.run(argv, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                check=False, timeout=10)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def assert_only_isolation_change(old, staged):
    require(type(old) is dict and type(staged) is dict)
    copied = dict(staged)
    candidate = copied.pop("ProgramArguments", None)
    require(candidate == old["ProgramArguments"][:1] + ["-I"]
            + old["ProgramArguments"][1:])
    reference = dict(old)
    reference.pop("ProgramArguments", None)
    require(copied == reference)


def store(home, uid, plan_tuple, *, backup_root=None):
    old, source, staged, oldsha = plan_tuple
    root = Path(backup_root or (Path(home) / "Library" / "Application Support"
                                 / "InvestmentStrategyLab" / "M1Rollback"))
    # Parents are under the user's HOME; no system-wide modifications.
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    secure_folder(root, uid)
    bundle = Path(tempfile.mkdtemp(prefix="m1-", dir=root))
    bundle.chmod(0o700)
    secure_folder(bundle, uid)
    try:
        for name, data in zip(FILES, (old, source, staged)):
            write_new(bundle / name, data, uid)
        manifest = {
            "kind": "ISL_M1_COLLECTOR_BACKUP",
            "running_supervisor_sha": oldsha,
            "original_collector_git_blob": GIT_BLOB,
            "file_hashes": {
                name: sha256(data).hexdigest()
                for name, data in zip(FILES, (old, source, staged))
            },
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "collector_launchagent_modified": False,
            "collector_reloaded": False,
            "financial_operations": 0
        }
        write_new(bundle / "manifest.json",
                  json.dumps(manifest, sort_keys=True).encode("utf-8"), uid)
        check = verify(bundle, uid)
        require(check["status"] == "ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY")
        return check
    except Exception:
        # Never delete a partial backup: preserve for forensic inspection.
        raise


def verify(bundle, uid):
    bundle = Path(bundle)
    secure_folder(bundle, uid)
    manifest = json.loads(private_read(bundle / "manifest.json", uid))
    require(manifest.get("kind") == "ISL_M1_COLLECTOR_BACKUP")
    require(manifest.get("collector_launchagent_modified") is False
            and manifest.get("collector_reloaded") is False
            and manifest.get("financial_operations") == 0)
    data = {name: private_read(bundle / name, uid, limit=400_000)
            for name in FILES}
    require(manifest.get("file_hashes") == {
        name: sha256(payload).hexdigest()
        for name, payload in data.items()
    })
    old = plistlib.loads(data["collector-before.plist"])
    new = plistlib.loads(data["collector-isolated-staged.plist"])
    assert_only_isolation_change(old, new)
    require(source_blob(data["collector-before.py"]) == GIT_BLOB)
    return {
        "mode": "M1_COLLECTOR_RELEASE_PREPARE_V1",
        "status": "ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY",
        "rollback_bundle_id": bundle.name,
        "old_supervisor_sha": manifest["running_supervisor_sha"],
        "old_collector_git_blob_verified": True,
        "original_plist_backup_verified": True,
        "original_collector_code_backup_verified": True,
        "staged_isolated_collector_plist_verified": True,
        "live_plist_modified": False,
        "launchagents_reloaded": False,
        "financial_operations": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-runtime-sha", required=True)
    args = parser.parse_args(argv)
    try:
        uid = os.getuid()
        home = Path.home()
        result = store(home, uid, plan(home, args.expected_runtime_sha, uid))
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        # No private file paths, command output or exception text.
        print("M1_COLLECTOR_ROLLBACK_PREPARE_REJECTED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
