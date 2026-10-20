"""Strict offline synthetic XLSX unit tests for archival forecast comparison."""
from __future__ import annotations
from copy import deepcopy
from datetime import date
from io import BytesIO
from unittest import TestCase
from zipfile import ZipFile, ZIP_DEFLATED

from scripts import steo_monthly_forecast_eval as ev
from src.isl_v2.eia_sources import SourceFormatError


def letters(num: int) -> str:
    output=""
    while num:
        num,rest=divmod(num-1,26)
        output=chr(65+rest)+output
    return output


def archived_fixture(issue="jan24", *, shift=0, missing_year=False, incorrect_name=False,
                     change_future=False):
    """Valid OOXML test rows 2022-2027, different starting offset per edition."""
    rows={
        1:['<c r="B1" t="inlineStr"><is><t>Table 2.  Energy Prices</t></is></c>'],
        3:['<c r="A3" t="inlineStr"><is><t>Forecast date:</t></is></c>'],
        4:['<c r="A4" t="inlineStr"><is><t>Tuesday</t></is></c>'],
        6:['<c r="A6" t="inlineStr"><is><t>WTIPUUS</t></is></c>',
           '<c r="B6" t="inlineStr"><is><t>'+
           ('fake series' if incorrect_name else 'West Texas Intermediate Spot Average')+
           '</t></is></c>'],
        7:['<c r="A7" t="inlineStr"><is><t>BREPUUS</t></is></c>',
           '<c r="B7" t="inlineStr"><is><t>Brent Spot Average</t></is></c>']
    }
    for y in range(2022,2028):
        start=3+shift+(y-2022)*12
        if y != 2023 or not missing_year:
            rows[3].append(f'<c r="{letters(start)}3"><v>{y}</v></c>')
        for month in range(1,13):
            col=letters(start+month-1)
            rows[4].append(
                f'<c r="{col}4" t="inlineStr"><is><t>{ev.MONTHS[month-1]}</t></is></c>')
            base=70 + (y-2022)*1.5 + month * .4
            for row in (6,7):
                val=base+(5 if row==7 else 0)
                if change_future and y>=2024 and month>=2:
                    val+=8
                # Must use cached numeric <v> even with formula present.
                rows[row].append(f'<c r="{col}{row}"><f>STATIC_FIXTURE</f>'
                                 f'<v>{val:.2f}</v></c>')
    xml='<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    xml+=''.join(f'<row r="{r}">{"".join(cells)}</row>' for r,cells in sorted(rows.items()))
    xml+='</sheetData></worksheet>'
    with BytesIO() as buffer:
        with ZipFile(buffer,"w",ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml",
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="2tab" sheetId="1" r:id="rId3"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId3" Target="worksheets/sheet3.xml" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
                '</Relationships>')
            z.writestr("xl/worksheets/sheet3.xml",xml)
        return buffer.getvalue()


class STEOForecastMonthlyTests(TestCase):
    def test_true_month_headers_change_columns_across_vintages(self):
        jan24=ev.parse_edition("jan24",archived_fixture("jan24",shift=0))
        jan25=ev.parse_edition("jan25",archived_fixture("jan25",shift=12))
        self.assertEqual(jan24["series"]["WTIPUUS"]["2025-02"],
                         jan25["series"]["WTIPUUS"]["2025-02"])
        self.assertEqual(jan24["series"]["BREPUUS"]["2024-01"],"78.40")
        self.assertTrue(all(len(x.split(".")[-1]) == 2
                            for x in jan24["series"]["WTIPUUS"].values()))
        self.assertNotEqual(jan24["raw_xlsx_sha256"],jan25["raw_xlsx_sha256"])
        self.assertFalse(jan24["original_first_release_bytes_certified"])
        self.assertFalse(jan24["forecast_completed_date_used_as_market_availability"])
        self.assertEqual(jan24["source_vintage"],
                         "RECONSTRUCTED_FROM_CURRENTLY_HOSTED_ARCHIVED_EDITION")

    def test_later_edition_reference_and_same_vintage_naive_baseline(self):
        a=ev.parse_edition("jan24",archived_fixture())
        b=ev.parse_edition("jan25",archived_fixture(shift=12,change_future=True))
        out=ev.compare_editions([a,b])
        self.assertGreaterEqual(out["paired_target_forecasts"],6)
        self.assertEqual(out["source_editions"],2)
        self.assertFalse(out["historical_source_as_published_bytes_certified"])
        self.assertEqual(out["reference_policy"],
                         "FIRST_SAMPLED_LATER_EDITION_AT_LEAST_TWO_CALENDAR_MONTHS_AFTER_TARGET")
        row=next(x for x in out["paired_records"]
                 if x["instrument_code"]=="WTI_EIA_STEO_USD_BBL"
                 and x["target_month"]=="2024-02")
        self.assertEqual(row["forecast_edition"],"jan24")
        self.assertEqual(row["reference_edition"],"jan25")
        self.assertEqual(row["horizon_calendar_months"],1)
        self.assertEqual(row["source_forecast_value"],"73.80")
        self.assertEqual(row["later_edition_reference_value"],"81.80")
        self.assertEqual(row["same_edition_previous_month_naive_value"],"76.30")
        self.assertEqual(row["absolute_source_forecast_error"],"8.00")
        self.assertEqual(out["database_writes"],0)
        self.assertEqual(out["real_orders"],0)
        self.assertEqual(out["virtual_model_rebalances"],0)
        self.assertFalse(out["original_observation_point_in_time_certified"])

    def test_same_report_cannot_be_its_own_realization(self):
        only=ev.parse_edition("jan24",archived_fixture())
        with self.assertRaisesRegex(SourceFormatError,"2-34"):
            ev.compare_editions([only])

    def test_wrong_wti_label_fail_closed(self):
        with self.assertRaisesRegex(SourceFormatError,"identity"):
            ev.parse_edition("jan24",archived_fixture(incorrect_name=True))

    def test_missing_year_header_is_rejected(self):
        with self.assertRaisesRegex(SourceFormatError,"continuous"):
            ev.parse_edition("jan24",archived_fixture(missing_year=True))

    def test_release_date_not_replaced_by_forecast_completion(self):
        obj=ev.parse_edition("jan25",archived_fixture("jan25"))
        self.assertEqual(obj["official_release_day"],"2025-01-14")
        self.assertEqual(obj["available_not_before_utc_date"],"2025-01-15")

    def test_duplicate_issue_and_spoofed_pit_fail_closed(self):
        x=ev.parse_edition("jan24",archived_fixture())
        with self.assertRaisesRegex(SourceFormatError,"distinct"):
            ev.compare_editions([x,x])
        y=ev.parse_edition("jan25",archived_fixture())
        fake=deepcopy(y)
        fake["original_first_release_bytes_certified"]=True
        with self.assertRaisesRegex(SourceFormatError,"unsupported"):
            ev.compare_editions([x,fake])

    def test_reject_unsupported_source_and_future_horizon(self):
        with self.assertRaisesRegex(SourceFormatError,"Unknown"):
            ev.parse_edition("jan23_not_official",archived_fixture())
        x=ev.parse_edition("jan24",archived_fixture())
        y=ev.parse_edition("jan25",archived_fixture())
        with self.assertRaisesRegex(SourceFormatError,"Unsupported"):
            ev.compare_editions([x,y],horizons=[0])
