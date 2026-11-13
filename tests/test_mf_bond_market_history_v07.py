"""Source parser safety baseline: offline stdlib-only XLSX, never execute macros."""
from datetime import datetime,timezone
from io import BytesIO
import json
import unittest
from zipfile import ZipFile

from scripts.mf_bond_market_history_v07 import (
    audit_mf_schema, read_mf_cells, OriginalEvidenceBlocked,
)

NOW=datetime(2026,11,13,tzinfo=timezone.utc)
N="http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def xlsx(*, shared=True, malformed=False, macro=False):
    workbook=f'<workbook xmlns="{N}"/>'
    sheet=(f'<worksheet xmlns="{N}"><sheetData><row r="1">'
           f'<c r="A1" t="s"><v>0</v></c>' if shared else
           f'<worksheet xmlns="{N}"><sheetData><row r="1">'
           f'<c r="A1" t="inlineStr"><is><t>Data</t></is></c>')
    sheet += '<c r="B1"><v>1234.5</v></c></row><row r="2"><c r="A2"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>'
    if malformed: sheet=sheet.replace("r=\"B1\"","r=\"B2\"")
    b=BytesIO()
    with ZipFile(b,"w") as z:
        z.writestr("[Content_Types].xml",b"<Types/>")
        z.writestr("xl/workbook.xml",workbook)
        z.writestr("xl/worksheets/sheet1.xml",sheet)
        if shared:
            z.writestr("xl/sharedStrings.xml",f'<sst xmlns="{N}"><si><t>Data</t></si></sst>')
        if macro: z.writestr("xl/vbaProject.bin",b"FAKE")
    return b.getvalue()


class MFHistoryParserSafetyTests(unittest.TestCase):
    def test_real_xlsx_shape_and_formula_not_executed(self):
        receipt,rows=read_mf_cells(xlsx(),completed_at=NOW)
        self.assertEqual(receipt["xml_rows"],2)
        self.assertEqual(receipt["formula_cells"],1)
        self.assertEqual(rows[0]["cells"]["A"]["value"],"Data")
        self.assertEqual(rows[0]["cells"]["B"]["value"],"1234.5")
        self.assertEqual(rows[1]["cells"]["A"]["t"],"formula")
        self.assertIsNone(rows[1]["cells"]["A"]["value"])
    def test_inline_string_without_shared_strings(self):
        _,rows=read_mf_cells(xlsx(shared=False),completed_at=NOW)
        self.assertEqual(rows[0]["cells"]["A"]["value"],"Data")
    def test_incorrect_cell_row_rejected(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"CELL_ADDRESS"):
            read_mf_cells(xlsx(malformed=True),completed_at=NOW)
    def test_macro_workbook_rejected(self):
        with self.assertRaises(OriginalEvidenceBlocked):
            read_mf_cells(xlsx(macro=True),completed_at=NOW)
    def test_bounded_preview_no_full_rows(self):
        result=audit_mf_schema(xlsx(),completed_at=NOW)
        self.assertEqual(result["xml_rows"],2)
        self.assertFalse(result["full_data_exported"])
        self.assertEqual(result["financial_operations"],0)
        self.assertEqual(result["database_writes"],0)
    def test_utc_clock_required(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"UTC_AWARE"):
            read_mf_cells(xlsx(),completed_at=datetime(2026,11,13))
