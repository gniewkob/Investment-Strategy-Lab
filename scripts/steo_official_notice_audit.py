"""Official EIA STEO dated correction-notice research register.

Read-only curated citations to official EIA notice pages. Classification is
per edition and affected table: a report re-post is NOT proof that Table 2's
WTI or Brent price data changed. No known notice is NOT proof of unmodified
historical original bytes or original availability (PIT).
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from urllib.parse import urlparse

from scripts.steo_historical_archive import catalog
from scripts.steo_prior_period_validation import prior_catalog
from src.isl_v2.eia_sources import SourceFormatError

# Independently checked public EIA official notice text, 20 October 2026.
# Only items whose body and issue assignment were actually examined.
# "scope" is deliberately a narrower evidence assertion than "XLSX changed".
OFFICIAL_NOTICES = (
    {
        "issue":"oct22",
        "notice_date":"2022-10-26",
        "url":"https://www.eia.gov/outlooks/steo/archives/notice_data_10_26_2022.php",
        "type":"WINTER_FUELS_SUPPLEMENT_CORRECTION",
        "scope":"WINTER_FUELS_OUTLOOK_HEATING_OIL_EXPENDITURE_TABLE",
        "table2_wti_brent_change_proven":False,
        "edition_reposted":False,
        "xlsx_reposted_proven":False,
        "detail":"October Winter Fuels Outlook supplementary expenditure table corrected; not STEO Table 2.",
    },
    {
        "issue":"feb23",
        "notice_date":"2023-02-08",
        "url":"https://www.eia.gov/outlooks/steo/archives/notice_data_02_08_2023.php",
        "type":"STEO_TEXT_REPOST",
        "scope":"TEXT_NATURAL_GAS_PRODUCTION_RECORD_CLAIM",
        "table2_wti_brent_change_proven":False,
        "edition_reposted":True,
        "xlsx_reposted_proven":False,
        "detail":"Correction to narrative claim about natural gas production; report reposted.",
    },
    {
        "issue":"may23",
        "notice_date":"2023-05-09",
        "url":"https://www.eia.gov/outlooks/steo/archives/notice_data_05_09_2023.php",
        "type":"STEO_TEXT_REPOST",
        "scope":"TEXT_SUMMER_TEMPERATURE_COMPARISON",
        "table2_wti_brent_change_proven":False,
        "edition_reposted":True,
        "xlsx_reposted_proven":False,
        "detail":"Same-day correction to summer temperature comparison; report reposted.",
    },
    {
        "issue":"nov23",
        "notice_date":"2023-11-09",
        "url":"https://www.eia.gov/outlooks/steo/archives/notice_data_11_09_2023.php",
        "type":"STEO_DATA_REPOST",
        "scope":"DATA_TABLES_4A_3A_3D_PETROLEUM_CONSUMPTION",
        "table2_wti_brent_change_proven":False,
        "edition_reposted":True,
        "xlsx_reposted_proven":False,
        "detail":"Corrected 2022 petroleum consumption in tables 4a, 3a, 3d; report reposted two days later.",
    },
    {
        "issue":"jun24",
        "notice_date":"2024-06-27",
        "url":"https://www.eia.gov/outlooks/steo/archives/notice_data_06_27_2024.php",
        "type":"STEO_DATA_REPOST",
        "scope":"DATA_TABLE_10B_SHALE_NATURAL_GAS",
        "table2_wti_brent_change_proven":False,
        "edition_reposted":True,
        "xlsx_reposted_proven":False,
        "detail":"Corrected Permian and total shale natural-gas production in table 10b, June report reposted.",
    },
    {
        "issue":"nov24",
        "notice_date":"2024-11-14",
        "url":"https://www.eia.gov/outlooks/steo/archives/notice_data_11_14_2024.php",
        "type":"STEO_DATA_REPOST",
        "scope":"DATA_TABLE_10B_TIGHT_OIL_SHALE_GAS_PRODUCTION",
        "table2_wti_brent_change_proven":False,
        "edition_reposted":True,
        "xlsx_reposted_proven":False,
        "detail":"November report reposted with corrections to four production series in table 10b.",
    },
    {
        "issue":"jan25",
        "notice_date":"2025-01-15",
        "url":"https://www.eia.gov/outlooks/steo/archives/notice_data_01_15_2025.php",
        "type":"STEO_DATA_REPOST",
        "scope":"DATA_TABLE_3E_GDP_AND_USD_INDEX",
        "table2_wti_brent_change_proven":False,
        "edition_reposted":True,
        "xlsx_reposted_proven":False,
        "detail":"Notice mentions incorrect November Table 3e data, but explicitly says January STEO was reposted Jan 15. Review issue attribution if using affected Table 3e.",
    },
    {
        "issue":"feb25",
        "notice_date":"2025-02-12",
        "url":"https://www.eia.gov/outlooks/steo/archives/notice_data_02_12_2025.php",
        "type":"STEO_PDF_ONLY_REPOST",
        "scope":"PDF_TABLE_3A_ONLY",
        "table2_wti_brent_change_proven":False,
        "edition_reposted":True,
        "xlsx_reposted_proven":False,
        "detail":"Notice says February PDF report was reposted after Table 3a error; no XLSX republication asserted.",
    },
    {
        "issue":"dec25",
        "notice_date":"2025-12-18",
        "url":"https://www.eia.gov/outlooks/steo/archives/notice_data_12_18_2025.php",
        "type":"STEO_ERROR_CORRECTION_NEXT_ISSUE",
        "scope":"HISTORICAL_PERMIAN_CRUDE_OUTPUT_REGION_BREAKOUT",
        "table2_wti_brent_change_proven":False,
        "edition_reposted":False,
        "xlsx_reposted_proven":False,
        "detail":"December notice identifies historical regional crude output error; correction scheduled for January 2026 edition.",
    },
)

def allowed_editions() -> dict:
    overlap = set(prior_catalog()) & set(catalog())
    if overlap:
        raise SourceFormatError("Official STEO issue catalogs overlap")
    return {**prior_catalog(), **catalog()}


def verify_notice_registry() -> None:
    valid = allowed_editions()
    seen = set()
    for item in OFFICIAL_NOTICES:
        issue=item["issue"]
        if issue not in valid or issue in seen:
            raise SourceFormatError("Notice mapped to unknown or duplicate source issue")
        seen.add(issue)
        if date.fromisoformat(item["notice_date"]) < date.fromisoformat(valid[issue]["official_release_day"]):
            raise SourceFormatError("Correction notice predates original official issue release")
        u=urlparse(item["url"])
        if (u.scheme != "https" or u.hostname != "www.eia.gov" or
                not u.path.startswith("/outlooks/steo/archives/notice_data_") or
                not u.path.endswith(".php") or u.query or u.fragment):
            raise SourceFormatError("Correction evidence is not an exact official EIA notice URL")
        if (type(item["table2_wti_brent_change_proven"]) is not bool or
                type(item["edition_reposted"]) is not bool or
                type(item["xlsx_reposted_proven"]) is not bool):
            raise SourceFormatError("Non-boolean official-source claim")
        if item["xlsx_reposted_proven"] and not item["edition_reposted"]:
            raise SourceFormatError("Original Excel republication claim inconsistent")


def edition_status(issue: str) -> dict:
    valid=allowed_editions()
    if issue not in valid:
        raise SourceFormatError("Issue outside previously verified historic EIA period")
    notices=[{k:v for k,v in n.items()} for n in OFFICIAL_NOTICES if n["issue"]==issue]
    any_reposted=any(n["edition_reposted"] for n in notices)
    any_data=any(n["type"]=="STEO_DATA_REPOST" for n in notices)
    return {
        "issue":issue,
        "official_listed_release_day":valid[issue]["official_release_day"],
        "official_notices_evaluated":len(notices),
        "notices":notices,
        "edition_repost_officially_documented":any_reposted,
        "non_table2_data_repost_officially_documented":any_data,
        "table2_wti_brent_revision_independently_proven":False,
        "xlsx_original_first_release_bytes_proven":False,
        "historical_point_in_time_certified":False,
        "absence_of_notice_proves_no_revision":False,
        "status":("OFFICIAL_EIA_CORRECTION_NOTICE_REQUIRES_SCOPE_REVIEW"
                  if notices else "NO_CURATED_OFFICIAL_NOTICE_NOT_PIT_EVIDENCE"),
    }


def audit_steo_notices() -> dict:
    verify_notice_registry()
    out=[edition_status(issue) for issue in allowed_editions()]
    noticed=[x for x in out if x["official_notices_evaluated"]]
    return {
        "status":"STEO_OFFICIAL_NOTICE_SCOPE_PROVENANCE_READ_ONLY_AUDIT",
        "issue_count":len(out),
        "official_notices_read_and_curated":len(OFFICIAL_NOTICES),
        "issues_with_notices":len(noticed),
        "issues_with_documented_report_repost":sum(x["edition_repost_officially_documented"] for x in out),
        "official_notice_is_independent_byte_archive":False,
        "historical_original_xlsx_bytes_pit_certified":False,
        "wtibrent_table2_revision_proven_by_these_notices":False,
        "scope_note":"An EIA report republication for another table does not establish WTI/Brent Table 2 prices changed or remained unchanged.",
        "per_issue":out,
        "database_connections":0,"database_writes":0,"real_orders":0,
        "paper_allocations_changed":0,"external_http_requests":0,"file_creations":0,
        "scheduled":False,
    }

def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description="Offline official EIA STEO correction-notice evidence only")
    p.add_argument("--issue",help="Optional official issue code, e.g. nov23")
    args=p.parse_args(argv)
    try:
        verify_notice_registry()
        report = edition_status(args.issue) if args.issue else audit_steo_notices()
        print(json.dumps(report,sort_keys=True,ensure_ascii=False,separators=(",",":")))
        return 0
    except SourceFormatError:
        print("STEO_OFFICIAL_NOTICE_PROVENANCE_FAILED",file=__import__("sys").stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
