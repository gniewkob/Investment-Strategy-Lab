"""Offline, fabricated fixtures for WorldPulse.ai NAV availability audit.

No real source quotes or license claims are embedded in tests.
"""
from datetime import date, datetime, timezone
import json
import unittest

from scripts.worldpulse_nav_availability_v04 import (
    URLS, assess_response, audit, _expected_origin,
)

NOW = datetime(2026, 11, 6, 21, tzinfo=timezone.utc)


def fixture_rows(months=60):
    results = []
    for i in range(months):
        year = 2021 + (10 + i) // 12
        month = (10 + i) % 12 + 1
        results.append({"date": f"{year:04d}-{month:02d}-28",
                        "value": str(100 + i)})
    return results


class WorldPulseNAVAuditTests(unittest.TestCase):
    def test_readable_60_month_json_still_not_licensed_or_certified(self):
        body = json.dumps({"isin": "IE00BK5BQT80", "data":
                           {"observations": fixture_rows()}}).encode()
        x = assess_response("json", 200, "application/json", body, clock=lambda: NOW)
        self.assertEqual(x["schema_status"], "RECOGNIZED_CANDIDATE_FORMAT")
        self.assertEqual(x["in_window_months"], 60)
        self.assertEqual(x["missing_month_count"], 0)
        self.assertEqual(x["availability"],
                         "DATA_COVERAGE_CANDIDATE_RIGHTS_UNVERIFIED")
        self.assertEqual(x["latest_observation_date"], "2026-10-28")
        self.assertFalse(x["rights_verified"])
        self.assertFalse(x["raw_values_saved"])
        self.assertEqual(x["research_backtest"], "NOT_RUN")
        self.assertEqual(x["financial_operations"], 0)

    def test_stale_2026_july_data_blocks_full_history_months(self):
        body = json.dumps({"data": fixture_rows(57)}).encode()
        x = assess_response("json", 200, "application/json", body, clock=lambda: NOW)
        self.assertEqual(x["missing_month_count"], 3)
        self.assertFalse(x["latest_target_month_present"])
        # 57 months might technically meet 36-month criterion,
        # but must never be represented as a full 60-month archive.
        self.assertEqual(x["availability"],
                         "DATA_COVERAGE_CANDIDATE_RIGHTS_UNVERIFIED")
        self.assertFalse(x["rights_verified"])

    def test_empty_or_inaccessible_returns_blocked(self):
        for code, payload in (
            (404, b""), (403, b""), (429, b""),
            (200, b"{}"), (200, b"[]"),
        ):
            with self.subTest(code=code, payload=payload):
                x = assess_response("json", code, "application/json", payload,
                                    clock=lambda: NOW)
                self.assertEqual(x["availability"], "BLOCKED")
                self.assertFalse(x["rights_verified"])

    def test_csv_36_month_candidate_is_not_registered_as_nav(self):
        s = "date,value\n" + "".join(
            f'{x["date"]},{x["value"]}\n' for x in fixture_rows(36))
        x = assess_response("csv", 200, "text/csv", s.encode(), clock=lambda: NOW)
        self.assertEqual(x["in_window_months"], 36)
        self.assertEqual(x["missing_month_count"], 24)
        self.assertEqual(x["availability"],
                         "DATA_COVERAGE_CANDIDATE_RIGHTS_UNVERIFIED")
        self.assertFalse(x["fund_isin_verified_against_issuer"])
        self.assertFalse(x["rights_verified"])

    def test_source_mismatch_and_duplicate_rows_are_not_interpreted(self):
        bogus = json.dumps({"isin": "WRONG", "data": fixture_rows()}).encode()
        x = assess_response("json", 200, "application/json", bogus, clock=lambda:NOW)
        self.assertEqual(x["schema_status"], "UNVERIFIED_SCHEMA")
        dup = json.dumps(fixture_rows() + fixture_rows()[:1]).encode()
        x = assess_response("json", 200, "application/json", dup, clock=lambda:NOW)
        self.assertEqual(x["schema_status"], "UNVERIFIED_SCHEMA")
        self.assertEqual(x["availability"], "BLOCKED")

    def test_host_is_exact_allowlist_and_never_fake_world_pulse(self):
        _expected_origin(URLS["json"])
        _expected_origin(URLS["csv"])
        for url in (
            "https://api.world-pulse.io/api/v1/timeseries/canonical/ie00bk5bqt80-nav",
            "http://api.worldpulse.ai/api/v1/timeseries/canonical/ie00bk5bqt80-nav",
            "https://api.worldpulse.ai.evil.example/api/v1/timeseries/canonical/ie00bk5bqt80-nav",
            "https://api.worldpulse.ai/api/v1/unrelated",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                _expected_origin(url)

    def test_36_sparse_months_do_not_pass_as_consecutive_history(self):
        full = fixture_rows()
        sparse = full[::2] + full[1::2][:6]
        body = json.dumps({"data": sparse}).encode()
        result = assess_response("json", 200, "application/json", body,
                                 clock=lambda:NOW)
        self.assertEqual(result["in_window_months"], 36)
        self.assertLess(result["max_consecutive_in_window_months"], 36)
        self.assertEqual(result["availability"], "BLOCKED")

    def test_date_with_trailing_non_iso_text_is_not_accepted(self):
        rows = fixture_rows()
        rows[0]["date"] = "2021-11-28garbage"
        body = json.dumps({"data": rows}).encode()
        result = assess_response("json", 200, "application/json", body,
                                 clock=lambda:NOW)
        self.assertEqual(result["schema_status"], "UNVERIFIED_SCHEMA")
        self.assertEqual(result["availability"], "BLOCKED")

    def test_one_failed_transport_does_not_pretend_all_ok(self):
        def fake(url):
            if url.endswith("/csv"):
                raise OSError("Network unavailable")
            return (200, "application/json", json.dumps({
                "data": fixture_rows()}).encode())
        result = audit(fetch=fake, clock=lambda:NOW)
        self.assertEqual(result["results"]["csv"]["schema_status"],
                         "TRANSPORT_ERROR")
        self.assertFalse(result["trading_price_certified"])
        self.assertEqual(result["status"],
                         "SOURCE_NOT_ACCEPTED_LICENSE_AND_ISSUER_VALIDATION_REQUIRED")
        self.assertEqual(result["financial_operations"],0)
        self.assertEqual(result["paper_events_created"],0)
        self.assertEqual(result["research_backtest"],"NOT_RUN")


if __name__ == "__main__":
    unittest.main()
