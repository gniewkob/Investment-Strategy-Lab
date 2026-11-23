"""Offline NAV quality checks after proven same-class validation."""
import unittest
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal
import json
from scripts.knf_one_class_nav_quality_v07 import describe_unit_nav
from scripts.knf_original_unit_history_research_v06 import Blocked
from tests.test_knf_original_unit_history_research_v06 import sample,raw

NOW=datetime(2026,11,13,tzinfo=timezone.utc)

def check(args=None):
    a,b,c,d=args or sample()
    return describe_unit_nav(raw(a),raw(b),raw(c),raw(d) if d is not None else None,
                             observed_at=NOW)

class KNFNavQualityV07Tests(unittest.TestCase):
    def test_three_samples_two_adjacent_observations(self):
        x=check()
        self.assertEqual(x["distinct_valuation_days"],3)
        self.assertEqual(x["observed_adjacent_nav_level_changes"],2)
        self.assertEqual(x["first_to_last_nav_level_change_pct_not_total_return"],"0.5000")
        self.assertEqual(x["model_m1_m2_m3"],"INSUFFICIENT_DATA_HOLD_CASH")
        self.assertFalse(x["nav_distribution_adjusted_return"])
        self.assertFalse(x["annualized_volatility_estimate"])
        self.assertFalse(x["historical_first_publication_proven"])
        self.assertEqual(x["financial_operations"],0)
    def test_observed_variability_exact_decimal(self):
        x=check()
        a=(Decimal("99.90")/Decimal("100")-1)*100
        b=(Decimal("100.5")/Decimal("99.90")-1)*100
        self.assertEqual(Decimal(x["smallest_adjacent_observed_nav_level_change_pct"]),a.quantize(Decimal("0.0001")))
        self.assertEqual(Decimal(x["largest_adjacent_observed_nav_level_change_pct"]),b.quantize(Decimal("0.0001")))
        self.assertGreater(Decimal(x["population_stddev_adjacent_observed_nav_level_change_pct_not_annualized"]),0)
    def test_weekday_gap_not_claimed_holiday(self):
        x=check()
        self.assertGreater(x["unobserved_weekday_calendar_dates_not_verified_market_holidays"],0)
        self.assertIn("not_trading_sessions",next(k for k in x if k.startswith("monday_friday")))
    def test_do_not_emit_levels_or_fund_identity(self):
        out=json.dumps(check())
        self.assertNotIn('"valuation"',out)
        self.assertNotIn('"fundId"',out)
        self.assertNotIn('"subfundId"',out)
        self.assertRegex(check()["source_history_sha256"],r"^[0-9a-f]{64}$")
    def test_wrong_currency_fail_closed(self):
        a,b,c,d=sample()
        c["content"][0]["currency"]="EUR"
        with self.assertRaisesRegex(Blocked,"HISTORY_DIFFERENT_FUND_UNIT"):
            check((a,b,c,d))
    def test_duplicate_date_fail_closed(self):
        a,b,c,d=sample()
        c["content"][1]["date"]=c["content"][0]["date"]
        with self.assertRaisesRegex(Blocked,"DUPLICATE"):
            check((a,b,c,d))
    def test_unsupported_kid_must_not_attach(self):
        a,b,c,d=sample()
        b["content"][0]["subfundId"]=123
        x=check((a,b,c,None))
        self.assertFalse(x["kid_exact_same_class_match"])
        self.assertIsNone(x["kid_risk_value_only_if_exact_matching"])
        self.assertTrue(all(v is None for v in x["kid_costs_only_if_exact_matching"].values()))
    def test_lookahead_kid_is_not_used(self):
        a,b,c,d=sample()
        b["content"][0]["publicationDate"]="2026-11-01"
        x=check((a,b,c,None))
        self.assertIsNone(x["kid_risk_value_only_if_exact_matching"])
    def test_zero_nav_blocks(self):
        a,b,c,d=sample()
        c["content"][1]["valuation"]=0
        with self.assertRaises(Blocked):
            check((a,b,c,d))
    def test_future_date_blocks(self):
        a,b,c,d=sample()
        c["content"][1]["date"]="2027-01-01"
        with self.assertRaises(Blocked):
            check((a,b,c,d))
    def test_no_zero_fill_for_missing_data(self):
        a,b,c,d=sample()
        del c["content"][1]["valuation"]
        with self.assertRaises(Blocked):
            check((a,b,c,d))
