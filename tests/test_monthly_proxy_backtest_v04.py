"""Synthetic-only acceptance tests for monthly proxy research backtest v0.4."""
from __future__ import annotations

import calendar
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import unittest

from scripts.monthly_proxy_backtest_v04 import (
    ASSETS, BacktestValidationError, run_backtest, validate,
)


def fixture(n=18, *, fee="20", slip="10", train=10, start_year=2024):
    periods = []
    series = {}
    for asset in ASSETS:
        series[asset] = {
            "quote_currency": "PLN",
            "return_basis": "TOTAL_RETURN",
            "instrument_kind": "NON_EXECUTABLE_BENCHMARK",
            "source_url": "https://research.example.org/reference/" + asset,
            "source_sha256": sha256(asset.encode()).hexdigest(),
            "rows": [],
        }
    for i in range(n):
        year = start_year + i // 12
        month = (i % 12) + 1
        end = date(year, month, calendar.monthrange(year, month)[1])
        first_next_year = year + (month == 12)
        first_next_month = 1 if month == 12 else month + 1
        first_usable = f"{first_next_year:04d}-{first_next_month:02d}-01T00:00:00+00:00"
        decision = f"{first_next_year:04d}-{first_next_month:02d}-02T10:00:00+00:00"
        periods.append({"month": f"{year:04d}-{month:02d}",
                        "decision_at": decision})
        for asset, growth in [
            ("GLOBAL_EQUITY_TR_PLN", Decimal("1.02")),
            ("PL_BONDS_TR_PLN", Decimal("1.005")),
            ("GOLD_TR_PLN", Decimal("1.01")),
        ]:
            price = Decimal("100") * growth**i
            series[asset]["rows"].append({
                "month": f"{year:04d}-{month:02d}",
                "observed_for": end.isoformat(),
                "first_usable_at": first_usable,
                "level_pln": format(price, "f"),
            })
    return {
        "mode": "EDUCATIONAL_RESEARCH_ONLY",
        "source_vintage": "SYNTHETIC_OFFLINE_FIXTURE",
        "historical_pit_certified": False,
        "monthly_contribution_pln": "100",
        "fee_bps": fee, "slippage_bps": slip,
        "training_periods": train,
        "periods": periods, "series": series,
    }


class MonthlyProxyBacktestTests(unittest.TestCase):
    def test_completes_three_models_same_budget_no_db_or_trading(self):
        result = run_backtest(fixture())
        self.assertEqual(result["status"], "SYNTHETIC_TEST_ONLY")
        self.assertEqual(len(result["results"]), 3)
        self.assertEqual([x["model_code"] for x in result["results"]],
                         ["M1_GLOBAL_EQ", "M2_DIVERSIFIED", "M3_TACTICAL"])
        self.assertEqual({r["contributed_pln"] for r in result["results"]},
                         {"1800.00"})
        self.assertEqual(result["training_periods"], 10)
        self.assertEqual(result["test_periods"], 8)
        self.assertEqual(result["real_orders"], 0)
        self.assertEqual(result["paper_events_created"], 0)
        self.assertEqual(result["database_connections"], 0)
        self.assertEqual(result["database_writes"], 0)
        self.assertFalse(result["investment_performance_proven"])
        self.assertFalse(result["historical_pit_certified"])
        self.assertTrue(result["monthly_reference_levels_are_not_executable_quotes"])
        self.assertTrue(result["costs_are_scenarios_not_actual_broker_fees"])
        for r in result["results"]:
            self.assertEqual(len(r["timeline"]), 18)
            self.assertTrue(all(x["segment"] in ("IN_SAMPLE", "OUT_OF_SAMPLE")
                                for x in r["timeline"]))
            self.assertTrue(all(Decimal(x["cash_pln"]) >= 0
                                for x in r["timeline"]))
            self.assertGreaterEqual(Decimal(r["assumed_fees_pln"]), 0)

    def test_deterministic_hash_and_input_change(self):
        p = fixture()
        self.assertEqual(run_backtest(p), run_backtest(deepcopy(p)))
        second = deepcopy(p)
        second["series"]["PL_BONDS_TR_PLN"]["rows"][-1]["level_pln"] = "500"
        self.assertNotEqual(run_backtest(p)["input_sha256"],
                            run_backtest(second)["input_sha256"])
        self.assertNotEqual(run_backtest(p)["results"],
                            run_backtest(second)["results"])

    def test_zero_cost_equity_dca_matches_fractional_index_accounting(self):
        p = fixture(fee="0", slip="0")
        r = run_backtest(p)["results"][0]
        prices = [
            Decimal(x["level_pln"])
            for x in p["series"]["GLOBAL_EQUITY_TR_PLN"]["rows"]
        ]
        expected = sum((Decimal("100") * prices[-1] / x
                        for x in prices), Decimal(0))
        self.assertLess(abs(Decimal(r["end_reference_value_pln"]) - expected),
                        Decimal("0.02"))
        self.assertEqual(r["cash_pln"], "0.00")
        self.assertEqual(r["assumed_fees_pln"], "0.00")
        self.assertEqual(r["assumed_slippage_pln"], "0.00")
        self.assertGreater(Decimal(r["net_reference_pnl_pln"]), 0)

    def test_explicit_costs_do_not_artificially_improve_equity_dca(self):
        expensive = run_backtest(fixture(fee="90", slip="50"))["results"][0]
        free = run_backtest(fixture(fee="0", slip="0"))["results"][0]
        self.assertLess(Decimal(expensive["end_reference_value_pln"]),
                        Decimal(free["end_reference_value_pln"]))
        self.assertGreater(Decimal(expensive["assumed_fees_pln"]), 0)
        self.assertGreater(Decimal(expensive["assumed_slippage_pln"]), 0)
        self.assertEqual(free["assumed_fees_pln"], "0.00")

    def test_risk_filter_has_three_month_warmup_then_predeclared_risk_on(self):
        r = run_backtest(fixture())["results"][2]
        reasons = [x["signal"] for x in r["timeline"]]
        self.assertEqual(reasons[:3], ["MOMENTUM_WARMUP_HOLD_CASH"] * 3)
        self.assertEqual(reasons[3:], ["MOMENTUM_RISK_ON"] * 15)
        self.assertEqual(r["timeline"][0]["cash_pln"], "100.00")
        self.assertEqual(r["timeline"][1]["cash_pln"], "200.00")
        self.assertEqual(r["timeline"][2]["cash_pln"], "300.00")
        self.assertEqual(r["timeline"][3]["hypothetical_weights"],
                         {"GLOBAL_EQUITY_TR_PLN": "0.6000",
                          "PL_BONDS_TR_PLN": "0.3000",
                          "GOLD_TR_PLN": "0.1000"})

    def test_negative_three_months_switches_risk_off_to_cash(self):
        p = fixture()
        for i, row in enumerate(p["series"]["GLOBAL_EQUITY_TR_PLN"]["rows"]):
            row["level_pln"] = str(Decimal("100") * Decimal(".95")**i)
        m3 = run_backtest(p)["results"][2]
        self.assertEqual(m3["timeline"][3]["signal"], "MOMENTUM_RISK_OFF")
        w = m3["timeline"][3]["hypothetical_weights"]
        self.assertEqual(w["GLOBAL_EQUITY_TR_PLN"], "0.3000")
        self.assertEqual(w["PL_BONDS_TR_PLN"], "0.3000")
        self.assertEqual(w["GOLD_TR_PLN"], "0.1000")
        self.assertGreater(Decimal(m3["timeline"][3]["cash_pln"]), 0)

    def test_future_month_cannot_change_past_decision_signal(self):
        original = run_backtest(fixture())["results"][2]
        p = fixture()
        p["series"]["GLOBAL_EQUITY_TR_PLN"]["rows"][-1]["level_pln"] = "10"
        changed = run_backtest(p)["results"][2]
        self.assertEqual([x["signal"] for x in original["timeline"][:-1]],
                         [x["signal"] for x in changed["timeline"][:-1]])
        self.assertNotEqual(original["timeline"][-1]["signal"],
                            changed["timeline"][-1]["signal"])

    def test_missing_series_returns_not_run_without_valuation(self):
        p = fixture()
        del p["series"]["PL_BONDS_TR_PLN"]
        result = run_backtest(p)
        self.assertEqual(result["status"], "NOT_RUN_INSUFFICIENT_DATA")
        self.assertEqual(result["missing_required_series"], ["PL_BONDS_TR_PLN"])
        self.assertEqual(result["results"], [])
        self.assertFalse(result["performance_proven"])
        self.assertEqual(result["paper_events_created"], 0)
        self.assertEqual(result["database_writes"], 0)

    def test_absent_data_all_three_sources_not_run(self):
        p = fixture()
        p["series"] = {}
        result = run_backtest(p)
        self.assertEqual(result["missing_required_series"], list(ASSETS))
        self.assertEqual(result["results"], [])

    def test_rejects_false_pit_and_live_execution_mode(self):
        p = fixture()
        p["historical_pit_certified"] = True
        with self.assertRaises(BacktestValidationError):
            run_backtest(p)
        p = fixture()
        p["mode"] = "LIVE_TRADING"
        with self.assertRaises(BacktestValidationError):
            run_backtest(p)
        p = fixture()
        p["source_vintage"] = "CERTIFIED_HISTORICAL_PIT"
        with self.assertRaises(BacktestValidationError):
            run_backtest(p)

    def test_rejects_wrong_currency_basis_and_tradability_claims(self):
        for field, val in (("quote_currency", "USD"),
                           ("return_basis", "PRICE_ONLY"),
                           ("instrument_kind", "TRADABLE_PRICE")):
            p = fixture()
            p["series"]["GOLD_TR_PLN"][field] = val
            with self.subTest(field=field), self.assertRaises(
                    BacktestValidationError):
                run_backtest(p)

    def test_rejects_unverified_or_insecure_sources(self):
        for url in ("http://example.org/research",
                    "https://user:secret@example.org/series",
                    "https://example.org/series#fragment"):
            p = fixture()
            p["series"]["GLOBAL_EQUITY_TR_PLN"]["source_url"] = url
            with self.subTest(url=url), self.assertRaises(
                    BacktestValidationError):
                run_backtest(p)
        p = fixture()
        p["series"]["GLOBAL_EQUITY_TR_PLN"]["source_sha256"] = "invalid"
        with self.assertRaises(BacktestValidationError):
            run_backtest(p)

    def test_late_observation_and_unavailable_benchmark_rejected(self):
        p = fixture()
        p["series"]["GOLD_TR_PLN"]["rows"][4]["first_usable_at"] = (
            "2024-06-03T00:00:00+00:00")
        with self.assertRaisesRegex(BacktestValidationError, "unavailable"):
            run_backtest(p)
        p = fixture()
        p["series"]["GOLD_TR_PLN"]["rows"][4]["observed_for"] = "2024-06-01"
        with self.assertRaisesRegex(BacktestValidationError, "late-month"):
            run_backtest(p)

    def test_missing_and_duplicate_months_rejected(self):
        p = fixture()
        p["periods"][8]["month"] = p["periods"][7]["month"]
        with self.assertRaises(BacktestValidationError):
            run_backtest(p)
        p = fixture()
        p["periods"][8]["month"] = "2024-11"
        with self.assertRaises(BacktestValidationError):
            run_backtest(p)

    def test_periods_need_separate_training_and_test_windows(self):
        for train in (0, 3, 15, 18, True, "10"):
            p = fixture()
            p["training_periods"] = train
            with self.subTest(train=train), self.assertRaises(
                    BacktestValidationError):
                run_backtest(p)

    def test_rejects_invalid_unbounded_costs_and_prices(self):
        for fee, slip in (("-1", "0"), ("201", "0"),
                          ("0", "300"), ("nan", "0")):
            p = fixture(fee=fee, slip=slip)
            with self.subTest(fee=fee, slip=slip), self.assertRaises(
                    BacktestValidationError):
                run_backtest(p)
        p = fixture()
        p["series"]["PL_BONDS_TR_PLN"]["rows"][4]["level_pln"] = "-3"
        with self.assertRaises(BacktestValidationError):
            run_backtest(p)
        p = fixture()
        p["series"]["PL_BONDS_TR_PLN"]["rows"][4]["level_pln"] = "NaN"
        with self.assertRaises(BacktestValidationError):
            run_backtest(p)

    def test_reconstruction_not_misreported_as_certified_or_real_return(self):
        short = fixture()
        short["source_vintage"] = "HISTORICAL_RESEARCH_RECONSTRUCTION"
        insufficient = run_backtest(short)
        self.assertEqual(insufficient["status"], "NOT_RUN_INSUFFICIENT_HISTORY")
        self.assertEqual(insufficient["available_months"], 18)
        self.assertEqual(insufficient["minimum_historical_months"], 36)
        self.assertEqual(insufficient["results"], [])
        p = fixture(n=48, train=30, start_year=2022)
        p["source_vintage"] = "HISTORICAL_RESEARCH_RECONSTRUCTION"
        r = run_backtest(p)
        self.assertEqual(r["status"], "CONDITIONAL_HISTORICAL_RECONSTRUCTION")
        self.assertFalse(r["historical_pit_certified"])
        self.assertFalse(r["investment_performance_proven"])
        self.assertEqual(r["accounting_basis"],
                         "NON_EXECUTABLE_FRACTIONAL_TOTAL_RETURN_INDEX_PROXY")
        self.assertEqual(r["real_orders"], 0)
        self.assertEqual(r["paper_events_created"], 0)

    def test_five_year_monthly_synthetic_scenario_not_real_performance(self):
        r = run_backtest(fixture(n=60, train=36))
        self.assertEqual(r["status"], "SYNTHETIC_TEST_ONLY")
        self.assertEqual((r["training_periods"], r["test_periods"]), (36, 24))
        self.assertEqual({x["contributed_pln"] for x in r["results"]},
                         {"6000.00"})
        self.assertEqual({len(x["timeline"]) for x in r["results"]}, {60})
        self.assertEqual(r["real_orders"], 0)
        self.assertFalse(r["investment_performance_proven"])

    def test_historical_reconstruction_must_not_use_future_data(self):
        p = fixture(n=48, train=30, start_year=2024)
        p["source_vintage"] = "HISTORICAL_RESEARCH_RECONSTRUCTION"
        with self.assertRaisesRegex(BacktestValidationError, "future date"):
            run_backtest(p)

    def test_nonboolean_self_certification_field_rejected(self):
        p = fixture()
        p["historical_pit_certified"] = "true"
        with self.assertRaisesRegex(BacktestValidationError, "self-certify"):
            run_backtest(p)

    def test_allocation_leverage_never_exceeds_one(self):
        r = run_backtest(fixture())
        for model in r["results"]:
            for month in model["timeline"]:
                total = sum((Decimal(v) for v in
                             month["hypothetical_weights"].values()),
                            Decimal("0"))
                self.assertLessEqual(total, Decimal("1"))
                self.assertGreaterEqual(Decimal(month["cash_pln"]), Decimal("0"))


if __name__ == "__main__":
    unittest.main()
