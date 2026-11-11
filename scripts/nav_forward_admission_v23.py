"""v0.23 admission checks for prospective, non-executable NAV/PLN references.

Default: validate pinned pre-December freeze and report PENDING. Optional
candidate: independently hash-check original new USD NAV export metadata,
exact-date NBP rate evidence, and enforce strict later-month chronology.
This remains self-reported source metadata until external retrieval evidence
is reviewed; no model M1 promotion, backtest, or trades.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from scripts.nav_forward_freeze_v22 import verify_pending
from scripts.reference_archive_calendar_v04 import _digest

SCHEMA="ISL_NAV_FORWARD_ADMISSION_V23_001"
ANCHORED_FREEZE_SHA="3b8aca44ffa6aa72bf2d3a0b5d49102f0dd857d11191dc10e7d21b5051e704a2"
ANCHOR_URL="https://github.com/gniewkob/Investment-Strategy-Lab/issues/97#issuecomment-6712908994"
HEX=re.compile(r"^[0-9a-f]{64}$")
D=Decimal


def _utc(value):
    if not isinstance(value,str):
        raise ValueError("explicit UTC timestamp required")
    try:
        x=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as e:
        raise ValueError("invalid UTC timestamp") from e
    if x.tzinfo is None or x.utcoffset()!=timedelta(0):
        raise ValueError("UTC timestamp required")
    return x.astimezone(timezone.utc)


def _positive(value):
    if isinstance(value,bool) or not isinstance(value,str) or value!=value.strip():
        raise ValueError("decimal string required")
    try:
        x=D(value)
    except (InvalidOperation,ValueError) as e:
        raise ValueError("invalid decimal") from e
    if not x.is_finite() or x<=0:
        raise ValueError("positive finite reference required")
    return x


def admission(frozen, candidate=None, *, clock=lambda: datetime.now(timezone.utc)):
    pending=verify_pending(frozen,clock=clock)
    if pending["freeze_receipt_sha256"]!=ANCHORED_FREEZE_SHA:
        raise ValueError("freeze SHA does not match prepublished GitHub anchor")
    now=clock()
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise ValueError("timezone-aware inspection time required")
    now=now.astimezone(timezone.utc)
    out={
        "schema":SCHEMA,
        "status":"PENDING_FIRST_POST_FREEZE_ORIGINAL_MONTH",
        "freeze_receipt_sha256":ANCHORED_FREEZE_SHA,
        "external_anchor_url":ANCHOR_URL,
        "anchor_sha_matched":True,
        "first_forward_month":"2026-11",
        "candidate_observed_for":None,
        "candidate_sha256":None,
        "prospective_eligible_reference_months":0,
        "candidate_provenance_independently_verified":False,
        "source_rights_independently_verified":False,
        "executable_market_fills_verified":False,
        "strict_m1_model_qualified":False,
        "out_of_sample_investment_performance_proven":False,
        "financial_operations":0,
        "orders_sent":0,
        "database_writes":0,
    }
    if candidate is not None:
        if not isinstance(candidate,dict) or set(candidate)!={
                "month","observed_for","nav_usd","usdpln_nbp",
                "nav_pln_reference","original_export_sha256",
                "original_export_retrieved_at_utc",
                "nbp_original_response_sha256","nbp_retrieved_at_utc",
                "nbp_source_url"}:
            raise ValueError("exact future source metadata contract required")
        if candidate["month"]!="2026-11":
            raise ValueError("only first planned future month is allowed")
        try:
            observed=date.fromisoformat(candidate["observed_for"])
        except (ValueError,TypeError) as e:
            raise ValueError("invalid observed date") from e
        if (observed.strftime("%Y-%m")!="2026-11" or observed.day<20
                or observed<=date.fromisoformat(frozen["last_known_month"]+"-31")):
            raise ValueError("not a valid new month-end reference")
        # Guard against partial-month peeking: do not admit November until
        # December even if a daily November price already exists.
        if now.date()<date(2026,12,1):
            raise ValueError("forward month is not yet complete")
        freeze_at=_utc(frozen["frozen_at_utc"])
        nav_at=_utc(candidate["original_export_retrieved_at_utc"])
        fx_at=_utc(candidate["nbp_retrieved_at_utc"])
        if (nav_at<=freeze_at or fx_at<=freeze_at or
                nav_at.date()<date(2026,12,1) or
                nav_at.date()<=observed or fx_at.date()<observed or
                nav_at>now or fx_at>now):
            raise ValueError("new original-source acquisition must follow completed month, observation and freeze")
        for k in ("original_export_sha256","nbp_original_response_sha256"):
            if not isinstance(candidate[k],str) or not HEX.fullmatch(candidate[k]):
                raise ValueError("original raw source SHA-256 required")
        if candidate["original_export_sha256"]==frozen["original_nav_file_sha256"]:
            raise ValueError("old original export cannot prove new observation")
        nav=_positive(candidate["nav_usd"])
        fx=_positive(candidate["usdpln_nbp"])
        pln=_positive(candidate["nav_pln_reference"])
        if nav*fx!=pln:
            raise ValueError("USD NAV and PLN FX multiplication mismatch")
        url=urlsplit(candidate["nbp_source_url"])
        if (url.scheme!="https" or url.hostname!="api.nbp.pl" or
                url.username or url.password or url.fragment or
                url.path!=f"/api/exchangerates/tables/a/{observed}/{observed}/"):
            raise ValueError("exact-day official NBP URL required")
        out["status"]="CANDIDATE_FORWARD_REFERENCE_REQUIRES_INDEPENDENT_SOURCE_REVIEW"
        out["candidate_observed_for"]=observed.isoformat()
        out["candidate_sha256"]=_digest(candidate)
        # A self-declared new source file hash and retrieval clock alone are
        # not third-party original attestation or a model-qualified outcome.
        out["prospective_eligible_reference_months"]=0
    out["admission_sha256"]=_digest(out)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freeze",type=Path,required=True)
    p.add_argument("--candidate",type=Path)
    args=p.parse_args()
    paths=[args.freeze]+([args.candidate] if args.candidate else [])
    for path in paths:
        if path.is_symlink() or not path.is_file() or path.stat().st_size>3_000_000:
            raise ValueError("regular bounded local JSON file required")
    frozen=json.loads(args.freeze.read_text(encoding="utf-8"))
    candidate=json.loads(args.candidate.read_text(encoding="utf-8")) if args.candidate else None
    out=admission(frozen,candidate)
    print("ISL_NAV_FORWARD_ADMISSION_V23="+
          json.dumps(out,sort_keys=True,separators=(",",":")))


if __name__=="__main__":
    main()
