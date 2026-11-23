"""Offline FRED-republished OECD Poland monthly share-PRICE index research.

No network or instrument execution. Input is a bounded operator-supplied textual
FRED table extract, NOT attested original HTTP bytes or a licensed source grant.
The index is not a Polish-zloty transaction price or total-return investment.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
from pathlib import Path
import re

SOURCE_URL = "https://fred.stlouisfed.org/data/SPASTT01PLM661N"
SOURCE_SERIES = "SPASTT01PLM661N"
SCHEMA = "ISL_FRED_OECD_POL_SECONDARY_RESEARCH_V03"
MONTHS = tuple(f"{y}-{m:02d}" for y in range(2022, 2026) for m in range(1, 13))
MAX_SOURCE_BYTES = 100_000
DECIMAL_RE = re.compile(r"\d{1,10}(?:\.\d{1,12})?\Z")
DATA_RE = re.compile(r"(\d{4}-\d{2}-01)\s+(\d{1,10}(?:\.\d{1,12})?)\Z")
CHECKSUM_RE = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_META = (
    "Financial Market: Share Prices for Poland",
    "Series ID SPASTT01PLM661N",
    "Source Organization for Economic Co-operation and Development",
    "Seasonal Adjustment Not Seasonally Adjusted",
    "Frequency Monthly",
    "Units Index 2015=100",
    "REF_AREA: POL",
    "MEASURE: SHARE",
    "UNIT_MEASURE: IX",
    "FREQ: M",
)


class SecondaryResearchBlocked(ValueError):
    """A secondary source has insufficient independent evidence or format."""


def _stamp(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        raise SecondaryResearchBlocked("EXACT_UTC_RETRIEVAL_TIME_REQUIRED")
    try:
        stamped = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise SecondaryResearchBlocked("EXACT_UTC_RETRIEVAL_TIME_REQUIRED") from e
    if stamped < datetime(2026, 1, 1, tzinfo=timezone.utc) or stamped > datetime.now(timezone.utc):
        raise SecondaryResearchBlocked("RETRIEVAL_TIME_OUT_OF_BOUNDS")
    return value


def _level(value: str) -> Decimal:
    if not isinstance(value, str) or not DECIMAL_RE.fullmatch(value):
        raise SecondaryResearchBlocked("SECONDARY_INDEX_LEVEL_INVALID")
    try:
        out = Decimal(value)
    except InvalidOperation as e:
        raise SecondaryResearchBlocked("SECONDARY_INDEX_LEVEL_INVALID") from e
    if not out.is_finite() or out <= 0 or not -10 <= out.adjusted() <= 10:
        raise SecondaryResearchBlocked("SECONDARY_INDEX_LEVEL_INVALID")
    return out


def parse_fred_table(raw: bytes, *, retrieved_at_utc: str) -> dict:
    """Require FRED series metadata and all 48 target months in exact order.

    Accepts a verbatim plain-text *display/table extraction* from FRED; does not
    claim that the operator-provided text represents original HTTP source bytes.
    """
    timestamp = _stamp(retrieved_at_utc)
    if type(raw) is not bytes or not 10 <= len(raw) <= MAX_SOURCE_BYTES:
        raise SecondaryResearchBlocked("SECONDARY_SOURCE_SIZE_INVALID")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as e:
        raise SecondaryResearchBlocked("SECONDARY_SOURCE_NOT_UTF8") from e
    lines = text.splitlines()
    if len(lines) > 1500 or any(len(line) > 2000 for line in lines):
        raise SecondaryResearchBlocked("SECONDARY_SOURCE_LINES_UNBOUNDED")
    before = []
    position = None
    for i, line in enumerate(lines):
        if line.strip() == "DATE VALUE":
            if position is not None:
                raise SecondaryResearchBlocked("AMBIGUOUS_FRED_TABLE")
            position = i
        if position is None:
            before.append(line.strip())
    if position is None:
        raise SecondaryResearchBlocked("FRED_DATA_TABLE_MISSING")
    header = "\n".join(before)
    if not all(fragment in header for fragment in REQUIRED_META):
        raise SecondaryResearchBlocked("FRED_SERIES_METADATA_MISMATCH")
    # Refuse duplicate, contradictory Series ID, Units, or Source labels.
    for field in ("Series ID", "Units", "Frequency", "Source", "REF_AREA:", "MEASURE:", "UNIT_MEASURE:"):
        count = sum(line.startswith(field + " ") for line in before)
        if count > 1:
            raise SecondaryResearchBlocked("DUPLICATE_FRED_METADATA")
    observations = []
    started = False
    for line in lines[position + 1:]:
        trimmed = line.strip()
        if not trimmed:
            if started:
                break
            continue
        match = DATA_RE.fullmatch(trimmed)
        if not match:
            if started:
                break
            raise SecondaryResearchBlocked("FRED_DATA_ROW_INVALID")
        started = True
        try:
            observed_date = date.fromisoformat(match.group(1))
        except ValueError as e:
            raise SecondaryResearchBlocked("FRED_DATE_INVALID") from e
        month = observed_date.strftime("%Y-%m")
        value = _level(match.group(2))
        if MONTHS[0] <= month <= MONTHS[-1]:
            observations.append((month, value))
    if [month for month, _ in observations] != list(MONTHS):
        raise SecondaryResearchBlocked("SECONDARY_48_MONTH_COVERAGE_OR_ORDER_INVALID")
    return {
        "levels": {month: value for month, value in observations},
        "source_receipt": {
            "display_url": SOURCE_URL,
            "source_series": SOURCE_SERIES,
            "retrieved_at_utc_user_supplied": timestamp,
            "provided_text_sha256": sha256(raw).hexdigest(),
            "provided_text_bytes": len(raw),
            "hash_basis": "OPERATOR_SUPPLIED_FRED_DISPLAY_TEXT_NOT_ORIGINAL_HTTP_BYTES",
            "provider_original_bytes_verified": False,
            "independent_source_vintage_verified": False,
            "series_specific_rights_verified": False,
        },
    }


def reconcile_primary_secondary(fred_levels: dict, oecd_levels: dict, *, tolerance: str = "0.000001") -> dict:
    """Exact month-by-month secondary-vs-primary level reconciliation only.

    This cannot certify independent historical vintages, source rights, or PIT.
    """
    if set(fred_levels) != set(MONTHS) or set(oecd_levels) != set(MONTHS):
        raise SecondaryResearchBlocked("RECONCILIATION_MONTHS_MISSING")
    allowed = _level(tolerance)
    if allowed > Decimal("0.0001"):
        raise SecondaryResearchBlocked("RECONCILIATION_TOLERANCE_EXCESSIVE")
    max_diff = Decimal(0)
    disagreements = 0
    for month in MONTHS:
        delta = abs(_level(format(fred_levels[month], "f")) - _level(format(oecd_levels[month], "f")))
        max_diff = max(max_diff, delta)
        if delta > allowed:
            disagreements += 1
    return {
        "pair_count": len(MONTHS),
        "max_abs_level_difference": format(max_diff, "f"),
        "tolerance": format(allowed, "f"),
        "disagreements": disagreements,
        "level_reconciliation_pass": disagreements == 0,
        "independent_pit_proof": False,
        "source_rights_proof": False,
    }


def describe_secondary(parsed: dict, *, primary_levels: dict | None = None) -> dict:
    levels = parsed["levels"]
    with localcontext() as ctx:
        ctx.prec = 45
        last = levels[MONTHS[-1]]
        equivalent = sum((Decimal(100) * last / levels[m] for m in MONTHS), Decimal(0))
        change = Decimal(100) * (last / levels[MONTHS[0]] - Decimal(1))
    report = {
        "schema": SCHEMA,
        "status": "SECONDARY_REAL_OBSERVATIONS_DESCRIPTIVE_NOT_EXECUTABLE",
        "series": "FRED republished OECD POL monthly share-PRICE index (2015=100)",
        "first_month": MONTHS[0],
        "last_month": MONTHS[-1],
        "observation_count": len(MONTHS),
        "fictional_monthly_contribution_pln": "100",
        "fictional_contributions_pln": "4800.00",
        "index_unit_terminal_equivalent_pln": format(equivalent.quantize(Decimal("0.01")), "f"),
        "index_change_first_to_last_pct": format(change.quantize(Decimal("0.01")), "f"),
        "source_receipt": parsed["source_receipt"],
        "oecd_primary_reconciliation": (
            reconcile_primary_secondary(levels, primary_levels)
            if primary_levels is not None else None
        ),
        "source_category": "SECONDARY_REPUBLICATION_NOT_CERTIFIED_RAW_OECD_CSV",
        "index_not_currency_or_purchase_price": True,
        "monthly_average_not_executable_month_end_close": True,
        "dividends_included": False,
        "transaction_costs_included": False,
        "historical_pit_certified": False,
        "qualified_asset_series": [],
        "m1_m2_m3": "INSUFFICIENT_DATA_HOLD_CASH",
        "database_writes": 0,
        "financial_operations": 0,
        "orders_sent": 0,
    }
    return report


def markdown(report: dict) -> str:
    compare = report["oecd_primary_reconciliation"]
    statement = ("Not performed: original OECD CSV was not provided."
                 if compare is None else
                 f"{compare['pair_count']} months, {compare['disagreements']} mismatches, "
                 f"max absolute index-level delta {compare['max_abs_level_difference']}. "
                 "Neither matching prices nor hashes prove first-publication vintages.")
    return ("# FRED / OECD Poland share-price index — secondary research appendix\n\n"
            "**Secondary retrospective reference only; M1/M2/M3 HOLD_CASH.**\n\n"
            f"Source: {SOURCE_URL} (FRED republishes OECD; operator-provided text), "
            f"period {report['first_month']}–{report['last_month']}, "
            f"{report['observation_count']} months.\n\n"
            f"Fictional contributions: {report['fictional_contributions_pln']} PLN; "
            f"index-unit equivalent: {report['index_unit_terminal_equivalent_pln']} PLN; "
            f"index change first vs last: {report['index_change_first_to_last_pct']}%.\n\n"
            f"Primary OECD per-month comparison: {statement}\n\n"
            "**Restrictions:** This is an index of Polish share prices (2015=100), "
            "not a tradable security, a global or total-return index, or a PLN fill. "
            "Monthly means have no executable month-end transaction price. "
            "Dividends, fees, taxes, first-publication PIT and series-specific "
            "rights are unverified. The receipt hashes operator-supplied text, "
            "**not original HTTP bytes**. No model admission or real operations.\n")


def _read(path: Path, size: int) -> bytes:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= size:
        raise SecondaryResearchBlocked("BOUNDED_REGULAR_INPUT_REQUIRED")
    data = path.read_bytes()
    if not 0 < len(data) <= size:
        raise SecondaryResearchBlocked("BOUNDED_REGULAR_INPUT_REQUIRED")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fred-table-text", type=Path, required=True)
    parser.add_argument("--text-sha256", required=True)
    parser.add_argument("--retrieved-at-utc", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--base-report", type=Path, help="Existing report, preserved unmodified")
    parser.add_argument("--oecd-csv", type=Path, help="Optional original OECD SDMX CSV, offline only")
    parser.add_argument("--oecd-sha256", help="Exact original OECD CSV bytes SHA-256")
    parser.add_argument("--oecd-retrieved-at-utc", help="Actual OECD retrieval timestamp")
    args = parser.parse_args(argv)
    try:
        if not CHECKSUM_RE.fullmatch(args.text_sha256):
            raise SecondaryResearchBlocked("EXACT_TEXT_SHA256_REQUIRED")
        if args.out_dir.exists() or args.out_dir.is_symlink():
            raise SecondaryResearchBlocked("OUT_DIR_ALREADY_EXISTS")
        raw = _read(args.fred_table_text, MAX_SOURCE_BYTES)
        if sha256(raw).hexdigest() != args.text_sha256:
            raise SecondaryResearchBlocked("FRED_TEXT_SHA256_MISMATCH")
        primary_levels = None
        oecd_opts = (args.oecd_csv, args.oecd_sha256, args.oecd_retrieved_at_utc)
        if any(v is not None for v in oecd_opts):
            if not all(v is not None for v in oecd_opts):
                raise SecondaryResearchBlocked("ALL_OECD_ORIGINAL_RECEIPT_FIELDS_REQUIRED")
            if not CHECKSUM_RE.fullmatch(args.oecd_sha256):
                raise SecondaryResearchBlocked("EXACT_OECD_RAW_SHA256_REQUIRED")
            oecd_raw = _read(args.oecd_csv, 1_000_000)
            if sha256(oecd_raw).hexdigest() != args.oecd_sha256:
                raise SecondaryResearchBlocked("ORIGINAL_OECD_SHA256_MISMATCH")
            from scripts.oecd_pol_benchmark import parse_csv as parse_primary
            primary_levels = parse_primary(oecd_raw, args.oecd_retrieved_at_utc)["levels"]
        result = describe_secondary(parse_fred_table(raw, retrieved_at_utc=args.retrieved_at_utc),
                                    primary_levels=primary_levels)
        if result["oecd_primary_reconciliation"] is not None and not result["oecd_primary_reconciliation"]["level_reconciliation_pass"]:
            raise SecondaryResearchBlocked("FRED_VS_OECD_MONTH_LEVEL_MISMATCH")
        intro = ""
        if args.base_report:
            intro = _read(args.base_report, 250_000).decode("utf-8").rstrip() + "\n\n---\n\n"
        report = intro + markdown(result)
        args.out_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        with (args.out_dir / "fred_oecd_secondary.json").open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, sort_keys=True, ensure_ascii=False)
            out.write("\n")
        (args.out_dir / "research_report.md").write_text(report, encoding="utf-8")
    except (SecondaryResearchBlocked, OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print("FRED_OECD_SECONDARY=" + json.dumps({
        "status": result["status"], "months": result["observation_count"],
        "m1_m2_m3": result["m1_m2_m3"], "database_writes": 0,
        "financial_operations": 0}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
