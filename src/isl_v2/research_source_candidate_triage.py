"""Research-only taxonomy of candidate sources versus ISL model semantics.

Official *descriptive web pages* establish candidate descriptions, not a
licensed authenticated source artifact or point-in-time data availability.
This catalog cannot create source pins, approve sources, fetch prices,
convert currencies, or enable paper/live portfolio targets.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from .total_return_evidence_preflight import EXPECTED_INSTRUMENTS


@dataclass(frozen=True)
class CandidateDescription:
    candidate_id: str
    proposed_slot: str
    value_concept: str
    currency: str
    exposure: str
    official_information_page: str
    license_reviewed: bool = False
    source_bytes_authenticated: bool = False
    vintage_publication_verified: bool = False


# All records are *unapproved research candidates*. Links document public
# classification only. They are not approved API endpoints or data licences.
_CANDIDATES = {
    "TBSP_INDEX": CandidateDescription(
        "TBSP_INDEX", "BONDS_TR_PLN", "TOTAL_RETURN_INDEX", "PLN",
        "PL_SOVEREIGN_BONDS",
        "https://www.bondspot.pl/tbsp_index_description_en",
    ),
    "VANGUARD_ALL_WORLD_ACC": CandidateDescription(
        "VANGUARD_ALL_WORLD_ACC", "EQUITY_TR_PLN",
        "ACCUMULATING_FUND_NAV", "USD", "GLOBAL_EQUITIES",
        "https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating",
    ),
    "NBP_GOLD_PRICE": CandidateDescription(
        "NBP_GOLD_PRICE", "GOLD_TR_PLN", "GOLD_SPOT_REFERENCE", "PLN", "GOLD",
        "https://api.nbp.pl/",
    ),
    "GPW_WIG": CandidateDescription(
        "GPW_WIG", "EQUITY_TR_PLN", "TOTAL_RETURN_INDEX", "PLN", "PL_EQUITIES",
        "https://gpwbenchmark.pl/karta-indeksu?isin=PL9999999995",
    ),
}
RESEARCH_CANDIDATES = MappingProxyType(_CANDIDATES)

SLOT_EXPOSURE = MappingProxyType({
    "EQUITY_TR_PLN": "GLOBAL_EQUITIES",
    "BONDS_TR_PLN": "PL_SOVEREIGN_BONDS",
    "GOLD_TR_PLN": "GOLD",
})


def candidate_screen(candidate: CandidateDescription) -> dict:
    """Non-authorizing semantic preflight. External flags never grant trust."""
    if not isinstance(candidate, CandidateDescription):
        raise ValueError("INVALID_CANDIDATE")
    if candidate.proposed_slot not in EXPECTED_INSTRUMENTS:
        raise ValueError("UNKNOWN_MODEL_SLOT")
    failures = []
    if candidate.value_concept != "TOTAL_RETURN_INDEX":
        failures.append("NOT_TOTAL_RETURN_INDEX")
    if candidate.currency != "PLN":
        failures.append("CURRENCY_TRANSFORMATION_REQUIRED")
    if candidate.exposure != SLOT_EXPOSURE[candidate.proposed_slot]:
        failures.append("MANDATE_EXPOSURE_MISMATCH")
    if candidate.license_reviewed is not True:
        failures.append("LICENCE_SCOPE_UNVERIFIED")
    if candidate.source_bytes_authenticated is not True:
        failures.append("SOURCE_BYTES_NOT_AUTHENTICATED")
    if candidate.vintage_publication_verified is not True:
        failures.append("HISTORICAL_PIT_UNVERIFIED")
    return {
        "candidate_id": candidate.candidate_id,
        "proposed_slot": candidate.proposed_slot,
        "semantic_match": not any(
            reason in failures for reason in (
                "NOT_TOTAL_RETURN_INDEX",
                "CURRENCY_TRANSFORMATION_REQUIRED",
                "MANDATE_EXPOSURE_MISMATCH",
            )
        ),
        "research_blockers": failures,
        "authenticated_source_manifest_present": False,
        "candidate_source_admitted": False,
        "historical_pit_certified": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def research_candidate_inventory() -> dict:
    return {
        "contract": "candidate_source_type_screen_v01",
        "candidates": [
            candidate_screen(RESEARCH_CANDIDATES[name])
            for name in sorted(RESEARCH_CANDIDATES)
        ],
        "reviewed_source_pin_count": 0,
        "candidate_source_admitted": False,
        "historical_pit_certified": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }
