"""Original Polish MF bond-market XLSX: safe XML read and bounded layout audit.

Read-only educational historical market-turnover source. Never execute formulas,
VBA, external links or arbitrary XLSX embedded code. The XML workbook and sheet
are inspected using stdlib only; no market data files written to disk.
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
    MF_URL, MAX_MF_BYTES, OriginalEvidenceBlocked, fetch_exact,
    inspect_mf_workbook, _utc,
)

SCHEMA = "ISL_MF_BOND_MARKET_HISTORY_SOURCE_V07"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
CELL = re.compile(r"^([A-Z]{1,3})([1-9]\d{0,4})$")
MAX_SHEET_BYTES = 4_000_000
MAX_STRINGS_BYTES = 1_000_000
MAX_TEXT = 96
MAX_ROWS = 5_000
MAX_COLS = 48


def _read_member(z: ZipFile, path: str, limit: int) -> bytes:
    info = z.getinfo(path)
    if info.file_size > limit or info.compress_size > MAX_MF_BYTES:
        raise OriginalEvidenceBlocked("MF_XML_MEMBER_SIZE_INVALID")
    with z.open(path) as stream:
        content = stream.read(limit + 1)
    if len(content) > limit or b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise OriginalEvidenceBlocked("MF_XML_MEMBER_UNSAFE")
    return content


def _text(value: str) -> str:
    if not isinstance(value, str):
        raise OriginalEvidenceBlocked("MF_TEXT_NOT_STRING")
    # Print limited text-only header excerpts; no raw rows, hyperlinks or formulas.
    clean = " ".join(value.split())
    if any(ord(c) < 32 or ord(c) == 127 for c in clean):
        raise OriginalEvidenceBlocked("MF_TEXT_CONTROL_CHARACTER")
    return clean[:MAX_TEXT]


def _shared_strings(z: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(_read_member(z,"xl/sharedStrings.xml",MAX_STRINGS_BYTES))
    if root.tag != NS+"sst":
        raise OriginalEvidenceBlocked("MF_SHARED_STRINGS_INVALID")
    strings = []
    for si in root.findall(NS+"si"):
        if len(strings) >= 5000:
            raise OriginalEvidenceBlocked("MF_SHARED_STRINGS_EXCESSIVE")
        pieces = [e.text or "" for e in si.iter(NS+"t")]
        strings.append(_text("".join(pieces)))
    return strings


def read_mf_cells(raw: bytes, *, completed_at: datetime) -> tuple[dict, list[dict]]:
    receipt = inspect_mf_workbook(raw, completed_at=completed_at)
    if type(raw) is not bytes or len(raw) > MAX_MF_BYTES:
        raise OriginalEvidenceBlocked("MF_RAW_BYTES_OUT_OF_BOUNDS")
    with ZipFile(BytesIO(raw)) as z:
        names = z.namelist()
        sheets = [n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml",n)]
        if len(sheets)!=1:
            raise OriginalEvidenceBlocked("MF_ONE_WORKSHEET_REQUIRED")
        shared = _shared_strings(z)
        root = ET.fromstring(_read_member(z,sheets[0],MAX_SHEET_BYTES))
        if root.tag != NS+"worksheet":
            raise OriginalEvidenceBlocked("MF_WORKSHEET_XML_INVALID")
        data = root.find(NS+"sheetData")
        if data is None:
            raise OriginalEvidenceBlocked("MF_SHEET_NO_DATA")
        output=[]
        seen_rows=set()
        for row in data.findall(NS+"row"):
            try:
                rn=int(row.attrib["r"])
            except (KeyError,ValueError) as exc:
                raise OriginalEvidenceBlocked("MF_ROW_NUMBER_INVALID") from exc
            if rn in seen_rows or not 1 <= rn <= MAX_ROWS:
                raise OriginalEvidenceBlocked("MF_DUPLICATE_OR_EXCESS_ROW")
            seen_rows.add(rn)
            cells={}
            for c in row.findall(NS+"c"):
                addr=c.attrib.get("r", "")
                match=CELL.fullmatch(addr)
                if not match or int(match.group(2))!=rn:
                    raise OriginalEvidenceBlocked("MF_CELL_ADDRESS_BAD")
                col=match.group(1)
                pos=0
                for letter in col:
                    pos=pos*26+ord(letter)-64
                if pos>MAX_COLS or col in cells:
                    raise OriginalEvidenceBlocked("MF_DUPLICATE_OR_WIDE_CELL")
                typ=c.attrib.get("t","n")
                v=c.find(NS+"v")
                formula=c.find(NS+"f")
                if formula is not None:
                    # Formula cells are metadata only; never execute or trust caches.
                    value = {"t":"formula","value":None}
                elif typ=="s":
                    if v is None or v.text is None:
                        raise OriginalEvidenceBlocked("MF_STRING_INDEX_MISSING")
                    try:
                        ix=int(v.text)
                        value={"t":"text","value":shared[ix]}
                    except (IndexError,ValueError) as exc:
                        raise OriginalEvidenceBlocked("MF_STRING_INDEX_INVALID") from exc
                elif typ=="inlineStr":
                    isl=c.find(NS+"is")
                    value={"t":"text","value":_text("".join(e.text or "" for e in isl.iter(NS+"t"))) if isl is not None else ""}
                elif typ in ("str","n","b","d"):
                    value={"t":typ,"value":_text(v.text or "") if v is not None else ""}
                elif typ=="e":
                    raise OriginalEvidenceBlocked("MF_EXCEL_ERROR_CELL")
                else:
                    raise OriginalEvidenceBlocked("MF_CELL_TYPE_UNSUPPORTED")
                cells[col]=value
            output.append({"row":rn,"cells":cells})
    receipt = {
        **receipt,
        "schema":SCHEMA,
        "xml_rows":len(output),
        "first_populated_row":min(seen_rows) if seen_rows else None,
        "last_populated_row":max(seen_rows) if seen_rows else None,
        "formula_cells":sum(c["t"]=="formula" for x in output for c in x["cells"].values()),
        "distinct_columns":sorted(set(c for x in output for c in x["cells"])),
        "source_sha256_rechecked":sha256(raw).hexdigest(),
        "source_rights":"PUBLIC_MINISTRY_STATISTICS_SOURCE_NOT_INDEX_PRICE_OR_TR",
        "historic_original_first_publication_verified":False,
    }
    return receipt, output


def audit_mf_schema(raw: bytes, *, completed_at: datetime) -> dict:
    receipt,rows=read_mf_cells(raw,completed_at=completed_at)
    # Only print compact, bounded original data-shape examples, no full rows.
    top=rows[:13]
    tail=rows[-4:] if len(rows)>17 else []
    preview=[]
    for record in top+tail:
        compact={}
        for col,cell in list(record["cells"].items())[:14]:
            compact[col]={"type":cell["t"],
                          "sample":cell["value"][:40] if cell["value"] is not None else None}
        preview.append({"row":record["row"],"cells":compact})
    return {**receipt,"schema_preview_first13_last4":preview,
            "full_data_exported":False,"financial_operations":0,
            "database_writes":0,"order_creation":0}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-mf-source-read",action="store_true")
    parser.add_argument("--audit-schema",action="store_true")
    args=parser.parse_args()
    if not args.allow_public_mf_source_read or not args.audit_schema:
        parser.error("Explicit public official read + --audit-schema required")
    data=fetch_exact(MF_URL)
    report=audit_mf_schema(data,completed_at=datetime.now(timezone.utc))
    print("ISL_ORIGINAL_MF_MARKET_SCHEMA="+json.dumps(report,sort_keys=True,separators=(",",":")))


if __name__=="__main__":
    main()
