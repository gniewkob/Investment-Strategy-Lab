"""Offline-only negative tests of current public source observation receipts."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import unittest

from scripts.public_first_prospective_source_observation_v03 import (
    SCHEMA, SourceObservationBlocked, assemble_receipt, compare_receipts,
    observe_once, verify_receipt,
)
from scripts.nbp_reference_capture import capture
from scripts.eurostat_hicp_macro_context_v01 import inspect_hicp
from tests.test_eurostat_hicp_macro_context_v01 import fixture

START, END = "2026-09-01", "2026-09-30"
SINCE, UNTIL = "2026-08", "2026-09"
AT = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)


def source_fetch(*, usd=4.0, shift_date="2026-09-14"):
    def fetch(url):
        if "/cenyzlota/" in url:
            return json.dumps([{"data": shift_date, "cena": 410.0}]).encode()
        if "/exchangerates/tables/a/" in url:
            return json.dumps([{
                "table": "A", "no": "178/A/NBP/2026",
                "effectiveDate": shift_date,
                "rates": [
                    {"code": "USD", "mid": usd},
                    {"code": "EUR", "mid": 4.50},
                ],
            }]).encode()
        raise AssertionError("UNEXPECTED_NBP_NETWORK_TARGET")
    return fetch


def eurostat_fetch(url):
    if ("ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
            "prc_hicp_minr?") not in url:
        raise AssertionError("UNEXPECTED_EUROSTAT_NETWORK_TARGET")
    return fixture(months=(SINCE, UNTIL), values=(101.2, 102.0))


def snap(*, when=AT, usd=4.0, end=END, hicp=eurostat_fetch):
    return observe_once(
        nbp_start=START, nbp_end=end, hicp_since=SINCE, hicp_until=UNTIL,
        nbp_fetch=source_fetch(usd=usd), hicp_fetch=hicp,
        clock=lambda: when)


class ProspectivePublicSourceTests(unittest.TestCase):
    def test_observed_receipt_is_metadata_only_and_unqualified(self):
        item = snap()
        self.assertEqual(item["schema"], SCHEMA)
        self.assertEqual(set(item["source_fingerprints_sha256"]),
                         {"nbp_fx", "nbp_gold", "eurostat_hicp"})
        self.assertEqual(item["nbp_observation_counts"],
                         {"usdpln": 1, "eurpln": 1, "gold": 1})
        self.assertEqual(item["eurostat_observation_months"], 2)
        self.assertEqual(item["qualified_model_series"], [])
        self.assertEqual(item["model_state"], "HOLD_CASH")
        self.assertFalse(item["historical_pit_certified"])
        self.assertFalse(item["historical_first_publication_timestamp_verified"])
        self.assertEqual(item["financial_operations"], 0)
        self.assertEqual(verify_receipt(item), item)
        self.assertNotIn("410.0", json.dumps(item))
        self.assertNotIn("4.5", json.dumps(item))
        self.assertNotIn("source_rows", item)

    def test_repeated_public_source_fingerprints_unchanged(self):
        first = snap()
        next_day = snap(when=AT + timedelta(days=1))
        comparison = compare_receipts(first, next_day)
        self.assertEqual(comparison["status"], "SOURCE_FINGERPRINTS_UNCHANGED")
        self.assertEqual(comparison["changed_sources"], [])
        self.assertFalse(comparison["historical_pit_certified"])
        self.assertEqual(comparison["financial_operations"], 0)

    def test_changed_original_nbp_response_detected(self):
        first = snap()
        new = snap(when=AT + timedelta(days=1), usd=4.01)
        receipt = compare_receipts(first, new)
        self.assertEqual(receipt["status"], "SOURCE_FINGERPRINTS_CHANGED")
        self.assertEqual(receipt["changed_sources"], ["nbp_fx"])
        self.assertTrue(receipt["does_not_establish_historic_first_release"])

    def test_changed_window_not_an_original_revision(self):
        first = snap()
        changed = snap(when=AT + timedelta(days=1), end="2026-09-29")
        with self.assertRaisesRegex(SourceObservationBlocked,
                                    "DIFFERENT_SOURCE_WINDOWS"):
            compare_receipts(first, changed)

    def test_duplicate_capture_or_time_regression_rejected(self):
        original = snap()
        for newer in (snap(), snap(when=AT - timedelta(seconds=1))):
            with self.assertRaisesRegex(SourceObservationBlocked,
                                        "NON_INCREASING_CAPTURE_TIME"):
                compare_receipts(original, newer)

    def test_sha_tampering_detected(self):
        forged = deepcopy(snap())
        forged["source_fingerprints_sha256"]["nbp_fx"] = "0" * 64
        with self.assertRaisesRegex(SourceObservationBlocked,
                                    "RECEIPT_INTEGRITY"):
            verify_receipt(forged)

    def test_false_pit_or_financial_authorization_rejected(self):
        for key, value in (("historical_pit_certified", True),
                           ("qualified_model_series", ["PL_BONDS_TR_PLN"]),
                           ("financial_operations", 1),
                           ("model_state", "TRADING")):
            forged = deepcopy(snap())
            forged[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                SourceObservationBlocked, "RECEIPT_INTEGRITY"):
                verify_receipt(forged)

    def test_missing_hicp_month_blocks(self):
        def incomplete(_):
            return fixture(months=(SINCE, UNTIL), values=(101.0, None))
        with self.assertRaisesRegex(SourceObservationBlocked,
                                    "EUROSTAT_SOURCE_CONTRACT"):
            snap(hicp=incomplete)

    def test_wrong_source_url_blocks(self):
        nbp = capture(START, END, fetch=source_fetch(), clock=lambda: AT)
        hicp = inspect_hicp(
            fixture(months=(SINCE, UNTIL), values=(101, 102)),
            since=SINCE, until=UNTIL,
            retrieval_scope="EUROSTAT_PUBLIC_READ_ONLY")
        nbp["receipts"]["fx"]["url"] = "https://evil.invalid/fake"
        with self.assertRaisesRegex(SourceObservationBlocked,
                                    "NBP_SOURCE_URL_MISMATCH"):
            assemble_receipt(nbp, hicp, nbp_start=START, nbp_end=END,
                             hicp_since=SINCE, hicp_until=UNTIL,
                             completed_at=AT)

    def test_future_source_window_rejected(self):
        with self.assertRaisesRegex(SourceObservationBlocked,
                                    "SOURCE_WINDOW_OUTSIDE"):
            snap(when=datetime(2026, 9, 1, tzinfo=timezone.utc))

    def test_mismatched_publication_semantics_blocked(self):
        nbp = capture(START, END, fetch=source_fetch(), clock=lambda: AT)
        hicp = inspect_hicp(
            fixture(months=(SINCE, UNTIL), values=(101, 102)),
            since=SINCE, until=UNTIL,
            retrieval_scope="EUROSTAT_PUBLIC_READ_ONLY")
        nbp["series"]["gold"][0]["basis"] = "TOTAL_RETURN"
        with self.assertRaisesRegex(SourceObservationBlocked,
                                    "NBP_REFERENCE_SEMANTICS"):
            assemble_receipt(nbp, hicp, nbp_start=START, nbp_end=END,
                             hicp_since=SINCE, hicp_until=UNTIL,
                             completed_at=AT)

    def test_malformed_or_future_provider_timestamp_rejected(self):
        for stamp in ("2035-01-01T11:00:00+0000",
                      "bad-updated",
                      "2026-11-12T10:00:00+0000\\n::warning::forged"):
            def fake(url):
                payload = eurostat_fetch(url)
                payload["updated"] = stamp
                return payload
            with self.subTest(stamp=stamp), self.assertRaisesRegex(
                SourceObservationBlocked, "EUROSTAT_PROVIDER_UPDATED_INVALID"):
                snap(hicp=fake)

    def test_no_implicit_network_or_naive_clock(self):
        with self.assertRaisesRegex(SourceObservationBlocked,
                                    "EXPLICIT_OFFICIAL_SOURCE_FETCH"):
            observe_once(nbp_start=START, nbp_end=END,
                         hicp_since=SINCE, hicp_until=UNTIL,
                         nbp_fetch=None, hicp_fetch=None)
        with self.assertRaisesRegex(SourceObservationBlocked,
                                    "UTC_AWARE_CLOCK_REQUIRED"):
            snap(when=datetime(2026, 11, 12, 18, 0))


if __name__ == "__main__":
    unittest.main()
