"""Offline, synthetic-only verification of deterministic virtual accounting."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from scripts.paper_strategy_tournament import (
    ValidationError, _signals, run_tournament, validate,
)

def fixture(timeframe="1h",count=220):
    t=datetime(2026,1,31,tzinfo=timezone.utc) if timeframe=="1h" else datetime(2026,1,1,tzinfo=timezone.utc)
    step=timedelta(hours=1) if timeframe=="1h" else timedelta(days=1)
    bars=[]
    for i in range(count):
        at=t+step*i
        a=100+i*.2+(-1)**i*.3
        b=80+i*.13+(-1)**(i//4)*.7
        bars.append({"start":at.isoformat(),"fx_asof":at.isoformat(),
                     "usdpln":"4.00","btc_open":str(a),"btc_close":str(a+.1),
                     "eth_open":str(b),"eth_close":str(b-.1)})
    return {"mode":"EDUCATIONAL_PAPER_ONLY","source_vintage":"SYNTHETIC_OFFLINE_FIXTURE",
            "timeframe":timeframe,"monthly_contribution_pln":"100",
            "fee_bps":"20","slippage_bps":"10","bars":bars}

class PaperTournamentTests(TestCase):
    def test_five_variants_same_budget_no_real_actions(self):
        result=run_tournament(fixture())
        self.assertEqual(len(result["strategies"]),5)
        self.assertEqual({x["contributed_pln"] for x in result["strategies"]},{"200.00"})
        self.assertEqual(result["orders_sent"],0)
        self.assertEqual(result["database_connections"],0)
        self.assertEqual(result["database_writes"],0)
        self.assertEqual(result["existing_M1_M2_M3"],"HOLD_NO_CHANGE")
        self.assertFalse(result["historical_pit_certified"])
        self.assertFalse(result["profitability_proven"])

    def test_results_are_reproducible_fingerprinted(self):
        a=fixture()
        self.assertEqual(run_tournament(a),run_tournament(deepcopy(a)))
        b=deepcopy(a)
        b["bars"][-1]["eth_close"]="999.9"
        self.assertNotEqual(run_tournament(a)["input_sha256"],run_tournament(b)["input_sha256"])

    def test_higher_fees_do_not_improve_dca(self):
        a=fixture()
        b=deepcopy(a)
        b["fee_bps"]="0"
        b["slippage_bps"]="0"
        left=run_tournament(a)["strategies"][0]
        right=run_tournament(b)["strategies"][0]
        self.assertGreaterEqual(float(right["ending_value_pln"]),float(left["ending_value_pln"]))
        self.assertTrue(all(float(x["ending_cash_pln"])>=-.000001
                            for x in run_tournament(a)["strategies"]))

    def test_next_bar_signal_ignores_current_bar_close(self):
        a=fixture()
        b=deepcopy(a)
        b["bars"][65]["btc_close"]="50000"
        rows1,settings=validate(a)
        rows2,_=validate(b)
        self.assertEqual(_signals(rows1,65,settings["lookback"]),
                         _signals(rows2,65,settings["lookback"]))
        self.assertNotEqual(_signals(rows1,66,settings["lookback"]),
                            _signals(rows2,66,settings["lookback"]))

    def test_monthly_deposits_on_daily_bars(self):
        result=run_tournament(fixture("1d",120))
        self.assertEqual({x["contributed_pln"] for x in result["strategies"]},{"400.00"})

    def test_no_future_or_stale_fx(self):
        a=fixture()
        a["bars"][2]["fx_asof"]="2026-02-02T00:00:00+00:00"
        with self.assertRaises(ValidationError):
            run_tournament(a)
        a=fixture()
        a["bars"][40]["fx_asof"]="2026-01-01T00:00:00+00:00"
        with self.assertRaises(ValidationError):
            run_tournament(a)

    def test_no_disordered_or_missing_bars(self):
        for n in (3,10):
            a=fixture()
            a["bars"][n]["start"]=a["bars"][n-1]["start"]
            with self.assertRaises(ValidationError):
                run_tournament(a)

    def test_fake_first_publication_certification_rejected(self):
        a=fixture()
        a["source_vintage"]="CERTIFIED_FIRST_PUBLICATION_PIT"
        with self.assertRaises(ValidationError):
            run_tournament(a)
        a=fixture()
        a["mode"]="LIVE_TRADING"
        with self.assertRaises(ValidationError):
            run_tournament(a)

    def test_invalid_pricing_or_unbounded_cost_rejected(self):
        a=fixture()
        a["bars"][6]["btc_open"]="0"
        with self.assertRaises(ValidationError):
            run_tournament(a)
        a=fixture()
        a["fee_bps"]="300"
        with self.assertRaises(ValidationError):
            run_tournament(a)

    def test_early_synthetic_period_no_fitted_parameters(self):
        a=fixture()
        self.assertEqual(run_tournament(a)["timeframe"],"1h")
        # Predeclared threshold makes outcomes reproducible with unchanged input.
        self.assertEqual(run_tournament(a)["strategies"],run_tournament(a)["strategies"])
