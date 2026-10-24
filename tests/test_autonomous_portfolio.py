"""Offline contracts, fault isolation and private-state tests; no real HTTP/key."""
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import autonomous_portfolio as m
from scripts.operational_read_only import read_private, write_private, ReadOnlyError
from tests.test_autonomous_coinbase_history import PORTFOLIO, Response, Provider
from tests.test_coinbase_deposit_history import ACCOUNT, NOW, transaction, page
from tests.test_operational_read_only import fake_rpc, watch

ADDRESS = "0x" + "1"*40


def balances(network="base"):
    return {"balances": [{"amount": {"amount": "1230000000000000000", "decimals": 18},
        "token": {"network": network, "symbol": "PRIVATE_UNTRUSTED_NAME", "name": "[PRIVATE]",
                  "contractAddress": m.NATIVE}}]}


def fx_fixture(now=NOW):
    return {"usdpln_mid_reference": "4.1234", "nbp_effective_date": now.date().isoformat(),
            "assumed_eligible_utc": now.isoformat(), "market_fx_tradable_quote": False}


class CdpTests(unittest.TestCase):
    def test_read_only_path_units_identity_and_redaction(self):
        calls, signed = [], []
        def open_(req, timeout):
            calls.append(req)
            return Response(req.full_url, balances())
        c = m.CdpBalances(lambda path: signed.append(path) or "synthetic", open_)
        r = c.collect(8453, ADDRESS)
        self.assertEqual(r["positions"][0]["quantity"], "1.23")
        self.assertEqual(r["positions"][0]["asset"], "ETH")
        self.assertEqual(calls[0].get_method(), "GET")
        self.assertIsNone(calls[0].data)
        self.assertEqual(len(signed), 1)
        self.assertNotIn("?", signed[0])
        self.assertNotIn(ADDRESS, json.dumps(r))
        self.assertNotIn("PRIVATE", json.dumps(r))

    def test_reject_unsupported_network_and_address_before_request(self):
        c = m.CdpBalances(lambda path: self.fail("must not sign"))
        for chain, address in ((True, ADDRESS), (137, ADDRESS), (8453, ADDRESS+"/orders"),
                               (8453, "https://example.invalid")):
            with self.assertRaises(ValueError): c.collect(chain, address)

    def test_schema_wrong_network_bad_precision_duplicates_and_error(self):
        cases = []
        b = balances(); b["balances"][0]["token"]["network"] = "ethereum"; cases.append(b)
        b = balances(); b["balances"][0]["amount"]["decimals"] = 6; cases.append(b)
        b = balances(); b["balances"][0]["amount"]["amount"] = "NaN"; cases.append(b)
        b = balances(); b["balances"] *= 2; cases.append(b)
        cases += [{"errorMessage": "[PRIVATE]"}, {"balances": None}]
        for body in cases:
            c = m.CdpBalances(lambda p: "token", lambda req, timeout: Response(req.full_url, body))
            with self.assertRaisesRegex(ValueError, "^CDP_BALANCE_READ_REJECTED$"):
                c.collect(8453, ADDRESS)

    def test_pagination_loop_not_silently_truncated(self):
        body = {"balances": [], "nextPageToken": "repeat"}
        c = m.CdpBalances(lambda p: "token", lambda req, timeout: Response(req.full_url, body))
        with self.assertRaises(ValueError): c.collect(8453, ADDRESS)

    def test_pagination_and_unknown_token_never_symbol_trusted(self):
        b = balances(); b["nextPageToken"] = "cursor/with?query"
        other = balances(); other["balances"][0]["token"]["contractAddress"] = "0x"+"2"*40
        calls = []
        def open_(req, timeout):
            calls.append(req.full_url)
            return Response(req.full_url, b if len(calls) == 1 else other)
        result = m.CdpBalances(lambda p: "token", open_).collect(8453, ADDRESS)
        self.assertEqual(len(result["positions"]), 2)
        self.assertIn("pageToken=cursor%2Fwith%3Fquery", calls[-1])
        self.assertFalse(result["positions"][1]["identity_verified"])
        self.assertEqual(result["positions"][1]["asset"], "UNREVIEWED_TOKEN")

    def test_redirect_rejected_and_token_not_printed(self):
        c = m.CdpBalances(lambda p: "token", lambda req, timeout:
                          Response("https://example.invalid", balances()))
        with self.assertRaises(ValueError): c.collect(8453, ADDRESS)
        c = m.CdpBalances(lambda p: "bad\nheader")
        with self.assertRaises(ValueError): c.collect(8453, ADDRESS)


class AccountsTests(unittest.TestCase):
    def test_accounts_minimize_private_fields_and_validate_balance(self):
        class Source:
            path = "/v2/accounts"
            def check_permissions(self): pass
            def get(self, path, cursor):
                return {"data": [{"id": ACCOUNT, "currency": {"code": "ETH"},
                    "name": "[PRIVATE]", "balance": {"currency": "ETH", "amount": "0.1"}}],
                    "pagination": {"next_uri": None}}
        self.assertEqual(m.exchange_accounts(Source()), [{"id": ACCOUNT, "asset": "ETH", "quantity": "0.1"}])
        src = Source()
        original = src.get
        def wrong(path, cursor):
            b = original(path, cursor); b["data"][0]["balance"]["currency"] = "BTC"; return b
        src.get = wrong
        with self.assertRaises(ValueError): m.exchange_accounts(src)

    def test_number_bounds(self):
        for value in (True, None, "NaN", "Infinity", "1e9", "-1", "9"*81):
            with self.assertRaises(ValueError): m.quantity(value)


class RuntimeTests(unittest.TestCase):
    def test_advancing_clock_keeps_cycle_expiry_valid_for_watchdog(self):
        tick = 0
        def clock():
            nonlocal tick
            tick += 1
            return NOW + timedelta(microseconds=tick)
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            config = {"credentials_file": "unused", "portfolio_id": PORTFOLIO,
                      "watchlist_file": None}
            with patch.object(m, "exchange_accounts", return_value=[]):
                report = m.cycle(config, root, clock,
                    signer_factory=lambda p: None, client_factory=lambda *args: None,
                    market_reader=lambda now: {}, fx_reader=fx_fixture)
            checked = datetime.fromisoformat(report["checked_at_utc"])
            expires = datetime.fromisoformat(report["expires_at_utc"])
            self.assertEqual(expires - checked, timedelta(minutes=30))
            self.assertEqual(read_private(root/"health.json")["expires_at_utc"],
                             report["expires_at_utc"])
            notifications = []
            self.assertEqual(m.check_health(root, clock(), notifications.append), "PARTIAL")
            self.assertEqual(notifications, ["PARTIAL"])

    def test_source_failure_redacts_error_and_preserves_unknown(self):
        def failed(): raise RuntimeError("[PRIVATE_ACCOUNT_JWT]")
        r = m.source_read(failed, lambda: NOW)
        self.assertEqual(r["status"], "UNAVAILABLE")
        self.assertIsNone(r["data"])
        self.assertNotIn("PRIVATE", json.dumps(r))

    def test_atomic_setup_and_permissions_no_secret_or_wallet_key(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            write_private(root/"reader.json", {"credentials_file": str(root/"existing-key.json"),
                "portfolio_id": PORTFOLIO})
            config = m.setup_wallet(root/"reader.json", lambda: ADDRESS)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            watchlist = read_private(root/"wallet-watch.json")
            self.assertEqual({r["chain_id"] for r in watchlist["watch"]}, {1, 8453})
            with self.assertRaises(ValueError): m.setup_wallet(root/"reader.json", lambda: ADDRESS)

    def test_cycle_separates_indexer_balances_and_finalized_holdings(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            write_private(root/"watch.json", watch())
            config = {"credentials_file": "unused", "portfolio_id": PORTFOLIO,
                      "watchlist_file": str(root/"watch.json")}
            class Source:
                def __init__(self, account, portfolio, signer):
                    self.account = account
                    self.path = "/v2/accounts" if account is None else f"/v2/accounts/{account}/transactions"
                def check_permissions(self): pass
                def get(self, path, cursor=None):
                    if self.account is None:
                        return {"data": [{"id": ACCOUNT, "currency": "ETH", "balance": {
                            "currency": "ETH", "amount": "2"}}], "pagination": {"next_uri": None}}
                    return page([transaction()])["response"]
            log_failure = [False]
            def wallet(conf, now, **kwargs):
                def rpc(chain, method, params):
                    if log_failure[0] and method == "eth_getLogs":
                        raise ReadOnlyError("SYNTHETIC_HISTORY_UNAVAILABLE")
                    result = fake_rpc(chain, method, params)
                    if method == "eth_getBlockByNumber":
                        result["timestamp"] = hex(int(now.timestamp())-30)
                    return result
                return m.observe_wallets(conf, now, rpc=rpc, **kwargs)
            with patch.object(m.CdpBalances, "collect", return_value={"positions": [{"quantity": "99999"}]}):
                report = m.cycle(config, root, lambda: NOW, signer_factory=lambda p: None,
                    client_factory=Source, cdp_factory=lambda p: None, wallet_reader=wallet,
                    fx_reader=lambda now: fx_fixture(now),
                    market_reader=lambda now: {asset+"-USD": {"last_closed_price_usd": "1000",
                        "last_completed_candle_end_utc": now.replace(minute=0,second=0,microsecond=0).isoformat()} for asset in ("BTC","ETH")})
            eth = [r for r in report["holdings"] if r["asset"] == "ETH"]
            self.assertEqual({r["quantity"] for r in eth}, {"2", "0.1"})
            self.assertEqual(report["known_priced_subtotal_usd"], "2100.0")
            self.assertEqual(report["known_priced_subtotal_pln"], "8659.14")
            self.assertEqual(report["reference_currency"], "PLN")
            self.assertEqual(report["financial_operations"], 0)
            self.assertEqual(report["status"], "OBSERVATION_OK")
            self.assertEqual(report["history_coverage"]["gap_range_count"], 0)
            self.assertFalse(report["history_coverage"]["complete_chain_history_certified"])
            self.assertEqual(report["history_coverage"]["streams"]["chain_primary_8453"]
                             ["last_complete_to_block"], 100)
            self.assertEqual(report["paper_simulation"]["status"], "OK")
            self.assertEqual(report["known_priced_concentration_pct"], {"ETH": "100.00"})
            self.assertFalse(report["complete_net_worth_certified"])
            self.assertFalse(report["reconciliation"]["full_autonomous_reconciliation_ready"])
            self.assertEqual((root/"portfolio.json").stat().st_mode & 0o777, 0o600)
            self.assertNotIn(ADDRESS, m.render(report))
            log_failure[0] = True
            with patch.object(m.CdpBalances, "collect", return_value={"positions": []}):
                partial = m.cycle(config, root, lambda: NOW, signer_factory=lambda p: None,
                    client_factory=Source, cdp_factory=lambda p: None, wallet_reader=wallet,
                    fx_reader=lambda now: fx_fixture(now),
                    market_reader=lambda now: {asset+"-USD": {"last_closed_price_usd": "1000",
                        "last_completed_candle_end_utc": now.replace(minute=0,second=0,microsecond=0).isoformat()}
                        for asset in ("BTC", "ETH")})
            self.assertEqual(partial["status"], "PARTIAL")
            self.assertEqual(partial["holdings"], report["holdings"])
            self.assertIn("chain_primary_8453", partial["alerts"])
            self.assertTrue(partial["history_coverage"]["latest_source_incomplete"])
            self.assertEqual(partial["history_coverage"]["streams"]["chain_primary_8453"]
                             ["last_complete_to_block"], 100)
            health = read_private(root/"health.json")
            self.assertEqual(health["status"], "PARTIAL")
            notifications = []
            m.check_health(root, NOW, notifications.append)
            self.assertEqual(notifications, ["PARTIAL"])
            def unavailable_fx(now):
                raise RuntimeError("SYNTHETIC_NBP_UNAVAILABLE")
            with patch.object(m.CdpBalances, "collect", return_value={"positions": []}):
                no_fx = m.cycle(config, root, lambda: NOW, signer_factory=lambda p: None,
                    client_factory=Source, cdp_factory=lambda p: None, wallet_reader=wallet,
                    fx_reader=unavailable_fx,
                    market_reader=lambda now: {asset+"-USD": {"last_closed_price_usd": "1000",
                        "last_completed_candle_end_utc": now.replace(minute=0,second=0,microsecond=0).isoformat()}
                        for asset in ("BTC", "ETH")})
            self.assertEqual(no_fx["status"], "PARTIAL")
            self.assertIn("usdpln", no_fx["alerts"])
            self.assertIsNone(no_fx["known_priced_subtotal_pln"])
            self.assertTrue(all(row["reference_value_pln"] is None for row in no_fx["holdings"]))
            self.assertEqual(no_fx["paper_last_success"]["units"], report["paper_last_success"]["units"])

    def test_dashboard_escapes_external_content_and_has_expiry(self):
        report = {"checked_at_utc": NOW.isoformat(), "expires_at_utc": NOW.isoformat(),
            "status": "PARTIAL", "known_priced_subtotal_usd": "0",
            "sources": {"<script>": {"status": "UNAVAILABLE"}},
            "holdings": [{"asset": "<img src=x onerror=alert(1)>"}]}
        html = m.render(report)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertIn("ważne do", html)
        self.assertIn("default-src 'none'", html)

    def test_html_symlink_target_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"dashboard.html"
            path.symlink_to(Path(root)/"other")
            with self.assertRaises(ValueError): m.private_html(path, "private")
            self.assertFalse((Path(root)/"other").exists())

    def test_live_opt_in(self):
        self.assertEqual(m.main(["--config", "/missing"]), 2)


class PaperAndHealthTests(unittest.TestCase):
    def market(self, now=NOW):
        at = now.replace(minute=0, second=0, microsecond=0).isoformat()
        return {asset+"-USD": {"last_closed_price_usd": "1000", "last_completed_candle_end_utc": at}
                for asset in ("BTC", "ETH")}

    def test_paper_initial_cost_and_same_candle_idempotency(self):
        r = m.paper_snapshot(None, self.market(), NOW)
        self.assertLess(m.quantity(r["reference_value_usd"]), m.Decimal("10000"))
        self.assertEqual(m.paper_snapshot(r, self.market(), NOW), r)
        self.assertFalse(r["real_holdings_used"])
        self.assertFalse(r["profitability_proven"])

    def test_paper_next_candle_no_reentry_cost_or_units_change(self):
        r = m.paper_snapshot(None, self.market(), NOW)
        now = NOW + timedelta(hours=1)
        result = m.paper_snapshot(r, self.market(now), now)
        self.assertEqual(result["units"], r["units"])
        self.assertEqual(result["reference_value_usd"], r["reference_value_usd"])

    def test_paper_stale_future_missing_price_and_backward_rejected(self):
        r = m.paper_snapshot(None, self.market(), NOW)
        for market in ({}, self.market(NOW+timedelta(hours=1)), self.market(NOW-timedelta(hours=3))):
            with self.assertRaises((ValueError, KeyError)): m.paper_snapshot(r, market, NOW)

    def test_watchdog_quiet_healthy_and_unchanged_then_stale_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); notifications = []
            health = {"status": "OBSERVATION_OK", "financial_operations": 0, "alerts": [],
                "checked_at_utc": NOW.isoformat(), "expires_at_utc": (NOW+timedelta(minutes=30)).isoformat()}
            write_private(root/"health.json", health)
            self.assertEqual(m.check_health(root, NOW, notifications.append), "OBSERVATION_OK")
            self.assertEqual(notifications, [])
            m.check_health(root, NOW+timedelta(minutes=31), notifications.append)
            m.check_health(root, NOW+timedelta(minutes=32), notifications.append)
            self.assertEqual(notifications, ["STALE"])
            m.check_health(root, NOW, notifications.append)
            self.assertEqual(notifications, ["STALE", "OBSERVATION_OK"])

    def test_watchdog_failed_notification_retried_without_marker(self):
        with tempfile.TemporaryDirectory() as root:
            def failed(_): raise RuntimeError("local notifier unavailable")
            with self.assertRaises(RuntimeError): m.check_health(root, NOW, failed)
            self.assertFalse((Path(root)/"watchdog.json").exists())
            calls=[];m.check_health(root, NOW, calls.append)
            self.assertEqual(calls, ["INVALID_OR_MISSING"])

    def test_private_html_atomic_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"dashboard.html"
            m.private_html(p,"first");m.private_html(p,"second")
            self.assertEqual(p.read_text(),"second")
            self.assertEqual(p.stat().st_mode & 0o777,0o600)

    def test_provider_enum_with_digit_not_misclassified_as_deposit(self):
        from scripts.coinbase_deposit_history import normalize_receives, CAPTURE_MODE
        row=transaction();row["type"]="retail_eth2_deprecation"
        r=normalize_receives({"mode":CAPTURE_MODE,"account_id":ACCOUNT,
            "captured_at":NOW.isoformat(),"pages":[page([row])]},NOW)
        self.assertEqual(r["event_count"],0)
        self.assertEqual(r["excluded_other_event_count"],1)


class PlnTests(unittest.TestCase):
    def report(self):
        return {"known_priced_subtotal_usd": "12.345", "holdings": [
            {"reference_value_usd": "12.345"}, {"reference_value_usd": None}],
            "paper_simulation": {"data": {"reference_value_usd": "10000", "units": {"ETH": "1"}}}}

    def test_conversion_rounding_unknown_and_paper_basis_preserved(self):
        report = self.report()
        original_paper = report["paper_simulation"]["data"]
        result = m.pln_values(report, fx_fixture())
        self.assertEqual(result["known_priced_subtotal_pln"], "50.90")
        self.assertIsNone(result["holdings"][1]["reference_value_pln"])
        self.assertEqual(result["paper_simulation"]["data"]["reference_value_pln"], "41234.00")
        self.assertEqual(original_paper, {"reference_value_usd": "10000", "units": {"ETH": "1"}})
        self.assertEqual(result["paper_simulation"]["data"]["reference_value_usd"], "10000")

    def test_missing_fx_is_unknown_not_zero_or_usd_relabelled(self):
        report = m.pln_values(self.report(), None)
        self.assertIsNone(report["known_priced_subtotal_pln"])
        self.assertTrue(all(r["reference_value_pln"] is None for r in report["holdings"]))
        self.assertIsNone(report["paper_simulation"]["data"]["reference_value_pln"])

    def test_reference_fx_rejects_zero_stale_future_and_nan(self):
        for field, value in (("usdpln_mid_reference", "0"), ("usdpln_mid_reference", "NaN"),
                ("assumed_eligible_utc", (NOW-timedelta(days=6)).isoformat()),
                ("assumed_eligible_utc", (NOW+timedelta(days=1)).isoformat()),
                ("nbp_effective_date", (NOW+timedelta(days=1)).date().isoformat())):
            fx = fx_fixture(); fx[field] = value
            with self.assertRaises(ValueError): m.reference_fx(NOW, lambda now: fx)

    def test_panel_labels_pln_and_nbp_date(self):
        report = {"checked_at_utc": NOW.isoformat(), "expires_at_utc": NOW.isoformat(),
            "status": "PARTIAL", "sources": {}, **self.report()}
        html = m.render(m.pln_values(report, fx_fixture()))
        self.assertIn("Wartość referencyjna PLN", html)
        self.assertIn("Wycena częściowa PLN: 50.90", html)
        self.assertIn("data tabeli: " + NOW.date().isoformat(), html)
        self.assertIn("Pokrycie historii ERC20", html)
        self.assertNotIn("Wartość referencyjna USD", html)


if __name__ == "__main__":
    unittest.main()
