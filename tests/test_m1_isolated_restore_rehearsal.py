"""Synthetic isolated restore rehearsal: never touches real LaunchAgents or keys."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import m1_collector_release_prepare as backup
from scripts import m1_isolated_restore_rehearsal as rehearsal
from test_m1_collector_release_prepare import PrepareTests, OLD_SHA


class RestoreRehearsalTests(unittest.TestCase):
    def test_reconstructs_original_files_in_new_private_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, live_plist, live_code, supervisor, commands = (
                PrepareTests().fixture(tmp))
            original_plist, original_code = live_plist.read_bytes(), live_code.read_bytes()
            with patch.object(backup.preflight, "read_launchagent",
                              return_value=supervisor):
                planned = backup.plan(
                    home, OLD_SHA, os.getuid(), commands=commands)
                result = backup.store(home, os.getuid(), planned)
            proof = rehearsal.rehearse(home, result["rollback_bundle_id"],
                                       os.getuid())
            self.assertEqual(
                proof["status"], "RESTORE_FILES_RECONSTRUCTED_ISOLATED_NO_DEPLOY")
            self.assertTrue(proof["isolated_file_copy_rehearsal_completed"])
            self.assertFalse(proof["actual_launchagent_restore_tested"])
            self.assertFalse(proof["active_plist_modified"])
            self.assertFalse(proof["launchagents_reloaded"])
            self.assertFalse(proof["interpreter_binary_attested"])
            self.assertEqual(proof["financial_operations"], 0)
            drill = backup.backup_base(home) / proof["isolated_drill_id"]
            self.assertEqual(drill.stat().st_mode & 0o777, 0o700)
            self.assertEqual((drill / rehearsal.SOURCE_FILES[0]).read_bytes(),
                             original_plist)
            self.assertEqual((drill / rehearsal.SOURCE_FILES[1]).read_bytes(),
                             original_code)
            for name in rehearsal.SOURCE_FILES:
                self.assertEqual((drill / name).stat().st_mode & 0o777, 0o600)
            self.assertEqual(live_plist.read_bytes(), original_plist)
            self.assertEqual(live_code.read_bytes(), original_code)
            self.assertNotIn(str(home), json.dumps(proof))

    def test_tampered_bundle_fails_before_any_restore_file_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, _, _, supervisor, commands = PrepareTests().fixture(tmp)
            with patch.object(backup.preflight, "read_launchagent",
                              return_value=supervisor):
                stored = backup.store(home, os.getuid(),
                    backup.plan(home, OLD_SHA, os.getuid(), commands=commands))
            root = backup.backup_base(home)
            source = root / stored["rollback_bundle_id"] / "collector-before.py"
            source.write_bytes(source.read_bytes() + b"\n# tampered")
            with self.assertRaises(ValueError):
                rehearsal.rehearse(home, stored["rollback_bundle_id"], os.getuid())
            self.assertFalse(any(p.name.startswith("m1-drill-")
                                 for p in root.iterdir()))

    def test_bad_bundle_id_is_never_interpreted_as_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            for bad in ("../other", "../../etc/passwd", "/tmp/other",
                        "m1-evil/other", "not-a-bundle", ""):
                with self.subTest(bad=bad):
                    with self.assertRaises(ValueError):
                        rehearsal.rehearse(home, bad, os.getuid())
            self.assertFalse((home / "Library").exists())


if __name__ == "__main__":
    unittest.main()
