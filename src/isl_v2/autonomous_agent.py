"""Deterministic autonomous research agent. Educational simulations ONLY.

Stages: point-in-time evidence -> falsifiable research hypothesis -> paper-only
portfolio intent -> immutable audit payload. There are no live trading APIs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .provenance import fingerprint, select_asof, utc

MODELS: dict[str, dict[str, Decimal]] = {
    "M1_GLOBAL_EQ": {"EQUITY_TR_PLN": Decimal("1")},
    "M2_DIVERSIFIED": {"EQUITY_TR_PLN": Decimal("0.6"), "BONDS_TR_PLN": Decimal("0.3"), "GOLD_TR_PLN": Decimal("0.1")},
    "M3_TACTICAL": {"EQUITY_TR_PLN": Decimal("0.6"), "BONDS_TR_PLN": Decimal("0.3"), "GOLD_TR_PLN": Decimal("0.1")},
}
WATCH = ("BRENT_EIA_USD_BBL", "COPPER_WB_USD_T")


def _date(s: str):
    return utc(s).date()


def _latest(prices: list[dict[str, Any]], code: str) -> list[dict[str, Any]]:
    return sorted((r for r in prices if r["instrument_code"] == code), key=lambda r: r["observed_for"])


def _paper_decisions(prices: list[dict[str, Any]], as_of: str, requirements: dict[str, Any]) -> list[dict[str, Any]]:
    """Fail closed until verified investable total-return levels AND later fill quotes.

    PRICE_ONLY and World Bank monthly commodity averages NEVER authorize fills.
    Rules produce a virtual target intent; a separate future-time fill processor
    must use a truly available future quote and verified fees. This agent does
    not implement fill processing, deliberately.
    """
    out = []
    for model, targets in MODELS.items():
        missing = []
        for code in targets:
            series = _latest(prices, code)
            cfg = requirements.get(code, {})
            if len(series) < 4 or cfg.get("basis") != "TOTAL_RETURN_INDEX" or cfg.get("currency") != "PLN":
                missing.append(code)
            elif any(row["interval_code"] != "1mo" for row in series[-4:]):
                missing.append(code)
        # Model 3 also needs four consecutive, already-public past monthly equity observations.
        decision = "HOLD_CASH" if missing else "PAPER_TARGET_INTENT"
        weights = {} if missing else {k: str(v) for k, v in targets.items()}
        if decision == "PAPER_TARGET_INTENT" and model == "M3_TACTICAL":
            eq = _latest(prices, "EQUITY_TR_PLN")
            vals = [Decimal(x["price_value"]) for x in eq[-4:]]
            if vals[-1] <= vals[0]:
                weights["EQUITY_TR_PLN"] = "0.3"
                weights["PLN_CASH"] = "0.3"
        out.append({"model_code": model, "decision_type": decision,
                    "target_weights": weights, "missing_data": missing,
                    "explanation": "Required published PLN total-return indexes unavailable; retain hypothetical cash"
                    if missing else "Research-only target, no execution or filled prices; execution must wait for future priced data",
                    "signal_cutoff": as_of, "paper_only": True,
                    "no_live_execution": True})
    return out


def _hypotheses(prices: list[dict[str, Any]], as_of: str) -> list[dict[str, Any]]:
    """Hypotheses are *tests*, not validated predictions or portfolio decisions.

    Only compare three prior observations of the same frequency; this is a
    screening hypothesis without any numerical future price target.
    """
    out = []
    for code in WATCH:
        history = _latest(prices, code)
        if len(history) < 13:
            continue
        recent = history[-4:]
        if len({r["interval_code"] for r in recent}) != 1:
            continue
        # Consecutive observations are tested for month data; daily datasets
        # need a separate trading-calendar validator (not yet implemented).
        if recent[-1]["interval_code"] != "1mo":
            continue
        vals = [Decimal(r["price_value"]) for r in recent]
        direction = "UP" if vals[-1] > vals[0] else "NON_UP"
        key = fingerprint({"instrument": code, "observation_date": recent[-1]["observed_for"], "method": "research_momentum_3m_v1"})
        out.append({"hypothesis_key": key, "instrument_code": code,
                    "as_of": as_of, "observation_date": recent[-1]["observed_for"],
                    "reference_value": str(vals[-1]), "direction": direction,
                    "statement": "Test whether the next fully published monthly average follows the sign of the prior three months",
                    "falsification": "Compare the next *published* monthly observation with the recorded reference; mark incorrect if its direction differs",
                    "status": "RESEARCH_ONLY_UNVALIDATED", "source_fingerprint": fingerprint(recent),
                    "paper_only": True})
    return out


def run_cycle(job: dict[str, Any]) -> dict[str, Any]:
    """Pure function; suitable for retry and deterministic CI. No side effects."""
    as_of = job["as_of"]
    utc(as_of)
    if not isinstance(job.get("observations"), list):
        raise ValueError("observations list is required")
    if not job.get("run_key") or not job.get("code_version"):
        raise ValueError("run_key and code_version are required")
    prices = select_asof(job["observations"], as_of)
    decisions = _paper_decisions(prices, as_of, job.get("requirements", {}))
    hypotheses = _hypotheses(prices, as_of)
    # Never convert an asset reference price into an executable simulated quote.
    run_id = fingerprint({"run_key": job["run_key"], "as_of": as_of,
                          "observations": job["observations"], "version": job["code_version"]})
    return {"run_key": job["run_key"], "input_sha256": run_id,
            "as_of": as_of, "code_version": job["code_version"],
            "cycle_status": "COMPLETED_RESEARCH_ONLY", "observations_available": len(prices),
            "hypotheses": hypotheses, "paper_decisions": decisions,
            "paper_fills_created": 0, "real_orders_created": 0,
            "reason_no_fills": "No verified next-available execution quotes and fee schedule",
            "no_live_execution": True}


def evaluate_hypothesis(hypothesis: dict[str, Any], observations: list[dict[str, Any]], evaluation_as_of: str) -> dict[str, Any]:
    """Resolve only with later *published* observation, never today's unfinished bar.

    This function does not mutate the original hypothesis.
    """
    price_rows = select_asof(observations, evaluation_as_of)
    later = [r for r in _latest(price_rows, hypothesis["instrument_code"])
             if r["observed_for"] > hypothesis["observation_date"] and r["interval_code"] == "1mo"]
    if not later:
        return {"status": "PENDING", "hypothesis_key": hypothesis["hypothesis_key"]}
    actual = Decimal(later[0]["price_value"])
    reference = Decimal(hypothesis["reference_value"])
    hit = ((actual > reference) == (hypothesis["direction"] == "UP"))
    return {"status": "EVALUATED", "hypothesis_key": hypothesis["hypothesis_key"],
            "evaluated_as_of": evaluation_as_of, "actual_observation": later[0]["observed_for"],
            "actual_value": str(actual), "reference_value": str(reference),
            "direction_correct": hit, "benchmark": "PERSISTENCE_SIGN_TEST_ONLY",
            "paper_only": True}
