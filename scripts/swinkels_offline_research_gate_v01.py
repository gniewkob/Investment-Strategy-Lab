"""Fail-closed, offline Swinkels research validation; no source ingest or trading.

Original ODS SHA is provenance, not evidence of numeric scale. Never infer the
unit from the magnitude of the historical observations.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

EXPECTED_MONTHS = tuple(f"{y:04d}-{m:02d}" for y in range(2020, 2023) for m in range(1, 13))
SOURCE_SHA256 = "90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847"
COUNTRIES = frozenset({"DE", "JP", "FR", "UK", "AU", "CA", "NO", "SE", "US_ORIGINAL", "US_IMPROVED"})


class ResearchGateBlocked(ValueError):
    """The input is not qualified even for offline return statistics."""


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ResearchGateBlocked("INVALID_RETURN_VALUE")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ResearchGateBlocked("INVALID_RETURN_VALUE") from None
    if not number.is_finite():
        raise ResearchGateBlocked("NONFINITE_RETURN_VALUE")
    return number


def validate_monthly_series(*, country, observations, source_sha256,
                            return_unit=None, unit_evidence=None,
                            methodology_evidence=None):
    """Production research admission is blocked until publisher units are verified.

    A free-text evidence string cannot qualify source units or methodology.
    """
    raise ResearchGateBlocked("SOURCE_UNITS_NOT_CERTIFIED")


def _validate_synthetic_monthly_series(*, country, observations, source_sha256,
                                       return_unit=None, unit_evidence=None,
                                       methodology_evidence=None):
    """Test-only math validation for artificial series; not source approval."""
    if source_sha256 != SOURCE_SHA256:
        raise ResearchGateBlocked("SOURCE_HASH_MISMATCH")
    if country not in COUNTRIES:
        raise ResearchGateBlocked("COUNTRY_OR_VARIANT_NOT_SUPPORTED")
    if return_unit not in ("decimal", "percent"):
        raise ResearchGateBlocked("RETURN_UNITS_UNVERIFIED")
    if not isinstance(unit_evidence, str) or not unit_evidence.strip():
        raise ResearchGateBlocked("RETURN_UNIT_EVIDENCE_MISSING")
    if not isinstance(methodology_evidence, str) or not methodology_evidence.strip():
        raise ResearchGateBlocked("METHODOLOGY_EVIDENCE_MISSING")
    if not isinstance(observations, (list, tuple)) or len(observations) != 36:
        raise ResearchGateBlocked("MONTHLY_COVERAGE_INCOMPLETE")
    seen = {}
    for item in observations:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ResearchGateBlocked("INVALID_OBSERVATION_SHAPE")
        month, raw = item
        if not isinstance(month, str) or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", month):
            raise ResearchGateBlocked("INVALID_MONTH")
        if month in seen:
            raise ResearchGateBlocked("DUPLICATE_MONTH")
        number = _decimal(raw)
        ret = number / Decimal(100) if return_unit == "percent" else number
        if ret <= -1:
            raise ResearchGateBlocked("RETURN_AT_OR_BELOW_MINUS_100_PERCENT")
        seen[month] = ret
    if set(seen) != set(EXPECTED_MONTHS):
        raise ResearchGateBlocked("MONTHLY_WINDOW_MISMATCH")
    return tuple(seen[month] for month in EXPECTED_MONTHS)


def offline_statistics(monthly_decimals):
    """Real-source statistics remain disabled until units are certified."""
    raise ResearchGateBlocked("SOURCE_UNITS_NOT_CERTIFIED")


def _offline_synthetic_statistics(monthly_decimals):
    """Synthetic math fixture only; never qualify original market returns."""
    if not isinstance(monthly_decimals, tuple) or len(monthly_decimals) != 36:
        raise ResearchGateBlocked("UNVALIDATED_MONTHLY_SERIES")
    if any(not isinstance(r, Decimal) or not r.is_finite() or r <= -1 for r in monthly_decimals):
        raise ResearchGateBlocked("UNVALIDATED_MONTHLY_SERIES")
    wealth = Decimal(1)
    peak = Decimal(1)
    max_drawdown = Decimal(0)
    for ret in monthly_decimals:
        wealth *= 1 + ret
        peak = max(peak, wealth)
        max_drawdown = min(max_drawdown, wealth / peak - 1)
    mean = sum(monthly_decimals) / len(monthly_decimals)
    variance = sum((r - mean) ** 2 for r in monthly_decimals) / (len(monthly_decimals) - 1)
    return {
        "sample_months": 36,
        "compounded_total_return": wealth - 1,
        "monthly_mean": mean,
        "monthly_sample_volatility": variance.sqrt(),
        "max_drawdown": max_drawdown,
        "source_type": "ESTIMATED_GOVERNMENT_BOND_RETURN",
        "historical_pit_certified": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
    }
