"""Offline negative and smoke checks for the manual GitHub billing fallback."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import ci_billing_fallback_v01 as fallback


SHA = "a" * 40
NOTE = "The job was not started because your account is locked due to a billing issue."


def snapshots():
    run_id = 987654
    run = {
        "id": run_id,
        "head_sha": SHA,
        "html_url": f"https://github.com/{fallback.REPOSITORY}/actions/runs/{run_id}",
        "path": fallback.WORKFLOW,
        "event": "pull_request",
        "status": "completed",
        "conclusion": "failure",
    }
    jobs = {
        "total_count": 2,
        "jobs": [{
            "name": name,
            "run_id": run_id,
            "head_sha": SHA,
            "status": "completed",
            "conclusion": "failure",
            "steps": [],
        } for name in ("stack-ubuntu", "stack-macos")],
    }
    return run, jobs


class BillingTriageTests(unittest.TestCase):
    def test_accepts_exact_pre_execution_failed_stack_jobs_only(self):
        run, jobs = snapshots()
        receipt = fallback.assess_billing_preexecution(run, jobs, SHA, NOTE)
        self.assertEqual(receipt["hosted_ci"], "FAILURE_WITH_ZERO_STEPS")
        self.assertEqual(receipt["billing_attribution"], "OPERATOR_COPIED_GITHUB_UI_UNVERIFIED")
        self.assertNotIn(NOTE, str(receipt))

    def test_rejects_other_commit(self):
        run, jobs = snapshots()
        with self.assertRaises(fallback.FallbackBlocked):
            fallback.assess_billing_preexecution(run, jobs, "b" * 40, NOTE)

    def test_rejects_non_exact_or_uppercase_sha(self):
        run, jobs = snapshots()
        for bad_sha in ("main", SHA.upper(), "a" * 39, "a" * 41):
            with self.subTest(bad_sha=bad_sha), self.assertRaises(fallback.FallbackBlocked):
                fallback.assess_billing_preexecution(run, jobs, bad_sha, NOTE)

    def test_rejects_missing_billing_message_and_generic_failure(self):
        run, jobs = snapshots()
        for note in ("", "Error: test failed", "Billing problem", "Job was not started"):
            with self.subTest(note=note), self.assertRaises(fallback.FallbackBlocked):
                fallback.assess_billing_preexecution(run, jobs, SHA, note)

    def test_rejects_wrong_run_url_workflow_or_event(self):
        for field, value in (
            ("html_url", "https://github.com/example/actions/runs/987654"),
            ("path", "other.yml"),
            ("event", "workflow_dispatch"),
            ("conclusion", "success"),
            ("status", "queued"),
        ):
            run, jobs = snapshots()
            run[field] = value
            with self.subTest(field=field), self.assertRaises(fallback.FallbackBlocked):
                fallback.assess_billing_preexecution(run, jobs, SHA, NOTE)

    def test_rejects_job_with_executed_steps(self):
        run, jobs = snapshots()
        jobs["jobs"][0]["steps"] = [{"name": "checkout", "conclusion": "failure"}]
        with self.assertRaises(fallback.FallbackBlocked):
            fallback.assess_billing_preexecution(run, jobs, SHA, NOTE)

    def test_rejects_missing_duplicated_wrong_or_unfinished_jobs(self):
        for field, value in (
            ("name", "wrong"),
            ("run_id", 1),
            ("head_sha", "b" * 40),
            ("status", "in_progress"),
            ("conclusion", "success"),
            ("steps", None),
        ):
            run, jobs = snapshots()
            jobs["jobs"][1][field] = value
            with self.subTest(field=field), self.assertRaises(fallback.FallbackBlocked):
                fallback.assess_billing_preexecution(run, jobs, SHA, NOTE)
        run, jobs = snapshots()
        jobs["jobs"][1] = dict(jobs["jobs"][0])
        with self.assertRaises(fallback.FallbackBlocked):
            fallback.assess_billing_preexecution(run, jobs, SHA, NOTE)
        jobs["jobs"].pop()
        with self.assertRaises(fallback.FallbackBlocked):
            fallback.assess_billing_preexecution(run, jobs, SHA, NOTE)


class CheckoutAndRunnerTests(unittest.TestCase):
    @mock.patch.object(fallback, "_git")
    @mock.patch.object(fallback.platform, "system", return_value="Darwin")
    def test_checkout_pinned_and_clean(self, _system, git):
        root = Path("/tmp/isl-target").resolve()
        git.side_effect = [str(root), SHA, ""]
        fallback.verify_checkout(root, SHA)
        self.assertEqual(git.call_count, 3)

    @mock.patch.object(fallback, "_git")
    @mock.patch.object(fallback.platform, "system", return_value="Darwin")
    def test_checkout_wrong_sha_or_dirty_is_blocked(self, _system, git):
        root = Path("/tmp/isl-target").resolve()
        for outputs in ([str(root), "b" * 40], [str(root), SHA, "?? new.py"]):
            git.side_effect = outputs
            with self.assertRaises(fallback.FallbackBlocked):
                fallback.verify_checkout(root, SHA)
            git.reset_mock()

    @mock.patch.object(fallback.platform, "system", return_value="Linux")
    def test_operational_runner_refuses_non_macos(self, _system):
        with self.assertRaisesRegex(fallback.FallbackBlocked, "macOS"):
            fallback.verify_checkout(Path("/tmp/unused"), SHA)

    @mock.patch.object(fallback.subprocess, "run")
    def test_run_exact_two_offline_stack_commands(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout=b"ok", stderr=b"")
        steps = fallback.run_offline_stack(Path("/tmp/isl-target"))
        self.assertEqual(len(steps), 2)
        self.assertTrue(all(s["exit_code"] == 0 for s in steps))
        first = run.call_args_list[0].args[0]
        second = run.call_args_list[1].args[0]
        self.assertEqual(first[1:], ["-m", "unittest", "-v", "tests.test_isl_stack_chain_acceptance_v01"])
        self.assertEqual(second[1:], ["-m", "scripts.isl_stack_chain_acceptance_v01", "--repository-root", "."])
        self.assertEqual(steps[0]["stdout_sha256"], fallback._digest(b"ok"))

    @mock.patch.object(fallback.subprocess, "run")
    def test_failed_first_step_halts_without_false_pass(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"fail")
        steps = fallback.run_offline_stack(Path("/tmp/isl-target"))
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["exit_code"], 1)
        self.assertEqual(run.call_count, 1)


class ReceiptTests(unittest.TestCase):
    def _fixture(self, temp: Path):
        target = temp / "checkout"
        target.mkdir()
        run, jobs = snapshots()
        (temp / "run.json").write_text(json.dumps(run), encoding="utf-8")
        (temp / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
        (temp / "note.txt").write_text(NOTE, encoding="utf-8")
        return argparse.Namespace(repository_root=str(target), sha=SHA,
                                  run_json=str(temp / "run.json"),
                                  jobs_json=str(temp / "jobs.json"),
                                  billing_note_file=str(temp / "note.txt"),
                                  out=str(temp / "receipt.json"))

    @mock.patch.object(fallback, "verify_checkout")
    @mock.patch.object(fallback, "run_offline_stack")
    def test_pass_receipt_is_local_only_and_does_not_overwrite(self, run_stack, checkout):
        run_stack.return_value = [{"exit_code": 0, "timed_out": False}] * 2
        with tempfile.TemporaryDirectory() as tempdir:
            args = self._fixture(Path(tempdir))
            self.assertEqual(fallback.execute(args), 0)
            receipt = json.loads(Path(args.out).read_text(encoding="utf-8"))
            self.assertEqual(receipt["local_test_status"], "PASS")
            self.assertFalse(receipt["hosted_checks_passed"])
            self.assertFalse(receipt["merge_authorized"])
            self.assertFalse(receipt["deploy_authorized"])
            self.assertTrue(receipt["checkout_unchanged_after_tests"])
            with self.assertRaises(fallback.FallbackBlocked):
                fallback.execute(args)
            self.assertEqual(run_stack.call_count, 1)

    @mock.patch.object(fallback, "verify_checkout")
    @mock.patch.object(fallback, "run_offline_stack")
    def test_failed_test_writes_failed_receipt(self, run_stack, checkout):
        run_stack.return_value = [{"exit_code": 1, "timed_out": False}]
        with tempfile.TemporaryDirectory() as tempdir:
            args = self._fixture(Path(tempdir))
            self.assertEqual(fallback.execute(args), 1)
            receipt = json.loads(Path(args.out).read_text(encoding="utf-8"))
            self.assertEqual(receipt["local_test_status"], "FAIL")

    @mock.patch.object(fallback, "verify_checkout")
    @mock.patch.object(fallback, "run_offline_stack")
    def test_post_run_dirty_checkout_invalidates_success(self, run_stack, checkout):
        run_stack.return_value = [{"exit_code": 0, "timed_out": False}] * 2
        checkout.side_effect = [None, fallback.FallbackBlocked("dirty")]
        with tempfile.TemporaryDirectory() as tempdir:
            args = self._fixture(Path(tempdir))
            self.assertEqual(fallback.execute(args), 1)
            receipt = json.loads(Path(args.out).read_text(encoding="utf-8"))
            self.assertEqual(receipt["local_test_status"], "FAIL")
            self.assertFalse(receipt["checkout_unchanged_after_tests"])

    @mock.patch.object(fallback, "verify_checkout")
    @mock.patch.object(fallback, "run_offline_stack")
    def test_bad_triage_never_runs_checks_or_writes_receipt(self, run_stack, checkout):
        with tempfile.TemporaryDirectory() as tempdir:
            args = self._fixture(Path(tempdir))
            Path(args.billing_note_file).write_text("tests failed", encoding="utf-8")
            with self.assertRaises(fallback.FallbackBlocked):
                fallback.execute(args)
            run_stack.assert_not_called()
            checkout.assert_not_called()
            self.assertFalse(Path(args.out).exists())


if __name__ == "__main__":
    unittest.main()
