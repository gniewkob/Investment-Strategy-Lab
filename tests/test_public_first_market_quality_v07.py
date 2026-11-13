"""Cross-source research quality: offline synthetic inputs, no assets/actions."""
import copy
from datetime import datetime,timezone
import json
import unittest

from scripts.public_first_market_quality_v07 import (
    integrate_market_quality, MarketQualityBlocked, SCHEMA,
)
from scripts.mf_bond_turnover_metrics_v07 import analyze_mf_original
from scripts.public_first_multisource_macro_evidence_v05 import (
    evaluate_combined_sources,
)
from scripts.knf_original_unit_history_research_v06 import evaluate_sample
from tests.test_mf_bond_turnover_metrics_v07 import synth
from tests.test_knf_original_unit_history_research_v06 import sample, raw
from tests.test_public_first_multisource_macro_evidence_v05 import inputs

NOW=datetime(2026,11,13,tzinfo=timezone.utc)


def synthetic_three_sources():
    mf=analyze_mf_original(synth(),completed_at=NOW)
    a,b,c,d=sample()
    from datetime import date
    business=[date(2026,9,day) for day in range(1,31)
              if date(2026,9,day).weekday()<5]
    assert len(business)==22
    template=c["content"][0]
    c["content"]=[{**template,"date":day.isoformat(),
                   "valuation":100.0 + ix*0.02}
                  for ix,day in enumerate(business)]
    c["page"]["totalElements"]=22
    b["content"][0]["subfundId"]=9999  # intentionally unrelated KID
    nav=evaluate_sample(raw(a),raw(b),raw(c),None,at=NOW)
    n,h,y=inputs()
    macro=evaluate_combined_sources(n,h,y,completed_at=NOW)
    return mf,nav,macro


class CrossMarketQualityTests(unittest.TestCase):
    def test_reconciled_different_grains_never_combine_as_returns(self):
        out=integrate_market_quality(*synthetic_three_sources())
        self.assertEqual(out["schema"],SCHEMA)
        self.assertEqual(out["aligned_observation_month"],"2026-09")
        self.assertEqual(out["source_quality_gate"]["mf_complete_history_months"],202)
        self.assertEqual(out["source_quality_gate"]["uknf_same_primary_class_nav_days"],22)
        self.assertFalse(out["source_quality_gate"]["uknf_kid_exact_asof_match"])
        self.assertFalse(out["historical_first_publication_vintages_proven"])
        self.assertFalse(out["cross_source_return_correlation_calculated"])
        self.assertFalse(out["cross_source_causal_inference_permitted"])
        self.assertEqual(out["model_trading_qualification"],[])
        self.assertEqual(out["m1_m2_m3"],"INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual(out["orders_sent"],0)
        self.assertEqual(out["financial_operations"],0)
        self.assertEqual(out["database_writes"],0)
        self.assertRegex(out["receipt_sha256"],"^[a-f0-9]{64}$")
    def test_four_original_source_fingerprints_present(self):
        out=integrate_market_quality(*synthetic_three_sources())
        self.assertEqual(len(out["original_source_payload_fingerprints"]),4)
        self.assertTrue(all(len(x)==64 for x in
                            out["original_source_payload_fingerprints"].values()))
    def test_no_false_kid_cost_attribution(self):
        mf,nav,macro=synthetic_three_sources()
        nav["kid_stated_costs_rates_not_actual_fees"]["maxEntryFeeRate"]="0.99"
        with self.assertRaisesRegex(MarketQualityBlocked,"KID_ANOTHER_FUND"):
            integrate_market_quality(mf,nav,macro)
    def test_no_source_first_published_pit_promotion(self):
        mf,nav,macro=synthetic_three_sources()
        mf["historical_pit_first_publication_certified"]=True
        with self.assertRaisesRegex(MarketQualityBlocked,"MF_ORIGINAL"):
            integrate_market_quality(mf,nav,macro)
    def test_wrong_fund_currency_blocks(self):
        mf,nav,macro=synthetic_three_sources()
        nav["selected_currency"]="USD"
        with self.assertRaisesRegex(MarketQualityBlocked,"NAV_ORIGINAL"):
            integrate_market_quality(mf,nav,macro)
    def test_tampered_macro_math_blocks(self):
        mf,nav,macro=synthetic_three_sources()
        macro["arithmetic_yield_minus_trailing_inflation_pp"]="10.0000"
        with self.assertRaisesRegex(MarketQualityBlocked,"ARITHMETIC"):
            integrate_market_quality(mf,nav,macro)
    def test_invalid_source_hash_blocks(self):
        mf,nav,macro=synthetic_three_sources()
        nav["source_documents"]["history_sha256"]="not-a-sha"
        with self.assertRaisesRegex(MarketQualityBlocked,"FINGERPRINT"):
            integrate_market_quality(mf,nav,macro)
    def test_non_utc_and_naive_retrieval_clock_blocks(self):
        mf,nav,macro=synthetic_three_sources()
        mf["source_observed_at_utc"]="2026-11-13T00:00:00"
        with self.assertRaisesRegex(MarketQualityBlocked,"CLOCK_NAIVE"):
            integrate_market_quality(mf,nav,macro)
    def test_gross_turnover_not_fund_nav_or_trade_signal(self):
        mf,nav,macro=synthetic_three_sources()
        out=integrate_market_quality(mf,nav,macro)
        self.assertEqual(out["context_only"]["mf_latest_total_mln_pln"],"3140385.25")
        self.assertFalse(out["licensed_bond_index_benchmarks_admitted"])
        self.assertEqual(out["portfolio_positions_queried"],0)
        self.assertEqual(out["scheduled_sources_created"],0)
    def test_any_financial_side_effect_blocks(self):
        mf,nav,macro=synthetic_three_sources()
        nav["financial_operations"]=1
        with self.assertRaisesRegex(MarketQualityBlocked,"FINANCIAL_OPERATION"):
            integrate_market_quality(mf,nav,macro)
