"""Synthetic OOXML unit tests only — not an official Vanguard export."""
from __future__ import annotations

import calendar
from datetime import date
from io import BytesIO
from zipfile import ZipFile
from xml.sax.saxutils import escape
import unittest

from scripts.vanguard_xlsx_offline_intake_v04 import (
    inspect_export, InvalidVanguardXLSX,
)


def _cell(ref, value, *, inline=False, formula=False):
    if formula:
        return f'<c r="{ref}"><f>NOW()</f><v>1</v></c>'
    if inline:
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
    return f'<c r="{ref}"><v>{escape(str(value))}</v></c>'


def fake_xlsx(months=60, *, skip=None, duplicate=False, numeric_dates=False,
              wrong_header=False, formula=False, macro=False):
    contents=[
        '<row r="1">'+_cell("A1","Date",inline=True)
        +_cell("B1","Market price (USD)",inline=True)
        +_cell("C1","Market price (USD)" if wrong_header else "NAV (USD)",inline=True)
        +'</row>'
    ]
    for i in range(months):
        y=2021+(10+i)//12;m=(10+i)%12+1
        month=f"{y:04d}-{m:02d}"
        if skip==month:continue
        day=date(y,m,calendar.monthrange(y,m)[1])
        value=str((day-date(1899,12,30)).days) if numeric_dates else day.isoformat()
        cells=_cell(f"A{i+2}",value,inline=not numeric_dates)
        cells+=_cell(f"B{i+2}",888+i)
        cells+=_cell(f"C{i+2}",100+i,formula=formula and i==0)
        contents.append(f'<row r="{i+2}">{cells}</row>')
        if duplicate and i==0:
            contents.append(f'<row r="{i+300}">'
                            +_cell(f"A{i+300}",day.isoformat(),inline=True)
                            +_cell(f"C{i+300}",100+i)+'</row>')
    sheet=('<?xml version="1.0" encoding="utf-8"?>'
           '<worksheet xmlns="http://schemas.openxmlformats.org/'
           'spreadsheetml/2006/main"><sheetData>'
           +''.join(contents)+'</sheetData></worksheet>').encode()
    workbook=b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'
    out=BytesIO()
    with ZipFile(out,"w") as z:
        z.writestr("[Content_Types].xml",b"source test fixture")
        z.writestr("xl/workbook.xml",workbook)
        z.writestr("xl/worksheets/sheet1.xml",sheet)
        if macro:z.writestr("xl/vbaProject.bin",b"not-allowed")
    return out.getvalue()


class VanguardOfflineXLSXIntakeTests(unittest.TestCase):
    def test_60_months_and_sha_keep_data_as_candidate_only(self):
        raw=fake_xlsx()
        doc=inspect_export(raw,"2021-11","2026-10")
        self.assertEqual(doc["months"],60)
        self.assertEqual(len(doc["monthly"]),60)
        self.assertEqual(doc["monthly"][0]["nav_usd"],"100")
        self.assertEqual(doc["monthly"][-1]["nav_usd"],"159")
        self.assertEqual(doc["monthly"][0]["month"],"2021-11")
        self.assertEqual(doc["monthly"][-1]["month"],"2026-10")
        self.assertEqual(len(doc["raw_export_sha256"]),64)
        self.assertFalse(doc["name_or_isin_authenticated_from_download"])
        self.assertFalse(doc["usable_as_GLOBAL_EQUITY_TR_PLN"])
        self.assertFalse(doc["historical_pit_certified"])
        self.assertEqual(doc["backtest"],"NOT_RUN_PROVIDER_PROVENANCE_REQUIRED")
        self.assertEqual(doc["financial_operations"],0)
        self.assertEqual(doc["paper_events_created"],0)
        self.assertEqual(doc,inspect_export(raw,"2021-11","2026-10"))

    def test_excel_numeric_date_serial_and_nav_vs_market_price(self):
        doc=inspect_export(fake_xlsx(36,numeric_dates=True),"2021-11","2024-10")
        self.assertEqual(doc["monthly"][0]["observed_for"],"2021-11-30")
        self.assertEqual(doc["monthly"][0]["nav_usd"],"100")

    def test_missing_calendar_month_is_not_filled(self):
        with self.assertRaisesRegex(InvalidVanguardXLSX,"missing original source"):
            inspect_export(fake_xlsx(skip="2024-02"),"2021-11","2026-10")

    def test_duplicate_daily_source_row_rejected(self):
        with self.assertRaisesRegex(InvalidVanguardXLSX,"duplicate original"):
            inspect_export(fake_xlsx(36,duplicate=True),"2021-11","2024-10")

    def test_wrong_header_does_not_substitute_market_price(self):
        with self.assertRaisesRegex(InvalidVanguardXLSX,"unique Date"):
            inspect_export(fake_xlsx(36,wrong_header=True),"2021-11","2024-10")

    def test_formula_or_embedded_macro_blocked(self):
        with self.assertRaisesRegex(InvalidVanguardXLSX,"formula"):
            inspect_export(fake_xlsx(36,formula=True),"2021-11","2024-10")
        with self.assertRaisesRegex(InvalidVanguardXLSX,"macros"):
            inspect_export(fake_xlsx(36,macro=True),"2021-11","2024-10")

    def test_not_zip_and_short_month_span_rejected(self):
        with self.assertRaises(InvalidVanguardXLSX):
            inspect_export(b"not-an-xlsx","2021-11","2024-10")
        with self.assertRaisesRegex(InvalidVanguardXLSX,"36-72"):
            inspect_export(fake_xlsx(),"2025-01","2025-12")


if __name__=="__main__":
    unittest.main()
