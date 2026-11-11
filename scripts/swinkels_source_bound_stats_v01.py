"""Source-bound 2020–2022 Swinkels audit receipt; no M1–M3 data admission.

This is a single consumer of the *actual* SHA-pinned CC BY 4.0 DataverseNL
ODS, not an arbitrary row/evidence-string validator. It requires independently
reconciled original US Eq. 3 and the nine other independent par-bond PV
calculations before emitting aggregate educational statistics. Raw original
returns, source file, private information and per-month values are not logged.

A 2025 Dataverse published version is NOT proof that its contents existed as
an unchanged 2020–2022 vintage, nor that the 2023 Erasmus v6 bytes match.
"""
from __future__ import annotations

import hashlib
import json

from scripts.research_swinkels_original_source_probe_v01 import (
    PUBLISHER, SourceUnavailable, fetch,
)
from scripts.swinkels_formula_topology_probe_v01 import (
    SOURCE_ID, SOURCE_BYTES, SOURCE_SHA,
)
from scripts.swinkels_original_us_equation3_audit_v01 import (
    extract_original_us, reconcile,
)
from scripts.swinkels_nine_independent_cashflow_pv_v01 import (
    reconcile_all_nine,
)
from scripts.swinkels_nine_equation3_diagnostic_v01 import SHEETS


def _safe_stats(stats):
    """Admit only aggregate, explicitly unqualified result metadata."""
    if (not isinstance(stats, dict)
            or stats.get("observations") != 36
            or stats.get("data_window") != "2020-01..2022-12"
            or stats.get("research_only") is not True
            or stats.get("historical_pit_certified") is not False
            or stats.get("costs_taxes_currency_translation_included") is not False):
        raise SourceUnavailable("source statistics contract not satisfied")
    keys = ("observations", "data_window", "compounded_total_return_pct",
            "mean_monthly_return_pct", "monthly_sample_volatility_pct",
            "max_drawdown_pct", "research_only", "historical_pit_certified",
            "costs_taxes_currency_translation_included")
    # Do not include raw source records or injected flags from a provider.
    if any(k not in stats for k in keys):
        raise SourceUnavailable("source statistics fields missing")
    return {k: stats[k] for k in keys}


def create_receipt(original_ods: bytes) -> dict:
    """Fail closed unless exact source bytes and both independent models agree."""
    if (type(original_ods) is not bytes
            or len(original_ods) != SOURCE_BYTES
            or hashlib.sha256(original_ods).hexdigest() != SOURCE_SHA):
        raise SourceUnavailable("original DataverseNL source bytes/hash mismatch")
    us = reconcile(extract_original_us(original_ods))
    other = reconcile_all_nine(original_ods)
    if (us.get("source_sha_verified") is not True
            or us.get("independent_equation3_reconciliation_passed") is not True
            or us.get("variant") != "Original_US_1962"
            or us.get("months_reconciled") != 36
            or us.get("qualified_model_series") != []
            or us.get("model_state") != "HOLD_CASH"
            or us.get("financial_operations") != 0
            or other.get("source_sha_verified") is not True
            or other.get("original_publisher_ods_sha256") != SOURCE_SHA
            or other.get("variants_verified") != 9
            or other.get("monthly_observations_verified") != 324
            or other.get("qualified_model_series") != []
            or other.get("model_state") != "HOLD_CASH"
            or other.get("financial_operations") != 0):
        raise SourceUnavailable("independent source-reconciliation proof incomplete")
    items = other.get("report")
    if (not isinstance(items, list) or len(items) != 9
            or {x.get("variant") for x in items if isinstance(x, dict)} != set(SHEETS)):
        raise SourceUnavailable("independent source-country variant coverage incomplete")
    results = [{
        "variant": "Original_US_1962",
        "independent_method": "Swinkels_2019_equation_3",
        "source_math": "RECONCILED",
        "statistics": _safe_stats(us.get("historical_research_statistics")),
    }]
    for item in sorted(items, key=lambda x: x["variant"]):
        if (item.get("months") != 36
                or item.get("independent_cashflow_reconciliation") != "PASS"):
            raise SourceUnavailable("source PV mathematical reconciliation missing")
        results.append({
            "variant": item["variant"],
            "independent_method": "remaining_par_bond_cashflow_pv",
            "source_math": "RECONCILED",
            "statistics": _safe_stats(item.get("historical_research_statistics")),
        })
    if len({x["variant"] for x in results}) != 10:
        raise SourceUnavailable("duplicate original source variant")
    return {
        "schema": "ISL_SWINKELS_SOURCE_BOUND_STATS_V01",
        "source": "DataverseNL original CC BY 4.0 government bond returns",
        "source_doi": "10.34894/YWT2IX",
        "source_original_file_id": SOURCE_ID,
        "original_sha256": SOURCE_SHA,
        "window": "2020-01..2022-12",
        "source_variants": 10,
        "monthly_observations": 360,
        "estimated_bond_return_not_executable_price": True,
        "source_statistics": results,
        "dataset_2023_erasmus_v6_byte_equivalence_verified": False,
        "original_historical_vintages_verified": False,
        "historical_point_in_time_certified": False,
        "source_qualified_for_M1_M2_M3": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def main() -> None:
    raw = fetch(PUBLISHER + "/api/access/datafile/" + str(SOURCE_ID), 5_000_000)
    print("SWINKELS_ORIGINAL_SOURCE_STATS_RECEIPT=" +
          json.dumps(create_receipt(raw), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        print("SWINKELS_ORIGINAL_SOURCE_STATS_RECEIPT=BLOCKED:" + str(exc))
        raise SystemExit(2) from None
