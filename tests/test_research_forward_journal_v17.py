"""v0.17 multi-cycle forward journal, source-gated and non-executable."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.research_decision_pipeline_v16 import _manifest_from_archived_bundle
from scripts.research_forward_journal_v17 import run_journal
from scripts.shadow_decision_engine_v05 import ASSETS, EQUITY, ShadowInputError, evaluate
from tests.test_research_decision_controller_v15 import pair
from tests.test_shadow_forward_evaluation_v05 import (
    ASOF, future_reference, make_months, source,
)
from tests.test_shadow_decision_engine_v05 import sample

MODE = "EDUCATIONAL_PROSPECTIVE_RESEARCH_ONLY"
ARCHIVE = (Path(__file__).resolve().parents[1] /
           "evidence/shadow/v09/checkpoint-bundle-run-42305280062.json")


def journal(*entries):
    return {"mode": MODE, "cycles": list(entries)}


def entry(current, forward=None):
    return {"current": current, "forward_reference": forward}


def usable_fixture():
    # Entirely synthetic historical prices, not a true PIT source.
    src = {}
    for code in ASSETS:
        value = source(code, rows=make_months(48))
        value["retrieved_at"] = ASOF
        src[code] = value
    current = {
        "mode": "EDUCATIONAL_SHADOW_ONLY",
        "as_of_utc": ASOF,
        "policy_version": "V05_FROZEN_001",
        "series": src,
    }
    prior = deepcopy(current)
    prior["as_of_utc"] = "2025-10-06T18:00:00+00:00"
    for value in prior["series"].values():
        value["observations"].pop()
        value["retrieved_at"] = prior["as_of_utc"]
    return prior, current, future_reference(evaluate(current))


class ForwardResearchJournalV17Tests(unittest.TestCase):
    def test_real_archive_can_be_replayed_with_no_fabricated_performance(self):
        bundle = json.loads(ARCHIVE.read_text())
        manifest, _ = _manifest_from_archived_bundle(bundle)
        out = run_journal(journal(entry(manifest)))
        self.assertEqual(out["status"], "NOT_RUN_NO_EVALUABLE_FORWARD_MARKET_DATA")
        self.assertEqual(out["cycles_completed"], 1)
        self.assertEqual(set(out["forward_evaluable_periods_per_model"].values()), {0})
        self.assertEqual(out["receipts"][0]["paper_candidates"], [])
        self.assertEqual(out["financial_operations"], 0)
        self.assertEqual(out["market_data_acceptance"],
                         "BLOCKED_INDEPENDENT_SOURCE_AND_PIT_EVIDENCE")

    def test_multiple_consecutive_raw_snapshots_produce_chained_receipts(self):
        current, previous = pair()
        result = run_journal(journal(entry(previous), entry(current)))
        self.assertEqual(result["cycles_completed"], 2)
        self.assertEqual(result["distinct_decision_months"], 2)
        self.assertEqual(result["receipts"][1]["previous_receipt_sha256"],
                         result["receipts"][0]["receipt_sha256"])
        self.assertEqual(result["receipts"][1]["paper_candidates"], list(
            ("M1_GLOBAL_EQ", "M2_DIVERSIFIED", "M3_TACTICAL")))
        self.assertEqual(set(result["forward_evaluable_periods_per_model"].values()), {0})
        self.assertFalse(result["profitability_or_alpha_proven"])

    def test_synthetic_forward_counts_only_previously_confirmed_candidates(self):
        previous, current, forward = usable_fixture()
        result = run_journal(journal(entry(previous), entry(current, forward)))
        self.assertEqual(result["status"], "SYNTHETIC_ONLY_NO_MARKET_ACCEPTANCE")
        self.assertEqual(result["forward_evaluable_periods_per_model"], {
            "M1_GLOBAL_EQ": 1, "M2_DIVERSIFIED": 1, "M3_TACTICAL": 1,
        })
        self.assertTrue(all(
            item["status"] == "ONE_FORWARD_REFERENCE_PERIOD_RESEARCH_ONLY"
            for item in result["receipts"][1]["forward_models"].values()))
        self.assertEqual(result["financial_operations"], 0)
        self.assertEqual(result["paper_fills"], 0)

    def test_unconfirmed_M3_has_no_forward_attribution_even_if_v05_has_target(self):
        _, current, forward = usable_fixture()
        result = run_journal(journal(entry(current, forward)))
        self.assertEqual(result["forward_evaluable_periods_per_model"], {
            "M1_GLOBAL_EQ": 1, "M2_DIVERSIFIED": 1, "M3_TACTICAL": 0})
        self.assertEqual(result["receipts"][0]["forward_models"]["M3_TACTICAL"],
                         {"status": "NOT_EVALUABLE_CONTROLLER_HOLD",
                          "hypothetical_net_return": None})

    def test_missing_data_remains_hold_cash_no_forward(self):
        result = run_journal(journal(entry(sample(include=()))))
        self.assertEqual(result["status"], "NOT_RUN_NO_EVALUABLE_FORWARD_MARKET_DATA")
        self.assertEqual(result["receipts"][0]["model_statuses"]["M1_GLOBAL_EQ"],
                         "HOLD_CASH")

    def test_determinism_and_no_mutation(self):
        current, previous = pair()
        source_doc = journal(entry(previous), entry(current))
        copy = deepcopy(source_doc)
        self.assertEqual(run_journal(source_doc), run_journal(copy))
        self.assertEqual(source_doc, copy)

    def test_wrong_mode_and_bad_structures_rejected(self):
        for doc in ({}, {"mode": "LIVE_TRADING", "cycles": []},
                    {"mode": MODE, "cycles": []},
                    {"mode": MODE, "cycles": [{}]}):
            with self.subTest(doc=doc), self.assertRaises(ShadowInputError):
                run_journal(doc)

    def test_duplicate_or_reverse_chronology_rejected(self):
        current, previous = pair()
        with self.assertRaisesRegex(ShadowInputError, "strictly increase"):
            run_journal(journal(entry(current), entry(previous)))
        with self.assertRaisesRegex(ShadowInputError, "strictly increase"):
            run_journal(journal(entry(current), entry(current)))

    def test_invalid_forward_costs_are_rejected(self):
        _, current, forward = usable_fixture()
        forward["fee_bps"] = "-10"
        with self.assertRaisesRegex(ShadowInputError, "outside 0"):
            run_journal(journal(entry(current, forward)))

    def test_forward_with_future_publication_is_rejected(self):
        _, current, forward = usable_fixture()
        forward["series"][EQUITY]["first_usable_at"] = "2025-12-03T00:00:00+00:00"
        with self.assertRaisesRegex(ShadowInputError, "look-ahead"):
            run_journal(journal(entry(current, forward)))

    def test_real_market_claim_never_certified_by_self_declared_manifest(self):
        _, current, forward = usable_fixture()
        forward["source_vintage"] = "FUTURE_PROSPECTIVE_RESEARCH"
        result = run_journal(journal(entry(current, forward)))
        self.assertEqual(result["status"],
                         "FORWARD_REFERENCE_OBSERVED_NOT_INDEPENDENTLY_ATTESTED")
        self.assertEqual(result["market_data_acceptance"],
                         "BLOCKED_INDEPENDENT_SOURCE_AND_PIT_EVIDENCE")
        self.assertFalse(result["profitability_or_alpha_proven"])


if __name__ == "__main__":
    unittest.main()
