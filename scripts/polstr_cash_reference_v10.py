"""Bounded public POLSTR CI PDF -> non-executable monthly cash comparator.

Reconstructs only 2022-2025 observations from GPW Benchmark annual PDFs.
Pre-production data and current historical downloads are not PIT evidence.
There are no accounts, cash deposits, real orders, database calls or schedules.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Callable
from urllib.request import Request, urlopen


POLSTR_YEARS = (2022, 2023, 2024, 2025)
OFFICIAL_PDF_URL = (
    "https://www.gpwbenchmark.pl/pub/BENCHMARK/files/Dane/PDF/POLSTR_{year}.pdf"
)
SCHEMA = "ISL_POLSTR_CI_CASH_REFERENCE_V10"
MAX_PDF_BYTES = 2_000_000
MAX_TEXT_CHARS = 200_000
INDEX_ROW = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s+")
MONTHS = tuple(f"{year}-{month:02d}" for year in POLSTR_YEARS
               for month in range(1, 13))
CONTRIBUTION = Decimal("100")


class PolstrReferenceBlocked(ValueError):
    """Unqualified data, incomplete chronology or unbounded source."""


def _amount(raw: object, *, positive: bool) -> Decimal:
    if type(raw) is not str:
        raise PolstrReferenceBlocked("INVALID_INDEX_ROW")
    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise PolstrReferenceBlocked("INVALID_INDEX_ROW") from exc
    if not number.is_finite() or (positive and number <= 0):
        raise PolstrReferenceBlocked("INVALID_INDEX_ROW")
    return number


def _extract_pdf_text(raw: bytes) -> str:
    command = shutil.which("pdftotext")
    if command is None:
        raise PolstrReferenceBlocked("PDFTOTEXT_REQUIRED_FOR_OPTIONAL_SOURCE_READ")
    try:
        result = subprocess.run(
            [command, "-layout", "-", "-"], input=raw,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PolstrReferenceBlocked("PDF_EXTRACTION_UNAVAILABLE") from exc
    if result.returncode != 0 or len(result.stdout) > MAX_TEXT_CHARS:
        raise PolstrReferenceBlocked("PDF_EXTRACTION_UNAVAILABLE")
    try:
        return result.stdout.decode("utf-8")
    except UnicodeError as exc:
        raise PolstrReferenceBlocked("PDF_TEXT_ENCODING_INVALID") from exc


def inspect_official_year(raw: bytes, *, year: int,
                          extract_text: Callable[[bytes], str] = _extract_pdf_text) -> dict:
    """Accept the full official annual PDF with no silent missing-day fill."""
    if (type(raw) is not bytes or not raw.startswith(b"%PDF-")
            or not 32 <= len(raw) <= MAX_PDF_BYTES or year not in POLSTR_YEARS):
        raise PolstrReferenceBlocked("ORIGINAL_PDF_INVALID")
    rendered = extract_text(raw)
    if (type(rendered) is not str or not 0 < len(rendered) <= MAX_TEXT_CHARS
            or "POLSTR_CI" not in rendered or "Index Date" not in rendered):
        raise PolstrReferenceBlocked("PDF_TABLE_HEADER_MISSING")
    daily: dict[date, Decimal] = {}
    for line in rendered.splitlines():
        if not INDEX_ROW.match(line):
            continue
        cells = line.split()
        if len(cells) != 6:
            raise PolstrReferenceBlocked("INVALID_INDEX_ROW")
        try:
            day = date.fromisoformat(cells[0])
        except ValueError as exc:
            raise PolstrReferenceBlocked("INVALID_INDEX_ROW") from exc
        if day.year != year:
            raise PolstrReferenceBlocked("UNEXPECTED_INDEX_YEAR")
        if day.weekday() >= 5:
            raise PolstrReferenceBlocked("INDEX_ON_NON_BUSINESS_DAY")
        if day in daily:
            raise PolstrReferenceBlocked("DUPLICATE_INDEX_DATE")
        for cell in cells[1:5]:
            _amount(cell, positive=False)
        daily[day] = _amount(cells[5], positive=True)
    month_ends = []
    for month in range(1, 13):
        values = [(day, level) for day, level in daily.items() if day.month == month]
        if len(values) < 10 or max((day.day for day, _ in values), default=0) < 20:
            raise PolstrReferenceBlocked("MONTHLY_COVERAGE_INCOMPLETE")
        selected, level = max(values, key=lambda pair: pair[0])
        if calendar.monthrange(year, month)[1] - selected.day > 6:
            raise PolstrReferenceBlocked("MONTH_END_NOT_OBSERVED")
        month_ends.append({
            "month": f"{year}-{month:02d}",
            "observed_day": selected.isoformat(),
            "index_level": format(level, "f"),
        })
    return {
        "year": year, "source_url": OFFICIAL_PDF_URL.format(year=year),
        "source_sha256": sha256(raw).hexdigest(),
        "daily_observation_count": len(daily), "month_count": len(month_ends),
        "month_ends": month_ends,
    }


def indexed_contribution_reference(levels: list[Decimal]) -> dict:
    """A pure hypothetical index-unit comparator, not cash interest or fills."""
    if (type(levels) is not list or not 2 <= len(levels) <= 120 or
            any(type(value) is not Decimal or not value.is_finite() or value <= 0
                for value in levels)):
        raise PolstrReferenceBlocked("INVALID_MONTHLY_LEVELS")
    with localcontext() as ctx:
        ctx.prec = 48
        terminal = sum((CONTRIBUTION * levels[-1] / value for value in levels),
                       Decimal(0))
        total = CONTRIBUTION * len(levels)
    def money(value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), "f")
    return {
        "hypothetical_contributions_pln": money(total),
        "terminal_index_reference_pln": money(terminal),
        "difference_vs_nominal_cash_pln": money(terminal - total),
    }


def _official_fetch(url: str) -> bytes:
    if url not in {OFFICIAL_PDF_URL.format(year=y) for y in POLSTR_YEARS}:
        raise PolstrReferenceBlocked("OFFICIAL_URL_ALLOWLIST_REQUIRED")
    request = Request(url, headers={"User-Agent": "InvestmentStrategyLab/1.0 research"})
    with urlopen(request, timeout=25) as response:
        if response.geturl() != url:
            raise PolstrReferenceBlocked("OFFICIAL_REDIRECT_NOT_ACCEPTED")
        return response.read(MAX_PDF_BYTES + 1)


def observe_once(*, fetch: Callable[[str], bytes],
                 extract_text: Callable[[bytes], str] = _extract_pdf_text,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict:
    """Exactly four public official annual source reads, no retries or writes."""
    if not callable(fetch) or not callable(extract_text):
        raise PolstrReferenceBlocked("EXPLICIT_SOURCE_ADAPTERS_REQUIRED")
    started = clock()
    if (not isinstance(started, datetime) or started.tzinfo is None
            or started.utcoffset() is None):
        raise PolstrReferenceBlocked("UTC_AWARE_CLOCK_REQUIRED")
    parts = []
    for year in POLSTR_YEARS:
        url = OFFICIAL_PDF_URL.format(year=year)
        parts.append(inspect_official_year(fetch(url), year=year,
                                           extract_text=extract_text))
    completed = clock()
    if (not isinstance(completed, datetime) or completed.tzinfo is None
            or completed.utcoffset() is None or completed < started):
        raise PolstrReferenceBlocked("VALID_COMPLETION_CLOCK_REQUIRED")
    rows = [row for part in parts for row in part["month_ends"]]
    if [row["month"] for row in rows] != list(MONTHS):
        raise PolstrReferenceBlocked("NONCONSECUTIVE_MONTHLY_BENCHMARK")
    result = {
        "schema": SCHEMA,
        "status": "HISTORICAL_POLSTR_CI_REFERENCE_ONLY",
        "source_vintage": "HISTORICAL_RESEARCH_RECONSTRUCTION",
        "source": "GPW Benchmark POLSTR_CI annual historical PDFs",
        "started_at_utc": started.astimezone(timezone.utc).isoformat(),
        "completed_at_utc": completed.astimezone(timezone.utc).isoformat(),
        "years": list(POLSTR_YEARS),
        "months": len(rows),
        "first_month": rows[0]["month"], "last_month": rows[-1]["month"],
        "preproduction_months": sum(row["month"] < "2025-05" for row in rows),
        "source_reads": len(parts),
        "source_fingerprints_sha256": {
            str(part["year"]): part["source_sha256"] for part in parts
        },
        "source_daily_counts": {
            str(part["year"]): part["daily_observation_count"] for part in parts
        },
        "reference_semantics": "NON_EXECUTABLE_COMPOUNDED_OVERNIGHT_RATE_INDEX",
        **indexed_contribution_reference([
            _amount(row["index_level"], positive=True) for row in rows
        ]),
        "historical_pit_certified": False,
        "preproduction_is_historical_release": False,
        "executable_cash_account": False,
        "investment_performance_proven": False,
        "qualified_total_return_series": [],
        "m1_m2_m3": "INSUFFICIENT_DATA_HOLD_CASH",
        "financial_operations": 0, "database_writes": 0,
        "orders_sent": 0, "paper_events_created": 0,
        "warning": (
            "Retrospective, nominal PLN index-unit arithmetic only. POLSTR CI "
            "is not a deposit, a tradeable security, actual cash interest, "
            "a guaranteed yield or evidence of original publication timing. "
            "No taxes, account fees, trading costs or investable fills modeled."
        ),
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"))
    result["receipt_sha256"] = sha256(canonical.encode("utf-8")).hexdigest()
    return result


def render_markdown(report: dict) -> str:
    return (
        "# POLSTR CI — historyczny benchmark gotówkowy (nie transakcje)\n\n"
        f"- Lata: {report['first_month']}–{report['last_month']}; "
        f"{report['months']} miesięcy; {report['source_reads']} oficjalne PDF.\n"
        f"- Symulowane wpłaty: {report['hypothetical_contributions_pln']} PLN "
        "(100 PLN miesięcznie).\n"
        f"- Końcowa wartość umownych jednostek indeksu: "
        f"{report['terminal_index_reference_pln']} PLN.\n"
        f"- Różnica względem nominalnych wpłat: "
        f"{report['difference_vs_nominal_cash_pln']} PLN.\n"
        f"- Miesiące preprodukcyjne (do IV 2025): "
        f"{report['preproduction_months']}. Historyczna data udostępnienia "
        "konkretnych danych nieudowodniona.\n\n"
        "**Ograniczenie:** POLSTR CI nie jest depozytem ani osiągalną lokatą, "
        "wynik nie oznacza rzeczywistego oprocentowania rachunku. "
        "Nie obejmuje podatków, opłat ani kosztów. To rekonstrukcja; "
        "nie kwalifikuje danych do M1/M2/M3 ani operacji finansowych.\n\n"
        f"SHA pokwitowania: `{report['receipt_sha256']}`.\n"
    )


def main(argv: list[str] | None = None, *, fetch: Callable[[str], bytes] = _official_fetch,
         extract_text: Callable[[bytes], str] = _extract_pdf_text) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-official-read", action="store_true")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    if not args.allow_public_official_read:
        parser.error("EXPLICIT_PUBLIC_SOURCE_READ_OPT_IN_REQUIRED")
    target = Path(args.out_dir)
    if target.exists() or target.is_symlink():
        parser.error("OUT_DIR_MUST_NOT_EXIST")
    result = observe_once(fetch=fetch, extract_text=extract_text)
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (target / "polstr_reference_v10.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2, ensure_ascii=False)
        stream.write("\n")
    with (target / "polstr_reference_v10.md").open("x", encoding="utf-8") as stream:
        stream.write(render_markdown(result))
    print("ISL_POLSTR_CI_V10=" + json.dumps({
        "status": "PASS_REFERENCE_ONLY", "months": result["months"],
        "source_reads": result["source_reads"],
        "receipt_sha256": result["receipt_sha256"],
        "financial_operations": result["financial_operations"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
