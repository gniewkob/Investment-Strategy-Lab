"""Separate bounded official NBP receipts; no alteration of pinned A2 adapter.

No combined fake original HTTP body or first-publication/PIT claim.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from scripts.nbp_reference_capture import capture


def capture_chunked(start, end, *, fetch=None,
                    clock=lambda: datetime.now(timezone.utc), chunk_days=10):
    """Read contiguous subranges and retain each real URL and raw SHA-256.

    ``chunks`` is a list of original response receipts, not a new original
    response fingerprint; no missing market observations are filled.
    """
    if fetch is None:
        raise ValueError("EXPLICIT_FETCH_REQUIRED")
    begin, finish = date.fromisoformat(start), date.fromisoformat(end)
    if (finish < begin or (finish - begin).days >= 93 or type(chunk_days) is not int
            or not 1 <= chunk_days <= 31):
        raise ValueError("invalid bounded NBP chunk interval")
    output = None
    cursor = begin
    while cursor <= finish:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), finish)
        item = capture(cursor.isoformat(), chunk_end.isoformat(), fetch=fetch, clock=clock)
        if output is None:
            output = {**item, "start": start, "end": end,
                      "receipts": {"fx": {"chunks": []}, "gold": {"chunks": []}},
                      "series": {"usdpln": [], "eurpln": [], "gold": []}}
        for kind in ("fx", "gold"):
            output["receipts"][kind]["chunks"].append(item["receipts"][kind])
        for kind, rows in item["series"].items():
            output["series"][kind].extend(rows)
        cursor = chunk_end + timedelta(days=1)
    for rows in output["series"].values():
        days = [row["publication_date"] for row in rows]
        if len(days) != len(set(days)):
            raise ValueError("duplicate publication date across NBP chunks")
    return output
