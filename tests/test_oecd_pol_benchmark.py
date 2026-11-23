"""Synthetic OECD-shaped fixtures only; no network or market observations."""
import csv
import hashlib
import io
import unittest
from scripts.oecd_pol_benchmark import benchmark, parse_csv, BenchmarkError, render_report

FIELDS = ['STRUCTURE', 'STRUCTURE_ID', 'ACTION', 'REF_AREA', 'FREQ', 'MEASURE',
          'UNIT_MEASURE', 'ACTIVITY', 'ADJUSTMENT', 'TRANSFORMATION', 'TIME_HORIZ',
          'METHODOLOGY', 'TIME_PERIOD', 'OBS_VALUE', 'OBS_STATUS', 'UNIT_MULT', 'BASE_PER']

def fixture():
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=FIELDS)
    writer.writeheader()
    for i in range(48):
        writer.writerow(dict(STRUCTURE='DATAFLOW', STRUCTURE_ID='OECD.SDD.STES:DSD_STES@DF_FINMARK(4.0)',
            ACTION='I', REF_AREA='POL', FREQ='M', MEASURE='SHARE', UNIT_MEASURE='IX',
            ACTIVITY='_Z', ADJUSTMENT='_Z', TRANSFORMATION='_Z', TIME_HORIZ='_Z',
            METHODOLOGY='N', TIME_PERIOD=f'{2022+i//12}-{1+i%12:02}', OBS_VALUE='100',
            OBS_STATUS='A', UNIT_MULT='0', BASE_PER='2015'))
    return buf.getvalue().encode()

class OECDTests(unittest.TestCase):
    def test_constant_index_and_research_boundary(self):
        data = fixture()
        result = benchmark(parse_csv(data, '2026-11-23T12:00:00Z'))
        self.assertEqual(result['status'], 'NON_EXECUTABLE_RESEARCH_BENCHMARK')
        self.assertEqual(result['contributions_pln'], '4800')
        self.assertEqual(result['terminal_index_equivalent_pln'], '4800')
        self.assertEqual(result['source_receipt']['sha256'], hashlib.sha256(data).hexdigest())
        self.assertFalse(result['historical_pit_certified'])
        self.assertFalse(result['model_admitted'])
        self.assertIn('not an executable', render_report(result))

    def test_increasing_final_index_changes_only_the_hypothetical_mark(self):
        data = fixture().replace(b'2025-12,100,', b'2025-12,200,')
        result = benchmark(parse_csv(data, '2026-11-23T12:00:00Z'))
        self.assertEqual(result['terminal_index_equivalent_pln'], '9500')
        self.assertEqual(result['cash_baseline_pln'], '4800')
        self.assertFalse(result['executable_price_certified'])
        self.assertFalse(result['total_return_certified'])

    def test_rejects_gaps_duplicates_wrong_series_and_bad_values(self):
        data = fixture()
        for changed in (data.replace(b'2022-02', b'2022-01'),
                        data.replace(b'2022-02', b'2026-02'),
                        data.replace(b',POL,', b',DEU,', 1),
                        data.replace(b',100,', b',NaN,', 1),
                        data.replace(b',2015\r\n', b',2020\r\n', 1),
                        data.replace(b',100,', b',0,', 1),
                        data + b'\n'):
            with self.subTest(changed=changed[:60]), self.assertRaises(BenchmarkError):
                parse_csv(changed, '2026-11-23T12:00:00Z')

    def test_receipt_time_must_be_explicit_utc_and_valid(self):
        for value in ('2022-01-01', 'x', '2020-01-01T00:00:00Z', '2026-11-23T12:00:00+01:00'):
            with self.subTest(value=value), self.assertRaises(BenchmarkError):
                parse_csv(fixture(), value)

if __name__ == '__main__':
    unittest.main()
