"""ISL v0.13: non-overwriting portable export and read-back of a v0.11 snapshot.

Export is NOT proof of a separate failure domain, immutability, offsite
retention or trusted time. It never opens a brokerage connection or scheduler.
The destination is operator-provided and must be a private directory.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat

from scripts.shadow_backup_restore_v11 import FILES, verify_snapshot
from scripts.shadow_decision_engine_v05 import ShadowInputError

SCHEMA = "ISL_SHADOW_COPY_V13_001"
MAX_FILE_BYTES = 64 * 1024 * 1024
NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,75}$")
HASH = re.compile(r"^[a-f0-9]{64}$")
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | NOFOLLOW


def _private_root(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ShadowInputError("destination must be an existing absolute non-symlink directory")
    descriptor = os.open(path, DIR_FLAGS)
    st = os.fstat(descriptor)
    if not stat.S_ISDIR(st.st_mode) or (st.st_mode & 0o077) or st.st_uid != os.getuid():
        os.close(descriptor)
        raise ShadowInputError("destination must be owner-controlled mode 0700")
    if (path.stat(follow_symlinks=False).st_ino,
            path.stat(follow_symlinks=False).st_dev) != (st.st_ino, st.st_dev):
        os.close(descriptor)
        raise ShadowInputError("destination path changed during opening")
    return descriptor


def _same_directory(fd, path):
    try:
        st = os.stat(path, follow_symlinks=False)
        opened = os.fstat(fd)
    except OSError as exc:
        raise ShadowInputError("destination disappeared") from exc
    if (st.st_dev, st.st_ino) != (opened.st_dev, opened.st_ino):
        raise ShadowInputError("destination path was swapped")


def _read_source(path, expected_hash):
    if not HASH.fullmatch(expected_hash):
        raise ShadowInputError("missing expected source digest")
    fd = os.open(path, os.O_RDONLY | NOFOLLOW)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE_BYTES:
            raise ShadowInputError("source is not a bounded regular file")
        with os.fdopen(os.dup(fd), "rb") as inp:
            data = inp.read(MAX_FILE_BYTES + 1)
        if (len(data) > MAX_FILE_BYTES
                or sha256(data).hexdigest() != expected_hash
                or (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != (st.st_dev, st.st_ino)):
            raise ShadowInputError("source changed or content hash mismatch")
        return data
    finally:
        os.close(fd)


def _read_at(dirfd, name, expected):
    fd = os.open(name, os.O_RDONLY | NOFOLLOW, dir_fd=dirfd)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE_BYTES:
            raise ShadowInputError("stored file is not bounded and regular")
        with os.fdopen(os.dup(fd), "rb") as f:
            data = f.read(MAX_FILE_BYTES + 1)
        if sha256(data).hexdigest() != expected:
            raise ShadowInputError("stored content sha256 mismatch")
        if (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != (st.st_dev, st.st_ino):
            raise ShadowInputError("stored file replaced during readback")
        return data
    finally:
        os.close(fd)


def _file_digests(snapshot, pinned_manifest):
    verified = verify_snapshot(snapshot, pinned_manifest)
    manifest = json.loads((Path(snapshot) / "manifest.json").read_bytes())
    return verified, {
        "manifest.json": pinned_manifest,
        "ledger.sqlite3": manifest["ledger_sha256"],
        "anchor.json": manifest["anchor_sha256"],
    }


def _check_name(name):
    if not NAME.fullmatch(name) or name in (".", ".."):
        raise ShadowInputError("invalid export name")


def export_copy(snapshot, pinned_manifest, destination_root, *, name):
    """Copy into a new private folder using openat-style exclusive creation.

    Destination verification is intentionally not conflated with DR readiness.
    No automatic retry, overwrite, deletion or rollback of partial exports.
    """
    _check_name(name)
    evidence, expected = _file_digests(snapshot, pinned_manifest)
    rootfd = _private_root(destination_root)
    try:
        _same_directory(rootfd, destination_root)
        # Explicitly disallow exporting inside the source snapshot tree.
        if Path(destination_root).resolve().is_relative_to(Path(snapshot).resolve()):
            raise ShadowInputError("destination inside snapshot is prohibited")
        try:
            os.mkdir(name, mode=0o700, dir_fd=rootfd)
        except FileExistsError as exc:
            raise ShadowInputError("destination already exists; never overwrite") from exc
        folderfd = os.open(name, DIR_FLAGS, dir_fd=rootfd)
        try:
            for filename in sorted(FILES):
                _same_directory(rootfd, destination_root)
                data = _read_source(Path(snapshot) / filename, expected[filename])
                dstfd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW,
                                0o600, dir_fd=folderfd)
                try:
                    with os.fdopen(dstfd, "wb", closefd=False) as out:
                        out.write(data)
                        out.flush()
                        os.fsync(out.fileno())
                finally:
                    os.close(dstfd)
                if _read_at(folderfd, filename, expected[filename]) != data:
                    raise ShadowInputError("destination readback differs from source")
            os.fsync(folderfd)
            _same_directory(rootfd, destination_root)
            stored = os.stat(name, dir_fd=rootfd, follow_symlinks=False)
            if (stored.st_dev, stored.st_ino) != (
                    os.fstat(folderfd).st_dev, os.fstat(folderfd).st_ino):
                raise ShadowInputError("export folder path swapped")
        finally:
            os.close(folderfd)
        os.fsync(rootfd)
        result = verify_export(destination_root, name, pinned_manifest)
        return {**result, "source_entries": evidence["current_entries"],
                "export_path": str(Path(destination_root) / name)}
    finally:
        os.close(rootfd)


def verify_export(destination_root, name, pinned_manifest):
    """Read files by directory descriptors and validate the full copied snapshot."""
    _check_name(name)
    rootfd = _private_root(destination_root)
    try:
        _same_directory(rootfd, destination_root)
        folderfd = os.open(name, DIR_FLAGS, dir_fd=rootfd)
        try:
            st = os.fstat(folderfd)
            if (not stat.S_ISDIR(st.st_mode) or (st.st_mode & 0o077)
                    or st.st_uid != os.getuid()):
                raise ShadowInputError("export folder permissions invalid")
            folder = Path(destination_root) / name
            if {x.name for x in folder.iterdir()} != FILES:
                raise ShadowInputError("unexpected copied file names")
            _read_at(folderfd, "manifest.json", pinned_manifest)
            manifest = json.loads(_read_at(folderfd, "manifest.json", pinned_manifest))
            for file, digest in (("ledger.sqlite3", manifest["ledger_sha256"]),
                                 ("anchor.json", manifest["anchor_sha256"])):
                _read_at(folderfd, file, digest)
            # Full SQLite and anchor cross-check; desc-bound byte checks above
            # catch symlink replacement and stale files. Recheck root and inode
            # after v0.11 path-based validator, closing normal path swaps.
            checked = verify_snapshot(folder, pinned_manifest)
            _same_directory(rootfd, destination_root)
            same = os.stat(name, dir_fd=rootfd, follow_symlinks=False)
            if (same.st_dev, same.st_ino) != (st.st_dev, st.st_ino):
                raise ShadowInputError("export directory replaced during verification")
            for filename, digest in (("ledger.sqlite3", manifest["ledger_sha256"]),
                                     ("anchor.json", manifest["anchor_sha256"]),
                                     ("manifest.json", pinned_manifest)):
                _read_at(folderfd, filename, digest)
            return {
                "schema": SCHEMA,
                "status": "COPY_READBACK_VERIFIED_FAILURE_DOMAIN_UNVERIFIED",
                "entries": checked["current_entries"],
                "manifest_sha256": pinned_manifest,
                "head_sha256": checked["anchored_head_sha256"],
                "independent_failure_domain_verified": False,
                "offsite_verified": False,
                "external_worm_verified": False,
                "trusted_timestamp_verified": False,
                "financial_operations": 0,
            }
        finally:
            os.close(folderfd)
    finally:
        os.close(rootfd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmds = parser.add_subparsers(dest="operation", required=True)
    for op in ("export", "verify"):
        cmd = cmds.add_parser(op)
        cmd.add_argument("--destination-root", type=Path, required=True)
        cmd.add_argument("--name", required=True)
        cmd.add_argument("--manifest-sha256", required=True)
        if op == "export":
            cmd.add_argument("--snapshot", type=Path, required=True)
    a = parser.parse_args()
    if a.operation == "export":
        result = export_copy(a.snapshot, a.manifest_sha256,
                             a.destination_root, name=a.name)
    else:
        result = verify_export(a.destination_root, a.name, a.manifest_sha256)
    print("ISL_SHADOW_COPY_V13=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
