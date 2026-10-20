"""Synthetic demo invariants (not market or investment-performance evidence)."""
from unittest import TestCase
from scripts.paper_strategy_tournament import run_tournament
from scripts.paper_tournament_synthetic_demo import make_fixture

class PaperTournamentDemoTests(TestCase):
    def test_hourly_demonstration_only(self):
        result=run_tournament(make_fixture("1h"))
        self.assertEqual(result["bars"],1728)
        self.assertEqual(result["source_vintage"],"SYNTHETIC_OFFLINE_FIXTURE")
        self.assertFalse(result["profitability_proven"])
        self.assertEqual(result["orders_sent"],0)
        self.assertEqual(len(result["strategies"]),5)

    def test_daily_demo_same_cashflow(self):
        result=run_tournament(make_fixture("1d"))
        self.assertEqual(len({s["contributed_pln"] for s in result["strategies"]}),1)
        self.assertEqual(result["database_writes"],0)
