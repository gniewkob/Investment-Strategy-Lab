"""Independent EIA STEO source-version comparison using a dated 2025 Zenodo ZIP.

Pure offline original-file analysis. Does not access network, disk, databases,
markets, portfolios or schedule tasks. Original 2024 STEO publication-day bytes
remain NOT certified by a third-party May 2025 deposit.
"""
from __future__ import annotations

from hashlib import md5, sha256
from io import BytesIO
import re
from zipfile import ZipFile, BadZipFile

from src.isl_v2.eia_sources import SourceFormatError

ZENODO_RECORD_ID=15386905
ZENODO_RELEASE_DAY="2025-05-26"
PARTITION_BUNDLE_MD5={
    2022:"cff52df8d14f214df0c1a47a0a3185e7",
    2023:"0f59168a86433af4e0e7be53c4684535",
    2024:"21b1dc10ba6503b4446143e212ada2a0",
}
MAX_YEAR_ZIP_BYTES=56_000_000
MAX_MEMBER_BYTES=16_000_000
MAX_UNCOMPRESSED_YEAR=1_200_000_000
CODES="jan feb mar apr may jun jul aug sep oct nov dec".split()
NAME_RE=re.compile(r"20(?:22|23|24)-(?:0[1-9]|1[012])/[a-z]{3}(?:22|23|24)_base\.xlsx\Z")


def check_2025_zenodo_year_archive(year: int, zip_data: bytes,
                                    oct2026_issuer_sha: dict[str,str]) -> dict:
    """Compare 2025-deposited original XLSX SHA with real Oct2026 EIA hashes.

    No extrapolation of historical original-release PIT from a May2025
    independent deposit. For any mismatch, the true result is a DIFFERENCE
    requiring source analysis, not automatic confirmation of a price revision.
    """
    if year not in PARTITION_BUNDLE_MD5:
        raise SourceFormatError("Only 2022-2024 predeclared Zenodo source partitions")
    if not 100 < len(zip_data) <= MAX_YEAR_ZIP_BYTES:
        raise SourceFormatError("Archive compressed byte bounds invalid")
    if md5(zip_data).hexdigest() != PARTITION_BUNDLE_MD5[year]:
        raise SourceFormatError("Zenodo original version 2.0 year ZIP MD5 mismatch")
    expected_issues={m+str(year)[2:] for m in CODES}
    if set(oct2026_issuer_sha) != expected_issues or any(
        re.fullmatch("[a-f0-9]{64}",str(val)) is None
        for val in oct2026_issuer_sha.values()
    ):
        raise SourceFormatError("Original 2026 EIA issuance digest inventory incomplete")
    try:
        with ZipFile(BytesIO(zip_data)) as z:
            info=z.infolist()
            if (not 1<=len(info)<=120 or
                    sum(x.file_size for x in info)>MAX_UNCOMPRESSED_YEAR or
                    any(x.flag_bits & 1 or x.filename.startswith("/") or
                        "\\" in x.filename or ".." in x.filename.split("/")
                        for x in info)):
                raise SourceFormatError("Zenodo zip member directory unsafe")
            entries=[x for x in info if x.filename.endswith("_base.xlsx")]
            member_by_issue={}
            for x in entries:
                if not NAME_RE.fullmatch(x.filename):
                    raise SourceFormatError("Undocumented Zenodo original STEO XLSX name")
                month_part,basename=x.filename.split("/")
                issue=basename.removesuffix("_base.xlsx")
                expected_prefix=f"{year:04d}-{CODES.index(issue[:3])+1:02d}"
                if issue not in expected_issues or month_part != expected_prefix or issue in member_by_issue:
                    raise SourceFormatError("STE0 source member year/month identity conflict")
                if not 1 <= x.file_size <= MAX_MEMBER_BYTES:
                    raise SourceFormatError("Original STEO XLSX member outside bounded size")
                member_by_issue[issue]=x
            if set(member_by_issue)!=expected_issues:
                raise SourceFormatError("Missing exactly twelve monthly raw XLSX source members")

            members=[]
            for issue in [m+str(year)[2:] for m in CODES]:
                file=member_by_issue[issue]
                raw=z.read(file)
                if not raw.startswith(b"PK\x03\x04"):
                    raise SourceFormatError("Archive member is not source XLSX")
                found=sha256(raw).hexdigest()
                comparison=oct2026_issuer_sha[issue]
                members.append({
                    "issue":issue,
                    "original_xlsx_source_in_2025_deposit":file.filename,
                    "original_xlsx_byte_count":len(raw),
                    "zenodo_may2025_original_xlsx_sha256":found,
                    "eia_oct2026_original_xlsx_sha256":comparison,
                    "exact_xlsx_bytes_match":found==comparison,
                    "historical_original_issue_day_PIT_certified":False,
                })
            return {
                "status":"ZENODO_2025_THIRD_PARTY_RAW_XLSX_VS_EIA_2026_BYTE_COMPARISON",
                "zenodo_record_id":ZENODO_RECORD_ID,
                "zenodo_version_published_day":ZENODO_RELEASE_DAY,
                "source_year":year,
                "year_zip_md5_matches_2025_record":True,
                "year_zip_sha256_acquired_today":sha256(zip_data).hexdigest(),
                "source_original_xlsx_count":len(members),
                "byte_identical_xlsx_count":sum(m["exact_xlsx_bytes_match"] for m in members),
                "byte_different_xlsx_count":sum(not m["exact_xlsx_bytes_match"] for m in members),
                "members":members,
                "original_2022_2024_issue_day_PIT_certified":False,
                "independent_source_snapshot_evidence_not_before":"2025-05-26",
                "data_numeric_quotes_extracted":0,
                "database_connections":0,"database_writes":0,
                "orders":0,"paper_allocations_changed":0,
            }
    except BadZipFile as exc:
        raise SourceFormatError("Invalid Zenodo third party archive ZIP") from exc


def consolidate_zenodo_audits(items: list[dict]) -> dict:
    if len(items)!=3 or {x.get("source_year") for x in items}!={2022,2023,2024}:
        raise SourceFormatError("Must confirm exactly three independent source years")
    if any(x.get("status")!="ZENODO_2025_THIRD_PARTY_RAW_XLSX_VS_EIA_2026_BYTE_COMPARISON"
           or x.get("source_original_xlsx_count")!=12
           or x.get("year_zip_md5_matches_2025_record") is not True
           or x.get("original_2022_2024_issue_day_PIT_certified") is not False
           for x in items):
        raise SourceFormatError("Third-party source proof acceptance prerequisites absent")
    members=[x for entry in items for x in entry["members"]]
    if len(members)!=36 or len(set(x["issue"] for x in members))!=36:
        raise SourceFormatError("Thirty-six source issue identities not unique")
    return {
        "status":"STEO_INDEPENDENT_ZENODO_2025_THIRTY_SIX_SOURCE_PROVENANCE_AUDIT",
        "third_party_record":ZENODO_RECORD_ID,
        "third_party_publication_day":ZENODO_RELEASE_DAY,
        "source_annual_archives":3,
        "source_original_xlsx_compared":len(members),
        "exact_byte_matches":sum(x["exact_xlsx_bytes_match"] for x in members),
        "different_bytes_requiring_semantic_review":[x["issue"] for x in members
                                                    if not x["exact_xlsx_bytes_match"]],
        "third_party_deposit_certifies_exact_source_bytes_on_original_EIA_release_day":False,
        "no_changes_beyond_zenodo_date_certified":False,
        "historical_first_publication_point_in_time_certified":False,
        "source_2025_snapshot_timestamp":"2025-05-26",
        "database_connections":0,"database_writes":0,"orders":0,
        "paper_allocations_changed":0,"source_binaries_persisted":0,
        "scheduled_jobs_created":0,
    }
