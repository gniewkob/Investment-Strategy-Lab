"""Strict source-audited monthly calendar reconciliation: official NBP + BondSpot.

SOURCE_REFERENCE_ONLY. Monthly closing observations on different calendar
dates must NEVER be silently joined as simultaneous. A matching calendar
date is not proof of historical publication hour or executable ETF price.
No backtest, writes, paper fills, financial account access or interpolation.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

SERIES = ("usdpln", "eurpln", "gold")
NBP_BASE = "api.nbp.pl"
BOND_BASE = "www.bondspot.pl"


def _digest(obj: dict) -> str:
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _verify_digest(obj: dict) -> None:
    if not isinstance(obj, dict):
        raise ValueError("source document must be a JSON object")
    declared = obj.get("evidence_sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise ValueError("missing source document SHA-256")
    evidence = {k: v for k, v in obj.items() if k != "evidence_sha256"}
    if _digest(evidence) != declared:
        raise ValueError("source evidence SHA-256 mismatch")


def _official_url(value: object, host: str) -> None:
    if not isinstance(value, str):
        raise ValueError("source URL missing")
    u = urlsplit(value)
    if (u.scheme != "https" or u.hostname != host or u.username
            or u.password or u.fragment):
        raise ValueError("unexpected source origin")


def _date(row: dict) -> date:
    month = row.get("month")
    observed = row.get("observed_for")
    if not isinstance(month, str) or not isinstance(observed, str):
        raise ValueError("source month/date missing")
    try:
        day = date.fromisoformat(observed)
    except ValueError as exc:
        raise ValueError("invalid observation date") from exc
    if day.strftime("%Y-%m") != month:
        raise ValueError("observation date outside claimed month")
    return day


def _price(row: dict) -> str:
    try:
        value = Decimal(str(row["value"]))
    except (InvalidOperation, KeyError, ValueError) as exc:
        raise ValueError("invalid reference value") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError("reference value must be positive")
    return format(value, "f")


def _continuity(months: list[str]) -> None:
    if not 36 <= len(months) <= 72 or len(set(months)) != len(months):
        raise ValueError("must have 36-72 distinct months")
    for prev, cur in zip(months, months[1:]):
        y, m = (int(v) for v in prev.split("-"))
        nxt = (y + (m == 12), 1 if m == 12 else m + 1)
        if cur != f"{nxt[0]:04d}-{nxt[1]:02d}":
            raise ValueError("gap or duplicate in source month calendar")


def reconcile(nbp: dict, bondspot: dict) -> dict:
    _verify_digest(nbp)
    _verify_digest(bondspot)
    if (nbp.get("source") != "NBP_OFFICIAL_API"
            or nbp.get("data_kind") != "NON_EXECUTABLE_REFERENCE_ONLY"
            or bondspot.get("source") != "BONDSPOT_OFFICIAL_ARCHIVE"
            or bondspot.get("identity") != "TBSP.Index"
            or bondspot.get("return_basis") != "BOND_TOTAL_RETURN_BENCHMARK_INDEX"
            or bondspot.get("instrument_kind") != "NON_TRADABLE_INDEX"):
        raise ValueError("unexpected source identity or return basis")
    series = nbp.get("monthly_observations", {})
    bond_rows = bondspot.get("monthly")
    if (not isinstance(series, dict) or set(series) != set(SERIES)
            or not isinstance(bond_rows, list)):
        raise ValueError("incomplete monthly reference series")
    months = [x.get("month") for x in bond_rows]
    if not all(isinstance(m, str) and len(m) == 7 for m in months):
        raise ValueError("invalid month")
    _continuity(months)
    if nbp.get("calendar_months") != len(months) or bondspot.get("months") != len(months):
        raise ValueError("declared month count disagrees")
    if (nbp.get("first_month"),nbp.get("last_month")) != (months[0], months[-1]):
        raise ValueError("NBP archive range differs")
    if (bondspot.get("first_month"),bondspot.get("last_month")) != (months[0], months[-1]):
        raise ValueError("BondSpot archive range differs")
    if nbp.get("historical_vintage_verified") or bondspot.get("historical_first_available_verified"):
        raise ValueError("source document cannot self-certify PIT history")
    windows = nbp.get("source_windows")
    if not isinstance(windows, list) or not windows:
        raise ValueError("NBP official source receipts required")
    receipts = {"fx": [], "gold": []}
    for win in windows:
        start, end = date.fromisoformat(win["from"]), date.fromisoformat(win["to"])
        if start > end or (end-start).days >= 93:
            raise ValueError("invalid NBP fetch window")
        for kind in receipts:
            rec = win["receipts"][kind]
            _official_url(rec["url"], NBP_BASE)
            if (not isinstance(rec["sha256"], str)
                    or len(rec["sha256"]) != 64):
                raise ValueError("invalid NBP response hash")
            receipts[kind].append((start, end, rec))
    aligned = {}
    for asset in SERIES:
        records = series[asset]
        if len(records) != len(months) or [v["month"] for v in records] != months:
            raise ValueError("series missing month, repeated month or unsorted")
        selected = []
        for rec in records:
            day = _date(rec)
            kind = "gold" if asset == "gold" else "fx"
            expected = [r for start,end,r in receipts[kind]
                        if start <= day <= end
                        and r["url"] == rec.get("source_url")
                        and r["sha256"] == rec.get("raw_sha256")
                        and r["retrieved_at"] == rec.get("retrieved_at")]
            if len(expected) != 1:
                raise ValueError("NBP observation has no unique authentic source receipt")
            _price(rec)
            selected.append(rec)
        aligned[asset] = selected
    for rec in bond_rows:
        day = _date(rec)
        _official_url(rec.get("source_url"), BOND_BASE)
        url = urlsplit(rec["source_url"])
        if (url.path != "/tbsp_index_archive_en"
                or f"date={day:%Y%m%d}" not in url.query
                or rec.get("return_basis") != "BOND_TOTAL_RETURN_BENCHMARK_INDEX"
                or rec.get("instrument_kind") != "NON_TRADABLE_INDEX"
                or rec.get("quote_currency") != "PLN"
                or not isinstance(rec.get("raw_sha256"), str)
                or len(rec["raw_sha256"]) != 64):
            raise ValueError("invalid BondSpot closing-price source evidence")
        _price(rec)

    timeline = []
    for i, b in enumerate(bond_rows):
        dates = {asset: aligned[asset][i]["observed_for"] for asset in SERIES}
        dates["tbsp"] = b["observed_for"]
        unique = set(dates.values())
        if len(unique) == 1:
            state = "MATCHING_CALENDAR_DATE_NOT_PIT_CERTIFIED"
        else:
            state = "DIFFERENT_LAST_PUBLICATION_DATES_NO_SAME_DAY_JOIN"
        timeline.append({
            "month": b["month"], "calendar_date_match_status": state,
            "observed_for": dates,
            "reference_levels": {asset: aligned[asset][i]["value"]
                                for asset in SERIES} | {"tbsp": b["value"]},
        })
    mismatched = [t["month"] for t in timeline
                  if t["calendar_date_match_status"].startswith("DIFFERENT_")]
    output = {
        "status": "REFERENCE_CALENDAR_AUDITED_NOT_TRADABLE",
        "nbp_evidence_sha256": nbp["evidence_sha256"],
        "bondspot_evidence_sha256": bondspot["evidence_sha256"],
        "months": len(months), "first_month": months[0], "last_month": months[-1],
        "same_calendar_date_months": len(months) - len(mismatched),
        "different_calendar_date_months": len(mismatched),
        "different_date_months": mismatched,
        "timeline": timeline,
        "nav_usd_acc_months": 0,
        "historical_first_usable_at_verified": False,
        "executable_price_verified": False,
        "backtest_status": "NOT_RUN_MISSING_OFFICIAL_NAV_AND_EXECUTION_EVIDENCE",
        "paper_events_created": 0, "financial_operations": 0,
    }
    output["reconciliation_sha256"] = _digest(output)
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nbp", type=Path, required=True)
    p.add_argument("--bondspot", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = reconcile(json.loads(args.nbp.read_text(encoding="utf-8")),
                       json.loads(args.bondspot.read_text(encoding="utf-8")))
    args.out.write_text(json.dumps(result, ensure_ascii=False,
                                   sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("ISL_REFERENCE_CALENDAR="+json.dumps({k:v for k,v in result.items()
          if k not in ("timeline",)}, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
