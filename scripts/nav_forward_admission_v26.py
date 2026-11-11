"""v0.26 active NAV admission safety wrapper around immutable v0.23 evidence.

The pinned v0.22/v0.23 historical source and freeze anchor are preserved.
This wrapper is the active admission entry point for all v0.24/v0.25
provider acquisition paths. Research-only; no data source promotion.
"""
from __future__ import annotations

from datetime import date

from scripts import nav_forward_admission_v23 as v23


def admission(frozen, candidate=None, *, clock):
    """Require the provider export to be acquired AFTER the full month ends."""
    result = v23.admission(frozen, candidate, clock=clock)
    if candidate is not None:
        observed = date.fromisoformat(candidate["observed_for"])
        start_next = date(observed.year + (observed.month == 12),
                          observed.month % 12 + 1, 1)
        acquired = v23._utc(candidate["original_export_retrieved_at_utc"])
        if acquired.date() < start_next:
            raise ValueError("original export must postdate completed observed month")
    return result
