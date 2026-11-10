"""One-shot original publisher DataverseNL Swinkels ODS evidence audit.

This probes ONLY a fixed public DataverseNL dataset DOI registered in B2FIND.
No login, paid data, trading, source mirror, market data API, broker, wallet,
scheduled collection, file export, database write or portfolio model call.

Source metadata and bytes must be obtained before claims of file coverage.
No spreadsheet data values, return numbers or full sheet names are uploaded.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

PUBLISHER = "https://dataverse.nl"
DOI = "10.34894/YWT2IX"
API_ROOT = PUBLISHER + "/api/datasets/:persistentId"
MAX_METADATA_BYTES = 2_000_000
MAX_SOURCE_BYTES = 5_000_000
MAX_UNCOMPRESSED_BYTES = 32_000_000
MAX_ZIP_ENTRIES = 160
SAFE_LABEL = re.compile(r"^[^\x00-\x1f]{0,120}$")
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_(). -]{1,160}$")
OFFICIAL_METADATA = API_ROOT + "/?persistentId=doi%3A" + urllib.parse.quote(DOI, safe="")
OFFICIAL_FILE_LIST = API_ROOT + "/versions/:latest/files?persistentId=doi%3A" + urllib.parse.quote(DOI, safe="")


class SourceUnavailable(RuntimeError):
    pass


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlparse(newurl)
        origin = urllib.parse.urlparse(req.full_url)
        allowed = (target.scheme == "https" and (
            target.hostname == "dataverse.nl"
            or (origin.hostname == "dataverse.nl"
                and target.hostname == "objectstore.surf.nl")
        ))
        if not allowed:
            # Never print presigned URLs, which may contain sensitive signatures.
            host = target.hostname or "MISSING_HOST"
            if len(host) > 160 or not re.fullmatch(r"[A-Za-z0-9.-]+", host):
                host = "UNSAFE_HOSTNAME"
            raise SourceUnavailable("original publisher redirect rejected; destination_host=" + host)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(path, cap):
    parsed = urllib.parse.urlparse(path)
    if parsed.scheme != "https" or parsed.hostname != "dataverse.nl":
        raise SourceUnavailable("only original DataverseNL host permitted")
    opener = urllib.request.build_opener(RestrictedRedirect())
    request = urllib.request.Request(path, headers={
        "User-Agent": "ISL-Swinkels-CCBY-original-file-research/0.1",
        "Accept": "application/json, application/octet-stream",
    })
    try:
        with opener.open(request, timeout=22) as response:
            if response.status != 200:
                raise SourceUnavailable("publisher HTTP status is not 200")
            final = urllib.parse.urlparse(response.geturl())
            if final.scheme != "https" or final.hostname not in (
                    "dataverse.nl", "objectstore.surf.nl"):
                raise SourceUnavailable("unexpected final download host")
            data = response.read(cap + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            OSError) as exc:
        status = getattr(exc, "code", None)
        raise SourceUnavailable(
            f"official publisher access blocked: HTTP_{status}" if status is not None
            else "official publisher access blocked: transport error"
        ) from exc
    if len(data) > cap:
        raise SourceUnavailable("official publisher response exceeds research size bound")
    return data


def parse_api(raw):
    try:
        doc = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SourceUnavailable("publisher response is not JSON") from exc
    if not isinstance(doc, dict) or doc.get("status") != "OK" or not isinstance(
            doc.get("data"), (dict, list)):
        raise SourceUnavailable("publisher API did not return OK structured dataset data")
    return doc["data"]


def discover_files():
    """Do not infer exact version mapping from the *legacy* Erasmus DOI."""
    errors = []
    for url in (OFFICIAL_FILE_LIST, OFFICIAL_METADATA):
        try:
            data = parse_api(fetch(url, MAX_METADATA_BYTES))
            version = data.get("latestVersion", {}) if isinstance(data, dict) else {}
            files = data if isinstance(data, list) else (data.get("files") or version.get("files") or [])
            if not isinstance(files, list) or not files:
                raise SourceUnavailable("official dataset has no exposed file list")
            result = []
            for item in files:
                descriptor = item.get("dataFile", item) if isinstance(item, dict) else {}
                if not isinstance(descriptor, dict):
                    continue
                name = descriptor.get("filename")
                size = descriptor.get("filesize", 0)
                file_id = descriptor.get("id")
                if (isinstance(name, str) and SAFE_FILENAME.fullmatch(name)
                        and type(size) is int and size > 0
                        and type(file_id) is int and file_id > 0):
                    result.append({
                        "name": name,
                        "size": size,
                        "id": file_id,
                        "content_type": descriptor.get("contentType", "NOT_PROVIDED"),
                        "checksum": descriptor.get("checksum"),
                    })
            if not result:
                raise SourceUnavailable("no publisher file descriptions with valid identifiers")
            return result, str(version.get("versionNumber", "NOT_PROVIDED"))
        except SourceUnavailable as exc:
            errors.append(str(exc))
    raise SourceUnavailable("Dataverse original file list unavailable; " + "; ".join(errors))


def _column_cells(row, ns_table):
    cells = []
    for child in row:
        if child.tag not in (ns_table + "table-cell",
                             ns_table + "covered-table-cell"):
            continue
        repeat = child.get(ns_table + "number-columns-repeated", "1")
        if not repeat.isdigit() or not 1 <= int(repeat) <= 1_000_000:
            raise SourceUnavailable("invalid repeated column count")
        # ODS commonly uses a single trailing empty cell repeated thousands of
        # times. Clamp without allocating those cells; the 2020-2022 Return M
        # source columns are within the first 200 cells.
        room = max(0, 200 - len(cells))
        if not room:
            break
        cells.extend([child] * min(int(repeat), room))
    return cells


def _cell_label(cell, ns_text):
    if cell is None:
        return ""
    return " ".join(
        "".join(p.itertext()).strip()
        for p in cell.findall(".//" + ns_text + "p")
    ).strip()


def _country_window_coverage(rows, ns_table, ns_office, ns_text):
    """Only coverage counts for original country Return M, never returns."""
    columns = None
    header_idx = -1
    for idx, row in enumerate(rows[:25]):
        cols = _column_cells(row, ns_table)
        labels = [_cell_label(cell, ns_text) for cell in cols]
        if "observation_date" in labels and "Return M" in labels:
            columns = (labels.index("observation_date"), labels.index("Return M"))
            header_idx = idx
            break
    if columns is None:
        return {"state": "NO_COUNTRY_RETURN_M_HEADER", "months_found": 0}
    dates = {}
    invalid_rows = 0
    duplicate_months = 0
    for row in rows[header_idx + 1:]:
        cols = _column_cells(row, ns_table)
        if max(columns) >= len(cols):
            continue
        date_cell, ret_cell = cols[columns[0]], cols[columns[1]]
        stamp = date_cell.get(ns_office + "date-value")
        if not stamp:
            stamp = _cell_label(date_cell, ns_text)
        if not stamp:
            continue
        parsed = None
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S",
                    "%d-%b-%Y", "%d-%B-%Y"):
            try:
                parsed = datetime.strptime(stamp[:19], fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            continue
        month = f"{parsed.year:04d}-{parsed.month:02d}"
        if not "2020-01" <= month <= "2022-12":
            continue
        if month in dates:
            duplicate_months += 1
            continue
        value_type = ret_cell.get(ns_office + "value-type")
        raw_value = ret_cell.get(ns_office + "value")
        if value_type not in ("float", "currency", "percentage") or not raw_value:
            dates[month] = False
            invalid_rows += 1
            continue
        try:
            number = Decimal(raw_value)
            valid = number.is_finite()
        except InvalidOperation:
            valid = False
        dates[month] = valid
        if not valid:
            invalid_rows += 1
    target = [f"{year}-{month:02d}" for year in range(2020, 2023)
              for month in range(1, 13)]
    missing_months = [month for month in target if month not in dates]
    nonnumeric_months = [month for month in target
                         if month in dates and not dates[month]]
    status = ("COMPLETE_36_SOURCE_RETURN_M_OBSERVATIONS"
              if not missing_months and not nonnumeric_months
              and not duplicate_months and not invalid_rows
              else "INCOMPLETE_OR_AMBIGUOUS_SOURCE_MONTHLY_OBSERVATIONS")
    return {
        "state": status,
        "source_months_found": len(dates),
        "numeric_months": sum(bool(x) for x in dates.values()),
        "missing_months": missing_months,
        "nonnumeric_months": nonnumeric_months,
        "duplicate_months": duplicate_months,
        "unparseable_or_empty_return_rows_in_window": invalid_rows,
        "window": "2020-01..2022-12",
        "return_unit_certified_from_original_methodology": False,
        "historical_point_in_time_certified": False,
    }


def ods_shape(raw):
    """Examine archive format/sheet counts only, not actual market return values."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise SourceUnavailable("original ODS is not a valid ZIP package") from exc
    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ZIP_ENTRIES or sum(e.file_size for e in entries) > MAX_UNCOMPRESSED_BYTES:
            raise SourceUnavailable("publisher ODS violates bounded extraction controls")
        if any(e.filename.startswith("/") or ".." in e.filename.split("/") for e in entries):
            raise SourceUnavailable("publisher ODS has unsafe archive path")
        names = set(archive.namelist())
        if "mimetype" not in names or "content.xml" not in names:
            raise SourceUnavailable("publisher ODS expected mimetype and content.xml")
        if archive.read("mimetype") != b"application/vnd.oasis.opendocument.spreadsheet":
            raise SourceUnavailable("publisher file is not an ODS document")
        xml = archive.read("content.xml")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise SourceUnavailable("original ODS content.xml cannot be parsed") from exc
    ns_table = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    ns_office = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
    ns_text = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    sheets = []
    for table in root.iter(ns_table + "table"):
        rows = list(table.iter(ns_table + "table-row"))
        name = table.attrib.get(ns_table + "name", "")
        if len(name) > 120 or not SAFE_LABEL.fullmatch(name):
            name = "INVALID_NAME"
        labels = []
        date_values = []
        numeric_cells = 0
        for row_no, row in enumerate(rows):
            for cell in row.iter():
                if cell.tag not in (ns_table + "table-cell",
                                    ns_table + "covered-table-cell"):
                    continue
                if cell.get(ns_office + "value-type") in ("float", "currency", "percentage"):
                    numeric_cells += 1
                date_value = cell.get(ns_office + "date-value")
                if date_value and len(date_value) < 40 and re.match(
                        r"^\d{4}-\d{2}-\d{2}", date_value):
                    date_values.append(date_value[:10])
                if row_no >= 10 or len(labels) >= 14:
                    continue
                for paragraph in cell.findall(".//" + ns_text + "p"):
                    label = "".join(paragraph.itertext()).strip()
                    # Human-readable *labels only*. Numeric return values
                    # from the original public workbook must not enter CI logs.
                    if (0 < len(label) <= 70
                            and SAFE_LABEL.fullmatch(label)
                            and re.search("[A-Za-z]", label)
                            and label not in labels):
                        labels.append(label)
                        break
        sheets.append({
            "ordinal": len(sheets) + 1,
            "sheet_name": name,
            "xml_row_nodes": len(rows),
            "numeric_cell_count_without_values": numeric_cells,
            "iso_date_cells": len(date_values),
            "iso_date_min": min(date_values, default=None),
            "iso_date_max": max(date_values, default=None),
            "early_textual_labels_not_observations": labels,
            "number_of_column_definitions": len(
                list(table.iter(ns_table + "table-column"))),
            "return_m_2020_2022_coverage": _country_window_coverage(
                rows, ns_table, ns_office, ns_text),
        })
    if not sheets:
        raise SourceUnavailable("original ODS has no spreadsheet table nodes")
    return sheets


def main():
    print("ISL_SOURCE_PUBLISHER=DataverseNL", flush=True)
    print("ISL_SWINKELS_PERSISTENT_ID=doi:" + DOI, flush=True)
    try:
        files, version = discover_files()
        public_files = [{
            "filename": f["name"], "bytes_claimed": f["size"],
            "file_id": f["id"], "mime": f["content_type"],
            "checksum_supplied": bool(f["checksum"]),
        } for f in files]
        print("ISL_SWINKELS_OFFICIAL_FILE_LIST=" + json.dumps(public_files, sort_keys=True), flush=True)
        print("ISL_SWINKELS_OFFICIAL_VERSION_FIELD=" + version, flush=True)
        candidates = [f for f in files if f["name"].lower().endswith(".ods")]
        if len(candidates) != 1:
            raise SourceUnavailable("expected exactly one source ODS file")
        source = candidates[0]
        if source["size"] > MAX_SOURCE_BYTES:
            raise SourceUnavailable("original file exceeds 5MB source admission limit")
        raw = fetch(PUBLISHER + "/api/access/datafile/" + str(source["id"]),
                    MAX_SOURCE_BYTES)
        if len(raw) != source["size"]:
            raise SourceUnavailable("download byte length disagrees with publisher metadata")
        shapes = ods_shape(raw)
        print("ISL_SWINKELS_OFFICIAL_BYTES_VERIFIED=true", flush=True)
        print("ISL_SWINKELS_ODS_FILENAME=" + source["name"], flush=True)
        print("ISL_SWINKELS_ODS_BYTE_COUNT=" + str(len(raw)), flush=True)
        print("ISL_SWINKELS_ODS_SHA256=" + hashlib.sha256(raw).hexdigest(), flush=True)
        print("ISL_SWINKELS_ODS_SCHEMA_ONLY=" + json.dumps(shapes, sort_keys=True), flush=True)
        print("ISL_SWINKELS_CCBY_PUBLISHER_LANDING_REVIEW_REQUIRED", flush=True)
        print("ISL_SWINKELS_RETURN_UNITS_NOT_YET_CHECKED", flush=True)
        print("ISL_SWINKELS_MONTHLY_COVERAGE_NOT_YET_CHECKED", flush=True)
        print("ISL_SWINKELS_COUNTRY_PL_NOT_PRESENT", flush=True)
        print("ISL_SWINKELS_QUALIFIED_M1_M2_M3_SERIES=0", flush=True)
    except SourceUnavailable as exc:
        print("ISL_SWINKELS_OFFICIAL_ORIGINAL_READ=BLOCKED", flush=True)
        print("ISL_SWINKELS_BLOCKER=" + str(exc), flush=True)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
