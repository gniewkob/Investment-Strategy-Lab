"""Read-only capability probe for a private EIA source archive filesystem.

Use it on MyDevil or a trusted private workstation BEFORE ANY raw EIA
capture. It does not create files, mutate permissions, contact EIA/Neon, or
claim WORM/backup durability. The target root must already exist 0700.
No hostnames, filesystem paths, original quotes, credentials or secrets are
emitted in the report.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys

from src.isl_v2.eia_raw_archive import (
    DIR_FLAGS, _root_fd, _subdir,
)
from src.isl_v2.eia_sources import SourceFormatError

SCHEMA = "EIA_PRIVATE_ARCHIVE_READONLY_PREFLIGHT_V1"
MIN_FREE_MIB_DEFAULT = 64


def _optional_subdir_status(root_fd: int, name: str) -> str:
    """Inspect a directory with O_NOFOLLOW, without creating it."""
    try:
        fd = _subdir(root_fd, name, create=False)
    except FileNotFoundError:
        return "NOT_CREATED"
    try:
        st = os.fstat(fd)
        if (not stat.S_ISDIR(st.st_mode)
                or st.st_uid != os.getuid()
                or stat.S_IMODE(st.st_mode) & 0o077):
            raise SourceFormatError("Private archive subfolder is not secure")
        return "PRIVATE_EXISTS"
    finally:
        os.close(fd)


def inspect_private_archive_root(path: str | Path, *,
                                 minimum_free_mib: int = MIN_FREE_MIB_DEFAULT) -> dict:
    """Pure read-only metadata probe: no chmod, mkdir, file writes or network.

    Filesystem free blocks and writability are NOT an account quota, proof of
    ZFS snapshot policy, persistence, WORM/Object Lock or backup recoverability.
    """
    if (type(minimum_free_mib) is not int or
            not 1 <= minimum_free_mib <= 1024 * 1024):
        raise SourceFormatError("Unreasonable private-archive free-space threshold")
    fd = _root_fd(path)
    try:
        st = os.fstat(fd)
        space = os.fstatvfs(fd)
        free_mib = space.f_bavail * space.f_frsize // (1024 * 1024)
        # _root_fd's security checks cover owner, non-symlink, mode and Git.
        # Check that a persistent writable object does not already occupy a
        # reserved directory name. _subdir rejects symlinks via O_NOFOLLOW.
        objects = _optional_subdir_status(fd, "objects")
        receipts = _optional_subdir_status(fd, "receipts")
    finally:
        os.close(fd)

    return {
        "status": ("PRIVATE_LOCAL_METADATA_PREFLIGHT_PASS"
                   if free_mib >= minimum_free_mib
                   else "PRIVATE_LOCAL_METADATA_PREFLIGHT_NO_GO_LOW_FREE_SPACE"),
        "schema": SCHEMA,
        "archive_backend": "PRIVATE_LOCAL_POSIX_STAGING_NOT_WORM",
        "root_owner_matches_current_process": st.st_uid == os.getuid(),
        "root_private_permissions": stat.S_IMODE(st.st_mode) & 0o077 == 0,
        "objects_directory": objects,
        "receipts_directory": receipts,
        "free_space_mib_reported_by_filesystem": free_mib,
        "minimum_free_space_mib": minimum_free_mib,
        "quota_and_inode_headroom_independently_verified": False,
        "private_volume_mount_persistence_verified": False,
        "zfs_snapshot_and_restore_verified": False,
        "independent_backup_verified": False,
        "worm_object_lock_verified": False,
        "first_real_eia_source_archive_captured": False,
        "archival_retention_compliance_verified": False,
        "approved_for_neon_versioned_writes": False,
        "database_connections": 0,
        "database_writes": 0,
        "hosting_configuration_changes": 0,
        "file_creations": 0,
        "external_http_requests": 0,
        "real_orders": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only EIA archive filesystem probe: NO DB/NO WRITES")
    parser.add_argument("--archive-root", required=True)
    parser.add_argument("--minimum-free-mib", type=int,
                        default=MIN_FREE_MIB_DEFAULT)
    options = parser.parse_args(argv)
    try:
        result = inspect_private_archive_root(
            options.archive_root, minimum_free_mib=options.minimum_free_mib)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0 if result["status"] == "PRIVATE_LOCAL_METADATA_PREFLIGHT_PASS" else 3
    except Exception as error:
        # Don't reveal root path, host, credentials or raw original HTML.
        print("EIA_ARCHIVE_READONLY_PREFLIGHT_FAILED: " + type(error).__name__,
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
