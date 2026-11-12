"""Schema-only probe contract: no implicit network or investment operations."""
import json
import unittest
from datetime import datetime, timezone
from scripts.eurostat_pl_bond_yield_source_probe_v04 import (
    inspect_source_shape, PublicEurostatProbeBlocked, URL, MAX_BYTES,
)

CLOCK = datetime(2026, 11, 12, tzinfo=timezone.utc)


def sample():
    return {
        "version": "2.0", "class": "dataset", "source": "ESTAT",
        "id": ["freq", "int_rt", "geo", "time"],
        "size": [1, 1, 1, 2],
        "dimension": {
            "freq": {"category": {"index": {"M": 0}}},
            "int_rt": {"category": {"index": {"MCBY": 0}}},
            "geo": {"category": {"index": {"PL": 0}}},
            "time": {"category": {"index": {"2026-08": 0, "2026-09": 1}}},
        },
        "value": {"0": 5.0, "1": 5.1},
    }


class EurostatPLBondYieldProbeTests(unittest.TestCase):
    def test_source_metadata_no_raw_values(self):
        out = inspect_source_shape(json.dumps(sample()).encode(), observed_at=CLOCK)
        self.assertEqual(out["time_count"], 2)
        self.assertEqual(out["fixed_category_codes"]["int_rt"], ["MCBY"])
        self.assertNotIn("5.0", json.dumps(out))
        self.assertFalse(out["bond_holding_period_total_return"])
        self.assertFalse(out["historical_pit_certified"])
        self.assertEqual(out["qualified_model_series"], [])
        self.assertEqual(out["financial_operations"], 0)

    def test_only_official_fixed_query(self):
        self.assertTrue(URL.startswith(
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/irt_lt_mcby_m?"))
        self.assertIn("geo=PL", URL)
        self.assertIn("int_rt=MCBY", URL)

    def test_invalid_payload_and_oversize_blocked(self):
        for raw in (b"", b"bad", b"{}", b"x" * (MAX_BYTES + 1)):
            with self.subTest(size=len(raw)), self.assertRaises(PublicEurostatProbeBlocked):
                inspect_source_shape(raw, observed_at=CLOCK)

    def test_naive_clock_blocked(self):
        with self.assertRaisesRegex(PublicEurostatProbeBlocked, "CLOCK_REQUIRED"):
            inspect_source_shape(json.dumps(sample()).encode(),
                                 observed_at=datetime(2026, 11, 12))

    def test_mismatched_dimensions_blocked(self):
        p = sample()
        p["size"] = [1, 1, 1, 3]
        with self.assertRaisesRegex(PublicEurostatProbeBlocked, "CATEGORIES_INVALID"):
            inspect_source_shape(json.dumps(p).encode(), observed_at=CLOCK)


if __name__ == "__main__":
    unittest.main()
