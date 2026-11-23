"""Synthetic offline TBSP.Index original HTML verification (never HTTP)."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from scripts.tbsp_original_archive_intake_v12 import (
    TBSPArchiveBlocked, inspect_original_html, summarize_months, main,
)

NOW = datetime(2026, 11, 22, 11, tzinfo=timezone.utc)


def url(day: date):
    return ("https://www.bondspot.pl/tbsp_index_archive_en"
            f"?date={day:%Y%m%d}&month={day:%m}&year={day:%Y}")


def html(day: date, *, close="2238.09", duplicate=False, second_table=False):
    main = ("<table class='tab_01'><thead><tr><th>Date</th><th>Opening value</th>"
            "<th>Closing value</th></tr></thead><tbody>"
            f"<tr><td>{day}</td><td>2237.34</td><td>{close}</td></tr>")
    if duplicate:
        main += f"<tr><td>{day}</td><td>2237.34</td><td>{close}</td></tr>"
    main += "</tbody></table>"
    return ("<!DOCTYPE html><html><body><h2>TBSP.Index archive</h2>"
            "<div><table><tr><th>Closing value:</th></tr>"
            "<tr><td>9999.99</td></tr></table></div>"
            + main + (main if second_table else "") + "</body></html>").encode()


def last_business_day(year, month):
    last = date(year, month, calendar.monthrange(year, month)[1])
    while last.weekday() >= 5:
        last = last.fromordinal(last.toordinal() - 1)
    return last


def twelve_records():
    return [inspect_original_html(
        html(last_business_day(2025, m), close="120.00" if m == 12 else "100.00"),
        source_url=url(last_business_day(2025, m)), retrieved_at=NOW)
        for m in range(1, 13)]


class OriginalArchiveIntakeTests(unittest.TestCase):
    def test_official_archive_table_excludes_unrelated_sidebar_value(self):
        day = date(2026, 11, 16)
        raw = html(day)
        r = inspect_original_html(raw, source_url=url(day), retrieved_at=NOW)
        self.assertEqual(r["observed_for"], "2026-11-16")
        self.assertEqual(r["close"], "2238.09")
        self.assertEqual(r["opening"], "2237.34")
        self.assertEqual(r["raw_source_sha256"], sha256(raw).hexdigest())
        self.assertFalse(r["source_entitlement_verified"])
        self.assertFalse(r["historical_point_in_time_certified"])
        self.assertEqual(r["source_url"], url(day))

    def test_rejects_duplicate_table_or_extra_original_row(self):
        day = date(2026, 11, 16)
        for raw in (html(day, duplicate=True), html(day, second_table=True)):
            with self.subTest(size=len(raw)), self.assertRaises(TBSPArchiveBlocked):
                inspect_original_html(raw, source_url=url(day), retrieved_at=NOW)

    def test_url_date_must_agree_with_table_and_exact_official_host(self):
        day = date(2026, 11, 16)
        bad_urls = [url(date(2026, 11, 17)),
                    url(day).replace("www.bondspot.pl", "www.bondspot.pl.evil.test"),
                    url(day).replace("https://", "http://"), url(day) + "&extra=1",
                    url(day).replace("month=11", "month=10"),
                    url(day).replace("date=20261116", "date")]
        for address in bad_urls:
            with self.subTest(address=address), self.assertRaises(TBSPArchiveBlocked):
                inspect_original_html(html(day), source_url=address, retrieved_at=NOW)

    def test_bad_value_missing_table_and_naive_receipt_rejected(self):
        day = date(2026, 11, 16)
        for raw in (html(day, close="NaN"), html(day, close="0"),
                    html(day, close="-5"), html(day, close="1e3"),
                    html(day).replace(b"Closing value</th>", b"Highest price</th>"),
                    b"not HTML", b"<html>" + b"X" * 300001):
            with self.subTest(size=len(raw)), self.assertRaises(TBSPArchiveBlocked):
                inspect_original_html(raw, source_url=url(day), retrieved_at=NOW)
        with self.assertRaises(TBSPArchiveBlocked):
            inspect_original_html(html(day), source_url=url(day),
                                  retrieved_at=datetime(2026, 11, 23))

    def test_future_retrieval_timestamp_is_not_presented_as_observed_receipt(self):
        day = date(2026, 11, 16)
        with self.assertRaises(TBSPArchiveBlocked):
            inspect_original_html(html(day), source_url=url(day),
                                  retrieved_at=datetime(2030, 1, 1, tzinfo=timezone.utc))

    def test_monthly_sample_must_be_near_end_and_metadata_unpromoted(self):
        rows = twelve_records()
        changed = [dict(x) for x in rows]
        changed[0]["source_entitlement_verified"] = True
        with self.assertRaises(TBSPArchiveBlocked):
            summarize_months(changed)
        changed = [dict(x) for x in rows]
        changed[0]["observed_for"] = "2025-01-01"
        with self.assertRaises(TBSPArchiveBlocked):
            summarize_months(changed)

    def test_monthly_reference_requires_closed_month_near_end_and_no_gaps(self):
        rows = twelve_records()
        r = summarize_months(rows)
        self.assertEqual(r["months"], 12)
        self.assertEqual(r["hypothetical_contributions_pln"], "1200.00")
        self.assertEqual(r["index_unit_terminal_reference_pln"], "1420.00")
        self.assertEqual(r["difference_vs_contributions_pln"], "220.00")
        self.assertEqual(r["first_month"], "2025-01")
        self.assertEqual(r["last_month"], "2025-12")
        self.assertFalse(r["actual_last_trading_day_certified"])
        self.assertEqual(r["qualified_model_series"], [])
        self.assertEqual(r["m1_m2_m3"], "INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual(r["database_writes"], 0)
        with self.assertRaises(TBSPArchiveBlocked):
            summarize_months(rows[:11])
        with self.assertRaises(TBSPArchiveBlocked):
            summarize_months(rows[:5] + rows[6:])
        with self.assertRaises(TBSPArchiveBlocked):
            summarize_months(rows + rows[:1])

    def test_cli_uses_exact_hash_and_rejects_outside_file(self):
        rows = twelve_records()
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            files = []
            for row in rows:
                day = date.fromisoformat(row["observed_for"])
                filename = f"original-{day}.html"
                raw = html(day, close="120.00" if day.month == 12 else "100.00")
                (folder / filename).write_bytes(raw)
                files.append({"file": filename, "source_url": url(day),
                              "raw_source_sha256": sha256(raw).hexdigest()})
            manifest = folder / "manifest.json"
            manifest.write_text(json.dumps({"retrieved_at": NOW.isoformat(), "files": files}))
            out = folder / "out"
            self.assertEqual(main(["--manifest", str(manifest), "--out-dir", str(out)]), 0)
            self.assertEqual({f.name for f in out.iterdir()}, {"tbsp_reference_v12.json"})
            self.assertNotIn("2238.09", (out / "tbsp_reference_v12.json").read_text())
            files[0]["raw_source_sha256"] = "0" * 64
            manifest.write_text(json.dumps({"retrieved_at": NOW.isoformat(), "files": files}))
            with self.assertRaises(TBSPArchiveBlocked):
                main(["--manifest", str(manifest), "--out-dir", str(folder / "other")])
            self.assertFalse((folder / "other").exists())
            files[0]["file"] = "../outside.html"
            manifest.write_text(json.dumps({"retrieved_at": NOW.isoformat(), "files": files}))
            with self.assertRaises(TBSPArchiveBlocked):
                main(["--manifest", str(manifest), "--out-dir", str(folder / "third")])


if __name__ == "__main__":
    unittest.main()
