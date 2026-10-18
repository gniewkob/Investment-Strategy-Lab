"""Provenance and as-of price rules; strictly offline, no brokerage operations."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

TOKEN = re.compile(r"^[A-Za-z0-9_\-]{2,100}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")


def utc(raw: str) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("Timestamp must be ISO8601 with timezone")
    try:
        x = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid ISO8601 timestamp") from exc
    if x.tzinfo is None:
        raise ValueError("Missing timezone")
    return x.astimezone(timezone.utc)


def canonical_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def fingerprint(data: object) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def parse_observation(row: dict) -> dict:
    """Fail closed on missing source, negative values, early availability or bad versions."""
    key = (row["instrument_code"], row["source_code"], row["interval_code"])
    if not all(isinstance(v, str) and TOKEN.fullmatch(v) for v in key):
        raise ValueError("Invalid series identifier")
    if row["interval_code"] not in ("1d", "1w", "1mo", "spot"):
        raise ValueError("Unknown interval")
    if row["value_concept"] not in ("DAILY_SPOT", "MONTHLY_AVERAGE", "FX_REFERENCE", "OTHER_REFERENCE"):
        raise ValueError("Unknown value concept")
    if row["interval_code"] == "1mo" and row["value_concept"] == "DAILY_SPOT":
        raise ValueError("Monthly averages cannot masquerade as spot")
    revision = row["revision_no"]
    if type(revision) is not int or revision < 1:
        raise ValueError("Invalid revision")
    try:
        price = Decimal(str(row["price_value"]))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid price") from exc
    if not price.is_finite() or price <= 0:
        raise ValueError("Price must be positive and finite")
    document = row["document"]
    url = document["canonical_url"]
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError("Require HTTPS source URL")
    sha = document["sha256_hex"]
    if not isinstance(sha, str) or not HEX64.fullmatch(sha):
        raise ValueError("Require valid SHA256")
    published = utc(document["published_at"])
    precision = document["publication_precision"]
    if precision not in ("EXACT", "DAY"):
        raise ValueError("Unknown publication precision")
    # Conservative: DAY-precision publication becomes available next UTC day.
    earliest = (published.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                if precision == "DAY" else published)
    available = utc(row["available_at"])
    observed = utc(row["observed_for"])
    if available < earliest or available < observed:
        raise ValueError("Future information leakage: early available_at")
    return {**row, "_observed": observed, "_available": available,
            "_published": published, "_price": price}


def select_asof(rows: list[dict], as_of: str) -> list[dict]:
    """Choose latest legitimately public revision per time series/period."""
    cutoff = utc(as_of)
    selected: dict[tuple, dict] = {}
    seen_versions: set[tuple] = set()
    for raw in rows:
        r = parse_observation(raw)
        key = (r["instrument_code"], r["source_code"], r["observed_for"], r["interval_code"])
        version_key = (*key, r["revision_no"])
        if version_key in seen_versions:
            raise ValueError("Duplicate revision key")
        seen_versions.add(version_key)
        if r["_available"] > cutoff:
            continue
        current = selected.get(key)
        if current is None or (r["_available"], r["revision_no"]) > (current["_available"], current["revision_no"]):
            selected[key] = r
    return [{"instrument_code": r["instrument_code"],
             "source_code": r["source_code"], "observed_for": r["observed_for"],
             "interval_code": r["interval_code"], "revision_no": r["revision_no"],
             "price_value": str(r["_price"]),
             "available_at": r["_available"].isoformat(),
             "source_sha256": r["document"]["sha256_hex"]}
            for _, r in sorted(selected.items())]
