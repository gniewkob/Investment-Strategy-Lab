"""v0.16 runnable research cycle, tested against repository's real archive."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.research_decision_pipeline_v16 import run_cycle, _manifest_from_archived_bundle
from scripts.shadow_decision_engine_v05 import ShadowInputError, EQUITY
from tests.test_research_decision_controller_v15 import pair
from tests.test_shadow_decision_engine_v05 import sample


ARCHIVE = (Path(__file__).resolve().parents[1] /
           "evidence/shadow/v09/checkpoint-bundle-run-42305280062.json")


class ResearchCycleV16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads(ARCHIVE.read_text())

    def test_real_archived_evidence_runs_to_three_holds_without_fabrication(self):
        out = run_cycle(archived_bundle=self.bundle)
        self.assertEqual(out["status"], "HOLD_CASH_SOURCE_OR_CONFIRMATION_BLOCKED")
        self.assertEqual(out["input_kind"], "ARCHIVED_READ_ONLY_CAPTURE_V09")
        self.assertEqual(set(out["model_decisions"]), {
            "M1_GLOBAL_EQ", "M2_DIVERSIFIED", "M3_TACTICAL"})
        self.assertTrue(all(m["status"] == "HOLD_CASH"
                            for m in out["model_decisions"].values()))
        self.assertEqual(out["paper_candidates"], [])
        self.assertEqual(len(out["missing_or_blocked_sources"]), 3)
        self.assertEqual(out["provenance"]["archived_run_id"], 42305280062)
        self.assertFalse(out["provenance"]["archived_data_is_qualified_model_series"])
        self.assertEqual(out["orders_sent"], 0)
        self.assertEqual(out["financial_operations"], 0)

    def test_repeated_archive_cycle_is_deterministic(self):
        self.assertEqual(run_cycle(archived_bundle=self.bundle),
                         run_cycle(archived_bundle=deepcopy(self.bundle)))

    def test_archive_mutation_rejected(self):
        bad = deepcopy(self.bundle)
        bad["capture"]["decision"]["as_of_utc"] = "1999-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(ShadowInputError, "capture fingerprint"):
            run_cycle(archived_bundle=bad)

    def test_archive_capture_mutation_rejected(self):
        bad = deepcopy(self.bundle)
        bad["capture"]["captured_at_utc"] = "1999-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(ShadowInputError, "capture fingerprint"):
            run_cycle(archived_bundle=bad)

    def test_archive_cross_document_mismatch_rejected(self):
        bad = deepcopy(self.bundle)
        bad["checkpoint"]["decision_sha256"] = "0" * 64
        with self.assertRaisesRegex(ShadowInputError, "checkpoint"):
            run_cycle(archived_bundle=bad)

    def test_archive_unexpected_order_activity_rejected(self):
        bad = deepcopy(self.bundle)
        bad["checkpoint"]["orders_sent"] = 1
        with self.assertRaisesRegex(ShadowInputError, "financial operation"):
            run_cycle(archived_bundle=bad)

    def test_archived_run_head_mismatch_rejected(self):
        bad = deepcopy(self.bundle)
        bad["run"]["head_sha"] = "a" * 40
        with self.assertRaisesRegex(ShadowInputError, "run context"):
            run_cycle(archived_bundle=bad)

    def test_current_empty_manifest_is_runnable_and_holds(self):
        current = sample(include=())
        out = run_cycle(current=current)
        self.assertEqual(out["status"], "HOLD_CASH_SOURCE_OR_CONFIRMATION_BLOCKED")
        self.assertEqual(out["provenance"]["archive_status"], None)

    def test_qualified_synthetic_m1_can_be_candidate_without_paper_execution(self):
        out = run_cycle(current=sample(include=(EQUITY,)))
        self.assertEqual(out["paper_candidates"], ["M1_GLOBAL_EQ"])
        self.assertEqual(out["model_decisions"]["M3_TACTICAL"]["status"], "HOLD_CASH")
        self.assertEqual(out["paper_fills"], 0)
        self.assertFalse(out["real_order_authorized"])

    def test_two_snapshot_M3_requires_full_qualified_history(self):
        current, previous = pair()
        out = run_cycle(current=current, previous=previous)
        self.assertEqual(out["paper_candidates"], [
            "M1_GLOBAL_EQ", "M2_DIVERSIFIED", "M3_TACTICAL"])
        self.assertFalse(out["performance_or_alpha_proven"])
        self.assertFalse(out["historical_point_in_time_certified"])

    def test_rejects_ambiguous_mode_and_prior_with_archive(self):
        with self.assertRaisesRegex(ShadowInputError, "exactly one"):
            run_cycle()
        with self.assertRaisesRegex(ShadowInputError, "exactly one"):
            run_cycle(current=sample(), archived_bundle=self.bundle)
        with self.assertRaisesRegex(ShadowInputError, "cannot take"):
            run_cycle(archived_bundle=self.bundle, previous=sample())

    def test_ineligible_gold_cannot_become_candidate(self):
        current = sample()
        current["series"]["GOLD_TR_PLN"]["return_basis"] = "PRICE_ONLY"
        out = run_cycle(current=current)
        self.assertEqual(out["paper_candidates"], ["M1_GLOBAL_EQ"])
        self.assertEqual(out["model_decisions"]["M2_DIVERSIFIED"]["status"], "HOLD_CASH")

    def test_input_documents_not_mutated(self):
        current, previous = pair()
        old = deepcopy((current, previous))
        run_cycle(current=current, previous=previous)
        self.assertEqual((current, previous), old)


if __name__ == "__main__":
    unittest.main()
