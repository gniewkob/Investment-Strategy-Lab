"""Offline prospective total-return index source evidence preflight.

Pure, deterministic, bounded checks of proposed source observations. This is
not a trusted-source registry, an investment backtest, a PIT certificate or a
way to authorize M1/M2/M3. Caller-provided evidence can pass *structural*
checks but NEVER grant model admission.

Designed separately from src.isl_v2.provenance and autonomous_agent to avoid
allowing external metadata to enable PAPER_TARGET_INTENT implicitly.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
from urllib.parse import urlsplit

from .provenance import utc

EXPECTED_INSTRUMENTS = (
    "EQUITY_TR_PLN", "BONDS_TR_PLN", "GOLD_TR_PLN",
)
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{2,100}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
MAX_OBSERVATIONS = 48
REQUIRED_FIELDS = (
    "instrument_code", "source_code", "official_series_id",
    "currency", "value_concept", "return_basis", "interval_code",
    "month", "observed_for", "price_value", "source_url",
    "source_sha256", "source_version", "first_public_at",
    "retrieved_at", "publication_precision", "license_url",
    "transformation_version",
)
ALLOWED_RETURN_BASIS = ("GROSS_TOTAL_RETURN", "NET_TOTAL_RETURN")


class EvidenceContractBlocked(ValueError):
    """Source evidence fails one or more structural preflight checks."""


def _month_floor(value: str) -> date:
    if not isinstance(value, str) or not _MONTH.fullmatch(value):
        raise EvidenceContractBlocked("INVALID_MONTH")
    return date(int(value[:4]), int(value[5:7]), 1)


def _month_index(first_day: date) -> int:
    return first_day.year * 12 + first_day.month


def _source_https(value: str) -> bool:
    if not isinstance(value, str) or len(value) > 512:
        return False
    try:
        u = urlsplit(value)
    except ValueError:
        return False
    return (
        u.scheme == "https" and bool(u.hostname)
        and u.username is None and u.password is None
        and u.fragment == "" and u.query == ""
        and u.port in (None, 443)
    )


def _finite_positive(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return False
    try:
        v = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False
    return v.is_finite() and v > 0


def _validate_one(row: dict, decision_cutoff: datetime) -> tuple[str, str]:
    if not isinstance(row, dict):
        raise EvidenceContractBlocked("INVALID_OBSERVATION")
    if any(k not in row for k in REQUIRED_FIELDS):
        raise EvidenceContractBlocked("REQUIRED_EVIDENCE_MISSING")

    instrument = row["instrument_code"]
    if instrument not in EXPECTED_INSTRUMENTS:
        raise EvidenceContractBlocked("UNKNOWN_INSTRUMENT")
    if not all(isinstance(row[name], str) and _TOKEN.fullmatch(row[name])
               for name in ("source_code", "official_series_id",
                            "source_version", "transformation_version")):
        raise EvidenceContractBlocked("SOURCE_IDENTIFIER_INVALID")
    if row["currency"] != "PLN":
        raise EvidenceContractBlocked("NON_PLN_PRICE_BASIS")
    if row["value_concept"] != "TOTAL_RETURN_INDEX":
        raise EvidenceContractBlocked("NOT_TOTAL_RETURN_INDEX")
    if row["return_basis"] not in ALLOWED_RETURN_BASIS:
        raise EvidenceContractBlocked("RETURN_BASIS_UNSPECIFIED")
    if row["interval_code"] != "1mo":
        raise EvidenceContractBlocked("NOT_MONTHLY")
    if not _finite_positive(row["price_value"]):
        raise EvidenceContractBlocked("NONPOSITIVE_OR_INVALID_INDEX_LEVEL")
    if not _source_https(row["source_url"]) or not _source_https(row["license_url"]):
        raise EvidenceContractBlocked("INVALID_SOURCE_OR_LICENSE_URL")
    if not isinstance(row["source_sha256"], str) or not _SHA.fullmatch(row["source_sha256"]):
        raise EvidenceContractBlocked("MISSING_VERIFIABLE_SHA256")

    month = _month_floor(row["month"])
    try:
        observed = utc(row["observed_for"])
        published = utc(row["first_public_at"])
        retrieved = utc(row["retrieved_at"])
    except ValueError as exc:
        raise EvidenceContractBlocked("TIMESTAMP_MISSING_OR_AMBIGUOUS") from exc

    if observed.year != month.year or observed.month != month.month:
        raise EvidenceContractBlocked("OBSERVATION_MONTH_MISMATCH")
    if row["publication_precision"] not in ("EXACT", "DAY"):
        raise EvidenceContractBlocked("PUBLICATION_PRECISION_UNSUPPORTED")
    # DAY precision is *not* proof of availability during that date.
    effective_publication = (
        published.replace(hour=0, minute=0, second=0, microsecond=0)
        + timedelta(days=1)
        if row["publication_precision"] == "DAY"
        else published
    )
    if effective_publication < observed:
        raise EvidenceContractBlocked("PUBLISHED_BEFORE_OBSERVATION")
    if retrieved < published:
        raise EvidenceContractBlocked("RETRIEVAL_BEFORE_PUBLISHED")
    if effective_publication > decision_cutoff:
        raise EvidenceContractBlocked("PUBLICATION_AFTER_DECISION")
    if retrieved > decision_cutoff:
        raise EvidenceContractBlocked("ARCHIVE_RETRIEVED_AFTER_DECISION")
    if observed > decision_cutoff:
        raise EvidenceContractBlocked("OBSERVATION_AFTER_DECISION")
    return instrument, row["month"]


def inspect_total_return_evidence(observations: object, *, decision_asof: str) -> dict:
    """Return structural evidence receipt; never approve a source or strategy.

    No fallback to a user's 'trusted', 'PIT_VERIFIED' or 'approved' flags. The
    caller controls this payload, so source authenticity is NOT established.
    """
    try:
        cutoff = utc(decision_asof)
    except ValueError as exc:
        raise EvidenceContractBlocked("INVALID_DECISION_CUTOFF") from exc
    if not isinstance(observations, (list, tuple)) or not 1 <= len(observations) <= MAX_OBSERVATIONS:
        raise EvidenceContractBlocked("EVIDENCE_SET_INVALID_SIZE")
    by_instrument: dict[str, set[str]] = {
        code: set() for code in EXPECTED_INSTRUMENTS
    }
    source_ids: dict[str, set[tuple[str, str]]] = {
        code: set() for code in EXPECTED_INSTRUMENTS
    }
    for row in observations:
        code, month = _validate_one(row, cutoff)
        if month in by_instrument[code]:
            raise EvidenceContractBlocked("DUPLICATE_INSTRUMENT_MONTH")
        by_instrument[code].add(month)
        source_ids[code].add((row["source_code"], row["official_series_id"]))
    for code in EXPECTED_INSTRUMENTS:
        months = sorted(by_instrument[code])
        if len(months) != 4:
            raise EvidenceContractBlocked("FOUR_MONTH_COVERAGE_INCOMPLETE")
        indexes = [_month_index(_month_floor(m)) for m in months]
        if indexes != list(range(indexes[0], indexes[0] + 4)):
            raise EvidenceContractBlocked("NONCONSECUTIVE_MONTHS")
        if len(source_ids[code]) != 1:
            raise EvidenceContractBlocked("INCONSISTENT_SOURCE_SERIES_ID")

    # This deterministic payload demonstrates that proposed metadata has
    # structurally consistent availability. It DOES NOT verify the truth of
    # the asserted timestamp, source contents, license or publisher identity.
    return {
        "contract": "total_return_index_evidence_preflight_v01",
        "decision_asof": cutoff.isoformat(),
        "instrument_count": len(EXPECTED_INSTRUMENTS),
        "observations_checked": len(observations),
        "structural_evidence_consistency": "PASS",
        "independent_source_authentication": "NOT_PERFORMED",
        "historic_first_publication_verified": False,
        "historical_pit_certified": False,
        "model_admission_granted": False,
        "qualified_model_series": [],
        "research_model_state": "HOLD_CASH",
        "financial_operations": 0,
    }
