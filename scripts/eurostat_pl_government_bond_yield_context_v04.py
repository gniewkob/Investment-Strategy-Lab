"""Polish sovereign 10Y-ish bond YIELD context from original Eurostat JSON-stat.

The Maastricht convergence series is a % p.a. interest rate (not holding-
period bond return, not TBSP, coupon data or an executable bond price).
A present-day official dataset is NOT proof of past first-publication versions.
This is read-only research context, never a trading or portfolio input.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
import re

from scripts.eurostat_pl_bond_yield_source_probe_v04 import (
    fetch_official, URL, MAX_BYTES,
)
from scripts.public_first_prospective_source_observation_v03 import (
    _provider_update,
)

SCHEMA = "ISL_EUROSTAT_PL_GOV_BOND_YIELD_CONTEXT_V04"
SINCE = "2021-11"
UNTIL = "2026-09"
MAX_MONTHS = 59
REQUIRED = {"freq": "M", "int_rt": "MCBY", "geo": "PL"}
DIMS = set(REQUIRED) | {"time"}
MONTH = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")


class PLYieldContextBlocked(ValueError):
    """Unsupported, incomplete or semantically incompatible source evidence."""


def _canon(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _aware_utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PLYieldContextBlocked("AWARE_UTC_OBSERVATION_CLOCK_REQUIRED")
    return value.astimezone(timezone.utc)


def _month(value: object) -> date:
    if not isinstance(value, str) or not MONTH.fullmatch(value):
        raise PLYieldContextBlocked("SOURCE_MONTH_INVALID")
    try:
        return date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise PLYieldContextBlocked("SOURCE_MONTH_INVALID") from exc


def _next_month(d: date) -> date:
    return date(d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1, 1)


def _indices(data: dict) -> tuple[list[str], list[int], dict[str, dict[str, int]]]:
    ids, sizes, dims = data.get("id"), data.get("size"), data.get("dimension")
    if (not isinstance(ids, list) or len(ids) != len(DIMS)
            or set(ids) != DIMS or len(set(ids)) != len(ids)
            or not isinstance(sizes, list) or len(sizes) != len(ids)
            or not isinstance(dims, dict) or set(dims) != DIMS):
        raise PLYieldContextBlocked("OFFICIAL_JSONSTAT_DIMENSION_CONFLICT")
    categories = {}
    for name, count in zip(ids, sizes):
        if type(count) is not int or not 1 <= count <= MAX_MONTHS:
            raise PLYieldContextBlocked("JSONSTAT_DIMENSION_SIZE_INVALID")
        dim = dims[name]
        cat = dim.get("category") if isinstance(dim, dict) else None
        ix = cat.get("index") if isinstance(cat, dict) else None
        if (not isinstance(ix, dict) or len(ix) != count
                or any(type(v) is not int for v in ix.values())
                or set(ix.values()) != set(range(count))):
            raise PLYieldContextBlocked("JSONSTAT_CATEGORY_POSITIONS_INVALID")
        categories[name] = ix
        if name in REQUIRED and ix != {REQUIRED[name]: 0}:
            raise PLYieldContextBlocked("WRONG_COUNTRY_RATE_OR_FREQUENCY")
    return ids, sizes, categories


def parse_original_yields(raw: bytes, *, observed_at: datetime) -> dict:
    """Parse one original raw Eurostat response; output aggregates, not rows.

    'observed_at' records our runner's completed HTTPS read or local fixture
    processing time. It is never original historic first-publication time.
    """
    observed_at = _aware_utc(observed_at)
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES:
        raise PLYieldContextBlocked("SOURCE_BYTES_OUT_OF_BOUNDS")
    try:
        data = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PLYieldContextBlocked("SOURCE_INVALID_JSON") from exc
    if (not isinstance(data, dict) or data.get("version") != "2.0"
            or data.get("class") != "dataset"
            or data.get("source") not in ("ESTAT", "Eurostat")):
        raise PLYieldContextBlocked("UNSUPPORTED_OFFICIAL_JSONSTAT_FORMAT")
    ids, sizes, cats = _indices(data)
    ordered = sorted(cats["time"].items(), key=lambda it: it[1])
    if (len(ordered) != MAX_MONTHS or ordered[0][0] != SINCE
            or ordered[-1][0] != UNTIL
            or _month(ordered[-1][0]) > observed_at.date().replace(day=1)):
        raise PLYieldContextBlocked("INCOMPLETE_OR_FUTURE_SOURCE_WINDOW")
    for idx, (month, pos) in enumerate(ordered):
        if pos != idx or _month(month) != (
                _month(SINCE) if idx == 0 else _next_month(_month(ordered[idx-1][0]))):
            raise PLYieldContextBlocked("MISSING_OR_REORDERED_MONTHS")

    values = data.get("value")
    statuses = data.get("status", {})
    cells = 1
    for size in sizes:
        cells *= size
    if (not isinstance(values, (dict, list)) or type(values) is bool
            or not isinstance(statuses, dict)
            or isinstance(values, list) and len(values) != cells
            or isinstance(values, dict) and any(
                not isinstance(k, str) or not k.isdigit()
                or not 0 <= int(k) < cells for k in values)
            or any(not isinstance(k, str) or not k.isdigit()
                   or not 0 <= int(k) < cells for k in statuses)):
        raise PLYieldContextBlocked("SOURCE_VALUE_VECTOR_MALFORMED")
    rates = []
    flags = {}
    for month, pos in ordered:
        coords = [pos if k == "time" else 0 for k in ids]
        offset = 0
        for coordinate, count in zip(coords, sizes):
            offset = offset * count + coordinate
        cell = values[offset] if isinstance(values, list) else values.get(str(offset))
        if (type(cell) not in (float, int, str) or cell is None
                or isinstance(cell, str) and len(cell) > 32):
            raise PLYieldContextBlocked("MISSING_OR_UNEXPECTED_YIELD")
        try:
            rate = Decimal(str(cell))
        except (InvalidOperation, ValueError) as exc:
            raise PLYieldContextBlocked("INVALID_PERCENT_PER_ANNUM") from exc
        # Negative Eurozone yields can occur, do not reject negative rates
        # automatically; bound the official PL series against unit mistakes.
        if not rate.is_finite() or not Decimal("-20") <= rate <= Decimal("50"):
            raise PLYieldContextBlocked("YIELD_UNITS_OR_NUMERIC_RANGE_INVALID")
        status = statuses.get(str(offset))
        if status is not None:
            if type(status) is not str or len(status) > 12 or not status.isalnum():
                raise PLYieldContextBlocked("SOURCE_STATISTICAL_FLAG_INVALID")
            flags[status] = flags.get(status, 0) + 1
        rates.append(rate)
    # This field is the provider's most recent dataset update, NOT the first
    # release timestamp of any constituent monthly observation.
    try:
        provider_update = _provider_update(
            data.get("updated", "NOT_PROVIDED"), observed_at)
    except ValueError as exc:
        raise PLYieldContextBlocked("PROVIDER_TIMESTAMP_INCONSISTENT") from exc
    with localcontext() as ctx:
        ctx.prec = 36
        avg = sum(rates, Decimal(0)) / len(rates)
        max_change_bps = max(abs((b-a) * Decimal(100))
                             for a,b in zip(rates, rates[1:]))
    out = {
        "schema": SCHEMA,
        "status": "PUBLIC_OFFICIAL_YIELD_CONTEXT_ONLY",
        "source": "Eurostat",
        "dataset": "irt_lt_mcby_m",
        "original_source_url": URL,
        "original_response_sha256": sha256(raw).hexdigest(),
        "observed_by_runner_at_utc": observed_at.isoformat(),
        "provider_reported_updated_not_first_release": provider_update,
        "source_attribution": "Eurostat/ECB/National Central Banks: irt_lt_mcby_m",
        "country": "PL",
        "frequency": "M",
        "interest_rate_code": "MCBY",
        "source_unit": "PERCENT_PER_ANNUM",
        "data_kind": "GOVERNMENT_BOND_CONVERGENCE_CRITERION_YIELD_NOT_RETURN",
        "residual_maturity": "APPROXIMATELY_TEN_YEARS",
        "first_month": SINCE,
        "last_month": UNTIL,
        "observed_months": len(rates),
        "min_yield_pct_per_annum": str(min(rates)),
        "max_yield_pct_per_annum": str(max(rates)),
        "mean_yield_pct_per_annum": format(avg.quantize(Decimal("0.0001")), "f"),
        "max_abs_adjacent_month_level_change_bps": format(
            max_change_bps.quantize(Decimal("0.01")), "f"),
        "source_statistical_flags_count": flags,
        "present_snapshot_not_original_historic_vintages": True,
        "historical_first_available_at_verified": False,
        "historical_pit_certified": False,
        "bond_holding_period_return_observed": False,
        "tbsp_income_index_observed": False,
        "estimated_coupon_reinvestment": False,
        "qualified_model_series": [],
        "legacy_m1_m2_m3": "INSUFFICIENT_DATA_HOLD_CASH",
        "orders_sent": 0,
        "financial_operations": 0,
        "database_writes": 0,
        "paper_events_created": 0,
    }
    out["receipt_sha256"] = sha256(_canon(out)).hexdigest()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-eurostat-read", action="store_true")
    args = parser.parse_args()
    if not args.allow_public_eurostat_read:
        parser.error("Explicit --allow-public-eurostat-read required")
    raw = fetch_official()
    receipt = parse_original_yields(raw, observed_at=datetime.now(timezone.utc))
    # No observations are printed, no data copied to files or GitHub artifacts.
    print("ISL_PUBLIC_EUROSTAT_PL_YIELD_RECEIPT=" +
          json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
