"""I6: offline NBP Table A USD/PLN *date-only* historical availability check.

The NBP API gives 'effectiveDate' but no signed first-publication instant.
Policy: do not use an observation in a historical research decision until
00:00 UTC on the NEXT calendar day after the NBP effectiveDate. This is a
deliberately conservative local assumption, not independent PIT certification.
Never forward-fill an absent requested date, never derive investable total
return or any real trade/paper candidate. No network or database access.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

SCHEMA = "ISL_I6_NBP_TABLE_A_USDPLN_DATE_LAG_OFFLINE_V01"
MAX_INPUT_BYTES = 250_000
MAX_ROWS = 93
MIN_PUBLICATION_DAY = date(2002, 1, 2)
MAX_PUBLICATION_DAY = date(2100, 12, 30)
CODE = "USD"
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
ROOT_FIELDS = {"table", "currency", "code", "rates"}
ROW_FIELDS = {"no", "effectiveDate", "mid"}
ZERO_ACTIVITY = {
    "orders_sent": 0, "paper_fills": 0,
    "financial_operations": 0, "database_writes": 0,
}


class NBPDateLagError(ValueError):
    """Source format or unsafe date selection is rejected."""


def _date(value):
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        raise NBPDateLagError("explicit ISO publication date required")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise NBPDateLagError("invalid publication date") from exc


def _utc(value):
    if not isinstance(value, str):
        raise NBPDateLagError("explicit UTC decision timestamp required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NBPDateLagError("invalid UTC decision timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise NBPDateLagError("UTC decision timestamp required")
    return stamp.astimezone(timezone.utc)


def _canonical(record):
    try:
        raw = json.dumps(record, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise NBPDateLagError("untrusted JSON snapshot") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise NBPDateLagError("snapshot exceeds offline limit")
    return raw


def _validate(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != ROOT_FIELDS:
        raise NBPDateLagError("expected exact NBP Table A USD rates snapshot fields")
    if snapshot["table"] != "A" or snapshot["code"] != CODE:
        raise NBPDateLagError("only NBP Table A USD/PLN is supported")
    if (not isinstance(snapshot["currency"], str)
            or len(snapshot["currency"]) > 100
            or not snapshot["currency"].strip()):
        raise NBPDateLagError("invalid NBP currency metadata")
    rows = snapshot["rates"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise NBPDateLagError("1-93 NBP publication rows required")
    dates = set()
    previous = None
    for item in rows:
        if not isinstance(item, dict) or set(item) != ROW_FIELDS:
            raise NBPDateLagError("unsupported NBP rate row schema")
        day = _date(item["effectiveDate"])
        if (day < MIN_PUBLICATION_DAY or day > MAX_PUBLICATION_DAY
                or (previous is not None and day <= previous)):
            raise NBPDateLagError("duplicate, unsorted, or unsupported publication day")
        no = item["no"]
        if (not isinstance(no, str)
                or re.fullmatch(r"[0-9]{1,3}/A/NBP/[0-9]{4}", no) is None
                or not no.endswith("/" + str(day.year))):
            raise NBPDateLagError("NBP Table A source number/year mismatch")
        raw = item["mid"]
        # JSON numbers are usually parsed as Python float. No arithmetic
        # here uses floating-point rates: they are validated, then redacted.
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise NBPDateLagError("NBP API mid must be a JSON number")
        try:
            val = Decimal(str(raw))
        except (InvalidOperation, ValueError) as exc:
            raise NBPDateLagError("invalid NBP rate") from exc
        if not val.is_finite() or val <= 0:
            raise NBPDateLagError("positive NBP reference FX expected")
        dates.add(day)
        previous = day
    return dates, _canonical(snapshot)


def assess_nbp_publication_lag(snapshot, *, requested_effective_date,
                               decision_at_utc):
    """Inspect one exact publication day without inventing a historical release hour.

    Always returns source/paper/trading blocked, even after conservative lag
    passes. No NBP FX value, price or converted index level appears in output.
    """
    requested = _date(requested_effective_date)
    decision = _utc(decision_at_utc)
    dates, raw = _validate(snapshot)
    if requested < MIN_PUBLICATION_DAY or requested > MAX_PUBLICATION_DAY:
        raise NBPDateLagError("publication date outside supported source history")
    # Date-only input cannot authenticate the exact first-published time.
    # The deliberate +1 calendar day UTC convention removes same-day use.
    not_before = datetime.combine(
        requested + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    found = requested in dates
    if not found:
        status = "NO_EXACT_SOURCE_PUBLICATION_DATE"
    elif decision < not_before:
        status = "NOT_YET_PASSED_CONSERVATIVE_NEXT_DAY_LAG"
    else:
        status = "DATE_LAG_PASSED_NOT_HISTORICAL_PIT_CERTIFIED"
    result = {
        "schema": SCHEMA,
        "status": status,
        "source_kind": "NBP_USDPLN_TABLE_A_MID_NON_EXECUTABLE_FX",
        "canonical_local_snapshot_sha256": sha256(raw).hexdigest(),
        "source_rows_examined": len(dates),
        "requested_effective_date": requested.isoformat(),
        "decision_at_utc": decision.isoformat(),
        "research_not_before_utc": not_before.isoformat(),
        "exact_publication_date_present": found,
        "same_day_use_allowed": False,
        "forward_fill_performed": False,
        "fx_conversion_performed": False,
        "rate_values_in_receipt": False,
        "independently_verified_first_publication_instant": False,
        "independently_certified_historical_pit": False,
        "independently_certified_source_rights": False,
        "eligible_as_model_total_return_series": False,
        "qualified_model_series": [],
        "paper_candidates": [],
        "market_execution_authorized": False,
        "source_manifest_created": False,
        "model_state": "HOLD_CASH",
        **ZERO_ACTIVITY,
    }
    result["receipt_sha256"] = sha256(_canonical(result)).hexdigest()
    return result


def _read_local(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise NBPDateLagError("bounded regular local NBP JSON snapshot required")
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise NBPDateLagError("oversized source JSON")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NBPDateLagError("invalid local JSON snapshot") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-nbp-table-a-usd-json", type=Path, required=True)
    parser.add_argument("--effective-date", required=True)
    parser.add_argument("--decision-at-utc", required=True)
    args = parser.parse_args()
    report = assess_nbp_publication_lag(
        _read_local(args.local_nbp_table_a_usd_json),
        requested_effective_date=args.effective_date,
        decision_at_utc=args.decision_at_utc,
    )
    print("ISL_I6_NBP_DATE_LAG_RECEIPT=" +
          json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
