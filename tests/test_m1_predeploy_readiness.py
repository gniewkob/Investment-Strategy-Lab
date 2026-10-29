"""No Mac/LaunchAgent access: fake commands and preflight metadata only."""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
import json
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
            "ProgramArguments": ["/usr/bin/python3", "-m",
                "scripts.unattended_acceptance", "--state-directory", STATE,
                "--output", OUT, "--expected-commit", OLD],
            "StartInterval": 60,
        },
    }


def commands(*args, cwd=None):
    if args[:2] == ("launchctl", "print"):
        if args[-1].endswith(m.LABEL_PORTFOLIO):
            return "pid = 123\nworking directory = " + ROOT
        if args[-1].endswith(m.LABEL_HEALTH):
            return "run interval = 300 seconds"
        if args[-1].endswith(m.LABEL_COLLECTOR):
            return "run interval = 60 seconds"
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
             lambda d: d[m.LABEL_COLLECTOR]["ProgramArguments"].remove(
                 "scripts.unattended_acceptance")),
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

            args = ["/usr/bin/python3", str(script)]
            self.assertEqual(m.verified_collector_entrypoint(args),
                             "REVIEWED_COPIED_PYTHON_SCRIPT")
            self.assertEqual(m.verified_collector_entrypoint([
                "/usr/bin/python3", "-m", "scripts.unattended_acceptance"]),
                "REVIEWED_PYTHON_MODULE")

            defs = fixtures()
            defs[m.LABEL_COLLECTOR]["ProgramArguments"][:3] = args
            result = self.verify(definitions=defs)
            self.assertEqual(result["collector_entrypoint_verified"],
                             "REVIEWED_COPIED_PYTHON_SCRIPT")
            self.assertNotIn(str(script), json.dumps(result))

    def test_copied_script_rejects_content_drift_or_untrusted_path(self):
        with tempfile.TemporaryDirectory() as folder:
            approved = Path(__file__).resolve().parents[1] / "scripts" / "unattended_acceptance.py"
            script = Path(folder) / "collector.py"
            pristine = approved.read_bytes()
            script.write_bytes(pristine + b"# extra line\n")
            script.chmod(0o600)
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(["/usr/bin/python3", str(script)])
            script.write_bytes(pristine)
            script.chmod(0o666)
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(["/usr/bin/python3", str(script)])
            script.chmod(0o600)
            link = Path(folder) / "alias.py"
            link.symlink_to(script)
            with self.assertRaises(OSError):
                m.verified_collector_entrypoint(["/usr/bin/python3", str(link)])
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(["/usr/bin/python3", "relative.py"])
            with self.assertRaises(m.PreflightRejected):
                m.verified_collector_entrypoint(["/bin/bash", str(script)])
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
                    ["/usr/bin/python3", str(altered_script)],
                    approved_source=altered_source)

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

    def test_command_line_option_rejects_duplicate_or_missing_values(self):
        self.assertEqual(m.option(["--output", OUT], "--output"), OUT)
        self.assertEqual(m.option(["--output="+OUT], "--output"), OUT)
        for args in (["--output"], [], ["--output", OUT, "--output", OUT]):
            with self.subTest(args=args):
                with self.assertRaises(m.PreflightRejected):
                    m.option(args, "--output")


if __name__ == "__main__":
    unittest.main()
