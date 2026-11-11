"""Emit a reproducible official-NBP receipt and validated SQL, without DB access.

Only scheduled job/operator with Neon access executes the emitted statement.
Stdout is public source metadata and a complete SQL statement, no secrets.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

from scripts.nbp_lab_prepare import prepare
from scripts.nbp_lab_ingest_sql import build_sql


def daily_source(now: datetime | None = None, *, fetch=None, clock=None, lookback_days: int = 31):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware current time required")
    if not isinstance(lookback_days, int) or not 7 <= lookback_days <= 90:
        raise ValueError("lookback_days must be 7..90")
    end = now.astimezone(timezone.utc).date()
    start = end - timedelta(days=lookback_days)
    options = {}
    if fetch is not None:
        options["fetch"] = fetch
    if clock is not None:
        options["clock"] = clock
    receipt = prepare(start.isoformat(), end.isoformat(), **options)
    sql = build_sql(receipt)
    if not sql.startswith("WITH raw AS (SELECT ") or not sql.endswith("0 AS paper_events_created,0 AS financial_operations"):
        raise ValueError("unexpected compiled SQL")
    if "\x00" in sql or "\n\n\n" in sql:
        raise ValueError("unexpected SQL encoding")
    executable = " ".join(sql.splitlines())
    source = receipt["source_receipts"]
    meta = {
        "source": receipt["source"],
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "captured_rows": receipt["row_count"],
        "by_series": receipt["by_series"],
        "nbp_raw_sha256_fx": source["fx"]["sha256"],
        "nbp_raw_sha256_gold": source["gold"]["sha256"],
        "fx_retrieved_at": source["fx"]["retrieved_at"],
        "gold_retrieved_at": source["gold"]["retrieved_at"],
        "compiled_sql_sha256": sha256(executable.encode("utf-8")).hexdigest(),
        "validated_sql_only": True,
        "paper_events_created": 0,
        "financial_operations": 0,
        "source_data_not_total_return": True,
    }
    return meta, executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lookback-days", type=int, default=31)
    args = parser.parse_args()
    meta, sql = daily_source(lookback_days=args.lookback_days)
    print("NBP_LAB_DAILY_META=" + json.dumps(meta, separators=(",", ":"), sort_keys=True))
    print("NBP_LAB_DAILY_SQL=" + sql)


if __name__ == "__main__":
    main()
