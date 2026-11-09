"""v0.24 offline Vanguard forward source-bundle preflight.

Manual new original XLSX and saved exact-date NBP raw response bytes only;
no browsing automation, no acceptance clicks, no source licensing claims.
Default PENDING before first completed November monthly observation.
All private source values remain local and CLI prints summary only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, date
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from scripts.nav_forward_admission_v23 import admission, _utc
from scripts.vanguard_xlsx_offline_intake_v04 import inspect_export
from scripts.vanguard_nav_intake_bundle_v04 import _parse_fx
from scripts.conditional_m1_nav_diagnostic_v20 import evaluate_nav_reference
from scripts.reference_archive_calendar_v04 import _digest

SCHEMA="ISL_NAV_FORWARD_PREFLIGHT_V24_001"
LAST_BASELINE="2026-10"
NEXT="2026-11"


def preflight(frozen, baseline, *, raw_export=None, raw_nbp=None,
              export_retrieved_at_utc=None, nbp_retrieved_at_utc=None,
              clock=lambda: datetime.now(timezone.utc)):
    # Strictly verify the earlier private 60-month receipt and the freeze
    # before trusting any candidate or retroactive history revision.
    old=evaluate_nav_reference(baseline)
    if old["source_evidence_sha256"]!=frozen.get("source_evidence_sha256"):
        raise ValueError("frozen baseline source digest mismatch")
    if old["nav_file_sha256"]!=frozen.get("original_nav_file_sha256"):
        raise ValueError("frozen original source identity mismatch")
    inspected=admission(frozen,clock=clock)
    now=clock()
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise ValueError("timezone aware inspection clock required")
    now=now.astimezone(timezone.utc)
    output={
        "schema":SCHEMA,
        "status":"PENDING_NEXT_COMPLETE_MONTH_OR_NEW_ORIGINAL_EXPORT",
        "freeze_receipt_sha256":inspected["freeze_receipt_sha256"],
        "baseline_source_sha256":baseline["evidence_sha256"],
        "first_forward_month":NEXT,
        "new_export_sha256":None,
        "nbp_raw_response_sha256":None,
        "historical_revisions_count":0,
        "historical_revision_months":[],
        "future_candidate_observed_for":None,
        "source_provenance_independently_verified":False,
        "qualified_m1_model_backtest":False,
        "oos_investment_performance_proven":False,
        "prospective_eligible_months":0,
        "financial_operations":0,
        "database_writes":0,
        "orders_sent":0,
    }
    if raw_export is None and raw_nbp is None:
        output["preflight_sha256"]=_digest(output)
        return output
    if not isinstance(raw_export,bytes) or not isinstance(raw_nbp,bytes):
        raise ValueError("new export and official NBP raw response bytes both required")
    if now.date()<date(2026,12,1):
        raise ValueError("cannot ingest partial November as completed month")
    export_time=_utc(export_retrieved_at_utc)
    nbp_time=_utc(nbp_retrieved_at_utc)
    if export_time>now or nbp_time>now:
        raise ValueError("retrieval timestamps must not be future")
    fresh=inspect_export(raw_export,"2021-11","2026-11",as_of=now.date())
    new_rows={r["month"]:r for r in fresh["monthly"]}
    old_rows={r["month"]:r for r in baseline["monthly"]}
    revisions=[]
    for m in old_rows:
        r=new_rows[m]
        older=old_rows[m]
        if (r["observed_for"]!=older["observed_for"] or
                Decimal(r["nav_usd"])!=Decimal(older["nav_usd"])):
            revisions.append(m)
    output["new_export_sha256"]=fresh["raw_export_sha256"]
    output["historical_revisions_count"]=len(revisions)
    output["historical_revision_months"]=revisions
    if fresh["raw_export_sha256"]==frozen["original_nav_file_sha256"]:
        raise ValueError("new original export identical to frozen original")
    if revisions:
        output["status"]="BLOCKED_HISTORICAL_SOURCE_REVISIONS_REQUIRE_REVIEW"
        output["preflight_sha256"]=_digest(output)
        return output
    newest=new_rows[NEXT]
    day=newest["observed_for"]
    url=f"https://api.nbp.pl/api/exchangerates/tables/a/{day}/{day}/?format=json"
    fx=_parse_fx(day,url,raw_nbp,nbp_retrieved_at_utc)
    candidate={
        "month":NEXT,
        "observed_for":day,
        "nav_usd":newest["nav_usd"],
        "usdpln_nbp":fx["usdpln"],
        "nav_pln_reference":str(Decimal(newest["nav_usd"])*Decimal(fx["usdpln"])),
        "original_export_sha256":fresh["raw_export_sha256"],
        "original_export_retrieved_at_utc":export_retrieved_at_utc,
        "nbp_original_response_sha256":sha256(raw_nbp).hexdigest(),
        "nbp_retrieved_at_utc":nbp_retrieved_at_utc,
        "nbp_source_url":url,
    }
    check=admission(frozen,candidate,clock=clock)
    output["status"]=check["status"]
    output["nbp_raw_response_sha256"]=sha256(raw_nbp).hexdigest()
    output["future_candidate_observed_for"]=day
    output["candidate_sha256"]=check["candidate_sha256"]
    # Still only a local source candidate; independent source attestation and
    # actual original issuer identity cannot be supplied by this report.
    output["preflight_sha256"]=_digest(output)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freeze",type=Path,required=True)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--new-xlsx",type=Path)
    p.add_argument("--nbp-response-json",type=Path)
    p.add_argument("--export-retrieved-at-utc")
    p.add_argument("--nbp-retrieved-at-utc")
    args=p.parse_args()
    paths=[args.freeze,args.baseline]+[x for x in
            (args.new_xlsx,args.nbp_response_json) if x is not None]
    for path in paths:
        if path.is_symlink() or not path.is_file() or path.stat().st_size>15_000_000:
            raise ValueError("bounded private regular file required")
    result=preflight(json.loads(args.freeze.read_text(encoding="utf-8")),
                     json.loads(args.baseline.read_text(encoding="utf-8")),
                     raw_export=args.new_xlsx.read_bytes() if args.new_xlsx else None,
                     raw_nbp=args.nbp_response_json.read_bytes() if args.nbp_response_json else None,
                     export_retrieved_at_utc=args.export_retrieved_at_utc,
                     nbp_retrieved_at_utc=args.nbp_retrieved_at_utc)
    print("ISL_NAV_FORWARD_PREFLIGHT_V24="+
          json.dumps(result,sort_keys=True,separators=(",",":")))


if __name__=="__main__":
    main()
