"""Synthetic offline regression tests for non-trading reference-data gates."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from scripts import (
    opportunity_demo_fixture,
    opportunity_radar,
    opportunity_research_pipeline,
    reference_data_quality as quality,
    evidence_decision_ledger,
)

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def sample_data():
    records = []
    for code, length in (("BRENT_EIA_USD_BBL", 100),
                         ("WTI_EIA_USD_BBL", 65)):
        price = 80.0
        for index in range(length):
            price *= 1.002 if index % 2 else 0.998
            records.append({
                "instrument_code": code, "interval_code": "1d",
                "return_basis": "PRICE_ONLY",
                "observed_for": (START + timedelta(days=index)).isoformat(),
                "ingested_at": "2026-04-15T00:00:00+00:00",
                "close_price": f"{price:.7f}",
            })
    return {
        "mode": "RETROSPECTIVE_RESEARCH_ONLY",
        "dataset_kind": "SYNTHETIC_OFFLINE_FIXTURE",
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "as_of": "2026-04-16T00:00:00+00:00",
        "records": records,
    }


class ReferenceDataQualityTests(unittest.TestCase):
    def test_stale_wti_and_peer_calendar_gap_block_research_promotion(self):
        snapshot = sample_data()
        result = opportunity_research_pipeline.run_pipeline(snapshot)
        series = {x["instrument_code"]: x for x in result["quality"]["series"]}
        self.assertIn("STALE_DATA", series["WTI_EIA_USD_BBL"]["warning_codes"])
        self.assertIn("PEER_COVERAGE_GAP", series["WTI_EIA_USD_BBL"]["warning_codes"])
        self.assertEqual(series["WTI_EIA_USD_BBL"]["quality_gate"],
                         "BLOCK_RESEARCH_PROMOTION")
        self.assertEqual(result["quality"]["peer_coverage"][0]["missing_after_last_observation"], 35)
        self.assertEqual(result["quality"]["peer_coverage"][0]["missing_matched_reference_dates"], 35)
        decisions = {x["instrument_code"]: x for x in result["ledger"]["questions"]}
        self.assertEqual(decisions["WTI_EIA_USD_BBL"]["educational_decision"],
                         "DATA_QUALITY_BLOCKED")
        self.assertTrue(result["manifest"]["data_quality_blocked_series"] >= 1)
        self.assertEqual(result["manifest"]["real_orders"], 0)
        self.assertEqual(result["manifest"]["database_writes"], 0)

    def test_stale_threshold_is_interval_specific(self):
        snapshot = sample_data()
        baseline = opportunity_radar.analyze(snapshot)
        q = quality.analyze_quality(snapshot, baseline)
        brent = next(x for x in q["series"] if x["instrument_code"] == "BRENT_EIA_USD_BBL")
        self.assertEqual(brent["age_calendar_days"], 6)
        self.assertEqual(brent["freshness_threshold_days"], 10)
        self.assertEqual(brent["quality_gate"], "REVIEW_ONLY")

    def test_relative_crypto_extreme_requires_independent_price_verification(self):
        snapshot = opportunity_demo_fixture.generate()
        r = opportunity_radar.analyze(snapshot)
        stamp = snapshot["records"][121]["observed_for"]
        r["cross_market_btc_eth"]["recent_divergence_events"] = [
            {"observed_for": stamp, "absolute_zscore": 16.266,
             "signal": "USD_CRYPTO_RELATIVE_MOVE_DIVERGENCE",
             "hypothesis_status": "INVESTIGATE_ONLY"}
        ]
        q = quality.analyze_quality(snapshot, r)
        self.assertEqual(len(q["extreme_relative_moves"]), 1)
        self.assertEqual(q["extreme_relative_moves"][0]["status"],
                         "SOURCE_REVALIDATION_REQUIRED")
        for item in q["series"]:
            self.assertIn("SOURCE_REVALIDATION_REQUIRED", item["warning_codes"])
            self.assertEqual(item["quality_gate"], "BLOCK_RESEARCH_PROMOTION")
        ledger = evidence_decision_ledger.make_ledger(
            r, quality=q)
        self.assertTrue(all(x["educational_decision"] == "DATA_QUALITY_BLOCKED"
                            for x in ledger["questions"]))

    def test_non_extreme_divergence_does_not_trigger_cross_market_block(self):
        snapshot = opportunity_demo_fixture.generate()
        r = opportunity_radar.analyze(snapshot)
        r["cross_market_btc_eth"]["recent_divergence_events"] = []
        q = quality.analyze_quality(snapshot, r)
        self.assertEqual(q["extreme_relative_moves"], [])
        self.assertEqual(q["source_vintage"], "UNVERIFIED_HISTORICAL_PUBLICATION")
        self.assertFalse(q["historical_release_dates_verified"])

    def test_changed_fingerprint_or_forged_quality_fails_closed(self):
        snapshot = sample_data()
        r = opportunity_radar.analyze(snapshot)
        changed = deepcopy(snapshot)
        changed["records"][0]["close_price"] = "123"
        with self.assertRaisesRegex(ValueError, "matching"):
            quality.analyze_quality(changed, r)
        q = quality.analyze_quality(snapshot, r)
        q["source_radar_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            evidence_decision_ledger.make_ledger(r, quality=q)

    def test_absent_quality_row_rejected_not_silently_approved(self):
        snapshot = sample_data()
        r = opportunity_radar.analyze(snapshot)
        q = quality.analyze_quality(snapshot, r)
        q["series"].pop()
        with self.assertRaisesRegex(ValueError, "missing"):
            evidence_decision_ledger.make_ledger(r, quality=q)

    def test_pipeline_is_reproducible_read_only_and_has_quality_artifact(self):
        result1 = opportunity_research_pipeline.run_pipeline(sample_data())
        result2 = opportunity_research_pipeline.run_pipeline(sample_data())
        self.assertEqual(result1, result2)
        self.assertIs(result1["quality"]["prediction_or_trading_authorized"], False)
        self.assertEqual(result1["quality"]["database_writes"], 0)
        self.assertEqual(result1["ledger"]["portfolio_reallocations"], 0)
        self.assertTrue(all(x["decision"] == "HOLD_NO_CHANGE"
                            for x in result1["ledger"]["paper_portfolio_decisions"]))


if __name__ == "__main__":
    unittest.main()
