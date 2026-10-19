"""Retrospective, research-only anomaly radar and historical evidence comparator.

Accepts an explicit, untrusted-vintage snapshot of LEGACY close prices.
Does NOT connect to databases, exchanges, brokers or execution systems.
Never treats a historical observation's date as proof of historical publication.
Outputs hypotheses to INVESTIGATE, not orders or allocation instructions.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median, pstdev
import sys

SUPPORTED = {
    "BTC-USD", "ETH-USD", "GOLD_NBP_PLN_G", "USDPLN_NBP",
    "EURPLN_NBP", "BRENT_EIA_USD_BBL", "WTI_EIA_USD_BBL",
    "HENRY_HUB_USD_MMBTU", "COPPER_WB_USD_T",
    "ALUMINUM_WB_USD_T", "NICKEL_WB_USD_T", "SILVER_WB_USD_OZ",
}
MIN_LOOKBACK = 20
HORIZON_BARS = 5
ZSCORE_THRESHOLD = 2.5
MIN_SIGNALS_FOR_COMPARISON = 5
MAX_RECORDS = 15_000


def _canonical(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Expected ISO timestamp")
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid timestamp") from None
    if when.tzinfo is None:
        raise ValueError("Timestamp must be timezone aware")
    return when.astimezone(timezone.utc)


def validate_snapshot(payload: dict) -> list[dict]:
    """Reject duplicate periods, future dates, missing or incompatible metadata."""
    if not isinstance(payload, dict) or payload.get("mode") != "RETROSPECTIVE_RESEARCH_ONLY":
        raise ValueError("Explicit retrospective research mode required")
    if payload.get("source_vintage") != "UNVERIFIED_HISTORICAL_PUBLICATION":
        raise ValueError("Do not misrepresent a legacy backfill as point-in-time evidence")
    as_of = _time(payload["as_of"])
    if not isinstance(payload.get("records"), list):
        raise ValueError("Missing historical records")
    if not 1 <= len(payload["records"]) <= MAX_RECORDS:
        raise ValueError("Unsupported snapshot size")
    rows = []
    seen: set[tuple[str, str, str]] = set()
    for entry in payload["records"]:
        if not isinstance(entry, dict):
            raise ValueError("Invalid row")
        code, interval, basis = entry["instrument_code"], entry["interval_code"], entry["return_basis"]
        if code not in SUPPORTED or interval not in ("1d", "1mo") or basis not in ("PRICE_ONLY", "FX_RATE"):
            raise ValueError("Unsupported legacy instrument, frequency or basis")
        observed = _time(entry["observed_for"])
        ingested = _time(entry["ingested_at"])
        if observed > as_of or ingested > as_of or ingested < observed:
            raise ValueError("Future, missing or chronologically inconsistent legacy snapshot")
        key = (code, interval, observed.isoformat())
        if key in seen:
            raise ValueError("Duplicate legacy observation period")
        seen.add(key)
        try:
            value = Decimal(str(entry["close_price"]))
        except (InvalidOperation, ValueError):
            raise ValueError("Invalid close price") from None
        if not value.is_finite() or value <= 0:
            raise ValueError("Close must be positive and finite for this experiment")
        rows.append({"instrument_code": code, "interval_code": interval,
                     "return_basis": basis, "observed_for": observed.isoformat(),
                     "ingested_at": ingested.isoformat(), "close_price": str(value)})
    return sorted(rows, key=lambda r:(r["instrument_code"], r["interval_code"], r["observed_for"]))


def _change(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        raise ValueError("Only positive reference prices")
    return b / a - 1


def _safe_percent(value: float | None) -> float | None:
    return None if value is None else round(value * 100, 4)


def _series_report(code: str, interval: str, rows: list[dict]) -> dict:
    n = len(rows)
    prices = [float(Decimal(r["close_price"])) for r in rows]
    one_step = [_change(prices[i-1], prices[i]) for i in range(1, n)]
    split = max(MIN_LOOKBACK + 1, int(n * 0.65))
    # The first 65% is not used to score outcomes. This is a chronological
    # holdout, not a proof of out-of-sample predictive performance.
    events = []
    baseline = []
    for idx in range(split, n - HORIZON_BARS):
        forward = _change(prices[idx], prices[idx + HORIZON_BARS])
        baseline.append(forward)
        if idx <= MIN_LOOKBACK:
            continue
        # At time idx, only returns strictly BEFORE idx define the norm;
        # today's observed return is the candidate shock.
        reference = one_step[idx-MIN_LOOKBACK-1:idx-1]
        today = one_step[idx-1]
        if len(reference) != MIN_LOOKBACK:
            raise AssertionError("lookback window violates historical chronology")
        volatility = pstdev(reference)
        if volatility < 1e-10:
            continue
        z = (today - mean(reference)) / volatility
        if abs(z) >= ZSCORE_THRESHOLD:
            events.append({
                "observed_for": rows[idx]["observed_for"],
                "signal": "UNUSUAL_ONE_PERIOD_PRICE_MOVE",
                "absolute_zscore": round(abs(z), 4),
                "direction": "UP" if z > 0 else "DOWN",
                "forward_bars_for_retrospective_evaluation": HORIZON_BARS,
                "forward_reference_change_pct": _safe_percent(forward),
                "hypothesis_status": "RETROSPECTIVELY_OBSERVED_NOT_ACTIONABLE",
            })
    event_forward = [e["forward_reference_change_pct"] / 100 for e in events]
    baseline_pct = _safe_percent(mean(baseline)) if baseline else None
    event_pct = _safe_percent(mean(event_forward)) if event_forward else None
    # Never infer statistical significance from overlapping five-bar returns.
    evidence = (
        "EXPLORATORY_ONLY" if len(events) >= MIN_SIGNALS_FOR_COMPARISON
        else "TOO_FEW_SIGNALS_FOR_COMPARISON"
    )
    return {
        "instrument_code":code, "interval_code":interval,
        "legacy_rows":n, "first_observed":rows[0]["observed_for"],
        "last_observed":rows[-1]["observed_for"],
        "last_legacy_ingested_at":max(r["ingested_at"] for r in rows),
        "retrospective_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "holdout_start":rows[split]["observed_for"] if split < n else None,
        "five_bar_baseline_samples":len(baseline),
        "shock_samples":len(events),
        "baseline_average_five_bar_change_pct":baseline_pct,
        "shock_average_five_bar_change_pct":event_pct,
        "vs_unchanged_nominal_reference_pct":event_pct,
        "evidence_label":evidence,
        "signals":events[-15:],
        "interpretation":(
            "Price anomalies are hypotheses to investigate, not evidence for buy/sell."
            " The no-change comparator is a 0% nominal reference, not a cash yield."
        ),
    }


def _btc_eth_divergence(by_series: dict[tuple[str, str], list[dict]]) -> dict:
    """Compare synchronized *USD* BTC/ETH returns; no cross-currency mixing."""
    a = by_series.get(("BTC-USD", "1d"), [])
    b = by_series.get(("ETH-USD", "1d"), [])
    x = {r["observed_for"]:float(Decimal(r["close_price"])) for r in a}
    y = {r["observed_for"]:float(Decimal(r["close_price"])) for r in b}
    days = sorted(set(x).intersection(y))
    if len(days) < 32:
        return {"status":"INSUFFICIENT_MATCHED_HISTORY",
                "matched_observations":len(days), "recent_divergence_events":[]}
    changes = [
        _change(x[days[i-1]], x[days[i]]) -
        _change(y[days[i-1]], y[days[i]])
        for i in range(1,len(days))
    ]
    findings = []
    for i in range(MIN_LOOKBACK+1,len(days)):
        # If there is a missing day on either side we compare LAST matched
        # dates, not an imaginary same-day execution price. Pure observation.
        reference = changes[i-MIN_LOOKBACK-1:i-1]
        gap = changes[i-1]
        sigma = pstdev(reference)
        if sigma >= 1e-10:
            z = (gap-mean(reference))/sigma
            if abs(z)>=ZSCORE_THRESHOLD:
                findings.append({"observed_for":days[i],
                                 "absolute_zscore":round(abs(z),4),
                                 "signal":"USD_CRYPTO_RELATIVE_MOVE_DIVERGENCE",
                                 "hypothesis_status":"INVESTIGATE_ONLY"})
    return {"status":"RETROSPECTIVE_UNVERIFIED_VINTAGE",
            "matched_observations":len(days),
            "recent_divergence_events":findings[-10:],
            "no_arbitrage_or_trade_inference":True}


def analyze(payload: dict) -> dict:
    records = validate_snapshot(payload)
    by_series: dict[tuple[str,str],list[dict]] = defaultdict(list)
    for r in records:
        by_series[(r["instrument_code"],r["interval_code"])].append(r)
    reports = [_series_report(code,interval,group)
               for (code,interval),group in sorted(by_series.items())
               if len(group)>=MIN_LOOKBACK + HORIZON_BARS + 3]
    left_out = sorted(f"{code}/{interval}" for (code,interval),group in by_series.items()
                      if len(group)<MIN_LOOKBACK + HORIZON_BARS + 3)
    digest = hashlib.sha256(_canonical(records).encode("utf-8")).hexdigest()
    return {
        "status":"RETROSPECTIVE_RESEARCH_COMPLETE",
        "as_of":_time(payload["as_of"]).isoformat(),
        "source_vintage":"UNVERIFIED_HISTORICAL_PUBLICATION",
        "data_sha256":digest,
        "price_records":len(records),
        "series_analyzed":len(reports),
        "insufficient_series":left_out,
        "series":reports,
        "cross_market_btc_eth":_btc_eth_divergence(by_series),
        "decision_classification":"INVESTIGATE_OR_OBSERVE_ONLY",
        "virtual_portfolio_changes":0,
        "real_orders":0,
        "database_writes":0,
        "pit_backtest_certified":False,
        "schedule_enabled":False,
        "disclaimer":"A retrospective pattern search, not a prediction or investment advice.",
    }


def markdown_report(result: dict) -> str:
    lines = [
        "# Opportunity Radar — retrospective educational research",
        "", "**Status:** retrospective / historical publication vintages unverified",
        f"**Input fingerprint:** `{result['data_sha256']}`",
        f"**Records:** {result['price_records']}; **analyzed series:** {result['series_analyzed']}",
        "",
        "| Series | Bars | 5-bar holdout windows | Shock events | Evidence |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for s in result["series"]:
        lines.append(f"| {s['instrument_code']} ({s['interval_code']}) | {s['legacy_rows']} "
                     f"| {s['five_bar_baseline_samples']} | {s['shock_samples']} "
                     f"| {s['evidence_label']} |")
    if result["insufficient_series"]:
        lines += ["", "Excluded (too short): " + ", ".join(result["insufficient_series"])]
    lines += [
        "", "## Critical methodological limitations",
        "- Legacy prices were imported later than their market observation dates.",
        "- The original publication/vintage of each historical quote is unverified.",
        "- The holdout uses overlapping future evaluation windows; no p-values, ROI or alpha claims.",
        "- Different currencies, price-only indexes and spot references must not be treated as total-return assets.",
        "- Ranking a historical anomaly is **not** a buy/sell or portfolio change recommendation.",
        "- Benchmark includes unchanged nominal reference (0%) and unconditional five-bar price change.",
        "- All outcomes are retrospective; no broker calls, data writes, fills or live trading.",
        "", "**Decision:** investigate evidence or observe; do not alter portfolio allocations.", "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline retrospective opportunity hypotheses")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", default="artifacts/opportunity-radar")
    args = parser.parse_args()
    try:
        source = Path(args.input)
        if source.stat().st_size > 4_000_000:
            raise ValueError("Snapshot exceeds max size")
        obj = json.loads(source.read_text(encoding="utf-8"))
        outcome = analyze(obj)
        folder = Path(args.out_dir)
        folder.mkdir(parents=True, exist_ok=True)
        (folder/"radar.json").write_text(_canonical(outcome)+"\n",encoding="utf-8")
        (folder/"report.md").write_text(markdown_report(outcome),encoding="utf-8")
        print("OPPORTUNITY_RADAR_RETROSPECTIVE_COMPLETE",
              "records", outcome["price_records"],
              "series", outcome["series_analyzed"],
              "real_orders", 0, "database_writes", 0)
        return 0
    except Exception as exc:
        # File paths, source content and other errors may contain private info.
        print("OPPORTUNITY_RADAR_FAILED: "+type(exc).__name__,file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
