"""v0.19 offline intake audit for licensed MSCI ACWI NETR USD monthly export.

Never download MSCI data or certify access rights. A CSV file, even if it
matches the CFA monthly schema, cannot self-certify originality, historical
point-in-time availability, or permitted derivative use. We report metadata
and coverage, not index values or a qualified M1 decision.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
from pathlib import Path

from scripts.shadow_decision_engine_v05 import ShadowInputError, _digest, _utc

SCHEMA = "ISL_ACWI_NETR_MONTHLY_INTAKE_V19_001"
HEADER = ["Date", "Code", "Index name", "Index variant", "Index level"]
MAX_BYTES = 4_000_000
MIN_MONTHS = 36
MAX_MONTHS = 120


def _positive(raw):
    if not isinstance(raw, str) or not raw or raw != raw.strip():
        raise ShadowInputError("index level missing or invalid")
    try:
        val = Decimal(raw)
    except (ValueError, InvalidOperation) as exc:
        raise ShadowInputError("index level not decimal") from exc
    if not val.is_finite() or val <= 0:
        raise ShadowInputError("index level must be positive and finite")
    return val


def audit(raw, nbp, *, as_of_utc):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ShadowInputError("bounded original monthly CSV bytes required")
    as_of = _utc(as_of_utc)
    try:
        stream = io.StringIO(raw.decode("utf-8-sig"), newline="")
    except UnicodeDecodeError as exc:
        raise ShadowInputError("source CSV must be UTF-8") from exc
    reader = csv.DictReader(stream)
    if reader.fieldnames != HEADER:
        raise ShadowInputError("expected CFA monthly MSCI CSV headers")
    selected = {}
    seen = set()
    source_codes = set()
    total_rows = 0
    for record in reader:
        total_rows += 1
        if total_rows > 40000 or not isinstance(record, dict) or set(record) != set(HEADER):
            raise ShadowInputError("unbounded or ambiguous MSCI CSV")
        try:
            day = datetime.strptime(record["Date"], "%d/%m/%Y").date()
        except (TypeError, ValueError) as exc:
            raise ShadowInputError("MSCI date must be DD/MM/YYYY") from exc
        if day > as_of.date() or day.day < 20:
            raise ShadowInputError("future or non-month-end monthly observation")
        code, name, variant = (record[k] for k in ("Code", "Index name", "Index variant"))
        if not all(isinstance(x, str) for x in (code, name, variant)):
            raise ShadowInputError("incomplete MSCI index identity")
        if name.strip().upper() not in ("MSCI ACWI", "MSCI ACWI INDEX") or variant.strip().upper() != "NETR":
            continue
        if not code.strip():
            raise ShadowInputError("MSCI index code required")
        source_codes.add(code.strip())
        if len(source_codes) > 1:
            raise ShadowInputError("mixed MSCI code for same index")
        month = day.strftime("%Y-%m")
        level = _positive(record["Index level"])
        if month in seen:
            raise ShadowInputError("duplicate MSCI ACWI NETR monthly record")
        seen.add(month)
        selected[month] = (day, level)
    if not selected:
        raise ShadowInputError("MSCI ACWI NETR USD series absent")
    months = sorted(selected)
    previous = None
    for month in months:
        day = date.fromisoformat(month + "-01")
        if previous is not None:
            nxt = date(previous.year + (previous.month == 12),
                       1 if previous.month == 12 else previous.month + 1, 1)
            if day != nxt:
                raise ShadowInputError("month gaps in selected ACWI NETR series")
        previous = day
    if len(months) > MAX_MONTHS:
        raise ShadowInputError("excess monthly history")
    if not isinstance(nbp, dict):
        raise ShadowInputError("official NBP archive required")
    declared = nbp.get("evidence_sha256")
    if not isinstance(declared, str) or _digest({
            k: v for k, v in nbp.items() if k != "evidence_sha256"
    }) != declared:
        raise ShadowInputError("NBP source archive fingerprint mismatch")
    if (nbp.get("source") != "NBP_OFFICIAL_API" or
            nbp.get("data_kind") != "NON_EXECUTABLE_REFERENCE_ONLY" or
            nbp.get("series_contract", {}).get("usdpln", {}).get("return_basis") != "FX_RATE"):
        raise ShadowInputError("official NBP USDPLN FX rate expected")
    fx_rows = nbp.get("monthly_observations", {}).get("usdpln")
    if not isinstance(fx_rows, list):
        raise ShadowInputError("NBP USDPLN monthly rows missing")
    fx_dates = {}
    for r in fx_rows:
        if not isinstance(r, dict) or not isinstance(r.get("observed_for"), str):
            raise ShadowInputError("malformed NBP observations")
        day = date.fromisoformat(r["observed_for"])
        _positive(r.get("value"))
        if day in fx_dates:
            raise ShadowInputError("duplicate NBP USDPLN observation")
        fx_dates[day] = r
    matched, unmatched = 0, []
    for month in months:
        source_day, _ = selected[month]
        if source_day not in fx_dates:
            unmatched.append(month)
        else:
            matched += 1
    result = {
        "schema": SCHEMA,
        "status": "SOURCE_CANDIDATE_RIGHTS_AND_PIT_UNVERIFIED",
        "candidate": "MSCI_ACWI_NETR_USD_MONTHLY",
        "claimed_index_code": next(iter(source_codes)),
        # The five-column CSV has NO currency field. Neither a plausible
        # index name/code nor calendar alignment with USDPLN establishes
        # that the source index levels are denominated in USD.
        "claimed_currency": "UNKNOWN_NOT_IN_SOURCE_CSV",
        "source_currency_independently_verified": False,
        "usd_pln_conversion_performed": False,
        "nbp_fx_date_matches_are_diagnostic_only": True,
        "claimed_return_basis": "NET_TOTAL_RETURN",
        "claimed_return_basis_independently_verified": False,
        "declared_index_name": "MSCI ACWI",
        "original_csv_sha256": sha256(raw).hexdigest(),
        "nbp_archive_sha256": declared,
        "first_month": months[0],
        "last_month": months[-1],
        "monthly_observations": len(months),
        "minimum_months_met": len(months) >= MIN_MONTHS,
        "same_date_nbp_fx_matches": matched,
        "same_date_nbp_fx_missing": unmatched,
        "same_date_fx_complete": not unmatched,
        "original_provider_identity_independently_authenticated": False,
        "original_export_rights_independently_verified": False,
        "historical_first_publication_independently_verified": False,
        "pln_tr_model_qualification": "BLOCKED_UNVERIFIED_RIGHTS_AND_PIT",
        "eligible_M1": False,
        "estimated_returns": None,
        "financial_operations": 0,
        "orders_sent": 0,
        "paper_fills": 0,
        "database_writes": 0,
    }
    result["audit_receipt_sha256"] = _digest(result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--msci-csv", type=Path, required=True)
    p.add_argument("--nbp-archive", type=Path, required=True)
    p.add_argument("--as-of-utc", required=True)
    args = p.parse_args()
    data_path = args.msci_csv
    if data_path.is_symlink() or not data_path.is_file() or data_path.stat().st_size > MAX_BYTES:
        raise ShadowInputError("regular bounded original MSCI file required")
    result = audit(data_path.read_bytes(), json.loads(
        args.nbp_archive.read_text(encoding="utf-8")), as_of_utc=args.as_of_utc)
    print("ISL_ACWI_NETR_INTAKE_V19=" +
          json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
