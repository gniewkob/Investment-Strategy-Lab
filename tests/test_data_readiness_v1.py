import unittest

from scripts.data_readiness_v1 import assess


class DataReadinessTests(unittest.TestCase):
    def test_empty_manifest_fails_closed(self):
        result = assess({})
        self.assertEqual(result["backtest"], "NOT_RUN")
        self.assertEqual(set(result["models"].values()), {"INSUFFICIENT_DATA"})
        self.assertEqual(result["paper_events_created"], 0)

    def test_agg_and_price_cannot_be_polish_total_return(self):
        result = assess({"bonds": {"market": "US", "basis": "price"}})
        reasons = result["series"]["bonds"]["reasons"]
        self.assertIn("bond_market_unverified", reasons)
        self.assertIn("total_return_unverified", reasons)

    def test_publication_and_duplicate_guards(self):
        row = {"observed_for": "2020-01-31", "available_at": "2020-01-30T00:00:00Z", "retrieved_at": "2020-02-01T00:00:00Z", "value": 1}
        result = assess({"equity": {"observations": [row, row]}})
        self.assertIn("invalid_or_duplicate_observation", result["series"]["equity"]["reasons"])

    def test_unsupported_attestation_never_promotes_backtest(self):
        item = {"source_url": "https://example.org", "license_status": "verified_permitted", "instrument_kind": "index", "currency": "PLN", "basis": "total_return", "market": "PLN_POLISH_GOVERNMENT", "observations": [{"observed_for": "2020-01-31", "available_at": "2020-02-01T00:00:00Z", "retrieved_at": "2020-02-02T00:00:00Z", "value": 1}]}
        self.assertEqual(assess({k: item for k in ("equity", "bonds", "gold", "usdpln", "eurpln", "inflation", "costs")})["backtest"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
