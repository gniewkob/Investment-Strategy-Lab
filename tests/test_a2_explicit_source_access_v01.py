"""A2 independent offline access gate regressions.

Only synthetic in-memory source manifests; absolutely no real provider reads,
DB, paper trade, portfolio connection, or executable market orders.
"""
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

from scripts.nbp_reference_capture import capture, main as capture_cli
from scripts.nbp_bondspot_exact_date_v04 import match
from tests.test_reference_archive_calendar_v04 import sample, official_day_stub


class A2ExplicitSourceAccessTests(unittest.TestCase):
    def test_missing_exact_day_cannot_start_implicit_network_capture(self):
        nbp, bond = sample(36, mismatches=1)
        with patch("scripts.nbp_bondspot_exact_date_v04.capture") as provider:
            with self.assertRaisesRegex(ValueError, "EXPLICIT_FETCH_REQUIRED"):
                match(nbp, bond)
            provider.assert_not_called()

    def test_capture_requires_explicit_fetch_function(self):
        with patch("scripts.nbp_reference_capture._fetch") as provider:
            with self.assertRaisesRegex(ValueError, "EXPLICIT_FETCH_REQUIRED"):
                capture("2021-11-27", "2021-11-27")
            provider.assert_not_called()

    def test_same_day_history_without_gaps_needs_no_fetcher(self):
        nbp, bond = sample(36, mismatches=0)
        with patch("scripts.nbp_bondspot_exact_date_v04.capture") as provider:
            result = match(nbp, bond)
            provider.assert_not_called()
        self.assertEqual(result["official_exact_day_retrieval_count"], 0)
        self.assertFalse(result["historical_publication_hour_verified"])
        self.assertEqual(result["financial_operations"], 0)

    def test_explicit_synthetic_fetch_still_preserves_offline_reconciliation(self):
        nbp, bond = sample(36, mismatches=1)
        stamp = datetime(2026, 11, 6, 14, tzinfo=timezone.utc)
        result = match(nbp, bond, fetch=official_day_stub, clock=lambda: stamp)
        self.assertEqual(result["official_exact_day_retrieval_count"], 1)
        self.assertEqual(result["source_request_count"], 2)
        self.assertEqual(result["financial_operations"], 0)
        self.assertFalse(result["historical_vintage_verified"])

    def test_cli_without_opt_in_flag_is_not_a_provider_fetch(self):
        with patch("sys.argv", ["nbp_reference_capture", "2021-11-27", "2021-11-27"]):
            with patch("scripts.nbp_reference_capture._fetch") as provider:
                with patch("sys.stderr"):
                    with self.assertRaises(SystemExit) as caught:
                        capture_cli()
                self.assertEqual(caught.exception.code, 2)
                provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
