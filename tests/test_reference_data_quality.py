"""Synthetic offline regression tests for non-trading reference-data gates."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
import math
from statistics import mean, pstdev

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


def synthetic_aged_crypto_divergence():
    """Artificial relative-return series: 1 early extreme, 11 later mild alerts.

    Prices have no relationship to actual market data. The later 11 ordinary
    alerts displace the early one from radar's last-ten presentation list.
    """
    gap_returns = [
        .001 * math.sin(i * .31) + .0012 * math.cos(i * .7)
        for i in range(230)
    ]
    gap_returns[45] = .15
    for j in range(11):
        idx = 75 + 13 * j
        reference = gap_returns[idx - 20:idx]
        gap_returns[idx] = mean(reference) + 3.2 * pstdev(reference)
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    records = []
    btc, eth = 100.0, 100.0
    for idx in range(len(gap_returns) + 1):
        if idx:
            btc *= 1.002
            eth *= 1.002 - gap_returns[idx - 1]
        day = (start + timedelta(days=idx)).isoformat()
        for code, price in (("BTC-USD", btc), ("ETH-USD", eth)):
            records.append({
                "instrument_code": code,
                "interval_code": "1d",
                "return_basis": "PRICE_ONLY",
                "observed_for": day,
                "ingested_at": "2026-10-18T00:00:00+00:00",
                "close_price": f"{price:.10f}",
            })
    return {
        "mode": "RETROSPECTIVE_RESEARCH_ONLY",
        "dataset_kind": "SYNTHETIC_OFFLINE_FIXTURE",
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "as_of": "2026-10-19T00:00:00+00:00",
        "records": records,
    }, (start + timedelta(days=46)).isoformat()


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

    def test_aged_extreme_not_lost_after_ten_later_display_alerts(self):
        snapshot, extreme_day = synthetic_aged_crypto_divergence()
        radar_result = opportunity_radar.analyze(snapshot)
        shown = radar_result["cross_market_btc_eth"]["recent_divergence_events"]
        self.assertEqual(len(shown), 10)
        self.assertNotIn(extreme_day, [event["observed_for"] for event in shown])
        # The DISPLAY may lose its old event; quality must not.
        q = quality.analyze_quality(snapshot, radar_result)
        extremes = q["extreme_relative_moves"]
        self.assertEqual(len(extremes), 1)
        self.assertEqual(extremes[0]["observed_for"], extreme_day)
        self.assertGreater(extremes[0]["absolute_zscore"], 8)
        self.assertEqual(extremes[0]["reference_bars"], 20)
        self.assertEqual(extremes[0]["status"], "SOURCE_REVALIDATION_REQUIRED")
        for item in q["series"]:
            self.assertEqual(item["quality_gate"], "BLOCK_RESEARCH_PROMOTION")
            self.assertIn("SOURCE_REVALIDATION_REQUIRED", item["warning_codes"])
        ledger = evidence_decision_ledger.make_ledger(radar_result, quality=q)
        self.assertTrue(all(x["educational_decision"] == "DATA_QUALITY_BLOCKED"
                            for x in ledger["questions"]))

    def test_presentation_list_cannot_clear_or_forge_extreme(self):
        snapshot, _ = synthetic_aged_crypto_divergence()
        radar_result = opportunity_radar.analyze(snapshot)
        q = quality.analyze_quality(snapshot, radar_result)
        modified = deepcopy(radar_result)
        modified["cross_market_btc_eth"]["recent_divergence_events"] = []
        self.assertEqual(q, quality.analyze_quality(snapshot, modified))
        modified["cross_market_btc_eth"]["recent_divergence_events"] = [{
            "observed_for": "2026-03-28T00:00:00+00:00",
            "absolute_zscore": 100000,
        }]
        self.assertEqual(q, quality.analyze_quality(snapshot, modified))

    def test_future_bars_cannot_change_an_older_divergence_quality_score(self):
        snapshot, extreme_day = synthetic_aged_crypto_divergence()
        complete = quality.analyze_quality(snapshot, opportunity_radar.analyze(snapshot))
        before = deepcopy(snapshot)
        before["records"] = [r for r in before["records"]
                             if r["observed_for"] <= "2026-05-19T00:00:00+00:00"]
        reduced = quality.analyze_quality(before, opportunity_radar.analyze(before))
        old_full = next(x for x in complete["extreme_relative_moves"]
                        if x["observed_for"] == extreme_day)
        old_reduced = next(x for x in reduced["extreme_relative_moves"]
                           if x["observed_for"] == extreme_day)
        self.assertEqual(old_full, old_reduced)

    def test_non_extreme_divergence_does_not_trigger_cross_market_block(self):
        snapshot = opportunity_demo_fixture.generate()
        btc_prices = {r["observed_for"]: r["close_price"] for r in snapshot["records"]
                      if r["instrument_code"] == "BTC-USD"}
        for row in snapshot["records"]:
            if row["instrument_code"] == "ETH-USD":
                row["close_price"] = btc_prices[row["observed_for"]]
        r = opportunity_radar.analyze(snapshot)
        r["cross_market_btc_eth"]["recent_divergence_events"] = [{
            "observed_for": snapshot["records"][121]["observed_for"],
            "absolute_zscore": 999.0,
        }]
        q = quality.analyze_quality(snapshot, r)
        self.assertEqual(q["extreme_relative_moves"], [])
        self.assertTrue(all("SOURCE_REVALIDATION_REQUIRED" not in x["warning_codes"]
                            for x in q["series"]))
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
