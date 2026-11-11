import unittest
from datetime import datetime, timezone

from scripts.gus_cpi_normalize import normalize

URL = "https://publikacje.new.stat.gov.pl/portal-publikacje/miesieczne-wskazniki-cen-towarow-i-uslug-konsumpcyjnych-od-1982-r"
TIME = datetime(2026, 11, 5, 20, 0, tzinfo=timezone.utc)


def read(text, *, date="2026-10-14", url=URL):
    return normalize(text.encode("utf-8"), official_publication_url=url,
                     snapshot_published_on=date, retrieved_at=TIME)


class GUSCpiIntakeTests(unittest.TestCase):
    def test_valid_csv_and_polish_decimal(self):
        result = read("year;month;previous_month_100\n2026;08;100,2\n2026;09;99,9\n")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["observations"][0],
                         {"observed_for": "2026-08-31", "index_previous_month_100": "100.2"})
        self.assertEqual(result["missing_ranges"], [])
        self.assertEqual(result["source_basis"], "PREVIOUS_MONTH_100")
        self.assertEqual(len(result["normalized_export_sha256"]), 64)
        self.assertIsNone(result["official_raw_source_sha256"])
        self.assertFalse(result["historical_vintage_verified"])
        self.assertEqual(result["backtest"], "NOT_RUN")
        self.assertEqual(result["paper_events_created"], 0)

    def test_sorted_months_and_gaps_are_reported_not_filled(self):
        result = read("year;month;previous_month_100\n2026;09;99,9\n2026;07;100,1\n")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["missing_ranges"][0]["missing_months"], 1)

    def test_duplicate_month_fails(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            read("year;month;previous_month_100\n2026;09;100\n2026;9;101\n")

    def test_unknown_basis_cannot_silently_enter(self):
        with self.assertRaisesRegex(ValueError, "header"):
            read("year;month;year_on_year_100\n2026;09;100\n")

    def test_missing_and_invalid_values_fail(self):
        for value in ("", "0", "-1", "NaN", "Infinity", "100,2,3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                read(f"year;month;previous_month_100\n2026;09;{value}\n")

    def test_future_month_rejected(self):
        with self.assertRaisesRegex(ValueError, "after source snapshot"):
            read("year;month;previous_month_100\n2026;11;100\n")

    def test_wrong_domain_and_insecure_urls_rejected(self):
        for url in ("https://stat.gov.pl.evil.org/table", "http://stat.gov.pl/table",
                    "https://example.com/table"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "official HTTPS"):
                read("year;month;previous_month_100\n2026;09;100\n", url=url)

    def test_snapshot_must_precede_retrieval(self):
        with self.assertRaisesRegex(ValueError, "retrieval precedes"):
            read("year;month;previous_month_100\n2026;09;100\n", date="2026-12-01")

    def test_empty_rows_and_extra_column_rejected(self):
        for text in ("year;month;previous_month_100\n",
                     "year;month;previous_month_100\n2026;09;100;extra\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                read(text)

    def test_naive_retrieval_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            normalize(b"year;month;previous_month_100\n2026;09;100\n",
                      official_publication_url=URL, snapshot_published_on="2026-10-14",
                      retrieved_at=datetime(2026, 11, 5))


if __name__ == "__main__":
    unittest.main()
