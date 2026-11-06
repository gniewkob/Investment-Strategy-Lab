"""BondSpot TBSP.Index month-end research candidate collector.

Reads ONLY the official public date-specific archive HTML. It searches
backwards from the calendar month end, accepting the last date with an
explicit dated closing index value. This is an NON-TRADABLE total-return
benchmark, not a fill price, fund NAV or a paper-trade instruction.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import re
from pathlib import Path
from urllib.request import urlopen, Request

from scripts.official_market_source_probe_v04 import _Extractor, MAX_BYTES, _official_url

HOST = "www.bondspot.pl"
BASE = "https://www.bondspot.pl/tbsp_index_archive_en"
MONTH = re.compile(r"^\d{4}-\d{2}$")
VALUE = r"([0-9]{3,5}(?:[.,][0-9]{1,4})?)"


def _month(value):
    if not isinstance(value, str) or not MONTH.fullmatch(value):
        raise ValueError("YYYY-MM expected")
    y, m = (int(v) for v in value.split("-"))
    if not 1 <= m <= 12 or not 2006 <= y <= 2100:
        raise ValueError("month outside TBSP archive supported dates")
    return y, m


def _months(first, last):
    a, b = _month(first), _month(last)
    if a > b:
        raise ValueError("start_month after end_month")
    result = []
    while a <= b:
        result.append(f"{a[0]:04d}-{a[1]:02d}")
        a = (a[0] + (a[1] == 12), 1 if a[1] == 12 else a[1] + 1)
    if len(result) > 72:
        raise ValueError("maximum 72 months per run")
    return result


def _url(day):
    return f"{BASE}?date={day:%Y%m%d}&month={day:%m}&year={day:%Y}"


def _fetch(url):
    _official_url(url, HOST)
    req = Request(url, headers={
        "Accept": "text/html",
        "User-Agent": "Mozilla/5.0 (compatible; ISL-public-index-research/0.4)"
    })
    with urlopen(req, timeout=20) as response:
        _official_url(response.geturl(), HOST)
        if response.status != 200 or "text/html" not in response.headers.get("Content-Type", ""):
            raise ValueError("unexpected BondSpot response")
        b = response.read(MAX_BYTES + 1)
        if len(b) > MAX_BYTES:
            raise ValueError("BondSpot page too large")
        return b


def parse_close(day: date, raw: bytes) -> str | None:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError("bounded official page required")
    extractor = _Extractor()
    extractor.feed(raw.decode("utf-8-sig"))
    visible = " ".join(extractor.parts)
    # Exact date row: page headline may show a DIFFERENT "current" quote.
    pattern = rf"\b{day:%Y-%m-%d}\b\s+{VALUE}\s+{VALUE}\b"
    rows = re.findall(pattern, visible)
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("ambiguous duplicate date-specific index row")
    close = Decimal(rows[0][1].replace(",", "."))
    if not close.is_finite() or close <= 0:
        raise ValueError("invalid TBSP closing value")
    return format(close, "f")


def collect(first: str, last: str, *, fetch=_fetch, clock=None, max_days_back=8):
    if not isinstance(max_days_back, int) or not 1 <= max_days_back <= 10:
        raise ValueError("max_days_back must be 1..10")
    months = _months(first, last)
    now = clock() if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware clock required")
    end_y, end_m = _month(months[-1])
    if date(end_y, end_m, calendar.monthrange(end_y, end_m)[1]) > now.date():
        raise ValueError("only completed months")
    monthly = []
    for month in months:
        y, m = _month(month)
        end = date(y, m, calendar.monthrange(y, m)[1])
        receipt = None
        for i in range(max_days_back):
            day = end - timedelta(days=i)
            if day.weekday() >= 5:
                continue
            url = _url(day)
            raw = fetch(url)
            level = parse_close(day, raw)
            if level is None:
                continue
            receipt = {
                "month": month, "observed_for": day.isoformat(),
                "value": level, "source_url": url,
                "raw_sha256": sha256(raw).hexdigest(),
                "retrieved_at": now.astimezone(timezone.utc).isoformat(),
                "return_basis": "BOND_TOTAL_RETURN_BENCHMARK_INDEX",
                "instrument_kind": "NON_TRADABLE_INDEX",
                "quote_currency": "PLN",
            }
            break
        if receipt is None:
            raise ValueError(f"NO_VERIFIED_BONDSPOT_CLOSE_WITHIN_{max_days_back}_DAYS: {month}")
        monthly.append(receipt)
    result = {
        "source": "BONDSPOT_OFFICIAL_ARCHIVE",
        "identity": "TBSP.Index", "first_month": first, "last_month": last,
        "monthly": monthly, "months": len(months),
        "return_basis": "BOND_TOTAL_RETURN_BENCHMARK_INDEX",
        "instrument_kind": "NON_TRADABLE_INDEX",
        "historical_first_available_verified": False,
        "history_36_months_verified": len(months) >= 36,
        "executable_price_verified": False,
        "backtest": "NOT_RUN_PENDING_SOURCE_VALIDATION",
        "paper_events_created": 0, "financial_operations": 0,
    }
    result["evidence_sha256"] = sha256(json.dumps(result, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start-month", required=True)
    p.add_argument("--end-month", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    data = collect(args.start_month, args.end_month)
    args.out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print("BONDSPOT_MONTHLY_RECEIPT=" + json.dumps({
        "months": data["months"], "first": data["first_month"],
        "last": data["last_month"], "evidence_sha256": data["evidence_sha256"],
        "last_close": data["monthly"][-1]["value"],
        "backtest": data["backtest"], "financial_operations": 0
    }, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
