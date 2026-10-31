"""Offline tests only: launchd is simulated; no real services are changed."""
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from scripts import m1_isolated_launchd_rollback_drill as drill


class FakeLaunchctl:
    def __init__(self, fail_v3_check=False):
        self.loaded = {}
        self.actions = []
        self.fail_v3_check = fail_v3_check
        self.observed_durations = []

    def __call__(self, argv):
        self.actions.append(tuple(argv))
        if argv[0] != drill.LAUNCHCTL:
            raise AssertionError("Wrong executable")
        action = argv[1]
        if action == "bootstrap":
            definition = plistlib.loads(Path(argv[3]).read_bytes())
            label = definition["Label"]
            assert label.startswith(drill.LABEL_PREFIX)
            assert definition["Program"] == drill.SLEEP
            assert definition["ProgramArguments"][0] == drill.SLEEP
            assert argv[2].startswith("gui/")
            assert label not in self.loaded
            self.loaded[label] = definition["ProgramArguments"]
            self.observed_durations.append(definition["ProgramArguments"][1])
            return ""
        if action == "print":
            label = argv[2].split("/", 2)[2]
            seconds = self.loaded[label][1]
            if seconds == drill.V3_SECONDS and self.fail_v3_check:
                seconds = "999"
            return (
                "program = /bin/sleep\n"
                "arguments = {\n"
                "    /bin/sleep\n"
                f"    {seconds}\n"
                "}\n"
                "pid = 12345\n"
            )
        if action == "bootout":
            label = argv[2].split("/", 2)[2]
            del self.loaded[label]
            return ""
        raise AssertionError("Unsupported action")


class IsolatedLaunchdDrillTests(unittest.TestCase):
    def test_fake_launchctl_print_is_valid_and_has_exact_argument(self):
        fake = FakeLaunchctl()
        label = drill.LABEL_PREFIX + "c" * 16
        fake.loaded[label] = [drill.SLEEP, drill.V2_SECONDS]
        payload = fake([drill.LAUNCHCTL, "print", "gui/501/" + label])
        self.assertIn("arguments = {", payload)
        self.assertIn("600", payload)
        drill.verify_loaded(payload, label, drill.V2_SECONDS)

    def test_synthetic_v2_v3_v2_then_unload(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeLaunchctl()
            report = drill.rehearse(
                runner=fake, uid=os.getuid(), directory=directory
            )
            self.assertEqual(report["status"],
                             "SYNTHETIC_V2_RESTORED_AND_UNLOADED")
            self.assertTrue(report["isolated_v2_v3_v2_cycle"])
            self.assertFalse(report["active_collector_restore_tested"])
            self.assertFalse(report["production_launchagents_modified"])
            self.assertFalse(report["historical_evidence_modified"])
            self.assertEqual(report["financial_operations"], 0)
            self.assertFalse(report["g3_authorization"])
            self.assertEqual(fake.observed_durations, [
                drill.V2_SECONDS, drill.V3_SECONDS, drill.V2_SECONDS
            ])
            self.assertEqual(fake.loaded, {})
            self.assertEqual([action[1] for action in fake.actions], [
                "bootstrap", "print", "bootout",
                "bootstrap", "print", "bootout",
                "bootstrap", "print", "bootout"
            ])
            self.assertFalse(list(Path(directory).iterdir()))

    def test_unexpected_v3_metadata_fails_and_attempts_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeLaunchctl(fail_v3_check=True)
            with self.assertRaisesRegex(drill.DrillRejected, "^VERIFY_V3$"):
                drill.rehearse(runner=fake, uid=os.getuid(),
                               directory=directory)
            self.assertEqual(fake.loaded, {})
            self.assertEqual(fake.actions[-1][1], "bootout")

    def test_refuses_non_synthetic_label_or_program(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for label, duration in [
                ("pl.gniewkob.isl.acceptance", drill.V2_SECONDS),
                (drill.LABEL_PREFIX + "abc", drill.V2_SECONDS),
                (drill.LABEL_PREFIX + "a" * 16, "13"),
            ]:
                with self.subTest(label=label, duration=duration):
                    with self.assertRaises(drill.DrillRejected):
                        drill.private_plist(path, label, "test", duration)
            self.assertEqual(list(path.iterdir()), [])

    def test_cli_defaults_to_no_service_operations(self):
        out = StringIO()
        with redirect_stdout(out):
            rc = drill.main([])
        self.assertEqual(rc, 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report["status"], "PLAN_ONLY_NOT_EXECUTED")
        self.assertFalse(report["production_launchagents_modified"])
        self.assertFalse(report["g3_authorization"])

    def test_cli_refuses_non_darwin(self):
        out = StringIO()
        with patch.object(drill.platform, "system", return_value="Linux"):
            with redirect_stdout(out):
                rc = drill.main(["--run-isolated"])
        self.assertEqual(rc, 2)
        self.assertIn("REJECTED_WRONG_PLATFORM", out.getvalue())
        self.assertIn("M1_G3_AUTHORIZATION=NO", out.getvalue())

    def test_loaded_parser_rejects_wrong_command_or_missing_pid(self):
        label = drill.LABEL_PREFIX + "b" * 16
        for payload in (
            "program = /bin/sleep\narguments = {\n/bin/sleep\n13\n}\npid = 3",
            "program = /bin/bash\narguments = {\n/bin/sleep\n600\n}\npid = 3",
            "program = /bin/sleep\narguments = {\n/bin/sleep\n600\n}",
            "",
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(drill.DrillRejected):
                    drill.verify_loaded(payload, label, drill.V2_SECONDS)


if __name__ == "__main__":
    unittest.main()
