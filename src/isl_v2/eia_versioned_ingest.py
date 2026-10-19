"""Versioned EIA snapshot ingestion core — gated, research-only, NO live CLI writer.

The CLI fetches *public* official HTML and prints metadata-only dry-run plans.
apply_plan() has no connection creation or commit; it requires a separately
provisioned least-privilege STAGING writer role and a caller-owned transaction.
No such writer role/credential is created by this module or its workflows.
A 2026 fetched snapshot does NOT establish original availability of 2024 bars.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import re
import sys
from urllib.request import Request, urlopen

from src.isl_v2.eia_sources import SOURCES, Snapshot, SourceFormatError, parse_snapshot

READER_ONLY_CLI = True
EXPECTED_WRITER = "isl_eia_pit_staging_writer"  # Not provisioned as of 2026-10-19
EXPECTED_DATABASE = "investment_lab"
MAX_SOURCE_BYTES = 8_000_000
FINGERPRINT = re.compile(r"[a-f0-9]{64}\Z")
NOTE = "CURRENT_SNAPSHOT_NOT_ORIGINAL_HISTORICAL_OBSERVATION_VINTAGE"
UNVERIFIED = "CURRENT_SNAPSHOT_UNVERIFIED_HISTORICAL_PUBLICATION"


@dataclass(frozen=True)
class IngestionPlan:
    snapshot: Snapshot
    available_at: datetime
    source_bytes_sha256: str


def prepare(source: str, original_html: bytes, fetched_at: datetime, *,
            max_age_days: int = 420) -> IngestionPlan:
    """Hash the exact bytes the parser sees; never fabricate original vintages."""
    if source not in SOURCES or type(original_html) is not bytes:
        raise SourceFormatError("Only allowlisted original HTML bytes are accepted")
    if (fetched_at.tzinfo is None or fetched_at.utcoffset() is None
            or not 1 <= max_age_days <= 1500):
        raise SourceFormatError("UTC-aware retrieval and bounded window required")
    actual_fetch = fetched_at.astimezone(timezone.utc)
    if not original_html or len(original_html) > MAX_SOURCE_BYTES:
        raise SourceFormatError("Official source HTML is empty or too large")
    parsed = parse_snapshot(source, original_html, actual_fetch,
                            max_age_days=max_age_days)
    digest = hashlib.sha256(original_html).hexdigest()
    if parsed.sha256_hex != digest or parsed.url != SOURCES[source][2]:
        raise SourceFormatError("Original source bytes and parser provenance differ")
    release_day_end = datetime.combine(
        parsed.release_day + timedelta(days=1), time.min, tzinfo=timezone.utc)
    # Source has only a DAY precision release date. Do not assume the content
    # existed before retrieval, or infer per-observation older publication dates.
    available_at = max(actual_fetch, release_day_end)
    if available_at > actual_fetch:
        raise SourceFormatError("Day-precision current release is not yet eligible")
    return IngestionPlan(parsed, available_at, digest)


def fetch_plan(source: str, fetched_at: datetime, *,
               max_age_days: int = 420, opener=urlopen) -> IngestionPlan:
    """Allowlisted HTTPS, no redirect, validated Content-Type/bytes."""
    if source not in SOURCES:
        raise SourceFormatError("EIA source not on allowlist")
    url = SOURCES[source][2]
    req = Request(url, headers={
        "Accept": "text/html",
        "User-Agent": "ISL-Research-Source-Validator/3.0",
    })
    with opener(req, timeout=30) as resp:
        if resp.geturl() != url:
            raise SourceFormatError("Unexpected EIA redirect")
        if "text/html" not in resp.headers.get("Content-Type", "").lower():
            raise SourceFormatError("Unexpected EIA media type")
        original_html = resp.read(MAX_SOURCE_BYTES + 1)
    return prepare(source, original_html, fetched_at, max_age_days=max_age_days)


def dry_run_summary(plan: IngestionPlan) -> dict:
    """Log only source metadata and counts — NEVER quote values or raw HTML."""
    s = plan.snapshot
    return {
        "status": "EIA_VERSIONED_INGEST_DRY_RUN_NO_DATABASE",
        "source_code": s.source_code,
        "instrument_code": s.instrument_code,
        "current_snapshot_url": s.url,
        "original_html_sha256": plan.source_bytes_sha256,
        "current_source_release_day": s.release_day.isoformat(),
        "release_date_precision": "DAY",
        "retrieved_at_actual": s.downloaded_at.isoformat(),
        "current_snapshot_available_not_before": plan.available_at.isoformat(),
        "first_observed_for": s.observations[0].observed_on.isoformat(),
        "last_observed_for": s.observations[-1].observed_on.isoformat(),
        "daily_spot_observations": len(s.observations),
        "historical_individual_publication_vintages_verified": False,
        "source_vintage": UNVERIFIED,
        "source_bytes_retained_by_database": False,
        "database_connections": 0,
        "database_writes": 0,
        "real_orders": 0,
        "schedule_enabled": False,
    }


def _assert_writer_identity(cur) -> datetime:
    """Refuse owner, historical reader, journal agent and overprivileged roles."""
    cur.execute("""
        SELECT current_user,current_database(),current_setting('transaction_read_only'),
               r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolbypassrls,
               pg_has_role(current_user,'neon_superuser','MEMBER'),
               has_database_privilege(current_user,current_database(),'CREATE'),
               has_schema_privilege(current_user,'investment_lab','CREATE'),
               has_table_privilege(current_user,'investment_lab.source_documents','SELECT'),
               has_table_privilege(current_user,'investment_lab.source_documents','INSERT'),
               has_table_privilege(current_user,'investment_lab.price_observation_versions','SELECT'),
               has_table_privilege(current_user,'investment_lab.price_observation_versions','INSERT'),
               has_table_privilege(current_user,'investment_lab.price_observations','SELECT'),
               has_table_privilege(current_user,'investment_lab.price_observations','INSERT'),
               has_table_privilege(current_user,'investment_lab.holding_snapshots','SELECT'),
               has_table_privilege(current_user,'investment_lab.valuations','SELECT'),
               has_table_privilege(current_user,'investment_lab.paper_events','SELECT'),
               has_table_privilege(current_user,'investment_lab.agent_cycles','INSERT')
        FROM pg_roles r WHERE r.rolname=current_user
    """)
    row = cur.fetchone()
    if row is None or len(row) != 20:
        raise SourceFormatError("Dedicated writer identity proof unavailable")
    (role, database, read_only, superuser, createdb, createrole, bypass,
     neon_admin, db_create, schema_create, doc_read, doc_write,
     versions_read, versions_write, legacy_read, legacy_write,
     holdings_read, valuations_read, paper_read, journal_write) = row
    if (role != EXPECTED_WRITER or database != EXPECTED_DATABASE
            or read_only != "off"
            or not all((doc_read, doc_write, versions_read, versions_write))
            or any((superuser, createdb, createrole, bypass, neon_admin,
                    db_create, schema_create, legacy_read, legacy_write,
                    holdings_read, valuations_read, paper_read, journal_write))):
        raise SourceFormatError("Dedicated least-privilege staging writer denied")
    cur.execute("SELECT now()")
    as_of = cur.fetchone()
    if as_of is None or len(as_of) != 1 or as_of[0].tzinfo is None:
        raise SourceFormatError("Database time unavailable")
    return as_of[0].astimezone(timezone.utc)


def apply_plan(cur, plan: IngestionPlan) -> dict:
    """Caller-owned SQL transaction only; NO commit, CLI write path or DSN.

    A *new*, dedicated writer identity with exactly bounded privileges
    is required. No existing Neon role currently satisfies this contract.
    Uses parameter binding, a per-source advisory lock and append-only versions.
    The caller must roll back the whole transaction on ANY error.
    """
    if not isinstance(plan, IngestionPlan) or not FINGERPRINT.fullmatch(
            plan.source_bytes_sha256):
        raise SourceFormatError("Missing original document fingerprint")
    s = plan.snapshot
    if (s.url not in (x[2] for x in SOURCES.values())
            or (s.instrument_code, s.source_code, s.url) not in SOURCES.values()
            or s.sha256_hex != plan.source_bytes_sha256
            or s.downloaded_at.tzinfo is None
            or plan.available_at.tzinfo is None):
        raise SourceFormatError("Ingestion plan does not match official EIA identity")
    pub = datetime.combine(s.release_day, time.min, tzinfo=timezone.utc)
    minimum_time = max(s.downloaded_at.astimezone(timezone.utc),
                       pub + timedelta(days=1))
    if plan.available_at.astimezone(timezone.utc) != minimum_time:
        raise SourceFormatError("Current source availability was fabricated")
    now = _assert_writer_identity(cur)
    if plan.available_at > now + timedelta(seconds=5):
        raise SourceFormatError("Source was not yet available at database time")

    # Fail first on missing catalogue keys, do not silently add sources/units.
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (s.source_code,))
    cur.execute("SELECT source_code FROM investment_lab.data_sources WHERE source_code=%s",
                (s.source_code,))
    if cur.fetchone() != (s.source_code,):
        raise SourceFormatError("Official source catalogue missing")
    cur.execute("SELECT instrument_code FROM investment_lab.instruments WHERE instrument_code=%s",
                (s.instrument_code,))
    if cur.fetchone() != (s.instrument_code,):
        raise SourceFormatError("Official instrument catalogue missing")

    meta = {
        "source_type": "EIA_DAILY_SPOT",
        "unit": "USD/MMBtu" if s.source_code == "eia_henryhub_daily" else "USD/bbl",
        "source_vintage": UNVERIFIED,
        "synthetic": False,
        "original_historical_publication_verified": False,
        "source_bytes_retained": False,
    }
    cur.execute("""
        INSERT INTO investment_lab.source_documents
         (source_code,canonical_url,sha256_hex,published_at,publication_precision,
          retrieved_at,content_type,metadata)
        VALUES (%s,%s,%s,%s,'DAY',%s,'text/html',%s::jsonb)
        ON CONFLICT (source_code,canonical_url,sha256_hex) DO NOTHING
        RETURNING document_id
    """, (s.source_code, s.url, s.sha256_hex, pub, s.downloaded_at,
          json.dumps(meta, sort_keys=True)))
    inserted = cur.fetchone()
    doc_added = inserted is not None
    cur.execute("""
        SELECT document_id,published_at,publication_precision,retrieved_at,metadata
        FROM investment_lab.source_documents
        WHERE source_code=%s AND canonical_url=%s AND sha256_hex=%s
    """, (s.source_code, s.url, s.sha256_hex))
    doc = cur.fetchone()
    if (doc is None or doc[1] != pub or doc[2] != "DAY"
            or doc[3] > s.downloaded_at
            or doc[4] != meta):
        raise SourceFormatError("Saved official document provenance differs")
    doc_id = doc[0]
    new, revised, unchanged = 0, 0, 0
    for spot in s.observations:
        observed = datetime.combine(spot.observed_on, time.min, tzinfo=timezone.utc)
        if (not isinstance(spot.price, Decimal)
                or not spot.price.is_finite() or spot.price <= 0):
            raise SourceFormatError("Unsupported daily spot value")
        cur.execute("""
            SELECT v.revision_no,v.price_value,v.available_at,d.metadata
            FROM investment_lab.price_observation_versions v
            JOIN investment_lab.source_documents d ON d.document_id=v.document_id
            WHERE v.instrument_code=%s AND v.source_code=%s
              AND v.observed_for=%s AND v.interval_code='1d'
            ORDER BY v.revision_no DESC LIMIT 1
        """, (s.instrument_code, s.source_code, observed))
        prev = cur.fetchone()
        if prev is not None:
            if (not isinstance(prev[3], dict)
                    or prev[3].get("source_type") != "EIA_DAILY_SPOT"
                    or prev[3].get("source_vintage") != UNVERIFIED
                    or prev[3].get("synthetic") is not False):
                raise SourceFormatError("Existing observation provenance is not accepted")
            if Decimal(str(prev[1])) == spot.price:
                unchanged += 1
                continue
            if plan.available_at <= prev[2]:
                raise SourceFormatError("Correction chronology must be strictly increasing")
        revision = 1 if prev is None else int(prev[0]) + 1
        cur.execute("""
            INSERT INTO investment_lab.price_observation_versions
             (instrument_code,source_code,observed_for,interval_code,revision_no,
              document_id,price_value,value_concept,available_at,note)
            VALUES (%s,%s,%s,'1d',%s,%s,%s,'DAILY_SPOT',%s,%s)
        """, (s.instrument_code, s.source_code, observed, revision,
              doc_id, spot.price, plan.available_at, NOTE))
        new += 1
        if prev is not None:
            revised += 1
    return {
        "status": "EIA_VERSIONED_STAGING_TRANSACTION_PENDING_CALLER_COMMIT",
        "document_added": doc_added,
        "new_observation_versions": new,
        "revised_observation_versions": revised,
        "unchanged_prices": unchanged,
        "source_original_html_sha256": s.sha256_hex,
        "source_vintage": UNVERIFIED,
        "individual_historical_publication_vintages_verified": False,
        "real_orders": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Official EIA dry-run ONLY; no DB or writes")
    parser.add_argument("--source", choices=sorted(SOURCES), default="wti")
    parser.add_argument("--max-age-days", type=int, default=420)
    args = parser.parse_args(argv)
    try:
        plan = fetch_plan(args.source, datetime.now(timezone.utc),
                          max_age_days=args.max_age_days)
        print(json.dumps(dry_run_summary(plan), sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        # Never echo SQL, secrets, source HTML or source quote values.
        print("EIA_VERSIONED_DRY_RUN_FAILED: " + type(exc).__name__,
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
