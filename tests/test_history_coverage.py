"""Synthetic continuous/partial rolling history tests; no network or account access."""
from copy import deepcopy
import json
import unittest

from scripts import history_coverage as c

ADDRESS = "0x" + "a" * 40
TOKEN = "0x" + "b" * 40
LABEL = "synthetic"
CHAIN = 8453
KEY = "chain_synthetic_8453"
ENTRIES = [(CHAIN, ADDRESS, LABEL, frozenset({TOKEN}))]


def source(start, end, status="OK"):
    if status != "OK":
        return {KEY: {"status": status, "data": None}}
    return {KEY: {"status": "OK", "data": {
        "wallets": [{"wallet_label": LABEL, "chain_id": CHAIN,
                     "source_block_number": end,
                     "history": {"status": "COMPLETE_REQUESTED_TOKEN_RANGE",
                                 "from_block": start, "to_block": end}}]}}}


class HistoryCoverageTests(unittest.TestCase):
    def test_first_complete_window_only_not_full_history(self):
        out = c.advance(None, ENTRIES, source(1000, 1999))
        self.assertEqual(out["gap_range_count"], 0)
        self.assertFalse(out["historical_gap_detected"])
        self.assertFalse(out["complete_chain_history_certified"])
        self.assertFalse(out["account_to_chain_linkage_certified"])
        self.assertEqual(out["streams"][KEY]["first_complete_from_block"], 1000)
        self.assertEqual(out["streams"][KEY]["last_complete_to_block"], 1999)

    def test_overlapping_and_adjacent_success_remain_contiguous(self):
        first = c.advance(None, ENTRIES, source(1000, 1999))
        second = c.advance(first, ENTRIES, source(1500, 2499))
        third = c.advance(second, ENTRIES, source(2500, 2999))
        self.assertFalse(third["historical_gap_detected"])
        self.assertEqual(third["streams"][KEY]["last_complete_to_block"], 2999)
        self.assertEqual(third["streams"][KEY]["latest_status"], "COMPLETE_RANGE")

    def test_partial_rpc_failure_does_not_advance_and_gap_is_sticky(self):
        first = c.advance(None, ENTRIES, source(1000, 1999))
        before = deepcopy(first)
        failed = c.advance(first, ENTRIES, source(0, 0, "PARTIAL"))
        self.assertEqual(first, before)
        self.assertEqual(failed["streams"][KEY]["last_complete_to_block"], 1999)
        self.assertTrue(failed["latest_source_incomplete"])
        recovered = c.advance(failed, ENTRIES, source(2500, 3499))
        self.assertEqual(recovered["streams"][KEY]["gap_ranges"], [[2000, 2499]])
        self.assertTrue(recovered["historical_gap_detected"])
        recovered_again = c.advance(recovered, ENTRIES, source(3000, 3999))
        self.assertEqual(recovered_again["streams"][KEY]["gap_ranges"], [[2000, 2499]])
        self.assertTrue(recovered_again["historical_gap_detected"])
        self.assertEqual(recovered_again["financial_operations"], 0)

    def test_unavailable_without_success_never_becomes_empty_complete(self):
        first = c.advance(None, ENTRIES, source(0, 0, "UNAVAILABLE"))
        self.assertIsNone(first["streams"][KEY]["last_complete_to_block"])
        self.assertTrue(first["latest_source_incomplete"])
        next_ = c.advance(first, ENTRIES, source(501, 1500))
        self.assertFalse(next_["latest_source_incomplete"])
        self.assertFalse(next_["historical_gap_detected"])
        self.assertEqual(next_["streams"][KEY]["first_complete_from_block"], 501)

    def test_provider_block_regression_does_not_erase_high_watermark(self):
        first = c.advance(None, ENTRIES, source(1000, 1999))
        out = c.advance(first, ENTRIES, source(900, 1899))
        self.assertEqual(out["streams"][KEY]["latest_status"], "BLOCK_REGRESSION")
        self.assertEqual(out["streams"][KEY]["last_complete_to_block"], 1999)
        self.assertTrue(out["latest_source_incomplete"])

    def test_watch_identity_rotation_resets_coverage_explicitly(self):
        first = c.advance(None, ENTRIES, source(1000, 1999))
        rotated = [(CHAIN, "0x" + "c"*40, LABEL, frozenset({TOKEN}))]
        result = c.advance(first, rotated, source(5000, 5999))
        self.assertTrue(result["streams"][KEY]["scope_reset"])
        self.assertEqual(result["streams"][KEY]["first_complete_from_block"], 5000)
        self.assertEqual(result["gap_range_count"], 0)
        self.assertNotIn(ADDRESS, json.dumps(result))

    def test_token_allowlist_change_resets_coverage(self):
        first = c.advance(None, ENTRIES, source(1000, 1999))
        rotated = [(CHAIN, ADDRESS, LABEL, frozenset())]
        result = c.advance(first, rotated, source(5000, 5999))
        self.assertTrue(result["streams"][KEY]["scope_reset"])

    def test_malformed_old_state_or_response_fails_closed(self):
        first = c.advance(None, ENTRIES, source(1000, 1999))
        bad = deepcopy(first)
        bad["streams"][KEY]["last_complete_to_block"] = "1999"
        with self.assertRaises(c.CoverageError):
            c.advance(bad, ENTRIES, source(2000, 2999))
        bad = deepcopy(first)
        bad["streams"][KEY]["gap_ranges"] = [[3, 2]]
        with self.assertRaises(c.CoverageError):
            c.advance(bad, ENTRIES, source(2000, 2999))
        for a,b in ((3000,2999),(3000,4001),(True,3000)):
            with self.subTest(start=a,end=b):
                with self.assertRaises(c.CoverageError):
                    c.advance(first, ENTRIES, source(a,b))
        malformed = source(2000, 2999)
        malformed[KEY]["data"]["wallets"][0]["wallet_label"] = "different"
        with self.assertRaises(c.CoverageError):
            c.advance(first, ENTRIES, malformed)

    def test_gap_limit_never_silently_erases_incompleteness(self):
        first = c.advance(None, ENTRIES, source(0, 0))
        for n in range(66):
            first = c.advance(first, ENTRIES, source(n*3+2, n*3+2))
        self.assertEqual(first["gap_range_count"], c.MAX_GAPS)
        self.assertTrue(first["streams"][KEY]["gap_range_overflow"])
        self.assertTrue(first["historical_gap_detected"])

    def test_does_not_publish_watch_address_or_contract(self):
        result = c.advance(None, ENTRIES, source(1000, 1999))
        serialized = json.dumps(result)
        self.assertNotIn(ADDRESS, serialized)
        self.assertNotIn(TOKEN, serialized)
        self.assertEqual(result["financial_operations"], 0)


if __name__ == "__main__":
    unittest.main()
