"""Match official NBP reference quotes to exact BondSpot month-end dates.

The original 60-month end-of-month NBP archive is preserved verbatim.
Only when a BondSpot closing date differs, fetch that EXACT same calendar
day from the public NBP FX table A and gold API, with raw SHA-256 receipts.
No nearest-neighbor interpolation, no post-dated FX, no fund NAV, no fills.
Even matching dates do NOT certify historical publication hour/vintage.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from scripts.nbp_reference_capture import capture
from scripts.reference_archive_calendar_v04 import reconcile, _digest

ASSETS = ("usdpln", "eurpln", "gold")


def match(nbp: dict, bondspot: dict, *, fetch=None, clock=None) -> dict:
    proof = reconcile(nbp, bondspot)
    date_mismatches = proof["different_date_months"]
    if date_mismatches and fetch is None:
        # This module belongs to the offline A2 source contract. Missing
        # reference dates do not implicitly authorize public HTTP requests.
        raise ValueError(
            "EXPLICIT_FETCH_REQUIRED: same-day NBP source retrieval is not automatic"
        )
    by_month = {row["month"]: row for row in bondspot["monthly"]}
    original = {key: {row["month"]: row
                      for row in nbp["monthly_observations"][key]}
                for key in ASSETS}
    replacements = {}
    for month in date_mismatches:
        day = by_month[month]["observed_for"]
        options = {}
        if fetch is not None:
            options["fetch"] = fetch
        if clock is not None:
            options["clock"] = clock
        source = capture(day, day, **options)
        if source.get("source") != "NBP" or source.get("paper_events_created") != 0:
            raise ValueError("not a valid NBP read-only source receipt")
        records = {}
        for key in ASSETS:
            rows = source["series"].get(key)
            if not isinstance(rows, list) or len(rows) != 1:
                raise ValueError("same-day NBP quote missing: " + day + "/" + key)
            r = rows[0]
            kind = "gold" if key == "gold" else "fx"
            receipt = source["receipts"][kind]
            expected_basis = ("PRICE_ONLY_PLN_PER_GRAM" if key == "gold"
                              else "TABLE_A_MID_PLN_PER_FOREIGN_UNIT")
            if (r["observed_for"] != day or r.get("available_at") is not None
                    or r.get("currency") != "PLN"
                    or r.get("basis") != expected_basis
                    or r["source_url"] != receipt["url"]
                    or r["source_sha256"] != receipt["sha256"]
                    or r["retrieved_at"] != receipt["retrieved_at"]):
                raise ValueError("unverifiable same-day NBP reference: " + day)
            value = Decimal(r["value"])
            if not value.is_finite() or value <= 0:
                raise ValueError("invalid same-day NBP reference value")
            records[key] = {
                "month": month, "observed_for": day, "value": str(value),
                "raw_sha256": r["source_sha256"],
                "source_url": r["source_url"],
                "retrieved_at": r["retrieved_at"],
                "basis": expected_basis,
                "alignment": "ORIGINAL_NBP_SAME_DATE_AS_TBSP",
            }
        replacements[month] = {
            "date": day, "original_fx_receipt": source["receipts"]["fx"],
            "original_gold_receipt": source["receipts"]["gold"],
            "reference_rows": records,
        }
    timeline = []
    for b in bondspot["monthly"]:
        month, bond_day = b["month"], b["observed_for"]
        ref = {}
        for key in ASSETS:
            if month in replacements:
                item = replacements[month]["reference_rows"][key]
            else:
                item = dict(original[key][month])
                item["alignment"] = "MONTHLY_NBP_SAME_DATE_AS_TBSP"
            if item["observed_for"] != bond_day:
                raise ValueError("date-matching operation did not align " + month)
            ref[key] = item
        timeline.append({
            "month": month,
            "reference_date": bond_day,
            "bondspot_total_return_index_close": b["value"],
            "bondspot_source_url": b["source_url"],
            "bondspot_raw_sha256": b["raw_sha256"],
            "nbp": ref,
            "same_calendar_date": True,
        })
    result = {
        "status": "SAME_CALENDAR_DATE_REFERENCE_NOT_PIT_OR_EXECUTABLE",
        "months": len(timeline),
        "first_month": timeline[0]["month"],
        "last_month": timeline[-1]["month"],
        "original_mismatches": date_mismatches,
        "official_exact_day_retrieval_count": len(replacements),
        "source_request_count": 2 * len(replacements),
        "replacement_source_receipts": replacements,
        "timeline": timeline,
        "nbp_evidence_sha256": nbp["evidence_sha256"],
        "bondspot_evidence_sha256": bondspot["evidence_sha256"],
        "historical_publication_hour_verified": False,
        "historical_vintage_verified": False,
        "investable_security_price_verified": False,
        "vanguard_nav_series_ready": False,
        "backtest": "NOT_RUN_NO_VERIFIED_VANGUARD_NAV_AND_TRADABLE_PRICES",
        "financial_operations": 0,
        "paper_events_created": 0,
    }
    result["evidence_sha256"] = _digest(result)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nbp", type=Path, required=True)
    p.add_argument("--bondspot", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    data = match(json.loads(args.nbp.read_text(encoding="utf-8")),
                 json.loads(args.bondspot.read_text(encoding="utf-8")))
    args.out.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    print("ISL_NBP_TBSP_EXACT_DATES=" + json.dumps({
        "months": data["months"],
        "original_mismatches": data["original_mismatches"],
        "official_exact_day_retrieval_count": data["official_exact_day_retrieval_count"],
        "source_request_count": data["source_request_count"],
        "evidence_sha256": data["evidence_sha256"],
        "backtest": data["backtest"],
        "financial_operations": 0,
    }, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
