"""Synthetic-only v0.21 tests; never embed real Vanguard NAV levels."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import unittest

from scripts.conditional_m1_nav_analytics_v21 import (
    SCENARIOS, _xirr, _reference_max_drawdown, evaluate,
)
from tests.test_conditional_m1_nav_diagnostic_v20 import sample_receipt, seal


class ConditionalNAVAnalyticsV21Tests(unittest.TestCase):
    def test_four_scenarios_nonexecutible_real_receipt_contract(self):
        r = evaluate(sample_receipt())
        self.assertEqual(r["status"], "CONDITIONAL_NAV_ANALYTICS_RESEARCH_ONLY")
        self.assertEqual(len(r["scenarios"]), 4)
        self.assertEqual(r["months"], 60)
        self.assertEqual(r["total_hypothetical_contributions_pln"], "6000.00")
        self.assertEqual([x["scenario"] for x in r["scenarios"]],
                         [x[0] for x in SCENARIOS])
        self.assertTrue(all(x["cashflow_date_convention"] ==
                            "SOURCE_NAV_DATE_NOT_EXECUTABLE_ORDER_DATE"
                            for x in r["scenarios"]))
        self.assertFalse(r["historical_point_in_time_certified"])
        self.assertFalse(r["qualified_m1_model_backtest"])
        self.assertFalse(r["prospective_oos_performance_proven"])
        self.assertEqual(r["financial_operations"], 0)
        self.assertEqual(r["orders_sent"], 0)

    def test_sensitivity_monotonic_and_cash_xirr_zero(self):
        r = evaluate(sample_receipt())
        amounts = [Decimal(x["hypothetical_net_final_pln"])
                   for x in r["scenarios"]]
        self.assertEqual(amounts, sorted(amounts, reverse=True))
        self.assertGreater(amounts[0], amounts[-1])
        self.assertTrue(all(x["zero_interest_cash_xirr_annual_percent"]
                            == "0.0000" for x in r["scenarios"]))
        self.assertTrue(all(Decimal(x["hypothetical_entry_frictions_pln"]) >= 0
                            for x in r["scenarios"]))

    def test_same_reference_drawdown_across_cost_scenarios(self):
        r = evaluate(sample_receipt())
        self.assertEqual(len({x["nav_pln_reference_max_drawdown_percent"]
                              for x in r["scenarios"]}), 1)
        self.assertEqual(r["drawdown_method"],
                         "NAV_PLN_MONTH_END_REFERENCE_LEVEL_PEAK_TO_TROUGH")
        self.assertTrue(r["drawdown_not_cashflow_portfolio_drawdown"])

    def test_xirr_zero_and_one_year_simple_example(self):
        first = date(2024, 1, 1)
        days = [first + timedelta(days=30*i) for i in range(60)]
        self.assertAlmostEqual(float(_xirr(days, deposit=Decimal("100"),
                                            terminal=Decimal("6000"))), 0, places=8)
        # For two equal-spaced deposits, derive terminal with a declared 10%
        # annual rate; the solver must recover 10% rather than 10%/12.
        target = 0.10
        t0 = days[0]
        terminal = sum(100 * (1+target)**((days[-1]-d).days/365.25)
                       for d in days)
        self.assertAlmostEqual(float(_xirr(days, deposit=Decimal("100"),
                                            terminal=Decimal(str(terminal)))),
                               target, places=7)

    def test_monthly_reference_drawdown_is_peak_to_trough(self):
        levels = list(map(Decimal, ("100", "120", "90", "100", "130", "100")))
        self.assertEqual(_reference_max_drawdown(levels), Decimal("-0.25"))
        self.assertEqual(_reference_max_drawdown(
            [Decimal("100"), Decimal("101"), Decimal("102")]), Decimal("0"))

    def test_mutations_and_unverified_status_rejected(self):
        original = sample_receipt()
        old = deepcopy(original)
        self.assertEqual(evaluate(original), evaluate(deepcopy(original)))
        self.assertEqual(original, old)
        bad = sample_receipt()
        bad["monthly"][0]["nav_pln_reference"] = "999999"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            evaluate(bad)
        bad = sample_receipt()
        bad["usable_as_GLOBAL_EQUITY_TR_PLN"] = True
        seal(bad)
        with self.assertRaisesRegex(ValueError, "unqualified NAV"):
            evaluate(bad)

    def test_missing_month_or_fx_fails_closed(self):
        bad = sample_receipt()
        bad["monthly"].pop(0)
        seal(bad)
        with self.assertRaisesRegex(ValueError, "exact 60-month"):
            evaluate(bad)
        bad = sample_receipt()
        bad["missing_exact_day_fx"] = [{"month":"2022-01"}]
        seal(bad)
        with self.assertRaisesRegex(ValueError, "unqualified NAV"):
            evaluate(bad)

    def test_invalid_xirr_cashflows_rejected(self):
        days = [date(2024,1,1)] * 60
        with self.assertRaisesRegex(ValueError, "dates"):
            _xirr(days,deposit=Decimal("100"),terminal=Decimal("6000"))
        days = [date(2024,1,1) + timedelta(days=30*i) for i in range(60)]
        with self.assertRaisesRegex(ValueError, "cashflows"):
            _xirr(days,deposit=Decimal("0"),terminal=Decimal("6000"))


if __name__ == "__main__":
    unittest.main()
