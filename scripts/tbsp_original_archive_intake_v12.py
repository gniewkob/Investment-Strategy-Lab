"""Offline verification of independently obtained official TBSP.Index HTML.

Never downloads, redistributes or treats BondSpot/GPW Benchmark index values
as executable bond prices. Input files must have been acquired lawfully by the
operator; a successful raw-file mapping does not confer source-entitlement,
original point-in-time publication or last-trading-day certification.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

ARCHIVE = "https://www.bondspot.pl/tbsp_index_archive_en"
SCHEMA = "ISL_TBSP_ORIGINAL_HTML_OFFLINE_V12"
MAX_HTML_BYTES = 300_000
MAX_MANIFEST_BYTES = 40_000
MAX_SAMPLES = 60
HEAD = ["Date", "Opening value", "Closing value"]
NUMBER = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


class TBSPArchiveBlocked(ValueError):
    """One original archive observation cannot be independently validated."""


class _ArchiveTables(HTMLParser):
    """Read structural table cells, never sidebar totals or regex matches."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.tables = []
        self.rows = None
        self.row = None
        self.cell = None
        self.cell_tag = None
        self.in_heading = False
        self.heading = []
        self.page_headings = []

    def handle_starttag(self, tag, attrs):
        if tag == "h2":
            self.in_heading = True
            self.heading = []
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.rows = []
        elif tag == "tr" and self.depth == 1:
            self.row = []
        elif tag in ("th", "td") and self.depth == 1 and self.row is not None:
            self.cell = []
            self.cell_tag = tag

    def handle_data(self, data):
        if self.in_heading:
            self.heading.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "h2" and self.in_heading:
            self.page_headings.append(" ".join("".join(self.heading).split()))
            self.in_heading = False
        if (tag in ("th", "td") and self.depth == 1
                and self.row is not None and self.cell is not None):
            self.row.append((self.cell_tag, " ".join("".join(self.cell).split())))
            self.cell = None
        elif tag == "tr" and self.depth == 1 and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table" and self.depth:
            self.depth -= 1
            if self.depth == 0:
                self.tables.append(self.rows)
                self.rows = None


def _source_date(source_url):
    if type(source_url) is not str:
        raise TBSPArchiveBlocked("EXACT_OFFICIAL_SOURCE_URL_REQUIRED")
    url = urlsplit(source_url)
    if (url.scheme != "https" or url.netloc != "www.bondspot.pl"
            or url.path != "/tbsp_index_archive_en" or url.fragment):
        raise TBSPArchiveBlocked("EXACT_OFFICIAL_SOURCE_URL_REQUIRED")
    try:
        args = parse_qs(url.query, strict_parsing=True, keep_blank_values=True)
    except ValueError as exc:
        raise TBSPArchiveBlocked("ORIGINAL_ARCHIVE_DATE_PARAMETERS_REQUIRED") from exc
    if set(args) != {"date", "month", "year"} or any(len(v) != 1 for v in args.values()):
        raise TBSPArchiveBlocked("ORIGINAL_ARCHIVE_DATE_PARAMETERS_REQUIRED")
    val = args["date"][0]
    if not re.fullmatch(r"[0-9]{8}", val):
        raise TBSPArchiveBlocked("ORIGINAL_ARCHIVE_DATE_PARAMETERS_REQUIRED")
    try:
        day = date(int(val[:4]), int(val[4:6]), int(val[6:]))
    except ValueError as exc:
        raise TBSPArchiveBlocked("INVALID_ARCHIVE_CALENDAR_DAY") from exc
    if args["month"][0] != f"{day:%m}" or args["year"][0] != f"{day:%Y}":
        raise TBSPArchiveBlocked("ARCHIVE_DATE_MONTH_YEAR_MISMATCH")
    return day


def _number(value):
    if type(value) is not str or not NUMBER.fullmatch(value):
        raise TBSPArchiveBlocked("INVALID_INDEX_LEVEL")
    try:
        n = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise TBSPArchiveBlocked("INVALID_INDEX_LEVEL") from exc
    if not n.is_finite() or n <= 0:
        raise TBSPArchiveBlocked("INVALID_INDEX_LEVEL")
    return format(n, "f")


def inspect_original_html(raw: bytes, *, source_url: str,
                          retrieved_at: datetime) -> dict:
    """One official page, one archive row, original byte SHA, no network."""
    day = _source_date(source_url)
    if (not isinstance(retrieved_at, datetime) or retrieved_at.tzinfo is None
            or retrieved_at.utcoffset() is None
            or retrieved_at.astimezone(timezone.utc) > datetime.now(timezone.utc)
            or day > retrieved_at.astimezone(timezone.utc).date()
            or day.weekday() >= 5):
        raise TBSPArchiveBlocked("VALID_AWARE_RETRIEVAL_AND_BUSINESS_DATE_REQUIRED")
    if (type(raw) is not bytes or not 120 <= len(raw) <= MAX_HTML_BYTES
            or b"<html" not in raw.lower()):
        raise TBSPArchiveBlocked("BOUNDED_ORIGINAL_HTML_REQUIRED")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise TBSPArchiveBlocked("ORIGINAL_HTML_NOT_UTF8") from exc
    parser = _ArchiveTables()
    parser.feed(text)
    parser.close()
    if "TBSP.Index archive" not in parser.page_headings:
        raise TBSPArchiveBlocked("OFFICIAL_ARCHIVE_HEADING_MISSING")
    matching = [table for table in parser.tables
                if any([value for tag, value in row if tag == "th"] == HEAD
                       for row in table)]
    if len(matching) != 1 or len(matching[0]) != 2:
        raise TBSPArchiveBlocked("UNIQUE_ARCHIVE_TABLE_REQUIRED")
    table = matching[0]
    if (table[0] != [("th", x) for x in HEAD]
            or len(table[1]) != 3 or any(tag != "td" for tag, _ in table[1])):
        raise TBSPArchiveBlocked("ARCHIVE_TABLE_SHAPE_CHANGED")
    cells = [value for _, value in table[1]]
    if cells[0] != day.isoformat():
        raise TBSPArchiveBlocked("ARCHIVE_ROW_DATE_MISMATCH")
    return {
        "source": "BONDSPOT_OFFICIAL_ARCHIVE", "identifier": "TBSP.Index",
        "instrument_kind": "NON_TRADABLE_INDEX",
        "return_basis": "BOND_TOTAL_RETURN_BENCHMARK_INDEX",
        "currency": "PLN", "observed_for": day.isoformat(),
        "month": day.strftime("%Y-%m"),
        "opening": _number(cells[1]), "close": _number(cells[2]),
        "source_url": source_url, "raw_source_sha256": sha256(raw).hexdigest(),
        "retrieved_at_utc": retrieved_at.astimezone(timezone.utc).isoformat(),
        "source_entitlement_verified": False,
        "historical_point_in_time_certified": False,
        "actual_last_trading_day_certified": False,
    }


def _next_month(month):
    year, m = map(int, month.split("-"))
    return f"{year + (m == 12):04d}-{m % 12 + 1:02d}"


def summarize_months(observations: list[dict]) -> dict:
    """Hypothetical units, *sampled* near month-end, not executable fills."""
    if (type(observations) is not list or not 12 <= len(observations) <= MAX_SAMPLES):
        raise TBSPArchiveBlocked("TWELVE_TO_SIXTY_MONTHLY_ORIGINALS_REQUIRED")
    rows = sorted(observations, key=lambda r: r.get("observed_for", ""))
    for index, row in enumerate(rows):
        try:
            day = date.fromisoformat(row["observed_for"])
        except (KeyError, ValueError, TypeError) as exc:
            raise TBSPArchiveBlocked("INVALID_ORIGINAL_SAMPLE_DATE") from exc
        month = day.strftime("%Y-%m")
        if (day.weekday() >= 5
                or calendar.monthrange(day.year, day.month)[1] - day.day > 7
                or row.get("month") != month
                or row.get("identifier") != "TBSP.Index"
                or row.get("instrument_kind") != "NON_TRADABLE_INDEX"
                or row.get("return_basis") != "BOND_TOTAL_RETURN_BENCHMARK_INDEX"
                or row.get("currency") != "PLN"
                or row.get("source_entitlement_verified") is not False
                or row.get("historical_point_in_time_certified") is not False
                or row.get("actual_last_trading_day_certified") is not False
                or not isinstance(row.get("raw_source_sha256"), str)
                or not SHA.fullmatch(row["raw_source_sha256"])
                or _source_date(row.get("source_url")) != day):
            raise TBSPArchiveBlocked("UNQUALIFIED_OR_NOT_NEAR_MONTH_END")
        if index and _next_month(rows[index - 1]["month"]) != month:
            raise TBSPArchiveBlocked("MISSING_OR_DUPLICATE_MONTH")
    levels = [Decimal(_number(row["close"])) for row in rows]
    with localcontext() as ctx:
        ctx.prec = 48
        final = sum((Decimal(100) * levels[-1] / level for level in levels), Decimal(0))
    report = {
        "schema": SCHEMA,
        "status": "SAMPLED_TBSP_INDEX_REFERENCE_NO_EXECUTION_OR_PIT",
        "first_month": rows[0]["month"], "last_month": rows[-1]["month"],
        "months": len(rows), "original_page_count": len(rows),
        "source": "BondSpot archived TBSP.Index close HTML, offline original copy",
        "reference_semantics": "PLN_TOTAL_RETURN_GOV_BOND_INDEX_NON_TRADABLE",
        "source_sha256_by_month": {row["month"]: row["raw_source_sha256"] for row in rows},
        "hypothetical_contributions_pln": f"{Decimal(100) * len(rows):.2f}",
        "index_unit_terminal_reference_pln": f"{final:.2f}",
        "difference_vs_contributions_pln": f"{(final - Decimal(100) * len(rows)):.2f}",
        "source_entitlement_verified": False,
        "historical_point_in_time_certified": False,
        "actual_last_trading_day_certified": False,
        "qualified_model_series": [], "m1_m2_m3": "INSUFFICIENT_DATA_HOLD_CASH",
        "financial_operations": 0, "database_writes": 0,
        "orders_sent": 0, "paper_events_created": 0,
        "warning": (
            "Offline original page mapping is not a licence grant, independent "
            "historical vintage or proof the selected dates were actual month-end "
            "closes. The TBSP.Index is not a purchasable bond, ETF or fill. "
            "No fees/taxes, no historical PIT admission, no real trading."
        ),
    }
    report["receipt_sha256"] = sha256(json.dumps(
        report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return report


def _read_regular(path, limit):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise TBSPArchiveBlocked("BOUNDED_REGULAR_ORIGINAL_FILE_REQUIRED")
    raw = path.read_bytes()
    if len(raw) > limit:
        raise TBSPArchiveBlocked("BOUNDED_REGULAR_ORIGINAL_FILE_REQUIRED")
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out_dir.exists() or args.out_dir.is_symlink():
        parser.error("OUT_DIR_MUST_NOT_EXIST")
    try:
        manifest = json.loads(_read_regular(args.manifest, MAX_MANIFEST_BYTES))
    except (ValueError, UnicodeError) as exc:
        raise TBSPArchiveBlocked("INVALID_OFFLINE_MANIFEST") from exc
    if (not isinstance(manifest, dict)
            or set(manifest) != {"retrieved_at", "files"}
            or not isinstance(manifest["files"], list)
            or not 12 <= len(manifest["files"]) <= MAX_SAMPLES):
        raise TBSPArchiveBlocked("INVALID_OFFLINE_MANIFEST")
    try:
        timestamp = datetime.fromisoformat(manifest["retrieved_at"])
    except (TypeError, ValueError) as exc:
        raise TBSPArchiveBlocked("INVALID_OFFLINE_RETRIEVAL_CLOCK") from exc
    observations = []
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or set(entry) != {"file", "source_url", "raw_source_sha256"}:
            raise TBSPArchiveBlocked("INVALID_ORIGINAL_FILE_RECEIPT")
        filename = entry["file"]
        if (type(filename) is not str or not filename
                or Path(filename).name != filename or filename in (".", "..")):
            raise TBSPArchiveBlocked("SAME_DIRECTORY_ORIGINAL_FILES_ONLY")
        raw = _read_regular(args.manifest.parent / filename, MAX_HTML_BYTES)
        if entry["raw_source_sha256"] != sha256(raw).hexdigest():
            raise TBSPArchiveBlocked("ORIGINAL_HTML_SHA_MISMATCH")
        observations.append(inspect_original_html(
            raw, source_url=entry["source_url"], retrieved_at=timestamp))
    report = summarize_months(observations)
    args.out_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (args.out_dir / "tbsp_reference_v12.json").open("x", encoding="utf-8") as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write("\n")
    print("ISL_TBSP_V12=" + json.dumps({
        "status": "SYNTHETIC_OR_AUTHORIZED_OFFLINE_REFERENCE_ONLY",
        "months": report["months"], "receipt_sha256": report["receipt_sha256"],
        "financial_operations": 0, "database_writes": 0,
    }, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
