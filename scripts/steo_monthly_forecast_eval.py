"""Research-only EIA STEO monthly WTI / Brent archive vintage forecast evaluation.

Uses independently issued workbook editions, not a present-day historical
spot-price web page. Computes labelled, *retrospectively reconstructed*
source-report comparisons, NOT independently certified original PIT bytes,
tradable asset returns, verified forecast skill or an allocation signal.
No database or portfolio connections, trades, scheduled jobs or disk writes.
"""
from __future__ import annotations

import argparse
from itertools import groupby
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
from io import BytesIO
import json
import re
import sys
from zipfile import ZipFile

from scripts.steo_historical_archive import catalog, inspect_xlsx, retrieve
from scripts.steo_xlsx_label_probe import MAIN, _read_part, _resolve_sheet, _shared_strings
from src.isl_v2.eia_sources import SourceFormatError

HEADERS = {
    "WTIPUUS": ("WTI_EIA_STEO_USD_BBL", "West Texas Intermediate Spot Average"),
    "BREPUUS": ("BRENT_EIA_STEO_USD_BBL", "Brent Spot Average"),
}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
CELL = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,4})\Z")
FUTURE_HORIZONS = (1, 3, 6)
MAX_ARCHIVES = 34


def _col(reference: str) -> tuple[int, int]:
    match = CELL.fullmatch(reference)
    if not match:
        raise SourceFormatError("Malformed EIA STEO worksheet cell reference")
    col = 0
    for letter in match.group(1):
        col = col * 26 + ord(letter) - 64
    if col < 1 or col > 256:
        raise SourceFormatError("STEO column beyond supported monthly range")
    return col, int(match.group(2))


def _text(cell, shared: list[str]) -> str:
    t = cell.attrib.get("t", "n")
    v = cell.find(MAIN + "v")
    if t == "s" and v is not None and v.text is not None:
        try:
            index = int(v.text)
            if 0 <= index < len(shared):
                return shared[index].strip()
        except ValueError:
            pass
        raise SourceFormatError("Invalid historical shared-string index")
    if t == "inlineStr":
        return "".join(x.text or "" for x in cell.iter(MAIN + "t")).strip()
    if t == "str" and v is not None:
        return (v.text or "").strip()
    return ""


def _price(cell) -> Decimal | None:
    typ = cell.attrib.get("t", "n")
    if typ not in ("n", ""):
        # Errors and text are NOT numerical projections.
        return None
    v = cell.find(MAIN + "v")
    if v is None or v.text is None or not v.text.strip():
        return None
    try:
        value = Decimal(v.text.strip())
    except InvalidOperation as exc:
        raise SourceFormatError("Non-numeric cached STEO table value") from exc
    if not value.is_finite() or value < 0 or value > 1_000_000:
        raise SourceFormatError("STEO reference-price value outside accepted domain")
    return value if value > 0 else None


def _ym(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _add_month(issue: date, offset: int) -> str:
    index = issue.year * 12 + issue.month - 1 + offset
    return _ym(index // 12, index % 12 + 1)


def parse_edition(issue: str, raw: bytes) -> dict:
    spec = catalog().get(issue)
    if spec is None:
        raise SourceFormatError("Unknown officially released STEO edition")
    inspect_xlsx(raw)
    with ZipFile(BytesIO(raw)) as z:
        shared = _shared_strings(z)
        sheet = _read_part(z, _resolve_sheet(z, "2tab"), 14_000_000)
        cells: dict[int, dict[int, object]] = {}
        seen: set[tuple[int, int]] = set()
        for row in sheet.iter(MAIN + "row"):
            row_no = int(row.attrib.get("r", "0"))
            if row_no not in (1, 2, 3, 4, 6, 7):
                continue
            target = cells.setdefault(row_no, {})
            for cell in row.findall(MAIN + "c"):
                col, cell_row = _col(cell.attrib.get("r", ""))
                if cell_row != row_no or (row_no, col) in seen:
                    raise SourceFormatError("Duplicate or misplaced STEO worksheet cells")
                target[col] = cell
                seen.add((row_no, col))
        def title(row: int, col: int) -> str:
            item = cells.get(row, {}).get(col)
            return _text(item, shared) if item is not None else ""
        if "Table 2" not in title(1, 2) or "Energy Prices" not in title(1, 2):
            raise SourceFormatError("Official STEO energy-price table header missing")
        # Internal "Forecast date" can precede PUBLIC release by several days.
        # It must NEVER be used as first market availability.
        if title(3, 1) != "Forecast date:":
            raise SourceFormatError("STEO edition forecast-completed header absent")
        for row, code, name in (
            (6, "WTIPUUS", HEADERS["WTIPUUS"][1]),
            (7, "BREPUUS", HEADERS["BREPUUS"][1]),
        ):
            if title(row, 1) != code or title(row, 2) != name:
                raise SourceFormatError("STEO WTI/Brent identity mismatch")

        years: dict[int, int] = {}
        for col, cell in cells.get(3, {}).items():
            if col < 3:
                continue
            val = _price(cell)
            if val is None:
                continue
            if val != val.to_integral_value() or not 2020 <= val <= 2035:
                raise SourceFormatError("STEO calendar year header invalid")
            years[col] = int(val)
        if not 3 <= len(years) <= 8:
            raise SourceFormatError("STEO monthly calendar years missing")
        starts = sorted(years)
        for col in starts:
            if title(4, col) != "Jan":
                raise SourceFormatError("STEO calendar year must start in January")
        if any(b - a != 12 or years[b] != years[a] + 1
               for a, b in zip(starts, starts[1:])):
            raise SourceFormatError("STEO years must be continuous 12-month blocks")

        monthly_cols: dict[int, str] = {}
        for start in starts:
            for delta, month in enumerate(MONTHS):
                col = start + delta
                if title(4, col) != month:
                    raise SourceFormatError("STEO per-year month header mismatch")
                stamp = _ym(years[start], delta + 1)
                if stamp in monthly_cols.values():
                    raise SourceFormatError("Duplicated STEO forecast month")
                monthly_cols[col] = stamp
        series = {}
        for code, (instrument, name) in HEADERS.items():
            row = 6 if code == "WTIPUUS" else 7
            values = {}
            for col, target_month in monthly_cols.items():
                cell = cells[row].get(col)
                value = _price(cell) if cell is not None else None
                if value is not None:
                    values[target_month] = str(value)
            if len(values) < 18:
                raise SourceFormatError("Insufficient STEO monthly reference-price cells")
            series[code] = values
        return {
            "issue": issue,
            "official_release_day": spec["official_release_day"],
            "release_precision": "DAY",
            "available_not_before_utc_date": (
                date.fromisoformat(spec["official_release_day"]) + timedelta(days=1)
            ).isoformat(),
            "raw_xlsx_sha256": hashlib.sha256(raw).hexdigest(),
            "source_vintage":"RECONSTRUCTED_FROM_CURRENTLY_HOSTED_ARCHIVED_EDITION",
            "original_first_release_bytes_certified":False,
            "independent_original_publication_time_certified":False,
            "price_basis":"MONTHLY_SPOT_REFERENCE_USD_PER_BARREL_NOT_TOTAL_RETURN",
            "series":series,
            "forecast_completed_date_used_as_market_availability":False,
        }


def compare_editions(editions: list[dict], *, horizons=FUTURE_HORIZONS) -> dict:
    if not 2 <= len(editions) <= MAX_ARCHIVES or not horizons:
        raise SourceFormatError("Historical research needs 2-34 distinct released editions")
    indexed = {x["issue"]: x for x in editions}
    if len(indexed) != len(editions):
        raise SourceFormatError("Historical editions must be distinct")
    if any(x.get("original_first_release_bytes_certified") is not False for x in editions):
        raise SourceFormatError("unsupported historical publication certification")
    ordered = sorted(editions, key=lambda x: x["official_release_day"])
    if any(a["official_release_day"] >= b["official_release_day"] for a, b in zip(ordered, ordered[1:])):
        raise SourceFormatError("Source vintage release chronology inconsistent")
    if not all(type(h) is int and 1 <= h <= 12 for h in horizons):
        raise SourceFormatError("Unsupported forecast evaluation horizons")
    report = []
    for original in ordered:
        published = date.fromisoformat(original["official_release_day"])
        issue_month = date(published.year, published.month, 1)
        # Last known prior month from the SAME forecast workbook, not from
        # a later-revised database series (naive persistence comparator).
        baseline_month = _add_month(issue_month, -1)
        for code, (instrument, _) in HEADERS.items():
            baseline_text = original["series"][code].get(baseline_month)
            if baseline_text is None:
                continue
            baseline = Decimal(baseline_text)
            for horizon in horizons:
                target = _add_month(issue_month, horizon)
                predicted_text = original["series"][code].get(target)
                if predicted_text is None:
                    continue
                # First other archived release at least TWO full calendar
                # months AFTER the target period, to avoid confusing
                # same-target-month nowcasts with later reported references.
                candidate = None
                for future in ordered:
                    ref_date = date.fromisoformat(future["official_release_day"])
                    future_month = date(ref_date.year, ref_date.month, 1)
                    after_target = _add_month(date.fromisoformat(target+"-01"), 2)
                    if (_ym(future_month.year,future_month.month) >= after_target
                            and ref_date > published
                            and future["series"][code].get(target) is not None):
                        candidate = future
                        break
                if candidate is None:
                    continue
                estimate = Decimal(predicted_text)
                reference = Decimal(candidate["series"][code][target])
                report.append({
                    "forecast_edition":original["issue"],
                    "edition_release_day":original["official_release_day"],
                    "reference_edition":candidate["issue"],
                    "reference_edition_release_day":candidate["official_release_day"],
                    "instrument_code":instrument,
                    "target_month":target,
                    "horizon_calendar_months":horizon,
                    "source_forecast_value":str(estimate),
                    "later_edition_reference_value":str(reference),
                    "same_edition_previous_month_naive_value":str(baseline),
                    "absolute_source_forecast_error":str(abs(estimate-reference)),
                    "absolute_naive_error":str(abs(baseline-reference)),
                    "reference_character":"LATER_EDITION_HISTORICAL_REFERENCE_ESTIMATE_NOT_FINAL_TRADABLE_CLOSE",
                })
    aggregates = []
    for (inst,h),group in groupby(
        sorted(report,key=lambda r:(r["instrument_code"],r["horizon_calendar_months"])),
        key=lambda r:(r["instrument_code"],r["horizon_calendar_months"])):
        pairs=list(group)
        forecast_mae=sum(Decimal(x["absolute_source_forecast_error"]) for x in pairs)/len(pairs)
        naive_mae=sum(Decimal(x["absolute_naive_error"]) for x in pairs)/len(pairs)
        aggregates.append({
            "instrument_code":inst,"horizon_calendar_months":h,"paired_edition_targets":len(pairs),
            "source_forecast_mae_usd_per_barrel":str(forecast_mae.quantize(Decimal(".01"))),
            "same_edition_naive_mae_usd_per_barrel":str(naive_mae.quantize(Decimal(".01"))),
            "source_forecast_lower_mae_in_this_retrospective_sample":forecast_mae<naive_mae,
            "predictive_advantage_established":False,
        })
    return {
        "status":"STEO_RECONSTRUCTED_HISTORICAL_FORECAST_ERROR_COMPARISON",
        "source_editions":len(ordered),
        "paired_target_forecasts":len(report),
        "reference_policy":"FIRST_SAMPLED_LATER_EDITION_AT_LEAST_TWO_CALENDAR_MONTHS_AFTER_TARGET",
        "forecast_data_basis":"CURRENTLY_HOSTED_ARCHIVED_EDITION_BYTES_MAY_HAVE_BEEN_REVISED",
        "historical_source_as_published_bytes_certified":False,
        "original_observation_point_in_time_certified":False,
        "returns_or_trading_backtest":False,
        "investable_instrument_returns_verified":False,
        "reproducible_reconstruction_only":True,
        "paired_records":report,
        "aggregates":aggregates,
        "research_decision":"DESCRIPTIVE_ONLY_NO_PORTFOLIO_ACTION",
        "virtual_model_rebalances":0,"real_orders":0,
        "database_connections":0,"database_writes":0,"file_creations":0,
        "scheduled":False,
    }


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="STEO vintage source-forecast research, no Neon/trades")
    parser.add_argument("--issues",required=True,
                        help="Comma-separated 2-6 official edition IDs")
    args=parser.parse_args(argv)
    try:
        issue_ids=args.issues.split(",")
        if not 2<=len(issue_ids)<=6 or len(set(issue_ids)) != len(issue_ids):
            raise SourceFormatError("Select 2-6 distinct official archive issues")
        vintage=[]
        for issue in issue_ids:
            raw,_=retrieve(issue)
            vintage.append(parse_edition(issue,raw))
        result=compare_editions(vintage)
        result["source_http_requests"]=len(vintage)
        # Numeric values are official public historical source-report prices;
        # preserve study provenance and never claim prices are trade fills.
        print(json.dumps(result,sort_keys=True,separators=(",",":"),
                         ensure_ascii=False,allow_nan=False))
        return 0
    except Exception as exc:
        print("STEO_HISTORICAL_FORECAST_RESEARCH_FAILED: "+
              type(exc).__name__, file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
