"""Verify and combine real BondSpot TBSP 12-month source-evidence chunks.

Uses only already collected data; never invents or interpolates missing
months. Unauthenticated HTTP isn't called here; the offline merger
recomputes SHA-256 of each source chunk and every month boundary.
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

HOST="www.bondspot.pl"
BASIS="BOND_TOTAL_RETURN_BENCHMARK_INDEX"
SERIES="BONDSPOT_TBSP_CLOSE_PLN"
MAX_MONTHS=72

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("utf-8")

def next_month(value: str):
    year,month=map(int,value.split("-"))
    return f"{year+1:04d}-01" if month==12 else f"{year:04d}-{month+1:02d}"

def check_chunk(value):
    if not isinstance(value,dict) or value.get("source")!="BONDSPOT_TBSP_OFFICIAL_ARCHIVE":
        raise ValueError("unexpected BondSpot evidence source")
    digest=value.get("evidence_sha256")
    body={k:v for k,v in value.items() if k!="evidence_sha256"}
    if not isinstance(digest,str) or sha256(canonical(body)).hexdigest()!=digest:
        raise ValueError("chunk SHA-256 mismatch")
    if value.get("basis")!=BASIS or value.get("series_id")!=SERIES:
        raise ValueError("unapproved index source basis")
    if value.get("instrument_kind")!="NON_TRADABLE_INDEX":
        raise ValueError("index is not executable")
    if (value.get("historical_pit_certified") is not False or
        value.get("tradable_fills_authorized") is not False or
        value.get("paper_events_created") != 0 or
        value.get("financial_operations") != 0 or
        value.get("backtest") != "NOT_RUN_SOURCE_ONLY"):
        raise ValueError("invalid research-only restrictions")
    rows=value.get("observations")
    if not isinstance(rows,list) or len(rows)!=value.get("months") or not rows:
        raise ValueError("incomplete BondSpot evidence")
    last=None
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("invalid observation")
        month=row.get("month")
        observed=row.get("observed_for")
        if not isinstance(month,str) or not isinstance(observed,str):
            raise ValueError("missing dated observation")
        if len(month)!=7 or date.fromisoformat(observed).strftime("%Y-%m")!=month:
            raise ValueError("month and observed date mismatch")
        if last is not None and month!=next_month(last):
            raise ValueError("calendar gap or repeated month")
        if row.get("basis")!=BASIS or row.get("currency")!="PLN" or row.get("instrument_kind")!="NON_TRADABLE_INDEX":
            raise ValueError("unauthorized transformation of source")
        if row.get("historical_first_usable_at") is not None:
            raise ValueError("fabricated first usability timestamp")
        from decimal import Decimal,InvalidOperation
        try:
            val=Decimal(str(row.get("level")))
        except InvalidOperation as exc:
            raise ValueError("invalid TBSP index") from exc
        if not val.is_finite() or val<=0:
            raise ValueError("invalid TBSP index value")
        for suffix in ("calendar","dated"):
            u=row.get(suffix+"_url")
            digest2=row.get(suffix+"_sha256")
            if not isinstance(u,str) or not isinstance(digest2,str) or len(digest2)!=64:
                raise ValueError("invalid page provenance")
            host=urlsplit(u)
            if host.scheme!="https" or host.hostname!=HOST or host.path!="/tbsp_index_archiwum":
                raise ValueError("non-official source URL")
            if any(ch not in "0123456789abcdef" for ch in digest2):
                raise ValueError("invalid page SHA-256")
            qs=parse_qs(host.query)
            if qs.get("year")!=[month[:4]] or qs.get("month")!=[month[5:]]:
                raise ValueError("source URL calendar mismatch")
            if suffix=="dated" and qs.get("date")!=[observed.replace("-","")]:
                raise ValueError("source page not dated for observation")
        last=month
    if rows[0]["month"]!=value.get("first_month") or rows[-1]["month"]!=value.get("last_month"):
        raise ValueError("chunk bounds mismatch")
    return rows

def merge(chunks:list[dict],first:str,last:str):
    if not isinstance(chunks,list) or not chunks or len(chunks)>MAX_MONTHS:
        raise ValueError("bounded chunk list required")
    chunks=sorted(chunks,key=lambda x:x.get("first_month",""))
    rows=[]
    keys=[]
    for data in chunks:
        entries=check_chunk(data)
        if rows and entries[0]["month"]!=next_month(rows[-1]["month"]):
            raise ValueError("gap or overlap between BondSpot chunks")
        keys.append({"first_month":data["first_month"],
                     "last_month":data["last_month"],
                     "sha256":data["evidence_sha256"]})
        rows.extend(entries)
        if len(rows)>MAX_MONTHS:
            raise ValueError("too many months")
    if rows[0]["month"]!=first or rows[-1]["month"]!=last:
        raise ValueError("combined evidence does not cover requested horizon")
    output={
        "source":"BONDSPOT_TBSP_OFFICIAL_ARCHIVE",
        "series_id":SERIES,"basis":BASIS,
        "instrument_kind":"NON_TRADABLE_INDEX",
        "first_month":first,"last_month":last,
        "monthly_count":len(rows),
        "chunk_receipts":keys,
        "monthly_observations":rows,
        "historical_pit_certified":False,
        "trading_price_proven":False,
        "backtest":"NOT_RUN_SOURCE_ONLY",
        "paper_events_created":0,"financial_operations":0,
    }
    output["evidence_sha256"]=sha256(canonical(output)).hexdigest()
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chunks-dir",type=Path,required=True)
    p.add_argument("--start-month",required=True)
    p.add_argument("--end-month",required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    files=sorted(args.chunks_dir.rglob("*.json"))
    if not files:
        raise ValueError("missing BondSpot archive files")
    data=[json.loads(f.read_text(encoding="utf-8")) for f in files]
    combined=merge(data,args.start_month,args.end_month)
    args.out.write_text(json.dumps(combined,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("TBSP_FIVE_YEAR_EVIDENCE="+json.dumps({
        "source":combined["source"],"first_month":combined["first_month"],
        "last_month":combined["last_month"],"months":combined["monthly_count"],
        "chunks":len(combined["chunk_receipts"]),
        "sha256":combined["evidence_sha256"],
        "historical_pit_certified":False,
        "backtest":combined["backtest"],
        "financial_operations":0},sort_keys=True,separators=(",",":")))

if __name__=="__main__":
    main()
