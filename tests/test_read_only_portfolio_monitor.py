"""Synthetic, secret-free verification for read-only market and portfolio briefing."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from scripts.read_only_portfolio_monitor import (
    HOURS, MonitoringError, _market_parse, analyze_portfolio,
    build_report, fetch_usdpln, render_markdown,
)

AT = datetime(2026,10,21,2,15,tzinfo=timezone.utc)
END = int(AT.timestamp()) // 3600 * 3600
FIRST = END - HOURS * 3600


def candles(*, missing=False, duplicated=False, malformed=False):
    arr=[]
    for j,t in enumerate(range(FIRST, END, 3600)):
        close = 100.0 + j/10
        arr.append({"start":str(t),"open":str(close-.1),
                    "close":str(close), "high":str(close+.5),
                    "low":str(close-.8), "volume":"2.5"})
    if missing:
        arr.pop(8)
    if duplicated:
        arr.append(dict(arr[4]))
    if malformed:
        arr[5]["high"]="1"
    # Real Coinbase source may expose a single unfinished END boundary.
    arr.append({"start":str(END),"open":"110","close":"111",
                "high":"112","low":"109","volume":"3"})
    import json
    return json.dumps({"candles":arr}).encode()


def market():
    return {p:_market_parse(candles(),p,FIRST,END)
            for p in ("BTC-USD","ETH-USD","ATOM-USD")}


def snapshot():
    return {
        "source":"SYNTHETIC_TEST_ONLY",
        "captured_at":"2026-10-21T02:10:00Z",
        "portfolio_balances":{"total_balance":{"currency":"USD","value":"100"}},
        "spot_positions":[
            {"asset":"ETH","account_type":"ACCOUNT_TYPE_STAKED_FUNDS",
             "total_balance_fiat":80,"total_balance_crypto":0.04},
            {"asset":"ATOM","account_type":"ACCOUNT_TYPE_STAKED_FUNDS",
             "total_balance_fiat":19.50,"total_balance_crypto":10},
            {"asset":"EURC","account_type":"ACCOUNT_TYPE_WALLET",
             "is_cash":True,"total_balance_fiat":0.50,"total_balance_crypto":0.5},
            {"asset":"EUR","account_type":"ACCOUNT_TYPE_FIAT","is_cash":True},
        ]}


def fx():
    return {"usdpln_mid_reference":"3.70","nbp_effective_date":"2026-10-20",
            "assumed_eligible_utc":"2026-10-21T00:00:00+00:00",
            "publication_time_is_exact":False,
            "nbp_source_canonical_sha256":"synthetic-not-an-actual-hash"}


class MonitoringOfflineTests(TestCase):
    def test_complete_three_asset_market_72_hour_range(self):
        data=market()
        self.assertEqual(len(data),3)
        self.assertEqual({v["verified_hourly_candles"] for v in data.values()},{72})
        self.assertEqual(data["ATOM-USD"]["price_type"],
                         "PUBLIC_HOURLY_CLOSE_NOT_EXECUTABLE_BID_ASK")
        self.assertNotEqual(data["BTC-USD"]["raw_source_sha256"],"")

    def test_incomplete_duplicated_and_inconsistent_prices_rejected(self):
        for name,kwargs in (
            ("missing",{"missing":True}),
            ("duplicate",{"duplicated":True}),
            ("broken_OHLC",{"malformed":True}),
        ):
            with self.subTest(name=name):
                with self.assertRaises(MonitoringError):
                    _market_parse(candles(**kwargs),"ATOM-USD",FIRST,END)

    def test_unapproved_market_identity_rejected(self):
        with self.assertRaises(MonitoringError):
            _market_parse(candles(),"FAKE-USD",FIRST,END)

    def test_private_staking_not_assumed_liquid(self):
        p=analyze_portfolio(snapshot(),AT)
        self.assertEqual(p["reported_total_usd"],"100.0000")
        self.assertEqual(p["staked_value_usd"],"99.5000")
        self.assertEqual(p["staked_share_pct"],"99.50")
        self.assertEqual(p["largest_asset"],"ETH")
        self.assertEqual(p["largest_asset_share_pct"],"80.00")
        self.assertTrue(p["no_tradability_inferred_from_total_balance"])
        self.assertIn("HIGH_SINGLE_ASSET_CONCENTRATION",p["risk_flags"])

    def test_all_snapshots_are_just_user_asserted_not_authenticated_by_cli(self):
        p=analyze_portfolio(snapshot(),AT)
        self.assertFalse(p["connected_account_validated_by_cli"])
        self.assertFalse(p["liquidity_not_verified_for"])

    def test_no_unvalued_asset_omission(self):
        p=snapshot()
        p["spot_positions"].append({"asset":"BTC","account_type":"ACCOUNT_TYPE_WALLET"})
        with self.assertRaisesRegex(MonitoringError,"no USD valuation"):
            analyze_portfolio(p,AT)

    def test_reconciliation_failure_is_not_hidden(self):
        p=snapshot()
        p["spot_positions"][0]["total_balance_fiat"]=70
        with self.assertRaisesRegex(MonitoringError,"do not reconcile"):
            analyze_portfolio(p,AT)

    def test_unsafe_account_snapshot_time_rejected(self):
        p=snapshot()
        p["captured_at"]="2026-11-30T00:00:00Z"
        with self.assertRaises(MonitoringError):
            analyze_portfolio(p,AT)
        p=snapshot()
        p["captured_at"]="2026-07-20T00:00:00Z"
        with self.assertRaises(MonitoringError):
            analyze_portfolio(p,AT)

    def test_report_without_private_holdings_never_pretends_zero_balance(self):
        r=build_report(AT,market(),fx())
        self.assertIsNone(r["portfolio"])
        self.assertEqual(r["portfolio_data"],"NOT_CONNECTED_TO_CLI")
        self.assertIn("Brak prywatnego snapshotu",render_markdown(r))
        self.assertEqual(r["executed_orders"],0)
        self.assertEqual(r["neon_writes"],0)
        self.assertFalse(r["profitability_proven"])

    def test_private_portfolio_report_mentions_staking(self):
        r=build_report(AT,market(),fx(),snapshot())
        text=render_markdown(r)
        self.assertIn("staking",text)
        self.assertIn("99.50%",text)
        self.assertIn("ATOM-USD",text)
        self.assertNotIn("buy ETH",text.lower())
        self.assertEqual(r["scheduled_runs_created"],0)

    def test_old_market_data_rejected(self):
        p=market()
        for m in p.values():
            m["last_completed_candle_end_utc"]="2026-10-18T00:00:00Z"
        with self.assertRaisesRegex(MonitoringError,"too old"):
            build_report(AT,p,fx())

    def test_nbp_eligibility_is_not_inferred_from_same_day(self):
        recent=datetime(2026,10,21,tzinfo=timezone.utc)
        rates={
            datetime(2026,10,20,tzinfo=timezone.utc).date():{
                "mid":"3.75","effective_date":"2026-10-20",
                "assumed_eligible_utc":"2026-10-21T00:00:00+00:00"},
            datetime(2026,10,21,tzinfo=timezone.utc).date():{
                "mid":"3.90","effective_date":"2026-10-21",
                "assumed_eligible_utc":"2026-10-22T00:00:00+00:00"},
        }
        def fake_fetch(start,end):
            return rates, {"canonical_sha256":"fake-only"}
        answer=fetch_usdpln(recent+timedelta(hours=2),fetcher=fake_fetch)
        self.assertEqual(answer["usdpln_mid_reference"],"3.75")
        self.assertFalse(answer["publication_time_is_exact"])
