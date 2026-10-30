"""Prepare and verify the collector's private rollback snapshot; never deploy.

The planner performs read-only metadata checks and static Python compilation.
It NEVER runs code from the live collector plist (even for --help).
Only writes new 0600 backup files through securely opened directory fds.
No launchctl bootstrap/bootout, real trading, network calls or evidence edits.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import plistlib
import re
import secrets
import stat

from scripts import m1_predeploy_readiness as preflight

GIT_BLOB = preflight.APPROVED_COLLECTOR_GIT_BLOB
SHA = re.compile(r"[0-9a-f]{40}\Z")
LABEL = preflight.LABEL_COLLECTOR
FILES = ("collector-before.plist", "collector-before.py",
         "collector-isolated-staged.plist")
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def require(condition):
    if not condition:
        raise ValueError("M1_COLLECTOR_ROLLBACK_PREPARE_REJECTED")


def private_read(path, uid, *, limit=200_000, backup=False):
    """Read bounded regular bytes; no symlink at final component."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        s = os.fstat(stream.fileno())
        forbidden = 0o077 if backup else 0o022
        require(stat.S_ISREG(s.st_mode) and s.st_uid == uid
                and not (s.st_mode & forbidden) and 0 < s.st_size <= limit)
        data = stream.read(limit + 1)
    require(len(data) == s.st_size)
    return data


def source_blob(content):
    return sha1(b"blob " + str(len(content)).encode("ascii")
                + b"\x00" + content).hexdigest()


def source_syntax_valid(content):
    """Compile in memory without executing the Python script or its imports."""
    try:
        compile(content, "<approved-collector>", "exec", dont_inherit=True)
        return True
    except (SyntaxError, ValueError, TypeError):
        return False


def plan(home, expected_runtime_sha, uid, *, commands=None, check_syntax=None):
    require(type(expected_runtime_sha) is str
            and SHA.fullmatch(expected_runtime_sha) is not None)
    if commands is None:
        commands = preflight.command
    if check_syntax is None:
        check_syntax = source_syntax_valid

    home = Path(home)
    plist_path = home / "Library" / "LaunchAgents" / (LABEL + ".plist")
    s = plist_path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_uid == uid
            and not s.st_mode & 0o022 and 0 < s.st_size <= 64_000)
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
    # No subprocess using argv[0] or argv[1]: prevents untrusted-executable
    # invocation and time-of-check/time-of-use source replacement attacks.
    require(check_syntax(approved) is True)

    supervisor = preflight.read_launchagent(home, preflight.LABEL_PORTFOLIO, uid)
    active_root = supervisor.get("WorkingDirectory")
    require(type(active_root) is str and Path(active_root).is_absolute())
    require(preflight.option(argv, "--runtime") == active_root)
    require(Path(preflight.option(argv, "--state-directory")).is_absolute())
    require(Path(preflight.option(argv, "--output")).is_absolute())
    require(preflight.option(argv, "--expected-commit") == expected_runtime_sha)
    if commands is preflight.command:
        preflight.assert_trusted_git_checkout(active_root, uid)
    require(commands("git", "-C", active_root, "rev-parse", "HEAD") ==
            expected_runtime_sha)
    require(commands("git", "-C", active_root, "status",
                     "--porcelain", "--untracked-files=all",
                     "--ignore-submodules=all") == "")
    # Existing launchd must still be the OLD (non-isolated) definition.
    loaded = commands("launchctl", "print", f"gui/{uid}/{LABEL}")
    require("run interval = 60 seconds" in loaded)
    loaded_program, loaded_argv = preflight.loaded_collector_arguments(loaded)
    require(loaded_program == argv[0] and loaded_argv == argv)

    staged = dict(definition)
    staged["ProgramArguments"] = [argv[0], "-I"] + argv[1:]
    require(len(staged["ProgramArguments"]) == 11)
    staged_bytes = plistlib.dumps(staged, sort_keys=True)
    assert_only_isolation_change(definition, plistlib.loads(staged_bytes))
    return (old_bytes, approved, staged_bytes, expected_runtime_sha)


def assert_only_isolation_change(old, staged):
    require(type(old) is dict and type(staged) is dict)
    copied = dict(staged)
    candidate = copied.pop("ProgramArguments", None)
    require(candidate == old["ProgramArguments"][:1] + ["-I"]
            + old["ProgramArguments"][1:])
    reference = dict(old)
    reference.pop("ProgramArguments", None)
    require(copied == reference)


def backup_base(home):
    return (Path(home) / "Library" / "Application Support"
            / "InvestmentStrategyLab" / "M1Rollback")


def checked_dir_metadata(st, uid, *, leaf=False):
    require(stat.S_ISDIR(st.st_mode))
    if leaf:
        require(st.st_uid == uid and not (st.st_mode & 0o077))
    else:
        # /tmp is typically root-owned, sticky and world-writable. No other
        # writable ancestor is accepted (including symlinks).
        sticky_root = (st.st_uid == 0 and (st.st_mode & 0o1000)
                       and (st.st_mode & 0o002))
        require(st.st_uid in (uid, 0)
                and (not (st.st_mode & 0o022) or sticky_root))


@contextmanager
def checked_directory(path, uid, *, create=False, leaf=True):
    """Open each component O_NOFOLLOW and perform mkdir/open via dir_fd.

    The returned fd binds operations to this directory regardless of later
    path renames. Never chmod or follow any existing directory redirect.
    """
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts)
    fd = os.open("/", DIRECTORY_FLAGS)
    try:
        for i, token in enumerate(path.parts[1:]):
            last = i == len(path.parts) - 2
            checked_dir_metadata(os.fstat(fd), uid, leaf=False)
            try:
                child = os.open(token, DIRECTORY_FLAGS, dir_fd=fd)
            except FileNotFoundError:
                require(create)
                os.mkdir(token, 0o700, dir_fd=fd)
                child = os.open(token, DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
            checked_dir_metadata(os.fstat(fd), uid, leaf=leaf and last)
        yield fd
    finally:
        os.close(fd)


def read_backup(fd, name, uid):
    require(name in (*FILES, "manifest.json"))
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
    with os.fdopen(child, "rb") as stream:
        s = os.fstat(stream.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid == uid
                and not (s.st_mode & 0o077) and 0 < s.st_size <= 400_000)
        data = stream.read(400_001)
    require(len(data) == s.st_size)
    return data


def write_backup(fd, name, payload, uid):
    require(name in (*FILES, "manifest.json"))
    child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600, dir_fd=fd)
    with os.fdopen(child, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    require(read_backup(fd, name, uid) == payload)


def verify_contents(fd, uid, *, bundle_id):
    manifest = json.loads(read_backup(fd, "manifest.json", uid))
    require(manifest.get("kind") == "ISL_M1_COLLECTOR_BACKUP")
    require(manifest.get("collector_launchagent_modified") is False
            and manifest.get("collector_reloaded") is False
            and manifest.get("financial_operations") == 0)
    data = {name: read_backup(fd, name, uid) for name in FILES}
    require(manifest.get("file_hashes") == {
        name: sha256(payload).hexdigest()
        for name, payload in data.items()
    })
    old = plistlib.loads(data["collector-before.plist"])
    new = plistlib.loads(data["collector-isolated-staged.plist"])
    assert_only_isolation_change(old, new)
    require(source_blob(data["collector-before.py"]) == GIT_BLOB)
    require(type(manifest.get("running_supervisor_sha")) is str
            and SHA.fullmatch(manifest["running_supervisor_sha"]) is not None)
    return {
        "mode": "M1_COLLECTOR_RELEASE_PREPARE_V2",
        "status": "ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY",
        "rollback_bundle_id": bundle_id,
        "old_supervisor_sha": manifest["running_supervisor_sha"],
        "old_collector_git_blob_verified": True,
        "original_plist_backup_verified": True,
        "original_collector_code_backup_verified": True,
        "staged_isolated_collector_plist_verified": True,
        "isolated_collector_executed": False,
        "interpreter_binary_attested": False,
        "restore_rehearsal_completed": False,
        "live_plist_modified": False,
        "launchagents_reloaded": False,
        "financial_operations": 0,
    }


def store(home, uid, plan_tuple, *, backup_root=None):
    old, source, staged, oldsha = plan_tuple
    root = Path(backup_root or backup_base(home))
    with checked_directory(root, uid, create=True) as rootfd:
        for _ in range(8):
            name = "m1-" + secrets.token_urlsafe(7)
            try:
                os.mkdir(name, 0o700, dir_fd=rootfd)
                break
            except FileExistsError:
                continue
        else:
            require(False)
        bundle_fd = os.open(name, DIRECTORY_FLAGS, dir_fd=rootfd)
        try:
            checked_dir_metadata(os.fstat(bundle_fd), uid, leaf=True)
            for filename, data in zip(FILES, (old, source, staged)):
                write_backup(bundle_fd, filename, data, uid)
            manifest = {
                "kind": "ISL_M1_COLLECTOR_BACKUP",
                "running_supervisor_sha": oldsha,
                "original_collector_git_blob": GIT_BLOB,
                "file_hashes": {
                    filename: sha256(data).hexdigest()
                    for filename, data in zip(FILES, (old, source, staged))
                },
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "collector_launchagent_modified": False,
                "collector_reloaded": False,
                "financial_operations": 0,
            }
            write_backup(bundle_fd, "manifest.json",
                         json.dumps(manifest, sort_keys=True).encode(), uid)
            return verify_contents(bundle_fd, uid, bundle_id=name)
        finally:
            os.close(bundle_fd)


def verify(bundle, uid):
    path = Path(bundle)
    require(re.fullmatch(r"m1-[A-Za-z0-9_-]{4,64}", path.name) is not None)
    with checked_directory(path.parent, uid) as rootfd:
        fd = os.open(path.name, DIRECTORY_FLAGS, dir_fd=rootfd)
        try:
            checked_dir_metadata(os.fstat(fd), uid, leaf=True)
            return verify_contents(fd, uid, bundle_id=path.name)
        finally:
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    flags = parser.add_mutually_exclusive_group(required=True)
    flags.add_argument("--expected-runtime-sha")
    flags.add_argument("--verify-bundle-id")
    args = parser.parse_args(argv)
    try:
        uid = os.getuid()
        home = Path.home()
        if args.verify_bundle_id is not None:
            require(re.fullmatch(r"m1-[A-Za-z0-9_-]{4,64}",
                                 args.verify_bundle_id) is not None)
            result = verify(backup_base(home) / args.verify_bundle_id, uid)
        else:
            result = store(home, uid, plan(home, args.expected_runtime_sha, uid))
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        # Do not leak OS errors, filesystem locations, runtime args or keys.
        print("M1_COLLECTOR_ROLLBACK_PREPARE_REJECTED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
