import json
import unittest
from scripts.world_bank_gem_audit_v04 import MONTHS, analyze


def raw(rows, total=None, pages=1):
    return json.dumps([{'total': len(rows) if total is None else total, 'pages': pages}, rows]).encode()


def row(month, value=100):
    return {'date': month, 'value': value, 'country': {'id': 'USA'}, 'indicator': {'id': 'DSTKMKTXD'}}


class AuditTests(unittest.TestCase):
    def test_empty_world_is_blocked_with_all_months_missing(self):
        r = analyze(b'[{"total":0,"pages":0},null]', 'WLD', 'DSTKMKTXD')
        self.assertEqual(r['count'], 0)
        self.assertEqual(r['missing_months'], MONTHS)

    def test_complete_and_gaps(self):
        result = analyze(raw([row(m) for m in MONTHS]), 'USA', 'DSTKMKTXD')
        self.assertEqual(result['missing_months'], [])
        result = analyze(raw([row(m) for m in MONTHS[:-1]]), 'USA', 'DSTKMKTXD')
        self.assertEqual(result['missing_months'], [MONTHS[-1]])

    def test_duplicates_bad_values_identity_and_pagination_rejected(self):
        for body in (raw([row(MONTHS[0]), row(MONTHS[0])]), raw([row(MONTHS[0], None)]),
                     raw([row(MONTHS[0], -1)]), raw([row(MONTHS[0])], total=2),
                     raw([row(MONTHS[0])], pages=2)):
            with self.subTest(body=body), self.assertRaises(ValueError):
                analyze(body, 'USA', 'DSTKMKTXD')
        with self.assertRaises(ValueError):
            analyze(raw([row(MONTHS[0])]), 'WLD', 'DSTKMKTXD')


if __name__ == '__main__':
    unittest.main()
