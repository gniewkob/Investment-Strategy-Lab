"""Completely offline Eurostat/NBP purchasing-power research acceptance tests."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import copy
import unittest

from scripts.public_first_hicp_nbp_purchasing_power_v01 import (
    PurchasingPowerBlocked, public_purchasing_power_research,
)
from tests.test_public_first_nbp_reference_research_v01 import (
    CLOCK, TODAY, mock_fetch,
)


def months(start="2021-11", end="2026-09"):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    result = []
    while (y, m) <= (ey, em):
        result.append(f"{y:04d}-{m:02d}")
        y, m = ((y+1, 1) if m==12 else (y, m+1))
    return result


def eurostat_fixture(start="2021-11", end="2026-09", *,
                     missing=None, updated="2026-11-04T11:00:00+0100"):
    months_list = months(start, end)
    dimensions = {
        "freq": {"category": {"index": {"M": 0}}},
        "unit": {"category": {"index": {"I25": 0}}},
        "coicop18": {"category": {"index": {"TOTAL": 0}}},
        "geo": {"category": {"index": {"PL": 0}}},
        "time": {"category": {"index":
            {month: index for index, month in enumerate(months_list)}}},
    }
    values = {str(i): str(Decimal("76.54") + Decimal(i) * Decimal(".47"))
              for i, month in enumerate(months_list) if month != missing}
    return {
        "version": "2.0", "class": "dataset", "source": "ESTAT",
        "updated": updated,
        "id": ["freq", "unit", "coicop18", "geo", "time"],
        "size": [1, 1, 1, 1, len(months_list)],
        "dimension": dimensions,
        "value": values,
    }


class PublicInflationOverlayTests(unittest.TestCase):
    def run_overlay(self, *, since="2021-11", until="2026-09",
                    payload=None, fetch=None):
        if payload is None:
            payload = eurostat_fixture(since, until)
        if fetch is None:
            fetch = mock_fetch(since, until)
        return public_purchasing_power_research(
            since=since, until=until,
            nbp_fetch=fetch, hicp_payload=payload, today=TODAY, clock=CLOCK)

    def test_59_months_live_schema_with_fixture_not_proof(self):
        report = self.run_overlay()
        self.assertEqual(report["status"],
                         "PUBLIC_MACRO_REFERENCE_CONTEXT_ONLY")
        self.assertEqual(report["aligned_published_months"],59)
        self.assertEqual(report["first_month"],"2021-11")
        self.assertEqual(report["last_month"],"2026-09")
        self.assertEqual(report["hypothetical_nominal_contributions_pln"],
                         "5900.00")
        self.assertEqual(len(report["scenarios"]),7)
        self.assertEqual(len(report["source_eurostat_canonical_sha256"]),64)
        self.assertEqual(len(report["source_nbp_monthly_values_canonical_sha256"]),64)
        self.assertTrue(report["source_nbp_raw_sha256_receipts"])
        self.assertEqual(report["legacy_m1_m2_m3"],
                         "NOT_RUN_UNQUALIFIED_TOTAL_RETURN_SERIES")
        self.assertEqual(report["qualified_model_series"],[])
        self.assertFalse(report["historical_point_in_time_certified"])
        self.assertFalse(report["investment_profit_proven"])
        self.assertFalse(report["historical_first_release_captured"])
        self.assertEqual(report["financial_operations"],0)
        self.assertEqual(report["paper_events_created"],0)
        self.assertEqual(report["database_writes"],0)

    def test_result_deterministic_on_same_offline_sources(self):
        self.assertEqual(self.run_overlay(),self.run_overlay())

    def test_cost_stress_reduces_reference_levels(self):
        cases=self.run_overlay()["scenarios"]
        self.assertEqual(cases[0]["nominal_terminal_reference_pln"],
                         "5900.00")
        for idx in (1,3,5):
            nominal=Decimal(cases[idx]["nominal_terminal_reference_pln"])
            stress=Decimal(cases[idx+1]["nominal_terminal_reference_pln"])
            self.assertGreater(nominal,stress)
            self.assertEqual(cases[idx+1]["assumed_one_way_cost_bps"],"30")
            self.assertTrue(cases[idx+1]["not_executable_or_predicted"])

    def test_matched_cashflow_hicp_inflation_arithmetic(self):
        data=self.run_overlay()
        h=Decimal(eurostat_fixture()["value"]["58"])
        baseline=sum(
            (Decimal("100") * h / Decimal(v)
             for v in eurostat_fixture()["value"].values()),Decimal("0"))
        self.assertEqual(data["cpi_matched_hypothetical_monthly_cashflows_pln"],
                         f"{baseline.quantize(Decimal('.01')):.2f}")
        self.assertEqual(
            Decimal(data["scenarios"][0]["difference_vs_cpi_matched_cashflows_pln"]),
            (Decimal("5900")-baseline).quantize(Decimal(".01")))

    def test_no_implicit_network(self):
        with self.assertRaisesRegex(PurchasingPowerBlocked,
                                    "EXPLICIT_PUBLIC_SOURCE_INPUTS_REQUIRED"):
            public_purchasing_power_research(today=TODAY)

    def test_source_report_does_not_disguise_vintage(self):
        result=self.run_overlay()
        self.assertFalse(result["source_eurostat_first_published_asof_verified"])
        self.assertTrue(result["hicp_is_macro_context_not_asset_return"])
        self.assertTrue(result["gold_reference_is_price_only_not_total_return"])
        self.assertTrue(result["historical_nbpxfx_mid_not_executable"])

    def test_reject_unpublished_october_2026(self):
        payload=eurostat_fixture("2021-11","2026-10",missing="2026-10")
        with self.assertRaises(PurchasingPowerBlocked):
            self.run_overlay(until="2026-10",payload=payload,
                             fetch=mock_fetch("2021-11","2026-10"))

    def test_missing_mid_series_month_fails_closed(self):
        payload=eurostat_fixture(missing="2024-04")
        with self.assertRaises(PurchasingPowerBlocked):
            self.run_overlay(payload=payload)

    def test_wrong_country_pl_rejected(self):
        p=eurostat_fixture()
        p["dimension"]["geo"]["category"]["index"]={"DE":0}
        with self.assertRaisesRegex(PurchasingPowerBlocked,
                                    "OFFICIAL_SOURCE_CONTRACT_REJECTED"):
            self.run_overlay(payload=p)

    def test_wrong_hicp_unit_rejected(self):
        p=eurostat_fixture()
        p["dimension"]["unit"]["category"]["index"]={"I15":0}
        with self.assertRaises(PurchasingPowerBlocked):
            self.run_overlay(payload=p)

    def test_wrong_ecoicop_measure_rejected(self):
        p=eurostat_fixture()
        p["dimension"]["coicop18"]["category"]["index"]={"CP00":0}
        with self.assertRaises(PurchasingPowerBlocked):
            self.run_overlay(payload=p)

    def test_hicp_nonpositive_or_nan_rejected(self):
        for bad in ("0","-1","NaN","Infinity"):
            with self.subTest(bad=bad):
                p=eurostat_fixture()
                p["value"]["14"]=bad
                with self.assertRaises(PurchasingPowerBlocked):
                    self.run_overlay(payload=p)

    def test_hicp_month_gap_rejected(self):
        p=eurostat_fixture()
        p["dimension"]["time"]["category"]["index"].pop("2023-05")
        with self.assertRaises(PurchasingPowerBlocked):
            self.run_overlay(payload=p)

    def test_hicp_mismatched_window_rejected(self):
        with self.assertRaises(PurchasingPowerBlocked):
            self.run_overlay(payload=eurostat_fixture("2021-12","2026-10"))

    def test_nbp_missing_month_rejected(self):
        fetch=mock_fetch("2021-11","2026-09",missing_gold="2024-06-27")
        with self.assertRaises(PurchasingPowerBlocked):
            self.run_overlay(fetch=fetch)

    def test_eurostat_not_network_authenticated_by_fixture(self):
        p=eurostat_fixture()
        p["source"]="UNTRUSTED"
        with self.assertRaises(PurchasingPowerBlocked):
            self.run_overlay(payload=p)


if __name__ == "__main__":
    unittest.main()
