"""Safely inspect EIA STEO XLSX text labels / positions; never print price values.

Purpose: determine how historical official Table 2 workbook layouts changed
before implementing a source-specific forecast extractor. Only trusted
structure metadata and carefully selected short nonnumeric labels are output.
"""
from __future__ import annotations
from io import BytesIO
from posixpath import normpath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from scripts.steo_historical_archive import inspect_xlsx
from src.isl_v2.eia_sources import SourceFormatError

MAIN="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OFFICE="{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE="{http://schemas.openxmlformats.org/package/2006/relationships}"
PRICE_TERMS=re.compile(r"brent|west texas|henry hub|crude|petroleum|natural gas|prices|price|table\s*2|forecast",re.I)
CELL_REF=re.compile(r"[A-Z]{1,3}[1-9][0-9]{0,6}\Z")
MAX_LABELS=90


def _read_part(z:ZipFile,name:str,max_size=15_000_000)->ET.Element:
    parts=set(z.namelist())
    if name not in parts:
        raise SourceFormatError("STEO workbook structural part absent")
    info=z.getinfo(name)
    if info.file_size>max_size:
        raise SourceFormatError("STEO workbook part exceeds limit")
    raw=z.read(name)
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise SourceFormatError("Workbook DTD or entities not accepted")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SourceFormatError("Workbook XML parsing failed") from exc


def _resolve_sheet(z:ZipFile,sheet_name:str)->str:
    book=_read_part(z,"xl/workbook.xml",2_000_000)
    relationships=_read_part(z,"xl/_rels/workbook.xml.rels",2_000_000)
    rid=None
    for node in book.iter(MAIN+"sheet"):
        if node.attrib.get("name")==sheet_name:
            rid=node.attrib.get(OFFICE+"id")
    if not rid:
        raise SourceFormatError("Target STEO worksheet not present")
    target=None
    for relation in relationships.iter(PACKAGE+"Relationship"):
        if relation.attrib.get("Id")==rid:
            target=relation.attrib.get("Target")
            if relation.attrib.get("TargetMode")=="External":
                raise SourceFormatError("External worksheet relationship prohibited")
            break
    if not target or "\\" in target or ".." in target.split("/"):
        raise SourceFormatError("Worksheet relationship not allowlisted")
    if target.startswith("/"):
        path=target.lstrip("/")
    else:
        path=normpath("xl/"+target)
    if not re.fullmatch(r"xl/worksheets/sheet[0-9]+\.xml",path):
        raise SourceFormatError("Unexpected STEO target worksheet path")
    return path


def _shared_strings(z:ZipFile)->list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root=_read_part(z,"xl/sharedStrings.xml",14_000_000)
    result=[]
    for node in root.iter(MAIN+"si"):
        if len(result)>200_000:
            raise SourceFormatError("Too many workbook strings")
        result.append("".join(c.text or "" for c in node.iter(MAIN+"t")))
    return result


def inspect_price_table_labels(raw:bytes, sheet_name:str="2tab")->dict:
    inspect_xlsx(raw)
    with ZipFile(BytesIO(raw)) as z:
        path=_resolve_sheet(z,sheet_name)
        strings=_shared_strings(z)
        sheet=_read_part(z,path,14_000_000)
        labels=[]
        years=[]
        visited=0
        for row in sheet.iter(MAIN+"row"):
            row_idx=int(row.attrib.get("r","0"))
            if row_idx<1 or row_idx>2000:
                continue
            for cell in row.findall(MAIN+"c"):
                visited+=1
                if visited>40000:
                    raise SourceFormatError("Too many worksheet cells")
                position=cell.attrib.get("r","")
                if not CELL_REF.fullmatch(position):
                    raise SourceFormatError("Invalid spreadsheet cell reference")
                kind=cell.attrib.get("t","n")
                v=cell.find(MAIN+"v")
                if kind=="s" and v is not None and v.text is not None:
                    idx=int(v.text)
                    if idx<0 or idx>=len(strings):
                        raise SourceFormatError("Spreadsheet shared string index invalid")
                    text=strings[idx].strip()
                elif kind=="inlineStr":
                    text="".join(c.text or "" for c in cell.iter(MAIN+"t")).strip()
                elif kind=="str" and v is not None:
                    text=(v.text or "").strip()
                else:
                    text=""
                # Numeric year headers are metadata, NOT spot prices.
                if row_idx<=20 and kind=="n" and v is not None and (v.text or "") in [
                    str(year) for year in range(2022,2031)]:
                    years.append({"cell":position,"year":int(v.text)})
                if not text:
                    continue
                # Do not copy tables/long extracts to CI; permit only short
                # headings, and only if needed to identify the series rows.
                if len(text)>110 or not text.isprintable():
                    continue
                if row_idx<=14 or PRICE_TERMS.search(text):
                    labels.append({"cell":position,"row":row_idx,"label":text[:110]})
                if len(labels)>=MAX_LABELS:
                    break
            if len(labels)>=MAX_LABELS:
                break
    return {
        "status":"STEO_XLSX_PRICE_SHEET_TEXT_LABEL_PROBE",
        "sheet":sheet_name,
        "labels":labels,
        "numeric_year_headers":years[:25],
        "numeric_price_values_exposed":0,
        "formulas_evaluated":0,
        "original_historical_first_publication_bytes_verified":False,
        "database_connections":0,
        "database_writes":0,
        "real_orders":0,
    }
