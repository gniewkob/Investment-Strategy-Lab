"""v0.18 real-source reference intake into the research decision pipeline.

Consumes the independently archived NBP/TBSP 60-month reference-calendar
artifact, verifies its internal fingerprint with the existing v0.5 parser,
then runs v0.16 on a source manifest with NO QUALIFIED TR series. Actual NBP
gold PRICE_ONLY, USDPLN FX_RATE, and BondSpot nontradable index are reported
as observations, NOT silently promoted to equity/bonds/gold total-return.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.research_decision_pipeline_v16 import _load, run_cycle
from scripts.shadow_decision_engine_v05 import (
    ShadowInputError, _digest, _utc, from_reference_archive,
)

SCHEMA = "ISL_REAL_REFERENCE_GATEWAY_V18_001"


def evaluate_reference(archive, *, as_of_utc=None):
    verified = from_reference_archive(archive)
    if verified["reference_months"] < 36:
        raise ShadowInputError("reference calendar insufficient")
    last_month = verified["last_month"]
    # Archive proves monthly calendar alignment and internal hash consistency
    # but does NOT prove that its observations were available at historic time.
    # Use an explicit evaluation time rather than inventing a publication date.
    if as_of_utc is None:
        raise ShadowInputError("explicit UTC evaluation time required")
    as_of = _utc(as_of_utc)
    last_year, last_m = (int(x) for x in last_month.split("-"))
    if (as_of.year, as_of.month) <= (last_year, last_m):
        raise ShadowInputError("evaluation must follow final completed reference month")
    manifest = {
        "mode": "EDUCATIONAL_SHADOW_ONLY",
        "as_of_utc": as_of.isoformat(),
        "policy_version": "V05_FROZEN_001",
        "series": {},
    }
    cycle = run_cycle(current=manifest)
    if (cycle["paper_candidates"] or
            any(item["status"] != "HOLD_CASH" for item in cycle["model_decisions"].values()) or
            set(cycle["missing_or_blocked_sources"]) != set(verified["missing_model_sources"])):
        raise ShadowInputError("reference-only source promoted to model input")
    result = {
        "schema": SCHEMA,
        "status": "REFERENCE_DATA_OBSERVED_MODELS_BLOCKED",
        "as_of_utc": as_of.isoformat(),
        "source_archive_sha256": verified["source_archive_sha256"],
        "reference_months": verified["reference_months"],
        "first_month": verified["first_month"],
        "last_month": last_month,
        "real_reference_families": verified["observed_reference_families"],
        "qualified_total_return_model_series": [],
        "missing_qualified_model_series": verified["missing_model_sources"],
        "model_states": {model: state["status"]
                         for model, state in cycle["model_decisions"].items()},
        "decision_cycle_sha256": cycle["cycle_receipt_sha256"],
        "candidate_models": cycle["paper_candidates"],
        "independent_original_data_bytes_verified": False,
        "historical_pit_certified": False,
        "source_licence_independently_certified": False,
        "out_of_sample_performance_observed": False,
        "market_data_acceptance": "BLOCKED_MISSING_QUALIFIED_TOTAL_RETURN_SERIES",
        "financial_operations": 0,
        "orders_sent": 0, "paper_fills": 0, "database_writes": 0,
    }
    result["gateway_receipt_sha256"] = _digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-archive", type=Path, required=True)
    parser.add_argument("--as-of-utc", required=True)
    args = parser.parse_args()
    report = evaluate_reference(_load(args.reference_archive),
                                as_of_utc=args.as_of_utc)
    print("ISL_REAL_REFERENCE_GATEWAY_V18=" +
          json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
