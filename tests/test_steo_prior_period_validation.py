"""Synthetic offline tests of a previously untouched 2022-2023 EIA STEO period."""
from __future__ import annotations

from copy import deepcopy
from unittest import TestCase
from scripts import steo_prior_period_validation as prior
from scripts.steo_monthly_forecast_eval import parse_edition
from src.isl_v2.eia_sources import SourceFormatError

from test_steo_monthly_forecast_eval import archived_fixture


def eligible_editions():
    originals=[]
    for issue in prior.prior_catalog():
        # Jan22 original source lacks A3 labelled forecast-completion text.
        raw=archived_fixture(issue,first_year=(2018 if issue.endswith("22") else 2019),
                             omit_forecast_date=(issue=="jan22"))
        originals.append(parse_edition(issue,raw))
    bridge=[parse_edition(issue,archived_fixture(issue,first_year=2021))
            for issue in list(prior.catalog())[:8]]
    return originals,bridge


class STEOPriorHistoricalPeriodTests(TestCase):
    def test_official_date_coverage_frozen_and_nonoverlapping(self):
        c=prior.prior_catalog()
        self.assertEqual(len(c),24)
        self.assertEqual(c["jan22"]["official_release_day"],"2022-01-11")
        self.assertEqual(c["dec22"]["official_release_day"],"2022-12-06")
        self.assertEqual(c["jan23"]["official_release_day"],"2023-01-10")
        self.assertEqual(c["dec23"]["official_release_day"],"2023-12-12")
        self.assertTrue(all(not x["historical_original_bytes_certified"] for x in c.values()))
        self.assertTrue(set(c).isdisjoint(prior.catalog()))

    def test_prior_pilot_jan22_allows_missing_non_public_forecast_date(self):
        raw=archived_fixture("jan22",omit_forecast_date=True)
        edition=parse_edition("jan22",raw)
        self.assertEqual(edition["official_release_day"],"2022-01-11")
        self.assertEqual(edition["available_not_before_utc_date"],"2022-01-12")
        self.assertEqual(edition["series"]["WTIPUUS"]["2022-02"],"70.80")
        self.assertFalse(edition["forecast_completed_date_used_as_market_availability"])
        self.assertFalse(edition["original_first_release_bytes_certified"])

    def test_official_pre_2020_year_groups_validated_without_loosening_unrelated_range(self):
        old=parse_edition("jan22",
                          archived_fixture("jan22",first_year=2018,omit_forecast_date=True))
        self.assertEqual(old["series"]["WTIPUUS"]["2022-02"],"76.80")
        later=parse_edition("jan23",archived_fixture("jan23",first_year=2019))
        self.assertEqual(later["official_release_day"],"2023-01-10")
        with self.assertRaisesRegex(SourceFormatError,"calendar year"):
            parse_edition("jan22",archived_fixture("jan22",first_year=2017,
                                                   omit_forecast_date=True))

    def test_missing_forecast_header_in_2023_remains_rejected(self):
        raw=archived_fixture("jan23",omit_forecast_date=True)
        with self.assertRaisesRegex(SourceFormatError,"forecast-completed"):
            parse_edition("jan23",raw)

    def test_full_24_earlier_source_forecasts_and_8_reference_only_bridges(self):
        docs,bridge=eligible_editions()
        report=prior.fixed_rule_prior_period_report(docs,bridge)
        self.assertEqual(report["status"],
                         "STEO_PREDECLARED_EARLIER_2022_2023_HISTORICAL_SOURCE_VALIDATION")
        self.assertEqual(report["prior_editions"],24)
        self.assertEqual(report["reference_only_bridge_editions"],8)
        self.assertEqual(report["original_old_era_forecast_pairs"],144)
        self.assertEqual(report["prior_period_test_rule"],
                         "FROZEN_ALWAYS_EIA_VS_SAME_OLD_EDITION_PREVIOUS_MONTH_NAIVE")
        self.assertFalse(report["heldout_period_is_chronologically_future"])
        self.assertFalse(report["historical_original_publication_bytes_certified"])
        self.assertEqual(len(report["by_source_horizon"]),6)
        for row in report["by_source_horizon"]:
            self.assertEqual(row["n_forecast_issues"],24)
            self.assertEqual(row["by_year"]["2022"]["forecast_count"],12)
            self.assertEqual(row["by_year"]["2023"]["forecast_count"],12)
        for key in ("database_connections","database_writes","real_orders",
                    "paper_allocations_changed","source_workbooks_persisted"):
            self.assertEqual(report[key],0)
        self.assertFalse(report["schedule_enabled"])

    def test_bogus_source_date_and_missing_bridge_rejected(self):
        docs,bridge=eligible_editions()
        with self.assertRaisesRegex(SourceFormatError,"24-issue"):
            prior.fixed_rule_prior_period_report(docs[:-1],bridge)
        fake=deepcopy(docs)
        fake[0]["official_release_day"]="2022-01-09"
        with self.assertRaisesRegex(SourceFormatError,"chronology"):
            prior.fixed_rule_prior_period_report(fake,bridge)
        with self.assertRaisesRegex(SourceFormatError,"24-issue"):
            prior.fixed_rule_prior_period_report(docs,bridge[:-1])

    def test_old_source_retrieval_allowlist_and_external_redirect(self):
        with self.assertRaisesRegex(SourceFormatError,"allowlisted"):
            prior.retrieve_prior("jan19")
        class Fake:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def geturl(self):return "https://attacker.example/jan22_base.xlsx"
        with self.assertRaisesRegex(SourceFormatError,"official allowlist"):
            prior.retrieve_prior("jan22",opener=lambda request,timeout:Fake())
