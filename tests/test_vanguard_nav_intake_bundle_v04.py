"""Disposable offline fixtures for local Vanguard NAV XLSX + NBP intake.

The workbook and NBP responses here are SYNTHETIC, not investment data.
No real orders, source credentials, database writes, or HTTP requests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import unittest

from scripts.reference_archive_calendar_v04 import _digest
from scripts.vanguard_nav_intake_bundle_v04 import (
    prepare, _official_fx_source, _parse_fx,
)
from tests.test_reference_archive_calendar_v04 import sample
from tests.test_vanguard_xlsx_offline_intake_v04 import fake_xlsx


NOW = datetime(2026, 11, 6, 18, tzinfo=timezone.utc)


def fixture(months=60):
    doc, _ = sample(months, mismatches=0)
    doc["series_contract"] = {
        "usdpln": {"instrument_code": "USDPLN_NBP", "return_basis": "FX_RATE"},
        "eurpln": {"instrument_code": "EURPLN_NBP", "return_basis": "FX_RATE"},
        "gold": {"instrument_code": "GOLD_NBP_PLN_G", "return_basis": "PRICE_ONLY"},
    }
    doc["evidence_sha256"] = _digest({
        k: v for k, v in doc.items() if k != "evidence_sha256"
    })
    return fake_xlsx(months), doc


def official_fake_fx(url):
    # The real network is deliberately not accessed in unit tests.
    parts = url.split("/")
    day = parts[-3]
    if day != parts[-2]:
        raise AssertionError("date range exceeded a single day")
    return json.dumps([
        {"table": "A", "no": "009/A/NBP/2024", "effectiveDate": day,
         "rates": [{"code": "USD", "mid": 3.85},
                   {"code": "EUR", "mid": 4.30}]}
    ]).encode()


class VanguardLocalBundleTests(unittest.TestCase):
    def test_offline_reports_all_dates_needing_exact_fx_without_valuation(self):
        raw, nbp = fixture()
        r = prepare(raw, nbp, "2021-11", "2026-10", clock=lambda: NOW)
        self.assertEqual(r["status"], "BLOCKED_NEEDS_EXACT_DAY_NBP_FX")
        self.assertEqual(r["months_requested"], 60)
        self.assertEqual(r["official_extra_fx_reads"], 0)
        self.assertGreater(len(r["missing_exact_day_fx"]), 0)
        self.assertEqual(r["monthly"], [])
        self.assertEqual(r["real_model_backtest"],
                         "NOT_RUN_PENDING_ORIGINAL_NAV_PROVENANCE")
        self.assertEqual(r["paper_events_created"], 0)
        self.assertEqual(r["financial_operations"], 0)
        self.assertEqual(r["database_writes"], 0)

    def test_exact_day_fx_synthetic_probe_produces_60_nontradable_references(self):
        raw, nbp = fixture()
        r = prepare(raw, nbp, "2021-11", "2026-10",
                    fetch=official_fake_fx, clock=lambda: NOW)
        self.assertEqual(r["status"],
                         "CANDIDATE_NAV_PLN_REFERENCE_READY_FOR_SOURCE_REVIEW")
        self.assertEqual(r["months_requested"], 60)
        self.assertEqual(len(r["monthly"]), 60)
        self.assertEqual(len(r["missing_exact_day_fx"]), 0)
        self.assertGreater(r["official_extra_fx_reads"], 0)
        self.assertEqual(r["monthly"][0]["nav_usd"], "100")
        self.assertEqual(r["monthly"][0]["usdpln_nbp"], "3.85")
        self.assertEqual(r["monthly"][0]["nav_pln_reference"], "385.00")
        self.assertTrue(all(
            row["nbp_source_url"].startswith(
                "https://api.nbp.pl/api/exchangerates/tables/a/")
            for row in r["monthly"]))
        self.assertEqual(r["nav_candidate_file_sha256"], sha256(raw).hexdigest())
        self.assertEqual(len(r["evidence_sha256"]), 64)
        self.assertFalse(r["fund_identity_authenticated_from_original_file"])
        self.assertFalse(r["usable_as_GLOBAL_EQUITY_TR_PLN"])
        self.assertFalse(r["executable_market_fill_price"])
        self.assertEqual(r["real_orders"], 0)
        self.assertEqual(r["paper_events_created"], 0)
        self.assertEqual(r["database_writes"], 0)
        self.assertEqual(r["financial_operations"], 0)
        self.assertEqual(r, prepare(
            raw, nbp, "2021-11", "2026-10",
            fetch=official_fake_fx, clock=lambda: NOW))

    def test_missing_one_exact_day_reference_fails_without_interpolation(self):
        raw, nbp = fixture()
        def incomplete(url):
            raw_response = json.loads(official_fake_fx(url))
            raw_response[0]["effectiveDate"] = "2024-04-20"
            return json.dumps(raw_response).encode()
        with self.assertRaisesRegex(ValueError, "observed_for differs"):
            prepare(raw, nbp, "2021-11", "2026-10",
                    fetch=incomplete, clock=lambda: NOW)

    def test_only_usd_mid_rate_table_a_accepted(self):
        day = "2024-05-31"
        url = f"https://api.nbp.pl/api/exchangerates/tables/a/{day}/{day}/?format=json"
        for response in (
            [], [{"table": "B", "effectiveDate": day,
                  "rates": [{"code": "USD", "mid": 3.85}]}],
            [{"table": "A", "effectiveDate": day,
              "rates": [{"code": "EUR", "mid": 4.5}]}],
            [{"table": "A", "effectiveDate": day,
              "rates": [{"code": "USD", "mid": "0"}]}],
        ):
            with self.subTest(response=response), self.assertRaises(ValueError):
                _parse_fx(day, url, json.dumps(response).encode(), NOW.isoformat())
        with self.assertRaises(ValueError):
            _official_fx_source("https://untrusted.example/nbp")

    def test_tampered_NBP_archive_and_xlsx_bytes_not_accepted(self):
        raw, nbp = fixture()
        nbp["monthly_observations"]["usdpln"][0]["value"] = "100000"
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            prepare(raw, nbp, "2021-11", "2026-10",
                    clock=lambda: NOW)
        raw, nbp = fixture()
        with self.assertRaisesRegex(ValueError, "unreadable original XLSX"):
            prepare(b"not really xlsx", nbp, "2021-11", "2026-10",
                    clock=lambda: NOW)

    def test_wrong_NBP_basis_and_unmatched_receipt_blocked(self):
        raw, nbp = fixture()
        nbp["series_contract"]["usdpln"]["return_basis"] = "PRICE_ONLY"
        nbp["evidence_sha256"] = _digest({
            k: v for k, v in nbp.items() if k != "evidence_sha256"
        })
        with self.assertRaisesRegex(ValueError, "verified-contract"):
            prepare(raw, nbp, "2021-11", "2026-10", clock=lambda: NOW)
        raw, nbp = fixture()
        nbp["monthly_observations"]["usdpln"][0]["raw_sha256"] = "f"*64
        nbp["evidence_sha256"] = _digest({
            k: v for k, v in nbp.items() if k != "evidence_sha256"
        })
        with self.assertRaisesRegex(ValueError, "source receipt"):
            prepare(raw, nbp, "2021-11", "2026-10", clock=lambda: NOW)

    def test_no_future_month_and_short_history(self):
        raw, nbp = fixture()
        with self.assertRaises(ValueError):
            prepare(raw, nbp, "2025-11", "2026-10", clock=lambda: NOW)
        with self.assertRaisesRegex(ValueError, "completed historical months"):
            prepare(raw, nbp, "2022-11", "2026-11", clock=lambda: NOW)

    def test_source_failure_bubbles_up_without_partial_valuation(self):
        raw, nbp = fixture()
        def unavailable(url):
            raise OSError("official API not reachable")
        with self.assertRaisesRegex(OSError, "not reachable"):
            prepare(raw, nbp, "2021-11", "2026-10",
                    fetch=unavailable, clock=lambda: NOW)


if __name__ == "__main__":
    unittest.main()
