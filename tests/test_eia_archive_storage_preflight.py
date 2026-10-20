"""Synthetic no-network/no-write tests of MyDevil/private POSIX storage probe."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import os

from scripts import eia_archive_storage_preflight as subject


class PrivateArchiveReadOnlyProbeTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="isl-archive-readonly-probe-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)

    def test_existing_empty_private_dir_passes_without_creating_files(self):
        before = set(self.root.iterdir())
        result = subject.inspect_private_archive_root(self.root)
        self.assertEqual(result["status"], "PRIVATE_LOCAL_METADATA_PREFLIGHT_PASS")
        self.assertEqual(result["objects_directory"], "NOT_CREATED")
        self.assertEqual(result["receipts_directory"], "NOT_CREATED")
        self.assertTrue(result["root_owner_matches_current_process"])
        self.assertTrue(result["root_private_permissions"])
        self.assertEqual(set(self.root.iterdir()), before)
        for key in ("worm_object_lock_verified", "zfs_snapshot_and_restore_verified",
                    "approved_for_neon_versioned_writes",
                    "private_volume_mount_persistence_verified",
                    "first_real_eia_source_archive_captured"):
            self.assertFalse(result[key])
        for key in ("file_creations", "external_http_requests", "database_writes",
                    "hosting_configuration_changes"):
            self.assertEqual(result[key], 0)
        payload = json.dumps(result)
        for secret in (str(self.root), "postgresql://", "101.10"):
            self.assertNotIn(secret, payload)

    def test_private_empty_subfolders_are_read_only_inspected(self):
        (self.root / "objects").mkdir(mode=0o700)
        (self.root / "receipts").mkdir(mode=0o700)
        before = sorted(self.root.iterdir())
        result = subject.inspect_private_archive_root(self.root)
        self.assertEqual(result["objects_directory"], "PRIVATE_EXISTS")
        self.assertEqual(result["receipts_directory"], "PRIVATE_EXISTS")
        self.assertEqual(sorted(self.root.iterdir()), before)

    def test_free_space_threshold_fails_without_sneaky_capture(self):
        stat = os.statvfs(self.root)
        from types import SimpleNamespace
        simulated = SimpleNamespace(f_bavail=0, f_frsize=stat.f_frsize)
        with patch.object(subject.os, "fstatvfs", return_value=simulated):
            result = subject.inspect_private_archive_root(self.root)
        self.assertEqual(result["status"],
                         "PRIVATE_LOCAL_METADATA_PREFLIGHT_NO_GO_LOW_FREE_SPACE")
        self.assertFalse(list(self.root.iterdir()))

    def test_bad_private_mode_relative_path_and_git_checkout_fail_closed(self):
        self.root.chmod(0o755)
        with self.assertRaisesRegex(Exception, "private"):
            subject.inspect_private_archive_root(self.root)
        self.root.chmod(0o700)
        with self.assertRaisesRegex(Exception, "absolute"):
            subject.inspect_private_archive_root("relative-folder")
        (self.root / ".git").mkdir(mode=0o700)
        with self.assertRaisesRegex(Exception, "Git checkout"):
            subject.inspect_private_archive_root(self.root)

    def test_symlinked_reserved_directory_fails_and_does_not_follow(self):
        (self.root / "objects").symlink_to("/tmp", target_is_directory=True)
        with self.assertRaises(OSError):
            subject.inspect_private_archive_root(self.root)
        self.assertEqual(len(list(self.root.iterdir())),1)

    def test_cli_aggregates_only_and_no_implicit_directory_creation(self):
        output=StringIO()
        with redirect_stdout(output):
            exit_code=subject.main(["--archive-root",str(self.root)])
        self.assertEqual(exit_code, 0)
        report=json.loads(output.getvalue())
        self.assertEqual(report["schema"],subject.SCHEMA)
        self.assertNotIn(str(self.root),output.getvalue())
        self.assertEqual(list(self.root.iterdir()),[])

    def test_cli_fail_closed_without_leaking_private_paths(self):
        self.root.chmod(0o777)
        errors=StringIO()
        with redirect_stderr(errors):
            rc=subject.main(["--archive-root",str(self.root)])
        self.assertEqual(rc,2)
        self.assertEqual(
            errors.getvalue(),
            "EIA_ARCHIVE_READONLY_PREFLIGHT_FAILED: SourceFormatError\n")
        self.assertNotIn(str(self.root), errors.getvalue())
        self.root.chmod(0o700)
        with redirect_stderr(StringIO()):
            self.assertEqual(subject.main([
                "--archive-root",str(self.root), "--minimum-free-mib","0"]),2)
