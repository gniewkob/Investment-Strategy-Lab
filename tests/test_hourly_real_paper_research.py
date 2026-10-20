"""Offline-only historical source bridge tests; no market performance assertion."""
from datetime import date, datetime, timedelta, timezone
import json
from unittest import TestCase
from unittest.mock import patch

from scripts.hourly_real_paper_research import (
    SourceError, build_payload, parse_nbp, fetch_nbp, _timestamp, START, END,
    research_once,
)
from scripts.paper_strategy_tournament import run_tournament

def nbp_fixture(start=date(2026,7,20),count=24):
    rows=[]
    for i in range(count):
        day=start+timedelta(days=i)
        rows.append({"no":f"{i+120}/A/NBP/{day.year}",
                     "effectiveDate":day.isoformat(),"mid":str(3.7+i*.001)})
    return json.dumps({"table":"A","currency":"dolar amerykański",
                       "code":"USD","rates":rows}).encode()


def dummy_bars(begin,end):
    btc={}
    eth={}
    for i,t in enumerate(range(begin,end,3600)):
        btc[t]={"open":str(100+i*.01),"close":str(100+i*.01+.003)}
        eth[t]={"open":str(80+i*.02),"close":str(80+i*.02-.004)}
    return btc,eth


class HistoricalNBPPaperTests(TestCase):
    def test_nbp_publication_day_and_one_day_lag(self):
        rows,receipt=parse_nbp(nbp_fixture(),date(2026,7,20),date(2026,8,12))
        self.assertEqual(len(rows),24)
        self.assertEqual(rows[date(2026,7,31)]["assumed_eligible_utc"],
                         "2026-08-01T00:00:00+00:00")
        self.assertFalse(receipt["historical_as_published_content_certified"])

    def test_nbp_wrong_source_rejected(self):
        raw=json.loads(nbp_fixture());raw["code"]="GBP"
        with self.assertRaises(SourceError):
            parse_nbp(json.dumps(raw).encode(),date(2026,7,20),date(2026,8,12))

    def test_nbp_duplicate_publication_day_rejected(self):
        raw=json.loads(nbp_fixture())
        raw["rates"].append(dict(raw["rates"][-1]))
        with self.assertRaises(SourceError):
            parse_nbp(json.dumps(raw).encode(),date(2026,7,20),date(2026,8,12))

    def test_nbp_future_or_bad_rate_rejected(self):
        raw=json.loads(nbp_fixture())
        raw["rates"][0]["mid"]="NaN"
        with self.assertRaises(SourceError):
            parse_nbp(json.dumps(raw).encode(),date(2026,7,20),date(2026,8,12))
        raw=json.loads(nbp_fixture())
        raw["rates"][0]["effectiveDate"]="2026-07-19"
        with self.assertRaises(SourceError):
            parse_nbp(json.dumps(raw).encode(),date(2026,7,20),date(2026,8,12))

    def test_next_day_NBP_visibility_gate_on_first_hour(self):
        base=_timestamp("2026-08-01T00:00:00Z")
        rates,_=parse_nbp(nbp_fixture(),date(2026,7,20),date(2026,8,12))
        btc,eth=dummy_bars(base,base+48*3600)
        payload=build_payload(btc,eth,rates,base,base+48*3600)
        self.assertEqual(payload["bars"][0]["fx_asof"],"2026-08-01T00:00:00+00:00")
        self.assertEqual(payload["bars"][0]["usdpln"],rates[date(2026,7,31)]["mid"])
        self.assertEqual(payload["source_vintage"],"RECONSTRUCTED_HISTORICAL_REFERENCE")
        result=run_tournament(payload)
        self.assertFalse(result["historical_pit_certified"])
        self.assertFalse(result["profitability_proven"])
        self.assertEqual(result["orders_sent"],0)

    def test_no_FX_before_eligible_date(self):
        base=_timestamp("2026-07-20T00:00:00Z")
        btc,eth=dummy_bars(base,base+48*3600)
        rates,_=parse_nbp(nbp_fixture(),date(2026,7,20),date(2026,8,12))
        with self.assertRaisesRegex(SourceError,"previously eligible"):
            build_payload(btc,eth,rates,base,base+48*3600)

    def test_source_gap_fails_closed(self):
        base=_timestamp("2026-08-01T00:00:00Z")
        btc,eth=dummy_bars(base,base+48*3600)
        del btc[base+3*3600]
        rates,_=parse_nbp(nbp_fixture(),date(2026,7,20),date(2026,8,12))
        with self.assertRaisesRegex(SourceError,"Missing market"):
            build_payload(btc,eth,rates,base,base+48*3600)

    def test_reproducible_spanning_two_months(self):
        begin=_timestamp("2026-08-01T00:00:00Z")
        end=_timestamp("2026-09-03T00:00:00Z")
        btc,eth=dummy_bars(begin,end)
        rates={}
        day=date(2026,7,31)
        for i in range(38):
            today=day+timedelta(days=i)
            eligible=datetime(today.year,today.month,today.day,tzinfo=timezone.utc)+timedelta(days=1)
            rates[today]={"mid":"3.8","assumed_eligible_utc":eligible.isoformat(),
                          "effective_date":today.isoformat(),"table_no":f"{i+1}/A/NBP/2026"}
        payload=build_payload(btc,eth,rates,begin,end)
        result=run_tournament(payload)
        self.assertEqual(result["bars"],792)
        self.assertEqual({s["contributed_pln"] for s in result["strategies"]},{"200.00"})
        self.assertFalse(result["profitability_proven"])
        self.assertEqual(result["existing_M1_M2_M3"],"HOLD_NO_CHANGE")

    def test_reject_excessive_nbp_query(self):
        with self.assertRaises(SourceError):
            fetch_nbp(date(2026,1,1),date(2026,7,1))

    def test_61day_paper_trial_reuses_one_market_source_for_three_cost_cases(self):
        begin,end=_timestamp(START),_timestamp(END)
        btc,eth=dummy_bars(begin,end)
        fx={}
        day=date(2026,7,31)
        while day<=date(2026,9,30):
            ts=datetime(day.year,day.month,day.day,tzinfo=timezone.utc)+timedelta(days=1)
            fx[day]={"mid":"3.8","assumed_eligible_utc":ts.isoformat(),
                     "effective_date":day.isoformat(),"table_no":"fixture"}
            day+=timedelta(days=1)
        source={"BTC-USD":btc,"ETH-USD":eth}
        with patch("scripts.hourly_real_paper_research.fetch_hourly",
                   side_effect=lambda asset, a, b: (source[asset],
                      {"product_id":asset,"bars":len(source[asset]),"source_chunks":1})) as downloaded:
            with patch("scripts.hourly_real_paper_research.fetch_nbp",
                       return_value=(fx,{"observed_nbp_release_dates":len(fx)})) as currency:
                result=research_once()
        self.assertEqual(downloaded.call_count,2)
        self.assertEqual(currency.call_count,1)
        self.assertEqual(result["results"]["bars"],1464)
        scenarios=result["fixed_policy_friction_sensitivity"]
        self.assertEqual([s["scenario"] for s in scenarios],
                         ["ZERO_COST_DIAGNOSTIC","FROZEN_BASELINE","DOUBLE_COST_STRESS"])
        self.assertEqual(len(scenarios[0]["policies"]),5)
        self.assertEqual({s["contributed_pln"] for s in result["results"]["strategies"]},{"200.00"})
        self.assertFalse(result["market_prediction_edge_proven"])
        self.assertFalse(result["results"]["historical_pit_certified"])
        self.assertEqual(result["external_orders"],0)
