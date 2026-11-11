import unittest
from datetime import datetime, timezone

from scripts.verified_source_candidate_intake import validate_mapped_series

TIME = datetime(2026, 11, 5, 20, 0, tzinfo=timezone.utc)
V = "VANGUARD_ALL_WORLD_ACC_NAV_USD"
B = "BONDSPOT_TBSP_CLOSE_PLN"
V_URL = "https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating"
B_URL = "https://www.bondspot.pl/tbsp_index_archive_en"


def parse(data, series=V, source=None, original=None, retrieval=TIME):
    return validate_mapped_series(data.encode("utf-8"), series_id=series,
                                  official_url=source or (B_URL if series == B else V_URL),
                                  retrieved_at=retrieval, official_raw_bytes=original)


class SourceIntakeTests(unittest.TestCase):
    def test_nav_metadata_not_traded_price(self):
        r = parse("date,value\n2026-10-30,191.05\n2026-10-29,191.0100\n")
        self.assertEqual(r["identifier"], "IE00BK5BQT80")
        self.assertEqual(r["currency"], "USD")
        self.assertEqual(r["basis"], "FUND_ACCUMULATING_NAV")
        self.assertEqual(r["instrument_kind"], "FUND_SHARE_CLASS_NAV")
        self.assertEqual(r["observations"][0]["value"], "191.0100")
        self.assertEqual(r["observations_count"], 2)
        self.assertFalse(r["source_entitlement_verified"])
        self.assertFalse(r["historical_vintage_verified"])
        self.assertEqual(r["backtest"], "NOT_RUN")
        self.assertEqual(r["paper_events_created"], 0)

    def test_tbsp_is_pln_total_return_benchmark_not_etf(self):
        r = parse("date,value\n2026-10-29,2250.05\n", B)
        self.assertEqual(r["currency"], "PLN")
        self.assertEqual(r["instrument_kind"], "NON_TRADABLE_INDEX")
        self.assertEqual(r["basis"], "BOND_TOTAL_RETURN_BENCHMARK_INDEX")
        self.assertEqual(r["status"], "INSUFFICIENT_DATA")

    def test_disallowed_source_host_fails(self):
        for url in ("https://bondspot.pl.evil.org/data", "http://www.bondspot.pl/data",
                    "https://www.vanguard.co.uk/data"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "source host"):
                parse("date,value\n2026-10-29,100\n", B, source=url)

    def test_duplicate_and_bad_values_fail_closed(self):
        csvs = [
            "date,value\n2026-10-29,100\n2026-10-29,100\n",
            "date,value\n2026-10-29,NaN\n",
            "date,value\n2026-10-29,0\n",
            "date,value\n2026-10-29,-1\n",
            "date,value\n2026-10-29,1,000\n",
            "date,value\n2026-10-29,1e3\n",
            "date,value\n2026-10-29,1.2.3\n",
        ]
        for data in csvs:
            with self.subTest(csv=data), self.assertRaises(ValueError):
                parse(data)

    def test_future_and_before_inception_dates_fail(self):
        for stamp in ("2019-07-22", "2026-11-06"):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                parse(f"date,value\n{stamp},100\n")

    def test_monthly_missing_periods_are_explicit(self):
        r = parse("date,value\n2026-08-31,100\n2026-10-30,101\n")
        self.assertEqual(r["no_monthly_observations"], ["2026-09"])
        self.assertFalse(r["daily_trading_session_coverage_verified"])

    def test_hash_of_normalized_and_original_remain_separate(self):
        r = parse("date,value\n2026-10-29,100\n", original=b"original authorised copy")
        self.assertEqual(len(r["normalized_csv_sha256"]), 64)
        self.assertEqual(len(r["raw_source_sha256"]), 64)
        self.assertNotEqual(r["normalized_csv_sha256"], r["raw_source_sha256"])
        self.assertFalse(r["raw_to_normalized_mapping_independently_verified"])

    def test_omitted_raw_source_does_not_invent_hash(self):
        r = parse("date,value\n2026-10-29,100\n")
        self.assertIsNone(r["raw_source_sha256"])

    def test_unsupported_series_and_wrong_header_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown source identity"):
            parse("date,value\n2026-10-29,100\n", series="AGG")
        with self.assertRaisesRegex(ValueError, "header"):
            parse("date,market_price\n2026-10-29,100\n")

    def test_malformed_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            parse("date,value\n2026-10-29,100\n",
                  retrieval=datetime(2026, 11, 5))


if __name__ == "__main__":
    unittest.main()
