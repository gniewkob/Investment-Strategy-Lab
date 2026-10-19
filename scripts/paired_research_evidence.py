"""Offline paired-event research diagnostic, NOT a forecasting/trading backtest.

Accepts ONLY the aggregate/non-overlap research JSON already produced by the
educational pipeline. No databases, market data fetch, wallets, or orders.
This deliberately computes *descriptive* paired counts, not a p-value or
investable performance estimate: these historically selected event dates are
not independently observed publication-vintage-verified evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys


HASH = re.compile(r"[a-f0-9]{64}\Z")
CODE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
MAX_INPUT_BYTES = 2_000_000


def _nonnegative_count(source: dict, key: str) -> int:
    value = source[key]
    if type(value) is not int or value < 0:
        raise ValueError("Invalid count in descriptive research report")
    return value


def summarize(source: dict) -> dict:
    """Require complete same-date paired outcomes and strictly no live claims."""
    if not isinstance(source, dict):
        raise ValueError("Expected historical research report")
    if (source.get("status") != "NONOVERLAPPING_RESEARCH_DIAGNOSTIC_ONLY"
            or source.get("source_vintage") != "UNVERIFIED_HISTORICAL_PUBLICATION"
            or source.get("independent_publication_vintages_verified") is not False
            or source.get("causal_predictive_advantage_established") is not False
            or source.get("investable_return_benchmark_verified") is not False
            or source.get("real_orders") != 0
            or source.get("database_writes") != 0
            or source.get("virtual_portfolio_changes") != 0
            or source.get("scheduled") is not False
            or source.get("schedule_enabled", False) is not False
            or not isinstance(source.get("source_radar_sha256"), str)
            or not HASH.fullmatch(source["source_radar_sha256"])):
        raise ValueError("Only fingerprinted unverified-vintage research is accepted")
    series = source.get("series")
    if not isinstance(series, list) or len(series) > 100:
        raise ValueError("Invalid research series set")
    if _nonnegative_count(source, "series_checked") != len(series):
        raise ValueError("Series count mismatch")
    seen_series = set()
    summarized = []
    total_n = 0
    total_overlap = 0
    total_shock_only = 0
    total_naive_only = 0
    for item in series:
        if not isinstance(item, dict):
            raise ValueError("Invalid series object")
        name = item.get("instrument_code")
        interval = item.get("interval_code")
        if (not isinstance(name, str) or not CODE.fullmatch(name)
                or interval not in ("1d", "1mo")):
            raise ValueError("Invalid instrument/interval")
        key = name, interval
        if key in seen_series:
            raise ValueError("Repeated research series")
        seen_series.add(key)
        n = _nonnegative_count(item, "nonoverlapping_shock_events")
        excluded = _nonnegative_count(item, "overlapping_candidates_excluded")
        candidates = _nonnegative_count(item, "raw_shock_candidates")
        reported_shock_hits = _nonnegative_count(
            item, "event_direction_consistency_count")
        reported_naive_hits = _nonnegative_count(
            item, "same_dates_naive_last_bar_hits")
        horizon = _nonnegative_count(item, "fixed_horizon_bars")
        if (horizon == 0 or candidates != n + excluded
                or reported_shock_hits > n or reported_naive_hits > n):
            raise ValueError("Inconsistent candidate/horizon counts")
        events = item.get("events")
        # Existing robustness.json contains ONLY events[-12:]. Detect future
        # truncation and fail closed, instead of computing biased confidence
        # or paired statistics from an incomplete event sample.
        if not isinstance(events, list) or len(events) != n:
            raise ValueError("Truncated or inconsistent event-level evidence")
        both_hit = both_miss = shock_only = naive_only = 0
        dates = set()
        for event in events:
            if not isinstance(event, dict):
                raise ValueError("Invalid paired event")
            when = event.get("observed_for")
            if not isinstance(when, str) or when in dates:
                raise ValueError("Missing or duplicate event timestamp")
            try:
                parsed = datetime.fromisoformat(when.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Invalid event timestamp") from exc
            if parsed.tzinfo is None:
                raise ValueError("Timezone-aware event timestamps required")
            dates.add(when)
            if event.get("horizon_bars") != horizon:
                raise ValueError("Mixed event horizons")
            e = event.get("next_horizon_direction_consistent")
            b = event.get("naive_last_bar_direction_consistent")
            if type(e) is not bool or type(b) is not bool:
                raise ValueError("Missing paired binary outcomes")
            if e and b:
                both_hit += 1
            elif e:
                shock_only += 1
            elif b:
                naive_only += 1
            else:
                both_miss += 1
        event_hits = both_hit + shock_only
        naive_hits = both_hit + naive_only
        if (event_hits != reported_shock_hits or naive_hits != reported_naive_hits
                or event_hits + (both_miss + naive_only) != n):
            raise ValueError("Reported hit counts differ from paired evidence")
        delta_pp = round(100 * (shock_only - naive_only) / n, 2) if n else None
        reported_delta = item.get("event_vs_same_date_naive_consistency_pp")
        if reported_delta is not None and reported_delta != delta_pp:
            raise ValueError("Inconsistent reported same-date effect")
        summarized.append({
            "instrument_code": name,
            "interval_code": interval,
            "paired_complete_events": n,
            "both_correct": both_hit,
            "both_incorrect": both_miss,
            "radar_only_correct": shock_only,
            "naive_only_correct": naive_only,
            "radar_direction_agreement_pct":
                round(100 * event_hits / n, 2) if n else None,
            "naive_direction_agreement_pct":
                round(100 * naive_hits / n, 2) if n else None,
            "observed_paired_difference_pp": delta_pp,
            "events_selected_retrospectively": True,
            "publication_vintage_verified": False,
            "predictive_edge_inferred": False,
        })
        total_n += n
        total_overlap += excluded
        total_shock_only += shock_only
        total_naive_only += naive_only

    if (total_n != _nonnegative_count(source, "total_nonoverlapping_events")
            or total_overlap != _nonnegative_count(source, "total_excluded_overlaps")):
        raise ValueError("Top-level totals do not match the series")
    return {
        "status": "PAIRED_BASELINE_DESCRIPTIVE_ONLY",
        "source_radar_sha256": source["source_radar_sha256"],
        "input_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "series_checked": len(summarized),
        "paired_events": total_n,
        "excluded_overlapping_candidates": total_overlap,
        "radar_only_correct": total_shock_only,
        "naive_only_correct": total_naive_only,
        "paired_difference_pp": (
            round(100 * (total_shock_only - total_naive_only) / total_n, 2)
            if total_n else None
        ),
        "series": summarized,
        "inference": "NO_PREDICTIVE_ADVANTAGE_OR_EQUIVALENCE_CLAIM",
        "reason": (
            "Historically selected, serially dependent and sparse shock events; "
            "the simple sign-persistence comparator is coupled to the shock "
            "direction; event outcomes were already inspected; true "
            "publication-vintage/out-of-sample evidence is unavailable."
        ),
        "independent_confirmatory_holdout_available": False,
        "point_in_time_certified": False,
        "research_only": True,
        "portfolio_change_authorized": False,
        "virtual_allocations_changed": 0,
        "database_writes": 0,
        "real_orders": 0,
        "schedule_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Descriptive comparison of historic radar and same-date naive outcomes")
    parser.add_argument("--robustness-json", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.robustness_json.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("Research JSON exceeds input cap")
        obj = json.loads(args.robustness_json.read_text(encoding="utf-8"))
        result = summarize(obj)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        # Deliberately never print paths, source JSON or exception text.
        print("PAIRED_RESEARCH_AUDIT_FAILED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
