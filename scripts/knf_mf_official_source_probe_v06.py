"""UKNF fund evidence and MF bond-market turnover original-public-source probe.

Source-first bounded discovery, not a scraper or fund/ETF recommendation.
No portfolio action, total-return qualification, historical-vintage promotion.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import re
from urllib.request import build_opener, HTTPRedirectHandler, HTTPSHandler, Request
from zipfile import BadZipFile, ZipFile

KNF_ROOT = "https://wybieramfundusze-api.knf.gov.pl"
KNF_PATHS = {
    "funds": "/v1/funds?page=0&size=2",
    "primary_pln_valuations": (
        "/v1/valuations/units?currency=PLN&isPrimary=true&fromDate=2026-09-01"
        "&toDate=2026-09-30&page=0&size=3"
    ),
    "kid_units": "/v1/key-information/units?page=0&size=2",
}
KNF_URLS = {kind: KNF_ROOT + path for kind, path in KNF_PATHS.items()}
MF_URL = "https://www.gov.pl/attachment/e720fd6f-1bd6-4e2f-87b4-6d05e03473d4"
MAX_KNF_BYTES = 320_000
MAX_MF_BYTES = 2_000_000
SCHEMA = "ISL_UKNF_MF_PUBLIC_MARKET_ORIGINAL_EVIDENCE_PROBE_V06"
UTC_DAY = re.compile(r"^20\d\d-\d\d-\d\d$")
SAFE_KEY = re.compile(r"^[A-Za-z_][A-Za-z_0-9]{0,55}$")
UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

class OriginalEvidenceBlocked(ValueError):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OriginalEvidenceBlocked("REDIRECT_SOURCE_CHANGED")

def _utc(v):
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        raise OriginalEvidenceBlocked("UTC_AWARE_CLOCK_REQUIRED")
    return v.astimezone(timezone.utc).isoformat()

def fetch_exact(url: str) -> bytes:
    allowed = set(KNF_URLS.values()) | {MF_URL}
    if url not in allowed:
        raise OriginalEvidenceBlocked("URL_NOT_OFFICIAL_ALLOWLIST")
    limit = MAX_MF_BYTES if url == MF_URL else MAX_KNF_BYTES
    op = build_opener(NoRedirect(), HTTPSHandler())
    req = Request(url, headers={"Accept": "application/octet-stream" if url == MF_URL else "application/json",
                                "User-Agent": "ISL-source-edu-v0.6/one-shot"})
    with op.open(req, timeout=25) as response:
        if response.status != 200 or response.geturl() != url:
            raise OriginalEvidenceBlocked("OFFICIAL_RESPONSE_IDENTITY_CHANGED")
        raw = response.read(limit + 1)
    if len(raw) == 0 or len(raw) > limit:
        raise OriginalEvidenceBlocked("SOURCE_BYTES_OUT_OF_BOUNDS")
    return raw

def _date(s: object) -> date:
    if not isinstance(s, str) or not UTC_DAY.fullmatch(s):
        raise OriginalEvidenceBlocked("SOURCE_DATE_INVALID")
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise OriginalEvidenceBlocked("SOURCE_DATE_INVALID") from exc

def inspect_knf_page(kind: str, raw: bytes, *, completed_at: datetime) -> dict:
    when = _utc(completed_at)
    if kind not in KNF_URLS or type(raw) is not bytes or not 0 < len(raw) <= MAX_KNF_BYTES:
        raise OriginalEvidenceBlocked("KNF_SOURCE_INVALID")
    try:
        payload = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OriginalEvidenceBlocked("KNF_INVALID_JSON") from exc
    if not isinstance(payload, dict):
        raise OriginalEvidenceBlocked("KNF_EXPECTED_PAGE_OBJECT")
    records, pg = payload.get("content"), payload.get("page")
    limit = 3 if kind == "primary_pln_valuations" else 2
    if (not isinstance(records, list) or len(records) > limit or
            not isinstance(pg, dict) or type(pg.get("number")) is not int or
            pg["number"] != 0 or type(pg.get("size")) is not int or
            not 1 <= pg["size"] <= limit or
            type(pg.get("totalElements")) is not int or
            not len(records) <= pg["totalElements"] <= 10_000_000):
        raise OriginalEvidenceBlocked("KNF_PAGINATION_CONTRACT")
    field_keys = set()
    for row in records:
        if not isinstance(row, dict) or len(row) > 50:
            raise OriginalEvidenceBlocked("KNF_ROW_INVALID")
        # Field names only, not names, valuations, issuer identifiers or KID forecasts.
        if any(not isinstance(k, str) or not SAFE_KEY.fullmatch(k) for k in row):
            raise OriginalEvidenceBlocked("KNF_FIELD_NAME_UNSAFE")
        field_keys.update(row)
        if kind == "funds":
            if type(row.get("fundId")) is not int or row["fundId"] < 1:
                raise OriginalEvidenceBlocked("KNF_FUND_ID_INVALID")
        elif kind == "primary_pln_valuations":
            if row.get("currency") != "PLN" or row.get("isPrimary") is not True:
                raise OriginalEvidenceBlocked("KNF_UNIT_CURRENCY_CLASS_INVALID")
            d = _date(row.get("date"))
            if not date(2026, 9, 1) <= d <= date(2026, 9, 30):
                raise OriginalEvidenceBlocked("KNF_DATE_OUT_OF_WINDOW")
            if (not isinstance(row.get("valuationUnitUuid"), str) or
                    not UUID.fullmatch(row["valuationUnitUuid"])):
                raise OriginalEvidenceBlocked("KNF_UNIT_ID_INVALID")
            value = row.get("valuation")
            if (type(value) not in (int, float) or not 0 < value < 1_000_000
                    or value != value or value == float("inf")):
                raise OriginalEvidenceBlocked("KNF_NAV_INVALID")
        elif kind == "kid_units":
            if (not isinstance(row.get("documentUuid"), str)
                    or not UUID.fullmatch(row["documentUuid"])):
                raise OriginalEvidenceBlocked("KNF_KID_ID_INVALID")
            d = _date(row.get("publicationDate"))
            if d > completed_at.date():
                raise OriginalEvidenceBlocked("KNF_FUTURE_KID_PUBLICATION")
    return {
        "source": "UKNF_WYBIERAM_FUNDUSZE_API",
        "endpoint_kind": kind,
        "official_url": KNF_URLS[kind],
        "original_raw_sha256": sha256(raw).hexdigest(),
        "retrieved_at_utc": when,
        "page_records": len(records),
        "reported_total_elements_current_snapshot": pg["totalElements"],
        "record_field_names": sorted(field_keys),
        "provider_rights": "FREE_PUBLIC_API_ATTRIBUTION_NO_OVERLOAD_TERMS_3_2_TO_3_6",
        "source_semantics": (
            "CURRENT_FUND_DIRECTORY_NOT_HISTORICAL_PIT" if kind == "funds"
            else "PLN_PRIMARY_UNIT_NAV_VALUATION_NOT_TOTAL_RETURN" if kind == "primary_pln_valuations"
            else "KID_DOCUMENT_RISK_COSTS_AND_SCENARIOS_NOT_REALIZED_PERFORMANCE"
        ),
        "historical_first_publication_certified": False,
        "total_return_admitted": False,
        "financial_operations": 0,
    }

def inspect_mf_zip_structure(raw: bytes, *, completed_at: datetime) -> dict:
    """Bounded original document metadata only, without reading spreadsheet cells."""
    when = _utc(completed_at)
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_MF_BYTES or not raw.startswith(b"PK\x03\x04"):
        raise OriginalEvidenceBlocked("MF_ORIGINAL_ZIP_REQUIRED")
    try:
        with ZipFile(BytesIO(raw)) as z:
            names = z.namelist()
            if len(names) > 300 or len(names) != len(set(names)):
                raise OriginalEvidenceBlocked("MF_BAD_ZIP_MEMBERS")
            for x in z.infolist():
                if (x.file_size > 6_000_000 or x.compress_size > MAX_MF_BYTES
                        or ".." in x.filename or x.filename.startswith("/")):
                    raise OriginalEvidenceBlocked("MF_ZIP_MEMBER_UNSAFE")
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise OriginalEvidenceBlocked("MF_UNREADABLE_ZIP") from exc
    return {
        "state": "STRUCTURE_ONLY_NOT_XLSX_SEMANTIC_ACCEPTANCE",
        "source": "Ministry of Finance gov.pl official document",
        "sha256": sha256(raw).hexdigest(),
        "size": len(raw),
        "retrieved_at_utc": when,
        "total_zip_members": len(names),
        "content_types": "[Content_Types].xml" in names,
        "workbook_xml": "xl/workbook.xml" in names,
        "worksheets": sum(x.startswith("xl/worksheets/sheet") and x.endswith(".xml") for x in names),
        "vba_members": sum("vbaproject" in x.lower() for x in names),
        "external_links": sum("externallink" in x.lower() for x in names),
        "bin_members": sum(x.endswith(".bin") for x in names),
        "only_printer_settings_binary": all(x.startswith("xl/printerSettings/") for x in names if x.endswith(".bin")),
        "no_source_cells_read": True,
        "financial_operations": 0,
    }

def inspect_mf_workbook(raw: bytes, *, completed_at: datetime) -> dict:
    when = _utc(completed_at)
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_MF_BYTES or not raw.startswith(b"PK\x03\x04"):
        raise OriginalEvidenceBlocked("MF_ORIGINAL_XLSX_REQUIRED")
    try:
        with ZipFile(BytesIO(raw)) as z:
            names = z.namelist()
            if (len(names) > 100 or len(names) != len(set(names)) or
                    "[Content_Types].xml" not in names or
                    "xl/workbook.xml" not in names or
                    not any(n.startswith("xl/worksheets/sheet") and n.endswith(".xml") for n in names) or
                    any("vbaproject" in n.lower() or "externallink" in n.lower()
                        or n.endswith(".bin") and not n.startswith("xl/printerSettings/")
                        for n in names)):
                raise OriginalEvidenceBlocked("MF_XLSX_STRUCTURE_UNSUPPORTED")
            for info in z.infolist():
                if (info.file_size > 4_000_000 or info.compress_size > MAX_MF_BYTES
                        or ".." in info.filename or info.filename.startswith("/")):
                    raise OriginalEvidenceBlocked("MF_ZIP_ENTRY_UNSAFE")
            sheet_count = sum(n.startswith("xl/worksheets/sheet") and n.endswith(".xml") for n in names)
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise OriginalEvidenceBlocked("MF_XLSX_INVALID") from exc
    return {
        "source": "PL_MINISTRY_OF_FINANCE_GOV_PL",
        "original_url": MF_URL,
        "source_document": "SECONDARY_TREASURY_BOND_TRANSACTIONS_BY_MARKET_TYPES",
        "original_raw_sha256": sha256(raw).hexdigest(),
        "retrieved_at_utc": when,
        "size_bytes": len(raw),
        "workbook_worksheet_count": sheet_count,
        "workbook_archive_members": len(names),
        "market_semantics": "OBSERVED_GROSS_TRADING_VOLUME_NOT_PRICE_YIELD_OR_BOND_TOTAL_RETURN",
        "historical_first_publication_certified": False,
        "any_macro_or_script_executed": False,
        "financial_operations": 0,
    }

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("knf", "mf"), required=True)
    parser.add_argument("--allow-public-original-source-read", action="store_true")
    parser.add_argument("--mf-structure-only", action="store_true")
    a = parser.parse_args()
    if not a.allow_public_original_source_read:
        parser.error("Explicit opt-in to original free official HTTP required")
    if a.source == "knf":
        output = [inspect_knf_page(kind, fetch_exact(url), completed_at=datetime.now(timezone.utc))
                  for kind, url in KNF_URLS.items()]
    else:
        raw = fetch_exact(MF_URL)
        output = [(inspect_mf_zip_structure(raw, completed_at=datetime.now(timezone.utc))
                   if a.mf_structure_only else inspect_mf_workbook(raw, completed_at=datetime.now(timezone.utc)))]
    print("ISL_UKNF_MF_OFFICIAL_SOURCE_PROBE=" + json.dumps({
        "schema": SCHEMA, "sources": output,
        "model_admission": [], "historical_pit_certified": False,
        "orders": 0, "database_writes": 0, "financial_operations": 0,
    }, sort_keys=True, separators=(",", ":")))

if __name__ == "__main__":
    main()
