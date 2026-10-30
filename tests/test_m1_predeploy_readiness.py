"""No Mac/LaunchAgent access: fake commands and preflight metadata only."""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
import json
import os
import subprocess
from types import SimpleNamespace
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import m1_predeploy_readiness as m

OLD = "9"*40
NEW = "a"*40
ROOT = "/private/only-running-service"
CONFIG = "/private/only-config"
STATE = "/private/only-state"
OUT = "/private/only-evidence"
COLLECTOR_FILE = str(Path(__file__).resolve().parents[1] /
                     "scripts" / "unattended_acceptance.py")


def fixtures():
    return {
        m.LABEL_PORTFOLIO: {
            "ProgramArguments": [
                "/usr/bin/python3", "-m", "scripts.autonomous_portfolio",
                "--enable-live-read", "--config", CONFIG,
            ],
            "WorkingDirectory": ROOT, "KeepAlive": True, "RunAtLoad": True,
        },
        m.LABEL_HEALTH: {
            "ProgramArguments": ["/usr/bin/python3", "-m",
                                 "scripts.autonomous_portfolio", "--check-health"],
            "StartInterval": 300,
        },
        m.LABEL_COLLECTOR: {
            "ProgramArguments": ["/usr/bin/python3", "-I", COLLECTOR_FILE,
                "--state-directory", STATE, "--output", OUT,
                "--expected-commit", OLD, "--runtime", ROOT],
            "StartInterval": 60,
        },
    }


def commands(*args, cwd=None, definitions=None):
    if args[:2] == ("launchctl", "print"):
        if args[-1].endswith(m.LABEL_PORTFOLIO):
            return "pid = 123\nworking directory = " + ROOT
        if args[-1].endswith(m.LABEL_HEALTH):
            return "run interval = 300 seconds"
        if args[-1].endswith(m.LABEL_COLLECTOR):
            argv = (definitions or fixtures())[m.LABEL_COLLECTOR]["ProgramArguments"]
            return ("run interval = 60 seconds\n"
                    + "program = " + argv[0] + "\n"
                    + "arguments = {\n"
                    + "\n".join("    " + arg for arg in argv)
                    + "\n}")
    if args[:3] == ("ps", "-p", "123"):
        return "/usr/bin/python3 -m scripts.autonomous_portfolio --enable-live-read"
    if args[:2] == ("git", "-C") and "rev-parse" in args:
        return OLD
    if args[:2] == ("git", "-C") and "status" in args:
        return ""
    raise AssertionError("UNEXPECTED_SYNTETHIC_CALL")


def probe(config_path, expected, phase, now):
    if config_path != CONFIG or expected != NEW or phase != "before":
        raise AssertionError("BAD_PREFLIGHT_CONTRACT")
    return {
        "result": "READY_FOR_CONTROLLED_READ_ONLY_CANARY",
        "source_commit_matches_clean_checkout": True,
        "private_config_permissions_valid": True,
        "financial_operations": 0,
        "network_requests": 0,
        "credentials_opened": False,
    }


class PreflightTests(unittest.TestCase):
    def verify(self, definitions=None, command_fn=commands, canary=probe):
        definitions = definitions or fixtures()
        def read(_home, label, _uid):
            return deepcopy(definitions[label])
        if command_fn is commands:
            command_fn = lambda *args, **kwargs: commands(
                *args, definitions=definitions, **kwargs)
        return m.check(NEW, reader=read, command_fn=command_fn,
                       probe=canary,
                       now=datetime(2026, 10, 29, tzinfo=timezone.utc))

    def test_valid_readonly_preflight_only_confirms_metadata(self):
        report = self.verify()
        self.assertEqual(report["status"], "READY_FOR_RELEASE_REVIEW_NOT_DEPLOYED")
        self.assertEqual(report["candidate_sha"], NEW)
        self.assertEqual(report["current_on_disk_runtime_sha"], OLD)
        self.assertFalse(report["candidate_is_active_on_disk_revision"])
        self.assertFalse(report["active_process_code_in_memory_attested"])
        self.assertFalse(report["rollback_backup_created"])
        self.assertEqual(report["financial_operations"], 0)
        self.assertEqual(report["files_changed"], 0)
        self.assertEqual(report["services_restarted"], 0)
        dumped = json.dumps(report)
        for private in (ROOT, CONFIG, STATE, OUT):
            self.assertNotIn(private, dumped)

    def test_unsafe_or_mismatched_collector_and_watchdog_are_blocked(self):
        for change in (
            lambda d: d[m.LABEL_COLLECTOR].update(StartInterval=15),
            lambda d: d[m.LABEL_HEALTH].update(StartInterval=60),
            lambda d: d[m.LABEL_PORTFOLIO].update(KeepAlive=False),
            lambda d: d[m.LABEL_COLLECTOR]["ProgramArguments"].extend(
                ["--expected-commit", NEW]),
            lambda d: d[m.LABEL_PORTFOLIO]["ProgramArguments"].append("--once"),
            lambda d: d[m.LABEL_PORTFOLIO].update(WorkingDirectory="relative"),
        ):
            with self.subTest(change=str(change)):
                d = fixtures()
                change(d)
                with self.assertRaises(m.PreflightRejected):
                    self.verify(definitions=d)

    def test_each_schedule_definition_has_distinct_safe_failure_stage(self):
        cases = (
            ("CHECK_WATCHDOG_COMMAND",
             lambda d: d[m.LABEL_HEALTH]["ProgramArguments"].remove("--check-health")),
            ("CHECK_WATCHDOG_INTERVAL",
             lambda d: d[m.LABEL_HEALTH].update(StartInterval=60)),
            ("CHECK_COLLECTOR_CODE_IDENTITY",
             lambda d: d[m.LABEL_COLLECTOR]["ProgramArguments"].__setitem__(
                 2, "/private/unapproved_entrypoint.py")),
            ("CHECK_COLLECTOR_INTERVAL",
             lambda d: d[m.LABEL_COLLECTOR].update(StartInterval=300)),
        )
        for expected_stage, mutate in cases:
            with self.subTest(expected_stage=expected_stage):
                definitions = fixtures()
                mutate(definitions)
                stages = []
                with self.assertRaises(m.PreflightRejected):
                    m.check(NEW,
                            reader=lambda _home, label, _uid: deepcopy(
                                definitions[label]),
                            command_fn=commands, probe=probe,
                            now=datetime(2026, 10, 29, tzinfo=timezone.utc),
                            stage=stages.append)
                self.assertEqual(stages[-1], expected_stage)
                self.assertNotIn(ROOT, stages[-1])
                self.assertNotIn(CONFIG, stages[-1])

    def test_reviewed_copied_script_attested_by_content_not_filename(self):
        with tempfile.TemporaryDirectory() as folder:
            approved = (Path(__file__).resolve().parents[1] /
                        "scripts" / "unattended_acceptance.py")
            script = Path(folder) / "collector-deployed-private.py"
            script.write_bytes(approved.read_bytes())
            script.chmod(0o600)

            args = ["/usr/bin/python3", "-I", str(script)]
            self.assertEqual(m.verified_collector_entrypoint(args),
                             "REVIEWED_ISOLATED_COPIED_PYTHON_SCRIPT")
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint([
                    "/usr/bin/python3", "-m", "scripts.unattended_acceptance"])

            defs = fixtures()
            defs[m.LABEL_COLLECTOR]["ProgramArguments"][:3] = args
            result = self.verify(definitions=defs)
            self.assertEqual(result["collector_entrypoint_verified"],
                             "REVIEWED_ISOLATED_COPIED_PYTHON_SCRIPT")
            self.assertTrue(result["collector_isolated_python_imports"])
            self.assertNotIn(str(script), json.dumps(result))

    def test_copied_script_rejects_content_drift_or_untrusted_path(self):
        with tempfile.TemporaryDirectory() as folder:
            approved = Path(__file__).resolve().parents[1] / "scripts" / "unattended_acceptance.py"
            script = Path(folder) / "collector.py"
            pristine = approved.read_bytes()
            script.write_bytes(pristine + b"# extra line\n")
            script.chmod(0o600)
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(["/usr/bin/python3", "-I", str(script)])
            script.write_bytes(pristine)
            script.chmod(0o666)
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(["/usr/bin/python3", "-I", str(script)])
            script.chmod(0o600)
            link = Path(folder) / "alias.py"
            link.symlink_to(script)
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(["/usr/bin/python3", "-I", str(link)])
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(["/usr/bin/python3", "-I", "relative.py"])
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(["/bin/bash", "-I", str(script)])
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(["/usr/bin/python3", "-c",
                                                   "import os"])

    def test_reviewed_source_mutation_cannot_be_approved(self):
        with tempfile.TemporaryDirectory() as folder:
            altered_source = Path(folder) / "unattended_acceptance.py"
            altered_script = Path(folder) / "deployed.py"
            content = (Path(__file__).resolve().parents[1] /
                       "scripts" / "unattended_acceptance.py").read_bytes()
            altered_source.write_bytes(content + b"# injected change\n")
            altered_script.write_bytes(content + b"# injected change\n")
            altered_source.chmod(0o600)
            altered_script.chmod(0o600)
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(
                    ["/usr/bin/python3", "-I", str(altered_script)],
                    approved_source=altered_source)

    def test_required_runtime_arg_must_be_single_and_match_supervisor(self):
        cases = (
            lambda d: d[m.LABEL_COLLECTOR]["ProgramArguments"].pop(),
            lambda d: d[m.LABEL_COLLECTOR]["ProgramArguments"].pop(-2),
            lambda d: d[m.LABEL_COLLECTOR]["ProgramArguments"].__setitem__(-1, "/wrong/runtime"),
            lambda d: d[m.LABEL_COLLECTOR]["ProgramArguments"].extend(
                ["--runtime", ROOT]),
        )
        for change in cases:
            with self.subTest(change=str(change)):
                d = fixtures()
                change(d)
                stages = []
                with self.assertRaises(m.PreflightRejected):
                    m.check(NEW, reader=lambda _home, label, _uid: d[label],
                            command_fn=lambda *args, **kw: commands(
                                *args, definitions=d, **kw),
                            probe=probe, stage=stages.append)
                self.assertEqual(stages[-1], "CHECK_COLLECTOR_EXPECTED_SHA")

    def test_module_name_cannot_trick_code_attestation(self):
        d = fixtures()
        d[m.LABEL_COLLECTOR]["ProgramArguments"][:3] = [
            "/usr/bin/python3", "-m", "scripts.unattended_acceptance"]
        stages = []
        with self.assertRaises(m.PreflightRejected):
            m.check(NEW, reader=lambda _home, label, _uid: d[label],
                    command_fn=commands, probe=probe, stage=stages.append)
        self.assertEqual(stages[-1], "CHECK_COLLECTOR_CODE_IDENTITY")

    def test_python_isolation_required_even_for_approved_script(self):
        for replacement in (
            ["/usr/bin/python3", COLLECTOR_FILE],
            ["/usr/bin/python3", "-E", COLLECTOR_FILE],
            ["/usr/bin/python3", "-s", COLLECTOR_FILE],
            ["/usr/bin/python3", "-m", "scripts.unattended_acceptance"],
            ["/usr/bin/python3", "-c", "import argparse"],
        ):
            with self.subTest(replacement=replacement[1]):
                d = fixtures()
                d[m.LABEL_COLLECTOR]["ProgramArguments"][:3] = replacement
                stages = []
                with self.assertRaises(m.PreflightRejected):
                    m.check(NEW, reader=lambda _home, label, _uid: d[label],
                            command_fn=commands, probe=probe, stage=stages.append)
                self.assertEqual(stages[-1], "CHECK_COLLECTOR_CODE_IDENTITY")

    def test_isolated_python_ignores_synthetic_pythonpath_shadow(self):
        with tempfile.TemporaryDirectory() as folder:
            shadow = Path(folder) / "argparse.py"
            shadow.write_text("raise RuntimeError('UNTRUSTED_SHADOW_LOADED')\n",
                              encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = folder
            code = ("import argparse, pathlib; "
                    "print(pathlib.Path(argparse.__file__).resolve())")
            isolated = subprocess.run(
                [sys.executable, "-I", "-c", code],
                env=env, capture_output=True, text=True, check=True, timeout=8)
            self.assertNotIn(folder, isolated.stdout)
            self.assertNotIn("UNTRUSTED_SHADOW_LOADED", isolated.stderr)

    def test_loaded_collector_must_match_approved_plist_args(self):
        def outdated(*args, **kwargs):
            if args[:2] == ("launchctl", "print") and args[-1].endswith(
                    m.LABEL_COLLECTOR):
                argv = fixtures()[m.LABEL_COLLECTOR]["ProgramArguments"][:]
                argv.remove("-I")  # simulated old loaded job still non-isolated
                return ("run interval = 60 seconds\n"
                        + "program = " + argv[0] + "\n"
                        + "arguments = {\n"
                        + "\n".join("    " + x for x in argv)
                        + "\n}")
            return commands(*args, **kwargs)
        stages = []
        with self.assertRaises(m.PreflightRejected):
            m.check(NEW, reader=lambda _home, label, _uid: fixtures()[label],
                    command_fn=outdated, probe=probe, stage=stages.append)
        self.assertEqual(stages[-1], "CHECK_LOADED_COLLECTOR_COMMAND")

    def test_explicit_program_override_is_not_trusted(self):
        d = fixtures()
        d[m.LABEL_COLLECTOR]["Program"] = "/usr/bin/false"
        stages = []
        with self.assertRaises(m.PreflightRejected):
            m.check(NEW, reader=lambda _home, label, _uid: d[label],
                    command_fn=commands, probe=probe, stage=stages.append)
        self.assertEqual(stages[-1], "CHECK_COLLECTOR_EXECUTABLE")
        d[m.LABEL_COLLECTOR]["Program"] = d[m.LABEL_COLLECTOR]["ProgramArguments"][0]
        self.assertTrue(self.verify(definitions=d)["loaded_collector_executable_arguments_attested"])

    def test_missing_loaded_arguments_block_fails_closed(self):
        def missing(*args, **kwargs):
            if args[:2] == ("launchctl", "print") and args[-1].endswith(
                    m.LABEL_COLLECTOR):
                return "run interval = 60 seconds\nprogram = /usr/bin/python3"
            return commands(*args, **kwargs)
        stages = []
        with self.assertRaises(m.PreflightRejected):
            m.check(NEW, reader=lambda _home, label, _uid: fixtures()[label],
                    command_fn=missing, probe=probe, stage=stages.append)
        self.assertEqual(stages[-1], "CHECK_LOADED_COLLECTOR_COMMAND")

    def test_live_process_not_in_approved_working_directory_is_blocked(self):
        def moved(*args, **kwargs):
            if args[0] == "launchctl" and args[-1].endswith(m.LABEL_PORTFOLIO):
                return "pid = 123\nworking directory = /unapproved"
            return commands(*args, **kwargs)
        with self.assertRaises(m.PreflightRejected):
            self.verify(command_fn=moved)

    def test_invalid_canary_and_bad_revision_fail_closed(self):
        with self.assertRaises(m.PreflightRejected):
            m.check("not-sha", reader=lambda *_: None)
        def fake(*args):
            report = probe(*args)
            report["credentials_opened"] = True
            return report
        with self.assertRaises(m.PreflightRejected):
            self.verify(canary=fake)

    def test_cli_never_leaks_errors_or_private_paths(self):
        out = StringIO()
        with patch.object(m, "check", side_effect=RuntimeError(
                "credential content /private/DO_NOT_OUTPUT")):
            with redirect_stdout(out):
                self.assertEqual(m.main(["--expected-commit", NEW]), 2)
        self.assertEqual(out.getvalue().strip().splitlines(), [
            "M1_PREDEPLOY_READONLY_REJECTED",
            "M1_FAILURE_STAGE=VALIDATE_EXPECTED_SHA",
        ])
        self.assertNotIn("DO_NOT_OUTPUT", out.getvalue())

    def test_diagnostic_stage_sanitizes_bad_loaded_collector(self):
        observed = []

        def bad_collector(*args, **kwargs):
            if args[:2] == ("launchctl", "print") and args[-1].endswith(
                    m.LABEL_COLLECTOR):
                raise RuntimeError(
                    "private/config /secret-value should never appear")
            return commands(*args, **kwargs)

        with self.assertRaises(RuntimeError):
            m.check(NEW, reader=lambda _home, label, _uid: fixtures()[label],
                    command_fn=bad_collector, probe=probe, stage=observed.append)
        self.assertEqual(observed[-1], "CHECK_LOADED_PERIODIC_SCHEDULES")

        def bad_canary(*args):
            raise RuntimeError("wallet address private")

        observed.clear()
        with self.assertRaises(RuntimeError):
            m.check(NEW, reader=lambda _home, label, _uid: fixtures()[label],
                    command_fn=commands, probe=bad_canary,
                    stage=observed.append)
        self.assertEqual(observed[-1], "CHECK_CANDIDATE_RELEASE_CANARY")

    def test_cli_sanitizes_caught_stage_diagnostic(self):
        output = StringIO()

        def reject(_sha, *, stage):
            stage("CHECK_COLLECTOR_EXPECTED_SHA")
            raise RuntimeError("sensitive local path")

        with patch.object(m, "check", side_effect=reject):
            with redirect_stdout(output):
                self.assertEqual(m.main(["--expected-commit", NEW]), 2)
        self.assertEqual(output.getvalue().strip().splitlines(), [
            "M1_PREDEPLOY_READONLY_REJECTED",
            "M1_FAILURE_STAGE=CHECK_COLLECTOR_EXPECTED_SHA",
        ])
        self.assertNotIn("sensitive", output.getvalue())

    def test_git_attestation_rejects_executable_checkout_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "runtime"
            git = root / ".git"
            git.mkdir(parents=True)
            config = git / "config"
            for payload in (
                "[core]\nfsmonitor = /untrusted/hook\n",
                "[filter \"external\"]\nclean = /untrusted/filter\n",
                "[include]\npath = /untrusted/extra-config\n",
                "[hook \"post-index-change\"]\ncommand = /untrusted/hook\n",
                "[core]\nhooksPath = /untrusted/hooks\n",
            ):
                config.write_text(payload)
                with self.subTest(payload=payload.splitlines()[0]):
                    with self.assertRaises(m.PreflightRejected):
                        m.assert_trusted_git_checkout(root, os.getuid())
            config.write_text("[core]\nrepositoryformatversion = 0\n")
            m.assert_trusted_git_checkout(root, os.getuid())
            config.chmod(0o666)
            with self.assertRaises(m.PreflightRejected):
                m.assert_trusted_git_checkout(root, os.getuid())
            config.chmod(0o600)
            config.unlink()
            external = Path(d) / "external"
            external.write_text("[core]\nrepositoryformatversion = 0\n")
            config.symlink_to(external)
            with self.assertRaises(OSError):
                m.assert_trusted_git_checkout(root, os.getuid())

    def test_system_git_invocation_scrubs_inherited_config_and_disables_hooks(self):
        with patch.dict(os.environ, {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.fsmonitor",
                "GIT_CONFIG_VALUE_0": "/untrusted/exec",
                "GIT_DIR": "/untrusted/repo"}):
            with patch.object(m.subprocess, "run",
                    return_value=SimpleNamespace(returncode=0, stdout="")) as mocked:
                self.assertEqual(m.command(
                    "git", "-C", "/safe/repo", "status", "--porcelain"), "")
            argv = mocked.call_args.args[0]
            env = mocked.call_args.kwargs["env"]
            self.assertEqual(argv[0], "/usr/bin/git")
            self.assertIn("--no-optional-locks", argv)
            self.assertIn("core.fsmonitor=false", argv)
            self.assertIn("core.hooksPath=/dev/null", argv)
            self.assertIn("core.untrackedCache=false", argv)
            self.assertNotIn("GIT_DIR", env)
            self.assertNotIn("GIT_CONFIG_COUNT", env)
            self.assertEqual(env["GIT_OPTIONAL_LOCKS"], "0")
            self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")

    def test_command_line_option_rejects_duplicate_or_missing_values(self):
        self.assertEqual(m.option(["--output", OUT], "--output"), OUT)
        self.assertEqual(m.option(["--output="+OUT], "--output"), OUT)
        for args in (["--output"], [], ["--output", OUT, "--output", OUT]):
            with self.subTest(args=args):
                with self.assertRaises(m.PreflightRejected):
                    m.option(args, "--output")


if __name__ == "__main__":
    unittest.main()
