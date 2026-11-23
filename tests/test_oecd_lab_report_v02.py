"""Synthetic fixtures only; never fetch or embed real OECD market observations."""
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.oecd_lab_report_v02 import (assemble, write_report, OECDReportBlocked)
from scripts.oecd_pol_benchmark import BenchmarkError

FIELDS = ['STRUCTURE', 'STRUCTURE_ID', 'ACTION', 'REF_AREA', 'FREQ', 'MEASURE',
          'UNIT_MEASURE', 'ACTIVITY', 'ADJUSTMENT', 'TRANSFORMATION', 'TIME_HORIZ',
          'METHODOLOGY', 'TIME_PERIOD', 'OBS_VALUE', 'OBS_STATUS', 'UNIT_MULT', 'BASE_PER']
STAMP = '2026-11-23T12:00:00Z'


def fixture():
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()
    for i in range(48):
        writer.writerow({'STRUCTURE': 'DATAFLOW',
            'STRUCTURE_ID': 'OECD.SDD.STES:DSD_STES@DF_FINMARK(4.0)',
            'ACTION': 'I', 'REF_AREA': 'POL', 'FREQ': 'M', 'MEASURE': 'SHARE',
            'UNIT_MEASURE': 'IX', 'ACTIVITY': '_Z', 'ADJUSTMENT': '_Z',
            'TRANSFORMATION': '_Z', 'TIME_HORIZ': '_Z', 'METHODOLOGY': 'N',
            'TIME_PERIOD': f'{2022 + i//12}-{i%12 + 1:02d}',
            'OBS_VALUE': '100', 'OBS_STATUS': 'A', 'UNIT_MULT': '0', 'BASE_PER': '2015'})
    return out.getvalue().encode('utf-8')


class OECDLabReportTests(unittest.TestCase):
    def test_full_synthetic_48_months_embedded_in_existing_lab_report(self):
        raw = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            original = work / 'source.csv'
            original.write_bytes(raw)
            base = work / 'research_report.md'
            base.write_text('# ISL main research report\n\nMain report is read-only.\n')
            out = work / 'appendix'
            result = write_report(original_file=original,
                expected_sha256=sha256(raw).hexdigest(),
                retrieved_at_utc=STAMP, out_dir=out, base_report_file=base)
            self.assertEqual(result['status'], 'NON_EXECUTABLE_RESEARCH_BENCHMARK')
            self.assertEqual(result['observation_count'], 48)
            self.assertEqual(result['benchmark']['terminal_index_equivalent_pln'], '4800')
            self.assertEqual(result['benchmark']['contributions_pln'], '4800')
            self.assertEqual(result['m1_m2_m3'], 'INSUFFICIENT_DATA_HOLD_CASH')
            self.assertFalse(result['rights_specific_to_series_verified'])
            self.assertFalse(result['historical_point_in_time_certified'])
            self.assertEqual(result['orders_sent'], 0)
            self.assertEqual(result['database_writes'], 0)
            self.assertEqual(result['qualified_asset_series'], [])
            self.assertEqual(json.loads((out / 'oecd_research_appendix.json').read_text())['schema'], result['schema'])
            text = (out / 'research_report.md').read_text()
            self.assertIn('# ISL main research report', text)
            self.assertIn('Poland share-index research benchmark', text)
            self.assertIn('upstream data ownership', text)
            self.assertEqual(base.read_text(), '# ISL main research report\n\nMain report is read-only.\n')
            self.assertNotIn('TIME_PERIOD', text)

    def test_wrong_source_hash_fails_before_creating_output_directory(self):
        raw = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            source = work / 'source.csv'
            source.write_bytes(raw)
            dest = work / 'appendix'
            with self.assertRaisesRegex(OECDReportBlocked, 'ORIGINAL_RAW_SHA256_MISMATCH'):
                write_report(original_file=source, expected_sha256='0' * 64,
                             retrieved_at_utc=STAMP, out_dir=dest)
            self.assertFalse(dest.exists())

    def test_missing_month_is_a_blocker_not_a_partial_comparison(self):
        raw = fixture().replace(b'2024-05,100,', b'2024-06,100,')
        with self.assertRaises(BenchmarkError):
            assemble(raw=raw, expected_sha256=sha256(raw).hexdigest(),
                     retrieved_at_utc=STAMP)

    def test_rejects_source_with_wrong_series_while_preserving_output(self):
        raw = fixture().replace(b',POL,', b',DEU,', 1)
        with self.assertRaises(BenchmarkError):
            assemble(raw=raw, expected_sha256=sha256(raw).hexdigest(),
                     retrieved_at_utc=STAMP)

    def test_rejects_invalid_expected_hash_and_base_report(self):
        raw = fixture()
        for invalid in ('A' * 64, '0' * 63, '../source', '', None):
            with self.subTest(invalid=invalid), self.assertRaises(OECDReportBlocked):
                assemble(raw=raw, expected_sha256=invalid, retrieved_at_utc=STAMP)
        with self.assertRaisesRegex(OECDReportBlocked, 'EXISTING_REPORT_REQUIRED'):
            assemble(raw=raw, expected_sha256=sha256(raw).hexdigest(),
                     retrieved_at_utc=STAMP, base_report='   ')

    def test_symlink_and_existing_destination_are_rejected(self):
        raw = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            original = work / 'source.csv'
            original.write_bytes(raw)
            link = work / 'linked.csv'
            link.symlink_to(original)
            for source in (link, work / 'missing.csv'):
                with self.subTest(source=source), self.assertRaises(OECDReportBlocked):
                    write_report(original_file=source, expected_sha256=sha256(raw).hexdigest(),
                                 retrieved_at_utc=STAMP, out_dir=work / 'new')
            with self.assertRaisesRegex(OECDReportBlocked, 'OUTPUT_DIRECTORY_MUST_NOT_EXIST'):
                write_report(original_file=original, expected_sha256=sha256(raw).hexdigest(),
                             retrieved_at_utc=STAMP, out_dir=work)

    def test_wrong_future_timestamp_is_rejected(self):
        raw = fixture()
        with self.assertRaises(BenchmarkError):
            assemble(raw=raw, expected_sha256=sha256(raw).hexdigest(),
                     retrieved_at_utc='2030-01-01T00:00:00Z')

    def test_cli_round_trip_synthetic_and_no_database_access(self):
        raw = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.csv'
            source.write_bytes(raw)
            out = root / 'out'
            command = [sys.executable, '-m', 'scripts.oecd_lab_report_v02',
                '--input', str(source), '--raw-sha256', sha256(raw).hexdigest(),
                '--retrieved-at-utc', STAMP, '--out-dir', str(out)]
            response = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertIn('NON_EXECUTABLE_RESEARCH_BENCHMARK', response.stdout)
            self.assertTrue((out / 'research_report.md').is_file())
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn('OUTPUT_DIRECTORY_MUST_NOT_EXIST', again.stderr)

if __name__ == '__main__':
    unittest.main()
