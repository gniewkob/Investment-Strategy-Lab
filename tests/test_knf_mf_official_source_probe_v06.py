"""Real-official-shape negative tests, no sockets and no data ingestion."""
from datetime import datetime, timezone
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.knf_mf_official_source_probe_v06 import (
    inspect_knf_page, inspect_mf_workbook, fetch_exact, KNF_URLS, MF_URL,
    OriginalEvidenceBlocked, MAX_KNF_BYTES, MAX_MF_BYTES,
)

NOW = datetime(2026,11,13,0,10,tzinfo=timezone.utc)
UUID = "12345678-1234-1234-1234-123456789abc"

def page(kind):
    row = (
        {"fundId": 123, "name": "Test Fund"}
        if kind == "funds"
        else {"valuationUnitUuid": UUID, "currency": "PLN",
              "isPrimary": True, "date": "2026-09-30", "valuation": 150.0}
        if kind == "primary_pln_valuations"
        else {"documentUuid": UUID, "publicationDate": "2026-09-30",
              "riskLevel": 3, "scenarios": [{"name": "fictional"}]}
    )
    return {"content": [row], "page": {"size": 3 if kind == "primary_pln_valuations" else 2,
                                       "number": 0, "totalElements": 1}}

def blob(d):
    return json.dumps(d).encode()

def fake_xlsx(*, poison=None):
    b=BytesIO()
    with ZipFile(b,"w") as z:
        for path in ("[Content_Types].xml", "xl/workbook.xml", "xl/worksheets/sheet1.xml"):
            z.writestr(path,b"<xml/>")
        if poison:
            z.writestr(poison,b"x")
    return b.getvalue()

class OfficialMarketSourcesTests(unittest.TestCase):
    def test_three_knf_contracts(self):
        for k in KNF_URLS:
            with self.subTest(k=k):
                x=inspect_knf_page(k,blob(page(k)),completed_at=NOW)
                self.assertEqual(x["page_records"],1)
                self.assertFalse(x["historical_first_publication_certified"])
                self.assertFalse(x["total_return_admitted"])
                self.assertEqual(x["financial_operations"],0)
                self.assertEqual(len(x["original_raw_sha256"]),64)
                self.assertNotIn("Test Fund",json.dumps(x))
                self.assertNotIn("150.0",json.dumps(x))
    def test_mf_real_xlsx_structure(self):
        x=inspect_mf_workbook(fake_xlsx(),completed_at=NOW)
        self.assertEqual(x["workbook_worksheet_count"],1)
        self.assertFalse(x["any_macro_or_script_executed"])
        self.assertEqual(x["financial_operations"],0)
    def test_mf_printersettings_are_data_only(self):
        receipt=inspect_mf_workbook(
            fake_xlsx(poison="xl/printerSettings/printerSettings1.bin"),
            completed_at=NOW)
        self.assertEqual(receipt["workbook_worksheet_count"],1)
        self.assertFalse(receipt["any_macro_or_script_executed"])

    def test_mf_rejects_macros_and_external_links(self):
        for poison in ("xl/vbaProject.bin","xl/externalLinks/externalLink1.xml",
                       "xl/notes.BIN","xl/VBAPROJECT.BIN","../unsafe.xml"):
            with self.subTest(poison=poison),self.assertRaises(OriginalEvidenceBlocked):
                inspect_mf_workbook(fake_xlsx(poison=poison),completed_at=NOW)
    def test_mf_rejects_fake_zip(self):
        for raw in (b"",b"<html>login required</html>",b"PK\x03\x04bad",b"x"*(MAX_MF_BYTES+1)):
            with self.assertRaises(OriginalEvidenceBlocked):
                inspect_mf_workbook(raw,completed_at=NOW)
    def test_knf_wrong_country_and_class(self):
        d=page("primary_pln_valuations")
        for key,bad in (("currency","USD"),("isPrimary",False)):
            d2=json.loads(json.dumps(d));d2["content"][0][key]=bad
            with self.assertRaisesRegex(OriginalEvidenceBlocked,"CURRENCY_CLASS"):
                inspect_knf_page("primary_pln_valuations",blob(d2),completed_at=NOW)
    def test_knf_wrong_date_and_nav(self):
        for k,v in (("date","2026-10-15"),("valuation",0),("valuation",float("nan")),
                    ("valuation",True),("valuation",float("inf"))):
            d=page("primary_pln_valuations");d["content"][0][k]=v
            with self.subTest(k=k,v=str(v)),self.assertRaises(OriginalEvidenceBlocked):
                inspect_knf_page("primary_pln_valuations",blob(d),completed_at=NOW)
    def test_knf_future_kid_rejected(self):
        d=page("kid_units");d["content"][0]["publicationDate"]="2030-01-01"
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"FUTURE_KID"):
            inspect_knf_page("kid_units",blob(d),completed_at=NOW)
    def test_knf_bad_pagination_and_raw_bounded(self):
        for k in KNF_URLS:
            d=page(k);d["page"]["number"]=1
            with self.subTest(k=k),self.assertRaisesRegex(OriginalEvidenceBlocked,"PAGINATION"):
                inspect_knf_page(k,blob(d),completed_at=NOW)
        with self.assertRaises(OriginalEvidenceBlocked):
            inspect_knf_page("funds",b"x"*(MAX_KNF_BYTES+1),completed_at=NOW)
    def test_knf_injection_field_rejected(self):
        d=page("funds");d["content"][0]["line\n::warning::hack"]="danger"
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"FIELD_NAME_UNSAFE"):
            inspect_knf_page("funds",blob(d),completed_at=NOW)
    def test_no_network_from_parser(self):
        with patch("socket.socket.connect",side_effect=AssertionError("SHOULD_NEVER_CONNECT")):
            inspect_knf_page("funds",blob(page("funds")),completed_at=NOW)
            inspect_mf_workbook(fake_xlsx(),completed_at=NOW)
    def test_fetch_allowlisted(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"ALLOWLIST"):
            fetch_exact("https://evil.invalid/v1/funds")
    def test_utc_aware_required(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"UTC_AWARE"):
            inspect_knf_page("funds",blob(page("funds")),
                             completed_at=datetime(2026,11,13))
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"UTC_AWARE"):
            inspect_mf_workbook(fake_xlsx(),completed_at=datetime(2026,11,13))
