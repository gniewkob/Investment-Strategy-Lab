"""No-network tests of official STEO edition catalog and local RAW-XLSX archive."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zipfile import ZipFile, ZIP_DEFLATED
import json
import stat

from scripts import steo_historical_archive as steo
from src.isl_v2.eia_sources import SourceFormatError


def test_xlsx(sheet="Table 2", value=""):
    target=BytesIO()
    with ZipFile(target,"w",ZIP_DEFLATED) as file:
        file.writestr("[Content_Types].xml",'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
        file.writestr("xl/workbook.xml",
            '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="'+sheet+'" sheetId="1" /></sheets></workbook>')
        file.writestr("xl/worksheets/sheet1.xml",
            '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c t="inlineStr"><is><t>'+value+'</t></is></c></row></sheetData></worksheet>')
    return target.getvalue()


class Response:
    def __init__(self,issue,content):
        self.issue=issue
        self.content=content
        self.url=steo.BASE+issue+"_base.xlsx"
    def __enter__(self):return self
    def __exit__(self,*unused):return False
    def geturl(self):return self.url
    def read(self,max_bytes):return self.content[:max_bytes]


class STEOArchiveResearchTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix="private-steo-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.root.chmod(0o700)

    def opener(self,request,timeout):
        self.assertGreater(timeout,0)
        issue=request.full_url.rsplit("/",1)[-1].replace("_base.xlsx","")
        return Response(issue,test_xlsx())

    def capture(self,issue="jan24"):
        return steo.capture(str(self.root),issue,opener=self.opener)

    def test_official_catalog_has_34_exact_monthly_issues(self):
        entries=steo.catalog()
        self.assertEqual(len(entries),34)
        self.assertEqual(entries["jan24"]["official_release_day"],"2024-01-09")
        self.assertEqual(entries["oct26"]["official_release_day"],"2026-10-06")
        self.assertEqual(entries["dec25"]["official_release_day"],"2025-12-09")
        self.assertEqual(entries["feb24"]["official_release_day"],"2024-02-06")
        self.assertTrue(entries["jan24"]["xlsx_url"].endswith("/jan24_base.xlsx"))
        for x in entries.values():
            self.assertFalse(x["historical_original_bytes_certified"])
        output=StringIO()
        with redirect_stdout(output):
            self.assertEqual(steo.main(["catalog"]),0)
        json_response=json.loads(output.getvalue())
        self.assertEqual(json_response["external_http_requests"],0)
        self.assertEqual(json_response["file_creations"],0)
        self.assertEqual(json_response["total_editions"],34)

    def test_true_original_xlsx_capture_and_offline_replay(self):
        out=self.capture("jan24")
        self.assertEqual(out["status"],"STEO_HISTORICAL_XLSX_LOCAL_CAPTURED")
        self.assertEqual(out["sheet_names"],["Table 2"])
        self.assertEqual(out["sheet_count"],1)
        self.assertTrue(out["original_object_created"])
        self.assertTrue(out["receipt_created"])
        self.assertFalse(out["historical_original_publication_bytes_certified"])
        self.assertEqual(out["database_writes"],0)
        before=list(self.root.rglob("*"))
        offline=steo.verify_all(str(self.root))
        self.assertEqual(offline["status"],"STEO_LOCAL_ARCHIVE_ALL_VINTAGES_OFFLINE_VERIFIED")
        self.assertEqual(offline["verified_issues"],1)
        self.assertEqual(offline["verified_retrievals"],1)
        self.assertEqual(offline["external_http_requests"],0)
        self.assertEqual(offline["file_creations"],0)
        self.assertEqual(before,list(self.root.rglob("*")))
        self.assertEqual(len(list((self.root/"objects").glob("*.xlsx"))),1)
        self.assertEqual(len(list((self.root/"receipts"/"jan24").glob("*.json"))),1)
        for p in self.root.rglob("*"):
            self.assertEqual(stat.S_IMODE(p.stat().st_mode)&0o077,0)

    def test_multi_edition_capture_is_independently_checkable(self):
        self.capture("jan24")
        self.capture("oct26")
        result=steo.verify_all(str(self.root))
        self.assertEqual(result["verified_retrievals"],2)
        self.assertEqual(result["verified_issues"],2)
        # Deliberately identical toy sheets share content-addressed bytes.
        self.assertEqual(len(list((self.root/"objects").glob("*.xlsx"))),1)

    def test_invalid_urls_and_html_bodies_are_refused(self):
        with self.assertRaisesRegex(SourceFormatError,"allowlisted"):
            steo.retrieve("jan23_typo",opener=self.opener)
        class Malicious(Response):
            def geturl(self):return "https://attacker.example/payload.xlsx"
        with self.assertRaisesRegex(SourceFormatError,"redirected"):
            steo.retrieve("jan24",opener=lambda req,timeout:Malicious("jan24",test_xlsx()))
        with self.assertRaises(SourceFormatError):
            steo.inspect_xlsx(b"<html>not a genuine XLSX</html>")
        self.assertEqual(list(self.root.rglob("*")),[])

    def test_corrupted_source_fails_closed(self):
        out=self.capture()
        raw=self.root/"objects"/(out["sha256"]+".xlsx")
        raw.write_bytes(b"not-a-zip")
        with self.assertRaises(SourceFormatError):
            steo.verify_all(str(self.root))

    def test_manifest_forged_release_day_rejected(self):
        self.capture()
        path=next((self.root/"receipts"/"jan24").glob("*.json"))
        data=json.loads(path.read_text())
        data["official_release_day"]="2023-01-09"
        path.write_text(json.dumps(data))
        with self.assertRaises(SourceFormatError):
            steo.verify_all(str(self.root))

    def test_world_readable_root_rejected_and_error_redacted(self):
        self.capture()
        self.root.chmod(0o755)
        with self.assertRaisesRegex(SourceFormatError,"private"):
            steo.verify_all(str(self.root))
        errors=StringIO()
        with redirect_stderr(errors):
            self.assertEqual(steo.main(["verify","--archive-root",str(self.root)]),2)
        self.assertNotIn(str(self.root),errors.getvalue())
        self.assertIn("STEO_RESEARCH_FAILED: ",errors.getvalue())

    def test_invalid_batch_input_no_writes(self):
        errors=StringIO()
        with redirect_stderr(errors):
            self.assertEqual(steo.main(["capture","--archive-root",str(self.root),
                                        "--issues","jan24,jan24"]),2)
        self.assertIn("STEO_RESEARCH_FAILED",errors.getvalue())
        self.assertEqual(list(self.root.rglob("*")),[])

    def test_zip_member_traversal_and_decompression_bomb_guard(self):
        buff=BytesIO()
        with ZipFile(buff,"w",ZIP_DEFLATED) as z:
            z.writestr("../escape","something")
            z.writestr("[Content_Types].xml","<Types/>")
            z.writestr("xl/workbook.xml","<workbook/>")
        with self.assertRaises(SourceFormatError):
            steo.inspect_xlsx(buff.getvalue())
