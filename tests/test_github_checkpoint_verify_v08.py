"""Synthetic GitHub API response fixtures; no network and no transactions."""
from copy import deepcopy
import unittest

from scripts.shadow_capture_v07 import capture, REPO
from scripts.github_checkpoint_verify_v08 import verify
from scripts.shadow_decision_engine_v05 import ShadowInputError

WHEN = "2026-11-06T18:00:00Z"
CUTOFF = "2026-11-07T00:00:00Z"


def scenario():
    metadata = {
        "repository": REPO, "run_id": 42303069319, "run_attempt": 1,
        "head_sha": "a" * 40, "event": "pull_request",
    }
    cap = capture(metadata, WHEN)
    run = {
        "id": metadata["run_id"], "run_attempt": 1,
        "head_sha": metadata["head_sha"], "event": "pull_request",
        "status": "completed", "conclusion": "success",
        "repository": {"full_name": REPO},
        "head_repository": {"full_name": REPO},
        "path": ".github/workflows/shadow-capture-v07.yml@refs/pull/96/merge",
        "created_at": "2026-11-06T17:59:00Z",
        "run_started_at": "2026-11-06T17:59:30Z",
        "updated_at": "2026-11-06T18:03:00Z",
    }
    artifacts = {"artifacts": [{
        "id": 1234567,
        "name": "isl-v07-shadow-capture-run-42303069319-attempt-1",
        "expired": False,
        "workflow_run": {"id": metadata["run_id"], "head_sha": metadata["head_sha"]},
        "created_at": "2026-11-06T18:02:00Z",
    }]}
    return cap, run, artifacts


class GithubCheckpointV08Tests(unittest.TestCase):
    def test_matches_separately_fetched_metadata_but_no_timestamp_certificate(self):
        cap, run, artifacts = scenario()
        a = verify(cap, run, artifacts, cutoff_utc=CUTOFF)
        self.assertEqual(a, verify(deepcopy(cap), deepcopy(run), deepcopy(artifacts), cutoff_utc=CUTOFF))
        self.assertEqual(a["artifact_id"], 1234567)
        self.assertTrue(a["github_api_metadata_matches"])
        self.assertFalse(a["artifact_bytes_externally_authenticated"])
        self.assertFalse(a["trusted_timestamp_certified"])
        self.assertFalse(a["prospective_performance_verified"])
        self.assertFalse(a["model_returns_calculated"])
        self.assertEqual(a["orders_sent"], 0)

    def test_forged_capture_rejected(self):
        cap, run, arts = scenario()
        cap["captured_at_utc"] = "2026-11-05T18:00:00Z"
        with self.assertRaisesRegex(ShadowInputError, "fingerprint mismatch"):
            verify(cap, run, arts, cutoff_utc=CUTOFF)

    def test_run_failure_and_wrong_commit_rejected(self):
        cap, run, arts = scenario()
        run["conclusion"] = "failure"
        with self.assertRaisesRegex(ShadowInputError, "identity or success"):
            verify(cap, run, arts, cutoff_utc=CUTOFF)
        cap, run, arts = scenario()
        run["head_sha"] = "b" * 40
        with self.assertRaisesRegex(ShadowInputError, "identity or success"):
            verify(cap, run, arts, cutoff_utc=CUTOFF)

    def test_wrong_workflow_or_fork_rejected(self):
        cap, run, arts = scenario()
        run["path"] = ".github/workflows/other.yml@main"
        with self.assertRaisesRegex(ShadowInputError, "workflow path"):
            verify(cap, run, arts, cutoff_utc=CUTOFF)
        cap, run, arts = scenario()
        run["head_repository"]["full_name"] = "attacker/fork"
        with self.assertRaisesRegex(ShadowInputError, "head repository"):
            verify(cap, run, arts, cutoff_utc=CUTOFF)

    def test_missing_duplicate_or_expired_artifact_rejected(self):
        cap, run, arts = scenario()
        arts["artifacts"] = []
        with self.assertRaisesRegex(ShadowInputError, "exactly one"):
            verify(cap, run, arts, cutoff_utc=CUTOFF)
        cap, run, arts = scenario()
        arts["artifacts"].append(deepcopy(arts["artifacts"][0]))
        with self.assertRaisesRegex(ShadowInputError, "exactly one"):
            verify(cap, run, arts, cutoff_utc=CUTOFF)
        cap, run, arts = scenario()
        arts["artifacts"][0]["expired"] = True
        with self.assertRaisesRegex(ShadowInputError, "identity or retention"):
            verify(cap, run, arts, cutoff_utc=CUTOFF)

    def test_retroactive_cutoff_rejected(self):
        cap, run, arts = scenario()
        with self.assertRaisesRegex(ShadowInputError, "complete before"):
            verify(cap, run, arts, cutoff_utc="2026-11-06T18:01:00Z")
        cap, run, arts = scenario()
        run["updated_at"] = "2026-11-06T18:01:00Z"
        with self.assertRaisesRegex(ShadowInputError, "preserved before cutoff"):
            verify(cap, run, arts, cutoff_utc="2026-11-06T18:01:30Z")

    def test_github_second_precision_artifact_time_does_not_false_reject(self):
        from scripts.shadow_decision_engine_v05 import _digest
        cap, run, arts = scenario()
        instant = "2026-11-06T18:00:00.500000+00:00"
        cap["captured_at_utc"] = instant
        cap["decision"]["as_of_utc"] = instant
        cap["decision"]["decision_fingerprint_sha256"] = _digest({
            k: v for k, v in cap["decision"].items() if k != "decision_fingerprint_sha256"
        })
        cap["capture_sha256"] = _digest({
            k: v for k, v in cap.items() if k != "capture_sha256"
        })
        # GitHub rounds/truncates artifact timestamp to the whole second.
        arts["artifacts"][0]["created_at"] = "2026-11-06T18:00:00Z"
        checked = verify(cap, run, arts, cutoff_utc=CUTOFF)
        self.assertTrue(checked["github_api_metadata_matches"])
        self.assertFalse(checked["trusted_timestamp_certified"])
        arts["artifacts"][0]["created_at"] = "2026-11-06T17:59:59Z"
        with self.assertRaisesRegex(ShadowInputError, "not preserved before cutoff"):
            verify(cap, run, arts, cutoff_utc=CUTOFF)

    def test_mismatched_frozen_decision_rejected(self):
        cap, run, arts = scenario()
        cap["decision"]["as_of_utc"] = "2026-11-06T18:01:00Z"
        from scripts.shadow_decision_engine_v05 import _digest
        cap["decision"]["decision_fingerprint_sha256"] = _digest({
            k: v for k, v in cap["decision"].items() if k != "decision_fingerprint_sha256"
        })
        cap["capture_sha256"] = _digest({
            k: v for k, v in cap.items() if k != "capture_sha256"
        })
        with self.assertRaisesRegex(ShadowInputError, "capture date differs"):
            verify(cap, run, arts, cutoff_utc=CUTOFF)


if __name__ == "__main__":
    unittest.main()
