"""Offline checks for v0.7 read-only GitHub-context capture."""
from copy import deepcopy
import unittest

from scripts.shadow_capture_v07 import capture, REPO
from scripts.shadow_decision_engine_v05 import ShadowInputError, _digest


def context():
    return {
        "repository": REPO,
        "run_id": 42302612971,
        "run_attempt": 1,
        "head_sha": "a" * 40,
        "event": "pull_request",
    }


class ShadowCaptureV07Tests(unittest.TestCase):
    def test_deterministic_read_only_capture(self):
        a = capture(context(), "2026-11-06T18:00:00+00:00")
        self.assertEqual(a, capture(deepcopy(context()), "2026-11-06T18:00:00Z"))
        self.assertEqual(a["capture_sha256"], _digest(
            {k: v for k, v in a.items() if k != "capture_sha256"}))
        self.assertEqual(a["decision"]["eligible_models"], [])
        self.assertTrue(all(x["status"] == "HOLD_CASH"
                            for x in a["decision"]["model_decisions"].values()))
        for k in ("github_metadata_independently_verified",
                  "artifact_timestamp_independently_verified",
                  "prospective_timing_certified", "future_performance_observed"):
            self.assertFalse(a[k])
        self.assertEqual(a["orders_sent"], 0)
        self.assertEqual(a["paper_fills"], 0)
        self.assertEqual(a["database_writes"], 0)

    def test_reject_wrong_repository_and_unknown_event(self):
        m = context()
        m["repository"] = "attacker/other"
        with self.assertRaisesRegex(ShadowInputError, "unexpected repository"):
            capture(m, "2026-11-06T18:00:00Z")
        m = context()
        m["event"] = "repository_dispatch"
        with self.assertRaisesRegex(ShadowInputError, "unsupported event"):
            capture(m, "2026-11-06T18:00:00Z")

    def test_reject_invalid_run_attempt_and_commit(self):
        m = context()
        m["run_attempt"] = True
        with self.assertRaisesRegex(ShadowInputError, "invalid run attempt"):
            capture(m, "2026-11-06T18:00:00Z")
        m = context()
        m["head_sha"] = "not-an-object-id"
        with self.assertRaisesRegex(ShadowInputError, "invalid commit SHA"):
            capture(m, "2026-11-06T18:00:00Z")

    def test_reject_unknown_fields_and_future_time(self):
        m = context()
        m["arbitrary_order"] = "buy"
        with self.assertRaisesRegex(ShadowInputError, "invalid GitHub run metadata"):
            capture(m, "2026-11-06T18:00:00Z")
        with self.assertRaisesRegex(ShadowInputError, "future capture time"):
            capture(context(), "2099-01-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
