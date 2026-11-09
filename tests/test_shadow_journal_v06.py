"""Offline v0.6 audit-chain tests; missing sources never imply gains."""
from copy import deepcopy
import unittest

from scripts.shadow_decision_engine_v05 import evaluate, ShadowInputError
from scripts.shadow_journal_v06 import MODE, build_journal


def pair(decision_at, forward_at):
    decision = evaluate({
        "mode": "EDUCATIONAL_SHADOW_ONLY",
        "as_of_utc": decision_at,
        "series": {},
        "policy_version": "V05_FROZEN_001",
    })
    forward = {
        "mode": "EDUCATIONAL_FORWARD_REFERENCE_ONLY",
        "source_vintage": "SYNTHETIC_OFFLINE_FIXTURE",
        "as_of_utc": forward_at,
        "series": {},
        "fee_bps": "20",
        "slippage_bps": "10",
    }
    return {"decision": decision, "forward_reference": forward}


class ShadowJournalV06Tests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            pair("2025-11-06T18:00:00+00:00", "2025-12-02T18:00:00+00:00"),
            pair("2025-12-03T18:00:00+00:00", "2026-01-02T18:00:00+00:00"),
        ]

    def test_two_periods_are_audited_without_fictitious_returns(self):
        payload = {"mode": MODE, "entries": self.entries}
        report = build_journal(payload)
        self.assertEqual(report, build_journal(deepcopy(payload)))
        self.assertEqual(report["entries"], 2)
        self.assertEqual(report["receipts"][0]["previous_receipt_sha256"], "0" * 64)
        self.assertEqual(report["receipts"][1]["previous_receipt_sha256"],
                         report["receipts"][0]["receipt_sha256"])
        self.assertEqual(report["head_sha256"], report["receipts"][-1]["receipt_sha256"])
        self.assertEqual(report["model_status_counts"]["M1_GLOBAL_EQ"]
                         ["NOT_EVALUABLE_PREVIOUSLY_HOLD_CASH"], 2)
        self.assertFalse(report["investment_performance_proven"])
        self.assertFalse(report["independent_capture_attested"])
        self.assertIsNone(report["sharpe"])
        self.assertEqual(report["orders_sent"], 0)
        self.assertEqual(report["database_writes"], 0)

    def test_duplicate_decision_rejected(self):
        with self.assertRaisesRegex(ShadowInputError, "duplicate frozen"):
            build_journal({"mode": MODE, "entries": [self.entries[0], self.entries[0]]})

    def test_overlapping_or_backdated_decision_rejected(self):
        bad = deepcopy(self.entries)
        bad[1] = pair("2025-12-01T18:00:00+00:00", "2026-01-02T18:00:00+00:00")
        with self.assertRaisesRegex(ShadowInputError, "overlapping"):
            build_journal({"mode": MODE, "entries": bad})

    def test_tampered_decision_rejected_by_forward_gate(self):
        bad = deepcopy(self.entries)
        bad[0]["decision"]["model_decisions"]["M1_GLOBAL_EQ"]["status"] = "VIRTUAL_TARGET_ONLY"
        with self.assertRaisesRegex(ShadowInputError, "fingerprint mismatch"):
            build_journal({"mode": MODE, "entries": bad})

    def test_wrong_mode_and_empty_journal_rejected(self):
        with self.assertRaisesRegex(ShadowInputError, "only educational"):
            build_journal({"mode": "LIVE", "entries": self.entries})
        with self.assertRaisesRegex(ShadowInputError, "bounded"):
            build_journal({"mode": MODE, "entries": []})

    def test_forward_evaluation_must_follow_decision(self):
        bad = [pair("2026-01-05T18:00:00+00:00", "2025-12-02T18:00:00+00:00")]
        with self.assertRaisesRegex(ShadowInputError, "follow frozen decision"):
            build_journal({"mode": MODE, "entries": bad})


if __name__ == "__main__":
    unittest.main()
