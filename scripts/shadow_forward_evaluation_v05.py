"""A single forward-only evaluation of frozen educational shadow targets.

NO real or paper executions. A forward total-return benchmark observation
can evaluate a previously frozen *hypothetical target*, but the reported
gross/net change is a theoretical reference return, not investor P&L.
Source licences, historical first availability and investability are NOT
certified by JSON manifest self-assertions. No Sharpe, edge or success rate
from fewer than a defensible multi-period out-of-sample sample.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from scripts.shadow_decision_engine_v05 import (
    ASSETS, MODEL_ASSETS, ShadowInputError, _digest, _month,
    _next_month, _positive, _utc
)
D=Decimal
BPS=D("10000")

def _nonnegative(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,str,D)):
        raise ShadowInputError(label+" invalid decimal")
    try:
        out=D(str(value))
    except (InvalidOperation,ValueError) as exc:
        raise ShadowInputError(label+" invalid decimal") from exc
    if not out.is_finite() or out<0 or out>200:
        raise ShadowInputError(label+" outside 0..200bps")
    return out


def evaluate_forward(decision, observation):
    if not isinstance(decision,dict) or not isinstance(observation,dict):
        raise ShadowInputError("forward input requires two JSON documents")
    digest=decision.get("decision_fingerprint_sha256")
    if not isinstance(digest,str) or _digest({k:v for k,v in decision.items()
                                               if k!="decision_fingerprint_sha256"})!=digest:
        raise ShadowInputError("original frozen decision fingerprint mismatch")
    if decision.get("mode")!="EDUCATIONAL_SHADOW_ONLY" or decision.get("policy_version")!="V05_FROZEN_001":
        raise ShadowInputError("shadow-only frozen policy expected")
    if observation.get("mode")!="EDUCATIONAL_FORWARD_REFERENCE_ONLY":
        raise ShadowInputError("no financial account or live trading mode allowed")
    if observation.get("source_vintage") not in (
        "SYNTHETIC_OFFLINE_FIXTURE", "FUTURE_PROSPECTIVE_RESEARCH"):
        raise ShadowInputError("only explicit prospective or synthetic study")
    as_of=_utc(observation.get("as_of_utc"))
    decided_at=_utc(decision.get("as_of_utc"))
    if as_of<=decided_at:
        raise ShadowInputError("forward observation must follow frozen decision")
    if observation["source_vintage"]=="FUTURE_PROSPECTIVE_RESEARCH":
        if as_of > datetime.now(timezone.utc)+timedelta(minutes=5):
            raise ShadowInputError("prospective source cannot be future dated")
    fee=_nonnegative(observation.get("fee_bps"),"fee")
    slip=_nonnegative(observation.get("slippage_bps"),"slippage")
    series=observation.get("series")
    if not isinstance(series,dict) or not set(series).issubset(ASSETS):
        raise ShadowInputError("unapproved forward reference code")

    # Validate the independent forward observations before any model return.
    parsed={}
    for code,item in series.items():
        if not isinstance(item,dict) or set(item)!={
            "observed_for","first_usable_at","month",
            "prior_level_pln","level_pln","raw_sha256",
            "return_basis","quote_currency","instrument_kind",
            "source_status","rights_status",
        }:
            raise ShadowInputError("invalid forward source schema")
        month=_month(item["month"])
        try:
            observed=date.fromisoformat(item["observed_for"])
        except (TypeError,ValueError) as exc:
            raise ShadowInputError("invalid forward observation date") from exc
        first=_utc(item["first_usable_at"])
        if (observed.year,observed.month)!=(month.year,month.month) or observed.day<20:
            raise ShadowInputError("forward month/observation mismatch")
        if first.date()<=observed or first<=decided_at or first>as_of:
            raise ShadowInputError("unavailable forward observation or look-ahead")
        prior=_positive(item["prior_level_pln"])
        current=_positive(item["level_pln"])
        sha=item["raw_sha256"]
        if not isinstance(sha,str) or len(sha)!=64 or not all(c in "0123456789abcdef" for c in sha):
            raise ShadowInputError("raw forward source SHA-256 required")
        if (item["quote_currency"]!="PLN"
            or item["return_basis"]!="TOTAL_RETURN"
            or item["instrument_kind"]!="NON_EXECUTABLE_BENCHMARK"
            or item["source_status"]!="VERIFIED_ORIGINAL"
            or item["rights_status"]!="RESEARCH_USE_DOCUMENTED"):
            raise ShadowInputError("forward input is not declared usable PLN total-return benchmark")
        parsed[code]={"month":month,"observed":observed,"first":first,
                      "prior":prior,"current":current,"sha":sha}
    results={}
    for model in MODEL_ASSETS:
        original=decision.get("model_decisions",{}).get(model)
        if not isinstance(original,dict):
            raise ShadowInputError("missing frozen model")
        if original.get("status")!="VIRTUAL_TARGET_ONLY":
            results[model]={"status":"NOT_EVALUABLE_PREVIOUSLY_HOLD_CASH",
                            "hypothetical_gross_return":None,
                            "hypothetical_net_return_after_assumed_costs":None}
            continue
        evidence=original.get("signal_evidence")
        weights=original.get("target")
        if not isinstance(evidence,dict) or not isinstance(weights,dict):
            raise ShadowInputError("missing frozen target source receipt")
        target_month=_month(evidence.get("decision_month"))
        required=MODEL_ASSETS[model]
        if not set(required).issubset(parsed):
            results[model]={"status":"NOT_EVALUABLE_FORWARD_SERIES_MISSING",
                            "missing":[c for c in required if c not in parsed],
                            "hypothetical_gross_return":None,
                            "hypothetical_net_return_after_assumed_costs":None}
            continue
        if not all(parsed[c]["month"]==_next_month(target_month) for c in required):
            raise ShadowInputError("forward observation must be next completed month")
        if set(weights)!=(set(required)|{"CASH_PLN"}):
            raise ShadowInputError("unexpected frozen weights")
        weight={k:_nonnegative(weights[k],k) for k in weights}
        # A 100% total-weight requirement. _nonnegative uses 200 as an
        # upper bound (bps helper); this separate gate prevents leverage.
        if sum(weight.values())!=D("1") or any(v>1 for v in weight.values()):
            raise ShadowInputError("leverage or incomplete frozen target")
        for code in required:
            baseline=evidence.get("baseline_level_sha256",{}).get(code)
            if _digest({"month":target_month.strftime("%Y-%m"),
                        "level_pln":str(parsed[code]["prior"])})!=baseline:
                raise ShadowInputError("prior frozen level does not match source checkpoint")
        gross=sum((weight[code]*(parsed[code]["current"]/parsed[code]["prior"]-D("1"))
                  for code in required),D("0"))
        # One hypothetical entry friction assumption from a cash start.
        # NOT measured trading costs and NOT evidence fills were possible.
        invested=sum((weight[c] for c in required),D("0"))
        friction=invested*(fee+slip)/BPS
        net=(D("1")+gross)*(D("1")-friction)-D("1")
        results[model]={
            "status":"ONE_FORWARD_REFERENCE_PERIOD_RESEARCH_ONLY",
            "reference_month":_next_month(target_month).strftime("%Y-%m"),
            "hypothetical_gross_return":format(gross,"f"),
            "hypothetical_net_return_after_assumed_costs":format(net,"f"),
            "assumed_fee_bps":str(fee),
            "assumed_slippage_bps":str(slip),
            "source_sha256":{c:parsed[c]["sha"] for c in required},
            "benchmark_is_not_an_executable_security":True,
            "real_fills":0,
        }
    out={
        "status":"FORWARD_SHADOW_REFERENCE_DIAGNOSTIC_NOT_INVESTOR_RETURN",
        "source_vintage":observation["source_vintage"],
        "decision_fingerprint_sha256":digest,
        "reference_evaluated_at":as_of.isoformat(),
        "results":results,
        "periods_evaluated_per_model_max":1,
        "risk_adjusted_return_estimate":None,
        "sharpe":None,"max_drawdown":None,
        "statistical_edge_proven":False,
        "historical_pit_certified":False,
        "investable_execution_price_verified":False,
        "source_rights_independently_certified":False,
        "transactions":0,"paper_fills":0,"orders_sent":0,"database_writes":0,
    }
    out["receipt_sha256"]=_digest(out)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--decision",type=Path,required=True)
    p.add_argument("--forward-reference",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    out=evaluate_forward(
        json.loads(args.decision.read_text(encoding="utf-8")),
        json.loads(args.forward_reference.read_text(encoding="utf-8"))
    )
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("ISL_SHADOW_FORWARD_V05="+json.dumps(out,sort_keys=True,separators=(",",":")))


if __name__=="__main__":
    main()
