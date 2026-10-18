"""Evidence ledger for the retrospective *educational* opportunity radar.

Classifies historical questions worth investigating, never financial orders.
A high score prioritizes research and cannot authorize simulated allocation
changes; missing vintage/benchmark evidence always fails closed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ALLOWED_DECISIONS = ("OBSERVE", "INVESTIGATE_RESEARCH_ONLY", "INSUFFICIENT_EVIDENCE")
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
    if not isinstance(radar.get("data_sha256"),str) or len(radar["data_sha256"]) != 64:
        raise ValueError("Missing research provenance fingerprint")
    return series


def make_ledger(radar: dict) -> dict:
    series = _validated_radar(radar)
    questions = []
    for entry in series:
        name = entry["instrument_code"]
        interval = entry["interval_code"]
        count = entry["shock_samples"]
        samples = entry["five_bar_baseline_samples"]
        if not isinstance(name,str) or interval not in ("1d","1mo"):
            raise ValueError("Unexpected market series")
        if (type(count) is not int or count < 0
                or type(samples) is not int or samples < 0 or count > samples):
            raise ValueError("Invalid evidence size")
        adequate = count >= MIN_FLAGS and samples >= MIN_HOLDOUT
        decision = "INVESTIGATE_RESEARCH_ONLY" if adequate else "INSUFFICIENT_EVIDENCE"
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
        if not adequate:
            reasons_against.append("Insufficient independent anomalies or comparison windows")
        questions.append({
            "instrument_code":name,
            "interval_code":interval,
            "research_priority": "EVALUATE_EVIDENCE" if adequate else "COLLECT_MORE_EVIDENCE",
            "educational_decision":decision,
            "observed_outliers":count,
            "evaluation_windows":samples,
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
