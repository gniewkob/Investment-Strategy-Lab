"""Synthetic-only tests: M1 collector backup preparation never edits LaunchAgents."""
from contextlib import redirect_stdout
from io import StringIO
from hashlib import sha256
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
                  "tests" / "fixtures" / "collector_legacy_v2.txt")
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
                           check_syntax=lambda content: content.startswith(b"\"\"\""))
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
            for name in (*m.FILES_UPGRADE, "manifest.json"):
                self.assertEqual((folder/name).stat().st_mode & 0o777, 0o600)
            staged_code = (folder / m.NEW_FILE).read_bytes()
            self.assertEqual(m.source_blob(staged_code), m.NEW_GIT_BLOB)
            self.assertTrue(result["staged_isolated_collector_code_verified"])
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
                           check_syntax=lambda _argv: True)
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
                           check_syntax=lambda _argv: True)
                def stale(*args, **kwargs):
                    result = commands(*args, **kwargs)
                    if args[:2] == ("launchctl", "print"):
                        return result.replace("run interval = 60 seconds",
                                              "run interval = 15 seconds")
                    return result
                with self.assertRaises(ValueError):
                    m.plan(home, OLD_SHA, os.getuid(), commands=stale,
                           check_syntax=lambda _argv: True)
            self.assertFalse((Path(d) / "rollbacks").exists())

    def test_unapproved_collector_and_syntax_failure_are_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            home, plist, code, sup, commands = self.fixture(d)
            old = plist.read_bytes()
            with patch.object(m.preflight, "read_launchagent",
                              return_value=sup):
                with self.assertRaises(ValueError):
                    m.plan(home, OLD_SHA, os.getuid(), commands=commands,
                           check_syntax=lambda _argv: False)
                code.write_bytes(code.read_bytes() + b"\n# modified")
                with self.assertRaises(ValueError):
                    m.plan(home, OLD_SHA, os.getuid(), commands=commands,
                           check_syntax=lambda _argv: True)
            self.assertEqual(plist.read_bytes(), old)

    def test_bundle_reverification_and_reject_traversal_id(self):
        with tempfile.TemporaryDirectory() as d:
            home, plist, code, sup, commands = self.fixture(d)
            with patch.object(m.preflight, "read_launchagent",
                              return_value=sup):
                plan = m.plan(home, OLD_SHA, os.getuid(), commands=commands,
                              check_syntax=lambda args: True)
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

    def test_prepare_does_not_execute_an_untrusted_interpreter_or_script(self):
        with tempfile.TemporaryDirectory() as d:
            home, plist, script, supervisor, commands = self.fixture(d)
            original = plistlib.loads(plist.read_bytes())
            original["ProgramArguments"][0] = str(Path(d) / "python3")
            fake = Path(d) / "python3"
            fake.write_text("MALICIOUS_EXECUTABLE", encoding="utf-8")
            fake.chmod(0o700)
            plist.write_bytes(plistlib.dumps(original))
            def synced(*args, **kwargs):
                if args[:2] == ("launchctl", "print"):
                    argv = original["ProgramArguments"]
                    return ("run interval = 60 seconds\nprogram = " + argv[0]
                            + "\narguments = {\n" +
                            "\n".join("  " + x for x in argv) + "\n}")
                return commands(*args, **kwargs)
            with patch.object(m.preflight, "read_launchagent",
                              return_value=supervisor), \
                 patch("subprocess.run", side_effect=AssertionError(
                     "PROBE_MUST_NOT_EXECUTE")):
                data = m.plan(home, OLD_SHA, os.getuid(), commands=synced)
            result = m.store(home, os.getuid(), data,
                             backup_root=Path(d) / "safe-rollback")
            self.assertFalse(result["interpreter_binary_attested"])
            self.assertFalse(result["isolated_collector_executed"])
            self.assertEqual(fake.read_text(), "MALICIOUS_EXECUTABLE")

    def test_symlinked_backup_ancestor_cannot_redirect_writes(self):
        with tempfile.TemporaryDirectory() as d:
            home, plist, script, supervisor, commands = self.fixture(d)
            with patch.object(m.preflight, "read_launchagent",
                              return_value=supervisor):
                data = m.plan(home, OLD_SHA, os.getuid(), commands=commands)
            untrusted = Path(d) / "external"
            untrusted.mkdir()
            app_support = home / "Library" / "Application Support"
            app_support.symlink_to(untrusted, target_is_directory=True)
            with self.assertRaises(OSError):
                m.store(home, os.getuid(), data)
            self.assertEqual(list(untrusted.iterdir()), [])

    def test_other_writable_ancestor_rejected_before_backup_creation(self):
        with tempfile.TemporaryDirectory() as d:
            home, plist, script, supervisor, commands = self.fixture(d)
            with patch.object(m.preflight, "read_launchagent",
                              return_value=supervisor):
                data = m.plan(home, OLD_SHA, os.getuid(), commands=commands)
            bad = Path(d) / "bad-ancestor"
            bad.mkdir(mode=0o777)
            bad.chmod(0o777)
            with self.assertRaises(ValueError):
                m.store(home, os.getuid(), data, backup_root=bad / "rollback")
            self.assertFalse((bad / "rollback").exists())

    def test_preparer_rejects_untrusted_git_config_without_running_git(self):
        with tempfile.TemporaryDirectory() as d:
            home, _plist, _code, supervisor, _cmd = self.fixture(d)
            active = Path(supervisor["WorkingDirectory"])
            repo = active / ".git"
            repo.mkdir()
            config = repo / "config"
            for payload in (
                "[core]\nfsmonitor = /untrusted/command\n",
                "[filter \"malicious\"]\nprocess = /untrusted/program\n",
            ):
                config.write_text(payload)
                with patch.object(m.preflight, "read_launchagent",
                                  return_value=supervisor), \
                     patch.object(m.preflight, "command") as fake_git:
                    with self.assertRaises(m.preflight.PreflightRejected):
                        m.plan(home, OLD_SHA, os.getuid())
                    fake_git.assert_not_called()

    def test_legacy_v2_bundle_remains_verifiable_after_v3_source_pin(self):
        with tempfile.TemporaryDirectory() as d:
            home, plist, code, sup, commands = self.fixture(d)
            with patch.object(m.preflight, "read_launchagent", return_value=sup):
                plan = m.plan(home, OLD_SHA, os.getuid(), commands=commands)
                root = m.backup_base(home)
                new = m.store(home, os.getuid(), plan, backup_root=root)
            new_dir = root / new["rollback_bundle_id"]
            old_dir = root / "m1-legacycompatible"
            old_dir.mkdir(mode=0o700)
            files = {}
            for filename in m.FILES:
                payload = (new_dir / filename).read_bytes()
                output = old_dir / filename
                output.write_bytes(payload)
                output.chmod(0o600)
                files[filename] = sha256(payload).hexdigest()
            manifest = {
                "kind": "ISL_M1_COLLECTOR_BACKUP",
                "original_collector_git_blob": m.GIT_BLOB,
                "running_supervisor_sha": OLD_SHA,
                "file_hashes": files,
                "collector_launchagent_modified": False,
                "collector_reloaded": False,
                "financial_operations": 0,
            }
            name = old_dir / "manifest.json"
            name.write_text(json.dumps(manifest))
            name.chmod(0o600)
            check = m.verify(old_dir, os.getuid())
            self.assertEqual(check["status"], "ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY")
            self.assertEqual(check["mode"], "M1_COLLECTOR_RELEASE_PREPARE_V2")
            self.assertFalse(check["staged_isolated_collector_code_verified"])
            self.assertFalse(check["restore_rehearsal_completed"])

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
