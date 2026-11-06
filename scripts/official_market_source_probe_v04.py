"""Read-only official Vanguard/BondSpot historical source capability probe.

One official URL per provider, no secrets, no database, no trading, no
historical completeness claims. Fail closed on unexpected host or response.
Source bytes are hashed and retained as short, inspectable research receipts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SOURCES = {
    "vanguard_nav_usd_acc": (
        "https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits",
        "www.vanguard.co.uk", "IE00BK5BQT80",
    ),
    "bondspot_tbsp_total_return_benchmark": (
        "https://www.bondspot.pl/tbsp_index_archive_en?date=20240216&month=02&year=2024",
        "www.bondspot.pl", "2024-02-16",
    ),
}
MAX_BYTES = 2_000_000


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if not self.depth:
            s = " ".join(data.split())
            if s:
                self.parts.append(s)


def _fetch(url):
    req = Request(url, headers={
        "Accept": "text/html",
        "User-Agent": "Mozilla/5.0 (compatible; ISL-official-source-research/0.4)",
    })
    with urlopen(req, timeout=22) as r:
        if r.status != 200:
            raise ValueError(f"unexpected HTTP {r.status}")
        final_url = r.geturl()
        _official_url(final_url, urlsplit(url).hostname)
        content_type = r.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            raise ValueError(f"unexpected content-type: {content_type}")
        raw = r.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("official page too large")
    return raw, final_url


def _official_url(url, expected_host):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != expected_host
            or parts.username or parts.password or parts.fragment):
        raise ValueError("source changed host or protocol")
    return url


def parse_snapshot(key, raw, *, final_url=None, retrieved_at=None):
    if key not in SOURCES:
        raise ValueError("unknown official source")
    url, host, identity = SOURCES[key]
    _official_url(final_url or url, host)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError("nonempty bounded official HTML required")
    try:
        body = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("non-UTF8 official HTML") from exc
    parser = _Extractor()
    parser.feed(body)
    visible = " ".join(parser.parts)
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("timezone-aware collection timestamp required")
    detected_identity = identity in visible or identity in body
    nav_evidence = ("Historical Prices" in visible
                    and ("NAV (USD)" in visible or "NAV Price (USD)" in visible)
                    and "Accumulating" in visible) if key.startswith("vanguard") else None
    bond_match = re.search(
        r"\b2024-02-16\b\s+([0-9]{3,5}(?:[.,][0-9]{1,4})?)\s+([0-9]{3,5}(?:[.,][0-9]{1,4})?)\b",
        visible
    ) if key.startswith("bondspot") else None
    # Treat provider page visibility as source feasibility, never as a
    # verified 36-month monthly data series.
    parse_status = (
        "SOURCE_PAGE_VISIBLE_CANDIDATE" if detected_identity and
        (nav_evidence if key.startswith("vanguard") else bond_match is not None)
        else "SOURCE_PAGE_UNVERIFIED"
    )
    sample = None
    if bond_match:
        opening, closing = bond_match.groups()
        sample = {"observed_for": "2024-02-16",
                  "opening": opening, "closing": closing,
                  "currency": "PLN",
                  "return_basis": "BOND_TOTAL_RETURN_BENCHMARK_INDEX",
                  "instrument_kind": "NON_TRADABLE_INDEX"}
    return {
        "source": key,
        "provider": host,
        "url": final_url or url,
        "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat(),
        "response_bytes": len(raw),
        "raw_sha256": sha256(raw).hexdigest(),
        "source_identity_detected": detected_identity,
        "visible_text_length": len(visible),
        "nav_table_heading_detected": nav_evidence,
        "sample": sample,
        "parse_status": parse_status,
        "history_36_months_verified": False,
        "historical_first_usable_at_verified": False,
        "executable_price_verified": False,
        "research_backtest_status": "NOT_RUN",
        "paper_events_created": 0,
        "financial_operations": 0,
    }


def probe(fetch=_fetch):
    out = {}
    for key, (url, host, _) in SOURCES.items():
        _official_url(url, host)
        raw, final = fetch(url)
        out[key] = parse_snapshot(key, raw, final_url=final)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json-output", default=None)
    args = p.parse_args()
    result = probe()
    report = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_output:
        from pathlib import Path
        Path(args.json_output).write_text(report + "\n", encoding="utf-8")
    print("OFFICIAL_SOURCE_PROBE=" + json.dumps(result, separators=(",", ":"),
                                                  ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
