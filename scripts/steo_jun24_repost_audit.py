"""Read-only June 2024 STEO Table 10b Wayback correction evidence.

Compares two fixed, independently timestamped XLSX replay bodies. No disk,
database, model, portfolio or trade effects. Not first-publication PIT proof.
"""
from __future__ import annotations

from datetime import timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
import hashlib
from io import BytesIO
import json
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OFFICE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE = "{http://schemas.openxmlformats.org/package/2006/relationships}"
BASE = "https://www.eia.gov/outlooks/steo/archives/jun24_base.xlsx"
CAPTURES = (
    ("20240613190415", 1024116, "dde84a2e66e7652b75a2db8f6e24059e05d105a4d2dcce59dc1f920a717487c7"),
    ("20241002195759", 1024084, "12cd939ba0d9d6b559d56d40cc0650e99c57d249fff1ecc691af601a2e0de636"),
)
SERIES = ("SNGPRPM", "SNGPRL48")
MAX_BYTES = 3_000_000
MAX_UNCOMPRESSED = 160_000_000
CELL = re.compile(r"[A-Z]{1,3}[1-9][0-9]{0,4}\Z")


class AuditError(ValueError):
    pass


def _xml(raw: bytes):
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise AuditError("Unsafe workbook XML")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise AuditError("Malformed workbook XML") from exc


def _read(z, name, bound=6_000_000):
    try:
        info = z.getinfo(name)
    except KeyError as exc:
        raise AuditError("Required workbook part absent") from exc
    if info.file_size > bound or info.flag_bits & 1:
        raise AuditError("Unsafe workbook part")
    return _xml(z.read(name))


def extract_10b_rows(raw: bytes) -> dict:
    """Read cached numeric cells for exactly the two named official series."""
    if len(raw) > MAX_BYTES or not raw.startswith(b"PK\x03\x04"):
        raise AuditError("Unexpected XLSX size or signature")
    try:
        with ZipFile(BytesIO(raw)) as z:
            members = z.infolist()
            if (len(members) > 650 or
                sum(x.file_size for x in members) > MAX_UNCOMPRESSED or
                any(x.flag_bits & 1 or x.filename.startswith("/") or "\\" in x.filename
                    or ".." in x.filename.split("/") for x in members) or
                len({x.filename for x in members}) != len(members)):
                raise AuditError("Unsafe XLSX archive")
            book = _read(z, "xl/workbook.xml")
            relations = _read(z, "xl/_rels/workbook.xml.rels")
            ids = [s.attrib.get(OFFICE + "id") for s in book.iter(MAIN + "sheet")
                   if re.fullmatch(r"10b(?:tab)?", s.attrib.get("name", ""), re.I)]
            if len(ids) != 1 or not ids[0]:
                raise AuditError("Table 10b named sheet absent or ambiguous")
            paths = [n.attrib for n in relations.iter(PACKAGE + "Relationship")
                     if n.attrib.get("Id") == ids[0]]
            if len(paths) != 1 or paths[0].get("TargetMode") == "External":
                raise AuditError("Untrusted sheet relationship")
            path = paths[0].get("Target", "")
            if path.startswith("/xl/"):
                path = path[1:]
            elif re.fullmatch(r"worksheets/sheet\d+\.xml", path):
                path = "xl/" + path
            if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", path):
                raise AuditError("Untrusted sheet path")
            sheet = _read(z, path, 18_000_000)
            shared = []
            if "xl/sharedStrings.xml" in z.namelist():
                strings = _read(z, "xl/sharedStrings.xml", 12_000_000)
                for si in strings.iter(MAIN + "si"):
                    if len(shared) >= 200_000:
                        raise AuditError("Too many shared strings")
                    shared.append("".join(node.text or "" for node in si.iter(MAIN + "t")))
            result, seen = {}, set()
            for row in sheet.iter(MAIN + "row"):
                values, names = {}, set()
                for c in row.findall(MAIN + "c"):
                    ref = c.attrib.get("r", "")
                    if not CELL.fullmatch(ref) or ref in seen:
                        raise AuditError("Duplicate or invalid cell")
                    seen.add(ref)
                    kind = c.attrib.get("t", "n")
                    v = c.find(MAIN + "v")
                    original = v.text if v is not None else None
                    if kind == "s" and original is not None:
                        try:
                            index = int(original)
                            if index < 0:
                                raise ValueError()
                            label = shared[index].strip()
                        except (ValueError, IndexError) as exc:
                            raise AuditError("Invalid shared-string reference") from exc
                    elif kind == "inlineStr":
                        label = "".join(n.text or "" for n in c.iter(MAIN + "t")).strip()
                    elif kind == "str":
                        label = (original or "").strip()
                    else:
                        label = ""
                    if label in SERIES and re.fullmatch(r"A[1-9][0-9]*", ref):
                        names.add(label)
                    if kind in ("", "n") and original is not None and original.strip():
                        try:
                            number = Decimal(original.strip())
                        except InvalidOperation as exc:
                            raise AuditError("Invalid cached number") from exc
                        if not number.is_finite():
                            raise AuditError("Nonfinite cached cell")
                        formula = c.find(MAIN + "f")
                        values[ref] = {"value": str(number),
                                       "formula": formula.text if formula is not None else None}
                if names:
                    if len(names) != 1 or next(iter(names)) in result:
                        raise AuditError("Target series duplicated or ambiguous")
                    result[next(iter(names))] = values
            if set(result) != set(SERIES):
                raise AuditError("Expected Table 10b series missing")
            if any(len(cells) < 12 for cells in result.values()):
                raise AuditError("Too few target numeric cells")
            return result
    except BadZipFile as exc:
        raise AuditError("Corrupt XLSX") from exc


def verify_replay(stamp: str, length: int, expected_hash: str, opener=urlopen):
    url = f"https://web.archive.org/web/{stamp}id_/{BASE}"
    with opener(Request(url, headers={"User-Agent": "ISL-STEO-Source-Research/1.0"}), timeout=90) as reply:
        final = reply.geturl()
        loc = urlparse(final)
        if (loc.scheme != "https" or loc.hostname != "web.archive.org"
            or loc.path != f"/web/{stamp}id_/{BASE}" or loc.query or loc.fragment):
            raise AuditError("Replay redirected to different capture")
        if reply.status != 200:
            raise AuditError("Replay HTTP status not 200")
        header = reply.headers.get("Memento-Datetime")
        if not header:
            raise AuditError("Missing Memento timestamp")
        try:
            dt = parsedate_to_datetime(header).astimezone(timezone.utc)
        except (TypeError, ValueError) as exc:
            raise AuditError("Invalid Memento timestamp") from exc
        if dt.strftime("%Y%m%d%H%M%S") != stamp:
            raise AuditError("Memento timestamp differs from requested capture")
        raw = reply.read(MAX_BYTES + 1)
    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) != length or digest != expected_hash:
        raise AuditError("Archived RAW bytes differ from previously verified evidence")
    return raw, {"capture_utc": dt.isoformat(), "sha256": digest, "length": len(raw),
                 "source_url": url, "http_status": 200}


def compare_versions(early: dict, late: dict) -> dict:
    results = {}
    for code in SERIES:
        a, b = early[code], late[code]
        changed = []
        value_changes = 0
        for ref in sorted(set(a) | set(b)):
            before, after = a.get(ref), b.get(ref)
            if before != after:
                if before is None or after is None or Decimal(before["value"]) != Decimal(after["value"]):
                    value_changes += 1
                changed.append({"cell": ref, "before": before, "after": after})
        results[code] = {"early_numeric_cells": len(a), "late_numeric_cells": len(b),
                         "compared_cell_positions": len(set(a) | set(b)),
                         "changed_cells_including_formulas": len(changed),
                         "changed_cached_numeric_values": value_changes, "changes": changed}
    return {"status": "STEO_JUN24_TABLE10B_ORIGINAL_CAPTURE_COMPARISON", "series": results,
            "changed_cells_total": sum(r["changed_cells_including_formulas"] for r in results.values()),
            "official_notice": "https://www.eia.gov/outlooks/steo/archives/notice_data_06_27_2024.php",
            "causal_attribution_to_notice_proven": False,
            "historical_first_release_bytes_certified": False,
            "wtibrent_comparison_reperformed": False,
            "database_writes": 0, "orders": 0, "strategy_changes": 0}


def main():
    editions = []
    for specification in CAPTURES:
        raw, receipt = verify_replay(*specification)
        rows = extract_10b_rows(raw)
        print("STEO_JUN24_VERIFIED_REPLAY " + json.dumps(receipt, sort_keys=True), flush=True)
        editions.append(rows)
    print("STEO_JUN24_TABLE10B_REAL_RESULT " +
          json.dumps(compare_versions(*editions), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
