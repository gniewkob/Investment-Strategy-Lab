"""Content-addressed *semantic* fingerprints of official EIA daily spot observations.

Compare original HTML byte hashes against these canonical date/value digests.
An HTML template change may change raw SHA without changing any quote.
Neither digest authenticates historical first-publication timestamps.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import hashlib
import json

from src.isl_v2.eia_sources import SOURCES, Snapshot, SourceFormatError


def semantic_evidence(snapshot: Snapshot) -> dict:
    """Canonical, stable metadata for the exact decoded EIA date/price series.

    Enforces strictly increasing unique dates, identity, positive finite
    Decimal values, and a fixed instrument unit. Does not emit prices.
    """
    source = next(
        (slug for slug, triple in SOURCES.items()
         if triple == (snapshot.instrument_code, snapshot.source_code,
                       snapshot.url)), None)
    if source is None or not snapshot.observations:
        raise SourceFormatError("Unknown or empty EIA semantic evidence")
    unit = "USD/MMBtu" if source == "henry_hub" else "USD/bbl"
    previous: date | None = None
    quotes: list[list[str]] = []
    for row in snapshot.observations:
        if (not isinstance(row.observed_on, date)
                or (previous is not None and row.observed_on <= previous)
                or type(row.price) is not Decimal
                or not row.price.is_finite() or row.price <= 0):
            raise SourceFormatError("EIA semantic observations not strictly valid")
        previous = row.observed_on
        # Decimal('100.00') and Decimal('1E+2') are the same price, and
        # must hash identically: the EIA display format is not a revision.
        quotes.append([row.observed_on.isoformat(), format(row.price.normalize(), "f")])
    canonical = {
        "schema": "EIA_DAILY_SPOT_DATE_PRICE_V1",
        "source_code": snapshot.source_code,
        "instrument_code": snapshot.instrument_code,
        "unit": unit,
        "observations": quotes,
    }
    serialized = json.dumps(canonical, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"), allow_nan=False).encode("utf-8")
    return {
        "semantic_schema": "EIA_DAILY_SPOT_DATE_PRICE_V1",
        "semantic_observations_sha256": hashlib.sha256(serialized).hexdigest(),
        "semantic_observation_count": len(quotes),
        "first_observed": quotes[0][0],
        "last_observed": quotes[-1][0],
        "unit": unit,
        "historical_publication_vintages_verified": False,
    }
