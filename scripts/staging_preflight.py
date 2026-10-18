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


class ConfigurationError(ValueError):
    """A fixed public status code, never derived from secret material."""


def validate_dsn(dsn: str) -> None:
    """Fail closed with non-sensitive, stable configuration error codes."""
    if not dsn:
        raise ConfigurationError("MISSING_SECRET")
    try:
        parsed = urlsplit(dsn)
        if parsed.scheme not in ("postgresql", "postgres"):
            raise ConfigurationError("NOT_POSTGRESQL_URL")
        host, port = parsed.hostname, parsed.port
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError("MALFORMED_URL") from None
    if host != EXPECTED_HOST or port not in (None, 5432):
        raise ConfigurationError("HOST_OR_POOLING_MISMATCH")

    from psycopg.conninfo import conninfo_to_dict
    try:
        parts = conninfo_to_dict(dsn)
    except Exception:
        # psycopg errors may contain user-provided DSN fragments. Never log them.
        raise ConfigurationError("MALFORMED_URL") from None
    if parts.get("user") != EXPECTED_USER:
        raise ConfigurationError("ROLE_MISMATCH")
    if parts.get("dbname") != EXPECTED_DATABASE:
        raise ConfigurationError("DATABASE_MISMATCH")
    if parts.get("host") != EXPECTED_HOST:
        raise ConfigurationError("HOST_OR_POOLING_MISMATCH")
    if not parts.get("password"):
        raise ConfigurationError("PASSWORD_MISSING")
    if parts.get("sslmode") != "verify-full":
        raise ConfigurationError("TLS_VERIFY_FULL_REQUIRED")
    if any(parts.get(k) for k in ("hostaddr", "service", "passfile")):
        raise ConfigurationError("INDIRECT_CONNECTION_FORBIDDEN")


def check_connection(dsn: str) -> dict:
    """Verify known staging identity and ACL in an entirely read-only session."""
    validate_dsn(dsn)
    import psycopg

    with psycopg.connect(
        dsn,
        sslmode="verify-full",
        # On GitHub Ubuntu runners, libpq must be given the system CA bundle.
        # Keep hostname validation; never downgrade to sslmode=require.
        sslrootcert="/etc/ssl/certs/ca-certificates.crt",
        connect_timeout=12,
        options="-c default_transaction_read_only=on",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("""
                SELECT current_user, current_database(),
                       current_setting('transaction_read_only'),
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
            (user, dbname, ro, createrole, createdb, superuser, bypassrls,
             neon_admin, db_create, schema_create, public_create,
             source_read, source_insert, versions_read, versions_insert,
             journal_read, journal_insert, journal_update, journal_delete,
             paper_insert, hypotheses_insert, evaluations_insert,
             pipeline_insert, old_positions_read) = row
            # Neon terminates client TLS at its proxy. pg_stat_ssl reports
            # the backend leg and can be false even with verified client TLS.
            # TLS is enforced by libpq sslmode=verify-full + trusted CA above.
            if user != EXPECTED_USER or dbname != EXPECTED_DATABASE or ro != "on":
                raise RuntimeError("unexpected role, database or read-only session")
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


def classify_operational_error(exc: Exception) -> str:
    """Map driver errors to safe codes. Never emit raw libpq error text.

    libpq may include hostnames, usernames or connection details in errors.
    Keyword checks influence ONLY a fixed public category, not log contents.
    """
    state = getattr(exc, "sqlstate", None)
    if state in ("28P01", "28000"):
        return "AUTHENTICATION_FAILED"
    message = str(exc).lower()
    if ("password authentication failed" in message
            or "sasl authentication failed" in message):
        return "AUTHENTICATION_FAILED"
    if ("root certificate" in message or "certificate verify failed" in message
            or "certificate validation failed" in message
            or "could not verify server certificate" in message):
        return "TLS_CERTIFICATE_FAILED"
    if "could not translate host name" in message or "name or service not known" in message:
        return "DNS_LOOKUP_FAILED"
    if "timeout" in message or "timed out" in message:
        return "CONNECTION_TIMEOUT"
    if "connection refused" in message:
        return "CONNECTION_REFUSED"
    return "OTHER_CONNECTION_FAILURE"


def main() -> int:
    try:
        result = check_connection(os.getenv("NEON_DATABASE_URL", ""))
        print(json.dumps(result, sort_keys=True))
        return 0
    except ConfigurationError as exc:
        # Only fixed internal error codes are printed: no host/URI/password data.
        print("STAGING_PREFLIGHT_CONFIG: " + str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        # Only output an allowlisted category, never an unfiltered exception.
        if type(exc).__name__ == "OperationalError":
            print("STAGING_PREFLIGHT_CONNECT: " + classify_operational_error(exc), file=sys.stderr)
        else:
            print("STAGING_PREFLIGHT_FAILED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
