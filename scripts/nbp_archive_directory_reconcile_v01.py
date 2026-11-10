"""I7: OFFLINE cross-check of NBP API date/number against archive dirYYYY.txt.

NBP's published filename convention is documented at:
https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/instrukcja-pobierania-kursow-walut/

This verifies consistency between TWO locally supplied records, NOT whether
those records came from NBP, were historically published at a precise hour,
were available to a past model, or may be used under any particular licence.

Research-only: no FX values in output, source collection, database or trading.
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from scripts.nbp_publication_lag_offline_v01 import (
    NBPDateLagError, MAX_INPUT_BYTES as API_LIMIT, _read_local,
    assess_nbp_publication_lag,
)

SCHEMA = "ISL_I7_NBP_ARCHIVE_DIRECTORY_CONSISTENCY_V01"
MAX_DIRECTORY_BYTES = 180_000
MAX_DIRECTORY_ENTRIES = 6000
MIN_ARCHIVE_YEAR = 2002
MAX_ARCHIVE_YEAR = 2099
FILENAME_RE = re.compile(r"^([abch])([0-9]{3})z([0-9]{2})([0-9]{2})([0-9]{2})$")
API_NUMBER_RE = re.compile(r"^([0-9]{1,3})/A/NBP/([0-9]{4})$")


class NBPDirectoryError(ValueError):
    """Offline evidence is inconsistent or cannot be safely inspected."""


def _canonical(obj: object) -> bytes:
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise NBPDirectoryError("canonical metadata receipt required") from exc


def _year(value: object) -> int:
    if type(value) is not int or not MIN_ARCHIVE_YEAR <= value <= MAX_ARCHIVE_YEAR:
        raise NBPDirectoryError("explicit bounded archive year required")
    return value


def _archive_inventory(raw: bytes, *, year: int) -> dict[date, int]:
    """Parse exact NBP names; keep ONLY table A entries, no exchange rates."""
    year = _year(year)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_DIRECTORY_BYTES:
        raise NBPDirectoryError("bounded nonempty local dirYYYY.txt bytes required")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise NBPDirectoryError("NBP archive names must be ASCII") from exc
    lines = [line.strip() for line in text.splitlines()]
    if not lines or len(lines) > MAX_DIRECTORY_ENTRIES or any(not line for line in lines):
        raise NBPDirectoryError("empty, invalid or oversized archive inventory")
    seen_names = set()
    dates: dict[date, int] = {}
    for name in lines:
        match = FILENAME_RE.fullmatch(name)
        if match is None:
            raise NBPDirectoryError("unknown NBP archive filename syntax")
        if name in seen_names:
            raise NBPDirectoryError("duplicate NBP archive filename")
        seen_names.add(name)
        table, number, yy, mm, dd = match.groups()
        if yy != f"{year % 100:02d}":
            raise NBPDirectoryError("archive entry belongs to different year")
        try:
            observed = date(year, int(mm), int(dd))
        except ValueError as exc:
            raise NBPDirectoryError("invalid archive filename publication date") from exc
        if table == "a":
            if observed in dates:
                raise NBPDirectoryError("multiple table A numbers for one date")
            dates[observed] = int(number)
    if not dates:
        raise NBPDirectoryError("no official Table A publication filenames in directory")
    return dates


def reconcile_archive(snapshot: object, inventory_bytes: bytes, *,
                      archive_year: int, requested_effective_date: str,
                      decision_at_utc: str) -> dict:
    """Compare NBP metadata with archive directory; no source is certified."""
    year = _year(archive_year)
    # The previously reviewed I6 validator checks the API payload and
    # applies the conservative next-UTC-day date-only decision rule.
    try:
        lag = assess_nbp_publication_lag(
            snapshot,
            requested_effective_date=requested_effective_date,
            decision_at_utc=decision_at_utc,
        )
    except NBPDateLagError as exc:
        raise NBPDirectoryError("invalid NBP local JSON or chronology") from exc
    requested = date.fromisoformat(lag["requested_effective_date"])
    if requested.year != year:
        raise NBPDirectoryError("archive year and requested date disagree")
    if any(date.fromisoformat(row["effectiveDate"]).year != year
           for row in snapshot["rates"]):
        raise NBPDirectoryError("split cross-year API windows before archive comparison")

    names_by_day = _archive_inventory(inventory_bytes, year=year)
    exact, absent, number_mismatch = 0, 0, 0
    selected_consistent = False
    for row in snapshot["rates"]:
        day = date.fromisoformat(row["effectiveDate"])
        found = names_by_day.get(day)
        if found is None:
            absent += 1
        else:
            api_number_match = API_NUMBER_RE.fullmatch(row["no"])
            if api_number_match is None:
                raise NBPDirectoryError("invalid API table publication number")
            number = int(api_number_match.group(1))
            if number != found:
                number_mismatch += 1
            else:
                exact += 1
                if day == requested:
                    selected_consistent = True

    if not lag["exact_publication_date_present"]:
        status = "REQUESTED_DATE_NOT_IN_API_WINDOW"
    elif not selected_consistent:
        status = "REQUESTED_DATE_NOT_MATCHED_TO_ARCHIVE"
    elif absent or number_mismatch:
        status = "ARCHIVE_RECONCILIATION_INCOMPLETE"
    elif lag["status"] != "DATE_LAG_PASSED_NOT_HISTORICAL_PIT_CERTIFIED":
        status = "CONSERVATIVE_DATE_LAG_NOT_PASSED"
    else:
        status = "LOCAL_RECORDS_CONSISTENT_PIT_AND_RIGHTS_UNVERIFIED"

    output = {
        "schema": SCHEMA,
        "status": status,
        "source_kind": "NBP_TABLE_A_USDPLN_REFERENCE_METADATA_ONLY",
        "archive_year": year,
        "requested_effective_date": lag["requested_effective_date"],
        "decision_at_utc": lag["decision_at_utc"],
        "research_not_before_utc": lag["research_not_before_utc"],
        "api_snapshot_canonical_sha256": lag["canonical_local_snapshot_sha256"],
        "archive_directory_local_sha256": sha256(inventory_bytes).hexdigest(),
        "nbp_i6_lag_receipt_sha256": lag["receipt_sha256"],
        "api_rows_examined": len(snapshot["rates"]),
        "directory_table_a_dates": len(names_by_day),
        "identical_table_a_day_and_number_pairs": exact,
        "api_dates_missing_in_directory": absent,
        "api_table_numbers_mismatched": number_mismatch,
        "requested_date_cross_checked": selected_consistent,
        "same_day_use_allowed": False,
        "source_records_independently_authenticated": False,
        "historical_first_publication_timestamp_certified": False,
        "source_rights_independently_authorized": False,
        "price_levels_exported": False,
        "nbp_fx_values_exported": False,
        "fx_conversion_performed": False,
        "total_return_series_qualified": False,
        "qualified_model_series": [],
        "paper_candidates": [],
        "model_state": "HOLD_CASH",
        "market_execution_authorized": False,
        "source_manifest_created": False,
        "orders_sent": 0,
        "paper_fills": 0,
        "financial_operations": 0,
        "database_writes": 0,
    }
    output["receipt_sha256"] = sha256(_canonical(output)).hexdigest()
    return output


def _read_directory(path: Path, year: int) -> bytes:
    year = _year(year)
    if path.name != f"dir{year}.txt":
        raise NBPDirectoryError("local file must be named dirYYYY.txt for the requested year")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_DIRECTORY_BYTES:
        raise NBPDirectoryError("bounded regular archive directory required")
    raw = path.read_bytes()
    if len(raw) > MAX_DIRECTORY_BYTES:
        raise NBPDirectoryError("oversized local archive list")
    return raw


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--local-nbp-table-a-usd-json", type=Path, required=True)
    p.add_argument("--local-dir-year", type=Path, required=True)
    p.add_argument("--archive-year", type=int, required=True)
    p.add_argument("--effective-date", required=True)
    p.add_argument("--decision-at-utc", required=True)
    args = p.parse_args()
    _year(args.archive_year)
    snapshot = _read_local(args.local_nbp_table_a_usd_json)
    raw = _read_directory(args.local_dir_year, args.archive_year)
    result = reconcile_archive(
        snapshot, raw, archive_year=args.archive_year,
        requested_effective_date=args.effective_date,
        decision_at_utc=args.decision_at_utc,
    )
    print("ISL_I7_NBP_ARCHIVE_DIRECTORY_RECEIPT=" +
          json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
