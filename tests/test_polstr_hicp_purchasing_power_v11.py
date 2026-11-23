"""Synthetic original-format acceptance; no HTTP, databases, or trades."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from scripts.polstr_hicp_purchasing_power_v11 import analyze_once, main, ReferenceBlocked

YEARS = (2022, 2023, 2024, 2025)
MONTHS = [f"{y}-{m:02d}" for y in YEARS for m in range(1, 13)]
NOW = datetime(2026, 11, 23, 11, tzinfo=timezone.utc)


def year_text(year, final_level="120.000"):
    lines = ["Index Date POLSTR POLSTR_1M POLSTR_3M POLSTR_6M POLSTR_CI"]
    for month in range(1, 13):
        day = date(year, month, 1)
        count = 0
        while day.month == month and count < 10:
            if day.weekday() < 5:
                level = final_level if (year, month) == (2025, 12) else "100.000"
                lines.append(f"{day} 5.0 5.0 5.0 5.0 {level}")
                count += 1
            day += timedelta(days=1)
        last = date(year, month, 28)
        while last.weekday() > 4:
            last -= timedelta(days=1)
        level = final_level if (year, month) == (2025, 12) else "100.000"
        lines.append(f"{last} 5.0 5.0 5.0 5.0 {level}")
    return "\n".join(lines)


def hicp(levels=None, geo="PL"):
    levels = [100] * 47 + [110] if levels is None else levels
    cats = {"freq": {"M": 0}, "unit": {"I25": 0},
            "coicop18": {"TOTAL": 0}, "geo": {geo: 0},
            "time": {m: i for i, m in enumerate(MONTHS)}}
    ids = list(cats)
    return {"version": "2.0", "class": "dataset", "source": "ESTAT",
            "updated": "2026-11-18T10:00:00Z", "id": ids,
            "size": [len(cats[k]) for k in ids],
            "dimension": {k: {"category": {"index": cats[k]}} for k in ids},
            "value": {str(i): v for i, v in enumerate(levels)}, "status": {}}


def adapters(payload=None, invalid_year=None, final_level="120.000"):
    calls = []
    def pdf(url):
        calls.append(("PDF", url))
        year = int(url.removesuffix(".pdf").rsplit("_", 1)[1])
        return b"bad" if year == invalid_year else b"%PDF-1.4 SYNTHETIC TEST ONLY 000000000000 " + str(year).encode()
    def extract(raw):
        return year_text(int(raw[-4:].decode()), final_level)
    def eurostat(url):
        calls.append(("HICP", url))
        return hicp() if payload is None else payload
    return pdf, eurostat, extract, calls


class PurchasingPowerTests(unittest.TestCase):
    def test_48_month_cashflows_and_hicp_comparator(self):
        pdf, hist, extract, calls = adapters()
        r = analyze_once(fetch_pdf=pdf, fetch_hicp=hist,
                         extract_pdf=extract, clock=lambda: NOW)
        self.assertEqual(r["hypothetical_nominal_contributions_pln"], "4800.00")
        self.assertEqual(r["polstr_ci_terminal_reference_pln"], "5740.00")
        self.assertEqual(r["hicp_matched_cashflows_at_end_pln"], "5270.00")
        self.assertEqual(r["difference_vs_hicp_matched_cashflows_pln"], "470.00")
        self.assertEqual(r["nominal_cash_shortfall_vs_hicp_pln"], "470.00")
        self.assertEqual(r["hicp_change_first_to_last_pct"], "10.00")
        self.assertEqual(r["preproduction_polstr_months"], 40)
        self.assertEqual([kind for kind, _ in calls], ["PDF"] * 4 + ["HICP"])
        self.assertIn("sinceTimePeriod=2022-01", calls[-1][1])
        self.assertIn("untilTimePeriod=2025-12", calls[-1][1])

    def test_exact_arithmetic_before_output_rounding(self):
        pdf, hist, extract, _ = adapters(
            payload=hicp([100] * 47 + [100.0001]), final_level="100.0002")
        r = analyze_once(fetch_pdf=pdf, fetch_hicp=hist,
                         extract_pdf=extract, clock=lambda: NOW)
        self.assertEqual(r["polstr_ci_terminal_reference_pln"], "4800.01")
        self.assertEqual(r["difference_vs_hicp_matched_cashflows_pln"], "0.00")

    def test_no_imputation_of_invalid_month_or_foreign_country(self):
        for data in (hicp([100] * 47 + [None]), hicp([100] * 47 + [-1]),
                     hicp([100] * 47), hicp(geo="DE")):
            with self.subTest(size=len(data["value"])), self.assertRaises(ReferenceBlocked):
                pdf, hist, extract, _ = adapters(payload=data)
                analyze_once(fetch_pdf=pdf, fetch_hicp=hist,
                             extract_pdf=extract, clock=lambda: NOW)

    def test_corrupt_pdf_stops_before_reading_hicp(self):
        pdf, hist, extract, calls = adapters(invalid_year=2023)
        with self.assertRaises(ReferenceBlocked):
            analyze_once(fetch_pdf=pdf, fetch_hicp=hist,
                         extract_pdf=extract, clock=lambda: NOW)
        self.assertEqual([kind for kind, _ in calls], ["PDF", "PDF"])

    def test_naive_clock_stops_before_any_fetch(self):
        pdf, hist, extract, calls = adapters()
        with self.assertRaises(ReferenceBlocked):
            analyze_once(fetch_pdf=pdf, fetch_hicp=hist,
                         extract_pdf=extract, clock=lambda: datetime(2026, 1, 1))
        self.assertEqual(calls, [])

    def test_receipt_remains_aggregate_not_tradable_or_pit(self):
        pdf, hist, extract, _ = adapters()
        r = analyze_once(fetch_pdf=pdf, fetch_hicp=hist,
                         extract_pdf=extract, clock=lambda: NOW)
        self.assertEqual(r["source_reads"], 5)
        self.assertFalse(r["historical_point_in_time_certified"])
        self.assertFalse(r["executable_investment_price"])
        self.assertFalse(r["investment_performance_proven"])
        self.assertEqual(r["qualified_total_return_series"], [])
        self.assertEqual(r["m1_m2_m3"], "INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual([r[k] for k in ("financial_operations", "database_writes", "orders_sent")], [0, 0, 0])
        self.assertEqual(len(r["polstr_source_sha256_by_year"]), 4)
        self.assertEqual(len(r["hicp_source_sha256"]), 64)
        self.assertNotIn("observations", json.dumps(r).lower())

    def test_cli_requires_opt_in_and_immutable_output(self):
        pdf, hist, extract, calls = adapters()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "report"
            with self.assertRaises(SystemExit):
                main(["--out-dir", str(out)], fetch_pdf=pdf, fetch_hicp=hist, extract_pdf=extract)
            out.mkdir()
            with self.assertRaises(SystemExit):
                main(["--allow-public-official-read", "--out-dir", str(out)],
                     fetch_pdf=pdf, fetch_hicp=hist, extract_pdf=extract)
        self.assertEqual(calls, [])

    def test_cli_writes_two_aggregate_files_only(self):
        pdf, hist, extract, calls = adapters()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "new"
            self.assertEqual(main(["--allow-public-official-read", "--out-dir", str(out)],
                                  fetch_pdf=pdf, fetch_hicp=hist,
                                  extract_pdf=extract, clock=lambda: NOW), 0)
            self.assertEqual(len(calls), 5)
            self.assertEqual({p.name for p in out.iterdir()},
                             {"polstr_hicp_reference_v11.json", "polstr_hicp_reference_v11.md"})
            self.assertIn("nie jest", (out / "polstr_hicp_reference_v11.md").read_text())
            self.assertNotIn("observations", (out / "polstr_hicp_reference_v11.json").read_text())


if __name__ == "__main__":
    unittest.main()
