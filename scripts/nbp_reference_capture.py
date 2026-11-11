"""Capture official NBP references as a non-trading research evidence receipt.

The API gives publication dates, not first-publication timestamps or vintages.
No database, account, or trade access is provided by this module.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from urllib.request import Request, urlopen

BASE = "https://api.nbp.pl/api"


def _positive(value):
    if isinstance(value, bool):
        raise ValueError("invalid reference value")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid reference value") from None
    if not number.is_finite() or number <= 0:
        raise ValueError("invalid reference value")
    return str(number)


def _fetch(url):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "ISL-data-readiness/1"})
    with urlopen(request, timeout=20) as response:
        return response.read()


def capture(start, end, fetch=None, clock=lambda: datetime.now(timezone.utc)):
    """Return read-only source receipt only with an explicitly injected fetch.

    No network transport is assumed by the offline research API.
    The separate CLI --allow-public-nbp-fetch gate is an explicit opt-in.
    """
    if fetch is None:
        raise ValueError("EXPLICIT_FETCH_REQUIRED: no implicit public NBP network access")
    begin, finish = date.fromisoformat(start), date.fromisoformat(end)
    if finish < begin or (finish - begin).days >= 93:
        raise ValueError("expected an ordered interval of at most 93 days")
    urls = {"fx": f"{BASE}/exchangerates/tables/a/{start}/{end}/?format=json",
            "gold": f"{BASE}/cenyzlota/{start}/{end}/?format=json"}
    series = {"usdpln": [], "eurpln": [], "gold": []}
    receipts = {}
    for kind, url in urls.items():
        raw = fetch(url)  # HTTP errors, including 404, remain errors; never fabricate an empty series.
        retrieved = clock()
        if retrieved.tzinfo is None or retrieved.utcoffset() is None:
            raise ValueError("timezone required")
        payload = json.loads(raw)
        if not isinstance(payload, list) or not payload:
            raise ValueError("empty or invalid response")
        receipts[kind] = {"url": url, "sha256": hashlib.sha256(raw).hexdigest(),
                          "retrieved_at": retrieved.astimezone(timezone.utc).isoformat()}
        seen = set()
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("invalid response record")
            published = item.get("effectiveDate") if kind == "fx" else item.get("data")
            day = date.fromisoformat(published)
            if day < begin or day > finish or day in seen:
                raise ValueError("out of range or duplicate publication date")
            seen.add(day)
            common = {"observed_for": published, "publication_date": published, "available_at": None,
                      "retrieved_at": receipts[kind]["retrieved_at"], "source_url": url,
                      "source_sha256": receipts[kind]["sha256"], "historical_vintage_verified": False,
                      "license_status": "unverified", "currency": "PLN"}
            if kind == "gold":
                series["gold"].append({**common, "basis": "PRICE_ONLY_PLN_PER_GRAM",
                                       "value": _positive(item.get("cena"))})
            else:
                if item.get("table") != "A" or not isinstance(item.get("rates"), list):
                    raise ValueError("invalid table A")
                for code in ("USD", "EUR"):
                    matches = [row for row in item["rates"] if isinstance(row, dict) and row.get("code") == code]
                    if len(matches) != 1:
                        raise ValueError("missing or duplicate exchange rate")
                    series[code.lower() + "pln"].append({**common, "basis": "TABLE_A_MID_PLN_PER_FOREIGN_UNIT",
                                                        "value": _positive(matches[0].get("mid")), "table_no": item.get("no")})
    for rows in series.values():
        rows.sort(key=lambda row: row["publication_date"])
    return {"source": "NBP", "start": start, "end": end, "receipts": receipts,
            "series": series, "gold_basis": "PRICE_ONLY_PLN_PER_GRAM",
            "fx_basis": "TABLE_A_MID_PLN_PER_FOREIGN_UNIT", "license_status": "UNVERIFIED",
            "pit_status": "UNVERIFIED_HISTORICAL_VINTAGE_AND_PUBLICATION_TIME",
            "market_data_readiness": "INSUFFICIENT_DATA", "paper_events_created": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start")
    parser.add_argument("end")
    parser.add_argument(
        "--allow-public-nbp-fetch", action="store_true",
        help="explicitly opt in to public NBP HTTPS; default is offline/fail-closed",
    )
    args = parser.parse_args()
    if not args.allow_public_nbp_fetch:
        parser.error("public NBP source access needs --allow-public-nbp-fetch")
    print(json.dumps(
        capture(args.start, args.end, fetch=_fetch), indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
