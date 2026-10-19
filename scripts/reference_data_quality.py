"""Research-only freshness, peer-coverage and extreme-anomaly quality gate.

No HTTP, SQL, portfolio, brokerage or scheduler operations. The snapshot is
legacy retrospective data: observation dates DO NOT prove publication dates.
This module blocks promotion of incomplete data, not historical investigation.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from statistics import mean, median, pstdev
import hashlib
import math

from scripts import opportunity_radar as radar

DAILY_MAX_AGE_DAYS = 10
CRYPTO_MAX_AGE_DAYS = 4
MONTHLY_MAX_AGE_DAYS = 75
EXTREME_CROSS_MARKET_Z = 8.0
MIN_CRYPTO_REFERENCE_BARS = radar.MIN_LOOKBACK

PEERS = (("WTI_EIA_USD_BBL", "BRENT_EIA_USD_BBL", "1d"),)


def _max_age(code: str, interval: str) -> int:
    if interval == "1mo":
        return MONTHLY_MAX_AGE_DAYS
    if code in ("BTC-USD", "ETH-USD"):
        return CRYPTO_MAX_AGE_DAYS
    return DAILY_MAX_AGE_DAYS


def _extreme_relative_moves(by_series: dict) -> list[dict]:
    """Check ALL matched-date crypto returns, independent of radar display.

    The 20-bar mean/std estimate uses only returns strictly before the
    candidate date, exactly as the descriptive radar. Recent display results
    and any manually edited radar presentation cannot clear a quality flag.
    Robust MAD is a diagnostic, not a forecast or trading signal.
    """
    values = []
    for code in ("BTC-USD", "ETH-USD"):
        values.append({
            r["observed_for"]: float(Decimal(r["close_price"]))
            for r in by_series.get((code, "1d"), [])
        })
    matching = sorted(values[0].keys() & values[1].keys())
    if len(matching) < MIN_CRYPTO_REFERENCE_BARS + 2:
        return []
    gaps = [
        values[0][matching[i]] / values[0][matching[i - 1]]
        - values[1][matching[i]] / values[1][matching[i - 1]]
        for i in range(1, len(matching))
    ]
    findings = []
    for i in range(MIN_CRYPTO_REFERENCE_BARS + 1, len(matching)):
        # changes[j] is the return ending on matching[j+1].
        # Exclude the candidate return and use the PRECEDING 20.
        historical = gaps[i - MIN_CRYPTO_REFERENCE_BARS - 1:i - 1]
        if len(historical) != MIN_CRYPTO_REFERENCE_BARS:
            raise ValueError("Invalid historical divergence reference window")
        sigma = pstdev(historical)
        if sigma < 1e-10:
            continue
        score = (gaps[i - 1] - mean(historical)) / sigma
        if not math.isfinite(score) or abs(score) < EXTREME_CROSS_MARKET_Z:
            continue
        med = median(historical)
        mad = median(abs(x - med) for x in historical)
        robust = (gaps[i - 1] - med) / (1.4826 * mad) if mad > 1e-12 else None
        findings.append({
            "observed_for": matching[i],
            "absolute_zscore": round(abs(score), 4),
            "absolute_robust_zscore": round(abs(robust), 2)
            if robust is not None and math.isfinite(robust) else None,
            "reference_bars": len(historical),
            "status": "SOURCE_REVALIDATION_REQUIRED",
        })
    return findings

def analyze_quality(snapshot: dict, radar_report: dict) -> dict:
    records = radar.validate_snapshot(snapshot)
    fingerprint = hashlib.sha256(radar._canonical(records).encode("utf-8")).hexdigest()
    if (not isinstance(radar_report, dict)
            or radar_report.get("data_sha256") != fingerprint
            or radar_report.get("source_vintage") != "UNVERIFIED_HISTORICAL_PUBLICATION"
            or radar_report.get("pit_backtest_certified") is not False
            or radar_report.get("real_orders") != 0):
        raise ValueError("Quality gate requires matching retrospective radar")
    as_of = radar._time(snapshot["as_of"])
    grouped = defaultdict(list)
    for row in records:
        grouped[(row["instrument_code"], row["interval_code"])].append(row)
    cross = _extreme_relative_moves(grouped)
    cross_blocked = {"BTC-USD", "ETH-USD"} if cross else set()
    checked = []
    for (code, interval), group in sorted(grouped.items()):
        latest = radar._time(group[-1]["observed_for"])
        age = round((as_of - latest).total_seconds() / 86400, 3)
        max_age = _max_age(code, interval)
        warnings = []
        if age > max_age:
            warnings.append("STALE_DATA")
        if code in cross_blocked:
            warnings.append("SOURCE_REVALIDATION_REQUIRED")
        checked.append({
            "instrument_code": code,
            "interval_code": interval,
            "observations": len(group),
            "last_observed_for": latest.isoformat(),
            "age_calendar_days": age,
            "freshness_threshold_days": max_age,
            "warning_codes": warnings,
            "quality_gate": "BLOCK_RESEARCH_PROMOTION" if warnings else "REVIEW_ONLY",
            "historical_publication_verified": False,
        })

    by_code = {(s["instrument_code"], s["interval_code"]): s for s in checked}
    peer_gaps = []
    for dependent, reference, interval in PEERS:
        left = grouped.get((dependent, interval))
        right = grouped.get((reference, interval))
        if not left or not right:
            continue
        own_dates = {x["observed_for"] for x in left}
        counterpart = [x["observed_for"] for x in right if x["observed_for"] not in own_dates]
        own_latest = left[-1]["observed_for"]
        after = [d for d in counterpart if d > own_latest]
        peer_gaps.append({
            "series": dependent,
            "reference_series": reference,
            "reference_calendar_is_not_publication_proof": True,
            "missing_matched_reference_dates": len(counterpart),
            "missing_after_last_observation": len(after),
            "first_missing_after_last_observation": min(after) if after else None,
            "status": "PEER_COVERAGE_GAP_REVIEW" if counterpart else "NO_PEER_COVERAGE_GAP",
        })
        if after and "PEER_COVERAGE_GAP" not in by_code[(dependent, interval)]["warning_codes"]:
            row = by_code[(dependent, interval)]
            row["warning_codes"].append("PEER_COVERAGE_GAP")
            row["quality_gate"] = "BLOCK_RESEARCH_PROMOTION"

    blocked = sum(x["quality_gate"] == "BLOCK_RESEARCH_PROMOTION" for x in checked)
    return {
        "status": "REFERENCE_DATA_QUALITY_RESEARCH_ONLY",
        "source_radar_sha256": fingerprint,
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "snapshot_as_of": as_of.isoformat(),
        "series": checked,
        "blocked_series": blocked,
        "peer_coverage": peer_gaps,
        "extreme_relative_moves": cross,
        "historical_release_dates_verified": False,
        "freshness_means_publication_verified": False,
        "prediction_or_trading_authorized": False,
        "virtual_portfolio_changes": 0,
        "database_writes": 0,
        "real_orders": 0,
        "schedule_enabled": False,
    }
