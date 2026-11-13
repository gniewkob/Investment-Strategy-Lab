"""Bounded original MF Treasury secondary-market workbook schema reconnaissance.

Only safe spreadsheet structure, header candidates and signatures. No source
market-volume rows are printed, no executable content or financial activity.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from scripts.knf_mf_official_source_probe_v06 import (
    MF_URL, MAX_MF_BYTES, fetch_exact, inspect_mf_workbook,
    OriginalEvidenceBlocked as Blocked,
)

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MAX_XML = 2_000_000
SAFE_HEADER = re.compile(r"^[\w .,%/()\-]+$", re.UNICODE)


def _xml_member(z: ZipFile, name: str):
    if name not in z.namelist():
        return None
    info=z.getinfo(name)
    if info.file_size > MAX_XML:
        raise Blocked("MF_XML_EXCEEDS_BOUNDS")
    raw=z.read(info)
    if len(raw) > MAX_XML or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise Blocked("MF_UNTRUSTED_XML_ENTITIES")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise Blocked("MF_BAD_OFFICE_XML") from exc


def _shared(z):
    root=_xml_member(z,"xl/sharedStrings.xml")
    if root is None:
        return []
    data=[]
    for si in root.findall(NS+"si"):
        value="".join(t.text or "" for t in si.iter(NS+"t"))
        if len(value)>200:
            raise Blocked("MF_STRING_OVERSIZE")
        data.append(value)
        if len(data)>5000:
            raise Blocked("MF_SHARED_STRINGS_TOO_MANY")
    return data


def _cell(cell, strings):
    t=cell.get("t","n")
    ref=cell.get("r")
    value=cell.find(NS+"v")
    inline=cell.find(NS+"is")
    if t=="s":
        if value is None or not (value.text or "").isdigit():
            raise Blocked("MF_SHARED_STRING_INDEX_BAD")
        i=int(value.text)
        if i>=len(strings):
            raise Blocked("MF_SHARED_STRING_INDEX_BAD")
        return ref,"text",strings[i]
    if t=="inlineStr" and inline is not None:
        txt="".join(t.text or "" for t in inline.iter(NS+"t"))
        return ref,"text",txt[:200]
    if t in ("n","", "e","b","str") and value is not None:
        if t == "e":
            return ref,"error",value.text or ""
        if t == "b":
            return ref,"boolean",value.text or ""
        if t == "str":
            return ref,"text",value.text or ""
        return ref,"number",value.text or ""
    return ref,"blank",None


def inspect_market_sheet(raw: bytes, *, observed_at: datetime) -> dict:
    if not isinstance(observed_at,datetime) or observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise Blocked("UTC_AWARE_REQUIRED")
    base=inspect_mf_workbook(raw,completed_at=observed_at)
    with ZipFile(BytesIO(raw)) as z:
        strings=_shared(z)
        root=_xml_member(z,"xl/worksheets/sheet1.xml")
        if root is None:
            raise Blocked("MF_FIRST_SHEET_MISSING")
        sheetData=root.find(NS+"sheetData")
        if sheetData is None:
            raise Blocked("MF_NO_SHEET_DATA")
        all_rows=list(sheetData.findall(NS+"row"))
        if not 15 <= len(all_rows) <= 2000:
            raise Blocked("MF_UNEXPECTED_ROW_COUNT")
        shape=[]
        for row in all_rows[:28]:
            cells=[_cell(c,strings) for c in row.findall(NS+"c")]
            if len(cells)>80:
                raise Blocked("MF_TOO_MANY_COLUMNS")
            labels=[]
            for ref,kind,value in cells:
                if kind=="text" and isinstance(value,str) and 0<len(value)<=60 and SAFE_HEADER.fullmatch(value):
                    labels.append({"column":re.match(r"^[A-Z]+",ref or "").group(0) if re.match(r"^[A-Z]+",ref or "") else "UNKNOWN",
                                   "caption":value})
            shape.append({"excel_row":row.get("r"),"cell_types":{k:sum(t==k for _,t,_ in cells) for k in ("text","number","error","blank","boolean")},
                          "safe_text_captions":labels[:12]})
        return {
            "schema":"ISL_MF_OFFICIAL_SECONDARY_TREASURY_SCHEMA_AUDIT_V07",
            "state":"ORIGINAL_WORKBOOK_SCHEMA_ONLY_NO_TURNOVER_ADMISSION",
            "source":"PL_MINISTRY_OF_FINANCE_GOV_PL",
            "source_url":MF_URL,
            "sha256":sha256(raw).hexdigest(),
            "observed_at_utc":observed_at.astimezone(timezone.utc).isoformat(),
            "workbook_worksheet_count":base["workbook_worksheet_count"],
            "rows_in_first_sheet":len(all_rows),
            "shared_string_entries":len(strings),
            "first_28_rows_types_and_captions":shape,
            "source_data_rows_in_report":0,
            "turnover_units_validated":False,
            "historical_first_publication_proven":False,
            "bond_total_return_observed":False,
            "database_writes":0,
            "financial_operations":0,
        }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-mf-read",action="store_true")
    args=parser.parse_args()
    if not args.allow_public_mf_read:
        parser.error("Explicit --allow-public-mf-read required")
    output=inspect_market_sheet(fetch_exact(MF_URL),observed_at=datetime.now(timezone.utc))
    print("ISL_MF_ORIGINAL_STRUCTURE_V07="+json.dumps(output,sort_keys=True,separators=(",",":")))


if __name__=="__main__":
    main()
