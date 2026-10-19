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
                "pit_fixture_visible", "pit_nonfixture_visible",
                "pit_verified_market", "verified_series",
                "future_local_timestamps", "unmatched_sources", "series")
    if any(k not in snapshot for k in required):
        raise ValueError("Incomplete data audit snapshot")
    counts = ("documents", "versions", "pit_eligible",
              "pit_fixture_visible", "pit_nonfixture_visible",
              "pit_verified_market", "future_local_timestamps", "unmatched_sources")
    if any(type(snapshot[k]) is not int or snapshot[k] < 0 for k in counts):
        raise ValueError("Invalid audit counts")
    # All versioned PIT rows are only TECHNICALLY visible. No data can be
    # promoted by a synthetic test fixture or an unreviewed source document.
    if (snapshot["pit_fixture_visible"] + snapshot["pit_nonfixture_visible"]
            != snapshot["pit_eligible"]
            or snapshot["pit_verified_market"] > snapshot["pit_nonfixture_visible"]
            or snapshot["pit_eligible"] > snapshot["versions"]):
        raise ValueError("Inconsistent point-in-time source categories")
    if (not isinstance(snapshot["series"], list)
            or not isinstance(snapshot["verified_series"], list)):
        raise ValueError("Expected series lists")
    # Validate technical diagnostics too, even though they cannot count
    # toward market-data readiness.
    for group in (snapshot["series"], snapshot["verified_series"]):
        for row in group:
            if not isinstance(row, dict):
                raise ValueError("Invalid series summary")
            try:
                code = row["instrument_code"]
                interval = row["interval_code"]
                concept = row["value_concept"]
                periods = row["periods"]
            except KeyError as exc:
                raise ValueError("Invalid series summary") from exc
            if not (isinstance(code, str) and isinstance(interval, str)
                    and isinstance(concept, str) and type(periods) is int
                    and periods >= 0):
                raise ValueError("Invalid series summary")
    # Only independently attested market-data coverage could pass this gate.
    series = snapshot["verified_series"]
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
        warnings.append("FUTURE_LOCAL_INGESTION_TIMESTAMP")
    if snapshot["unmatched_sources"]:
        warnings.append("DOCUMENT_SOURCE_MISMATCH")
    if any(target_gaps.values()):
        warnings.append("INSUFFICIENT_MONTHLY_TOTAL_RETURN_SERIES")
    if any(research_gaps.values()):
        warnings.append("INSUFFICIENT_MONTHLY_RESEARCH_HISTORY")
    if snapshot["pit_fixture_visible"]:
        warnings.append("SYNTHETIC_PIT_FIXTURE_NOT_MARKET_DATA")
    if snapshot["pit_nonfixture_visible"] > snapshot["pit_verified_market"]:
        warnings.append("UNVERIFIED_PIT_SOURCE_RECORDS")
    if snapshot["pit_eligible"] == 0:
        warnings.append("NO_POINT_IN_TIME_EVIDENCE")
    if snapshot["pit_verified_market"] == 0:
        warnings.append("NO_VERIFIED_POINT_IN_TIME_MARKET_EVIDENCE")
    # A passing SQL/SSL check never overrides a data-quality block.
    return {
        "status": "MARKET_DATA_NOT_READY" if warnings else "COVERAGE_GATE_PASSED_REVIEW_REQUIRED",
        "as_of_utc": snapshot["server_time"],
        "documents": snapshot["documents"],
        "version_rows": snapshot["versions"],
        # Legacy key remains TECHNICAL visibility for backward compatibility.
        "pit_eligible_rows": snapshot["pit_eligible"],
        "pit_fixture_rows": snapshot["pit_fixture_visible"],
        "pit_nonfixture_unverified_rows": (
            snapshot["pit_nonfixture_visible"] - snapshot["pit_verified_market"]
        ),
        "pit_verified_market_rows": snapshot["pit_verified_market"],
        "technical_pit_is_not_source_verification": True,
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
                 (SELECT COUNT(*) FROM investment_lab.prices_asof(%s) p
                    JOIN investment_lab.source_documents d USING (document_id)
                    WHERE lower(coalesce(d.metadata->>'synthetic','')) = 'true'
                       OR lower(coalesce(d.metadata->>'fixture_only','')) = 'true'),
                 (SELECT COUNT(*) FROM investment_lab.prices_asof(%s) p
                    JOIN investment_lab.source_documents d USING (document_id)
                    WHERE NOT (lower(coalesce(d.metadata->>'synthetic','')) = 'true'
                       OR lower(coalesce(d.metadata->>'fixture_only','')) = 'true')),
                 (SELECT COUNT(*) FROM investment_lab.price_observation_versions v
                  JOIN investment_lab.source_documents d USING (document_id)
                  WHERE v.recorded_at > %s OR d.retrieved_at > %s),
                 (SELECT COUNT(*) FROM investment_lab.price_observation_versions v
                  JOIN investment_lab.source_documents d USING (document_id)
                  WHERE v.source_code <> d.source_code)
            """, (server_time, server_time, server_time,
                  server_time, server_time))
            docs, revisions, pit, fixtures, nonfixtures, future, mismatch = (
                int(v) for v in cur.fetchone()
            )
            # prices_asof excludes future recordings, but does NOT certify
            # that a price is real historical published market data.
            # There is currently no independent documentary-vintage attestation
            # contract; fail closed rather than treating a non-fixture URL,
            # downloaded HTML hash, or observed_for date as verified provenance.
            cur.execute("""
                SELECT instrument_code,interval_code,value_concept,
                       COUNT(DISTINCT observed_for) AS periods
                FROM investment_lab.prices_asof(%s)
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
        "pit_fixture_visible": fixtures,
        "pit_nonfixture_visible": nonfixtures,
        # No attestation mechanism exists. False positives here would turn
        # purely technical observations into fictional historical evidence.
        "pit_verified_market": 0,
        "verified_series": [],
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
        f"| Technically PIT-visible records (incl. fixtures) | {summary['pit_eligible_rows']} |",
        f"| Synthetic PIT fixtures | {summary['pit_fixture_rows']} |",
        f"| Non-fixture PIT records without independent source proof | {summary['pit_nonfixture_unverified_rows']} |",
        f"| Independently vintage-verified real market records | {summary['pit_verified_market_rows']} |",
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
        "Technically visible PIT records do not prove historical publication.",
        "Synthetically generated fixtures MUST NOT count as real market evidence.",
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
              "pit_rows_technical", outcome["pit_eligible_rows"],
              "pit_rows_fixture", outcome["pit_fixture_rows"],
              "pit_rows_verified_market", outcome["pit_verified_market_rows"],
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
