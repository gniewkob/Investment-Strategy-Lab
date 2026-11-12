"""Independent DOI-registry crosswalk for original Swinkels dataset lineage.

Reads only two public DataCite DOI JSON metadata records. It never downloads
bond returns, XLSX, ODS, PDF, figures, credentials, or source file variants.
A same-name/size/DOI-chain match supports migration provenance, NEVER an
identical-bytes or historical point-in-time claim. Research-only.
"""
from __future__ import annotations

import json
import re
import sys
from urllib import error, parse, request

HISTORIC_DOI = "10.25397/eur.8152748.v6"
HISTORIC_BASE_DOI = "10.25397/eur.8152748"
CURRENT_DOI = "10.34894/ywt2ix"
HISTORIC_SIZE = 1040468
ODS_SIZE = 913425
README_SIZE = 127043
ODS_SOURCE_SHA256 = "90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847"
TITLE = "Historical Data: International monthly government bond returns"
AUTHOR = "Swinkels, Laurens"
MAX_METADATA_BYTES = 256000
DOI_API = "https://api.datacite.org/dois/"
ALLOWED_URLS = frozenset(DOI_API + parse.quote(s, safe="") for s in (
    HISTORIC_DOI, CURRENT_DOI,
))


class CrosswalkBlocked(ValueError):
    """The primary-source metadata does not prove the expected DOI chain."""


def _attributes(record, expected_doi):
    if not isinstance(record, dict) or not isinstance(record.get("data"), dict):
        raise CrosswalkBlocked("DOI_METADATA_MISSING")
    data = record["data"]
    attrs = data.get("attributes")
    if not isinstance(attrs, dict) or (
        str(attrs.get("doi", "")).lower() != expected_doi
    ):
        raise CrosswalkBlocked("DOI_IDENTITY_MISMATCH")
    return attrs


def _has_rights(attrs):
    rights = attrs.get("rightsList")
    return (isinstance(rights, list) and
            any(isinstance(x, dict) and x.get("rightsIdentifier") == "cc-by-4.0"
                for x in rights))


def _canonical_creator_and_title(attrs):
    creators, titles = attrs.get("creators"), attrs.get("titles")
    return (isinstance(creators, list) and
            any(isinstance(c, dict) and c.get("name") == AUTHOR for c in creators)
            and isinstance(titles, list)
            and any(isinstance(t, dict) and t.get("title") == TITLE for t in titles))


def _is_old_base_linked_in_legacy(attrs):
    linked = attrs.get("relatedIdentifiers")
    return isinstance(linked, list) and any(
        isinstance(x, dict) and x.get("relationType") == "IsIdenticalTo"
        and str(x.get("relatedIdentifier", "")).lower() == HISTORIC_BASE_DOI
        and x.get("relatedIdentifierType") == "DOI"
        for x in linked)


def _is_old_base_linked_in_current(attrs):
    items = list(attrs.get("alternateIdentifiers") or []) + list(
        attrs.get("identifiers") or []
    )
    return any(
        isinstance(x, dict)
        and str(x.get("alternateIdentifier", x.get("identifier", ""))).lower()
            == "https://doi.org/" + HISTORIC_BASE_DOI
        for x in items)


def _sizes(attrs, old):
    sizes = attrs.get("sizes")
    if not isinstance(sizes, list) or len(sizes) != (1 if old else 2):
        raise CrosswalkBlocked("PUBLISHER_FILE_SIZE_LIST_MISSING")
    strings = []
    for value in sizes:
        if not isinstance(value, str):
            raise CrosswalkBlocked("INVALID_PACKAGE_SIZE")
        pattern = r"([0-9]+) Bytes" if old else r"([0-9]+)"
        match = re.fullmatch(pattern, value)
        if not match:
            raise CrosswalkBlocked("INVALID_PACKAGE_SIZE")
        number = int(match.group(1))
        if number <= 0 or number > 5_000_000:
            raise CrosswalkBlocked("INVALID_PACKAGE_SIZE")
        strings.append(number)
    return sorted(strings)


def audit(historic, current):
    """Verify actual primary registry lineage, never bytes or vintage PIT."""
    old = _attributes(historic, HISTORIC_DOI)
    new = _attributes(current, CURRENT_DOI)
    if (not _canonical_creator_and_title(old) or
            not _canonical_creator_and_title(new)):
        raise CrosswalkBlocked("PUBLISHER_TITLE_AUTHOR_MISMATCH")
    if not _has_rights(old) or not _has_rights(new):
        raise CrosswalkBlocked("PUBLISHER_CCBY_LICENSE_MISSING")
    if (not _is_old_base_linked_in_legacy(old)
            or not _is_old_base_linked_in_current(new)
            or str(old.get("url", "")).lower() !=
               "https://doi.org/" + CURRENT_DOI):
        raise CrosswalkBlocked("PUBLISHER_DOI_CROSSWALK_MISSING")
    size_old = _sizes(old, True)[0]
    size_new = _sizes(new, False)
    if (size_old != HISTORIC_SIZE
            or size_new != sorted((ODS_SIZE, README_SIZE))
            or sum(size_new) != size_old):
        raise CrosswalkBlocked("PUBLISHER_PACKAGE_SIZE_MISMATCH")
    if (old.get("publicationYear") != 2023
            or new.get("publicationYear") != 2025
            or new.get("version") != "1.0"):
        raise CrosswalkBlocked("PUBLISHER_VERSION_CHRONOLOGY_MISMATCH")
    dates = new.get("dates")
    if (not isinstance(dates, list)
            or not any(isinstance(d, dict) and
                       d.get("dateType") == "Available" and
                       d.get("date") == "2025-08-22" for d in dates)):
        raise CrosswalkBlocked("PUBLISHER_RELEASE_DATE_MISSING")

    return {
        "receipt": "ISL_SWINKELS_DATACITE_LINEAGE_V01",
        "historic_erasmus_doi": HISTORIC_DOI,
        "current_dataverse_doi": CURRENT_DOI,
        "historic_package_size": size_old,
        "current_original_file_sizes": size_new,
        "package_size_match": True,
        "metadata_doi_and_author_lineage_confirmed": True,
        "publisher_license": "CC-BY-4.0",
        "historical_record_publication_year": 2023,
        "dataverse_dataset_available_date": "2025-08-22",
        "current_ods_sha256_pinned_by_separate_real_source_audit": ODS_SOURCE_SHA256,
        "old_v6_file_checksums_accessible_in_this_audit": False,
        "old_v6_and_new_dataverse_bytes_identical": False,
        "first_available_at_for_historic_months_confirmed": False,
        "historical_pit_certified": False,
        "eligible_pln_bond_total_return": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


class _SameHostRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = parse.urlsplit(newurl)
        if target.scheme != "https" or target.hostname != "api.datacite.org":
            raise CrosswalkBlocked("UNTRUSTED_METADATA_REDIRECT")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_doi_metadata(url):
    if url not in ALLOWED_URLS:
        raise CrosswalkBlocked("UNAUTHORIZED_METADATA_URL")
    opener = request.build_opener(_SameHostRedirect())
    req = request.Request(url, headers={
        "Accept": "application/vnd.api+json",
        "User-Agent": "Investment-Strategy-Lab-source-lineage/1.0",
    })
    try:
        with opener.open(req, timeout=22) as response:
            if (response.status != 200 or
                    parse.urlsplit(response.geturl()).hostname != "api.datacite.org"):
                raise CrosswalkBlocked("PUBLISHER_METADATA_ACCESS_REJECTED")
            data = response.read(MAX_METADATA_BYTES + 1)
    except (error.HTTPError, error.URLError, TimeoutError, OSError) as exc:
        raise CrosswalkBlocked("PUBLISHER_METADATA_UNAVAILABLE") from exc
    if len(data) > MAX_METADATA_BYTES:
        raise CrosswalkBlocked("PUBLISHER_METADATA_OVERSIZED")
    try:
        payload = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise CrosswalkBlocked("PUBLISHER_METADATA_INVALID_JSON") from exc
    if not isinstance(payload, dict):
        raise CrosswalkBlocked("PUBLISHER_METADATA_INVALID_SHAPE")
    return payload


def main():
    old = fetch_doi_metadata(DOI_API + parse.quote(HISTORIC_DOI, safe=""))
    new = fetch_doi_metadata(DOI_API + parse.quote(CURRENT_DOI, safe=""))
    print("SWINKELS_DATACITE_DOI_LINEAGE=" + json.dumps(audit(old, new), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except CrosswalkBlocked as exc:
        print("SWINKELS_DATACITE_DOI_LINEAGE=BLOCKED: " + str(exc))
        sys.exit(2)
