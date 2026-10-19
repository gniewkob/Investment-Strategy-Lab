"""Evidence ledger for the retrospective *educational* opportunity radar.

Classifies historical questions worth investigating, never financial orders.
A high score prioritizes research and cannot authorize simulated allocation
changes; missing vintage/benchmark evidence always fails closed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys

from scripts.opportunity_radar import SUPPORTED

ALLOWED_DECISIONS = ("OBSERVE", "INVESTIGATE_RESEARCH_ONLY", "INSUFFICIENT_EVIDENCE", "DATA_QUALITY_BLOCKED")
REQUIRED_VINTAGE = "UNVERIFIED_HISTORICAL_PUBLICATION"
REQUIRED_STATUS = "RETROSPECTIVE_RESEARCH_COMPLETE"
MIN_FLAGS = 5
MIN_HOLDOUT = 60
PAPER_MODELS = ("M1_GLOBAL_EQ", "M2_DIVERSIFIED", "M3_TACTICAL")


def _validated_radar(radar: dict) -> list[dict]:
    if not isinstance(radar, dict):
        raise ValueError("Research result must be an object")
    if (radar.get("status") != REQUIRED_STATUS
            or radar.get("source_vintage") != REQUIRED_VINTAGE
            or radar.get("pit_backtest_certified") is not False
            or radar.get("real_orders") != 0
            or radar.get("database_writes") != 0
            or radar.get("virtual_portfolio_changes") != 0
            or radar.get("decision_classification") != "INVESTIGATE_OR_OBSERVE_ONLY"):
        raise ValueError("Non-retrospective or trade-authorizing input rejected")
    series = radar.get("series")
    if not isinstance(series, list) or len(series) > 30:
        raise ValueError("Series collection invalid")
    if not isinstance(radar.get("data_sha256"),str) or not re.fullmatch(r"[a-f0-9]{64}",radar["data_sha256"]):
        raise ValueError("Missing research provenance fingerprint")
    return series


def _verified_robustness(radar: dict, robustness: dict | None) -> dict:
    """Require same input fingerprint; never let unaudited diagnostics promote."""
    if robustness is None:
        return {}
    if (not isinstance(robustness, dict)
            or robustness.get("status") != "NONOVERLAPPING_RESEARCH_DIAGNOSTIC_ONLY"
            or robustness.get("source_vintage") != REQUIRED_VINTAGE
            or robustness.get("source_radar_sha256") != radar["data_sha256"]
            or robustness.get("real_orders") != 0
            or robustness.get("virtual_portfolio_changes") != 0
            or robustness.get("causal_predictive_advantage_established") is not False):
        raise ValueError("Invalid independent-window evidence contract")
    series = robustness.get("series")
    if not isinstance(series, list):
        raise ValueError("Missing independent-window series")
    by_key = {}
    for entry in series:
        if not isinstance(entry, dict):
            raise ValueError("Bad independent-window evidence record")
        key=(entry.get("instrument_code"),entry.get("interval_code"))
        samples=entry.get("nonoverlapping_shock_events")
        baseline=entry.get("baseline_grid_independent_windows")
        if (key in by_key or key[0] not in SUPPORTED
                or key[1] not in ("1d","1mo")
                or type(samples) is not int or samples < 0
                or type(baseline) is not int or baseline < 0):
            raise ValueError("Invalid independent-window series")
        by_key[key]=entry
    return by_key


def _verified_quality(radar: dict, quality: dict | None) -> dict:
    """Fail closed on missing or mismatched reference-quality evidence."""
    if quality is None:
        return {}
    if (not isinstance(quality, dict)
            or quality.get("status") != "REFERENCE_DATA_QUALITY_RESEARCH_ONLY"
            or quality.get("source_vintage") != REQUIRED_VINTAGE
            or quality.get("source_radar_sha256") != radar["data_sha256"]
            or quality.get("historical_release_dates_verified") is not False
            or quality.get("prediction_or_trading_authorized") is not False
            or quality.get("virtual_portfolio_changes") != 0
            or quality.get("database_writes") != 0
            or quality.get("real_orders") != 0):
        raise ValueError("Quality evidence must match research fingerprint")
    series = quality.get("series")
    if not isinstance(series, list):
        raise ValueError("Missing quality series")
    by_key = {}
    for row in series:
        if not isinstance(row, dict):
            raise ValueError("Invalid quality series")
        key = (row.get("instrument_code"), row.get("interval_code"))
        if (key in by_key or key[0] not in SUPPORTED or key[1] not in ("1d", "1mo")
                or row.get("quality_gate") not in ("REVIEW_ONLY", "BLOCK_RESEARCH_PROMOTION")
                or not isinstance(row.get("warning_codes"), list)
                or row.get("historical_publication_verified") is not False):
            raise ValueError("Invalid quality classification")
        if (row["quality_gate"] == "BLOCK_RESEARCH_PROMOTION") != bool(row["warning_codes"]):
            raise ValueError("Quality flags inconsistent with gate")
        by_key[key] = row
    return by_key


def make_ledger(radar: dict, robustness: dict | None = None,
                quality: dict | None = None) -> dict:
    series = _validated_radar(radar)
    checked = _verified_robustness(radar, robustness)
    quality_checked = _verified_quality(radar, quality)
    if quality is not None and any((x["instrument_code"], x["interval_code"]) not in quality_checked
                                   for x in series):
        raise ValueError("Quality gate missing an analyzed reference series")
    questions = []
    for entry in series:
        if not isinstance(entry, dict):
            raise ValueError("Unexpected evidence record")
        name = entry["instrument_code"]
        interval = entry["interval_code"]
        count = entry["shock_samples"]
        samples = entry["five_bar_baseline_samples"]
        if name not in SUPPORTED or interval not in ("1d","1mo"):
            raise ValueError("Unexpected market series")
        if (type(count) is not int or count < 0
                or type(samples) is not int or samples < 0 or count > samples):
            raise ValueError("Invalid evidence size")
        independent = checked.get((name, interval))
        robust_samples = (independent["nonoverlapping_shock_events"]
                          if independent else None)
        grid = (independent["baseline_grid_independent_windows"]
                if independent else None)
        if robustness is not None and independent is not None:
            if robust_samples > count:
                raise ValueError("Independent events exceed detected anomaly candidates")
        adequate = count >= MIN_FLAGS and samples >= MIN_HOLDOUT
        if robustness is not None:
            adequate = (adequate and independent is not None
                        and robust_samples >= MIN_FLAGS and grid >= 12)
        quality_row = quality_checked.get((name, interval))
        blocked = (quality_row is not None and
                   quality_row["quality_gate"] == "BLOCK_RESEARCH_PROMOTION")
        decision = ("DATA_QUALITY_BLOCKED" if blocked else
                    "INVESTIGATE_RESEARCH_ONLY" if adequate else "INSUFFICIENT_EVIDENCE")
        reasons_for = [
            f"{count} historical outlier events observed in {samples} evaluation windows",
            "Signal is computed from strictly lagged reference-price observations",
        ] if count else ["No qualifying historical outlier in evaluated windows"]
        reasons_against = [
            "Original historical publication vintages not verified",
            "Overlapping forward windows create correlated observations",
            "Conditional price-change differences do not demonstrate predictive skill",
            "Source price quotes are not executable return-inclusive instruments",
        ]
        if blocked:
            reasons_against.append("Research promotion blocked by data-quality flags: " +
                                   ", ".join(quality_row["warning_codes"]))
        if robustness is not None and not adequate:
            reasons_against.append(
                "Non-overlapping event count or pre-registered baseline grid below exploratory gate"
            )
        if not adequate:
            reasons_against.append("Insufficient independent anomalies or comparison windows")
        questions.append({
            "instrument_code":name,
            "interval_code":interval,
            "research_priority": ("RESOLVE_DATA_QUALITY" if blocked else
                                  "EVALUATE_EVIDENCE" if adequate else "COLLECT_MORE_EVIDENCE"),
            "quality_gate": quality_row["quality_gate"] if quality_row else "NOT_CHECKED",
            "data_quality_warning_codes": quality_row["warning_codes"] if quality_row else [],
            "educational_decision":decision,
            "observed_outliers":count,
            "evaluation_windows":samples,
            "nonoverlapping_events":robust_samples,
            "nonoverlap_baseline_windows":grid,
            "overlap_screened":robustness is not None,
            "evidence_for":reasons_for,
            "evidence_against":reasons_against,
            "unconditional_mean_5bar_price_pct":entry.get("baseline_average_five_bar_change_pct"),
            "conditional_mean_5bar_price_pct":entry.get("shock_average_five_bar_change_pct"),
            "unchanged_nominal_reference_pct":0,
            "counterfactual_quality":"NOT_CAUSAL_NOT_EXECUTABLE",
            "missing_prerequisites":[
                "Verified historical release vintages",
                "Non-overlapping evaluation and uncertainty intervals",
                "Investable total-return series, costs and PLN FX if portfolio comparison intended",
                "Independent held-out research validation",
            ],
            "change_virtual_allocation":False,
            "trade_or_purchase_allowed":False,
        })
    research_interest = sum(q["educational_decision"]=="INVESTIGATE_RESEARCH_ONLY"
                            for q in questions)
    return {
        "status":"EVIDENCE_LEDGER_RESEARCH_ONLY",
        "source_radar_sha256":radar["data_sha256"],
        "vintage_status":REQUIRED_VINTAGE,
        "tracked_questions":len(questions),
        "nonoverlap_evidence_considered":robustness is not None,
        "reference_data_quality_considered":quality is not None,
        "questions_blocked_by_data_quality":sum(q["educational_decision"] == "DATA_QUALITY_BLOCKED" for q in questions),
        "questions_for_independent_review":research_interest,
        "questions":questions,
        "paper_portfolio_decisions":[
            {"model_code":code, "decision":"HOLD_NO_CHANGE",
             "reason":"Hypothesis screen alone does not validate portfolio changes; total-return prerequisites missing",
             "orders":0}
            for code in PAPER_MODELS
        ],
        "portfolio_reallocations":0,
        "real_orders":0,
        "database_writes":0,
        "automated_execution":False,
        "schedule_enabled":False,
    }


def markdown_report(outcome:dict) -> str:
    lines=[
        "# Decision Evidence Ledger — educational, retrospective",
        "",
        "Historical signals are questions for investigation, **not trade recommendations**.",
        f"Radar fingerprint: \`{outcome['source_radar_sha256']}\`",
        f"Questions: {outcome['tracked_questions']} ; independent-review candidates: {outcome['questions_for_independent_review']}",
        "",
        "| Reference series | Historical anomalies | Research decision |",
        "| --- | ---: | --- |",
    ]
    for q in outcome["questions"]:
        lines.append(f"| {q['instrument_code']} ({q['interval_code']}) "
                     f"| {q['observed_outliers']} | {q['educational_decision']} |")
    lines += ["", "## Reasons to withhold virtual allocation changes",
              "- Historical source publication time remains unverified.",
              "- Benchmark comparisons are descriptive and may have overlapping future windows.",
              "- No investable total-return index, transaction costs or reliable forward fills are established.",
              "- All M1/M2/M3 models remain HOLD_NO_CHANGE.",
              "", "No trades, transfers, brokerage APIs or automatic schedule.", ""]
    return "\n".join(lines)


def main() -> int:
    ap=argparse.ArgumentParser(description="Explain retrospective research questions")
    ap.add_argument("--radar-input",required=True)
    ap.add_argument("--out-dir",default="artifacts/evidence-ledger")
    args=ap.parse_args()
    try:
        path=Path(args.radar_input)
        if path.stat().st_size > 1_000_000:
            raise ValueError("Oversized research input")
        original=json.loads(path.read_text(encoding="utf-8"))
        ledger=make_ledger(original)
        out=Path(args.out_dir)
        out.mkdir(parents=True,exist_ok=True)
        (out/"decision_ledger.json").write_text(
            json.dumps(ledger,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
            encoding="utf-8")
        (out/"decision_ledger.md").write_text(markdown_report(ledger),encoding="utf-8")
        print("RESEARCH_EVIDENCE_LEDGER_READY",
              "questions",ledger["tracked_questions"],
              "review",ledger["questions_for_independent_review"],
              "portfolio_reallocations",0,"real_orders",0)
        return 0
    except Exception as exc:
        print("RESEARCH_EVIDENCE_LEDGER_FAILED: "+type(exc).__name__,file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
