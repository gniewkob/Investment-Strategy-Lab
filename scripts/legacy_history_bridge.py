"""Manually authorised, READ-ONLY legacy market-history bridge (staging only).

A separate login with SELECT on the public market-price legacy table is
required. The existing agent journal role MUST NOT be broadened.
No source rows, credentials, portfolio records or account data are uploaded
to GitHub artifacts. Research outcomes are retrospective, not PIT-certified.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from scripts import opportunity_radar as radar
from scripts import opportunity_research_pipeline as research
from scripts.staging_preflight import EXPECTED_HOST, EXPECTED_DATABASE

EXPECTED_READER = "isl_legacy_history_reader"
MAX_ROWS = radar.MAX_RECORDS
# These are market-price references, NOT verified investable total-return assets.
SOURCES: dict[str, tuple[str, str, str]] = {
    "BTC-USD": ("coinbase_spot", "1d", "PRICE_ONLY"),
    "ETH-USD": ("coinbase_spot", "1d", "PRICE_ONLY"),
    "GOLD_NBP_PLN_G": ("nbp_gold", "1d", "PRICE_ONLY"),
    "EURPLN_NBP": ("nbp_rates", "1d", "FX_RATE"),
    "USDPLN_NBP": ("nbp_rates", "1d", "FX_RATE"),
    "BRENT_EIA_USD_BBL": ("eia_brent_daily", "1d", "PRICE_ONLY"),
    "WTI_EIA_USD_BBL": ("eia_wti_daily", "1d", "PRICE_ONLY"),
    "HENRY_HUB_USD_MMBTU": ("eia_henryhub_daily", "1d", "PRICE_ONLY"),
    "COPPER_WB_USD_T": ("wb_pink_monthly", "1mo", "PRICE_ONLY"),
    "ALUMINUM_WB_USD_T": ("wb_pink_monthly", "1mo", "PRICE_ONLY"),
    "NICKEL_WB_USD_T": ("wb_pink_monthly", "1mo", "PRICE_ONLY"),
    "SILVER_WB_USD_OZ": ("wb_pink_monthly", "1mo", "PRICE_ONLY"),
}


def validate_research_dsn(dsn: str) -> None:
    """Reject privileged credentials, a pooled/prod endpoint or unverified TLS."""
    if not dsn:
        raise ValueError("HISTORICAL_READ_SECRET_MISSING")
    from psycopg.conninfo import conninfo_to_dict
    try:
        parsed = urlsplit(dsn)
        if parsed.scheme not in ("postgresql", "postgres"):
            raise ValueError("INVALID_SCHEME")
        if parsed.hostname != EXPECTED_HOST or parsed.port not in (None, 5432):
            raise ValueError("HOST_MISMATCH")
        p = conninfo_to_dict(dsn)
    except Exception:
        # Bad URLs can contain credentials; never echo the parser's exception.
        raise ValueError("MALFORMED_HISTORICAL_DSN") from None
    if p.get("host") != EXPECTED_HOST:
        raise ValueError("HOST_MISMATCH")
    if p.get("user") != EXPECTED_READER or p.get("dbname") != EXPECTED_DATABASE:
        raise ValueError("NOT_DEDICATED_HISTORICAL_READER")
    if not p.get("password"):
        raise ValueError("HISTORICAL_PASSWORD_MISSING")
    if p.get("sslmode") != "verify-full":
        raise ValueError("FULL_TLS_VERIFICATION_REQUIRED")
    if any(p.get(key) for key in ("hostaddr", "service", "passfile")):
        raise ValueError("INDIRECT_CONNECTION_NOT_ALLOWED")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("DB timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def snapshot_from_rows(rows: list[tuple], as_of: datetime) -> tuple[dict, dict]:
    """Validate untrusted legacy rows; never fabricate publication vintages."""
    time = _utc(as_of)
    if not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError("Historical data row limit violated")
    records = []
    verified_source_rows = []
    counts = Counter()
    for raw in rows:
        if not isinstance(raw, (tuple, list)) or len(raw) != 7:
            raise ValueError("Unexpected legacy price shape")
        code, source, interval, basis, observed, ingested, raw_close = raw
        if code not in SOURCES or (source, interval, basis) != SOURCES[code]:
            raise ValueError("Unknown or mismatched market-data source")
        observed, ingested = _utc(observed), _utc(ingested)
        if observed > time or ingested > time or ingested < observed:
            raise ValueError("Historical source chronology inconsistent")
        try:
            value = Decimal(str(raw_close))
        except Exception:
            raise ValueError("Invalid legacy price") from None
        if not value.is_finite() or value <= 0:
            raise ValueError("Unsupported nonpositive legacy reference price")
        entry = {
            "instrument_code": code, "interval_code": interval,
            "return_basis": basis,
            "observed_for": observed.isoformat(),
            "ingested_at": ingested.isoformat(),
            "close_price": str(value),
        }
        records.append(entry)
        verified_source_rows.append({**entry, "source_code": source})
        counts[code] += 1
    snapshot = {
        "mode": "RETROSPECTIVE_RESEARCH_ONLY",
        "dataset_kind": "LEGACY_REFERENCE_SNAPSHOT_UNVERIFIED",
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "as_of": time.isoformat(),
        "records": records,
    }
    # Radar's own strict validator also rejects duplicate dates/periods.
    radar.validate_snapshot(snapshot)
    provenance_hash = hashlib.sha256(
        radar._canonical(sorted(verified_source_rows, key=lambda r:
            (r["instrument_code"], r["interval_code"], r["observed_for"]))).encode("utf-8")
    ).hexdigest()
    return snapshot, {
        "status": "HISTORICAL_REFERENCE_SNAPSHOT_VALIDATED",
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "source_mapping_sha256": provenance_hash,
        "series_counts": dict(sorted(counts.items())),
        "total_rows": len(records),
        "as_of": time.isoformat(),
        "raw_price_exported_as_artifact": False,
        "portfolio_tables_accessed": False,
        "database_writes": 0,
        "orders": 0,
    }


def _assert_reader_acl(cur) -> None:
    cur.execute("""
        SELECT current_user, current_database(),
               current_setting('transaction_read_only'),
               r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolbypassrls,
               pg_has_role(current_user,'neon_superuser','MEMBER'),
               has_database_privilege(current_user,current_database(),'CREATE'),
               has_schema_privilege(current_user,'investment_lab','CREATE'),
               has_table_privilege(current_user,'investment_lab.price_observations','SELECT'),
               has_table_privilege(current_user,'investment_lab.price_observations','INSERT,UPDATE,DELETE,TRUNCATE'),
               has_table_privilege(current_user,'investment_lab.holding_snapshots','SELECT'),
               has_table_privilege(current_user,'investment_lab.valuations','SELECT'),
               has_table_privilege(current_user,'investment_lab.paper_events','SELECT'),
               has_table_privilege(current_user,'investment_lab.agent_cycles','INSERT')
        FROM pg_roles r WHERE r.rolname=current_user
    """)
    row=cur.fetchone()
    if row is None:
        raise RuntimeError("Historical reader role metadata unavailable")
    (user, database, read_only, superuser, createdb, createrole, bypassrls,
     neon_admin, db_create, schema_create, market_read, market_write,
     holdings_read, valuations_read, paper_read, journal_write) = row
    if (user != EXPECTED_READER or database != EXPECTED_DATABASE or read_only != "on"
            or not market_read or any((superuser, createdb, createrole, bypassrls,
                                       neon_admin, db_create, schema_create,
                                       market_write, holdings_read, valuations_read,
                                       paper_read, journal_write))):
        raise RuntimeError("Historical reader least-privilege boundary failed")


def fetch_staging_history(dsn: str) -> tuple[dict, dict]:
    """SELECT from one public-price table in a read-only Postgres transaction."""
    validate_research_dsn(dsn)
    import psycopg
    with psycopg.connect(
        dsn, sslmode="verify-full",
        sslrootcert="/etc/ssl/certs/ca-certificates.crt",
        connect_timeout=12,
        options="-c default_transaction_read_only=on",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            _assert_reader_acl(cur)
            cur.execute("SELECT now()")
            as_of=_utc(cur.fetchone()[0])
            cur.execute("""
                SELECT instrument_code,source_code,interval_code,return_basis,
                       observed_for,ingested_at,close_price
                FROM investment_lab.price_observations
                WHERE instrument_code=ANY(%s)
                  AND observed_for<=%s AND ingested_at<=%s
                ORDER BY instrument_code,interval_code,observed_for
                LIMIT %s
            """, (list(SOURCES), as_of, as_of, MAX_ROWS+1))
            snapshot, manifest = snapshot_from_rows(cur.fetchall(), as_of)
    return snapshot, manifest


def run_and_report(snapshot: dict, manifest: dict, out_dir: Path) -> dict:
    """Run existing evidence workflow; publish only aggregate research results."""
    result=research.run_pipeline(snapshot)
    if (result["manifest"]["decision"] != "INVESTIGATE_OR_HOLD_NO_CHANGE_ONLY"
            or result["manifest"]["hypothetical_allocation_changes"] != 0
            or result["manifest"]["paper_fills"] != 0
            or result["manifest"]["real_orders"] != 0
            or result["manifest"]["database_writes"] != 0):
        raise RuntimeError("Historical research output crossed the safety boundary")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir/"research_report.md").write_text(research.report(result),encoding="utf-8")
    (out_dir/"manifest.json").write_text(
        json.dumps({**manifest, "pipeline": result["manifest"]},
                   ensure_ascii=False,sort_keys=True,indent=2)+"\n", encoding="utf-8")
    # Outputs contain only aggregate evidence and classifications, not raw rows.
    for key in ("radar", "robustness", "ledger", "context"):
        (out_dir/(key+".json")).write_text(
            json.dumps(result[key],ensure_ascii=False,sort_keys=True,
                       allow_nan=False)+"\n",encoding="utf-8")
    return result["manifest"]


def main() -> int:
    try:
        dsn=os.getenv("NEON_HISTORICAL_READ_DATABASE_URL", "")
        snapshot, manifest=fetch_staging_history(dsn)
        out_dir=Path(os.getenv("ISL_HISTORICAL_REPORT_DIR",
                               "artifacts/legacy-history-research"))
        outcome=run_and_report(snapshot,manifest,out_dir)
        print("LEGACY_HISTORY_RESEARCH_OK",
              "observations",manifest["total_rows"],
              "series",outcome["series_analyzed"],
              "hypotheses_for_review",outcome["questions_for_independent_review"],
              "orders",0,"database_writes",0)
        return 0
    except Exception as exc:
        # No raw libpq errors, environment variables, or URLs in workflow logs.
        print("LEGACY_HISTORY_RESEARCH_FAILED: "+type(exc).__name__,file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
