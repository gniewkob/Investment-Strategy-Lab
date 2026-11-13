"""Original MF workbook schema audit; no actual source data exposed."""
import json
import unittest
from datetime import datetime,timezone
from io import BytesIO
from zipfile import ZipFile
from scripts.mf_original_turnover_schema_v07 import inspect_market_sheet
from scripts.knf_mf_official_source_probe_v06 import OriginalEvidenceBlocked

NOW=datetime(2026,11,13,12,0,tzinfo=timezone.utc)
N="http://schemas.openxmlformats.org/spreadsheetml/2006/main"

def make(rows=20, malicious=False, badidx=False):
    buf=BytesIO()
    with ZipFile(buf,"w") as z:
        z.writestr("[Content_Types].xml","<types/>")
        z.writestr("xl/workbook.xml","<workbook/>")
        texts="<sst xmlns='"+N+"'><si><t>Obroty</t></si></sst>"
        z.writestr("xl/sharedStrings.xml",texts)
        values=[]
        for i in range(1,rows+1):
            value="<c r='A1' t='s'><v>2</v></c>" if badidx and i==1 else "<c r='A"+str(i)+"' t='s'><v>0</v></c>"
            values.append("<row r='"+str(i)+"'>"+value+"<c r='B"+str(i)+"' t='n'><v>1.5</v></c></row>")
        xml="<worksheet xmlns='"+N+"'><sheetData>"+"".join(values)+"</sheetData></worksheet>"
        if malicious:xml=xml.replace("<worksheet","<!DOCTYPE evil><worksheet",1)
        z.writestr("xl/worksheets/sheet1.xml",xml)
    return buf.getvalue()

class MFTurnoverSchemaTests(unittest.TestCase):
    def test_fixture_headers_and_types_no_raw_numbers(self):
        result=inspect_market_sheet(make(),observed_at=NOW)
        self.assertEqual(result["rows_in_first_sheet"],20)
        self.assertEqual(result["shared_string_entries"],1)
        self.assertEqual(result["first_28_rows_types_and_captions"][0]["safe_text_captions"][0]["caption"],"Obroty")
        self.assertEqual(result["source_data_rows_in_report"],0)
        self.assertFalse(result["turnover_units_validated"])
        self.assertEqual(result["financial_operations"],0)
    def test_reject_untrusted_xml_entities(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"MF_UNTRUSTED_XML_ENTITIES"):
            inspect_market_sheet(make(malicious=True),observed_at=NOW)
    def test_reject_bad_shared_string_index(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"MF_SHARED_STRING_INDEX_BAD"):
            inspect_market_sheet(make(badidx=True),observed_at=NOW)
    def test_reject_bad_number_rows(self):
        for rows in (1,4,2001):
            with self.subTest(rows=rows),self.assertRaises(OriginalEvidenceBlocked):
                inspect_market_sheet(make(rows=rows),observed_at=NOW)
    def test_reject_naive_clock(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"UTC_AWARE_REQUIRED"):
            inspect_market_sheet(make(),observed_at=datetime(2026,11,13))
