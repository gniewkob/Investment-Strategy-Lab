"""Synthetic EIA HTML fixtures — never market data."""
import unittest
from datetime import datetime, timezone
from dataclasses import replace

from src.isl_v2.eia_sources import parse_snapshot, SourceFormatError


def fixture(release="10/15/2026", replace_cell=None, extra_row=""):
    base = [
        ("2026 Sep-21 to Sep-25", ["101.10", "101.20", "101.30", "101.40", "101.50"]),
        ("2026 Sep-28 to Oct- 2", ["102.10", "102.20", "102.30", "102.40", "102.50"]),
        ("2026 Oct- 5 to Oct- 9", ["103.10", "103.20", "103.30", "103.40", "103.50"]),
        ("2026 Oct-12 to Oct-16", ["104.10", "104.20", "104.30", "", ""]),
    ]
    if replace_cell:
        week, day, text = replace_cell
        base[week][1][day] = text
    rows = ["<tr><th>Week Of</th><th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th></tr>"]
    for label, cells in base:
        rows.append("<tr><td>" + label + "</td>" + "".join("<td>" + x + "</td>" for x in cells) + "</tr>")
    rows.append(extra_row)
    return ("<html><body><table>" + "".join(rows) + "</table><div>Release Date: " +
            release + "</div><div>Next Release Date: 10/21/2026</div></body></html>").encode()


NOW = datetime(2026, 10, 18, 8, 30, tzinfo=timezone.utc)


class EIASourceTests(unittest.TestCase):
    def test_parse_daily_rows_without_inventing_missing_quotes(self):
        parsed = parse_snapshot("brent", fixture(), NOW)
        self.assertEqual(len(parsed.observations), 18)
        self.assertEqual(parsed.release_day.isoformat(), "2026-10-15")
        self.assertEqual(parsed.observations[-1].observed_on.isoformat(), "2026-10-14")
        self.assertEqual(str(parsed.observations[-1].price), "104.30")
        self.assertEqual(parsed.raw_count, 18)
        self.assertEqual(len(parsed.sha256_hex), 64)

    def test_identical_fetch_same_document_fingerprint(self):
        a = parse_snapshot("brent", fixture(), NOW)
        b = parse_snapshot("brent", fixture(), NOW)
        self.assertEqual(a.sha256_hex, b.sha256_hex)
        self.assertEqual(a.observations, b.observations)

    def test_price_revision_changes_document_fingerprint(self):
        a = parse_snapshot("brent", fixture(), NOW)
        b = parse_snapshot("brent", fixture(replace_cell=(0, 0, "100.99")), NOW)
        self.assertNotEqual(a.sha256_hex, b.sha256_hex)
        self.assertNotEqual(a.observations[0].price, b.observations[0].price)

    def test_reject_future_dated_observation(self):
        with self.assertRaises(SourceFormatError):
            parse_snapshot("brent", fixture(replace_cell=(3, 3, "120.00")), NOW)

    def test_reject_malformed_numeric_quote(self):
        with self.assertRaises(SourceFormatError):
            parse_snapshot("brent", fixture(replace_cell=(1, 1, "OOPS")), NOW)

    def test_reject_missing_release_date(self):
        with self.assertRaises(SourceFormatError):
            parse_snapshot("brent", fixture(release="unknown"), NOW)

    def test_reject_conflicting_date(self):
        x = "<tr><td>2026 Oct- 5 to Oct- 9</td><td>10</td><td>10</td><td>10</td><td>10</td><td>10</td></tr>"
        with self.assertRaises(SourceFormatError):
            parse_snapshot("brent", fixture(extra_row=x), NOW)

    def test_limit_historical_backfill_without_data_fabrication(self):
        with self.assertRaises(SourceFormatError):
            parse_snapshot("brent", fixture(), NOW, max_age_days=1)

    def test_reject_unknown_source(self):
        with self.assertRaises(SourceFormatError):
            parse_snapshot("unlisted", fixture(), NOW)


if __name__ == "__main__":
    unittest.main()
