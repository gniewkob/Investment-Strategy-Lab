"""Official MF bond-market turnover: monthly figures, quality and time series.

Only descriptive secondary-market activity, not investment returns, yields or
a licensed trading/index feed. A current workbook is not a historical PIT vintage.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
import re
import unicodedata

from scripts.mf_bond_market_history_v07 import (
    MF_URL, read_mf_cells, OriginalEvidenceBlocked,
)

SCHEMA="ISL_MF_SECONDARY_MARKET_TURNOVER_HISTORY_V07"
LATEST="2026-09"
FIRST="2009-12"
MONTHS=202
# MF original official Sep-2026 publication (unit: million PLN)
OFFICIAL_LATEST={
    "interbank":Decimal("2782687.61"),
    "bondspot":Decimal("357071.50"),
    "gpw":Decimal("626.14"),
    "total":Decimal("3140385.25"),
}


def _clean(s):
    if not isinstance(s,str):
        raise OriginalEvidenceBlocked("MF_NOT_TEXT")
    v=unicodedata.normalize("NFKD",s)
    return " ".join("".join(c for c in v if not unicodedata.combining(c)).upper().split())


def _number(s):
    if not isinstance(s,str) or len(s)>40:
        raise OriginalEvidenceBlocked("MF_VALUE_TYPE")
    value=s.strip().replace("\u00a0","").replace(" ","")
    if "," in value and "." in value:
        if value.rfind(",")>value.rfind("."):
            value=value.replace(".","").replace(",",".")
        else:
            value=value.replace(",","")
    else:
        value=value.replace(",",".")
    try:
        out=Decimal(value)
    except (InvalidOperation,ValueError) as exc:
        raise OriginalEvidenceBlocked("MF_VALUE_NOT_NUMERIC") from exc
    if not out.is_finite() or out<0 or out>Decimal("999999999"):
        raise OriginalEvidenceBlocked("MF_VALUE_OUT_OF_RANGE")
    return out


def _month(s):
    if not isinstance(s,str):return None
    s=_clean(s)
    for pat,flip in [(r"^(20\d{2})[-/.](\d{1,2})$",False),
                     (r"^(\d{1,2})[-/.](20\d{2})$",True)]:
        hit=re.fullmatch(pat,s)
        if hit:
            year,month=(int(hit.group(2)),int(hit.group(1))) if flip else (
                int(hit.group(1)),int(hit.group(2)))
            if 2009<=year<=2026 and 1<=month<=12:
                return f"{year:04d}-{month:02d}"
    try:serial=int(s)
    except ValueError:return None
    if 39000<=serial<=50000:
        dt=date(1899,12,30)+timedelta(days=serial)
        return f"{dt.year:04d}-{dt.month:02d}"
    return None


def _header(rows):
    words={
        "interbank":("NIEREGULOWAN","INTERBANK","POZAGIELD","OTC"),
        "bondspot":("BONDSPOT","TBS POLAND","TREASURY BOND"),
        "gpw":("GPW","GIELDA PAPIEROW"),
        "total":("RAZEM","OGOL","SUMA","TOTAL"),
        "month":("MIESIAC","OKRES","DATA","MONTH","PERIOD"),
    }
    for row in rows[:80]:
        cols={}
        for col,c in row["cells"].items():
            if c["t"]!="text":continue
            val=_clean(c["value"] or "")
            for k,variants in words.items():
                if any(v in val for v in variants):
                    if k in cols:
                        raise OriginalEvidenceBlocked("MF_AMBIGUOUS_COLUMN")
                    cols[k]=col
        if all(k in cols for k in ("interbank","bondspot","gpw","total")):
            if "month" not in cols:
                candidates=[col for col in row["cells"] if col not in cols.values()]
                if len(candidates)!=1:
                    raise OriginalEvidenceBlocked("MF_NO_UNAMBIGUOUS_PERIOD_COLUMN")
                cols["month"]=candidates[0]
            return row["row"],cols
    raise OriginalEvidenceBlocked("MF_TABLE_HEADER_UNSUPPORTED")


def _successor(month):
    year,mm=map(int,month.split("-"))
    return f"{year+1:04d}-01" if mm==12 else f"{year:04d}-{mm+1:02d}"


def _fmt(v):
    return format(v.quantize(Decimal("0.0001")),"f")


def analyze_mf_original(raw: bytes, *, completed_at: datetime) -> dict:
    proof,rows=read_mf_cells(raw,completed_at=completed_at)
    header,cols=_header(rows)
    series={}
    for row in rows:
        if row["row"]<=header:continue
        cell=row["cells"].get(cols["month"])
        key=_month(cell["value"]) if cell and cell["value"] is not None else None
        if key is None:continue
        if not FIRST<=key<=LATEST:
            raise OriginalEvidenceBlocked("MF_DATE_OUT_OF_CLOSED_WINDOW")
        if key in series:
            raise OriginalEvidenceBlocked("MF_DUPLICATE_MONTH")
        values={}
        for kind in ("interbank","bondspot","gpw","total"):
            cell=row["cells"].get(cols[kind])
            if cell is None or cell["t"]=="formula" or not cell["value"]:
                raise OriginalEvidenceBlocked("MF_EMPTY_OR_FORMULA_FINANCIAL_AMOUNT")
            values[kind]=_number(cell["value"])
        if abs(sum((values[k] for k in ("interbank","bondspot","gpw")),Decimal(0))-
               values["total"])>Decimal("0.1"):
            raise OriginalEvidenceBlocked("MF_CHANNELS_DO_NOT_RECONCILE")
        if values["total"]<=0:raise OriginalEvidenceBlocked("MF_MONTH_ZERO_TOTAL")
        series[key]=values
    ordered=sorted(series)
    if len(ordered)!=MONTHS or ordered[0]!=FIRST or ordered[-1]!=LATEST or any(
            b!=_successor(a) for a,b in zip(ordered,ordered[1:])):
        raise OriginalEvidenceBlocked("MF_INCOMPLETE_202_MONTH_ARCHIVE")
    latest=series[LATEST]
    if any(abs(latest[k]-v)>Decimal("0.1") for k,v in OFFICIAL_LATEST.items()):
        raise OriginalEvidenceBlocked("MF_2026_SEPT_OFFICIAL_PUBLISHER_RECONCILIATION_FAILED")
    with localcontext() as ctx:
        ctx.prec=40
        aug=series["2026-08"]["total"]
        prev=series["2025-09"]["total"]
        if aug<=0 or prev<=0:raise OriginalEvidenceBlocked("MF_ZERO_COMPARISON_DENOMINATOR")
        mom=(latest["total"]/aug-1)*100
        yoy=(latest["total"]/prev-1)*100
        if abs(mom-Decimal("16.8"))>Decimal("0.15"):
            raise OriginalEvidenceBlocked("MF_SEPT_HEADLINE_GROWTH_MISMATCH")
        last12=[series[m] for m in ordered[-12:]]
        annual=sum((r["total"] for r in last12),Decimal(0))
        latest_share={
            k:_fmt(latest[k]/latest["total"]*100)
            for k in ("interbank","bondspot","gpw")}
        avg_share={
            k:_fmt(sum((r[k] for r in last12),Decimal(0))/annual*100)
            for k in ("interbank","bondspot","gpw")}
    return {
        "schema":SCHEMA,
        "status":"ORIGINAL_MARKET_ACTIVITY_DESCRIPTION_ONLY",
        "source":"POLAND_MINISTRY_OF_FINANCE",
        "source_url":MF_URL,
        "source_sha256":proof["original_raw_sha256"],
        "source_observed_at_utc":proof["retrieved_at_utc"],
        "grain":"CALENDAR_MONTH_BY_MARKET_CHANNEL",
        "unit":"MILLION_PLN_TURNOVER_NOT_PRICE_OR_TOTAL_RETURN",
        "unique_month_count":len(ordered),
        "first_month":ordered[0],
        "last_month":ordered[-1],
        "latest_total_mln_pln":str(latest["total"]),
        "latest_interbank_mln_pln":str(latest["interbank"]),
        "latest_bondspot_mln_pln":str(latest["bondspot"]),
        "latest_gpw_mln_pln":str(latest["gpw"]),
        "latest_mom_change_pct":_fmt(mom),
        "latest_yoy_change_pct":_fmt(yoy),
        "latest_month_channel_shares_pct":latest_share,
        "trailing12m_channel_shares_pct":avg_share,
        "source_reported_month_is_not_identical_trade_clock":True,
        "historical_pit_first_publication_certified":False,
        "tradable_bond_total_return_series_qualified":False,
        "licensed_index_bulk_download":False,
        "accounts":0,"orders":0,"database_writes":0,"financial_operations":0,
    }


def main():
    import argparse
    from datetime import timezone
    from scripts.knf_mf_official_source_probe_v06 import fetch_exact
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-original-mf-public-read",action="store_true")
    args=parser.parse_args()
    if not args.allow_original_mf_public_read:
        parser.error("Explicit --allow-original-mf-public-read required")
    report=analyze_mf_original(fetch_exact(MF_URL),
                               completed_at=datetime.now(timezone.utc))
    print("ISL_MF_ORIGINAL_MARKET_TURNOVER_HISTORY="+json.dumps(
        report,sort_keys=True,separators=(",",":")))


if __name__=="__main__":
    main()
