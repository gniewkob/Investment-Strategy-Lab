"""Offline source-bound chronological and reference-revision robustness tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest import TestCase

from scripts.steo_historical_archive import catalog
from scripts.steo_monthly_forecast_eval import compare_editions
from scripts.steo_robustness_audit import walkforward_audit, reference_revision_audit
from src.isl_v2.eia_sources import SourceFormatError


def fixture(n=24):
    """Fake 2024-25 archive matrices: only valid official release IDs/days."""
    editions=[]
    for i,(issue,sp) in enumerate(list(catalog().items())[:n]):
        issued_month=sp["official_release_day"][:7]
        series={}
        for name, base in (("WTIPUUS", Decimal("60")),("BREPUUS",Decimal("65"))):
            month_values={}
            for year in range(2022,2029):
                for month in range(1,13):
                    target=f"{year:04d}-{month:02d}"
                    ordinal=(year-2022)*12+month
                    value=base + Decimal(ordinal)*Decimal(".19")
                    # Date-stamped report-to-report historical reference revisions.
                    value+=Decimal(i)*Decimal(".08")
                    if target>issued_month:
                        value+=Decimal((i%5)-2)*Decimal("1.25")
                    month_values[target]=str(value.quantize(Decimal(".01")))
            series[name]=month_values
        editions.append({
            "issue":issue,
            "official_release_day":sp["official_release_day"],
            "original_first_release_bytes_certified":False,
            "series":series,
        })
    return editions


class STEOArchivedRobustnessTests(TestCase):
    def test_walkforward_strictly_uses_matured_past_label_results(self):
        docs=fixture(24)
        pairs=compare_editions(docs)
        report=walkforward_audit(pairs,docs,min_matured=5)
        self.assertEqual(report["status"],"STEO_MATURED_LABEL_WALKFORWARD_RETROSPECTIVE_RESEARCH_ONLY")
        self.assertEqual(report["original_paired_records"],pairs["paired_target_forecasts"])
        self.assertTrue(report["no_future_reported_outcomes_as_model_inputs"])
        self.assertTrue(report["horizons_never_pooled_for_rule_selection"])
        self.assertGreater(report["reused_target_months_across_horizons"],0)
        self.assertEqual(len(report["groups"]),6)
        self.assertEqual(report["database_writes"],0)
        self.assertEqual(report["real_orders"],0)
        for group in report["groups"]:
            self.assertGreater(group["eligible_chronological_evaluations"],0)
            self.assertFalse(group["predictive_advantage_or_tradable_returns_established"])
            self.assertEqual(group["selected_naive_count"]+group["selected_eia_count"],
                             group["eligible_chronological_evaluations"])
            for item in group["decisions"]:
                self.assertGreaterEqual(item["matured_training_pairs_known_by_issue_day"],5)
                self.assertLess(item["latest_matured_reference_day"],item["forecast_issue_day"])

    def test_reference_revision_sensitivity_has_changed_quotes_without_changing_source(self):
        docs=fixture(24)
        paired=compare_editions(docs)
        before=deepcopy(docs)
        report=reference_revision_audit(paired,docs)
        self.assertEqual(report["status"],"STEO_LATER_REPORT_REFERENCE_REVISION_SENSITIVITY_RESEARCH")
        self.assertEqual(report["pairs"],paired["paired_target_forecasts"])
        self.assertEqual(len(report["groups"]),6)
        self.assertFalse(report["latest_eligible_reference_is_definitive_final_tradable_price"])
        self.assertTrue(report["reference_revision_does_not_establish_investable_advantage"])
        self.assertGreater(sum(g["later_reference_changed"] for g in report["groups"]),0)
        self.assertGreater(sum(g["later_reference_recheck_possible"] for g in report["groups"]),0)
        self.assertEqual(docs,before)
        self.assertEqual(report["database_connections"],0)
        self.assertEqual(report["database_writes"],0)
        self.assertEqual(report["real_orders"],0)

    def test_future_matured_labels_are_not_used_for_asof_rule_selection(self):
        docs=fixture(24)
        paired=compare_editions(docs)
        # Compare identical errors but only a SMALLER allowed training cutoff:
        # extra future references cannot count as known on past issue day.
        output=walkforward_audit(paired,docs,min_matured=16)
        for group in output["groups"]:
            for row in group["decisions"]:
                self.assertLess(row["latest_matured_reference_day"],row["forecast_issue_day"])
        # Large training guard means some forecast/asset/horizon groups abstain.
        self.assertLess(sum(g["eligible_chronological_evaluations"]
                            for g in output["groups"]),paired["paired_target_forecasts"])

    def test_tampered_pair_errors_and_fake_investable_backtest_fail(self):
        docs=fixture(24)
        paired=compare_editions(docs)
        corrupted=deepcopy(paired)
        corrupted["paired_records"][0]["absolute_source_forecast_error"]="9999"
        with self.assertRaisesRegex(SourceFormatError,"contradict"):
            walkforward_audit(corrupted,docs)
        corrupted=deepcopy(paired)
        corrupted["returns_or_trading_backtest"]=True
        with self.assertRaisesRegex(SourceFormatError,"Unsupported retrospective"):
            reference_revision_audit(corrupted,docs)
        corrupted=deepcopy(paired)
        corrupted["real_orders"]=1
        with self.assertRaisesRegex(SourceFormatError,"Side-effect"):
            walkforward_audit(corrupted,docs)

    def test_duplicate_target_same_instrument_horizon_rejected(self):
        docs=fixture(24)
        paired=compare_editions(docs)
        corrupted=deepcopy(paired)
        corrupted["paired_records"].append(deepcopy(corrupted["paired_records"][0]))
        corrupted["paired_target_forecasts"]+=1
        with self.assertRaisesRegex(SourceFormatError,"Duplicate"):
            walkforward_audit(corrupted,docs)

    def test_duplicate_source_or_spoofed_pit_and_invalid_min_pairs_fail(self):
        docs=fixture(24)
        paired=compare_editions(docs)
        with self.assertRaisesRegex(SourceFormatError,"supported"):
            walkforward_audit(paired,docs,min_matured=2)
        with self.assertRaisesRegex(SourceFormatError,"coverage"):
            walkforward_audit(paired,docs[:-1])
        fake=deepcopy(docs)
        fake[0]["original_first_release_bytes_certified"]=True
        with self.assertRaisesRegex(SourceFormatError,"publication proof"):
            walkforward_audit(paired,fake)

    def test_forged_ref_publication_day_rejected(self):
        docs=fixture(24)
        paired=compare_editions(docs)
        corrupted=deepcopy(paired)
        corrupted["paired_records"][0]["reference_edition_release_day"]="2026-12-01"
        with self.assertRaisesRegex(SourceFormatError,"chronological"):
            reference_revision_audit(corrupted,docs)
