"""Synthetic-only v0.20 diagnostic tests; no private Vanguard NAV exposed."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import unittest

from scripts.conditional_m1_nav_diagnostic_v20 import evaluate_nav_reference
from scripts.reference_archive_calendar_v04 import _digest
from scripts.vanguard_nav_intake_bundle_v04 import prepare
from tests.test_vanguard_nav_intake_bundle_v04 import fixture, official_fake_fx

NOW = datetime(2026,11,7,20,tzinfo=timezone.utc)


def sample_receipt():
    original, nbp = fixture()
    return prepare(original, nbp, "2021-11", "2026-10",
                   fetch=official_fake_fx, clock=lambda:NOW)


def seal(receipt):
    receipt["evidence_sha256"] = _digest({
        k: v for k, v in receipt.items() if k != "evidence_sha256"})
    return receipt


class ConditionalM1NAVResearchTests(unittest.TestCase):
    def test_real_contract_synthetic_60_months_vs_cash_and_receipt(self):
        doc=sample_receipt()
        r=evaluate_nav_reference(doc)
        self.assertEqual(r["periods"],60)
        self.assertEqual(r["contributions_pln"],"6000.00")
        self.assertEqual(r["cash_reference_final_pln"],"6000.00")
        self.assertEqual(len(r["timeline"]),60)
        self.assertEqual(r["status"],
                         "CONDITIONAL_HISTORICAL_NAV_REFERENCE_NOT_INVESTABLE_BACKTEST")
        self.assertEqual(r["source_evidence_sha256"],doc["evidence_sha256"])
        self.assertFalse(r["historical_point_in_time_certified"])
        self.assertFalse(r["m1_qualified_model_backtest"])
        self.assertFalse(r["statistical_edge_or_alpha_proven"])
        self.assertEqual(r["financial_operations"],0)
        self.assertEqual(r["paper_fills"],0)

    def test_zero_cost_gives_gross_and_more_than_fee_scenario(self):
        doc=sample_receipt()
        no_fee=evaluate_nav_reference(doc,fee_bps="0",slippage_bps="0")
        expensive=evaluate_nav_reference(doc,fee_bps="100",slippage_bps="100")
        self.assertEqual(no_fee["nav_reference_gross_final_pln"],
                         no_fee["nav_reference_net_final_pln"])
        self.assertGreater(Decimal(no_fee["nav_reference_net_final_pln"]),
                           Decimal(expensive["nav_reference_net_final_pln"]))
        self.assertEqual(no_fee["hypothetical_cumulative_frictions_pln"],"0.00")

    def test_repeatable_and_immutable_input(self):
        doc=sample_receipt()
        old=deepcopy(doc)
        self.assertEqual(evaluate_nav_reference(doc),
                         evaluate_nav_reference(deepcopy(doc)))
        self.assertEqual(doc,old)

    def test_tamper_raw_pln_detected(self):
        doc=sample_receipt()
        doc["monthly"][4]["nav_pln_reference"]="12345"
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            evaluate_nav_reference(doc)

    def test_cross_field_pln_mismatch_even_with_resealed_receipt(self):
        doc=sample_receipt()
        doc["monthly"][4]["nav_pln_reference"]="12345"
        seal(doc)
        with self.assertRaisesRegex(ValueError,"multiplication mismatch"):
            evaluate_nav_reference(doc)

    def test_missing_month_and_duplicate_fail_closed(self):
        doc=sample_receipt()
        doc["monthly"].pop(5)
        seal(doc)
        with self.assertRaisesRegex(ValueError,"exact 60-month"):
            evaluate_nav_reference(doc)
        doc=sample_receipt()
        doc["monthly"][10]["month"]=doc["monthly"][9]["month"]
        seal(doc)
        with self.assertRaisesRegex(ValueError,"month gap or duplicate"):
            evaluate_nav_reference(doc)

    def test_source_is_not_qualified_total_return_even_if_receipt_changes(self):
        doc=sample_receipt()
        doc["usable_as_GLOBAL_EQUITY_TR_PLN"]=True
        seal(doc)
        with self.assertRaisesRegex(ValueError,"unqualified NAV"):
            evaluate_nav_reference(doc)
        doc=sample_receipt()
        doc["historical_pit_certified"]=True
        seal(doc)
        with self.assertRaisesRegex(ValueError,"unqualified NAV"):
            evaluate_nav_reference(doc)

    def test_unmatched_fx_not_accepted(self):
        doc=sample_receipt()
        doc["missing_exact_day_fx"]=[{"month":"2022-01"}]
        seal(doc)
        with self.assertRaisesRegex(ValueError,"unqualified NAV"):
            evaluate_nav_reference(doc)

    def test_invalid_costs_rejected(self):
        doc=sample_receipt()
        for val in ("-1","201","nan","Infinity"):
            with self.subTest(val=val),self.assertRaises(ValueError):
                evaluate_nav_reference(doc,fee_bps=val)

    def test_wrong_input_status_rejected(self):
        doc=sample_receipt()
        doc["status"]="BLOCKED_NEEDS_EXACT_DAY_NBP_FX"
        seal(doc)
        with self.assertRaisesRegex(ValueError,"unqualified NAV"):
            evaluate_nav_reference(doc)


if __name__=="__main__":
    unittest.main()
