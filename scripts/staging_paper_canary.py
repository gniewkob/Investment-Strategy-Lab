"""One fixed-date EDUCATIONAL staging research canary, never trading execution.

Manual-only, staging-only, fail-closed, append-only. Does not generate trading
signals or simulated fills. The only decisions are synthetic HOLD_CASH.
Requires a separately verified, least-privileged staging Postgres identity.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from scripts.staging_preflight import (
    EXPECTED_DATABASE,
    EXPECTED_USER,
    check_connection,
    validate_dsn,
)

AS_OF = datetime(2026, 10, 18, 7, tzinfo=timezone.utc)
RUN_KEY = "github-staging-canary-2026-10-18-utc07-v1"
VERSION = "canary-manual-hold-cash-v1"
MODELS = {
    "M1_GLOBAL_EQ": ["EQUITY_TR_PLN"],
    "M2_DIVERSIFIED": ["EQUITY_TR_PLN", "BONDS_TR_PLN", "GOLD_TR_PLN"],
    "M3_TACTICAL": ["EQUITY_TR_PLN", "BONDS_TR_PLN", "GOLD_TR_PLN"],
}


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def evidence_rows(cur) -> list[dict]:
    """Always use the revisioned point-in-time SQL SECURITY INVOKER view."""
    cur.execute("""
        SELECT instrument_code, source_code, observed_for, interval_code,
               price_value, value_concept, revision_no, available_at,
               document_id
        FROM investment_lab.prices_asof(%s)
        ORDER BY instrument_code,source_code,observed_for,interval_code
    """, (AS_OF,))
    rows = []
    for code, source, observed, interval, value, concept, revision, available, document_id in cur.fetchall():
        if available > AS_OF or observed > AS_OF:
            raise RuntimeError("PIT source contains future-dated evidence")
        rows.append({
            "instrument_code": code,
            "source_code": source,
            "observed_for": observed.isoformat(),
            "interval_code": interval,
            "price_value": str(value),
            "value_concept": concept,
            "revision_no": revision,
            "available_at": available.isoformat(),
            "document_id": str(document_id),
        })
    return rows


def fixed_fingerprint(rows: list[dict]) -> str:
    payload = {"run_key": RUN_KEY, "as_of": AS_OF.isoformat(),
               "version": VERSION, "records": rows,
               "simulation": "fixed_synthetic_HOLD_CASH_only"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def run_once(dsn: str) -> dict:
    """Read PIT data, atomically append fixed synthetic decisions, verify history."""
    validate_dsn(dsn)
    import psycopg

    with psycopg.connect(
        dsn,
        sslmode="verify-full",
        sslrootcert="/etc/ssl/certs/ca-certificates.crt",
        connect_timeout=12,
        autocommit=False,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_user,current_database(),"
                "has_table_privilege(current_user,'investment_lab.agent_cycles','INSERT'),"
                "has_table_privilege(current_user,'investment_lab.source_documents','INSERT')"
            )
            role, database, can_append, can_write_sources = cur.fetchone()
            if (role != EXPECTED_USER or database != EXPECTED_DATABASE
                    or can_append is not True or can_write_sources is not False):
                raise RuntimeError("Insufficient least-privilege staging identity")
            cur.execute(
                "SELECT model_code FROM investment_lab.models WHERE model_code=ANY(%s)",
                (list(MODELS),),
            )
            if {r[0] for r in cur.fetchall()} != set(MODELS):
                raise RuntimeError("Expected paper model catalog is incomplete")

            rows = evidence_rows(cur)
            fingerprint = fixed_fingerprint(rows)
            summary = {"test_type": "SYNTHETIC_HOLD_CASH_CANARY",
                       "research_only": True, "no_live_execution": True,
                       "input_observations": len(rows), "paper_decisions": 3,
                       "paper_fills": 0, "real_orders": 0}
            cur.execute("""
                INSERT INTO investment_lab.agent_cycles
                   (run_key,as_of,input_sha256,code_version,records_seen,summary)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (run_key) DO NOTHING
                RETURNING run_key
            """, (RUN_KEY, AS_OF, fingerprint, VERSION, len(rows),
                  canonical_json(summary)))
            created = cur.fetchone() is not None
            if created:
                for model, missing in sorted(MODELS.items()):
                    cur.execute("""
                        INSERT INTO investment_lab.agent_paper_decisions
                           (run_key,model_code,signal_cutoff,decision_type,
                            target_weights,missing_data,explanation,paper_only)
                        VALUES (%s,%s,%s,'HOLD_CASH','{}'::jsonb,%s::jsonb,%s,true)
                    """, (RUN_KEY, model, AS_OF, canonical_json(missing),
                          "SYNTHETIC RESEARCH CANARY: no signal, no simulated fills"))
            cur.execute("""
                SELECT input_sha256,code_version,records_seen,paper_fills,
                       real_orders,as_of
                FROM investment_lab.agent_cycles WHERE run_key=%s
            """, (RUN_KEY,))
            item = cur.fetchone()
            if (item is None or item[0] != fingerprint or item[1] != VERSION
                    or item[2] != len(rows) or item[3] != 0 or item[4] != 0
                    or item[5] != AS_OF):
                raise RuntimeError("Previously stored cycle differs; refuse overwrite")

            cur.execute("""
                SELECT model_code,decision_type,paper_only,target_weights,
                       missing_data,explanation
                FROM investment_lab.agent_paper_decisions WHERE run_key=%s
                ORDER BY model_code
            """, (RUN_KEY,))
            decisions = cur.fetchall()
            if (len(decisions) != 3
                    or [d[0] for d in decisions] != sorted(MODELS)
                    or any(d[1] != "HOLD_CASH" or d[2] is not True
                           or d[3] != {} or d[4] != MODELS[d[0]]
                           for d in decisions)):
                raise RuntimeError("Synthetic canary decision journal not complete")
        # Commit is atomic: either the whole cycle and its three intents exist or none.
        conn.commit()
    return {"status": "STAGING_PAPER_CANARY_VERIFIED",
            "run_key": RUN_KEY, "as_of": AS_OF.isoformat(),
            "input_sha256": fingerprint,
            "records_seen": len(rows), "paper_decisions": 3,
            "all_hold_cash": True, "newly_written": created,
            "paper_fills": 0, "real_orders": 0, "test_type": "SYNTHETIC_ONLY"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="artifacts/staging-canary")
    args = parser.parse_args()
    try:
        dsn = os.environ.get("NEON_DATABASE_URL", "")
        # Existing read-only TLS, permission and branch identity test.
        check_connection(dsn)
        result = run_once(dsn)
        replay = run_once(dsn)
        if (replay["newly_written"] is not False
                or replay["input_sha256"] != result["input_sha256"]
                or replay["paper_decisions"] != 3):
            raise RuntimeError("Staging canary replay was not idempotent")
        folder = Path(args.out_dir)
        folder.mkdir(parents=True, exist_ok=True)
        report = {**result, "retry_inserted_new_rows": 0,
                  "research_only": True}
        (folder / "cycle.json").write_text(
            canonical_json(report) + "\n", encoding="utf-8"
        )
        (folder / "report.md").write_text(
            "# Investment Strategy Lab — staging canary\n\n"
            f"- Fixed research cutoff: {AS_OF.isoformat()}\n"
            f"- PIT records available: {result['records_seen']}\n"
            "- M1, M2, M3: SYNTHETIC HOLD_CASH\n"
            "- Retry: no additional cycle or decision rows\n"
            "- Paper fills: 0; real orders: 0\n\n"
            "Security/provenance experiment, not an investment strategy or a backtest.\n",
            encoding="utf-8"
        )
        print("STAGING_PAPER_CANARY_VERIFIED records", result["records_seen"],
              "hold_cash", 3, "new", result["newly_written"],
              "retry_duplicate_rows", 0, "paper_fills", 0, "real_orders", 0)
        return 0
    except Exception as exc:
        # NEVER leak connection URLs, driver exceptions or password content.
        print("STAGING_PAPER_CANARY_FAILED: " + type(exc).__name__,
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
