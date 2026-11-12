"""End-to-end public-first 5-series source bundle, network forbidden offline."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import json
import unittest
from unittest.mock import patch

from scripts.nbp_reference_capture import capture
from scripts.eurostat_hicp_macro_context_v01 import inspect_hicp
from scripts.public_first_multisource_macro_evidence_v05 import (
    evaluate_combined_sources, observe_once, SOURCE_QUEUE,
    MultiSourceBlocked, SCHEMA, HICP_SINCE, HICP_UNTIL,
    NBP_START, NBP_END,
)
from tests.test_public_first_prospective_source_observation_v03 import source_fetch
from tests.test_eurostat_hicp_macro_context_v01 import fixture
from tests.test_eurostat_pl_government_bond_yield_context_v04 import original_shape

AT = datetime(2026, 11, 13, 0, 0, tzinfo=timezone.utc)


def months():
    y, m = 2025, 9
    out = []
    for _ in range(13):
        out.append(f"{y}-{m:02d}")
        y, m = ((y + 1, 1) if m == 12 else (y, m + 1))
    assert out[0] == HICP_SINCE and out[-1] == HICP_UNTIL
    return out


def data_fixture():
    return fixture(
        months=months(),
        values=[100 + n * 0.4 for n in range(13)])


def inputs():
    nbp = capture(NBP_START, NBP_END, fetch=source_fetch(),
                  clock=lambda: AT)
    hicp = inspect_hicp(
        data_fixture(), since=HICP_SINCE, until=HICP_UNTIL,
        retrieval_scope="EUROSTAT_PUBLIC_READ_ONLY")
    yield_raw = json.dumps(original_shape()).encode()
    return nbp, hicp, yield_raw


class MultiSourceMacroEvidenceTests(unittest.TestCase):
    def test_five_source_series_and_derived_backward_gap(self):
        n, h, y = inputs()
        out = evaluate_combined_sources(n, h, y, completed_at=AT)
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(len(out["series_types"]), 5)
        self.assertEqual(out["hicp_months"], 13)
        self.assertEqual(out["government_yield_months"], 59)
        self.assertEqual(out["joint_reference_month"], "2026-09")
        self.assertEqual(out["pl_nominal_10y_government_yield_pct_per_annum"], "4.58")
        self.assertEqual(out["pl_trailing_12m_hicp_inflation_pct"], "4.8000")
        self.assertEqual(out["arithmetic_yield_minus_trailing_inflation_pp"], "-0.2200")
        self.assertFalse(out["historical_point_in_time_certified"])
        self.assertFalse(out["source_rights_fully_approved"])
        self.assertEqual(out["asset_total_return_series_qualified"], [])
        self.assertEqual(out["m1_m2_m3"], "INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual(out["orders_sent"], 0)
        self.assertEqual(out["financial_operations"], 0)
        self.assertEqual(out["database_writes"], 0)
        self.assertNotIn('"observations"', json.dumps(out))

    def test_source_hashes_linked_to_original_payload(self):
        n, h, y = inputs()
        out = evaluate_combined_sources(n, h, y, completed_at=AT)
        self.assertEqual(len(out["source_fingerprints_sha256"]), 4)
        self.assertTrue(all(len(x) == 64 for x in out["source_fingerprints_sha256"].values()))
        self.assertRegex(out["receipt_sha256"], r"^[a-f0-9]{64}$")

    def test_exchange_archives_all_licence_blocked(self):
        n, h, y = inputs()
        out = evaluate_combined_sources(n, h, y, completed_at=AT)
        self.assertEqual(len(out["external_exchange_source_queue"]), 4)
        self.assertEqual(tuple(x["id"] for x in SOURCE_QUEUE),
                         tuple(x["id"] for x in out["external_exchange_source_queue"]))
        self.assertTrue(all(x["automated_ingestion_authorized"] is False
                            and x["historic_first_published_proven"] is False
                            and x["asset_total_return_qualified"] is False
                            for x in out["external_exchange_source_queue"]))
        self.assertTrue(all(x["official_url"].startswith("https://")
                            for x in out["external_exchange_source_queue"]))

    def test_one_shot_explicit_injected_source_reads_only(self):
        def hicp_fetch(url):
            self.assertIn("prc_hicp_minr", url)
            return data_fixture()
        def yield_fetch():
            return json.dumps(original_shape()).encode()
        out = observe_once(
            nbp_fetch=source_fetch(), hicp_fetch=hicp_fetch,
            yield_fetch=yield_fetch, clock=lambda: AT)
        self.assertEqual(out["joint_reference_month"], "2026-09")
        self.assertEqual(out["financial_operations"], 0)

    def test_no_implicit_fetch_and_naive_clock_fail_before_network(self):
        with self.assertRaisesRegex(MultiSourceBlocked, "EXPLICIT"):
            observe_once(nbp_fetch=None, hicp_fetch=None, yield_fetch=None)
        calls = []
        def deny(*_a, **_k):
            calls.append(True)
            raise AssertionError("NETWORK_SHOULD_NOT_RUN")
        with self.assertRaisesRegex(MultiSourceBlocked, "UTC_AWARE_CLOCK"):
            observe_once(nbp_fetch=deny, hicp_fetch=deny, yield_fetch=deny,
                         clock=lambda: datetime(2026, 11, 13))
        self.assertEqual(calls, [])

    def test_no_future_window(self):
        n, h, y = inputs()
        with self.assertRaisesRegex(MultiSourceBlocked, "FUTURE"):
            evaluate_combined_sources(
                n, h, y,
                completed_at=datetime(2026, 8, 1, tzinfo=timezone.utc))

    def test_missing_hicp_month_fails_closed(self):
        n, h, y = inputs()
        h["observations"][2]["index_2025_100"] = None
        with self.assertRaises((ValueError, MultiSourceBlocked)):
            evaluate_combined_sources(n, h, y, completed_at=AT)

    def test_hicp_date_or_retrieval_scope_fails_closed(self):
        n, h, y = inputs()
        h["observations"][0]["month"] = "2025-08"
        with self.assertRaises((ValueError, MultiSourceBlocked)):
            evaluate_combined_sources(n, h, y, completed_at=AT)
        n, h, y = inputs()
        h["retrieval_scope"] = "SECRET_UNTRUSTED_SOURCE"
        with self.assertRaises((ValueError, MultiSourceBlocked)):
            evaluate_combined_sources(n, h, y, completed_at=AT)

    def test_wrong_nbp_source_or_units_rejected(self):
        n, h, y = inputs()
        n["receipts"]["fx"]["url"] = "https://untrusted.invalid/"
        with self.assertRaises((ValueError, MultiSourceBlocked)):
            evaluate_combined_sources(n, h, y, completed_at=AT)
        n, h, y = inputs()
        n["series"]["gold"][0]["basis"] = "TOTAL_RETURN"
        with self.assertRaises((ValueError, MultiSourceBlocked)):
            evaluate_combined_sources(n, h, y, completed_at=AT)

    def test_bad_bond_source_country_or_incomplete_months_rejected(self):
        n, h, y = inputs()
        data = original_shape()
        data["dimension"]["geo"]["category"]["index"] = {"DE": 0}
        with self.assertRaises((ValueError, MultiSourceBlocked)):
            evaluate_combined_sources(
                n, h, json.dumps(data).encode(), completed_at=AT)
        data = original_shape()
        data["value"].pop("10")
        with self.assertRaises((ValueError, MultiSourceBlocked)):
            evaluate_combined_sources(
                n, h, json.dumps(data).encode(), completed_at=AT)

    def test_invalid_bond_rate_unit_and_nonfinite_rejected(self):
        n, h, _ = inputs()
        for bad in (float("nan"), 60, True):
            data = original_shape()
            data["value"]["58"] = bad
            with self.subTest(bad=str(bad)), self.assertRaises((ValueError, MultiSourceBlocked)):
                evaluate_combined_sources(n, h, json.dumps(data).encode(),
                                          completed_at=AT)

    def test_all_offline_test_execution_denies_sockets(self):
        with patch("socket.socket.connect", side_effect=AssertionError(
                "UNEXPECTED_NETWORK")):
            n, h, y = inputs()
            self.assertEqual(evaluate_combined_sources(
                n, h, y, completed_at=AT)["account_connections"], 0)


if __name__ == "__main__":
    unittest.main()
