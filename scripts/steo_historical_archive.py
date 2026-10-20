"""Official EIA STEO historical XLSX catalog and independent local archive proofs.

Research-only. No Neon, brokerage or portfolio APIs. Downloading and disk
writes occur ONLY with an explicit capture subcommand; catalog and verify are
offline. Historic release dates are NOT a proof of immutable historic bytes.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
import hashlib
import io
import json
import os
import re
import sys
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET
from src.isl_v2.eia_raw_archive import _root_fd, _subdir, _read_exact, _write_once, UTC_STAMP
from src.isl_v2.eia_sources import SourceFormatError

BASE="https://www.eia.gov/outlooks/steo/archives/"
INDEX="https://www.eia.gov/outlooks/steo/outlook.php"
MONTHS="jan feb mar apr may jun jul aug sep oct nov dec".split()
RELEASES={
2024:[9,6,12,9,7,11,9,6,10,8,13,10],
2025:[14,11,11,10,6,10,8,12,9,7,12,9],
2026:[13,10,10,7,12,9,7,11,9,6],
}
SIZE_LIMIT=24*1024*1024
STORAGE_LIMIT=160*1024*1024
MAX_MEMBERS=650
STAMP_RE=re.compile(r"(\d{8}T\d{6}\.\d{6}Z)_([a-f0-9]{64})\.json\Z")
SHEET_TAG="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"


def catalog()->dict:
    out={}
    for year,days in RELEASES.items():
        for pos,day in enumerate(days,1):
            issue=MONTHS[pos-1]+str(year)[-2:]
            out[issue]={
                "issue":issue,"official_release_day":date(year,pos,day).isoformat(),
                "xlsx_url":BASE+issue+"_base.xlsx",
                "pdf_url":BASE+issue+".pdf",
                "official_index_url":INDEX,"release_precision":"DAY",
                "historical_original_bytes_certified":False,
            }
    return out


def inspect_xlsx(data:bytes)->dict:
    if not 100<len(data)<=SIZE_LIMIT or not data.startswith(b"PK\x03\x04"):
        raise SourceFormatError("Only bounded XLSX ZIP source bytes allowed")
    try:
        with ZipFile(io.BytesIO(data)) as z:
            members=z.infolist()
            if (not members or len(members)>MAX_MEMBERS
                    or sum(x.file_size for x in members)>STORAGE_LIMIT
                    or any(x.flag_bits&1 or x.filename.startswith("/") or
                        "\\" in x.filename or ".." in x.filename.split("/")
                        for x in members)):
                raise SourceFormatError("XLSX ZIP members rejected")
            names={x.filename for x in members}
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise SourceFormatError("Required XLSX parts absent")
            body=z.read("xl/workbook.xml")
            if len(body)>2_000_000 or b"<!DOCTYPE" in body or b"<!ENTITY" in body:
                raise SourceFormatError("Workbook XML rejected")
            root=ET.fromstring(body)
            titles=[x.attrib.get("name","") for x in root.iter(SHEET_TAG)]
            if not 1<=len(titles)<=80 or any(not t or len(t)>31 for t in titles):
                raise SourceFormatError("Workbook sheet names invalid")
            return {"sheet_count":len(titles),"sheet_names":titles,"zip_member_count":len(members)}
    except (BadZipFile, ET.ParseError, KeyError) as exc:
        raise SourceFormatError("XLSX structure invalid") from exc


def retrieve(issue:str, opener=urlopen)->tuple[bytes,str]:
    spec=catalog().get(issue)
    if spec is None:
        raise SourceFormatError("STEO issue not allowlisted")
    request=Request(spec["xlsx_url"],headers={"User-Agent":"ISL-Independent-STEO-Research/1.0"})
    with opener(request,timeout=30) as r:
        final=r.geturl()
        target=urlparse(final)
        if (target.scheme!="https" or target.hostname!="www.eia.gov"
                or target.path!="/outlooks/steo/archives/"+issue+"_base.xlsx"
                or target.username or target.password or target.query or target.fragment):
            raise SourceFormatError("STEO download redirected outside official allowlist")
        data=r.read(SIZE_LIMIT+1)
    inspect_xlsx(data)
    return data,final


def inspect_receipt(root:str,issue:str,sha:str,acquired:datetime)->dict:
    if issue not in catalog() or not re.fullmatch("[a-f0-9]{64}",sha):
        raise SourceFormatError("Unknown source receipt")
    stamp=acquired.astimezone(timezone.utc).strftime(UTC_STAMP)
    fd=_root_fd(root)
    try:
        objs=_subdir(fd,"objects",create=False)
        try:
            raw=_read_exact(objs,sha+".xlsx",SIZE_LIMIT)
        finally:
            os.close(objs)
        recs=_subdir(fd,"receipts",create=False)
        try:
            folder=_subdir(recs,issue,create=False)
            try:
                receipt=json.loads(_read_exact(folder,stamp+"_"+sha+".json",16384).decode())
            finally:
                os.close(folder)
        finally:
            os.close(recs)
    finally:
        os.close(fd)
    sheet=inspect_xlsx(raw)
    if (hashlib.sha256(raw).hexdigest()!=sha or not isinstance(receipt,dict)
            or receipt.get("source_issue")!=issue
            or receipt.get("original_xlsx_sha256")!=sha
            or receipt.get("retrieved_at")!=acquired.isoformat()
            or receipt.get("official_release_day")!=catalog()[issue]["official_release_day"]
            or receipt.get("original_edition_bytes_as_released_certified") is not False
            or receipt.get("sheet_names")!=sheet["sheet_names"]
            or receipt.get("byte_count")!=len(raw)):
        raise SourceFormatError("Archived XLSX or receipt does not match evidence")
    return {"status":"STEO_XLSX_ORIGINAL_BYTES_OFFLINE_VERIFIED",
            "issue":issue,"official_release_day":catalog()[issue]["official_release_day"],
            "retrieved_at":acquired.isoformat(),"sha256":sha,**sheet,
            "historical_original_publication_bytes_certified":False,
            "forecasts_extracted":0,"database_connections":0,"database_writes":0,
            "real_orders":0}


def capture(root:str,issue:str,opener=urlopen)->dict:
    raw,final=retrieve(issue,opener)
    acquired=datetime.now(timezone.utc)
    sha=hashlib.sha256(raw).hexdigest()
    sheets=inspect_xlsx(raw)
    manifest={"schema":"EIA_STEO_OFFICIAL_EDITION_LOCAL_CAPTURE_V1",
              "source_issue":issue,"official_index_url":INDEX,
              "source_url":final,
              "official_release_day":catalog()[issue]["official_release_day"],
              "original_edition_bytes_as_released_certified":False,
              "retrieved_at":acquired.isoformat(),"original_xlsx_sha256":sha,
              "byte_count":len(raw),**sheets}
    fd=_root_fd(root)
    try:
        objs=_subdir(fd,"objects")
        try:
            created=_write_once(objs,sha+".xlsx",raw)
        finally:
            os.close(objs)
        recs=_subdir(fd,"receipts")
        try:
            folder=_subdir(recs,issue)
            try:
                name=acquired.strftime(UTC_STAMP)+"_"+sha+".json"
                receipt_created=_write_once(folder,name,
                    (json.dumps(manifest,sort_keys=True,separators=(",",":"))+"\n").encode())
            finally:
                os.close(folder)
        finally:
            os.close(recs)
    finally:
        os.close(fd)
    verified=inspect_receipt(root,issue,sha,acquired)
    return {**verified,"status":"STEO_HISTORICAL_XLSX_LOCAL_CAPTURED",
            "original_object_created":created,"receipt_created":receipt_created,
            "network_requests_to_official_eia":1,"archive_is_worm":False}


def verify_all(root:str)->dict:
    fd=_root_fd(root)
    try:
        rfd=_subdir(fd,"receipts",create=False)
        try:
            issues=os.listdir(rfd)
            if not issues or len(issues)>len(catalog()) or any(x not in catalog() for x in issues):
                raise SourceFormatError("Unrecognized or empty STEO archive")
            entries=[]
            for issue in sorted(issues):
                child=_subdir(rfd,issue,create=False)
                try:
                    names=os.listdir(child)
                    if not 1<=len(names)<=100 or any(STAMP_RE.fullmatch(n) is None for n in names):
                        raise SourceFormatError("Unrecognized STEO receipt name")
                    entries.extend((issue,n) for n in names)
                finally:
                    os.close(child)
        finally:
            os.close(rfd)
    finally:
        os.close(fd)
    proofs=[]
    for issue,name in sorted(entries):
        stamp,sha=STAMP_RE.fullmatch(name).groups()
        at=datetime.strptime(stamp,UTC_STAMP).replace(tzinfo=timezone.utc)
        proofs.append(inspect_receipt(root,issue,sha,at))
    return {"status":"STEO_LOCAL_ARCHIVE_ALL_VINTAGES_OFFLINE_VERIFIED",
            "verified_issues":len(set(x["issue"] for x in proofs)),
            "verified_retrievals":len(proofs),
            "verified_workbooks":[{"issue":x["issue"],"sha256":x["sha256"],
                                  "release_day":x["official_release_day"],
                                  "sheet_names":x["sheet_names"]} for x in proofs],
            "historical_original_publication_bytes_certified":False,
            "database_connections":0,"database_writes":0,"real_orders":0,
            "external_http_requests":0,"file_creations":0}


def main(argv:list[str]|None=None)->int:
    ap=argparse.ArgumentParser(description="Read-only or explicitly captured historical EIA STEO editions")
    sub=ap.add_subparsers(dest="action",required=True)
    sub.add_parser("catalog")
    c=sub.add_parser("capture")
    c.add_argument("--archive-root",required=True)
    c.add_argument("--issues",required=True)
    v=sub.add_parser("verify")
    v.add_argument("--archive-root",required=True)
    args=ap.parse_args(argv)
    try:
        if args.action=="catalog":
            x=catalog()
            result={"status":"STEO_OFFICIAL_ARCHIVE_CATALOG",
                    "total_editions":len(x),"items":list(x.values()),
                    "historical_original_publication_bytes_certified":False,
                    "external_http_requests":0,"file_creations":0,
                    "database_connections":0,"database_writes":0,"real_orders":0}
        elif args.action=="capture":
            issues=args.issues.split(",")
            if not 1<=len(issues)<=6 or len(set(issues))!=len(issues) or any(x not in catalog() for x in issues):
                raise SourceFormatError("Choose 1-6 distinct allowlisted STEO editions")
            result={"status":"STEO_PRIVATE_RESEARCH_CAPTURE_COMPLETED",
                    "results":[capture(args.archive_root,x) for x in issues],
                    "database_connections":0,"database_writes":0,"real_orders":0}
        else:
            result=verify_all(args.archive_root)
        print(json.dumps(result,sort_keys=True,separators=(",",":")))
        return 0
    except Exception as exc:
        print("STEO_RESEARCH_FAILED: "+type(exc).__name__,file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
