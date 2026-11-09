"""Investment Strategy Lab: deterministic, non-executable shadow decision gate.

This is NOT a broker, trading bot, production readiness certificate, or
backtest. A signal describes a hypothetical TARGET for a future paper
experiment, never an executed position or a paper fill.

The engine is deliberately usable with partial real source coverage.
Missing global equity does not prevent daily receipt generation; it
produces HOLD_CASH with machine-readable reasons instead of inventing
returns. Source rights and first publication claims in submitted manifests
remain declarations, not independent authorization or PIT attestation.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

EQUITY = "GLOBAL_EQUITY_TR_PLN"
BONDS = "PL_BONDS_TR_PLN"
GOLD = "GOLD_TR_PLN"
ASSETS = (EQUITY, BONDS, GOLD)
MODEL_ASSETS = {
    "M1_GLOBAL_EQ": (EQUITY,),
    "M2_DIVERSIFIED": ASSETS,
    "M3_TACTICAL": ASSETS,
}
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
MIN_HISTORY = 36
MAX_HISTORY = 120
MAX_LAST_QUOTE_AGE_DAYS = 45
D = Decimal

class ShadowInputError(ValueError):
    pass


def _utc(value):
    if not isinstance(value, str):
        raise ShadowInputError("UTC datetime string required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ShadowInputError("invalid UTC datetime") from exc
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ShadowInputError("UTC offset required")
    return dt.astimezone(timezone.utc)


def _positive(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, D)):
        raise ShadowInputError("positive decimal string required")
    try:
        parsed = D(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ShadowInputError("invalid decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ShadowInputError("positive finite decimal required")
    return parsed


def _month(value):
    if not isinstance(value, str) or not MONTH_RE.fullmatch(value):
        raise ShadowInputError("invalid YYYY-MM month")
    try:
        return date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise ShadowInputError("invalid month") from exc


def _next_month(day):
    return date(day.year + (day.month == 12), 1 if day.month == 12 else day.month + 1, 1)


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _source_check(code, obj, as_of):
    if not isinstance(obj, dict) or set(obj) != {
        "series_code", "source_url", "source_sha256", "source_status",
        "rights_status", "quote_currency", "return_basis", "instrument_kind",
        "retrieved_at", "observations",
    }:
        raise ShadowInputError("invalid source envelope")
    if obj["series_code"] != code:
        raise ShadowInputError("source code mismatch")
    url = urlsplit(obj["source_url"])
    if (url.scheme != "https" or not url.hostname or url.username
            or url.password or url.fragment):
        raise ShadowInputError("https provenance URL required")
    if not isinstance(obj["source_sha256"], str) or not HEX.fullmatch(obj["source_sha256"]):
        raise ShadowInputError("raw source sha256 receipt required")
    retrieved = _utc(obj["retrieved_at"])
    if retrieved > as_of:
        raise ShadowInputError("future retrieval would be look-ahead")
    if obj["source_status"] not in ("VERIFIED_ORIGINAL", "CANDIDATE", "UNAVAILABLE"):
        raise ShadowInputError("invalid source verification status")
    if obj["rights_status"] not in ("RESEARCH_USE_DOCUMENTED", "UNVERIFIED"):
        raise ShadowInputError("invalid source rights status")
    if obj["return_basis"] not in ("TOTAL_RETURN", "PRICE_ONLY", "FX_RATE", "BOND_TOTAL_RETURN_BENCHMARK_INDEX", "NAV_REFERENCE"):
        raise ShadowInputError("invalid return basis")
    if obj["instrument_kind"] not in ("NON_EXECUTABLE_BENCHMARK", "NON_TRADABLE_INDEX", "NON_EXECUTABLE_NAV_REFERENCE", "REFERENCE_QUOTE"):
        raise ShadowInputError("invalid instrument kind")
    if obj["quote_currency"] != "PLN":
        # USD sources must first be independently converted to PLN.
        raise ShadowInputError("PLN reference is mandatory")
    rows = obj["observations"]
    if not isinstance(rows, list) or len(rows) > MAX_HISTORY:
        raise ShadowInputError("invalid bounded observation count")
    parsed = []
    previous = None
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"month", "observed_for", "level_pln", "first_usable_at"}:
            raise ShadowInputError("invalid monthly observation schema")
        ym = _month(row["month"])
        if previous is not None and ym != _next_month(previous):
            raise ShadowInputError("duplicate or missing month")
        try:
            observed = date.fromisoformat(row["observed_for"])
        except (TypeError, ValueError) as exc:
            raise ShadowInputError("invalid observed_for") from exc
        if (observed.year, observed.month) != (ym.year, ym.month) or observed.day < 20:
            raise ShadowInputError("monthly observation date outside late month")
        available = _utc(row["first_usable_at"])
        if available.date() <= observed or available > as_of:
            raise ShadowInputError("first_usable_at look-ahead or unverifiable timestamp")
        level = _positive(row["level_pln"])
        parsed.append((ym, observed, available, level))
        previous = ym
    reasons = []
    if obj["source_status"] != "VERIFIED_ORIGINAL":
        reasons.append("ORIGINAL_SOURCE_UNVERIFIED")
    if obj["rights_status"] != "RESEARCH_USE_DOCUMENTED":
        reasons.append("RIGHTS_UNVERIFIED")
    if obj["return_basis"] != "TOTAL_RETURN" or obj["instrument_kind"] != "NON_EXECUTABLE_BENCHMARK":
        reasons.append("NOT_PLN_TOTAL_RETURN_BENCHMARK")
    if len(parsed) < MIN_HISTORY:
        reasons.append("INSUFFICIENT_CONSECUTIVE_MONTHS")
    if parsed and (as_of.date() - parsed[-1][1]).days > MAX_LAST_QUOTE_AGE_DAYS:
        reasons.append("SOURCE_STALE")
    if not parsed:
        reasons.append("NO_OBSERVATIONS")
    return {"status": "RESEARCH_ELIGIBLE_DECLARED" if not reasons else "SOURCE_BLOCKED",
            "reasons": reasons, "months": len(parsed),
            "last_month": parsed[-1][0].strftime("%Y-%m") if parsed else None,
            "last_date": parsed[-1][1].isoformat() if parsed else None,
            "raw_sha256": obj["source_sha256"],
            "license_authorization_independently_certified": False}, parsed


def evaluate(payload):
    if not isinstance(payload, dict) or set(payload) != {"mode", "as_of_utc", "series", "policy_version"}:
        raise ShadowInputError("expected minimal shadow-only payload")
    if payload["mode"] != "EDUCATIONAL_SHADOW_ONLY" or payload["policy_version"] != "V05_FROZEN_001":
        raise ShadowInputError("frozen shadow-only policy required")
    as_of = _utc(payload["as_of_utc"])
    sources = payload["series"]
    if not isinstance(sources, dict) or not set(sources).issubset(ASSETS):
        raise ShadowInputError("unknown series cannot be promoted")
    checks = {}
    data = {}
    for code in ASSETS:
        if code not in sources:
            checks[code] = {
                "status": "SOURCE_MISSING", "reasons": ["SOURCE_MISSING"],
                "months": 0, "raw_sha256": None,
                "license_authorization_independently_certified": False,
            }
            continue
        checks[code], data[code] = _source_check(code, sources[code], as_of)
    decisions = {}
    for model, required in MODEL_ASSETS.items():
        blockers = {code: checks[code]["reasons"] for code in required
                    if checks[code]["status"] != "RESEARCH_ELIGIBLE_DECLARED"}
        if not blockers:
            months = {data[code][-1][0] for code in required}
            if len(months) != 1:
                blockers = {"CALENDAR": ["SOURCE_MONTHS_NOT_ALIGNED"]}
        if blockers:
            decisions[model] = {
                "status": "HOLD_CASH", "reason": "SOURCE_GATES_BLOCKED",
                "blockers": blockers, "target": {"CASH_PLN": "1"},
                "signal_evidence": None,
            }
            continue
        if model == "M1_GLOBAL_EQ":
            weights = {EQUITY: "1", "CASH_PLN": "0"}
            signal = "PASSIVE_GLOBAL_EQUITY_SHADOW_TARGET"
        elif model == "M2_DIVERSIFIED":
            weights = {EQUITY: "0.6", BONDS: "0.3", GOLD: "0.1", "CASH_PLN": "0"}
            signal = "FROZEN_DIVERSIFIED_SHADOW_TARGET"
        else:
            observations = data[EQUITY]
            current, lagged = observations[-1][3], observations[-4][3]
            if current > lagged:
                weights = {EQUITY: "0.6", BONDS: "0.3", GOLD: "0.1", "CASH_PLN": "0"}
                signal = "MOMENTUM_3M_RISK_ON"
            else:
                weights = {EQUITY: "0.3", BONDS: "0.3", GOLD: "0.1", "CASH_PLN": "0.3"}
                signal = "MOMENTUM_3M_RISK_OFF"
        decisions[model] = {
            "status": "VIRTUAL_TARGET_ONLY", "reason": signal,
            "blockers": {}, "target": weights,
            "signal_evidence": {
                "decision_month": next(iter({data[code][-1][0] for code in required})).strftime("%Y-%m"),
                "observation_dates": {c:data[c][-1][1].isoformat() for c in required},
                "source_sha256": {c:checks[c]["raw_sha256"] for c in required},
                "baseline_level_sha256": {c:_digest({"month":data[c][-1][0].strftime("%Y-%m"),"level_pln":str(data[c][-1][3])}) for c in required},
                "assumptions_are_not_independent_proof": True,
            },
        }
    result = {
        "mode": "EDUCATIONAL_SHADOW_ONLY",
        "as_of_utc": as_of.isoformat(),
        "policy_version": "V05_FROZEN_001",
        "source_readiness": checks,
        "model_decisions": decisions,
        "eligible_models": [m for m in MODEL_ASSETS if decisions[m]["status"]=="VIRTUAL_TARGET_ONLY"],
        "historical_pit_certified": False,
        "provider_license_independently_certified": False,
        "future_oos_returns_observed": False,
        "profitability_proven": False,
        "is_backtest": False,
        "orders_sent": 0, "paper_fills": 0, "database_writes": 0,
        "financial_operations": 0,
    }
    result["decision_fingerprint_sha256"] = _digest(result)
    return result


def from_reference_archive(source):
    """Real research archive: audit completeness without promoting gold/TBSP to asset TR."""
    from scripts.reference_archive_calendar_v04 import _digest as digest
    if not isinstance(source, dict) or source.get("status") != "SAME_CALENDAR_DATE_REFERENCE_NOT_PIT_OR_EXECUTABLE":
        raise ShadowInputError("not accepted reference-alignment format")
    fingerprint = source.get("evidence_sha256")
    if not isinstance(fingerprint, str) or not HEX.fullmatch(fingerprint):
        raise ShadowInputError("missing archive fingerprint")
    if digest({k:v for k,v in source.items() if k!="evidence_sha256"}) != fingerprint:
        raise ShadowInputError("reference source fingerprint mismatch")
    rows = source.get("timeline")
    if (not isinstance(rows,list) or len(rows)<36 or len(rows)>120 or
            source.get("months") != len(rows) or
            not all(isinstance(r,dict) and r.get("same_calendar_date") is True for r in rows)):
        raise ShadowInputError("reference archive history insufficient or unaligned")
    if source.get("financial_operations") != 0 or source.get("paper_events_created") != 0:
        raise ShadowInputError("unexpected source side effects")
    return {
        "status": "SHADOW_REFERENCE_OBSERVATION_ONLY",
        "source_archive_sha256": fingerprint,
        "reference_months": len(rows),
        "first_month": source["first_month"],
        "last_month": source["last_month"],
        "observed_reference_families": {
            "NBP_GOLD_PLN_G": "PRICE_ONLY_NOT_TOTAL_RETURN",
            "NBP_USDPLN": "FX_RATE_NOT_TOTAL_RETURN",
            "BONDSPOT_TBSP_INDEX": "NON_TRADABLE_BOND_BENCHMARK",
        },
        "missing_model_sources": [EQUITY, BONDS, GOLD],
        "model_decisions": {model:{"status":"HOLD_CASH", "reason":"NO_QUALIFIED_TOTAL_RETURN_SERIES"}
                            for model in MODEL_ASSETS},
        "historical_pit_certified": False,
        "future_oos_returns_observed": False,
        "orders_sent": 0,"paper_fills": 0,"database_writes":0,
        "financial_operations":0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path)
    group.add_argument("--reference-archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args=parser.parse_args()
    doc=json.loads((args.input or args.reference_archive).read_text(encoding="utf-8"))
    result=evaluate(doc) if args.input else from_reference_archive(doc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    print("ISL_SHADOW_V05="+json.dumps(result, separators=(",",":"),sort_keys=True))


if __name__=="__main__":
    main()
