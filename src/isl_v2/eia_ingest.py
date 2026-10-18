"""Optional EIA snapshot ingestion for controlled research staging only.

No execution/trading API. All source URLs come from an allowlist. The CLI's
default is read-only validation; --write requires explicit staging opt-in and
an externally supplied, least-privileged database credential.

Backfilling a historical observation today does NOT make it available to an
agent that ran last year. Research availability is the later of current source
retrieval and the conservative next-day release-date gate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, time, timezone
from decimal import Decimal
import json
import os
import sys
from urllib.request import Request, urlopen

from .eia_sources import SOURCES, Snapshot, SourceFormatError, parse_snapshot


MAX_BYTES = 8_000_000


def fetch_official(source: str, now: datetime, *, opener=urlopen) -> Snapshot:
    if source not in SOURCES:
        raise SourceFormatError("Source not in EIA URL allowlist")
    url = SOURCES[source][2]
    req = Request(url, headers={"Accept": "text/html", "User-Agent": "ISL-Research-Source-Validator/2.0"})
    with opener(req, timeout=30) as response:
        if response.geturl() != url:
            raise SourceFormatError("Redirect away from allowlisted EIA URL")
        media = response.headers.get("Content-Type", "").lower()
        if "text/html" not in media:
            raise SourceFormatError("EIA response is not HTML")
        raw = response.read(MAX_BYTES + 1)
    return parse_snapshot(source, raw, now)


def summary(snapshot: Snapshot, *, today=None) -> dict:
    now_day = today if today is not None else snapshot.downloaded_at.date()
    age = (now_day - snapshot.observations[-1].observed_on).days
    return {
        "source_code": snapshot.source_code,
        "instrument_code": snapshot.instrument_code,
        "canonical_url": snapshot.url,
        "source_release_day": snapshot.release_day.isoformat(),
        "downloaded_at": snapshot.downloaded_at.isoformat(),
        "document_sha256": snapshot.sha256_hex,
        "first_observation": snapshot.observations[0].observed_on.isoformat(),
        "last_observation": snapshot.observations[-1].observed_on.isoformat(),
        "validated_observations": len(snapshot.observations),
        "source_age_days": age,
        "is_stale": age > 14,
        "no_live_execution": True,
    }


def store(cur, snapshot: Snapshot) -> dict:
    """Call INSIDE a transaction; caller commits on success and rolls back on error.

    A source-level advisory lock serializes revisions; all SQL values use bound
    parameters. No use of legacy price_observations, portfolio, or brokerage.
    """
    pub = datetime.combine(snapshot.release_day, time.min, tzinfo=timezone.utc)
    conservative_pub = pub + timedelta(days=1)
    if snapshot.downloaded_at < conservative_pub:
        raise SourceFormatError("Release date is day-precision; defer import until next UTC day")
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (snapshot.source_code,))
    cur.execute("SELECT source_code FROM investment_lab.data_sources WHERE source_code=%s", (snapshot.source_code,))
    if cur.fetchone() is None:
        raise SourceFormatError("Source catalogue entry missing; no source creation implicit")
    cur.execute("SELECT instrument_code FROM investment_lab.instruments WHERE instrument_code=%s", (snapshot.instrument_code,))
    if cur.fetchone() is None:
        raise SourceFormatError("Instrument catalogue entry missing; no instrument creation implicit")

    run_key = "eia-snapshot-" + snapshot.source_code + "-" + snapshot.sha256_hex[:24]
    cur.execute("SELECT status FROM investment_lab.pipeline_runs WHERE run_key=%s", (run_key,))
    old = cur.fetchone()
    if old is not None:
        if old[0] != "SUCCEEDED":
            raise SourceFormatError("Prior run not successful; do not silently mark as complete")
        return {"run_key": run_key, "new": 0, "revised": 0, "duplicate_run": True}

    cur.execute(
        """INSERT INTO investment_lab.source_documents
          (source_code,canonical_url,sha256_hex,published_at,publication_precision,
           retrieved_at,content_type,metadata)
          VALUES (%s,%s,%s,%s,'DAY',%s,'text/html',%s::jsonb)
          ON CONFLICT(source_code,canonical_url,sha256_hex) DO NOTHING""",
        (snapshot.source_code, snapshot.url, snapshot.sha256_hex, pub,
         snapshot.downloaded_at, json.dumps({"source_type": "EIA_DAILY_SPOT", "unit": "USD/MMBtu" if snapshot.source_code == "eia_henryhub_daily" else "USD/bbl"})),
    )
    cur.execute(
        """SELECT document_id FROM investment_lab.source_documents
           WHERE source_code=%s AND canonical_url=%s AND sha256_hex=%s""",
        (snapshot.source_code, snapshot.url, snapshot.sha256_hex))
    doc = cur.fetchone()
    if doc is None:
        raise SourceFormatError("Cannot verify saved source document")
    document_id = doc[0]
    new, revised = 0, 0
    for item in snapshot.observations:
        observed = datetime.combine(item.observed_on, time.min, tzinfo=timezone.utc)
        cur.execute(
            """SELECT revision_no,price_value FROM investment_lab.price_observation_versions
               WHERE instrument_code=%s AND source_code=%s AND observed_for=%s AND interval_code='1d'
               ORDER BY revision_no DESC LIMIT 1""",
            (snapshot.instrument_code, snapshot.source_code, observed))
        prev = cur.fetchone()
        if prev is not None and Decimal(str(prev[1])) == item.price:
            continue
        revision = (int(prev[0]) + 1) if prev is not None else 1
        # A day-precision EIA release doesn't establish an intraday release time.
        # The ingestion timestamp is also an eligibility gate in prices_asof.
        cur.execute(
            """INSERT INTO investment_lab.price_observation_versions
                 (instrument_code,source_code,observed_for,interval_code,revision_no,
                  document_id,price_value,value_concept,available_at,note)
               VALUES (%s,%s,%s,'1d',%s,%s,%s,'DAILY_SPOT',%s,%s)""",
            (snapshot.instrument_code, snapshot.source_code, observed, revision,
             document_id, item.price, max(snapshot.downloaded_at, conservative_pub),
             "Source URL and SHA256 retained; EIA source page reflects snapshot, not original historical vintage."),
        )
        new += 1
        if prev is not None:
            revised += 1

    cur.execute(
        """INSERT INTO investment_lab.pipeline_runs
           (run_key,pipeline_name,code_version,started_at,finished_at,status,
            input_fingerprint,rows_received,rows_inserted,rows_revised)
           VALUES (%s,'eia_spot_snapshot','2.0.1',now(),now(),'SUCCEEDED',%s,%s,%s,%s)""",
        (run_key, snapshot.sha256_hex, len(snapshot.observations), new, revised))
    return {"run_key": run_key, "new": new, "revised": revised, "duplicate_run": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Allowlisted EIA source checks; research only")
    parser.add_argument("--source", choices=sorted(SOURCES), default="brent")
    parser.add_argument("--write", action="store_true", help="Explicit staging DB mode (default: no writes)")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    try:
        snapshot = fetch_official(args.source, now)
        info = summary(snapshot)
        if args.write:
            if os.getenv("ISL_ALLOW_STAGING_INGEST") != "YES":
                raise SourceFormatError("Staging ingestion explicitly disabled")
            dsn = os.getenv("NEON_DATABASE_URL")
            if not dsn:
                raise SourceFormatError("Missing staging database secret")
            import psycopg
            with psycopg.connect(dsn, connect_timeout=15, sslmode="require") as conn:
                with conn.cursor() as cur:
                    info["storage"] = store(cur, snapshot)
                conn.commit()
        else:
            info["storage"] = "DRY_RUN_NO_DATABASE_WRITE"
        print(json.dumps(info, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        # Do not leak connection strings, HTML, environment variables or API tokens.
        print("EIA_INGEST_FAILED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
