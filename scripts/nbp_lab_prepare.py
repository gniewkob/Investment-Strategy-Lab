"""Build a source-provenance receipt for incremental NBP LAB ingestion.

Network access is strictly public NBP HTTPS. This module has NO database,
brokerage, asset, transfer or paper-fill write capabilities. It NEVER promotes
PRICE_ONLY gold or an NBP mid FX rate to an investable total-return source.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json

from .nbp_reference_capture import capture, _fetch

MAP = {
    "usdpln": ("USDPLN_NBP", "nbp_rates", "FX_RATE"),
    "eurpln": ("EURPLN_NBP", "nbp_rates", "FX_RATE"),
    "gold": ("GOLD_NBP_PLN_G", "nbp_gold", "PRICE_ONLY"),
}


def prepare(start: str, end: str, *, fetch=None, clock=None) -> dict:
    # Use the exact shared adapter from Data Readiness PR #93 (now also in #95).
    options = {}
    if fetch is not None:
        options["fetch"] = fetch
    if clock is not None:
        options["clock"] = clock
    result = capture(start, end, **options)
    retrieved = {name: datetime.fromisoformat(v["retrieved_at"])
                 for name, v in result["receipts"].items()}
    if any(ts.tzinfo is None for ts in retrieved.values()):
        raise ValueError("retrieval timestamps must have timezone")
    allowed_until = min(ts.astimezone(timezone.utc).date()
                        for ts in retrieved.values()).isoformat()
    rows = []
    for series_name, (instrument, source, basis) in MAP.items():
        series = result["series"][series_name]
        if not series:
            raise ValueError("NBP series unexpectedly empty")
        for item in series:
            if item["publication_date"] > allowed_until:
                raise ValueError("future publication date")
            if item["observed_for"] != item["publication_date"]:
                raise ValueError("NBP observation is not aligned with publication")
            if item["currency"] != "PLN" or item["available_at"] is not None:
                raise ValueError("unexpected currency or implied historical timestamp")
            rows.append({
                "instrument_code": instrument,
                "source_code": source,
                "observed_for": item["publication_date"],
                "interval_code": "1d",
                "close_price": item["value"],
                "return_basis": basis,
                "source_url": item["source_url"],
                "source_sha256": item["source_sha256"],
                "retrieved_at": item["retrieved_at"],
            })
    rows.sort(key=lambda row: (row["observed_for"], row["instrument_code"]))
    if len({(r["instrument_code"], r["observed_for"]) for r in rows}) != len(rows):
        raise ValueError("duplicate instrument/date keys")
    return {
        "source": "NBP_OFFICIAL_API",
        "market_data_kind": "REFERENCE_ONLY_NOT_TOTAL_RETURN",
        "source_receipts": result["receipts"],
        "start": start,
        "end": end,
        "row_count": len(rows),
        "by_series": {key: len(result["series"][key]) for key in MAP},
        "rows": rows,
        "historical_publication_hour_verified": False,
        "historical_source_vintage_verified": False,
        "ingestion_authorized": False,
        "paper_events_created": 0,
        "real_financial_operations": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--allow-public-nbp-fetch", action="store_true")
    args = parser.parse_args()
    today = datetime.now(timezone.utc).date()
    start = args.start or (today - timedelta(days=31)).isoformat()
    end = args.end or today.isoformat()
    if not args.allow_public_nbp_fetch:
        parser.error("public NBP HTTPS access requires --allow-public-nbp-fetch")
    result = prepare(start, end, fetch=_fetch)
    # One compact single-line JSON receipt in CI logs; no secrets.
    print("NBP_LAB_RECEIPT_JSON=" + json.dumps(
        result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
