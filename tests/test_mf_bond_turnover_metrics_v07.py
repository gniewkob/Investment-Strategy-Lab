"""MF full monthly market-turnover contract: only synthetic fixture, no network."""
from __future__ import annotations

from datetime import datetime,timezone
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile
import unittest

from scripts.mf_bond_turnover_metrics_v07 import (
    analyze_mf_original,OriginalEvidenceBlocked,OFFICIAL_LATEST,
)

NOW=datetime(2026,11,13,tzinfo=timezone.utc)
N="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
YEARS=[(y,m) for y in range(2009,2027) for m in range(1,13)
       if (2009,12)<=(y,m)<=(2026,9)]


def synth(*,bad=None):
    """Every monthly observation is wholly synthetic, except Sep official comparator."""
    labels=["Month","Rynek nieregulowany","Treasury BondSpot Poland","GPW","Razem"]
    xml=[f'<worksheet xmlns="{N}"><sheetData><row r="1">']
    for i,head in enumerate(labels):
        col="ABCDE"[i]
        xml.append(f'<c r="{col}1" t="inlineStr"><is><t>{head}</t></is></c>')
    xml.append("</row>")
    for ix,(y,m) in enumerate(YEARS):
        rn=ix+2
        period=f"{y:04d}-{m:02d}"
        vals=[Decimal("1600000"),Decimal("250000"),Decimal("500")]
        if period=="2026-08":
            vals=[Decimal("2300000"),Decimal("388000"),Decimal("690")]
        if period=="2026-09":
            vals=[OFFICIAL_LATEST[k] for k in ("interbank","bondspot","gpw")]
        if bad=="missing" and period=="2026-02":
            continue
        if bad=="duplicated" and period=="2026-02":
            period="2026-01"
        if bad=="not_official" and period=="2026-09":
            vals[1]+=Decimal("5")
        if bad=="negative" and period=="2026-09":
            vals[0]=Decimal("-1")
        if bad=="bad_sum" and period=="2026-09":
            vals=vals[:-1]+[vals[-1]+Decimal("500")]
        total=sum(vals)
        if bad=="bad_sum" and period=="2026-09":
            total+=Decimal("5")
        xml.append(f'<row r="{rn}">')
        xml.append(f'<c r="A{rn}" t="inlineStr"><is><t>{period}</t></is></c>')
        for letter,val in zip("BCDE",(*vals,total)):
            if bad=="formula" and period=="2026-09" and letter=="E":
                xml.append(f'<c r="{letter}{rn}"><f>SUM(B{rn}:D{rn})</f><v>{val}</v></c>')
            else:
                xml.append(f'<c r="{letter}{rn}"><v>{val}</v></c>')
        xml.append("</row>")
    xml.append("</sheetData></worksheet>")
    out=BytesIO()
    with ZipFile(out,"w") as z:
        z.writestr("[Content_Types].xml",b"<Types/>")
        z.writestr("xl/workbook.xml",f'<workbook xmlns="{N}"/>')
        z.writestr("xl/worksheets/sheet1.xml","".join(xml))
    return out.getvalue()


class MFBondMarketHistoryTests(unittest.TestCase):
    def test_original_headline_and_202_months(self):
        o=analyze_mf_original(synth(),completed_at=NOW)
        self.assertEqual(o["unique_month_count"],202)
        self.assertEqual(o["first_month"],"2009-12")
        self.assertEqual(o["last_month"],"2026-09")
        self.assertEqual(o["latest_total_mln_pln"],"3140385.25")
        self.assertEqual(o["latest_interbank_mln_pln"],"2782687.61")
        self.assertEqual(o["latest_bondspot_mln_pln"],"357071.50")
        self.assertEqual(o["latest_gpw_mln_pln"],"626.14")
        self.assertAlmostEqual(float(o["latest_mom_change_pct"]),16.8,places=1)
        self.assertAlmostEqual(
            sum(map(float,o["latest_month_channel_shares_pct"].values())),100,places=3)
        self.assertFalse(o["historical_pit_first_publication_certified"])
        self.assertFalse(o["tradable_bond_total_return_series_qualified"])
        self.assertEqual(o["financial_operations"],0)
        self.assertEqual(o["orders"],0)
    def test_invalid_duplicate_month_rejected(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"DUPLICATE_MONTH"):
            analyze_mf_original(synth(bad="duplicated"),completed_at=NOW)
    def test_missing_month_rejected_not_filled_zero(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"INCOMPLETE_202_MONTH"):
            analyze_mf_original(synth(bad="missing"),completed_at=NOW)
    def test_source_latest_values_checked(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"CHANNELS_DO_NOT_RECONCILE|PUBLISHER_RECONCILIATION"):
            analyze_mf_original(synth(bad="not_official"),completed_at=NOW)
    def test_negative_values_rejected(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"VALUE_OUT_OF_RANGE"):
            analyze_mf_original(synth(bad="negative"),completed_at=NOW)
    def test_inconsistent_total_rejected(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"CHANNELS_DO_NOT_RECONCILE"):
            analyze_mf_original(synth(bad="bad_sum"),completed_at=NOW)
    def test_cached_excel_formula_not_trusted(self):
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"EMPTY_OR_FORMULA"):
            analyze_mf_original(synth(bad="formula"),completed_at=NOW)
    def test_no_implicit_network_or_ingestion(self):
        import socket
        old=socket.socket.connect
        try:
            socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError("network not allowed"))
            self.assertEqual(analyze_mf_original(synth(),completed_at=NOW)["database_writes"],0)
        finally:socket.socket.connect=old
