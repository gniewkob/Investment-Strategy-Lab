"""Independent-window checks for educational, retrospective anomaly hypotheses.

This is NOT a trading backtest: original historical release vintages are
unverified, spot references are not investable total-return series and no
signal is allowed to rebalance anything. It tests sample dependence and
naive sign-persistence baselines without ever contacting a broker or database.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import hashlib
from statistics import mean, pstdev

from scripts import opportunity_radar as radar

MIN_INDEPENDENT_EVENTS = 5
MIN_GRID_WINDOWS = 12


def _direction_same(one_bar: float, forward: float) -> bool:
    """Strict sign agreement; flat future changes are not counted as hits."""
    return (one_bar > 0 and forward > 0) or (one_bar < 0 and forward < 0)


def _series_check(code: str, interval: str, rows: list[dict]) -> dict:
    n = len(rows)
    px = [float(Decimal(r["close_price"])) for r in rows]
    one_step = [px[i] / px[i - 1] - 1.0 for i in range(1, n)]
    split = max(radar.MIN_LOOKBACK + 1, int(n * 0.65))
    horizon = radar.HORIZON_BARS
    if n < radar.MIN_LOOKBACK + horizon + 3:
        raise ValueError("Series too short for retrospective window comparison")

    # Non-overlapping baseline evaluation windows; no future prices enter the
    # preceding-bar predictor. The grid is chosen before observing signals.
    grid_hit = []
    grid_forward = []
    for idx in range(split, n - horizon, horizon):
        next_move = px[idx + horizon] / px[idx] - 1.0
        yesterday = one_step[idx - 1]
        grid_hit.append(_direction_same(yesterday, next_move))
        grid_forward.append(next_move)

    # Detector mirrors the current Opportunity Radar exactly. Every z-score
    # derives from the 20 changes PRECEDING the candidate one-bar shock.
    all_candidates = 0
    nonoverlap = []
    last_taken = -horizon
    for idx in range(split, n - horizon):
        if idx <= radar.MIN_LOOKBACK:
            continue
        history = one_step[idx - radar.MIN_LOOKBACK - 1:idx - 1]
        if len(history) != radar.MIN_LOOKBACK:
            raise AssertionError("Research time-window boundary invalid")
        sd = pstdev(history)
        if sd < 1e-10:
            continue
        impulse = one_step[idx - 1]
        z = (impulse - mean(history)) / sd
        if abs(z) < radar.ZSCORE_THRESHOLD:
            continue
        all_candidates += 1
        if idx < last_taken + horizon:
            continue
        forward = px[idx + horizon] / px[idx] - 1.0
        nonoverlap.append({
            "observed_for": rows[idx]["observed_for"],
            "shock_direction": "UP" if z > 0 else "DOWN",
            "shock_magnitude_z": round(abs(z), 4),
            "next_horizon_direction_consistent": _direction_same(z, forward),
            "naive_last_bar_direction_consistent": _direction_same(impulse, forward),
            "horizon_bars": horizon,
        })
        last_taken = idx

    signal_n = len(nonoverlap)
    hits = sum(row["next_horizon_direction_consistent"] for row in nonoverlap)
    naive_hits = sum(row["naive_last_bar_direction_consistent"] for row in nonoverlap)
    # The standardized shock can have a different sign from the raw last-bar
    # return. Report both on identical dates: this prevents confusing a
    # z-score event's direction with a trivial one-bar sign continuation.
    # No predictive or profit claim follows from these descriptive rates.
    enough = (signal_n >= MIN_INDEPENDENT_EVENTS
              and len(grid_hit) >= MIN_GRID_WINDOWS)
    return {
        "instrument_code": code,
        "interval_code": interval,
        "legacy_rows": n,
        "holdout_start": rows[split]["observed_for"],
        "fixed_horizon_bars": horizon,
        "raw_shock_candidates": all_candidates,
        "nonoverlapping_shock_events": signal_n,
        "overlapping_candidates_excluded": all_candidates - signal_n,
        "baseline_grid_independent_windows": len(grid_hit),
        "event_direction_consistency_count": hits,
        "event_direction_consistency_pct": (
            round(100 * hits / signal_n, 2) if signal_n else None
        ),
        "same_dates_naive_last_bar_hits": naive_hits,
        "same_dates_naive_last_bar_consistency_pct": (
            round(100 * naive_hits / signal_n, 2) if signal_n else None
        ),
        "event_vs_same_date_naive_consistency_pp": (
            round(100 * (hits - naive_hits) / signal_n, 2) if signal_n else None
        ),
        "matched_benchmark_evaluation": "SAME_DATES_DESCRIPTIVE_NO_CAUSAL_EDGE",
        "baseline_grid_last_bar_direction_consistency_pct": (
            round(100 * sum(grid_hit) / len(grid_hit), 2) if grid_hit else None
        ),
        "baseline_grid_average_forward_reference_pct": (
            round(100 * mean(grid_forward), 4) if grid_forward else None
        ),
        "sample_gate": (
            "EXPLORATORY_SAMPLE_ONLY" if enough
            else "INSUFFICIENT_NONOVERLAPPING_EVIDENCE"
        ),
        "events": nonoverlap[-12:],
        "interpretation": (
            "Non-overlapping outcomes reduce direct window duplication, "
            "but remain serially dependent and selected retrospectively. "
            "Benchmark grid is not event-matched, so rates are not a causal "
            "edge estimate. Source publication vintages are unverified."
        ),
        "allocation_change_authorized": False,
    }


def analyze_validation(snapshot: dict, radar_result: dict) -> dict:
    """Validate snapshot again and bind findings to the exact radar fingerprint."""
    records = radar.validate_snapshot(snapshot)
    payload_hash = hashlib.sha256(
        radar._canonical(records).encode("utf-8")
    ).hexdigest()
    if (not isinstance(radar_result, dict)
            or radar_result.get("data_sha256") != payload_hash
            or radar_result.get("source_vintage")
               != "UNVERIFIED_HISTORICAL_PUBLICATION"
            or radar_result.get("pit_backtest_certified") is not False):
        raise ValueError("Non-overlap validation must match retrospective radar")
    by_series: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in records:
        by_series[(row["instrument_code"], row["interval_code"])].append(row)
    checked = [
        _series_check(code, interval, series)
        for (code, interval), series in sorted(by_series.items())
        if len(series) >= radar.MIN_LOOKBACK + radar.HORIZON_BARS + 3
    ]
    return {
        "status": "NONOVERLAPPING_RESEARCH_DIAGNOSTIC_ONLY",
        "source_radar_sha256": payload_hash,
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "series_checked": len(checked),
        "total_nonoverlapping_events": sum(
            x["nonoverlapping_shock_events"] for x in checked
        ),
        "total_excluded_overlaps": sum(
            x["overlapping_candidates_excluded"] for x in checked
        ),
        "series": checked,
        "independent_publication_vintages_verified": False,
        "causal_predictive_advantage_established": False,
        "investable_return_benchmark_verified": False,
        "virtual_portfolio_changes": 0,
        "real_orders": 0,
        "database_writes": 0,
        "scheduled": False,
    }
