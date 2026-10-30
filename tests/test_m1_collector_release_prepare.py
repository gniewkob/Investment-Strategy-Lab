"""Synthetic-only tests: M1 collector backup preparation never edits LaunchAgents."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

from scripts import m1_collector_release_prepare as m

OLD_SHA = "9" * 40


class PrepareTests(unittest.TestCase):
    def fixture(self, root):
        root = Path(root)
        home = root / "home"
        agents = home / "Library" / "LaunchAgents"
        agents.mkdir(parents=True)
        runtime = root / "active-supervisor"
        runtime.mkdir()
        source = (Path(__file__).resolve().parents[1] /
                  "scripts" / "unattended_acceptance.py")
        copied = root / "private-collector.py"
        copied.write_bytes(source.read_bytes())
        copied.chmod(0o600)
        old = {
            "Label": m.LABEL, "StartInterval": 60,
            "ProgramArguments": [
                "/usr/bin/python3", str(copied),
                "--state-directory", str(root / "state"),
                "--output", str(root / "evidence"),
                "--expected-commit", OLD_SHA,
                "--runtime", str(runtime),
            ],
        }
        old_path = agents / (m.LABEL + ".plist")
        old_path.write_bytes(plistlib.dumps(old))
        old_path.chmod(0o644)
        supervisor = {"WorkingDirectory": str(runtime)}
        def commands(*args, **kwargs):
            if args[:2] == ("git", "-C"):
                return OLD_SHA if "rev-parse" in args else ""
            if args[:2] == ("launchctl", "print"):
                argv = old["ProgramArguments"]
                return ("run interval = 60 seconds\n"
                        + "program = " + argv[0] + "\n"
                        + "arguments = {\n"
                        + "\n".join("  " + a for a in argv) + "\n}")
            raise AssertionError("UNEXPECTED_COMMAND")
        return home, old_path, copied, supervisor, commands

    def test_private_rollback_staged_without_mutating_collector(self):
        with tempfile.TemporaryDirectory() as d:
            home, plist, code, sup, commands = self.fixture(d)
            old_plist = plist.read_bytes()
            old_source = code.read_bytes()
            with patch.object(m.preflight, "read_launchagent",
                              return_value=sup):
                p = m.plan(home, OLD_SHA, os.getuid(), commands=commands,
                           check_help=lambda args: args[1] == "-I")
                bundle_root = Path(d) / "private-backups"
                result = m.store(home, os.getuid(), p, backup_root=bundle_root)
            self.assertEqual(result["status"], "ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY")
            self.assertTrue(result["original_plist_backup_verified"])
            self.assertTrue(result["original_collector_code_backup_verified"])
            self.assertTrue(result["staged_isolated_collector_plist_verified"])
            self.assertFalse(result["live_plist_modified"])
            self.assertFalse(result["launchagents_reloaded"])
            self.assertEqual(plist.read_bytes(), old_plist)
            self.assertEqual(code.read_bytes(), old_source)
            folder = bundle_root / result["rollback_bundle_id"]
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
            for name in (*m.FILES, "manifest.json"):
                self.assertEqual((folder/name).stat().st_mode & 0o777, 0o600)
            staged = plistlib.loads((folder / m.FILES[2]).read_bytes())
            source = plistlib.loads(old_plist)
            self.assertEqual(staged["ProgramArguments"],
                             [source["ProgramArguments"][0], "-I"]
                             + source["ProgramArguments"][1:])
            self.assertNotIn(str(home), json.dumps(result))

    def test_change_or_remove_backup_fails_verification(self):
        with tempfile.TemporaryDirectory() as d:
            home, plist, code, sup, commands = self.fixture(d)
            with patch.object(m.preflight, "read_launchagent",
                              return_value=sup):
                p = m.plan(home, OLD_SHA, os.getuid(), commands=commands,
                           check_help=lambda _argv: True)
                root = Path(d) / "rollbacks"
                result = m.store(home, os.getuid(), p, backup_root=root)
            folder = root/result["rollback_bundle_id"]
            source = folder / m.FILES[1]
            source.write_bytes(source.read_bytes() + b"\n# altered")
            with self.assertRaises(ValueError):
                m.verify(folder, os.getuid())

    def test_stale_launchctl_or_wrong_sha_does_not_create_backup(self):
        with tempfile.TemporaryDirectory() as d:
            home, _, _, sup, commands = self.fixture(d)
            with patch.object(m.preflight, "read_launchagent",
                              return_value=sup):
                with self.assertRaises(ValueError):
                    m.plan(home, "a" * 40, os.getuid(), commands=commands,
                           check_help=lambda _argv: True)
                def stale(*args, **kwargs):
                    result = commands(*args, **kwargs)
                    if args[:2] == ("launchctl", "print"):
                        return result.replace("run interval = 60 seconds",
                                              "run interval = 15 seconds")
                    return result
                with self.assertRaises(ValueError):
                    m.plan(home, OLD_SHA, os.getuid(), commands=stale,
                           check_help=lambda _argv: True)
            self.assertFalse((Path(d) / "rollbacks").exists())

    def test_unapproved_collector_and_help_failure_are_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            home, plist, code, sup, commands = self.fixture(d)
            old = plist.read_bytes()
            with patch.object(m.preflight, "read_launchagent",
                              return_value=sup):
                with self.assertRaises(ValueError):
                    m.plan(home, OLD_SHA, os.getuid(), commands=commands,
                           check_help=lambda _argv: False)
                code.write_bytes(code.read_bytes() + b"\n# modified")
                with self.assertRaises(ValueError):
                    m.plan(home, OLD_SHA, os.getuid(), commands=commands,
                           check_help=lambda _argv: True)
            self.assertEqual(plist.read_bytes(), old)

    def test_bundle_reverification_and_reject_traversal_id(self):
        with tempfile.TemporaryDirectory() as d:
            home, plist, code, sup, commands = self.fixture(d)
            with patch.object(m.preflight, "read_launchagent",
                              return_value=sup):
                plan = m.plan(home, OLD_SHA, os.getuid(), commands=commands,
                              check_help=lambda args: True)
                bundle_root = m.backup_base(home)
                result = m.store(home, os.getuid(), plan,
                                 backup_root=bundle_root)
            new_check = m.verify(bundle_root/result["rollback_bundle_id"],
                                 os.getuid())
            self.assertEqual(new_check["status"],
                             "ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY")
            with patch.object(m.Path, "home", return_value=home):
                with redirect_stdout(StringIO()) as output:
                    self.assertEqual(m.main(["--verify-bundle-id",
                                              result["rollback_bundle_id"]]), 0)
                self.assertEqual(json.loads(output.getvalue())["status"],
                                 "ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY")
                with redirect_stdout(StringIO()) as rejected:
                    self.assertEqual(m.main(["--verify-bundle-id",
                                              "../../other"]), 2)
                self.assertEqual(rejected.getvalue().strip(),
                                 "M1_COLLECTOR_ROLLBACK_PREPARE_REJECTED")

    def test_output_redaction_on_failure(self):
        buffer = StringIO()
        with patch.object(m, "plan", side_effect=OSError(
                "secret /private/path/to-wallet")):
            with redirect_stdout(buffer):
                status = m.main(["--expected-runtime-sha", OLD_SHA])
        self.assertEqual(status, 2)
        self.assertEqual(buffer.getvalue().strip(),
                         "M1_COLLECTOR_ROLLBACK_PREPARE_REJECTED")
        self.assertNotIn("wallet", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
