"""Offline safety tests for the M1 collector-only G3 cutover.

No macOS services or financial accounts are accessed. All launchctl calls
are injected fakes; temporary files live under a private test root.
"""
from contextlib import contextmanager, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import plistlib
import signal
import tempfile
import unittest
from unittest.mock import patch

from scripts import m1_g3_collector_only_cutover as m
from scripts import m1_collector_release_prepare as backup


class FakeHost:
    def __init__(self, base, *, fail_v3_check=False, fail_v3_bootstrap=False):
        self.home = Path(base) / "home"
        self.home.mkdir(mode=0o700)
        # A verified local fixture file satisfies the host-executable guard.
        # Every service action is still intercepted by the fake job runner.
        self.fake_launchctl = self.home / "synthetic-launchctl-fixture"
        self.fake_launchctl.write_text("test fixture only, never execute\n")
        self.fake_launchctl.chmod(0o600)
        self.agents = self.home / "Library" / "LaunchAgents"
        self.agents.mkdir(parents=True)
        self.script = self.home / "private-collector.py"
        self.plist = self.agents / (m.LABEL + ".plist")
        self.backup_root = self.home / "PrivateBackup"
        self.backup_root.mkdir(mode=0o700)
        self.old_code = (Path(__file__).resolve().parent /
                         "fixtures" / "collector_legacy_v2.txt").read_bytes()
        self.new_code = (Path(__file__).resolve().parents[1] /
                         "scripts" / "unattended_acceptance.py").read_bytes()
        self.assert_source_blobs()
        self.script.write_bytes(self.old_code)
        self.script.chmod(0o600)
        self.runtime = self.home / "runtime"
        self.runtime.mkdir()
        self.old_plist = {
            "Label": m.LABEL, "StartInterval": 60,
            "ProgramArguments": [
                "/usr/bin/python3", str(self.script),
                "--state-directory", str(self.home / "collector_state"),
                "--output", str(self.home / "observations"),
                "--expected-commit", m.LEGACY_RUNTIME,
                "--runtime", str(self.runtime),
            ],
        }
        self.new_plist = dict(self.old_plist)
        self.new_plist["ProgramArguments"] = [
            "/usr/bin/python3", "-I", *self.old_plist["ProgramArguments"][1:]
        ]
        self.old_plist_bytes = plistlib.dumps(self.old_plist)
        self.new_plist_bytes = plistlib.dumps(self.new_plist)
        self.plist.write_bytes(self.old_plist_bytes)
        self.plist.chmod(0o600)
        self.bundle = {
            "collector-before.plist": self.old_plist_bytes,
            "collector-before.py": self.old_code,
            "collector-isolated-staged.plist": self.new_plist_bytes,
            "collector-isolated-staged.py": self.new_code,
        }
        self.loaded = True
        self.v3_attempted = False
        self.fail_v3_check = fail_v3_check
        self.fail_v3_bootstrap = fail_v3_bootstrap
        self.actions = []

    def assert_source_blobs(self):
        assert backup.source_blob(self.old_code) == backup.GIT_BLOB
        assert backup.source_blob(self.new_code) == backup.NEW_GIT_BLOB

    def fake_job(self, argv):
        self.actions.append(tuple(argv))
        if argv[0] == "bootout":
            assert self.loaded
            self.loaded = False
        elif argv[0] == "bootstrap":
            if self.fail_v3_bootstrap and self.script.read_bytes() == self.new_code:
                self.v3_attempted = True
                raise m.CutoverRejected("MOCK_REJECTED_BOOTSTRAP_V3")
            assert not self.loaded
            self.loaded = True
        else:
            raise AssertionError("Unexpected launchctl action")

    def fake_preflight(self, expected, *, collector_phase, **_):
        assert expected == m.CANDIDATE
        assert self.loaded, "Expected loaded collector in preflight"
        if collector_phase == "legacy-before":
            if (self.script.read_bytes() != self.old_code or
                    self.plist.read_bytes() != self.old_plist_bytes):
                raise m.CutoverRejected("MOCK_LEGACY_DRIFT")
            return {
                "status": "LEGACY_COLLECTOR_BASELINE_VERIFIED_NO_DEPLOY",
                "current_on_disk_runtime_sha": m.LEGACY_RUNTIME,
                "loaded_collector_executable_arguments_attested": True,
                "financial_operations": 0,
            }
        if collector_phase == "isolated-after":
            assert self.script.read_bytes() == self.new_code
            assert self.plist.read_bytes() == self.new_plist_bytes
            if self.fail_v3_check:
                raise m.CutoverRejected("MOCK_V3_POSTFLIGHT_REJECTED")
            return {
                "status": "ISOLATED_COLLECTOR_METADATA_VERIFIED_NOT_RUNTIME_ATTESTED",
                "loaded_collector_executable_arguments_attested": True,
                "financial_operations": 0,
            }
        raise AssertionError("Unexpected preflight phase")


class G3CutoverTests(unittest.TestCase):
    @contextmanager
    def host(self, root, **kwargs):
        h = FakeHost(root, **kwargs)
        with patch.object(m.platform, "system", return_value="Darwin"), \
             patch.object(m.Path, "home", return_value=h.home), \
             patch.object(m, "LAUNCHCTL", str(h.fake_launchctl)), \
             patch.object(backup, "backup_base", return_value=h.backup_root), \
             patch.object(m, "read_proven_bundle", return_value=h.bundle), \
             patch.object(m, "validate_candidate_checkout",
                          return_value=h.home / "pinned-candidate"), \
             patch.object(m.preflight, "check", side_effect=h.fake_preflight), \
             patch.object(m, "job", side_effect=h.fake_job), \
             patch.object(m, "current_loaded", side_effect=lambda: h.loaded), \
             patch.object(m, "approved_loaded_collector",
                          side_effect=lambda _bundle: h.loaded):
            yield h

    def test_candidate_checkout_required_and_fails_before_service_action(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                with patch.object(m, "validate_candidate_checkout",
                                  side_effect=m.CutoverRejected("NO_CANDIDATE")):
                    with self.assertRaisesRegex(
                            m.CutoverRejected, "^NO_CANDIDATE$"):
                        m.execute()
                self.assertEqual(h.actions, [])
                self.assertTrue(h.loaded)

    def test_candidate_checkout_git_head_must_match_pinned_source(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            root = Path(d)
            with patch.object(m.preflight, "assert_trusted_git_checkout") as trusted, \
                 patch.object(m.preflight, "command", side_effect=[
                     "0" * 40, ""]):
                with self.assertRaises(m.CutoverRejected):
                    m.validate_candidate_checkout(root, os.getuid())
                trusted.assert_called_once_with(root, os.getuid())

    def test_preflight_uses_pinned_candidate_checkout_not_controller(self):
        root = Path("/safe/candidate-checkout")
        with patch.object(m.preflight, "check", return_value={"status": "PASS"}) as check, \
             patch.object(m.preflight.canary, "inspect",
                          return_value={"result": "PASS"}) as inspect:
            self.assertEqual(
                m.candidate_preflight(root, collector_phase="legacy-before"),
                {"status": "PASS"})
            cb = check.call_args.kwargs["probe"]
            self.assertEqual(cb("config", m.CANDIDATE, "before", "now"),
                             {"result": "PASS"})
            self.assertEqual(inspect.call_args.kwargs["repository_root"], root)
            self.assertEqual(inspect.call_args.args[1], m.CANDIDATE)


    def test_recovery_refuses_unexpected_loaded_service_before_bootout(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                with patch.object(m, "approved_loaded_collector",
                                  side_effect=m.CutoverRejected("WRONG_JOB")):
                    with self.assertRaisesRegex(m.CutoverRejected, "WRONG_JOB"):
                        m.recover_v2()
                self.assertTrue(h.loaded)
                self.assertEqual(h.actions, [])
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)

    def test_actual_loaded_inspector_refuses_unknown_argv(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            h = FakeHost(d)
            from types import SimpleNamespace
            wrong = ("program = /bin/sleep\n"
                     "arguments = {\n"
                     "/bin/sleep\n"
                     "500\n"
                     "}\n"
                     "pid = 1234\n")
            with patch.object(m.subprocess, "run",
                              return_value=SimpleNamespace(returncode=0,
                                                           stdout=wrong)):
                with self.assertRaises(m.CutoverRejected):
                    m.approved_loaded_collector(h.bundle)

    def test_loaded_inspector_accepts_only_pinned_v2_v3(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            h = FakeHost(d)
            from types import SimpleNamespace
            for argv in (h.old_plist["ProgramArguments"],
                         h.new_plist["ProgramArguments"]):
                text = ("program = /usr/bin/python3\n"
                        "arguments = {\n" +
                        "".join(str(token) + "\n" for token in argv) +
                        "}\n"
                        "pid = 1234\n")
                with patch.object(m.subprocess, "run",
                                  return_value=SimpleNamespace(returncode=0,
                                                               stdout=text)):
                    self.assertTrue(m.approved_loaded_collector(h.bundle))


    def test_generic_launchctl_error_never_means_collector_is_unloaded(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            h = FakeHost(d)
            status = SimpleNamespace(returncode=5, stdout="",
                                     stderr="Input/output error")
            with patch.object(m.subprocess, "run", return_value=status):
                with self.assertRaisesRegex(
                        m.CutoverRejected, "^LAUNCHD_STATE_UNKNOWN$"):
                    m.approved_loaded_collector(h.bundle)
                with self.assertRaisesRegex(
                        m.CutoverRejected, "^LAUNCHD_STATE_UNKNOWN$"):
                    m.current_loaded()

    def test_only_exact_missing_service_response_certifies_absence(self):
        from types import SimpleNamespace
        uid = os.getuid()
        target = (f'Could not find service "{m.LABEL}" '
                  f'in domain for user gui: {uid}')
        for code, message, expected in [
            (113, "Bad request.\n" + target + "\n", True),
            (5, "Bad request.\n" + target, False),
            (113, "Could not find service other in domain", False),
            (113, "Access denied", False),
        ]:
            with self.subTest(code=code, message=message):
                result = SimpleNamespace(returncode=code,
                                         stdout="", stderr=message)
                self.assertEqual(m.confirmed_unregistered(result, uid),
                                 expected)
        missing = SimpleNamespace(returncode=113, stdout="",
                                  stderr=target)
        with patch.object(m.subprocess, "run", return_value=missing):
            self.assertFalse(m.current_loaded())
            with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
                h = FakeHost(d)
                self.assertFalse(m.approved_loaded_collector(h.bundle))

    def test_recovery_unknown_launchctl_error_preserves_files_and_service(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                unknown = SimpleNamespace(returncode=5, stdout="",
                                          stderr="Input/output error")
                original = m.approved_loaded_collector
                with patch.object(m.subprocess, "run", return_value=unknown), \
                     patch.object(m, "approved_loaded_collector",
                                  side_effect=original):
                    with self.assertRaisesRegex(
                            m.CutoverRejected, "^LAUNCHD_STATE_UNKNOWN$"):
                        m.recover_v2()
                self.assertEqual(h.actions, [])
                self.assertTrue(h.loaded)
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)

    def test_bootout_ambiguous_state_must_not_bootstrap_over_unknown_job(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                def reject_after_stop(argv):
                    if argv[0] == "bootout":
                        h.actions.append(tuple(argv))
                        raise m.CutoverRejected("MOCK_UNCERTAIN_STOP")
                    return h.fake_job(argv)
                status = SimpleNamespace(returncode=5, stdout="",
                                         stderr="Input/output error")
                with patch.object(m, "job", side_effect=reject_after_stop), \
                     patch.object(m, "approved_loaded_collector",
                                  side_effect=lambda _bundle:
                                  m.current_loaded()), \
                     patch.object(m.subprocess, "run", return_value=status):
                    with self.assertRaisesRegex(
                            m.CutoverRejected, "^LAUNCHD_STATE_UNKNOWN$"):
                        m.execute()
                self.assertEqual([x[0] for x in h.actions], ["bootout"])
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)

    def test_plan_only_never_touches_host(self):
        out = StringIO()
        with redirect_stdout(out):
            rc = m.main([])
        self.assertEqual(rc, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["status"], "G3_PLAN_ONLY_NO_HOST_CHANGE")
        self.assertFalse(result["g3_executed"])
        self.assertEqual(result["candidate_sha"], m.CANDIDATE)

    def test_host_guard_rejects_missing_launchctl_without_change(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                with patch.object(m, "LAUNCHCTL",
                                  str(h.home / "nonexistent-launchctl")):
                    with self.assertRaisesRegex(
                            m.CutoverRejected, "^PRECONDITION_REJECTED$"):
                        m.execute()
                self.assertEqual(h.actions, [])
                self.assertTrue(h.loaded)
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)

    def test_synthetic_success_v2_to_v3(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                result = m.execute()
                self.assertEqual(result["status"],
                                 "G3_COLLECTOR_ONLY_CUTOVER_AND_G4_METADATA_PASS")
                self.assertFalse(result["g5_24h_completed"])
                self.assertEqual(result["financial_operations"], 0)
                self.assertEqual(h.script.read_bytes(), h.new_code)
                self.assertEqual(h.plist.read_bytes(), h.new_plist_bytes)
                self.assertTrue(h.loaded)
                self.assertEqual([x[0] for x in h.actions],
                                 ["bootout", "bootstrap"])

    def test_failed_g4_restores_exact_original_files_and_service(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d, fail_v3_check=True) as h:
                with self.assertRaisesRegex(
                        m.CutoverRejected, "G3_FAILED_V2_ROLLBACK_VERIFIED"):
                    m.execute()
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)
                self.assertTrue(h.loaded)
                self.assertEqual([x[0] for x in h.actions],
                                 ["bootout", "bootstrap", "bootout", "bootstrap"])

    def test_failed_v3_bootstrap_restores_legacy_without_extra_bootout(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d, fail_v3_bootstrap=True) as h:
                with self.assertRaisesRegex(
                        m.CutoverRejected, "G3_FAILED_V2_ROLLBACK_VERIFIED"):
                    m.execute()
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)
                self.assertTrue(h.loaded)
                self.assertEqual([x[0] for x in h.actions],
                                 ["bootout", "bootstrap", "bootstrap"])

    def test_bootout_reports_error_but_stopped_old_job_is_restarted(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                def failed_bootout(argv):
                    if argv[0] == "bootout":
                        h.actions.append(tuple(argv))
                        h.loaded = False
                        raise m.CutoverRejected("MOCK_BOOTOUT_FAILED_AFTER_STOP")
                    return h.fake_job(argv)
                with patch.object(m, "job", side_effect=failed_bootout):
                    with self.assertRaisesRegex(
                            m.CutoverRejected,
                            "G3_STOP_FAILED_V2_RESTARTED_VERIFIED"):
                        m.execute()
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)
                self.assertTrue(h.loaded)
                self.assertEqual([x[0] for x in h.actions],
                                 ["bootout", "bootstrap"])

    def test_bootout_rejected_before_stop_preserves_old_job(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                def failed_bootout(argv):
                    if argv[0] == "bootout":
                        h.actions.append(tuple(argv))
                        raise m.CutoverRejected("MOCK_BOOTOUT_REJECTED")
                    return h.fake_job(argv)
                with patch.object(m, "job", side_effect=failed_bootout):
                    with self.assertRaisesRegex(
                            m.CutoverRejected,
                            "G3_STOP_REJECTED_OLD_JOB_LOADED"):
                        m.execute()
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)
                self.assertTrue(h.loaded)
                self.assertEqual([x[0] for x in h.actions], ["bootout"])

    def test_sigint_during_cutover_defers_signal_until_v2_rollback(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                prior = signal.getsignal(signal.SIGINT)
                interrupted = [False]

                def interrupt_once(argv):
                    result = h.fake_job(argv)
                    if argv[0] == "bootout" and not interrupted[0]:
                        interrupted[0] = True
                        signal.raise_signal(signal.SIGINT)
                    return result

                with patch.object(m, "job", side_effect=interrupt_once):
                    with self.assertRaisesRegex(
                            m.CutoverRejected,
                            "G3_FAILED_V2_ROLLBACK_VERIFIED"):
                        m.execute()
                self.assertIs(signal.getsignal(signal.SIGINT), prior)
                self.assertTrue(interrupted[0])
                self.assertTrue(h.loaded)
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)
                self.assertEqual([a[0] for a in h.actions],
                                 ["bootout", "bootstrap"])

    def test_pre_stop_directory_fsync_rejected_without_bootout(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                with patch.object(m, "sync_dir", side_effect=OSError):
                    with self.assertRaisesRegex(
                            m.CutoverRejected,
                            "G3_STOP_REJECTED_OLD_JOB_LOADED"):
                        m.execute()
                self.assertTrue(h.loaded)
                self.assertEqual(h.actions, [])
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)
                self.assertFalse(list(h.script.parent.glob(".isl-g3-pending-*")))
                self.assertFalse(list(h.plist.parent.glob(".isl-g3-pending-*")))

    def test_explicit_v2_recovery_from_partially_written_cutover(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                h.script.write_bytes(h.new_code)
                h.plist.write_bytes(h.old_plist_bytes)
                h.loaded = False
                result = m.recover_v2()
                self.assertEqual(result["status"],
                                 "G3_OPERATOR_V2_RECOVERY_VERIFIED")
                self.assertEqual(result["financial_operations"], 0)
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)
                self.assertTrue(h.loaded)
                self.assertEqual([x[0] for x in h.actions], ["bootstrap"])

    def test_recovery_of_loaded_v3_bootouts_before_v2_bootstrap(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                h.script.write_bytes(h.new_code)
                h.plist.write_bytes(h.new_plist_bytes)
                result = m.recover_v2()
                self.assertEqual(result["status"],
                                 "G3_OPERATOR_V2_RECOVERY_VERIFIED")
                self.assertEqual(h.script.read_bytes(), h.old_code)
                self.assertEqual(h.plist.read_bytes(), h.old_plist_bytes)
                self.assertTrue(h.loaded)
                self.assertEqual([x[0] for x in h.actions],
                                 ["bootout", "bootstrap"])

    def test_recovery_rejects_unknown_source_before_bootout(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                h.script.write_bytes(b"unknown source")
                with self.assertRaises(m.CutoverRejected):
                    m.recover_v2()
                self.assertTrue(h.loaded)
                self.assertEqual(h.actions, [])

    def test_wrong_original_code_prevents_any_bootout(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as d:
            with self.host(d) as h:
                h.script.write_bytes(b"unknown source")
                with self.assertRaises(m.CutoverRejected):
                    m.execute()
                self.assertTrue(h.loaded)
                self.assertEqual(h.actions, [])

    def test_job_restricts_all_targets_except_collector(self):
        with patch.object(m.subprocess, "run") as fake:
            for argv in (
                ["bootout", "gui/1234/pl.gniewkob.isl.portfolio"],
                ["bootstrap", "gui/1234", "/tmp/untrusted.plist"],
                ["kickstart", "gui/1234/pl.gniewkob.isl.acceptance"],
                ["bootout", "system/pl.gniewkob.isl.acceptance"],
            ):
                with self.subTest(argv=argv):
                    with self.assertRaises(m.CutoverRejected):
                        m.job(argv)
            fake.assert_not_called()


if __name__ == "__main__":
    unittest.main()
