"""Offline, deterministic educational research pipeline.

Consumes a supplied legacy-price snapshot, NEVER opens database connections,
uses exchanges, writes trades, or enables automatic portfolio changes.

Stages: historical anomaly questions -> evidence ledger -> research-only report.
Unverified source vintages are ALWAYS highlighted, never upgraded to PIT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from scripts import evidence_decision_ledger, opportunity_radar


def _json(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def run_pipeline(snapshot: dict) -> dict:
    """Build both reports from a single fingerprinted, validated input."""
    radar = opportunity_radar.analyze(snapshot)
    ledger = evidence_decision_ledger.make_ledger(radar)
    if (ledger["source_radar_sha256"] != radar["data_sha256"]
            or radar["source_vintage"] != "UNVERIFIED_HISTORICAL_PUBLICATION"
            or radar["pit_backtest_certified"] is not False
            or ledger["portfolio_reallocations"] != 0
            or ledger["real_orders"] != 0
            or radar["real_orders"] != 0):
        raise ValueError("Inconsistent research evidence / safety boundary")
    manifest = {
        "status": "EDUCATIONAL_EVIDENCE_PIPELINE_COMPLETE",
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "as_of": radar["as_of"],
        "input_rows": radar["price_records"],
        "series_analyzed": radar["series_analyzed"],
        "historical_events": sum(s["shock_samples"] for s in radar["series"]),
        "questions_for_independent_review": ledger["questions_for_independent_review"],
        "radar_data_sha256": radar["data_sha256"],
        "radar_report_sha256": hashlib.sha256(_json(radar).encode()).hexdigest(),
        "decision_ledger_sha256": hashlib.sha256(_json(ledger).encode()).hexdigest(),
        "uncertainty": "Unverified publication vintages; overlapping forward windows;"
                       " cannot establish investment performance or optimal allocation",
        "decision": "INVESTIGATE_OR_HOLD_NO_CHANGE_ONLY",
        "hypothetical_allocation_changes": 0,
        "paper_fills": 0,
        "real_orders": 0,
        "database_writes": 0,
        "schedule_enabled": False,
        "requires_verified_data_for_allocation_simulation": True,
    }
    return {"radar": radar, "ledger": ledger, "manifest": manifest}


def report(result: dict) -> str:
    manifest, ledger = result["manifest"], result["ledger"]
    lines = [
        "# Opportunity & Decision Intelligence — educational evidence report",
        "",
        "**This is a historical research exercise, not investment advice.**",
        "",
        f"Historical input rows: {manifest['input_rows']}",
        f"Analyzed reference series: {manifest['series_analyzed']}",
        f"Historical anomaly events: {manifest['historical_events']}",
        f"Questions for independent review: {manifest['questions_for_independent_review']}",
        "",
        "## Evidence ledger",
        "",
        "| Series | Unusual moves | Research status |",
        "| --- | ---: | --- |",
    ]
    for q in ledger["questions"]:
        lines.append(f"| {q['instrument_code']} ({q['interval_code']}) "
                     f"| {q['observed_outliers']} | {q['educational_decision']} |")
    lines += [
        "",
        "## Counterfactual: do not change hypothetical portfolio",
        "",
        "All M1/M2/M3 paper models: HOLD_NO_CHANGE.",
        "No evidence here supports a virtual rebalance or real-money action.",
        "Price anomalies are retrospective observations, not predictive signals.",
        "",
        "## Evidence quality and missing prerequisites",
        "",
        "- Original publication vintages of the legacy prices are unverified.",
        "- A historical holdout alone does not make correlated anomaly samples independent.",
        "- Source prices are not verified tradable total-return instruments.",
        "- Realistic next-session pricing, PLN FX, fees and uncertainty are not available.",
        "- Independent benchmarking and sequential validation are still required.",
        "",
        f"Source fingerprint: {manifest['radar_data_sha256']}",
        "Database writes: 0. Orders: 0. Schedule: disabled.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline educational opportunity evidence pipeline")
    ap.add_argument("--input", required=True, help="A staged historical research snapshot")
    ap.add_argument("--out-dir", default="artifacts/opportunity-evidence")
    args = ap.parse_args()
    try:
        source = Path(args.input)
        if source.stat().st_size > 4_000_000:
            raise ValueError("Research source exceeds input size limit")
        snapshot = json.loads(source.read_text(encoding="utf-8"))
        result = run_pipeline(snapshot)
        output = Path(args.out_dir)
        output.mkdir(parents=True, exist_ok=True)
        for name, key in (
            ("radar.json", "radar"),
            ("decision_ledger.json", "ledger"),
            ("manifest.json", "manifest"),
        ):
            (output / name).write_text(_json(result[key]) + "\n", encoding="utf-8")
        (output / "research_report.md").write_text(report(result), encoding="utf-8")
        print("EDUCATIONAL_EVIDENCE_PIPELINE_COMPLETE",
              "series", result["manifest"]["series_analyzed"],
              "events", result["manifest"]["historical_events"],
              "research_questions", result["manifest"]["questions_for_independent_review"],
              "virtual_changes", 0, "real_orders", 0, "writes", 0)
        return 0
    except Exception as exc:
        # Never render exceptions that could include private file contents/paths.
        print("EDUCATIONAL_EVIDENCE_PIPELINE_FAILED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
