"""Synthetic-only forward shadow attribution checks; no real investor P&L."""
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
import unittest

from scripts.shadow_decision_engine_v05 import (
    ASSETS, EQUITY, BONDS, GOLD, ShadowInputError, evaluate, _digest,
)
from scripts.shadow_forward_evaluation_v05 import evaluate_forward
from tests.test_shadow_decision_engine_v05 import make_months, source


ASOF="2025-11-06T18:00:00+00:00"
FORWARD="2025-12-02T18:00:00+00:00"


def input_decision(include=ASSETS, *, decline=False):
    data={}
    for code in include:
        rows=make_months(48,down=decline and code==EQUITY)
        obj=source(code,rows=rows)
        obj["retrieved_at"]=ASOF
        data[code]=obj
    payload={"mode":"EDUCATIONAL_SHADOW_ONLY",
             "as_of_utc":ASOF,"policy_version":"V05_FROZEN_001",
             "series":data}
    return evaluate(payload)


def future_reference(decision, *, include=ASSETS):
    rows={}
    for code in include:
        model=decision["model_decisions"]["M1_GLOBAL_EQ" if code==EQUITY
                else "M2_DIVERSIFIED"]
        baseline=model["signal_evidence"]["baseline_level_sha256"].get(code)
        if not baseline:
            raise AssertionError("missing synthetic source fixture baseline")
        # Oct 2025 in tests, computed from source fixture with n=48.
        prev="1470"
        if code==EQUITY:
            val="1500"
        elif code==BONDS:
            val="1485"
        else:
            val="1460"
        rows[code]={
            "month":"2025-11","observed_for":"2025-11-28",
            "first_usable_at":"2025-11-29T10:00:00+00:00",
            "prior_level_pln":prev,"level_pln":val,
            "raw_sha256":sha256(("forward-"+code).encode()).hexdigest(),
            "return_basis":"TOTAL_RETURN",
            "quote_currency":"PLN",
            "instrument_kind":"NON_EXECUTABLE_BENCHMARK",
            "source_status":"VERIFIED_ORIGINAL",
            "rights_status":"RESEARCH_USE_DOCUMENTED",
        }
    return {"mode":"EDUCATIONAL_FORWARD_REFERENCE_ONLY",
            "source_vintage":"SYNTHETIC_OFFLINE_FIXTURE",
            "as_of_utc":FORWARD,"series":rows,
            "fee_bps":"20","slippage_bps":"10"}


class ShadowForwardV05Tests(unittest.TestCase):
    def test_no_market_data_means_no_forward_performance(self):
        r=evaluate_forward(input_decision(include=()),future_reference(input_decision(),include=()))
        self.assertTrue(all(x["status"]=="NOT_EVALUABLE_PREVIOUSLY_HOLD_CASH"
                            for x in r["results"].values()))
        self.assertTrue(all(x["hypothetical_gross_return"] is None
                            for x in r["results"].values()))
        self.assertFalse(r["statistical_edge_proven"])
        self.assertIsNone(r["sharpe"])
        self.assertEqual(r["orders_sent"],0)
        self.assertEqual(r["paper_fills"],0)

    def test_one_synthetic_forward_period_calculates_reference_only(self):
        decision=input_decision()
        future=future_reference(decision)
        result=evaluate_forward(decision,future)
        self.assertTrue(all(x["status"]=="ONE_FORWARD_REFERENCE_PERIOD_RESEARCH_ONLY"
                            for x in result["results"].values()))
        self.assertEqual(result["periods_evaluated_per_model_max"],1)
        self.assertEqual(result["results"]["M1_GLOBAL_EQ"]["reference_month"],"2025-11")
        self.assertEqual(result["results"]["M1_GLOBAL_EQ"]["hypothetical_gross_return"],
                         format((__import__("decimal").Decimal("1500") /
                                 __import__("decimal").Decimal("1470"))-1,"f"))
        self.assertLess(float(result["results"]["M1_GLOBAL_EQ"]["hypothetical_net_return_after_assumed_costs"]),
                        float(result["results"]["M1_GLOBAL_EQ"]["hypothetical_gross_return"]))
        self.assertIsNone(result["sharpe"])
        self.assertIsNone(result["max_drawdown"])
        self.assertFalse(result["investable_execution_price_verified"])
        self.assertFalse(result["historical_pit_certified"])
        self.assertEqual(result["transactions"],0)
        self.assertEqual(result["orders_sent"],0)
        self.assertEqual(result,evaluate_forward(deepcopy(decision),deepcopy(future)))

    def test_partial_virtual_model_evaluation_does_not_fill_missing_assets(self):
        decision=input_decision(include=(EQUITY,))
        future=future_reference(input_decision(),include=(EQUITY,))
        result=evaluate_forward(decision,future)
        self.assertEqual(result["results"]["M1_GLOBAL_EQ"]["status"],
                         "ONE_FORWARD_REFERENCE_PERIOD_RESEARCH_ONLY")
        self.assertEqual(result["results"]["M2_DIVERSIFIED"]["status"],
                         "NOT_EVALUABLE_PREVIOUSLY_HOLD_CASH")
        self.assertEqual(result["results"]["M3_TACTICAL"]["status"],
                         "NOT_EVALUABLE_PREVIOUSLY_HOLD_CASH")

    def test_corrupted_previous_decision_or_baseline_rejected(self):
        decision=input_decision()
        decision["model_decisions"]["M1_GLOBAL_EQ"]["target"][EQUITY]="0.9"
        with self.assertRaisesRegex(ShadowInputError,"fingerprint mismatch"):
            evaluate_forward(decision,future_reference(input_decision()))
        decision=input_decision()
        forward=future_reference(decision)
        forward["series"][EQUITY]["prior_level_pln"]="1480"
        with self.assertRaisesRegex(ShadowInputError,"prior frozen level"):
            evaluate_forward(decision,forward)

    def test_missing_reference_prevents_only_models_requiring_it(self):
        d=input_decision()
        x=future_reference(d)
        x["series"].pop(GOLD)
        result=evaluate_forward(d,x)
        self.assertEqual(result["results"]["M1_GLOBAL_EQ"]["status"],
                         "ONE_FORWARD_REFERENCE_PERIOD_RESEARCH_ONLY")
        self.assertEqual(result["results"]["M2_DIVERSIFIED"]["status"],
                         "NOT_EVALUABLE_FORWARD_SERIES_MISSING")

    def test_reject_future_before_decision_and_ineligible_publication(self):
        d=input_decision()
        f=future_reference(d)
        f["as_of_utc"]="2025-11-01T18:00:00+00:00"
        with self.assertRaisesRegex(ShadowInputError,"follow frozen decision"):
            evaluate_forward(d,f)
        f=future_reference(d)
        f["series"][EQUITY]["first_usable_at"]="2025-12-03T00:00:00+00:00"
        with self.assertRaisesRegex(ShadowInputError,"look-ahead"):
            evaluate_forward(d,f)

    def test_reject_retrospectively_frozen_decision_before_delayed_publication(self):
        # Forged decision: created after the forward market close, but before
        # its delayed publication. A publication-only check previously passed.
        d=input_decision()
        d["as_of_utc"]="2025-11-28T18:00:00+00:00"
        d["decision_fingerprint_sha256"]=_digest({
            k:v for k,v in d.items() if k!="decision_fingerprint_sha256"
        })
        f=future_reference(d)
        with self.assertRaisesRegex(ShadowInputError,"observation must postdate"):
            evaluate_forward(d,f)

    def test_wrong_asset_semantics_and_invalid_costs_rejected(self):
        d=input_decision()
        f=future_reference(d)
        f["series"][EQUITY]["return_basis"]="PRICE_ONLY"
        with self.assertRaisesRegex(ShadowInputError,"declared usable"):
            evaluate_forward(d,f)
        f=future_reference(d)
        f["fee_bps"]="-1"
        with self.assertRaisesRegex(ShadowInputError,"outside 0"):
            evaluate_forward(d,f)
        f=future_reference(d)
        f["fee_bps"]="nan"
        with self.assertRaisesRegex(ShadowInputError,"outside 0"):
            evaluate_forward(d,f)

    def test_no_live_execution_mode_and_no_future_prospective_date(self):
        d=input_decision()
        f=future_reference(d)
        f["mode"]="REAL_ORDERS"
        with self.assertRaisesRegex(ShadowInputError,"no financial account"):
            evaluate_forward(d,f)
        f=future_reference(d)
        f["source_vintage"]="FUTURE_PROSPECTIVE_RESEARCH"
        f["as_of_utc"]="2032-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(ShadowInputError,"future dated"):
            evaluate_forward(d,f)


if __name__=="__main__":
    unittest.main()
