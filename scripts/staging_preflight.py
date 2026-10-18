"""Manual, read-only Neon staging connectivity and permissions preflight.

Self-contained: never imports the research agent, migrations, or any broker API.
Logs contain only coarse success/failure statuses, never credentials or DSNs.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlsplit

EXPECTED_HOST = "ep-summer-star-ba5trfu5.c-8.eu-central-1.aws.neon.tech"
EXPECTED_DATABASE = "investment_lab"
EXPECTED_USER = "isl_agent_staging_limited"
EXPECTED_CANARY = "staging-security-canary-2026-10-18"


def validate_dsn(dsn: str) -> None:
    """Reject wrong identities, compute endpoints and TLS settings before connecting."""
    if not dsn:
        raise ValueError("missing secret")
    # conninfo_to_dict accepts URI and keyword DSNs; the workflow requires URI.
    parsed = urlsplit(dsn)
    if parsed.scheme not in ("postgresql", "postgres"):
        raise ValueError("expected PostgreSQL URI")
    if parsed.hostname != EXPECTED_HOST or parsed.port not in (None, 5432):
        raise ValueError("unexpected staging endpoint")
    from psycopg.conninfo import conninfo_to_dict

    parts = conninfo_to_dict(dsn)
    if parts.get("user") != EXPECTED_USER or parts.get("dbname") != EXPECTED_DATABASE:
        raise ValueError("unexpected database identity")
    if parts.get("host") != EXPECTED_HOST:
        raise ValueError("unexpected database host")
    if not parts.get("password"):
        raise ValueError("missing database password")
    if parts.get("sslmode") != "verify-full":
        raise ValueError("TLS hostname verification required")
    if any(parts.get(k) for k in ("hostaddr", "service", "passfile")):
        raise ValueError("indirect endpoint or credential lookup forbidden")


def check_connection(dsn: str) -> dict:
    """Verify known staging identity and ACL in an entirely read-only session."""
    validate_dsn(dsn)
    import psycopg

    with psycopg.connect(
        dsn,
        sslmode="verify-full",
        connect_timeout=12,
        options="-c default_transaction_read_only=on",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("""
                SELECT current_user, current_database(),
                       current_setting('transaction_read_only'),
                       (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()),
                       r.rolcreaterole, r.rolcreatedb, r.rolsuper, r.rolbypassrls,
                       pg_has_role(current_user, 'neon_superuser', 'MEMBER'),
                       has_database_privilege(current_user, current_database(), 'CREATE'),
                       has_schema_privilege(current_user, 'investment_lab', 'CREATE'),
                       has_schema_privilege(current_user, 'public', 'CREATE'),
                       has_table_privilege(current_user, 'investment_lab.source_documents', 'SELECT'),
                       has_table_privilege(current_user, 'investment_lab.source_documents', 'INSERT'),
                       has_table_privilege(current_user, 'investment_lab.price_observation_versions', 'SELECT'),
                       has_table_privilege(current_user, 'investment_lab.price_observation_versions', 'INSERT'),
                       has_table_privilege(current_user, 'investment_lab.agent_cycles', 'SELECT'),
                       has_table_privilege(current_user, 'investment_lab.agent_cycles', 'INSERT'),
                       has_table_privilege(current_user, 'investment_lab.agent_cycles', 'UPDATE'),
                       has_table_privilege(current_user, 'investment_lab.agent_cycles', 'DELETE'),
                       has_table_privilege(current_user, 'investment_lab.agent_paper_decisions', 'INSERT'),
                       has_table_privilege(current_user, 'investment_lab.agent_hypotheses', 'INSERT'),
                       has_table_privilege(current_user, 'investment_lab.agent_hypothesis_evaluations', 'INSERT'),
                       has_table_privilege(current_user, 'investment_lab.pipeline_runs', 'INSERT'),
                       has_table_privilege(current_user, 'investment_lab.paper_events', 'SELECT')
                FROM pg_roles AS r WHERE r.rolname = current_user
            """)
            row = cur.fetchone()
            if not row:
                raise RuntimeError("database identity missing")
            (user, dbname, ro, tls, createrole, createdb, superuser, bypassrls,
             neon_admin, db_create, schema_create, public_create,
             source_read, source_insert, versions_read, versions_insert,
             journal_read, journal_insert, journal_update, journal_delete,
             paper_insert, hypotheses_insert, evaluations_insert,
             pipeline_insert, old_positions_read) = row
            if user != EXPECTED_USER or dbname != EXPECTED_DATABASE or ro != "on" or tls is not True:
                raise RuntimeError("unexpected role, database or session security")
            forbidden = (createrole, createdb, superuser, bypassrls, neon_admin,
                         db_create, schema_create, public_create, source_insert,
                         versions_insert, journal_update, journal_delete,
                         pipeline_insert, old_positions_read)
            required = (source_read, versions_read, journal_read, journal_insert,
                        paper_insert, hypotheses_insert, evaluations_insert)
            if any(forbidden) or not all(required):
                raise RuntimeError("unexpected PostgreSQL role permissions")
            # Canary was inserted by a staging-only role test. Do not accept a
            # different branch just because the account name happens to match.
            cur.execute(
                "SELECT count(*) FROM investment_lab.agent_cycles WHERE run_key=%s",
                (EXPECTED_CANARY,),
            )
            if cur.fetchone()[0] != 1:
                raise RuntimeError("staging branch marker not found")
            cur.execute(
                "SELECT count(*) FROM investment_lab.agent_paper_decisions "
                "WHERE run_key=%s AND decision_type='HOLD_CASH'",
                (EXPECTED_CANARY,),
            )
            if cur.fetchone()[0] != 3:
                raise RuntimeError("staging paper-only marker invalid")
            cur.execute("SELECT count(*) FROM investment_lab.prices_asof(now())")
            visible = int(cur.fetchone()[0])
    return {"status": "READ_ONLY_TLS_VALIDATED", "staging_marker_verified": True,
            "visible_market_observations": visible, "writes": 0, "real_orders": 0}


def main() -> int:
    try:
        result = check_connection(os.getenv("NEON_DATABASE_URL", ""))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        # Do not render driver exception messages: some contain connection info.
        print("STAGING_PREFLIGHT_FAILED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
