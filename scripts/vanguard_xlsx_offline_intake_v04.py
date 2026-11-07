"""Inspect a manually exported Vanguard price-history XLSX, OFFLINE.

This is an intake candidate, not a claim to have downloaded the official
file. Never accept legal attestations in a browser. Only read original
XLSX bytes; no server, database, portfolio, or transaction operations.

The format is not yet verified against an actual Vanguard XLSX export.
Unsupported layout => fail closed; do not fabricate historical NAV.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

MAIN="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
MAX_RAW=15_000_000
MAX_UNCOMPRESSED=65_000_000
MAX_ROWS=7000
SHARE_CLASS_INCEPTION=date(2019,7,23)
DATE_COLS={"date","valuation date","nav date","data"}
NAV_USD_COLS={"nav (usd)","nav price (usd)","net asset value (usd)",
              "nav usd","usd nav","net asset value usd"}
# Verified against an original 2026-11-07 Polish Vanguard export:
# dates like '06 lis 2026', NAV like '183,4672\\u00a0USD'.
PL_MONTHS={"sty":1,"lut":2,"mar":3,"kwi":4,"maj":5,"cze":6,
           "lip":7,"sie":8,"wrz":9,"paź":10,"lis":11,"gru":12}



class InvalidVanguardXLSX(ValueError):
    pass


def _text(cell, shared):
    kind=cell.get("t","")
    if cell.find(f"{{{MAIN}}}f") is not None:
        raise InvalidVanguardXLSX("formula cell not permitted for source NAV")
    if kind=="inlineStr":
        return "".join(x.text or "" for x in cell.findall(f".//{{{MAIN}}}t"))
    v=cell.find(f"{{{MAIN}}}v")
    if v is None:
        return ""
    raw=v.text or ""
    if kind=="s":
        try: return shared[int(raw)]
        except (IndexError,ValueError) as ex:
            raise InvalidVanguardXLSX("broken shared string") from ex
    if kind=="e":
        raise InvalidVanguardXLSX("Excel error value in source")
    return raw


def _sheet_rows(raw):
    if not isinstance(raw, bytes) or not raw or len(raw)>MAX_RAW:
        raise InvalidVanguardXLSX("bounded nonempty original XLSX bytes required")
    try:
        with ZipFile(BytesIO(raw)) as z:
            infos=z.infolist()
            names={i.filename for i in infos}
            if (sum(x.file_size for x in infos)>MAX_UNCOMPRESSED or
                    len(infos)>400 or "[Content_Types].xml" not in names or
                    "xl/workbook.xml" not in names or
                    "xl/worksheets/sheet1.xml" not in names):
                raise InvalidVanguardXLSX("invalid or oversized XLSX workbook")
            if any(x.startswith(("xl/externalLinks/","xl/vbaProject","xl/embeddings/"))
                   for x in names):
                raise InvalidVanguardXLSX("external references, macros or embeddings blocked")
            workbook=ET.fromstring(z.read("xl/workbook.xml"))
            options=workbook.find(f"{{{MAIN}}}workbookPr")
            if options is not None and options.get("date1904") in ("1","true"):
                raise InvalidVanguardXLSX("1904 Excel calendar unsupported")
            shared=[]
            if "xl/sharedStrings.xml" in names:
                root=ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in root.findall(f"{{{MAIN}}}si"):
                    shared.append("".join(t.text or "" for t in si.findall(f".//{{{MAIN}}}t")))
                if len(shared)>20000:
                    raise InvalidVanguardXLSX("unbounded shared string table")
            sheet=ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
            result=[]
            for row in sheet.findall(f".//{{{MAIN}}}sheetData/{{{MAIN}}}row"):
                cells={}
                for c in row.findall(f"{{{MAIN}}}c"):
                    match=re.match(r"^([A-Z]{1,3})[0-9]+$",c.get("r",""))
                    if not match:raise InvalidVanguardXLSX("unknown cell address")
                    col=0
                    for ch in match.group(1):col=26*col+ord(ch)-64
                    if col>40:continue
                    if col in cells:raise InvalidVanguardXLSX("duplicate cell address")
                    cells[col]=_text(c,shared).strip()
                result.append(cells)
                if len(result)>MAX_ROWS:
                    raise InvalidVanguardXLSX("too many worksheet rows")
            return result
    except (BadZipFile,ET.ParseError,KeyError) as exc:
        raise InvalidVanguardXLSX("unreadable original XLSX") from exc


def _date_from_xlsx(v):
    if not v:return None
    if re.fullmatch(r"[0-9]{5}",v):
        serial=int(v)
        if serial<61 or serial>75000:
            raise InvalidVanguardXLSX("out-of-range Excel date serial")
        return date(1899,12,30)+timedelta(days=serial)
    localized=re.fullmatch(r"([0-9]{1,2})\\s+([a-ząćęłńóśźż]{3})\\s+([0-9]{4})",v.lower())
    if localized:
        day,short,year=localized.groups()
        if short not in PL_MONTHS:
            raise InvalidVanguardXLSX("unrecognized Polish month in source date")
        try:
            return date(int(year),PL_MONTHS[short],int(day))
        except ValueError as exc:
            raise InvalidVanguardXLSX("invalid Polish source date") from exc
    for fmt in ("%Y-%m-%d","%d %b %Y","%d %B %Y"):
        try:
            from datetime import datetime
            return datetime.strptime(v,fmt).date()
        except ValueError:pass
    raise InvalidVanguardXLSX("unrecognized date format in candidate NAV row")


def _positive(v):
    if not v: return None
    cleaned=v.replace("\\u00a0"," ").strip()
    if cleaned.endswith(" USD"):
        # Actual official Polish export: decimal comma, USD suffix, and
        # possibly grouped thousands. Never interpret commas as thousands.
        localized=cleaned[:-4].strip()
        if not re.fullmatch(r"[0-9]+(?: [0-9]{3})*,[0-9]{1,8}",localized):
            raise InvalidVanguardXLSX("unrecognized localized NAV USD decimal")
        cleaned=localized.replace(" ","").replace(",",".")
    else:
        # Original synthetic/English fixture conventions remain supported.
        cleaned=cleaned.replace("US$","").replace("$","").replace(",","").strip()
    try: d=Decimal(cleaned)
    except InvalidOperation as exc:
        raise InvalidVanguardXLSX("unrecognized NAV decimal") from exc
    if not d.is_finite() or d<=0:
        raise InvalidVanguardXLSX("NAV must be positive finite")
    return format(d,"f")


def inspect_export(raw,first_month,last_month,*,as_of=None):
    # Allow time injection in offline tests, but never a future vintage.
    as_of = datetime.now(timezone.utc).date() if as_of is None else as_of
    if not isinstance(as_of,date) or isinstance(as_of,datetime):
        raise InvalidVanguardXLSX("as_of must be a calendar date")
    try: first=date.fromisoformat(first_month+"-01");last=date.fromisoformat(last_month+"-01")
    except ValueError as e:raise InvalidVanguardXLSX("invalid YYYY-MM range") from e
    if first<SHARE_CLASS_INCEPTION.replace(day=1):
        raise InvalidVanguardXLSX("requested data predates Vanguard share-class inception")
    if last>=as_of.replace(day=1):
        raise InvalidVanguardXLSX("only completed historical months are accepted")
    months=[]
    cursor=first
    while cursor<=last:
        months.append(cursor.strftime("%Y-%m"))
        cursor=date(cursor.year+(cursor.month==12),cursor.month%12+1,1)
        if len(months)>72:break
    if len(months)<36 or len(months)>72:
        raise InvalidVanguardXLSX("36-72 months required")
    rows=_sheet_rows(raw)
    choices=[]
    for i,row in enumerate(rows[:50]):
        normalized={k:" ".join(v.lower().strip().split()) for k,v in row.items()}
        date_cols=[k for k,v in normalized.items() if v in DATE_COLS]
        nav_cols=[k for k,v in normalized.items() if v in NAV_USD_COLS]
        if len(date_cols)==1 and len(nav_cols)==1 and date_cols[0]!=nav_cols[0]:
            choices.append((i,date_cols[0],nav_cols[0]))
    if len(choices)!=1:
        raise InvalidVanguardXLSX("unique Date and NAV (USD) header not identified")
    first_row,date_col,nav_col=choices[0]
    observed={}
    missing_nav_dates=[]
    seen=set()
    for row in rows[first_row+1:]:
        if not row.get(date_col):continue
        day=_date_from_xlsx(row[date_col])
        if day>as_of:
            raise InvalidVanguardXLSX("future NAV observation cannot be historical")
        if day<SHARE_CLASS_INCEPTION:
            raise InvalidVanguardXLSX("NAV observation predates share-class inception")
        if day in seen:raise InvalidVanguardXLSX("duplicate original NAV day")
        seen.add(day)
        val=_positive(row.get(nav_col,""))
        if val is None:
            missing_nav_dates.append(day.isoformat());continue
        month=day.strftime("%Y-%m")
        if month in months:
            if month not in observed or day>observed[month][0]:
                observed[month]=(day,val)
    missing=[m for m in months if m not in observed]
    if missing:
        raise InvalidVanguardXLSX("missing original source NAV months: "+",".join(missing))
    output={
        "status":"RAW_NAV_XLSX_CANDIDATE_NEEDS_PROVIDER_IDENTITY_ATTESTATION",
        "file_type":"XLSX",
        "raw_export_sha256":sha256(raw).hexdigest(),
        "source_file_format":"XLSX_DATE_NAV_USD_CANDIDATE_V1",
        "first_month":months[0],"last_month":months[-1],"months":len(months),
        "monthly":[{"month":m,"observed_for":observed[m][0].isoformat(),
                    "nav_usd":observed[m][1]} for m in months],
        "missing_nav_daily_rows":len(missing_nav_dates),
        "name_or_isin_authenticated_from_download":False,
        "historical_vintage_verified":False,
        "historical_pit_certified":False,
        "original_exchange_fill_price_verified":False,
        "usable_as_GLOBAL_EQUITY_TR_PLN":False,
        "backtest":"NOT_RUN_PROVIDER_PROVENANCE_REQUIRED",
        "paper_events_created":0,"financial_operations":0,
    }
    output["candidate_sha256"]=sha256(json.dumps(output,sort_keys=True,
        separators=(",",":")).encode()).hexdigest()
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file",type=Path,required=True)
    p.add_argument("--first-month",required=True)
    p.add_argument("--last-month",required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    result=inspect_export(args.file.read_bytes(),args.first_month,args.last_month)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("status","months","raw_export_sha256",
          "backtest","financial_operations")},sort_keys=True))


if __name__=="__main__":
    main()
