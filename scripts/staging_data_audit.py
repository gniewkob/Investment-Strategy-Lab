"""Manual-only market-data readiness audit for the educational research lab.

Never ingests, trades, writes to Postgres or changes the agent schedule.
Distinguishes successful read-only inspection from market-data readiness.
Only emits aggregate counts, known instrument codes and fixed status labels.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from scripts.staging_preflight import (
    EXPECTED_DATABASE, EXPECTED_USER, check_connection, validate_dsn,
)

# Educational research *coverage* requirements, not trading signals.
# The research runner needs >=4 monthly total-return index observations
# for each model's paper target-intent; no execution or fills are supported.
MONTHLY_PAPER_REFERENCES = (
    "EQUITY_TR_PLN", "BONDS_TR_PLN", "GOLD_TR_PLN",
)
MONTHLY_RESEARCH_WATCH = (
    "BRENT_EIA_USD_BBL", "COPPER_WB_USD_T",
)
MIN_TARGET_MONTHS = 4
MIN_RESEARCH_MONTHS = 13


def classify_snapshot(snapshot: dict) -> dict:
    """Produce deterministic, fail-closed readiness without numeric predictions."""
    required = ("server_time", "documents", "versions", "pit_eligible",
                "pit_fixture", "pit_nonfixture",
                "future_local_timestamps", "unmatched_sources", "series")
    if any(k not in snapshot for k in required):
        raise ValueError("Incomplete data audit snapshot")
    counts = ("documents", "versions", "pit_eligible", "pit_fixture",
              "pit_nonfixture", "future_local_timestamps", "unmatched_sources")
    if any(type(snapshot[k]) is not int or snapshot[k] < 0 for k in counts):
        raise ValueError("Invalid audit counts")
    if snapshot["pit_fixture"] + snapshot["pit_nonfixture"] != snapshot["pit_eligible"]:
        raise ValueError("PIT fixture and non-fixture counts must sum to PIT-visible rows")
    series = snapshot["series"]
    if not isinstance(series, list):
        raise ValueError("Expected series list")
    by_code: dict[str, int] = {}
    for row in series:
        code, interval, concept, periods = (
            row["instrument_code"], row["interval_code"],
            row["value_concept"], row["periods"],
        )
        if not (isinstance(code, str) and isinstance(interval, str)
                and isinstance(concept, str) and type(periods) is int
                and periods >= 0):
            raise ValueError("Invalid series summary")
        if interval == "1mo":
            if code in MONTHLY_PAPER_REFERENCES and concept == "TOTAL_RETURN_INDEX":
                by_code[code] = max(by_code.get(code, 0), periods)
            elif code in MONTHLY_RESEARCH_WATCH and concept == "MONTHLY_AVERAGE":
                by_code[code] = max(by_code.get(code, 0), periods)
    target_gaps = {c: max(0, MIN_TARGET_MONTHS - by_code.get(c, 0))
                   for c in MONTHLY_PAPER_REFERENCES}
    research_gaps = {c: max(0, MIN_RESEARCH_MONTHS - by_code.get(c, 0))
                     for c in MONTHLY_RESEARCH_WATCH}
    warnings = []
    if snapshot["future_local_timestamps"]:
        # It is possible for deliberately future-dated PIT fixtures to occur.
        # Keep the warning, but do not call the fixture real market evidence.
        warnings.append("FUTURE_LOCAL_INGESTION_TIMESTAMP")
    if snapshot["pit_fixture"]:
        warnings.append("SYNTHETIC_PIT_FIXTURES_NOT_MARKET_EVIDENCE")
    if snapshot["pit_nonfixture"] == 0:
        warnings.append("NO_NONFIXTURE_PIT_EVIDENCE")
    if snapshot["unmatched_sources"]:
        warnings.append("DOCUMENT_SOURCE_MISMATCH")
    if any(target_gaps.values()):
        warnings.append("INSUFFICIENT_MONTHLY_TOTAL_RETURN_SERIES")
    if any(research_gaps.values()):
        warnings.append("INSUFFICIENT_MONTHLY_RESEARCH_HISTORY")
    if snapshot["pit_eligible"] == 0:
        warnings.append("NO_POINT_IN_TIME_EVIDENCE")
    # A passing SQL/SSL check never overrides a data-quality block.
    return {
        "status": "MARKET_DATA_NOT_READY" if warnings else "COVERAGE_GATE_PASSED_REVIEW_REQUIRED",
        "as_of_utc": snapshot["server_time"],
        "documents": snapshot["documents"],
        "version_rows": snapshot["versions"],
        "pit_eligible_rows": snapshot["pit_eligible"],
        "pit_fixture_rows": snapshot["pit_fixture"],
        "pit_nonfixture_rows_unreviewed": snapshot["pit_nonfixture"],
        "publication_vintage_certified": False,
        "future_local_timestamp_rows": snapshot["future_local_timestamps"],
        "document_source_mismatch_rows": snapshot["unmatched_sources"],
        "monthly_total_return_gaps": target_gaps,
        "monthly_research_watch_gaps": research_gaps,
        "warning_codes": warnings,
        "data_ready_for_autonomous_experiments": False if warnings else None,
        "data_ready_for_real_trading": False,
        "broker_or_exchange_connection": False,
        "database_writes": 0,
        "approval_required_for_schedule": True,
    }


def read_snapshot(dsn: str) -> dict:
    """Verify strict staging identity and audit metadata in a READ ONLY txn."""
    validate_dsn(dsn)
    check_connection(dsn)
    import psycopg
    with psycopg.connect(
        dsn,
        sslmode="verify-full",
        sslrootcert="/etc/ssl/certs/ca-certificates.crt",
        connect_timeout=12,
        options="-c default_transaction_read_only=on",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                "SELECT current_user,current_database(),"
                "current_setting('transaction_read_only'),now()"
            )
            user, database, ro, server_time = cur.fetchone()
            if user != EXPECTED_USER or database != EXPECTED_DATABASE or ro != "on":
                raise RuntimeError("Unexpected Neon staging identity/readonly transaction")
            cur.execute("""
                SELECT
                 (SELECT COUNT(*) FROM investment_lab.source_documents),
                 (SELECT COUNT(*) FROM investment_lab.price_observation_versions),
                 (SELECT COUNT(*) FROM investment_lab.prices_asof(%s)),
                 (SELECT COUNT(*) FROM investment_lab.price_observation_versions v
                  JOIN investment_lab.source_documents d USING (document_id)
                  WHERE v.recorded_at > %s OR d.retrieved_at > %s),
                 (SELECT COUNT(*) FROM investment_lab.price_observation_versions v
                  JOIN investment_lab.source_documents d USING (document_id)
                  WHERE v.source_code <> d.source_code)
            """, (server_time, server_time, server_time))
            docs, revisions, pit, future, mismatch = (int(v) for v in cur.fetchone())
            # Count synthetic fixtures separately from non-fixture PIT-visible
            # rows. Neither count independently proves publication history.
            cur.execute("""
                SELECT
                 COUNT(*) FILTER (WHERE
                     COALESCE(s.metadata->>'synthetic' = 'true', false) OR
                     COALESCE(s.metadata->>'fixture_only' = 'true', false)),
                 COUNT(*) FILTER (WHERE NOT (
                     COALESCE(s.metadata->>'synthetic' = 'true', false) OR
                     COALESCE(s.metadata->>'fixture_only' = 'true', false)))
                FROM investment_lab.prices_asof(%s) p
                JOIN investment_lab.source_documents s USING (document_id)
            """, (server_time,))
            fixture, nonfixture = (int(v) for v in cur.fetchone())
            if fixture + nonfixture != pit:
                raise RuntimeError("PIT provenance coverage mismatch")
            # The versioned source view already filters late data and revisions,
            # so coverage cannot be inflated by future/non-public versions.
            cur.execute("""
                SELECT instrument_code,interval_code,value_concept,
                       COUNT(DISTINCT observed_for) AS periods
                FROM investment_lab.prices_asof(%s) p
                JOIN investment_lab.source_documents s USING (document_id)
                WHERE NOT (
                    COALESCE(s.metadata->>'synthetic' = 'true', false) OR
                    COALESCE(s.metadata->>'fixture_only' = 'true', false))
                GROUP BY instrument_code,interval_code,value_concept
                ORDER BY instrument_code,interval_code,value_concept
            """, (server_time,))
            series = [{
                "instrument_code": c, "interval_code": interval,
                "value_concept": concept, "periods": int(n),
            } for c, interval, concept, n in cur.fetchall()]
    return {
        "server_time": server_time.astimezone(timezone.utc).isoformat(),
        "documents": docs,
        "versions": revisions,
        "pit_eligible": pit,
        "pit_fixture": fixture,
        "pit_nonfixture": nonfixture,
        "future_local_timestamps": future,
        "unmatched_sources": mismatch,
        "series": series,
    }


def make_markdown(summary: dict) -> str:
    warnings = summary["warning_codes"]
    lines = [
        "# Staging point-in-time data audit — educational research only",
        "",
        f"**Result:** {summary['status']}",
        f"**Checked at:** {summary['as_of_utc']}",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Source documents | {summary['documents']} |",
        f"| Versioned price records | {summary['version_rows']} |",
        f"| PIT-visible records (including synthetic tests) | {summary['pit_eligible_rows']} |",
        f"| Synthetic PIT fixture rows (not market evidence) | {summary['pit_fixture_rows']} |",
        f"| PIT-visible non-fixture rows (not publication-certified) | {summary['pit_nonfixture_rows_unreviewed']} |",
        f"| Future local ingestion timestamps | {summary['future_local_timestamp_rows']} |",
        f"| Source mismatches | {summary['document_source_mismatch_rows']} |",
        "",
        "## Research-only coverage gaps",
    ]
    for name, value in summary["monthly_total_return_gaps"].items():
        lines.append(f"- {name}: {value} additional valid monthly periods needed for the minimum target-intent screening.")
    for name, value in summary["monthly_research_watch_gaps"].items():
        lines.append(f"- {name}: {value} additional valid monthly periods needed for the hypothesis history threshold.")
    lines += ["", "## Warning codes"]
    lines += [f"- {w}" for w in warnings] if warnings else ["- NONE (coverage still needs independent review)"]
    lines += [
        "", "No real orders, paper fills, data writes or financial recommendations.",
        "Fixture records are excluded from coverage; other visible records still need",
        "independent release-vintage source evidence before any readiness claim.",
        "This coverage screen does not certify publication-vintage source quality,",
        "reliable source ETL, alert delivery, benchmark performance or investment readiness.",
        "An unattended schedule remains disabled.", "",
    ]
    return "\n".join(lines)


def main() -> int:
    try:
        outcome = classify_snapshot(read_snapshot(os.getenv("NEON_DATABASE_URL", "")))
        destination = Path(os.getenv("ISL_DATA_AUDIT_DIR", "artifacts/data-audit"))
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "audit.json").write_text(
            json.dumps(outcome, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
        (destination / "audit.md").write_text(make_markdown(outcome), encoding="utf-8")
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
                fh.write(make_markdown(outcome))
        print("STAGING_DATA_AUDIT", outcome["status"],
              "pit_rows", outcome["pit_eligible_rows"],
              "fixture_rows", outcome["pit_fixture_rows"],
              "nonfixture_rows", outcome["pit_nonfixture_rows_unreviewed"],
              "future_ingestion_rows", outcome["future_local_timestamp_rows"],
              "warnings", len(outcome["warning_codes"]))
        # NOT_READY is a valid audit finding, not a successful market-data gate.
        return 0
    except Exception as exc:
        # Never dump psycopg's exception string or the connection URI.
        print("STAGING_DATA_AUDIT_FAILED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
