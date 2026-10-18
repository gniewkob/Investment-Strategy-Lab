"""Geopolitical & macroeconomic context for EDUCATIONAL opportunity research.

An event is an externally sourced observation, not an automatic return signal.
This module never fetches news, predicts market prices, executes trades,
inserts database records or retroactively grants a historical vintage.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from urllib.parse import urlsplit

MAX_EVENTS = 40
KINDS = frozenset({
    "CENTRAL_BANK_POLICY", "INFLATION", "ECONOMIC_GROWTH",
    "LABOR_MARKET", "SOVEREIGN_POLICY", "FISCAL_POLICY",
    "TRADE_TARIFF", "SANCTIONS", "CONFLICT_SECURITY",
    "SUPPLY_CHAIN", "ENERGY_SUPPLY", "COMMODITY_DEMAND",
    "FINANCIAL_STABILITY", "REGULATION",
})
CHANNELS = frozenset({
    "COST_OF_CAPITAL", "LIQUIDITY", "FX", "COMMODITY_SUPPLY",
    "COMMODITY_DEMAND", "TRANSPORT", "TRADE_FRICTION",
    "RISK_PREMIUM", "EARNINGS", "INFLATION_EXPECTATIONS",
})
CONFIRMATION = frozenset({"CONFIRMED_OFFICIAL", "REPORTED_UNCONFIRMED"})
EVIDENCE_GRADES = frozenset({"PRIMARY_OFFICIAL", "SECONDARY_CITED"})
SOURCE_DOMAINS = (
    "eia.gov", "iea.org", "imf.org", "oecd.org", "worldbank.org",
    "federalreserve.gov", "ecb.europa.eu", "nbp.pl", "stat.gov.pl",
    "ec.europa.eu", "gov.pl", "gov.uk", "gov",
)


def _instant(text: str) -> datetime:
    if not isinstance(text, str):
        raise ValueError("Missing timestamp")
    try:
        x = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid context timestamp") from None
    if x.tzinfo is None:
        raise ValueError("Context timestamp must be timezone aware")
    return x.astimezone(timezone.utc)


def _validated_https(url: str) -> bool:
    if not isinstance(url, str) or len(url) > 800:
        return False
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        return (p.scheme == "https" and p.username is None
                and p.password is None and p.port in (None, 443)
                and any(host == suffix or host.endswith("." + suffix)
                        for suffix in SOURCE_DOMAINS))
    except ValueError:
        return False


def analyze_context(snapshot: dict, radar: dict) -> dict:
    """Strictly observed context, with counterevidence and lag, NO trade influence."""
    as_of = _instant(radar["as_of"])
    data = snapshot.get("context_events", [])
    if not isinstance(data, list) or len(data) > MAX_EVENTS:
        raise ValueError("Invalid event context collection")
    if data and snapshot.get("context_source") != "UNVERIFIED_HISTORICAL_EVENT_VINTAGE":
        raise ValueError("Cannot assert past historical source vintage")
    if not data:
        return {
            "status": "NO_CONTEXT_EVIDENCE",
            "events": [], "context_events": 0,
            "source_vintage": "NO_EVENTS",
            "causal_effect_established": False,
            "market_prediction_allowed": False,
            "trade_or_allocation_allowed": False,
        }

    known = {x["instrument_code"] for x in radar["series"]}
    valid = []
    keys = set()
    for event in data:
        if not isinstance(event, dict):
            raise ValueError("Invalid event record")
        kind = event.get("category")
        channel = event.get("transmission_channel")
        if kind not in KINDS or channel not in CHANNELS:
            raise ValueError("Unsupported policy/geopolitical evidence category")
        if event.get("confirmation_status") not in CONFIRMATION:
            raise ValueError("Unverified event status")
        if event.get("evidence_grade") not in EVIDENCE_GRADES:
            raise ValueError("Unverified source quality")
        if not _validated_https(event.get("canonical_source_url")):
            raise ValueError("Unapproved source URL")
        published = _instant(event.get("published_at"))
        retrieved = _instant(event.get("retrieved_at"))
        if published > retrieved or retrieved > as_of:
            raise ValueError("Future/retroactively available event evidence")
        affected = event.get("reference_series", [])
        if not isinstance(affected, list) or len(affected) > 12:
            raise ValueError("Invalid affected series")
        if any(not isinstance(c, str) or c not in known for c in affected):
            raise ValueError("Event names a series not analyzed by research")
        if len(affected) != len(set(affected)):
            raise ValueError("Duplicate affected series")
        uid = event.get("event_key")
        if not isinstance(uid, str) or not 8 <= len(uid) <= 90 or uid in keys:
            raise ValueError("Invalid or duplicate event key")
        if not all(c.isalnum() or c in "-_" for c in uid):
            raise ValueError("Unsafe event key")
        keys.add(uid)
        if not isinstance(event.get("source_name"), str) or not 2 <= len(event["source_name"]) <= 100:
            raise ValueError("Invalid source name")
        if event.get("mechanism") not in (
            "HYPOTHESIZED_TRANSMISSION_ONLY",
        ):
            raise ValueError("No causal conclusion allowed")
        counter = event.get("counterargument")
        if not isinstance(counter, str) or not 12 <= len(counter) <= 300:
            raise ValueError("Explicit counterargument required")
        valid.append({
            "event_key": uid,
            "category": kind,
            "transmission_channel": channel,
            "source_name": event["source_name"],
            "canonical_source_url": event["canonical_source_url"],
            "confirmation_status": event["confirmation_status"],
            "published_at": published.isoformat(),
            "retrieved_at": retrieved.isoformat(),
            "reference_series": sorted(affected),
            "mechanism": "HYPOTHESIZED_TRANSMISSION_ONLY",
            "counterargument": counter,
            "historical_vintage_status": "UNVERIFIED_HISTORICAL_EVENT_VINTAGE",
            "causality_verified": False,
            "possible_direction_established": False,
        })
    valid.sort(key=lambda row: (row["published_at"], row["event_key"]))
    evidence_fingerprint = hashlib.sha256(
        json.dumps(valid, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "status": "CONTEXT_HYPOTHESES_ONLY",
        "source_vintage": "UNVERIFIED_HISTORICAL_EVENT_VINTAGE",
        "context_events": len(valid),
        "events": valid,
        "context_sha256": evidence_fingerprint,
        "causal_effect_established": False,
        "market_prediction_allowed": False,
        "trade_or_allocation_allowed": False,
    }
