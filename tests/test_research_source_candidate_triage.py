"""Offline research candidate taxonomy tests, no prices or trading."""
from dataclasses import replace
import unittest

from src.isl_v2.research_source_candidate_triage import (
    RESEARCH_CANDIDATES, CandidateDescription, candidate_screen,
    research_candidate_inventory,
)


class SourceTypeTriageTests(unittest.TestCase):
    def test_four_research_candidates_are_not_approved_sources(self):
        summary = research_candidate_inventory()
        self.assertEqual(len(summary["candidates"]), 4)
        self.assertEqual(summary["reviewed_source_pin_count"], 0)
        self.assertEqual(summary["qualified_model_series"], [])
        self.assertFalse(summary["candidate_source_admitted"])
        self.assertEqual(summary["model_state"], "HOLD_CASH")
        self.assertEqual(summary["financial_operations"], 0)

    def test_tbsp_semantic_match_still_has_three_evidence_blockers(self):
        result = candidate_screen(RESEARCH_CANDIDATES["TBSP_INDEX"])
        self.assertTrue(result["semantic_match"])
        self.assertIn("LICENCE_SCOPE_UNVERIFIED", result["research_blockers"])
        self.assertIn("SOURCE_BYTES_NOT_AUTHENTICATED", result["research_blockers"])
        self.assertIn("HISTORICAL_PIT_UNVERIFIED", result["research_blockers"])
        self.assertFalse(result["candidate_source_admitted"])

    def test_accumulating_fund_nav_cannot_masquerade_as_pln_tr_index(self):
        result = candidate_screen(RESEARCH_CANDIDATES["VANGUARD_ALL_WORLD_ACC"])
        self.assertFalse(result["semantic_match"])
        self.assertIn("NOT_TOTAL_RETURN_INDEX", result["research_blockers"])
        self.assertIn("CURRENCY_TRANSFORMATION_REQUIRED", result["research_blockers"])

    def test_nbp_spot_cannot_masquerade_as_gold_total_return(self):
        result = candidate_screen(RESEARCH_CANDIDATES["NBP_GOLD_PRICE"])
        self.assertFalse(result["semantic_match"])
        self.assertIn("NOT_TOTAL_RETURN_INDEX", result["research_blockers"])

    def test_wig_total_return_is_not_global_equity(self):
        result = candidate_screen(RESEARCH_CANDIDATES["GPW_WIG"])
        self.assertFalse(result["semantic_match"])
        self.assertIn("MANDATE_EXPOSURE_MISMATCH", result["research_blockers"])
        self.assertNotIn("NOT_TOTAL_RETURN_INDEX", result["research_blockers"])

    def test_claimed_licence_and_pit_flags_never_grant_model_admission(self):
        claimed = replace(
            RESEARCH_CANDIDATES["TBSP_INDEX"],
            license_reviewed=True,
            source_bytes_authenticated=True,
            vintage_publication_verified=True,
        )
        result = candidate_screen(claimed)
        self.assertEqual(result["research_blockers"], [])
        self.assertTrue(result["semantic_match"])
        self.assertFalse(result["authenticated_source_manifest_present"])
        self.assertFalse(result["candidate_source_admitted"])
        self.assertFalse(result["historical_pit_certified"])
        self.assertEqual(result["qualified_model_series"], [])
        self.assertEqual(result["financial_operations"], 0)

    def test_currency_cannot_be_papered_over_with_tr_concept(self):
        candidate = replace(
            RESEARCH_CANDIDATES["VANGUARD_ALL_WORLD_ACC"],
            value_concept="TOTAL_RETURN_INDEX",
        )
        result = candidate_screen(candidate)
        self.assertIn("CURRENCY_TRANSFORMATION_REQUIRED", result["research_blockers"])
        self.assertFalse(result["semantic_match"])

    def test_unknown_model_slot_is_blocked(self):
        candidate = replace(RESEARCH_CANDIDATES["TBSP_INDEX"], proposed_slot="NEW_ASSET")
        with self.assertRaisesRegex(ValueError, "UNKNOWN_MODEL_SLOT"):
            candidate_screen(candidate)

    def test_untyped_candidate_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "INVALID_CANDIDATE"):
            candidate_screen({"proposed_slot": "BONDS_TR_PLN"})

    def test_candidate_descriptions_are_immutable(self):
        with self.assertRaises((AttributeError, TypeError)):
            RESEARCH_CANDIDATES["TBSP_INDEX"].currency = "USD"

    def test_all_candidates_have_primary_https_information_pages(self):
        self.assertTrue(all(
            c.official_information_page.startswith("https://")
            for c in RESEARCH_CANDIDATES.values()
        ))

    def test_taxonomy_has_no_raw_price_or_trade_attributes(self):
        summary = research_candidate_inventory()
        for entry in summary["candidates"]:
            self.assertNotIn("price_value", entry)
            self.assertNotIn("paper_target", entry)
            self.assertNotIn("order", entry)
            self.assertFalse(entry["candidate_source_admitted"])


if __name__ == "__main__":
    unittest.main()
