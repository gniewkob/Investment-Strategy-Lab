"""Synthetic-only POLSTR CI PDF/benchmark acceptance; no network or trading."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from scripts.polstr_cash_reference_v10 import (
    POLSTR_YEARS, PolstrReferenceBlocked, inspect_official_year,
    indexed_contribution_reference, observe_once, main,
)


def year_text(year: int, *, missing_month=None, extra_line="") -> str:
    lines = ["Data Wskaźnika/", " Index Date   POLSTR POLSTR_1M POLSTR_3M POLSTR_6M POLSTR_CI"]
    for month in range(1, 13):
        if month == missing_month:
            continue
        found = 0
        day = date(year, month, 1)
        while day.month == month and found < 10:
            if day.weekday() < 5:
                ci = 100 + (year - 2022) * 12 + month
                lines.append(f" {day.isoformat()}   5.123 5.10000 5.20000 5.30000 {ci}.00000000")
                found += 1
            day += timedelta(days=1)
        # A later last trading date (still official shape) must win.
        last = date(year, month, 28)
        while last.weekday() > 4:
            last -= timedelta(days=1)
        lines.append(f" {last.isoformat()}   5.123 5.10000 5.20000 5.30000 "
                     f"{100 + (year - 2022) * 12 + month}.00000000")
    if extra_line:
        lines.append(extra_line)
    return "\n".join(lines)


def synthetic_pdf(year: int) -> bytes:
    return f"%PDF-1.7 SYNTHETIC_TEST_FIXTURE_POLSTR_{year}".encode()


def offline_adapters():
    reads = []

    def fetch(url):
        reads.append(url)
        year = int(url.removesuffix(".pdf").rsplit("_", 1)[1])
        return synthetic_pdf(year)

    def extract(raw):
        year = int(raw.decode()[-4:])
        return year_text(year)

    return fetch, extract, reads


class PolstrCashReferenceTests(unittest.TestCase):
    def test_exact_year_pdf_extraction_yields_last_observed_month_day(self):
        report = inspect_official_year(synthetic_pdf(2024), year=2024,
                                       extract_text=lambda _: year_text(2024))
        self.assertEqual(report["month_count"], 12)
        self.assertEqual(report["daily_observation_count"], 132)
        self.assertEqual(report["month_ends"][0], {
            "month": "2024-01", "observed_day": "2024-01-26", "index_level": "125.00000000"
        })
        self.assertEqual(report["month_ends"][-1]["index_level"], "136.00000000")

    def test_missing_month_or_forged_row_rejected_not_filled(self):
        for text, reason in (
            (year_text(2024, missing_month=3), "MONTHLY_COVERAGE_INCOMPLETE"),
            (year_text(2024, extra_line="2024-01-26 5 5 5 5 999.00000000"),
             "DUPLICATE_INDEX_DATE"),
            (year_text(2024, extra_line="2024-11-29 5 5 5 5 NaN"),
             "INVALID_INDEX_ROW"),
            (year_text(2024, extra_line="2025-01-02 5 5 5 5 999.00000000"),
             "UNEXPECTED_INDEX_YEAR"),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(
                    PolstrReferenceBlocked, reason):
                inspect_official_year(synthetic_pdf(2024), year=2024,
                                      extract_text=lambda _, t=text: t)

    def test_truncated_end_of_month_does_not_masquerade_as_month_end(self):
        shorter = year_text(2024).replace(
            "2024-01-26   5.123 5.10000 5.20000 5.30000 125.00000000",
            "2024-01-23   5.123 5.10000 5.20000 5.30000 125.00000000",
        )
        with self.assertRaisesRegex(PolstrReferenceBlocked, "MONTH_END_NOT_OBSERVED"):
            inspect_official_year(synthetic_pdf(2024), year=2024,
                                  extract_text=lambda _: shorter)

    def test_reference_accounting_uses_month_end_index_levels_not_real_cash(self):
        out = indexed_contribution_reference([Decimal("100"), Decimal("110")])
        self.assertEqual(out["hypothetical_contributions_pln"], "200.00")
        self.assertEqual(out["terminal_index_reference_pln"], "210.00")
        self.assertEqual(out["difference_vs_nominal_cash_pln"], "10.00")

    def test_four_years_official_urls_are_bounded_and_model_remains_hold(self):
        fetch, extract, reads = offline_adapters()
        result = observe_once(fetch=fetch, extract_text=extract)
        self.assertEqual(result["status"], "HISTORICAL_POLSTR_CI_REFERENCE_ONLY")
        self.assertEqual(result["months"], 48)
        self.assertEqual(result["hypothetical_contributions_pln"], "4800.00")
        self.assertEqual(result["preproduction_months"], 40)
        self.assertEqual(result["source_vintage"], "HISTORICAL_RESEARCH_RECONSTRUCTION")
        self.assertEqual(result["m1_m2_m3"], "INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual(result["qualified_total_return_series"], [])
        self.assertFalse(result["historical_pit_certified"])
        self.assertFalse(result["executable_cash_account"])
        self.assertFalse(result["investment_performance_proven"])
        self.assertEqual(result["financial_operations"], 0)
        self.assertEqual(result["database_writes"], 0)
        self.assertEqual(result["source_reads"], 4)
        self.assertEqual([int(url.split("_")[-1][:-4]) for url in reads], list(POLSTR_YEARS))
        self.assertNotIn("month_ends", result)
        self.assertEqual(len(result["source_fingerprints_sha256"]), 4)

    def test_retrieval_receipt_uses_clock_after_four_reads(self):
        fetch, extract, _ = offline_adapters()
        times = iter((datetime(2026, 11, 23, 10, tzinfo=timezone.utc),
                      datetime(2026, 11, 23, 10, 1, tzinfo=timezone.utc)))
        result = observe_once(fetch=fetch, extract_text=extract,
                              clock=lambda: next(times))
        self.assertEqual(result["started_at_utc"], "2026-11-23T10:00:00+00:00")
        self.assertEqual(result["completed_at_utc"], "2026-11-23T10:01:00+00:00")
        self.assertNotIn("retrieved_at_utc", result)

    def test_cli_requires_opt_in_and_refuses_existing_directory_before_read(self):
        fetch, extract, reads = offline_adapters()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "report"
            with self.assertRaises(SystemExit):
                main(["--out-dir", str(target)], fetch=fetch, extract_text=extract)
            self.assertEqual(reads, [])
            target.mkdir()
            with self.assertRaises(SystemExit):
                main(["--allow-public-official-read", "--out-dir", str(target)],
                     fetch=fetch, extract_text=extract)
            self.assertEqual(reads, [])

    def test_cli_writes_aggregate_only_after_four_validated_sources(self):
        fetch, extract, reads = offline_adapters()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "fresh"
            self.assertEqual(main(["--allow-public-official-read", "--out-dir", str(target)],
                                  fetch=fetch, extract_text=extract), 0)
            self.assertEqual(len(reads), 4)
            self.assertEqual({x.name for x in target.iterdir()},
                             {"polstr_reference_v10.json", "polstr_reference_v10.md"})
            result = json.loads((target / "polstr_reference_v10.json").read_text())
            self.assertEqual(result["months"], 48)
            self.assertNotIn("month_ends", json.dumps(result))
            md = (target / "polstr_reference_v10.md").read_text()
            self.assertIn("4800.00", md)
            self.assertIn("nie jest depozytem", md)


if __name__ == "__main__":
    unittest.main()
