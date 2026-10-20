"""Synthetic/offline Table 10b parser tests; never represent market source verification."""
from io import BytesIO
from unittest import TestCase
from zipfile import ZipFile, ZIP_DEFLATED

from scripts.steo_jun24_repost_audit import AuditError, compare_versions, extract_10b_rows


def workbook(*, sng=12, total=44, missing=False, duplicate=False,
             target="worksheets/sheet4.xml"):
    data = BytesIO()
    rows = []
    for idx, code, number in ((6, "SNGPRPM", sng), (7, "SNGPRL48", total)):
        if missing and idx == 7:
            continue
        cells = f'<c r="A{idx}" t="s"><v>{idx-6}</v></c>'
        for offset in range(12):
            col = chr(ord("B") + offset)
            cells += f'<c r="{col}{idx}"><v>{number + offset}</v></c>'
        rows.append(f'<row r="{idx}">{cells}</row>')
    if duplicate:
        rows.append('<row r="8"><c r="A8" t="s"><v>0</v></c></row>')
    with ZipFile(data, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("xl/workbook.xml",
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="10btab" sheetId="4" r:id="rId4"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId4" Target="' + target + '" '
                   'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
                   '</Relationships>')
        z.writestr("xl/sharedStrings.xml",
                   '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   '<si><t>SNGPRPM</t></si><si><t>SNGPRL48</t></si></sst>')
        z.writestr("xl/worksheets/sheet4.xml",
                   '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   '<sheetData>' + "".join(rows) + '</sheetData></worksheet>')
    return data.getvalue()


class Jun24AuditOfflineTests(TestCase):
    def test_targeted_change_detected_without_first_release_claim(self):
        early = extract_10b_rows(workbook())
        late = extract_10b_rows(workbook(sng=15))
        result = compare_versions(early, late)
        self.assertEqual(result["series"]["SNGPRPM"]["changed_cached_numeric_values"], 12)
        self.assertEqual(result["series"]["SNGPRL48"]["changed_cached_numeric_values"], 0)
        self.assertFalse(result["historical_first_release_bytes_certified"])
        self.assertFalse(result["causal_attribution_to_notice_proven"])
        self.assertEqual(result["database_writes"], 0)

    def test_identical_table_10b_rows(self):
        same = extract_10b_rows(workbook())
        self.assertEqual(compare_versions(same, same)["changed_cells_total"], 0)

    def test_missing_series_fails_closed(self):
        with self.assertRaisesRegex(AuditError, "missing"):
            extract_10b_rows(workbook(missing=True))

    def test_duplicate_series_fails_closed(self):
        with self.assertRaisesRegex(AuditError, "duplicated"):
            extract_10b_rows(workbook(duplicate=True))

    def test_external_or_traversing_relationship_fails_closed(self):
        with self.assertRaisesRegex(AuditError, "path"):
            extract_10b_rows(workbook(target="../../evil.xml"))

    def test_non_xlsx_fails_closed(self):
        with self.assertRaises(AuditError):
            extract_10b_rows(b"not-a-workbook")
