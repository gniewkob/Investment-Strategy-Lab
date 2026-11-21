"""Deterministic offline tests, using synthetic price observations only."""
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from scripts.paper_scenario_engine_v01 import (
    run_scenario, ScenarioBlocked, analyze_manifest, synthetic_demo_manifest,
)


def sample(prices=("10", "20", "20")):
    return [{"month": f"2026-{i:02d}", "available_month": f"2026-{i:02d}",
             "price_pln": p} for i, p in enumerate(prices, 1)]


class PaperScenarioEngineTests(unittest.TestCase):
    def test_asset_contributions_and_mark_to_market(self):
        result = run_scenario(observations=sample())
        self.assertEqual(Decimal(result["ending_value_pln"]), Decimal("400"))
        self.assertEqual(result["contributions_pln"], "300")
        self.assertEqual(Decimal(result["difference_vs_cash_pln"]), Decimal("100"))
        self.assertEqual(result["orders_sent"], 0)
        self.assertFalse(result["model_admitted"])

    def test_cash_baseline_ignores_market(self):
        result = run_scenario(observations=sample(), mode="cash")
        self.assertEqual(result["ending_value_pln"], "300")
        self.assertEqual(result["total_fees_pln"], "0")

    def test_costs_are_deducted_before_fractional_purchase(self):
        result = run_scenario(observations=sample(("10", "10", "10")), fee_fixed_pln="1", fee_rate="0.01")
        self.assertEqual(Decimal(result["ending_value_pln"]), Decimal("294"))
        self.assertEqual(Decimal(result["total_fees_pln"]), Decimal("6.00"))

    def test_one_month_exact_mark(self):
        result = run_scenario(observations=sample(("2",)))
        self.assertEqual(result["ending_value_pln"], "100")

    def test_unavailable_future_price_rejected(self):
        rows = sample()
        rows[0]["available_month"] = "2026-02"
        with self.assertRaisesRegex(ScenarioBlocked, "LOOK_AHEAD"):
            run_scenario(observations=rows)

    def test_missing_and_duplicate_month_rejected(self):
        for rows in (sample()[:1] + sample()[2:], sample()[:2] + sample()[1:2]):
            with self.subTest(rows=rows), self.assertRaisesRegex(ScenarioBlocked, "NONCONTIGUOUS"):
                run_scenario(observations=rows)

    def test_nan_boolean_and_negative_values_rejected(self):
        for bad in ("NaN", "Infinity", "-4", True, 1.1):
            rows = sample()
            rows[0]["price_pln"] = bad
            with self.subTest(bad=bad), self.assertRaises(ScenarioBlocked):
                run_scenario(observations=rows)

    def test_extreme_price_exponents_fail_closed(self):
        for price in ("1e-999999", "1e999999", "1e-999", "1e999", "9" * 300):
            rows = sample()
            rows[0]["price_pln"] = price
            with self.subTest(price=price[:20]), self.assertRaises(ScenarioBlocked):
                run_scenario(observations=rows)

    def test_fees_cannot_use_more_than_contribution(self):
        with self.assertRaises(ScenarioBlocked):
            run_scenario(observations=sample(), fee_fixed_pln="100")

    def test_no_network_or_persistence(self):
        import socket
        original = socket.socket.connect
        try:
            socket.socket.connect = lambda *_: (_ for _ in ()).throw(AssertionError("network"))
            result = run_scenario(observations=sample())
            self.assertEqual(result["database_writes"], 0)
        finally:
            socket.socket.connect = original


if __name__ == "__main__":
    unittest.main()

from scripts.paper_scenario_engine_v01 import compare_scenarios


class PaperScenarioComparisonTests(unittest.TestCase):
    def test_cash_and_fee_sensitive_comparison(self):
        strategies = [
            {"name": "zero fee", "fee_fixed_pln": "0", "fee_rate": "0"},
            {"name": "charged", "fee_fixed_pln": "1", "fee_rate": "0.01"},
        ]
        result = compare_scenarios(observations=sample(), strategies=strategies)
        self.assertEqual([x["name"] for x in result["comparison"]],
                         ["zero fee", "charged", "cash"])
        by_name = {x["name"]: x for x in result["comparison"]}
        self.assertEqual(Decimal(by_name["zero fee"]["ending_value_pln"]), Decimal("400"))
        self.assertEqual(Decimal(by_name["charged"]["ending_value_pln"]), Decimal("392"))
        self.assertEqual(by_name["cash"]["ending_value_pln"], "300")
        self.assertFalse(result["ranking_is_investment_recommendation"])
        self.assertFalse(result["model_admitted"])

    def test_different_prices_can_rank_cash_higher(self):
        result = compare_scenarios(observations=sample(("20", "10", "5")),
                                   strategies=[{"name": "asset", "fee_fixed_pln": "0", "fee_rate": "0"}])
        self.assertEqual(result["comparison"][0]["name"], "cash")
        self.assertEqual(Decimal(result["comparison"][1]["ending_value_pln"]), Decimal("175"))

    def test_reject_duplicate_and_bad_strategies(self):
        cases = [
            [],
            [{"name": "Cash", "fee_fixed_pln": "0", "fee_rate": "0"}],
            [{"name": "a", "fee_fixed_pln": "0", "fee_rate": "0"},
             {"name": "A", "fee_fixed_pln": "0", "fee_rate": "0"}],
            [{"name": "x", "fee_fixed_pln": "0"}],
            [{"name": "a\nline", "fee_fixed_pln": "0", "fee_rate": "0"}],
        ]
        for strategies in cases:
            with self.subTest(strategies=strategies), self.assertRaises(ScenarioBlocked):
                compare_scenarios(observations=sample(), strategies=strategies)

    def test_unverified_prices_remain_unqualified(self):
        result = compare_scenarios(observations=sample(), source_class="UNVERIFIED_EXTERNAL",
                                   strategies=[{"name": "asset", "fee_fixed_pln": "0", "fee_rate": "0"}])
        self.assertEqual(result["source_class"], "UNVERIFIED_EXTERNAL")
        self.assertFalse(result["historical_pit_certified"])
        self.assertEqual(result["orders_sent"], 0)

    def test_rejects_missing_month_in_all_strategies(self):
        with self.assertRaisesRegex(ScenarioBlocked, "NONCONTIGUOUS"):
            compare_scenarios(observations=sample()[:1] + sample()[2:],
                              strategies=[{"name": "asset", "fee_fixed_pln": "0", "fee_rate": "0"}])


class PaperScenarioReportTests(unittest.TestCase):
    def test_synthetic_demo_is_reproducible_and_cash_gated(self):
        payload = synthetic_demo_manifest()
        result = analyze_manifest(payload)
        self.assertEqual(result["months"], 60)
        self.assertEqual(result["first_month"], "2021-01")
        self.assertEqual(result["last_month"], "2025-12")
        self.assertEqual(result["contributions_pln"], "6000")
        self.assertEqual(result["source_class"], "SYNTHETIC")
        self.assertEqual(len(result["comparison"]), 6)  # five fee cases + cash
        self.assertFalse(result["model_admitted"])
        self.assertFalse(result["historical_pit_certified"])
        self.assertEqual(result["financial_operations"], 0)
        self.assertEqual(analyze_manifest(payload), result)
        self.assertEqual(len(result["input_sha256"]), 64)

    def test_manifest_rejects_ambiguous_provenance_and_schema(self):
        base = synthetic_demo_manifest()
        for changes in (
            {"currency": "USD"},
            {"mode": "LIVE_TRADING"},
            {"source_class": "VERIFIED_MARKET_DATA"},
            {"price_basis": "TOTAL_RETURN_INDEX"},
            {"monthly_contribution_pln": 100.0},
        ):
            payload = dict(base, **changes)
            with self.subTest(changes=changes), self.assertRaises(ScenarioBlocked):
                analyze_manifest(payload)
        payload = dict(base, trust_me=True)
        with self.assertRaises(ScenarioBlocked):
            analyze_manifest(payload)

    def test_unverified_inputs_keep_hold_cash_gate(self):
        payload = synthetic_demo_manifest()
        payload["source_class"] = "UNVERIFIED_EXTERNAL"
        result = analyze_manifest(payload)
        self.assertEqual(result["source_class"], "UNVERIFIED_EXTERNAL")
        self.assertEqual(result["paper_decision"], "HOLD_CASH")
        self.assertFalse(result["model_admitted"])

    def test_cli_produces_reproducible_json_and_markdown_report(self):
        with tempfile.TemporaryDirectory() as work:
            command = [sys.executable, "-m", "scripts.paper_scenario_engine_v01",
                       "--synthetic-demo", "--out-dir", work]
            first = subprocess.run(command, text=True, capture_output=True, check=True)
            output = Path(work, "comparison.json")
            report = Path(work, "report.md")
            self.assertTrue(output.is_file())
            self.assertTrue(report.is_file())
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["months"], 60)
            self.assertIn("HOLD_CASH", report.read_text(encoding="utf-8"))
            self.assertIn("SYNTHETIC", report.read_text(encoding="utf-8"))
            self.assertIn("| cash | 6000.00 | 0.00 | 0.00 |",
                          report.read_text(encoding="utf-8"))
            self.assertIn("comparison.json", first.stdout)
            saved = (output.read_bytes(), report.read_bytes())
            subprocess.run(command, text=True, capture_output=True, check=True)
            self.assertEqual((output.read_bytes(), report.read_bytes()), saved)

    def test_cli_rejects_bad_manifest_before_creating_report(self):
        with tempfile.TemporaryDirectory() as work:
            invalid = Path(work, "bad.json")
            payload = dict(synthetic_demo_manifest(), source_class="VERIFIED_MARKET_DATA")
            invalid.write_text(json.dumps(payload), encoding="utf-8")
            out_dir = Path(work, "report")
            command = [sys.executable, "-m", "scripts.paper_scenario_engine_v01",
                       "--input", str(invalid), "--out-dir", str(out_dir)]
            failed = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("MANIFEST_SOURCE_UNQUALIFIED", failed.stderr)
            self.assertFalse(out_dir.exists())

    def test_cli_accepts_explicit_unverified_external_schema(self):
        with tempfile.TemporaryDirectory() as work:
            src = Path(work, "input.json")
            payload = dict(synthetic_demo_manifest(), source_class="UNVERIFIED_EXTERNAL")
            src.write_text(json.dumps(payload), encoding="utf-8")
            out_dir = Path(work, "report")
            subprocess.run([sys.executable, "-m", "scripts.paper_scenario_engine_v01",
                            "--input", str(src), "--out-dir", str(out_dir)],
                           check=True, text=True, capture_output=True)
            result = json.loads(Path(out_dir, "comparison.json").read_text(encoding="utf-8"))
            self.assertEqual(result["source_class"], "UNVERIFIED_EXTERNAL")
            self.assertEqual(result["paper_decision"], "HOLD_CASH")
