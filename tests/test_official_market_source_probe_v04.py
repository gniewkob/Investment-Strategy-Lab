"""Offline tests for official, read-only Vanguard/BondSpot capability probe."""
from datetime import datetime, timezone
import unittest

from scripts.official_market_source_probe_v04 import parse_snapshot, probe


NOW = datetime(2026, 11, 6, 14, tzinfo=timezone.utc)
VANGUARD = b"""<html><title>FTSE All-World UCITS ETF</title><main>
<div>FTSE All-World UCITS ETF (USD) Accumulating</div>
<span>IE00BK5BQT80</span><h2>Historical Prices</h2>
<table><tr><th>Date</th><th>NAV (USD)</th></tr>
<tr><td>28 Oct 2026</td><td>US$191.5242</td></tr></table>
</main></html>"""
BONDSPOT = b"""<html><body><h1>TBSP.Index archive</h1>
<table><tr><td>2024-02-16</td><td>1966.95</td><td>1965.16</td></tr></table>
</body></html>"""


class OfficialSourceProbeTests(unittest.TestCase):
    def test_official_vanguard_nav_visibility_not_backtest_approval(self):
        r = parse_snapshot("vanguard_nav_usd_acc", VANGUARD,
                           retrieved_at=NOW)
        self.assertEqual(r["parse_status"], "SOURCE_PAGE_VISIBLE_CANDIDATE")
        self.assertTrue(r["nav_table_heading_detected"])
        self.assertTrue(r["source_identity_detected"])
        self.assertEqual(len(r["raw_sha256"]), 64)
        self.assertFalse(r["history_36_months_verified"])
        self.assertFalse(r["historical_first_usable_at_verified"])
        self.assertFalse(r["executable_price_verified"])
        self.assertEqual(r["research_backtest_status"], "NOT_RUN")

    def test_bondspot_parses_an_official_sample_not_tradable_security(self):
        r = parse_snapshot("bondspot_tbsp_total_return_benchmark", BONDSPOT,
                           retrieved_at=NOW)
        self.assertEqual(r["parse_status"], "SOURCE_PAGE_VISIBLE_CANDIDATE")
        self.assertEqual(r["sample"]["observed_for"], "2024-02-16")
        self.assertEqual(r["sample"]["closing"], "1965.16")
        self.assertEqual(r["sample"]["instrument_kind"], "NON_TRADABLE_INDEX")
        self.assertFalse(r["history_36_months_verified"])
        self.assertEqual(r["paper_events_created"], 0)
        self.assertEqual(r["financial_operations"], 0)

    def test_missing_visible_evidence_not_assumed_success(self):
        for key in ("vanguard_nav_usd_acc",
                    "bondspot_tbsp_total_return_benchmark"):
            r = parse_snapshot(key, b"<html>Archive temporarily unavailable</html>",
                               retrieved_at=NOW)
            self.assertEqual(r["parse_status"], "SOURCE_PAGE_UNVERIFIED")
            self.assertFalse(r["history_36_months_verified"])

    def test_source_redirect_to_nonofficial_host_rejected(self):
        for key in ("vanguard_nav_usd_acc",
                    "bondspot_tbsp_total_return_benchmark"):
            with self.assertRaisesRegex(ValueError, "host or protocol"):
                parse_snapshot(key, BONDSPOT,
                               final_url="https://unauthorized.example/price",
                               retrieved_at=NOW)

    def test_rejects_non_https_url_and_future_schema_fabrication(self):
        with self.assertRaises(ValueError):
            parse_snapshot("unexpected", VANGUARD, retrieved_at=NOW)
        with self.assertRaises(ValueError):
            parse_snapshot("vanguard_nav_usd_acc", VANGUARD,
                           final_url="http://www.vanguard.co.uk/x",
                           retrieved_at=NOW)
        with self.assertRaisesRegex(ValueError, "timestamp"):
            parse_snapshot("vanguard_nav_usd_acc", VANGUARD,
                           retrieved_at=datetime(2026, 11, 6))

    def test_live_fetch_mock_has_only_two_official_hosts(self):
        seen = []
        def stub(url):
            seen.append(url)
            raw = VANGUARD if "vanguard.co.uk" in url else BONDSPOT
            return raw, url

        result = probe(fetch=stub)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(seen), 2)
        self.assertEqual(
            {r["provider"] for r in result.values()},
            {"www.vanguard.co.uk", "www.bondspot.pl"})
        self.assertEqual(
            {r["research_backtest_status"] for r in result.values()},
            {"NOT_RUN"})


if __name__ == "__main__":
    unittest.main()
