"""Deterministic synthetic research tests; no market data or network."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.paper_multi_asset_research_v02 import (
    MultiAssetBlocked, compare, synthetic_manifest, markdown,
)


class MultiAssetResearchTests(unittest.TestCase):
    def setUp(self):
        self.manifest = synthetic_manifest()

    def test_complete_three_portfolio_synthetic_run(self):
        r = compare(self.manifest)
        self.assertEqual(r["months"], 60)
        self.assertEqual(r["cash_baseline_pln"], "6000.00")
        self.assertEqual([x["id"] for x in r["strategies"]], ["SIM_M1", "SIM_M2", "SIM_M3"])
        self.assertTrue(all(len(x["path"]) == 60 for x in r["strategies"]))
        self.assertTrue(all(float(x["fees_paid_pln"]) > 0 for x in r["strategies"]))
        self.assertEqual(r["paper_decision"], "INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual((r["financial_operations"],r["orders_sent"],r["database_writes"]), (0,0,0))
        self.assertFalse(r["historical_point_in_time_certified"])
        self.assertFalse(r["executable_prices_certified"])
        self.assertIn("fikcyjnych", markdown(r))

    def test_determinism_and_no_mutation(self):
        original = copy.deepcopy(self.manifest)
        self.assertEqual(compare(self.manifest),compare(self.manifest))
        self.assertEqual(self.manifest,original)

    def test_reject_wrong_source_or_price_semantics(self):
        for field,value in [("source_class","VERIFIED"),("currency","USD"),
                            ("simulation_mode","REAL_ORDER"),("monthly_contribution_pln",True)]:
            p = copy.deepcopy(self.manifest)
            p[field] = value
            with self.subTest(field=field),self.assertRaises(MultiAssetBlocked):
                compare(p)

    def test_reject_future_price_and_missing_month(self):
        p = copy.deepcopy(self.manifest)
        p["observations"][0]["available_month"] = "2021-02"
        with self.assertRaisesRegex(MultiAssetBlocked,"LOOKAHEAD"):
            compare(p)
        p = copy.deepcopy(self.manifest)
        del p["observations"][15]
        with self.assertRaisesRegex(MultiAssetBlocked,"MISSING_OR_DUPLICATE"):
            compare(p)

    def test_reject_nonpositive_missing_nan_and_float_prices(self):
        for value in ("0", "-2", "NaN", "Infinity", 100.0):
            p = copy.deepcopy(self.manifest)
            p["observations"][8]["levels_pln"]["ASSET_A"] = value
            with self.subTest(value=value),self.assertRaises(MultiAssetBlocked):
                compare(p)
        p = copy.deepcopy(self.manifest)
        del p["observations"][4]["levels_pln"]["ASSET_C"]
        with self.assertRaises(MultiAssetBlocked): compare(p)

    def test_reject_wrong_weights_and_strategy_identity(self):
        for value in (9999,-1,True,1.5):
            p = copy.deepcopy(self.manifest)
            p["strategies"][0]["weights_bps"]["ASSET_B"] = value
            with self.subTest(value=value),self.assertRaises(MultiAssetBlocked): compare(p)
        p = copy.deepcopy(self.manifest)
        p["strategies"][1]["id"] = "REAL_M2"
        with self.assertRaises(MultiAssetBlocked): compare(p)

    def test_reject_cost_exceeding_small_allocation(self):
        p = copy.deepcopy(self.manifest)
        p["strategies"][0]["fee_fixed_pln_per_order"] = "20"
        with self.assertRaisesRegex(MultiAssetBlocked,"FEE_EXCEEDS"):
            compare(p)

    def test_reject_incomplete_window(self):
        p = copy.deepcopy(self.manifest)
        p["observations"] = p["observations"][:35]
        with self.assertRaisesRegex(MultiAssetBlocked,"MONTH_COUNT"):
            compare(p)

    def test_no_network_or_persistence_required(self):
        import socket
        old = socket.socket.connect
        try:
            socket.socket.connect = lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("NETWORK_USED"))
            self.assertEqual(compare(self.manifest)["database_writes"],0)
        finally:
            socket.socket.connect = old

    def test_cli_creates_report_and_rejects_existing_target(self):
        with tempfile.TemporaryDirectory() as td:
            dst=Path(td)/"out"
            cmd=[sys.executable,"-m","scripts.paper_multi_asset_research_v02","--synthetic-demo","--out-dir",str(dst)]
            p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads((dst/"comparison.json").read_text())["months"],60)
            self.assertIn("INSUFFICIENT_DATA",(dst/"report.md").read_text())
            self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)


if __name__=="__main__": unittest.main()
