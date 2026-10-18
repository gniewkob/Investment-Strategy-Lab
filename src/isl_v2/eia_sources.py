"""Strict EIA daily spot-price snapshot parsing; NO broker or trade integrations.

Publication chronology: 'Release Date' describes the current EIA webpage
snapshot, NOT when each older observation was first published. A historical
backfill from this page must not be treated as available before fetch time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import hashlib
import re

SOURCES = {
    "brent": ("BRENT_EIA_USD_BBL", "eia_brent_daily", "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"),
    "wti": ("WTI_EIA_USD_BBL", "eia_wti_daily", "https://www.eia.gov/dnav/pet/hist/RWTCd.htm"),
    "henry_hub": ("HENRY_HUB_USD_MMBTU", "eia_henryhub_daily", "https://www.eia.gov/dnav/ng/hist/rngwhhdD.htm"),
}
MONTHS = {k: v for v, k in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
ROW = re.compile(r"^\s*(\d{4})\s+([A-Za-z]{3})-\s*(\d{1,2})\s+to\s+([A-Za-z]{3})-\s*(\d{1,2})\s*$")
RELEASE = re.compile(r"\bRelease\s+Date:\s*(\d{1,2})/(\d{1,2})/(\d{4})\b", re.I)
NUMBER = re.compile(r"\d+(?:\.\d+)?")
MISSING = {"", "-", "--", "NA", "W"}

class SourceFormatError(ValueError):
    pass

class _TableReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._cell = None
        self._depth = 0
        self.words = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._depth = 1
        elif self._cell is not None:
            self._depth += 1

    def handle_data(self, data):
        self.words.append(data)
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join(self._cell).strip())
            self._cell = None
            self._depth = 0
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

@dataclass(frozen=True)
class Spot:
    observed_on: date
    price: Decimal

@dataclass(frozen=True)
class Snapshot:
    instrument_code: str
    source_code: str
    url: str
    sha256_hex: str
    release_day: date
    downloaded_at: datetime
    observations: tuple[Spot, ...]
    raw_count: int

def parse_snapshot(source: str, html: bytes, downloaded_at: datetime,
                   *, max_age_days: int = 420) -> Snapshot:
    if source not in SOURCES:
        raise SourceFormatError("Unrecognised EIA source")
    if downloaded_at.tzinfo is None:
        raise SourceFormatError("UTC-aware retrieval time required")
    now = downloaded_at.astimezone(timezone.utc)
    if not (0 < len(html) <= 8_000_000):
        raise SourceFormatError("Empty or oversized EIA response")
    try:
        page = html.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SourceFormatError("EIA HTML is not valid UTF-8") from exc
    parsed = _TableReader()
    parsed.feed(page)
    text = " ".join(parsed.words)
    releases = RELEASE.findall(text)
    if len(releases) != 1:
        raise SourceFormatError("Exactly one EIA Release Date is required")
    month, day, year = (int(x) for x in releases[0])
    released = date(year, month, day)
    if released > now.date():
        raise SourceFormatError("Future release date")
    cutoff = now.date() - timedelta(days=max_age_days)
    observations = {}
    raw_count = 0
    for cells in parsed.rows:
        if not cells:
            continue
        found = ROW.match(cells[0].replace("\xa0", " "))
        if not found:
            continue
        if len(cells) != 6:
            raise SourceFormatError("EIA daily row requires five price columns")
        year = int(found[1])
        start_month, end_month = MONTHS.get(found[2].title()), MONTHS.get(found[4].title())
        if start_month is None or end_month is None:
            raise SourceFormatError("Unexpected EIA month name")
        start = date(year, start_month, int(found[3]))
        end = date(year + int(end_month < start_month), end_month, int(found[5]))
        if start.weekday() != 0 or end - start != timedelta(days=4):
            raise SourceFormatError("EIA row is not a Monday-Friday interval")
        for offset, raw_price in enumerate(cells[1:]):
            quoted_day = start + timedelta(days=offset)
            price_text = raw_price.strip().replace("\xa0", " ")
            if price_text.upper() in MISSING:
                continue
            if not NUMBER.fullmatch(price_text):
                raise SourceFormatError("Malformed EIA price cell")
            try:
                price = Decimal(price_text)
            except InvalidOperation as exc:
                raise SourceFormatError("Invalid EIA decimal") from exc
            if not price.is_finite() or price <= 0 or quoted_day > released:
                raise SourceFormatError("Invalid EIA price or future observation")
            raw_count += 1
            if quoted_day < cutoff:
                continue
            prior = observations.setdefault(quoted_day, price)
            if prior != price:
                raise SourceFormatError("Conflicting EIA prices for the same date")
    if raw_count < 15 or not observations:
        raise SourceFormatError("Too few complete official EIA price observations")
    instrument, source_code, url = SOURCES[source]
    return Snapshot(instrument, source_code, url, hashlib.sha256(html).hexdigest(),
                    released, now, tuple(Spot(d, v) for d, v in sorted(observations.items())), raw_count)
