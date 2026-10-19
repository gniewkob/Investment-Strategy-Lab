"""Research-only paired benchmark diagnostics on entirely synthetic input."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import paired_research_evidence as paired
from scripts import opportunity_demo_fixture, opportunity_research_pipeline


def synthetic_report(outcomes=None):
    if outcomes is None:
        outcomes = [(True, True), (False, False), (True, False),
                    (False, True)]
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = []
    for i, (radar_hit, naive_hit) in enumerate(outcomes):
        when = timestamp + timedelta(days=5 * i)
        events.append({
            "observed_for": when.isoformat(),
            "next_horizon_direction_consistent": radar_hit,
            "naive_last_bar_direction_consistent": naive_hit,
            "horizon_bars": 5,
        })
    n = len(events)
    hits = sum(x[0] for x in outcomes)
    baseline_hits = sum(x[1] for x in outcomes)
    row = {
        "instrument_code": "WTI_EIA_USD_BBL",
        "interval_code": "1d",
        "nonoverlapping_shock_events": n,
        "raw_shock_candidates": n + 3,
        "overlapping_candidates_excluded": 3,
        "event_direction_consistency_count": hits,
        "same_dates_naive_last_bar_hits": baseline_hits,
        "event_vs_same_date_naive_consistency_pp":
            round(100 * (hits - baseline_hits) / n, 2) if n else None,
        "fixed_horizon_bars": 5,
        "events": events,
    }
    return {
        "status": "NONOVERLAPPING_RESEARCH_DIAGNOSTIC_ONLY",
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "source_radar_sha256": "a" * 64,
        "independent_publication_vintages_verified": False,
        "causal_predictive_advantage_established": False,
        "investable_return_benchmark_verified": False,
        "real_orders": 0,
        "database_writes": 0,
        "virtual_portfolio_changes": 0,
        "scheduled": False,
        "series_checked": 1,
        "total_nonoverlapping_events": n,
        "total_excluded_overlaps": 3,
        "series": [row],
    }


class PairedDescriptiveResearchTests(unittest.TestCase):
    def test_correctly_counts_paired_discordances_without_edge_claims(self):
        out = paired.summarize(synthetic_report())
        self.assertEqual(out["paired_events"], 4)
        self.assertEqual(out["series"][0]["both_correct"], 1)
        self.assertEqual(out["series"][0]["both_incorrect"], 1)
        self.assertEqual(out["radar_only_correct"], 1)
        self.assertEqual(out["naive_only_correct"], 1)
        self.assertEqual(out["paired_difference_pp"], 0.0)
        self.assertEqual(out["inference"], "NO_PREDICTIVE_ADVANTAGE_OR_EQUIVALENCE_CLAIM")
        self.assertFalse(out["point_in_time_certified"])
        self.assertFalse(out["independent_confirmatory_holdout_available"])
        self.assertEqual(out["real_orders"], 0)
        self.assertEqual(out["database_writes"], 0)
        self.assertFalse(out["schedule_enabled"])

    def test_same_rates_can_hide_disagreement_between_predictors(self):
        out = paired.summarize(synthetic_report(
            [(True, False), (False, True)]))
        self.assertEqual(out["paired_difference_pp"], 0)
        self.assertEqual(out["radar_only_correct"], 1)
        self.assertEqual(out["naive_only_correct"], 1)
        self.assertEqual(out["series"][0]["both_correct"], 0)

    def test_positive_descriptive_score_does_not_authorize_anything(self):
        out = paired.summarize(synthetic_report(
            [(True, False), (True, False), (False, True)]))
        self.assertEqual(out["paired_difference_pp"], 33.33)
        self.assertFalse(out["portfolio_change_authorized"])
        self.assertEqual(out["virtual_allocations_changed"], 0)
        self.assertFalse(out["series"][0]["predictive_edge_inferred"])

    def test_original_report_must_have_all_paired_dates_not_just_last_12(self):
        data = synthetic_report([(True, True)] * 13)
        data["series"][0]["events"] = data["series"][0]["events"][-12:]
        with self.assertRaisesRegex(ValueError, "Truncated"):
            paired.summarize(data)

    def test_hit_count_and_top_level_total_tampering_rejected(self):
        data = synthetic_report()
        data["series"][0]["event_direction_consistency_count"] += 1
        with self.assertRaisesRegex(ValueError, "hit counts"):
            paired.summarize(data)
        data = synthetic_report()
        data["total_nonoverlapping_events"] += 1
        with self.assertRaisesRegex(ValueError, "Top-level"):
            paired.summarize(data)

    def test_false_pit_or_live_authorization_claim_rejected(self):
        for key, spoof in [
            ("source_vintage", "VERIFIED_PIT"),
            ("independent_publication_vintages_verified", True),
            ("causal_predictive_advantage_established", True),
            ("real_orders", 1),
            ("schedule_enabled", True),
            ("source_radar_sha256", "not-a-sha"),
        ]:
            report = synthetic_report()
            report[key] = spoof
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "Only fingerprinted"):
                    paired.summarize(report)

    def test_timestamp_and_duplicate_event_fail_closed(self):
        data = synthetic_report()
        data["series"][0]["events"][1]["observed_for"] = data["series"][0]["events"][0]["observed_for"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            paired.summarize(data)
        data = synthetic_report()
        data["series"][0]["events"][1]["observed_for"] = "2026-01-09"
        with self.assertRaisesRegex(ValueError, "Timezone-aware"):
            paired.summarize(data)

    def test_empty_paired_events_remain_uninformative(self):
        report = synthetic_report([])
        out = paired.summarize(report)
        self.assertEqual(out["paired_events"], 0)
        self.assertIsNone(out["paired_difference_pp"])
        self.assertIsNone(out["series"][0]["observed_paired_difference_pp"])
        self.assertFalse(out["portfolio_change_authorized"])

    def test_current_synthetic_pipeline_integration(self):
        result = opportunity_research_pipeline.run_pipeline(
            opportunity_demo_fixture.generate())
        out = paired.summarize(result["robustness"])
        self.assertEqual(out["source_radar_sha256"],
                         result["manifest"]["radar_data_sha256"])
        self.assertEqual(out["paired_events"],
                         result["robustness"]["total_nonoverlapping_events"])
        self.assertEqual(out["virtual_allocations_changed"], 0)

    def test_report_does_not_claim_context_evidence_when_empty(self):
        result = opportunity_research_pipeline.run_pipeline(
            opportunity_demo_fixture.generate())
        self.assertEqual(result["context"]["context_events"], 0)
        human = opportunity_research_pipeline.report(result)
        self.assertIn("No independently documented macro/geopolitical context events", human)
        self.assertNotIn("Events have publication/retrieval timestamps", human)

    def test_cli_suppresses_paths_and_fails_closed_on_truncated_evidence(self):
        bad = synthetic_report([(True, True)] * 13)
        bad["series"][0]["events"] = bad["series"][0]["events"][-12:]
        with tempfile.TemporaryDirectory() as td:
            location = Path(td) / "private-synthetic-evidence.json"
            location.write_text(json.dumps(bad), encoding="utf-8")
            stderr = StringIO()
            with redirect_stderr(stderr):
                code = paired.main(["--robustness-json", str(location)])
            self.assertEqual(code, 2)
            self.assertNotIn(td, stderr.getvalue())
            self.assertEqual(
                stderr.getvalue().strip(),
                "PAIRED_RESEARCH_AUDIT_FAILED: ValueError")


if __name__ == "__main__":
    unittest.main()
