"""Official BondSpot TBSP.Index date-page collector (non-executable benchmark).

This is a research-only collector. It never changes portfolios or Neon.
The official BondSpot archive is a daily dated HTML page; month calendars
link to dates. We select the last *published* date in a month, not a
fabricated calendar-end quote. Exact HTML body bytes are SHA-256 sealed.

TBSP is a PLN bond total-return BENCHMARK, not a tradable bond/ETF
fill price. Retrieved publication timestamps do NOT certify the first
historical availability/vintage or reuse rights.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

HOST = "www.bondspot.pl"
PATH = "/tbsp_index_archiwum"
DATE8 = re.compile(r"^\d{8}$")
DATE10 = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH = re.compile(r"^\d{4}-\d{2}$")
PRICE = re.compile(r"^\d+(?:\.\d+)?$")
# Dated row from "Data | Wartość otwarcia | Wartość zamknięcia".
ROW = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})\s+([0-9]+[.,][0-9]+)\s+([0-9]+[.,][0-9]+)(?!\d)")
MAX_MONTHS = 72


class ArchiveHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hrefs: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for key, value in attrs:
                if key == "href" and value:
                    self.hrefs.append(value)


def _url(month: str, date8: str | None = None) -> str:
    year, mm = month.split("-")
    query = {"month": mm, "year": year}
    if date8:
        query["date"] = date8
    return f"https://{HOST}{PATH}?" + urlencode(query)


def _read(url: str) -> bytes:
    req = Request(url, headers={"User-Agent":"ISL-research-source-evidence/1",
                                "Accept":"text/html"})
    with urlopen(req, timeout=20) as response:
        if response.url and urlsplit(response.url).hostname != HOST:
            raise ValueError("BondSpot redirect to unexpected host")
        if response.status != 200:
            raise OSError("BondSpot unexpected HTTP status")
        return response.read(3_000_000)


def _parse(data: bytes) -> ArchiveHTML:
    if not isinstance(data, bytes) or not data:
        raise ValueError("nonempty official HTML required")
    parser = ArchiveHTML()
    parser.feed(data.decode("utf-8", errors="replace"))
    if not any("TBSP" in x for x in parser.parts):
        raise ValueError("page does not identify TBSP")
    return parser


def _calendar_dates(page: ArchiveHTML, month: str) -> list[date]:
    y, m = [int(x) for x in month.split("-")]
    dates = set()
    for href in page.hrefs:
        u = urlsplit(urljoin("https://" + HOST + PATH, href))
        if u.scheme != "https" or u.hostname != HOST or u.path != PATH:
            continue
        args = parse_qs(u.query)
        raw = args.get("date", [""])[0]
        if not DATE8.fullmatch(raw):
            continue
        day = date.fromisoformat(raw[:4] + "-" + raw[4:6] + "-" + raw[6:])
        if day.year == y and day.month == m:
            dates.add(day)
    return sorted(dates)


def _day_row(page: ArchiveHTML, exact_date: date) -> str:
    # Restrict to the archive section rather than the current index summary.
    text = " ".join(x.strip() for x in page.parts if x.strip())
    section = text.find("Dane archiwalne TBSP.Index")
    if section < 0:
        raise ValueError("missing TBSP archive content")
    text = text[section:]
    candidates = [(d,a,b) for d,a,b in ROW.findall(text)
                  if d == exact_date.isoformat()]
    if len(candidates) != 1:
        raise ValueError("not exactly one official dated close row")
    _, _, close = candidates[0]
    value = close.replace(",", ".")
    if not PRICE.fullmatch(value) or not Decimal(value).is_finite() or Decimal(value)<=0:
        raise ValueError("invalid TBSP closing value")
    return str(Decimal(value))


def _months(first: str, last: str) -> list[str]:
    for term in (first,last):
        if not isinstance(term,str) or not MONTH.fullmatch(term):
            raise ValueError("expected YYYY-MM")
    fy,fm = map(int,first.split("-"))
    ty,tm = map(int,last.split("-"))
    if not (2007 <= fy <= 2100 and 2007 <= ty <= 2100
            and 1 <= fm <= 12 and 1 <= tm <= 12
            and (fy,fm) <= (ty,tm)):
        raise ValueError("invalid or reversed calendar")
    months=[]
    y,m=fy,fm
    while (y,m) <= (ty,tm):
        months.append(f"{y:04d}-{m:02d}")
        if len(months)>MAX_MONTHS:
            raise ValueError("at most 72 monthly observations per run")
        y,m=(y+1,1) if m==12 else (y,m+1)
    return months


def collect(first: str, last: str, *, fetch=_read,
            clock=lambda: datetime.now(timezone.utc)) -> dict:
    months=_months(first,last)
    now=clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware retrieval clock required")
    now=now.astimezone(timezone.utc)
    if date(*map(int,months[-1].split("-")),1) >= date(now.year,now.month,1):
        raise ValueError("monthly archive requires completed months")
    observations=[]
    for month in months:
        url=_url(month)
        raw=fetch(url)
        calendar_page=_parse(raw)
        all_dates=_calendar_dates(calendar_page,month)
        if not all_dates:
            raise ValueError("no dated TBSP archive links for "+month)
        selected=all_dates[-1]
        dated_url=_url(month,selected.strftime("%Y%m%d"))
        dated_raw=fetch(dated_url)
        dated_page=_parse(dated_raw)
        closing=_day_row(dated_page,selected)
        at=clock()
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("timezone-aware clock required")
        observations.append({
            "month":month,"observed_for":selected.isoformat(),
            "level":closing,"currency":"PLN",
            "basis":"BOND_TOTAL_RETURN_BENCHMARK_INDEX",
            "instrument_kind":"NON_TRADABLE_INDEX",
            "calendar_url":url,"calendar_sha256":sha256(raw).hexdigest(),
            "dated_url":dated_url,"dated_sha256":sha256(dated_raw).hexdigest(),
            "retrieved_at":at.astimezone(timezone.utc).isoformat(),
            "historical_first_usable_at":None,
        })
    evidence={
        "source":"BONDSPOT_TBSP_OFFICIAL_ARCHIVE",
        "source_vintage":"HISTORICAL_RETRIEVAL_2026_NOT_AS_PUBLISHED",
        "series_id":"BONDSPOT_TBSP_CLOSE_PLN",
        "basis":"BOND_TOTAL_RETURN_BENCHMARK_INDEX",
        "instrument_kind":"NON_TRADABLE_INDEX",
        "months":len(observations),
        "first_month":first,"last_month":last,
        "observations":observations,
        "historical_pit_certified":False,
        "tradable_fills_authorized":False,
        "paper_events_created":0,
        "financial_operations":0,
        "backtest":"NOT_RUN_SOURCE_ONLY",
    }
    raw=json.dumps(evidence,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    evidence["evidence_sha256"]=sha256(raw).hexdigest()
    return evidence


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start-month",required=True)
    p.add_argument("--end-month",required=True)
    p.add_argument("--out",help="write full original-source evidence JSON; console prints only summary")
    args=p.parse_args()
    result=collect(args.start_month,args.end_month)
    if args.out:
        from pathlib import Path
        dest=Path(args.out)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        summary={
            "series_id":result["series_id"],
            "first_month":result["first_month"],
            "last_month":result["last_month"],
            "months":result["months"],
            "evidence_sha256":result["evidence_sha256"],
            "first_observation":result["observations"][0]["observed_for"],
            "last_observation":result["observations"][-1]["observed_for"],
            "historical_pit_certified":False,
            "backtest":"NOT_RUN_SOURCE_ONLY",
            "financial_operations":0,
        }
        print("TBSP_ARCHIVE_SUMMARY="+json.dumps(summary,sort_keys=True,separators=(",",":")))
    else:
        print("TBSP_ARCHIVE_PROBE_JSON="+json.dumps(result,sort_keys=True,separators=(",",":")))


if __name__=="__main__":
    main()
