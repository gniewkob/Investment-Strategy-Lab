"""Offline official EIA STEO correction notices: no invented PIT or quote revisions."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from io import StringIO
import json
from unittest import TestCase
from unittest.mock import patch

from scripts import steo_official_notice_audit as notice
from src.isl_v2.eia_sources import SourceFormatError


class STEOOfficialErrataEvidenceTests(TestCase):
    def test_issue_catalog_unchanged_and_count_58(self):
        result=notice.audit_steo_notices()
        self.assertEqual(result["issue_count"],58)
        self.assertEqual(result["official_notices_read_and_curated"],9)
        self.assertEqual(result["issues_with_notices"],9)
        self.assertEqual(result["issues_with_documented_report_repost"],7)
        self.assertEqual(len(result["per_issue"]),58)
        self.assertFalse(result["historical_original_xlsx_bytes_pit_certified"])
        self.assertFalse(result["wtibrent_table2_revision_proven_by_these_notices"])
        self.assertFalse(result["official_notice_is_independent_byte_archive"])
        for k in ("database_connections","database_writes","real_orders",
                  "paper_allocations_changed","external_http_requests","file_creations"):
            self.assertEqual(result[k],0)

    def test_november_2023_and_january_2025_reposts_are_not_table2_proof(self):
        for issue,scope in (("nov23","DATA_TABLES_4A_3A_3D_PETROLEUM_CONSUMPTION"),
                            ("jan25","DATA_TABLE_3E_GDP_AND_USD_INDEX")):
            result=notice.edition_status(issue)
            self.assertTrue(result["edition_repost_officially_documented"])
            self.assertTrue(result["non_table2_data_repost_officially_documented"])
            self.assertEqual(result["official_notices_evaluated"],1)
            self.assertEqual(result["notices"][0]["scope"],scope)
            self.assertFalse(result["notices"][0]["xlsx_reposted_proven"])
            self.assertFalse(result["table2_wti_brent_revision_independently_proven"])
            self.assertFalse(result["historical_point_in_time_certified"])

    def test_supplement_pdf_only_and_future_correction_are_distinct(self):
        cases={
            "oct22":("WINTER_FUELS_SUPPLEMENT_CORRECTION",False),
            "feb25":("STEO_PDF_ONLY_REPOST",True),
            "dec25":("STEO_ERROR_CORRECTION_NEXT_ISSUE",False),
        }
        for issue,(expected,reposted) in cases.items():
            item=notice.edition_status(issue)
            self.assertEqual(item["notices"][0]["type"],expected)
            self.assertEqual(item["edition_repost_officially_documented"],reposted)
            self.assertFalse(item["table2_wti_brent_revision_independently_proven"])

    def test_no_known_curated_notice_does_not_certify_pit(self):
        item=notice.edition_status("feb24")
        self.assertEqual(item["official_notices_evaluated"],0)
        self.assertEqual(item["status"],"NO_CURATED_OFFICIAL_NOTICE_NOT_PIT_EVIDENCE")
        self.assertFalse(item["absence_of_notice_proves_no_revision"])
        self.assertFalse(item["historical_point_in_time_certified"])

    def test_unrecognized_issue_and_source_url_spoof_are_rejected(self):
        with self.assertRaisesRegex(SourceFormatError,"outside previously verified"):
            notice.edition_status("apr21")
        fake=deepcopy(notice.OFFICIAL_NOTICES[0])
        fake["url"]="https://www.eia.gov.attacker.example/outlooks/steo/archives/notice_data_10_26_2022.php"
        with patch.object(notice,"OFFICIAL_NOTICES",(fake,)):
            with self.assertRaisesRegex(SourceFormatError,"official EIA"):
                notice.verify_notice_registry()

    def test_forged_early_timestamp_and_duplicate_fail(self):
        fake=deepcopy(notice.OFFICIAL_NOTICES[0])
        fake["notice_date"]="2022-01-01"
        with patch.object(notice,"OFFICIAL_NOTICES",(fake,)):
            with self.assertRaisesRegex(SourceFormatError,"predates"):
                notice.verify_notice_registry()
        with patch.object(notice,"OFFICIAL_NOTICES",(notice.OFFICIAL_NOTICES[0],
                                                    notice.OFFICIAL_NOTICES[0])):
            with self.assertRaisesRegex(SourceFormatError,"duplicate"):
                notice.verify_notice_registry()

    def test_cli_is_offline_read_only_and_json_safe(self):
        out=StringIO()
        with redirect_stdout(out):
            self.assertEqual(notice.main(["--issue","nov23"]),0)
        res=json.loads(out.getvalue())
        self.assertEqual(res["issue"],"nov23")
        self.assertFalse(res["historical_point_in_time_certified"])
        errors=StringIO()
        with redirect_stderr(errors):
            self.assertEqual(notice.main(["--issue","not_real"]),2)
        self.assertEqual(errors.getvalue().strip(),
                         "STEO_OFFICIAL_NOTICE_PROVENANCE_FAILED")
