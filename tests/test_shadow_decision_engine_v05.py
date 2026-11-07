"""Offline tests for read-only M1–M3 shadow signals and real-source gates.

All portfolio levels here are synthetic. No performance claim or trading.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import unittest

from scripts.shadow_decision_engine_v05 import (
    ASSETS, EQUITY, BONDS, GOLD, ShadowInputError, evaluate,
    from_reference_archive,
)
from scripts.reference_archive_calendar_v04 import _digest

ASOF = "2026-11-06T20:00:00+00:00"


def make_months(n=60, *, down=False):
    result=[]
    for i in range(n):
        year=2021+(10+i)//12
        month=(10+i)%12+1
        day=date(year,month,28)
        if down:
            price=2000-i*10
        else:
            price=1000+i*10
        result.append({
            "month":day.strftime("%Y-%m"),
            "observed_for":day.isoformat(),
            "level_pln":str(price),
            "first_usable_at":datetime.combine(day+timedelta(days=1),
                                                datetime.min.time(),
                                                tzinfo=timezone.utc).isoformat(),
        })
    return result


def source(code, *, basis="TOTAL_RETURN", status="VERIFIED_ORIGINAL",
           rights="RESEARCH_USE_DOCUMENTED", rows=None):
    return {
        "series_code":code,
        "source_url":"https://example.invalid/testing-original-prices",
        "source_sha256":sha256(code.encode()).hexdigest(),
        "source_status":status,
        "rights_status":rights,
        "quote_currency":"PLN",
        "return_basis":basis,
        "instrument_kind":"NON_EXECUTABLE_BENCHMARK",
        "retrieved_at":ASOF,
        "observations":make_months() if rows is None else rows,
    }


def sample(*, include=ASSETS, down=False):
    return {
        "mode":"EDUCATIONAL_SHADOW_ONLY",
        "as_of_utc":ASOF,
        "policy_version":"V05_FROZEN_001",
        "series":{code:source(code, rows=make_months(down=down and code==EQUITY))
                  for code in include},
    }


class ShadowDecisionV05Tests(unittest.TestCase):
    def test_without_sources_returns_three_holds_not_three_fake_backtests(self):
        result=evaluate(sample(include=()))
        self.assertEqual(result["eligible_models"],[])
        self.assertEqual(set(result["model_decisions"]),
                         {"M1_GLOBAL_EQ","M2_DIVERSIFIED","M3_TACTICAL"})
        self.assertTrue(all(x["status"]=="HOLD_CASH"
                            for x in result["model_decisions"].values()))
        self.assertFalse(result["profitability_proven"])
        self.assertFalse(result["future_oos_returns_observed"])
        self.assertFalse(result["is_backtest"])
        for field in ("orders_sent","paper_fills","database_writes",
                      "financial_operations"):
            self.assertEqual(result[field],0)
        self.assertEqual(result,evaluate(sample(include=())))

    def test_partial_equity_only_can_simulate_m1_but_not_m2_m3(self):
        r=evaluate(sample(include=(EQUITY,)))
        self.assertEqual(r["eligible_models"],["M1_GLOBAL_EQ"])
        self.assertEqual(r["model_decisions"]["M1_GLOBAL_EQ"]["status"],
                         "VIRTUAL_TARGET_ONLY")
        self.assertEqual(r["model_decisions"]["M1_GLOBAL_EQ"]["target"][EQUITY],
                         "1")
        self.assertEqual(r["model_decisions"]["M2_DIVERSIFIED"]["status"],
                         "HOLD_CASH")
        self.assertEqual(r["model_decisions"]["M3_TACTICAL"]["status"],
                         "HOLD_CASH")
        self.assertFalse(r["provider_license_independently_certified"])
        self.assertEqual(len(r["decision_fingerprint_sha256"]),64)

    def test_complete_synthetic_series_generate_frozen_targets_only(self):
        r=evaluate(sample())
        self.assertEqual(len(r["eligible_models"]),3)
        self.assertEqual(r["model_decisions"]["M1_GLOBAL_EQ"]["target"][EQUITY],"1")
        self.assertEqual(r["model_decisions"]["M2_DIVERSIFIED"]["target"],
                        {EQUITY:"0.6",BONDS:"0.3",GOLD:"0.1","CASH_PLN":"0"})
        self.assertEqual(r["model_decisions"]["M3_TACTICAL"]["reason"],
                         "MOMENTUM_3M_RISK_ON")
        self.assertEqual(r["model_decisions"]["M3_TACTICAL"]["target"][EQUITY],
                         "0.6")
        self.assertFalse(r["historical_pit_certified"])
        self.assertFalse(r["future_oos_returns_observed"])
        self.assertEqual(r["orders_sent"],0)
        self.assertEqual(r["paper_fills"],0)

    def test_three_month_declining_equity_switches_virtual_risk_off(self):
        r=evaluate(sample(down=True))
        self.assertEqual(r["model_decisions"]["M3_TACTICAL"]["reason"],
                         "MOMENTUM_3M_RISK_OFF")
        self.assertEqual(r["model_decisions"]["M3_TACTICAL"]["target"]["CASH_PLN"],
                         "0.3")

    def test_unverified_rights_and_price_only_block_signals(self):
        x=sample()
        x["series"][EQUITY]["rights_status"]="UNVERIFIED"
        x["series"][BONDS]["return_basis"]="BOND_TOTAL_RETURN_BENCHMARK_INDEX"
        x["series"][GOLD]["return_basis"]="PRICE_ONLY"
        r=evaluate(x)
        self.assertEqual(r["eligible_models"],[])
        self.assertIn("RIGHTS_UNVERIFIED",r["source_readiness"][EQUITY]["reasons"])
        self.assertIn("NOT_PLN_TOTAL_RETURN_BENCHMARK",r["source_readiness"][BONDS]["reasons"])
        self.assertIn("NOT_PLN_TOTAL_RETURN_BENCHMARK",r["source_readiness"][GOLD]["reasons"])
        self.assertEqual(r["model_decisions"]["M1_GLOBAL_EQ"]["status"],
                         "HOLD_CASH")

    def test_unverified_original_or_missing_history_blocks(self):
        p=sample(include=(EQUITY,))
        p["series"][EQUITY]["source_status"]="CANDIDATE"
        p["series"][EQUITY]["observations"]=make_months(35)
        r=evaluate(p)
        self.assertEqual(r["eligible_models"],[])
        self.assertIn("ORIGINAL_SOURCE_UNVERIFIED",
                      r["source_readiness"][EQUITY]["reasons"])
        self.assertIn("INSUFFICIENT_CONSECUTIVE_MONTHS",
                      r["source_readiness"][EQUITY]["reasons"])

    def test_no_future_retrieval_no_observation_lookahead(self):
        p=sample(include=(EQUITY,))
        p["series"][EQUITY]["retrieved_at"]="2026-11-07T00:00:00+00:00"
        with self.assertRaisesRegex(ShadowInputError,"future retrieval"):
            evaluate(p)
        p=sample(include=(EQUITY,))
        p["series"][EQUITY]["observations"][-1]["first_usable_at"]="2026-11-07T00:00:00+00:00"
        with self.assertRaisesRegex(ShadowInputError,"look-ahead"):
            evaluate(p)
        p=sample(include=(EQUITY,))
        p["series"][EQUITY]["observations"][-1]["observed_for"]="2026-11-28"
        with self.assertRaisesRegex(ShadowInputError,"outside late month"):
            evaluate(p)

    def test_duplicate_gap_invalid_asset_and_wrong_mode_fail_closed(self):
        p=sample(include=(EQUITY,))
        p["series"][EQUITY]["observations"].pop(20)
        with self.assertRaisesRegex(ShadowInputError,"duplicate or missing month"):
            evaluate(p)
        p=sample(include=(EQUITY,))
        p["series"]["UNAPPROVED_ASSET"]=p["series"][EQUITY]
        with self.assertRaisesRegex(ShadowInputError,"unknown series"):
            evaluate(p)
        p=sample(include=())
        p["mode"]="ALLOW_REAL_TRADES"
        with self.assertRaisesRegex(ShadowInputError,"frozen shadow-only"):
            evaluate(p)

    def test_stale_sources_and_misaligned_calendar_hold(self):
        p=sample(include=(EQUITY,))
        p["as_of_utc"]="2027-02-01T10:00:00+00:00"
        r=evaluate(p)
        self.assertIn("SOURCE_STALE",r["source_readiness"][EQUITY]["reasons"])
        self.assertEqual(r["model_decisions"]["M1_GLOBAL_EQ"]["status"],"HOLD_CASH")
        p=sample(include=ASSETS)
        p["series"][GOLD]["observations"].pop()
        r=evaluate(p)
        self.assertEqual(r["model_decisions"]["M1_GLOBAL_EQ"]["status"],
                         "VIRTUAL_TARGET_ONLY")
        self.assertEqual(r["model_decisions"]["M2_DIVERSIFIED"]["status"],
                         "HOLD_CASH")

    def test_real_reference_archive_never_promotes_tbsp_and_nbp_gold(self):
        timeline=[{"month":x["month"],"same_calendar_date":True}
                  for x in make_months()]
        original={
            "status":"SAME_CALENDAR_DATE_REFERENCE_NOT_PIT_OR_EXECUTABLE",
            "months":60,"first_month":"2021-11","last_month":"2026-10",
            "timeline":timeline, "financial_operations":0,
            "paper_events_created":0,
        }
        original["evidence_sha256"]=_digest(original)
        result=from_reference_archive(original)
        self.assertEqual(result["reference_months"],60)
        self.assertEqual(len(result["missing_model_sources"]),3)
        self.assertEqual(result["model_decisions"]["M1_GLOBAL_EQ"]["status"],
                         "HOLD_CASH")
        self.assertEqual(result["financial_operations"],0)
        self.assertFalse(result["future_oos_returns_observed"])
        tampered=deepcopy(original)
        tampered["timeline"].pop()
        with self.assertRaisesRegex(ShadowInputError,"fingerprint mismatch"):
            from_reference_archive(tampered)
        tampered=deepcopy(original)
        tampered["timeline"][0]["same_calendar_date"]=False
        tampered["evidence_sha256"]=_digest({k:v for k,v in tampered.items()
                                             if k!="evidence_sha256"})
        with self.assertRaisesRegex(ShadowInputError,"insufficient or unaligned"):
            from_reference_archive(tampered)


if __name__=="__main__":
    unittest.main()
