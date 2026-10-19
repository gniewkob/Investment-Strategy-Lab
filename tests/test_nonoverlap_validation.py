"""Offline guards for independent-window opportunity research diagnostics."""
from datetime import datetime
from copy import deepcopy
import unittest

from scripts import (
    nonoverlap_validation as nv,
    opportunity_demo_fixture,
    opportunity_radar,
    opportunity_research_pipeline,
)


class NonOverlapResearchTests(unittest.TestCase):
    def sample(self):
        return opportunity_demo_fixture.generate()

    def evaluate(self, obj):
        first = opportunity_radar.analyze(obj)
        return nv.analyze_validation(obj, first)

    def test_synthetic_pipeline_contains_paired_research_diagnostic(self):
        p = self.sample()
        out = opportunity_research_pipeline.run_pipeline(p)
        report = out["robustness"]
        self.assertEqual(report["status"], "NONOVERLAPPING_RESEARCH_DIAGNOSTIC_ONLY")
        self.assertEqual(report["series_checked"], 2)
        self.assertEqual(report["source_radar_sha256"], out["radar"]["data_sha256"])
        self.assertEqual(out["manifest"]["nonoverlapping_event_count"],
                         report["total_nonoverlapping_events"])
        self.assertEqual(out["manifest"]["excluded_overlapping_events"],
                         report["total_excluded_overlaps"])
        self.assertEqual(out["manifest"]["hypothetical_allocation_changes"], 0)
        self.assertFalse(report["causal_predictive_advantage_established"])
        self.assertFalse(report["investable_return_benchmark_verified"])
        self.assertFalse(report["independent_publication_vintages_verified"])
        self.assertFalse(report["scheduled"])

    def test_repeated_runs_are_deterministic(self):
        p = self.sample()
        self.assertEqual(self.evaluate(p), self.evaluate(p))

    def test_nonoverlapping_candidate_windows_are_separated(self):
        r = self.evaluate(self.sample())
        for series in r["series"]:
            events = series["events"]
            dates = [datetime.fromisoformat(e["observed_for"]) for e in events]
            assert len(dates) <= 12
            for a, b in zip(dates, dates[1:]):
                self.assertGreaterEqual((b-a).days, nv.radar.HORIZON_BARS)

    def test_investigation_cannot_become_portfolio_instruction(self):
        r = self.evaluate(self.sample())
        self.assertEqual(r["virtual_portfolio_changes"], 0)
        self.assertEqual(r["real_orders"], 0)
        self.assertEqual(r["database_writes"], 0)
        for series in r["series"]:
            self.assertIs(series["allocation_change_authorized"], False)
            self.assertIn(series["sample_gate"],
                          ("EXPLORATORY_SAMPLE_ONLY",
                           "INSUFFICIENT_NONOVERLAPPING_EVIDENCE"))

    def test_naive_same_date_hits_bounded_by_selected_events(self):
        r = self.evaluate(self.sample())
        for series in r["series"]:
            count = series["nonoverlapping_shock_events"]
            self.assertLessEqual(series["same_dates_naive_last_bar_hits"], count)
            self.assertLessEqual(series["event_direction_consistency_count"], count)
            self.assertLessEqual(count, series["raw_shock_candidates"])
            self.assertEqual(series["raw_shock_candidates"]-count,
                             series["overlapping_candidates_excluded"])

    def test_benchmark_nonoverlapping_grid_count_is_bounded(self):
        result = self.evaluate(self.sample())
        for series in result["series"]:
            self.assertGreaterEqual(series["baseline_grid_independent_windows"], 1)
            self.assertLessEqual(
                series["baseline_grid_independent_windows"] *
                series["fixed_horizon_bars"],
                series["legacy_rows"] + series["fixed_horizon_bars"])
            self.assertTrue(series["interpretation"].startswith("Non-overlapping"))

    def test_changed_source_fingerprint_is_rejected(self):
        p = self.sample()
        r = opportunity_radar.analyze(p)
        p["records"][0]["close_price"] = "999.00"
        with self.assertRaisesRegex(ValueError, "must match"):
            nv.analyze_validation(p, r)

    def test_false_pit_vintage_is_rejected(self):
        p = self.sample()
        p["source_vintage"] = "VERIFIED_PIT"
        with self.assertRaises(ValueError):
            nv.analyze_validation(p, {"data_sha256": "a"*64})

    def test_lookahead_in_fake_snapshot_is_rejected(self):
        p = self.sample()
        p["records"][0]["ingested_at"] = "2030-01-01T00:00:00Z"
        with self.assertRaises(ValueError):
            self.evaluate(p)

    def test_future_changes_cannot_alter_earlier_logged_signal(self):
        p = self.sample()
        base = self.evaluate(p)
        changed = deepcopy(p)
        # Only alter the final bars of the series, after any earlier shocks.
        for row in changed["records"]:
            if (row["instrument_code"] == "BTC-USD"
                    and row["observed_for"] >= "2026-06-19T00:00:00+00:00"):
                row["close_price"] = str(float(row["close_price"]) * 1.03)
        after = self.evaluate(changed)
        for before, later in zip(base["series"], after["series"]):
            left = {e["observed_for"]: e for e in before["events"]}
            right = {e["observed_for"]: e for e in later["events"]}
            for when in left.keys() & right.keys():
                if when < "2026-06-12T00:00:00+00:00":
                    self.assertEqual(left[when], right[when])

    def test_too_short_series_does_not_pass(self):
        p = self.sample()
        p["records"] = p["records"][:26]
        result = self.evaluate(p)
        self.assertEqual(result["series_checked"], 0)
        self.assertEqual(result["total_nonoverlapping_events"], 0)
        self.assertEqual(result["real_orders"], 0)

    def test_unchanged_baseline_is_not_investment_perf_estimate(self):
        out = opportunity_research_pipeline.run_pipeline(self.sample())
        report = opportunity_research_pipeline.report(out)
        self.assertIn("Non-overlapping research checks", report)
        self.assertIn("unverified", report.lower())
        self.assertIn("virtual allocation changes remain disabled", report)
        self.assertIn("HOLD_NO_CHANGE", report)


if __name__ == "__main__":
    unittest.main()
