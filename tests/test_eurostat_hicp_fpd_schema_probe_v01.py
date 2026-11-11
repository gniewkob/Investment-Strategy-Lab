"""Synthetic, entirely offline FPD schema-probe tests: no inflation values."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.eurostat_hicp_fpd_schema_probe_v01 import (
    FPDProbeError, _read_offline, schema_receipt, FIXED_QUERY,
)


def example():
    return {
        "version": "2.0",
        "class": "dataset",
        "source": "ESTAT",
        "updated": "2026-10-16T00:00:00+0200",
        "id": ["freq", "unit", "coicop18", "geo", "release", "time"],
        "size": [1, 1, 1, 1, 2, 3],
        "dimension": {
            "freq": {"category": {"index": {"M": 0}}},
            "unit": {"category": {"index": {"I25": 0}}},
            "coicop18": {"category": {"index": {"TOTAL": 0}}},
            "geo": {"category": {"index": {"PL": 0}}},
            "release": {"category": {
                "index": {"R1": 0, "R2": 1},
                "label": {"R1": "first release", "R2": "following release"},
            }},
            "time": {"category": {
                "index": {"2026-07": 0, "2026-08": 1, "2026-09": 2},
            }},
        },
        "value": {"0": 103.212345, "5": 999999.999},
        "status": {"0": "e"},
    }


class EurostatFPDSchemaProbeTests(unittest.TestCase):
    def assert_research_only(self, output):
        self.assertEqual(output["dataset"], "prc_hicp_fpd")
        self.assertEqual(output["qualified_model_series"], [])
        self.assertEqual(output["paper_candidates"], [])
        self.assertEqual(output["model_state"], "HOLD_CASH")
        self.assertEqual(output["release_dimension_id"], "release")
        self.assertEqual(output["expected_selector"], FIXED_QUERY)
        self.assertFalse(output["historical_pit_certified"])
        self.assertFalse(output["first_release_value_compared"])
        self.assertFalse(output["original_release_date_per_value_authenticated"])
        self.assertFalse(output["index_values_emitted"])
        for key in ("financial_operations", "orders_sent", "paper_fills", "database_writes"):
            self.assertEqual(output[key], 0)
        self.assertRegex(output["receipt_sha256"], r"^[0-9a-f]{64}$")

    def test_standard_metadata_only_and_no_levels_disclosed(self):
        receipt = schema_receipt(example())
        self.assert_research_only(receipt)
        encoded = json.dumps(receipt)
        self.assertNotIn("103.212345", encoded)
        self.assertNotIn("999999.999", encoded)
        self.assertNotIn('"value"', encoded)
        self.assertEqual(len(receipt["dimensions"]), 6)

    def test_dimension_order_changes_preserved_without_value_decoding(self):
        data = example()
        data["id"] = list(reversed(data["id"]))
        data["size"] = list(reversed(data["size"]))
        result = schema_receipt(data)
        self.assert_research_only(result)
        self.assertEqual(result["dimensions"][0]["id"], "time")

    def test_supports_list_category_index_as_jsonstat_variant(self):
        data = example()
        data["dimension"]["release"]["category"]["index"] = ["R1", "R2"]
        receipt = schema_receipt(data)
        self.assert_research_only(receipt)

    def test_provenance_hash_changes_but_never_pit_certified(self):
        a = schema_receipt(example())
        changed = example()
        changed["value"]["0"] = 888888.12345
        b = schema_receipt(changed)
        self.assertNotEqual(a["canonical_local_response_sha256"],
                            b["canonical_local_response_sha256"])
        self.assert_research_only(b)
        self.assertNotIn("888888.12345", json.dumps(b))

    def test_no_mutation_or_nondeterminism(self):
        data = example()
        before = deepcopy(data)
        self.assertEqual(schema_receipt(data), schema_receipt(deepcopy(data)))
        self.assertEqual(data, before)

    def test_unknown_source_version_or_class_is_rejected(self):
        for field, value in (
                ("version", "1.0"), ("class", "table"),
                ("source", "third-party"), ("source", None)):
            data = example()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(FPDProbeError):
                schema_receipt(data)

    def test_missing_or_spoofed_release_dimension_is_rejected(self):
        data = example()
        data["id"][-2] = "wallet"
        data["dimension"]["wallet"] = data["dimension"].pop("release")
        with self.assertRaisesRegex(FPDProbeError, "Release"):
            schema_receipt(data)
        data = example()
        data["id"].remove("release")
        data["size"].remove(2)
        data["dimension"].pop("release")
        with self.assertRaisesRegex(FPDProbeError, "extra release"):
            schema_receipt(data)

    def test_out_of_range_index_or_cardinality_rejected(self):
        data = example()
        data["dimension"]["release"]["category"]["index"] = {"R1": 0, "R2": 0}
        with self.assertRaisesRegex(FPDProbeError, "position map"):
            schema_receipt(data)
        data = example()
        data["size"][4] = 199
        with self.assertRaisesRegex(FPDProbeError, "count mismatch"):
            schema_receipt(data)

    def test_extra_dim_or_unbounded_category_label_rejected(self):
        data = example()
        data["id"].append("asset_return")
        data["size"].append(1)
        data["dimension"]["asset_return"] = {"category": {"index": {"TR": 0}}}
        with self.assertRaisesRegex(FPDProbeError, "extra release"):
            schema_receipt(data)
        data = example()
        data["dimension"]["release"]["category"]["label"]["R1"] = "A" * 181
        with self.assertRaisesRegex(FPDProbeError, "unbounded category"):
            schema_receipt(data)

    def test_bounded_local_inputs_symlink_and_invalid_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            valid = root / "fpd.json"
            valid.write_text(json.dumps(example()), encoding="utf-8")
            self.assertEqual(_read_offline(valid), example())
            linked = root / "linked.json"
            linked.symlink_to(valid)
            with self.assertRaisesRegex(FPDProbeError, "bounded regular"):
                _read_offline(linked)
            oversized = root / "oversized.json"
            oversized.write_bytes(b" " * 2_000_001)
            with self.assertRaisesRegex(FPDProbeError, "bounded regular"):
                _read_offline(oversized)


if __name__ == "__main__":
    unittest.main()
