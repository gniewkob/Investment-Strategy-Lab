"""Synthetic, offline structure tests for STEO sheet label inspection."""
from __future__ import annotations
from io import BytesIO
from unittest import TestCase
from zipfile import ZipFile, ZIP_DEFLATED

from scripts import steo_xlsx_label_probe as probe
from src.isl_v2.eia_sources import SourceFormatError


def workbook(*, target="worksheets/sheet3.xml", external=False):
    data=BytesIO()
    sheet="""<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="D1"><v>2024</v></c></row>
<row r="17"><c r="B17" t="s"><v>1</v></c><c r="F17"><v>74.21</v></c></row>
<row r="22"><c r="B22" t="s"><v>2</v></c><c r="F22"><v>3.66</v></c></row>
</sheetData></worksheet>"""
    with ZipFile(data,"w",ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="2tab" sheetId="1" r:id="rId3"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId3" Target="'+target+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"'+(' TargetMode="External"' if external else '')+'/></Relationships>')
        z.writestr("xl/sharedStrings.xml",
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>U.S. Energy Prices</t></si><si><t>West Texas Intermediate crude oil spot price</t></si><si><t>Henry Hub natural gas spot price</t></si></sst>')
        z.writestr("xl/worksheets/sheet3.xml",sheet)
    return data.getvalue()


class HistoricalSTEOSheetLabelTests(TestCase):
    def test_labels_visible_but_no_numeric_quotes(self):
        out=probe.inspect_price_table_labels(workbook())
        labels={r["cell"]:r["label"] for r in out["labels"]}
        self.assertEqual(labels["A1"],"U.S. Energy Prices")
        self.assertIn("West Texas Intermediate",labels["B17"])
        self.assertIn("Henry Hub",labels["B22"])
        self.assertEqual(out["numeric_year_headers"],[{"cell":"D1","year":2024}])
        self.assertEqual(out["numeric_price_values_exposed"],0)
        self.assertEqual(out["formulas_evaluated"],0)
        self.assertFalse(out["original_historical_first_publication_bytes_verified"])
        self.assertNotIn("74.21",str(out))
        self.assertNotIn("3.66",str(out))
        self.assertEqual(out["database_connections"],0)
        self.assertEqual(out["database_writes"],0)
        self.assertEqual(out["real_orders"],0)

    def test_external_relation_and_traversal_fail_closed(self):
        with self.assertRaisesRegex(SourceFormatError,"External"):
            probe.inspect_price_table_labels(workbook(external=True))
        with self.assertRaisesRegex(SourceFormatError,"relationship"):
            probe.inspect_price_table_labels(workbook(target="../../file.xml"))

    def test_missing_named_sheet_fails_closed(self):
        with self.assertRaisesRegex(SourceFormatError,"not present"):
            probe.inspect_price_table_labels(workbook(),sheet_name="fake")
