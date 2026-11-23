"""Independent official NBP annual Table A archive FX reference, never TR/PIT.

The source is one original yearly public CSV snapshot, not NBP API JSON. It
provides Table A published dates and PLN middle reference quotations only.
No first-release time, investor return, FX execution, broker or DB access.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
import re
from urllib.request import Request, urlopen


SCHEMA = "ISL_NBP_TABLE_A_OFFICIAL_YEAR_CSV_V09"
ARCHIVE_URL = "https://static.nbp.pl/dane/kursy/Archiwum/archiwum_tab_a_2026.csv"
MAX_SOURCE_BYTES = 500_000
MAX_YEAR_ROWS = 300
SEPTEMBER = "2026-09"


class ArchiveBlocked(ValueError):
    """Unqualified, malformed or incomplete official archive reference."""


def _rate(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,6},\d{1,6}", value):
        raise ArchiveBlocked("INVALID_MID_FX_QUOTATION")
    try:
        number = Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise ArchiveBlocked("INVALID_MID_FX_QUOTATION") from exc
    if not number.is_finite() or number <= 0 or number > 1000:
        raise ArchiveBlocked("INVALID_MID_FX_QUOTATION")
    return str(number)


def inspect_archive(raw: bytes, *, observed_at: datetime) -> dict:
    if (type(raw) is not bytes or not 0 < len(raw) <= MAX_SOURCE_BYTES
            or not isinstance(observed_at, datetime) or observed_at.tzinfo is None
            or observed_at.utcoffset() is None):
        raise ArchiveBlocked("BOUNDED_RAW_CSV_AND_UTC_CLOCK_REQUIRED")
    observed = observed_at.astimezone(timezone.utc)
    if observed.date() < date(2026, 9, 30):
        raise ArchiveBlocked("FUTURE_REFERENCE_MONTH")
    try:
        lines = list(csv.reader(StringIO(raw.decode("cp1250")), delimiter=";"))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ArchiveBlocked("INVALID_ORIGINAL_CSV") from exc
    if not 3 <= len(lines) <= MAX_YEAR_ROWS + 6:
        raise ArchiveBlocked("ANNUAL_SOURCE_ROW_COUNT_INVALID")
    columns = lines[0]
    if (not columns or columns[0] != "data"
            or any(columns.count(field) != 1 for field in
                   ("1USD", "1EUR", "nr tabeli", "pełny numer tabeli"))):
        raise ArchiveBlocked("UNSUPPORTED_TABLE_A_ARCHIVE_COLUMNS")
    usd, eur = columns.index("1USD"), columns.index("1EUR")
    serial, full = columns.index("nr tabeli"), columns.index("pełny numer tabeli")
    if serial + 1 != full or full != len(columns) - 2 or columns[-1] != "":
        raise ArchiveBlocked("UNSUPPORTED_TABLE_A_ARCHIVE_COLUMNS")
    market_rows = lines[2:]
    if [] in market_rows:
        end = market_rows.index([])
        footer = market_rows[end + 1:]
        if ([row[0] if row else None for row in footer] !=
                ["kod ISO", "nazwa waluty", "liczba jednostek"]
                or any(len(row) != len(columns) - 2 for row in footer)):
            raise ArchiveBlocked("UNEXPECTED_OFFICIAL_ARCHIVE_FOOTER")
        market_rows = market_rows[:end]
    if not 1 <= len(market_rows) <= MAX_YEAR_ROWS:
        raise ArchiveBlocked("ANNUAL_SOURCE_ROW_COUNT_INVALID")
    chosen = []
    last_date = None
    for row in market_rows:
        if len(row) != len(columns) or not re.fullmatch(r"2026\d{4}", row[0]):
            raise ArchiveBlocked("MALFORMED_OR_UNEXPECTED_CSV_ROW")
        try:
            published = date.fromisoformat(
                row[0][:4] + "-" + row[0][4:6] + "-" + row[0][6:])
        except ValueError as exc:
            raise ArchiveBlocked("INVALID_OFFICIAL_TABLE_DATE") from exc
        if (last_date is not None and published <= last_date
                or published > observed.date()):
            raise ArchiveBlocked("DUPLICATE_NONCHRONOLOGICAL_OR_FUTURE_DATE")
        last_date = published
        if not row[serial].isdigit() or not 1 <= int(row[serial]) <= 300:
            raise ArchiveBlocked("WRONG_TABLE_A_SERIAL")
        if row[full] != f"{int(row[serial]):03d}/A/NBP/2026":
            raise ArchiveBlocked("WRONG_TABLE_A_IDENTIFIER")
        if published.strftime("%Y-%m") == SEPTEMBER:
            chosen.append((published, _rate(row[usd]), _rate(row[eur])))
    if not 1 <= len(chosen) <= 22:
        raise ArchiveBlocked("MISSING_OR_OVERSIZED_SEPTEMBER_WINDOW")
    return {
        "schema": SCHEMA,
        "source": "NBP",
        "source_url": ARCHIVE_URL,
        "original_csv_sha256": sha256(raw).hexdigest(),
        "retrieved_at_utc": observed.isoformat(),
        "year": 2026,
        "reference_month": SEPTEMBER,
        "september_2026_days": len(chosen),
        "first_publication_date": chosen[0][0].isoformat(),
        "last_publication_date": chosen[-1][0].isoformat(),
        "latest_usdpln_mid": chosen[-1][1],
        "latest_eurpln_mid": chosen[-1][2],
        "basis": "OFFICIAL_TABLE_A_MID_FX_REFERENCE_NOT_EXECUTABLE_PRICE",
        "historical_pit_certified": False,
        "historic_first_release_time_verified": False,
        "total_return_qualified": False,
        "license_status": "UNVERIFIED",
        "database_writes": 0,
        "financial_operations": 0,
        "orders_sent": 0,
    }


def fetch_official(url: str) -> bytes:
    if url != ARCHIVE_URL:
        raise ArchiveBlocked("UNEXPECTED_OFFICIAL_NBP_SOURCE")
    request = Request(url, headers={
        "Accept": "text/csv,application/octet-stream",
        "User-Agent": "Investment-Strategy-Lab-read-only-archive/0.9",
    })
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise ArchiveBlocked("OFFICIAL_SOURCE_NOT_HTTP_200")
        raw = response.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ArchiveBlocked("ORIGINAL_ARCHIVE_TOO_LARGE")
    return raw


def observe_once(*, fetch=None,
                 clock=lambda: datetime.now(timezone.utc)) -> dict:
    if fetch is None:
        raise ArchiveBlocked("EXPLICIT_PUBLIC_SOURCE_FETCH_REQUIRED")
    started = clock()
    if not isinstance(started, datetime) or started.tzinfo is None or started.utcoffset() is None:
        raise ArchiveBlocked("UTC_AWARE_CLOCK_REQUIRED")
    return inspect_archive(fetch(ARCHIVE_URL), observed_at=clock())
