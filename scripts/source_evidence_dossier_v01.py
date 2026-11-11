"""I5: offline research-source evidence dossier; NEVER qualifies market data.

Input is a collection of prior local, non-executable *audit reports*, not raw
vendor datasets. Checks only report structure and internal fingerprints. A
hash or self-declared licence/PIT flag is NOT independent source attestation.
No provider calls, financial operations, DB writes or data promotion.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

from scripts.shadow_decision_engine_v05 import ASSETS, MODEL_ASSETS

SCHEMA = "ISL_I5_SOURCE_EVIDENCE_DOSSIER_V01"
MAX_REPORT_BYTES = 1_000_000
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CANDIDATES = ("msci", "vanguard", "reference")
MSCI_KEYS = frozenset("""
schema status candidate claimed_index_code claimed_currency
source_currency_independently_verified usd_pln_conversion_performed
nbp_fx_date_matches_are_diagnostic_only claimed_return_basis
claimed_return_basis_independently_verified declared_index_name
original_csv_sha256 nbp_archive_sha256 first_month last_month
monthly_observations minimum_months_met same_date_nbp_fx_matches
same_date_nbp_fx_missing same_date_fx_complete
original_provider_identity_independently_authenticated
original_export_rights_independently_verified
historical_first_publication_independently_verified
pln_tr_model_qualification eligible_M1 estimated_returns
financial_operations orders_sent paper_fills database_writes
audit_receipt_sha256
""".split())
VANGUARD_KEYS = frozenset("""
status file_type raw_export_sha256 source_file_format
first_month last_month months monthly missing_nav_daily_rows
name_or_isin_authenticated_from_download historical_vintage_verified
historical_pit_certified original_exchange_fill_price_verified
usable_as_GLOBAL_EQUITY_TR_PLN backtest paper_events_created
financial_operations candidate_sha256
""".split())
REFERENCE_KEYS = frozenset("""
schema status as_of_utc source_archive_sha256 reference_months
first_month last_month real_reference_families
qualified_total_return_model_series missing_qualified_model_series
model_states decision_cycle_sha256 candidate_models
independent_original_data_bytes_verified historical_pit_certified
source_licence_independently_certified out_of_sample_performance_observed
market_data_acceptance financial_operations orders_sent paper_fills
database_writes gateway_receipt_sha256
""".split())
EVIDENCE_GAPS = {
    "GLOBAL_EQUITY_TR_PLN": [
        "INDEPENDENT_ORIGINAL_INDEX_OR_ETF_IDENTITY_MISSING",
        "RIGHTS_FOR_EXACT_DATASET_AND_RETENTION_UNVERIFIED",
        "SOURCE_CURRENCY_AND_TOTAL_RETURN_TRANSFORM_TO_PLN_UNVERIFIED",
        "FIRST_PUBLICATION_VINTAGES_AND_DECISION_CUTOFF_UNVERIFIED",
        "EXECUTABLE_INSTRUMENT_PRICE_AND_COST_BASIS_MISSING",
    ],
    "PL_BONDS_TR_PLN": [
        "BOND_INDEX_METHODOLOGY_AND_ORIGINAL_SOURCE_UNATTESTED",
        "RIGHTS_FOR_EXACT_DATASET_AND_RETENTION_UNVERIFIED",
        "INDEX_LEVEL_TO_PLN_TOTAL_RETURN_MAPPING_UNVERIFIED",
        "FIRST_PUBLICATION_VINTAGES_AND_DECISION_CUTOFF_UNVERIFIED",
        "EXECUTABLE_BOND_INSTRUMENT_PRICE_AND_COST_BASIS_MISSING",
    ],
    "GOLD_TR_PLN": [
        "REFERENCE_PRICE_NOT_FULL_INVESTABLE_TOTAL_RETURN",
        "RIGHTS_FOR_EXACT_DATASET_AND_RETENTION_UNVERIFIED",
        "FULL_PLN_RETURN_AND_COST_MODEL_UNVERIFIED",
        "FIRST_PUBLICATION_VINTAGES_AND_DECISION_CUTOFF_UNVERIFIED",
        "EXECUTABLE_GOLD_INSTRUMENT_PRICE_AND_COST_BASIS_MISSING",
    ],
}
EXPECTED_FAMILIES = {
    "NBP_GOLD_PLN_G": "PRICE_ONLY_NOT_TOTAL_RETURN",
    "NBP_USDPLN": "FX_RATE_NOT_TOTAL_RETURN",
    "BONDSPOT_TBSP_INDEX": "NON_TRADABLE_BOND_BENCHMARK",
}


class EvidenceDossierError(ValueError):
    pass


def _canonical(value):
    try:
        content = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise EvidenceDossierError("bounded canonical JSON report required") from exc
    if len(content) > MAX_REPORT_BYTES:
        raise EvidenceDossierError("candidate report exceeds metadata intake limit")
    return content


def _digest(value):
    return sha256(_canonical(value)).hexdigest()


def _check_header(record, expected, status, label):
    if not isinstance(record, dict) or set(record) != expected:
        raise EvidenceDossierError(label + ": unknown or promotion fields")
    if record.get("status") != status:
        raise EvidenceDossierError(label + ": unexpected audit status")


def _check_receipt(record, receipt, label):
    fingerprint = record[receipt]
    if (not isinstance(fingerprint, str) or not HEX64.fullmatch(fingerprint)
            or _digest({k: v for k, v in record.items() if k != receipt}) != fingerprint):
        raise EvidenceDossierError(label + ": internal receipt mismatch")


def _false(record, names, label):
    for name in names:
        if record.get(name) is not False:
            raise EvidenceDossierError(label + ": unsupported independent qualification")


def _zero(record, names, label):
    for name in names:
        if type(record.get(name)) is not int or record[name] != 0:
            raise EvidenceDossierError(label + ": financial/data-write activity claimed")


def _sha(value, label):
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise EvidenceDossierError(label + ": invalid raw SHA256 metadata")


def _month(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise EvidenceDossierError("invalid monthly observation month")
    try:
        return date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise EvidenceDossierError("invalid monthly date") from exc


def _next_month(x):
    return date(x.year + (x.month == 12), 1 if x.month == 12 else x.month + 1, 1)


def _month_span_matches(first, last, count):
    a, b = _month(first), _month(last)
    return (a <= b and (b.year - a.year) * 12 + b.month - a.month + 1 == count)


def _msci(record):
    label = "MSCI"
    _check_header(record, MSCI_KEYS,
                  "SOURCE_CANDIDATE_RIGHTS_AND_PIT_UNVERIFIED", label)
    if record["schema"] != "ISL_ACWI_NETR_MONTHLY_INTAKE_V19_001":
        raise EvidenceDossierError(label + ": incorrect source audit schema")
    _check_receipt(record, "audit_receipt_sha256", label)
    _sha(record["original_csv_sha256"], label)
    _sha(record["nbp_archive_sha256"], label)
    if (record["candidate"] != "MSCI_ACWI_NETR_USD_MONTHLY"
            or record["claimed_currency"] != "UNKNOWN_NOT_IN_SOURCE_CSV"
            or record["claimed_return_basis"] != "NET_TOTAL_RETURN"
            or record["declared_index_name"] != "MSCI ACWI"
            or record["pln_tr_model_qualification"] !=
                "BLOCKED_UNVERIFIED_RIGHTS_AND_PIT"
            or record["nbp_fx_date_matches_are_diagnostic_only"] is not True
            or record["estimated_returns"] is not None):
        raise EvidenceDossierError(label + ": unproven identity, currency or return basis")
    _false(record, (
        "source_currency_independently_verified",
        "usd_pln_conversion_performed",
        "claimed_return_basis_independently_verified",
        "original_provider_identity_independently_authenticated",
        "original_export_rights_independently_verified",
        "historical_first_publication_independently_verified",
        "eligible_M1",
    ), label)
    _zero(record, ("financial_operations", "orders_sent", "paper_fills",
                   "database_writes"), label)
    n = record["monthly_observations"]
    matched = record["same_date_nbp_fx_matches"]
    missing = record["same_date_nbp_fx_missing"]
    if (type(n) is not int or not 1 <= n <= 120
            or type(matched) is not int or not 0 <= matched <= n
            or not isinstance(missing, list)
            or len(missing) != n - matched
            or any(not isinstance(m, str) for m in missing)
            or record["minimum_months_met"] is not (n >= 36)
            or record["same_date_fx_complete"] is not (not missing)
            or not _month_span_matches(record["first_month"], record["last_month"], n)):
        raise EvidenceDossierError(label + ": malformed coverage / FX diagnostics")
    return {
        "source_kind": "MSCI_ACWI_NETR_CSV_CANDIDATE",
        "reported_months": n,
        "internal_receipt_sha256": record["audit_receipt_sha256"],
        "source_bytes_claimed_sha256": record["original_csv_sha256"],
        "source_currency_verified": False,
        "historical_pit_verified": False,
        "rights_verified": False,
    }


def _vanguard(record):
    label = "Vanguard"
    _check_header(record, VANGUARD_KEYS,
                  "RAW_NAV_XLSX_CANDIDATE_NEEDS_PROVIDER_IDENTITY_ATTESTATION", label)
    _check_receipt(record, "candidate_sha256", label)
    _sha(record["raw_export_sha256"], label)
    if (record["file_type"] != "XLSX"
            or record["source_file_format"] != "XLSX_DATE_NAV_USD_CANDIDATE_V1"
            or record["backtest"] != "NOT_RUN_PROVIDER_PROVENANCE_REQUIRED"):
        raise EvidenceDossierError(label + ": unsupported NAV candidate format")
    _false(record, (
        "name_or_isin_authenticated_from_download",
        "historical_vintage_verified",
        "historical_pit_certified",
        "original_exchange_fill_price_verified",
        "usable_as_GLOBAL_EQUITY_TR_PLN",
    ), label)
    _zero(record, ("financial_operations", "paper_events_created"), label)
    n = record["months"]
    rows = record["monthly"]
    if (type(n) is not int or not 36 <= n <= 72
            or type(record["missing_nav_daily_rows"]) is not int
            or record["missing_nav_daily_rows"] < 0
            or not isinstance(rows, list) or len(rows) != n):
        raise EvidenceDossierError(label + ": malformed NAV coverage")
    expected = _month(record["first_month"])
    for item in rows:
        if not isinstance(item, dict) or set(item) != {"month", "observed_for", "nav_usd"}:
            raise EvidenceDossierError(label + ": unsupported NAV observation format")
        observed_month = _month(item["month"])
        if observed_month != expected:
            raise EvidenceDossierError(label + ": missing or nonsequential NAV months")
        try:
            obs = date.fromisoformat(item["observed_for"])
            level = Decimal(item["nav_usd"])
        except (ValueError, TypeError, InvalidOperation) as exc:
            raise EvidenceDossierError(label + ": invalid NAV observation") from exc
        if (obs.year, obs.month) != (expected.year, expected.month):
            raise EvidenceDossierError(label + ": NAV observation month mismatch")
        if not level.is_finite() or level <= 0:
            raise EvidenceDossierError(label + ": invalid NAV reference level")
        expected = _next_month(expected)
    if rows[-1]["month"] != record["last_month"]:
        raise EvidenceDossierError(label + ": NAV last month mismatch")
    # Deliberately drop every actual monthly NAV price: only metadata
    # hashes/coverage are returned to the governance dossier.
    return {
        "source_kind": "VANGUARD_NAV_USD_XLSX_CANDIDATE",
        "reported_months": n,
        "internal_receipt_sha256": record["candidate_sha256"],
        "source_bytes_claimed_sha256": record["raw_export_sha256"],
        "original_instrument_identity_verified": False,
        "historical_pit_verified": False,
        "rights_verified": False,
        "is_executable_quote": False,
    }


def _reference(record):
    label = "NBP/BondSpot"
    _check_header(record, REFERENCE_KEYS,
                  "REFERENCE_DATA_OBSERVED_MODELS_BLOCKED", label)
    if record["schema"] != "ISL_REAL_REFERENCE_GATEWAY_V18_001":
        raise EvidenceDossierError(label + ": incorrect source audit schema")
    _check_receipt(record, "gateway_receipt_sha256", label)
    _sha(record["source_archive_sha256"], label)
    _sha(record["decision_cycle_sha256"], label)
    if (record["real_reference_families"] != EXPECTED_FAMILIES
            or record["qualified_total_return_model_series"] != []
            or record["candidate_models"] != []
            or record["missing_qualified_model_series"] != list(ASSETS)
            or record["model_states"] != {k: "HOLD_CASH" for k in MODEL_ASSETS}
            or record["market_data_acceptance"] !=
                "BLOCKED_MISSING_QUALIFIED_TOTAL_RETURN_SERIES"):
        raise EvidenceDossierError(label + ": reference index incorrectly promoted")
    _false(record, (
        "independent_original_data_bytes_verified",
        "historical_pit_certified",
        "source_licence_independently_certified",
        "out_of_sample_performance_observed",
    ), label)
    _zero(record, ("financial_operations", "orders_sent", "paper_fills",
                   "database_writes"), label)
    n = record["reference_months"]
    if (type(n) is not int or n < 36 or n > 120
            or not _month_span_matches(
                record["first_month"], record["last_month"], n)):
        raise EvidenceDossierError(label + ": invalid reference coverage")
    return {
        "source_kind": "NBP_BONDSPOT_NONEXECUTABLE_REFERENCE",
        "reported_months": n,
        "internal_receipt_sha256": record["gateway_receipt_sha256"],
        "source_bytes_claimed_sha256": record["source_archive_sha256"],
        "historical_pit_verified": False,
        "rights_verified": False,
        "is_total_return_model_data": False,
    }


AUDITORS = {"msci": _msci, "vanguard": _vanguard, "reference": _reference}
ASSET_CANDIDATES = {
    "GLOBAL_EQUITY_TR_PLN": ("msci", "vanguard"),
    "PL_BONDS_TR_PLN": ("reference",),
    "GOLD_TR_PLN": ("reference",),
}


def assess_dossier(reports: object) -> dict:
    """Classify evidence gaps; never issue model eligibility or a source manifest."""
    if not isinstance(reports, dict) or set(reports) - set(CANDIDATES):
        raise EvidenceDossierError("expected known candidate report families only")
    audited = {}
    for key in CANDIDATES:
        record = reports.get(key)
        if record is None:
            audited[key] = {"status": "NO_REPORT_AVAILABLE"}
            continue
        _canonical(record)
        audited[key] = {"status": "INTERNAL_CONSISTENCY_ONLY",
                        **AUDITORS[key](record)}
    assets = {
        asset: {
            "status": "BLOCKED_EVIDENCE_INCOMPLETE",
            "candidate_audits_available": [
                source for source in ASSET_CANDIDATES[asset]
                if audited[source]["status"] == "INTERNAL_CONSISTENCY_ONLY"
            ],
            "required_independent_evidence": list(EVIDENCE_GAPS[asset]),
            "qualified_source_available": False,
        }
        for asset in ASSETS
    }
    output = {
        "schema": SCHEMA,
        "status": "SOURCE_EVIDENCE_REVIEW_REQUIRED",
        "report_integrity_scope": "UNTRUSTED_METADATA_INTERNAL_CHECKSUMS_ONLY",
        "reports": audited,
        "asset_qualification": assets,
        "qualified_model_series": [],
        "model_decisions": {
            key: {"status": "HOLD_CASH", "virtual_target": {"CASH_PLN": "1"}}
            for key in MODEL_ASSETS
        },
        "paper_candidates": [],
        "historical_point_in_time_certified": False,
        "source_rights_independently_certified": False,
        "market_execution_authorized": False,
        "integration_to_main_authorized": False,
        "source_manifest_created": False,
        "orders_sent": 0,
        "paper_fills": 0,
        "financial_operations": 0,
        "database_writes": 0,
    }
    output["dossier_sha256"] = _digest(output)
    return output


def _read_bounded(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise EvidenceDossierError("bounded regular metadata report required")
    raw = path.read_bytes()
    if len(raw) > MAX_REPORT_BYTES:
        raise EvidenceDossierError("oversized candidate report")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceDossierError("invalid candidate report JSON") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--msci-report", type=Path)
    parser.add_argument("--vanguard-report", type=Path)
    parser.add_argument("--reference-report", type=Path)
    args = parser.parse_args()
    reports = {
        key: _read_bounded(p)
        for key, p in (("msci", args.msci_report),
                       ("vanguard", args.vanguard_report),
                       ("reference", args.reference_report))
        if p is not None
    }
    print("ISL_I5_EVIDENCE_DOSSIER=" +
          json.dumps(assess_dossier(reports), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
