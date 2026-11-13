"""Cross-provider research readiness without conflating nominal yields, NAV or turnover.

Consumes already validated metadata-only receipts; no HTTP, no original
market rows, no account access. Source evidence is not historical PIT proof.
"""
from __future__ import annotations

import json
import re
from datetime import datetime,timezone
from hashlib import sha256

class ResearchEvidenceBlocked(ValueError):
    pass


def _sha(value, label):
    if not isinstance(value,str) or not re.fullmatch(r"[0-9a-f]{64}",value):
        raise ResearchEvidenceBlocked(label+"_ORIGINAL_SHA_REQUIRED")
    return value


def compose_source_readiness(*, nav_quality: dict, mf_schema: dict,
                             macro_reference: dict | None = None,
                             observed_at: datetime) -> dict:
    if (not isinstance(observed_at,datetime) or observed_at.tzinfo is None
            or observed_at.utcoffset() is None):
        raise ResearchEvidenceBlocked("UTC_AWARE_OBSERVATION_REQUIRED")
    if (not isinstance(nav_quality,dict)
            or nav_quality.get("schema")!="ISL_UKNF_ONE_CLASS_DESCRIPTIVE_NAV_QUALITY_V07"
            or nav_quality.get("same_unit_primary_pln") is not True
            or nav_quality.get("nav_distribution_adjusted_return") is not False
            or nav_quality.get("historical_first_publication_proven") is not False
            or nav_quality.get("asset_return_series_admitted")!=[]
            or nav_quality.get("financial_operations")!=0):
        raise ResearchEvidenceBlocked("NAV_QUALITY_UNTRUSTED_OR_PROMOTED")
    nav_hash=_sha(nav_quality.get("source_history_sha256"),"NAV")
    if (not isinstance(mf_schema,dict)
            or mf_schema.get("schema")!="ISL_MF_OFFICIAL_SECONDARY_TREASURY_SCHEMA_AUDIT_V07"
            or mf_schema.get("state")!="ORIGINAL_WORKBOOK_SCHEMA_ONLY_NO_TURNOVER_ADMISSION"
            or mf_schema.get("turnover_units_validated") is not False
            or mf_schema.get("historical_first_publication_proven") is not False
            or mf_schema.get("bond_total_return_observed") is not False
            or mf_schema.get("source_data_rows_in_report")!=0
            or mf_schema.get("financial_operations")!=0):
        raise ResearchEvidenceBlocked("MF_ORIGINAL_SCHEMA_UNTRUSTED_OR_PROMOTED")
    mf_hash=_sha(mf_schema.get("sha256"),"MF")
    rows=[
        {"source":"UKNF","data_type":"SINGLE_PRIMARY_PLN_UNIT_NAV_LEVELS",
         "original_response_sha256":nav_hash,
         "observed_points":nav_quality["distinct_valuation_days"],
         "observed_units":"ONE_FUND_UNIT_PLN_NOMINAL_NAV",
         "data_fitness":"SAME_CLASS_DESCRIPTIVE_NAV_CHANGE_ONLY",
         "historical_first_publication_certified":False,
         "income_or_distribution_adjusted_total_return":False,
         "source_rights":"FREE_PUBLIC_UKNF_API_ATTRIBUTION_NO_OVERLOAD"},
        {"source":"MINISTRY_OF_FINANCE","data_type":"GOVERNMENT_BOND_SECONDARY_TURNOVER_XLSX",
         "original_response_sha256":mf_hash,
         "observed_points":None,
         "observed_units":"NOT_YET_SEMANTICALLY_VERIFIED",
         "data_fitness":"ORIGINAL_WORKBOOK_SCHEMA_VERIFIED_TURNOVER_VALUES_BLOCKED",
         "historical_first_publication_certified":False,
         "income_or_distribution_adjusted_total_return":False,
         "source_rights":"PUBLIC_ORIGINAL_FILE_REUSE_SCOPE_NEEDS_REVIEW"},
    ]
    if macro_reference is not None:
        m=macro_reference
        if (not isinstance(m,dict)
                or m.get("schema")!="ISL_PUBLIC_MULTISOURCE_MACRO_EVIDENCE_V05"
                or m.get("historical_point_in_time_certified") is not False
                or m.get("source_rights_fully_approved") is not False
                or m.get("asset_total_return_series_qualified")!=[]
                or m.get("financial_operations")!=0
                or m.get("hicp_months")!=13
                or m.get("government_yield_months")!=59
                or not isinstance(m.get("source_fingerprints_sha256"),dict)
                or set(m["source_fingerprints_sha256"])!={"nbp_gold","nbp_fx","eurostat_hicp","eurostat_pl_government_yield"}):
            raise ResearchEvidenceBlocked("MACRO_SOURCE_SEMANTIC_CONFLICT")
        for k in m["source_fingerprints_sha256"]:
            _sha(m["source_fingerprints_sha256"][k],"MACRO")
        macro_hash=_sha(m.get("receipt_sha256"),"MACRO_RECEIPT")
        rows.append({
            "source":"NBP_EUROSTAT",
            "data_type":"FX_MID_GOLD_PRICE_HICP_AND_GOV_YIELD_REFERENCE",
            "original_response_sha256":macro_hash,
            "observed_points":None,
            "observed_units":"MIXED_CURRENCY_PER_G_PRICE_INDEX_AND_YIELD_PA_SEPARATE",
            "data_fitness":"MACRO_REFERENCE_CONTEXT_ONLY",
            "historical_first_publication_certified":False,
            "income_or_distribution_adjusted_total_return":False,
            "source_rights":"OFFICIAL_PUBLIC_STATS_NEED_ATTRIBUTION",
        })
    out={
        "schema":"ISL_MULTISOURCE_RESEARCH_READINESS_V07",
        "status":"DATA_QUALITY_RESEARCH_REFERENCE_NOT_TRADABLE_SERIES",
        "observed_at_utc":observed_at.astimezone(timezone.utc).isoformat(),
        "source_readiness":rows,
        "source_families":len(rows),
        "historical_pit_admitted":False,
        "asset_total_return_qualified":[],
        "live_execution_authorized":False,
        "m1_m2_m3":"INSUFFICIENT_DATA_HOLD_CASH",
        "outbound_source_reads":0,
        "database_writes":0,
        "orders":0,
        "financial_operations":0,
    }
    out["receipt_sha256"]=sha256(json.dumps(out,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return out
