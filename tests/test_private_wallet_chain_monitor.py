"""Only manufactured balances and fake HTTP. No real wallet identifiers are stored."""
from datetime import datetime, timezone
from unittest import TestCase
import json

from scripts.private_wallet_chain_monitor import (
    WalletSourceError, _private_config, _parse_chain,
    inspect_wallet_watchlist, reconcile_custodial_and_wallet, _fetch_json
)
from scripts.read_only_portfolio_monitor import build_report, render_markdown

FAKE_A = "0x" + "1" * 40
FAKE_TOKEN = "0x" + "a" * 40
OTHER_TOKEN = "0x" + "b" * 40
NOW = datetime(2026,10,21,7,tzinfo=timezone.utc)


def watch():
    return {"mode":"PRIVATE_WALLET_READ_ONLY",
            "watch":[{"label":"primary","chain_id":8453,"address":FAKE_A,
                      "verified_token_contracts":[FAKE_TOKEN]},
                     {"label":"legacy","chain_id":1,"address":FAKE_A,
                      "verified_token_contracts":[]}]}


def blockscout_records(chain, addr, path):
    assert addr == FAKE_A.lower()
    assert chain in (1, 8453)
    if path == "":
        if chain == 8453:
            return {"coin_balance":"100000000000000000",
                    "exchange_rate":"2000"}, "f" * 64
        return {"coin_balance":"0","exchange_rate":"2000"}, "a" * 64
    if chain == 8453:
        return [
            {"value":"100000","token":{"type":"ERC-20","address_hash":FAKE_TOKEN,
                                        "symbol":"cbBTC","decimals":"8","exchange_rate":"100000"}},
            {"value":"1200000000000","token":{"type":"ERC-20","address_hash":OTHER_TOKEN,
                                                "symbol":"cbBTC","decimals":"18","exchange_rate":"999999"}},
            {"value":"1","token":{"type":"ERC-721","address_hash":"0x"+"c"*40,
                                  "symbol":"NFT","decimals": "0"}},
        ], "b" * 64
    return [], "c" * 64


def private_cex():
    return {"status":"PRIVATE_READ_ONLY_SNAPSHOT_RISK_REVIEW",
            "reported_total_usd":"100.0000",
            "staked_value_usd":"80","largest_asset":"ETH",
            "largest_asset_share_pct":"80.00"}


def minimal_market():
    return {s:{"symbol":s,"verified_hourly_candles":72,
               "last_completed_candle_end_utc":"2026-10-21T07:00:00+00:00",
               "last_closed_price_usd":"100","price_change_24h_pct":"1.20",
               "observed_realized_volatility_24h_pct":"3.20"}
            for s in ("BTC-USD","ETH-USD","ATOM-USD")}


class WalletEvidenceTests(TestCase):
    def test_distinct_chains_same_address_are_not_same_position(self):
        out=inspect_wallet_watchlist(watch(),NOW,fetcher=blockscout_records)
        self.assertEqual(out["wallet_account_chain_count"],2)
        self.assertEqual(out["priced_subtotal_usd"],"300.000")
        self.assertEqual(out["unpriced_or_unreviewed_position_count"],1)
        self.assertFalse(out["complete_all_assets_valuation"])
        self.assertEqual(out["financial_operations"],0)
        primary=out["wallets"][0]["positions"]
        self.assertEqual(primary[0]["asset"],"ETH")
        self.assertEqual(primary[1]["asset"],"cbBTC")
        self.assertEqual(primary[2]["asset"],"UNREVIEWED_ERC20")
        self.assertIsNone(primary[2]["usd_estimate"])
        self.assertNotIn(FAKE_A.lower(),json.dumps(out).lower())
        self.assertNotIn(OTHER_TOKEN.lower(),json.dumps(out).lower())

    def test_aggregation_is_separate_from_custodian_and_not_full_net_worth(self):
        wallet=inspect_wallet_watchlist(watch(),NOW,fetcher=blockscout_records)
        all_=reconcile_custodial_and_wallet(private_cex(),wallet)
        self.assertEqual(all_["known_priced_amount_usd"],"400.0000")
        self.assertFalse(all_["total_portfolio_net_worth_certified"])
        self.assertFalse(all_["all_assets_completely_valued"])
        self.assertEqual(all_["transfers_or_trades"],0)

    def test_without_exchange_value_must_not_claim_full_portfolio(self):
        wallet=inspect_wallet_watchlist(watch(),NOW,fetcher=blockscout_records)
        all_=reconcile_custodial_and_wallet(None,wallet)
        self.assertEqual(all_["known_priced_amount_usd"],"300.000")
        self.assertFalse(all_["all_sources_present"])
        self.assertIn("COINBASE_EXCHANGE_SNAPSHOT_MISSING",all_["warnings"])

    def test_duplicate_wallet_alias_same_network_fails(self):
        w=watch()
        w["watch"].append({"label":"duplicate","chain_id":8453,
                           "address":FAKE_A,"verified_token_contracts":[]})
        with self.assertRaisesRegex(WalletSourceError,"twice"):
            _private_config(w)

    def test_same_contract_duplicate_token_rows_fails(self):
        obj=blockscout_records(8453,FAKE_A,"/token-balances")[0]
        obj.append(dict(obj[0]))
        with self.assertRaisesRegex(WalletSourceError,"Duplicate contract"):
            _parse_chain({"coin_balance":"0","exchange_rate":"2000"},obj,{FAKE_TOKEN})

    def test_secrets_and_bad_chains_are_never_accepted(self):
        data=watch()
        data["private_key"]="0x"+"e"*64
        with self.assertRaises(WalletSourceError):
            _private_config(data)
        data=watch()
        data["watch"][0]["chain_id"]=56
        with self.assertRaises(WalletSourceError):
            _private_config(data)
        data=watch()
        data["watch"][0]["address"]="this-is-not-an-address"
        with self.assertRaises(WalletSourceError):
            _private_config(data)

    def test_no_unverified_spoofed_price_in_total(self):
        raw=blockscout_records(8453,FAKE_A,"/token-balances")[0]
        vals,total,unknown=_parse_chain(
            {"coin_balance":"0","exchange_rate":"2000"},raw,{FAKE_TOKEN.lower()})
        self.assertEqual(total,100)
        self.assertEqual(unknown,1)
        self.assertTrue(any(v["asset"]=="UNREVIEWED_ERC20" for v in vals))

    def test_missing_erc20_exchange_rate_is_unpriced(self):
        rows=blockscout_records(8453,FAKE_A,"/token-balances")[0]
        rows[0]["token"]["exchange_rate"]=None
        positions,value,unknown=_parse_chain(
            {"coin_balance":"0","exchange_rate":None},rows,{FAKE_TOKEN.lower()})
        self.assertEqual(value,0)
        self.assertEqual(unknown,2)
        self.assertEqual(positions[0]["valuation_status"],"UNPRICED")

    def test_reject_redirect_and_sanitize_http_error_url(self):
        from urllib.error import HTTPError
        class Failing:
            def __call__(self,req,timeout):
                raise HTTPError(req.full_url,429,"Too Many Requests",{},None)
        try:
            _fetch_json(8453,FAKE_A,"",opener=Failing())
        except WalletSourceError as exc:
            self.assertNotIn(FAKE_A.lower(),str(exc).lower())
            self.assertIsNone(exc.__cause__)
        else:
            self.fail("Expected safe source error")

    def test_market_report_integrates_wallet_separately(self):
        wallet=inspect_wallet_watchlist(watch(),NOW,fetcher=blockscout_records)
        fx={"usdpln_mid_reference":"3.70","nbp_effective_date":"2026-10-20"}
        report=build_report(NOW,minimal_market(),fx,wallet_report=wallet)
        self.assertIsNone(report["portfolio"])
        self.assertEqual(report["onchain_wallets"]["priced_subtotal_usd"],"300.000")
        self.assertEqual(report["combined_known_holdings"]["known_priced_amount_usd"],"300.000")
        self.assertIn("CEX + wallet",render_markdown(report))
        self.assertNotIn(FAKE_A.lower(),json.dumps(report).lower())
        self.assertEqual(report["executed_orders"],0)
        self.assertEqual(report["scheduled_runs_created"],0)
