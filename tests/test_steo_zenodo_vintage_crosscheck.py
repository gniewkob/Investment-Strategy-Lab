"""Offline 2025-deposited EIA STEO original-byte 2026 cross-check tests."""
from __future__ import annotations

from hashlib import md5,sha256
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from scripts import steo_zenodo_vintage_crosscheck as x
from src.isl_v2.eia_sources import SourceFormatError


def fixture(year: int, *, omit=None, change=None):
    data=BytesIO()
    known={}
    with ZipFile(data,"w",ZIP_DEFLATED) as z:
        for i,month in enumerate(x.CODES,1):
            issue=month+str(year)[-2:]
            raw=b"PK\x03\x04" + f"FAKE_SOURCE_ONLY:{year}:{i:02d}".encode()
            # Source hash is calculated from test bytes, not from invented EIA
            # quotes, and compared against exactly identical actual raw bytes.
            known[issue]=sha256(raw).hexdigest()
            original=raw+b"-later_oct2026" if issue==change else raw
            if issue!=omit:
                z.writestr(f"{year}-{i:02d}/{issue}_base.xlsx",original)
                z.writestr(f"{year}-{i:02d}/{issue}.pdf",b"%PDF-1.7\nFIXTURE")
    return data.getvalue(),known


class ThirdPartyEIASourceVintageTests(TestCase):
    def test_2025_archive_thirty_six_raw_months_match_all_original_sha(self):
        reports=[]
        with patch.dict(x.PARTITION_BUNDLE_MD5,{},clear=False):
            for year in (2022,2023,2024):
                raw,known=fixture(year)
                with patch.dict(x.PARTITION_BUNDLE_MD5,{year:md5(raw).hexdigest()}):
                    report=x.check_2025_zenodo_year_archive(year,raw,known)
                self.assertEqual(report["source_original_xlsx_count"],12)
                self.assertEqual(report["byte_identical_xlsx_count"],12)
                self.assertEqual(report["byte_different_xlsx_count"],0)
                self.assertFalse(report["original_2022_2024_issue_day_PIT_certified"])
                self.assertEqual(report["database_connections"],0)
                self.assertEqual(report["database_writes"],0)
                self.assertEqual(report["orders"],0)
                reports.append(report)
        all_time=x.consolidate_zenodo_audits(reports)
        self.assertEqual(all_time["source_original_xlsx_compared"],36)
        self.assertEqual(all_time["exact_byte_matches"],36)
        self.assertEqual(all_time["different_bytes_requiring_semantic_review"],[])
        self.assertFalse(all_time["historical_first_publication_point_in_time_certified"])
        self.assertEqual(all_time["source_binaries_persisted"],0)

    def test_different_sha_requires_review_not_price_revision_claim(self):
        year=2024
        raw,oct_sha=fixture(year,change="nov24")
        # Fake Oct2026 hash corresponds to ORIGINAL pre-modification XLSX,
        # but Zenodo member intentionally has different bytes.
        with patch.dict(x.PARTITION_BUNDLE_MD5,{year:md5(raw).hexdigest()}):
            report=x.check_2025_zenodo_year_archive(year,raw,oct_sha)
        self.assertEqual(report["byte_identical_xlsx_count"],11)
        self.assertEqual(report["byte_different_xlsx_count"],1)
        self.assertFalse(next(i for i in report["members"] if i["issue"]=="nov24")
                         ["exact_xlsx_bytes_match"])

    def test_corrupt_declared_zip_md5_rejected_even_with_matching_member_digest(self):
        raw,known=fixture(2024)
        with self.assertRaisesRegex(SourceFormatError,"MD5 mismatch"):
            x.check_2025_zenodo_year_archive(2024,raw,known)

    def test_missing_month_is_not_accepted(self):
        raw,known=fixture(2024,omit="jun24")
        with patch.dict(x.PARTITION_BUNDLE_MD5,{2024:md5(raw).hexdigest()}):
            with self.assertRaisesRegex(SourceFormatError,"Missing exactly twelve"):
                x.check_2025_zenodo_year_archive(2024,raw,known)

    def test_missing_oct_2026_source_hash_refuses_independent_comparison(self):
        raw,known=fixture(2023)
        known.pop("dec23")
        with patch.dict(x.PARTITION_BUNDLE_MD5,{2023:md5(raw).hexdigest()}):
            with self.assertRaisesRegex(SourceFormatError,"incomplete"):
                x.check_2025_zenodo_year_archive(2023,raw,known)

    def test_wrong_year_and_raw_path_traversal_rejected(self):
        raw,known=fixture(2024)
        with self.assertRaisesRegex(SourceFormatError,"predeclared"):
            x.check_2025_zenodo_year_archive(2021,raw,known)
        zipped=BytesIO()
        with ZipFile(zipped,"w",ZIP_DEFLATED) as z:
            z.writestr("../escape",b"test")
        with patch.dict(x.PARTITION_BUNDLE_MD5,{2024:md5(zipped.getvalue()).hexdigest()}):
            with self.assertRaisesRegex(SourceFormatError,"unsafe"):
                x.check_2025_zenodo_year_archive(2024,zipped.getvalue(),known)

    def test_consolidation_cannot_be_called_with_incomplete_years(self):
        with self.assertRaisesRegex(SourceFormatError,"three"):
            x.consolidate_zenodo_audits([])
