"""Read-only staging connectivity check; no portfolio actions or database writes.

This entrypoint is designed for a manually approved GitHub environment secret.
Never logs connection strings, secrets, database query values or exception text.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import sys

EXPECTED_ROLE = "isl_agent_staging_limited"
EXPECTED_DATABASE = "investment_lab"


def validate_target(dsn: str) -> None:
    """Fail closed before connecting to any endpoint, including main or localhost."""
    if not dsn:
        raise ValueError("Missing staging-only connection secret")
    from psycopg.conninfo import conninfo_to_dict
    parts = conninfo_to_dict(dsn)
    host = (parts.get("host") or "").lower().rstrip(".")
    if not (host.endswith(".neon.tech") and host.count(",") == 0):
        raise ValueError("Only a single Neon TLS host is allowed")
    if parts.get("hostaddr") or parts.get("service"):
        raise ValueError("Direct-IP or service-based targets are not permitted")
    if parts.get("user") != EXPECTED_ROLE or parts.get("dbname") != EXPECTED_DATABASE:
        raise ValueError("Unexpected staging user or database")
    if not parts.get("password"):
        raise ValueError("Password must be set in GitHub environment secret")
    if parts.get("sslmode") not in (None, "verify-full"):
        raise ValueError("TLS must use certificate and hostname validation")


def check_connection(dsn: str) -> dict:
    """Establish a verified-TLS, read-only session with the staging role only."""
    validate_target(dsn)
    import psycopg
    from .agent_runner import assert_research_runtime

    with psycopg.connect(
        dsn,
        sslmode="verify-full",
        connect_timeout=12,
        options="-c default_transaction_read_only=on",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            assert_research_runtime(cur)
            cur.execute(
                "SELECT current_user, current_database(), "
                "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
            )
            role, dbname, tls = cur.fetchone()
            if role != EXPECTED_ROLE or dbname != EXPECTED_DATABASE or tls is not True:
                raise RuntimeError("Unverified database role, target, or TLS")
            cur.execute(
                "SELECT count(*) FROM investment_lab.prices_asof(%s)",
                (datetime.now(timezone.utc),),
            )
            evidence_count = int(cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM investment_lab.agent_cycles")
            cycle_count = int(cur.fetchone()[0])
    return {
        "status": "READ_ONLY_TLS_VALIDATED",
        "role": EXPECTED_ROLE,
        "database": EXPECTED_DATABASE,
        "validated_evidence_rows": evidence_count,
        "existing_research_cycles": cycle_count,
        "writes": 0,
        "paper_fills": 0,
        "real_orders": 0,
    }


def main() -> int:
    try:
        outcome = check_connection(os.environ.get("NEON_DATABASE_URL", ""))
    except Exception as exc:
        # Exception strings from psycopg can include hostnames or credentials.
        print("STAGING_CONNECTIVITY_FAILED: " + type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps(outcome, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
