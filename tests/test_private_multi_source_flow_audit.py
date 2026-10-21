"""Synthetic-only accounting regression; no live accounts, wallets or transfers."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest import TestCase

from scripts.private_multi_source_flow_audit import (
    FlowAuditError, audit_flows, render_markdown,
)

AT=datetime(2026,10,21,8,tzinfo=timezone.utc)

def journal():
    return {
        "mode":"PRIVATE_READ_ONLY_FLOW_AUDIT",
        "currency":"USD",
        "snapshots":[
            {"captured_at":"2026-10-01T12:00:00Z",
             "exchange_observed_at":"2026-10-01T11:55:00Z",
             "wallet_observed_at":"2026-10-01T11:55:00Z",
             "exchange_priced_usd":"100.00","wallet_priced_usd":"75.00",
             "wallet_unpriced_count":1,
             "wallet_coverage":"BASE_ETHEREUM_WALLET_PRICED_SUBSET",
             "valuation_source":"SYNTHETIC_OFFLINE_FIXTURE"},
            {"captured_at":"2026-10-20T12:00:00Z",
             "exchange_observed_at":"2026-10-20T11:58:00Z",
             "wallet_observed_at":"2026-10-20T11:58:00Z",
             "exchange_priced_usd":"109.50","wallet_priced_usd":"115.00",
             "wallet_unpriced_count":1,
             "wallet_coverage":"BASE_ETHEREUM_WALLET_PRICED_SUBSET",
             "valuation_source":"SYNTHETIC_OFFLINE_FIXTURE"},
        ],
        "events":[
            {"id":"outside_funding_1","reference":"test-fund-0001",
             "at":"2026-10-10T00:00:00Z","type":"external_inflow",
             "from":"external","to":"exchange",
             "amount_usd":"50.00","fee_usd":"0",
             "confirmed_source":True,"confirmed_destination":True},
            {"id":"internal_shift_1","reference":"test-move-0002",
             "at":"2026-10-15T00:00:00Z","type":"internal_movement",
             "from":"exchange","to":"wallet",
             "amount_usd":"40.00","fee_usd":"0.50",
             "confirmed_source":True,"confirmed_destination":True}
        ]
    }

class PrivateFlowAuditTests(TestCase):
    def test_internal_movement_does_not_create_external_contribution(self):
        out=audit_flows(journal(),AT)
        self.assertEqual(out["first_identified_subtotal_usd"],"175.00")
        self.assertEqual(out["last_identified_subtotal_usd"],"224.50")
        self.assertEqual(out["recorded_external_inflow_usd"],"50.00")
        self.assertEqual(out["confirmed_internal_movement_usd"],"40.00")
        self.assertEqual(out["recorded_event_fees_usd"],"0.50")
        self.assertEqual(out["unexplained_reference_change_after_recorded_flows_usd"],"0.00")
        self.assertFalse(out["market_profitability_or_return_certified"])
        self.assertFalse(out["current_holdings_complete"])
        self.assertEqual(out["external_operations"],0)

    def test_external_inflow_is_not_falsely_counted_as_profit(self):
        v=journal()
        v["events"]=v["events"][:1]
        v["snapshots"][1]["exchange_priced_usd"]="150"
        v["snapshots"][1]["wallet_priced_usd"]="75"
        result=audit_flows(v,AT)
        self.assertEqual(result["last_identified_subtotal_usd"],"225.00")
        self.assertEqual(result["net_recorded_external_funding_usd"],"50.00")
        self.assertEqual(result["unexplained_reference_change_after_recorded_flows_usd"],"0.00")

    def test_external_outflow_direction_and_amount(self):
        v=journal()
        v["events"]=[{
            "id":"external_exit","reference":"test-out-0003",
            "at":"2026-10-18T00:00:00Z","type":"external_outflow",
            "from":"wallet","to":"external","amount_usd":"10","fee_usd":"0",
            "confirmed_source":True,"confirmed_destination":True}]
        v["snapshots"][1]["exchange_priced_usd"]="100"
        v["snapshots"][1]["wallet_priced_usd"]="65"
        result=audit_flows(v,AT)
        self.assertEqual(result["net_recorded_external_funding_usd"],"-10.00")
        self.assertEqual(result["unexplained_reference_change_after_recorded_flows_usd"],"0.00")

    def test_unconfirmed_movement_does_not_imply_profitability(self):
        v=journal()
        v["events"][1]["confirmed_destination"]=False
        result=audit_flows(v,AT)
        self.assertEqual(result["pending_event_count"],1)
        self.assertIsNone(result["unexplained_reference_change_after_recorded_flows_usd"])
        self.assertIn("PENDING_MOVEMENTS_NOT_COUNTED_YET",result["warnings"])

    def test_duplicate_event_identifier_and_reference_rejected(self):
        for key in ("id","reference"):
            v=journal()
            dup=deepcopy(v["events"][0])
            dup["id"]="unique_2"
            dup["reference"]="unique-new-reference"
            dup[key]=v["events"][0][key]
            v["events"].append(dup)
            with self.subTest(key=key):
                with self.assertRaisesRegex(FlowAuditError,"Duplicate"):
                    audit_flows(v,AT)

    def test_direction_mismatch_rejected(self):
        v=journal()
        v["events"][1]["from"]="external"
        with self.assertRaisesRegex(FlowAuditError,"Internal movement"):
            audit_flows(v,AT)
        v=journal()
        v["events"][0]["to"]="external"
        with self.assertRaisesRegex(FlowAuditError,"inflow direction"):
            audit_flows(v,AT)

    def test_mismatched_wallet_coverage_is_fail_closed(self):
        v=journal()
        v["snapshots"][1]["wallet_coverage"]="OTHER_EXPLICITLY_NAMED_SCOPES"
        with self.assertRaisesRegex(FlowAuditError,"different wallet"):
            audit_flows(v,AT)

    def test_wallet_and_cex_capture_disparity_fails(self):
        v=journal()
        v["snapshots"][1]["wallet_observed_at"]="2026-10-18T00:00:00Z"
        with self.assertRaisesRegex(FlowAuditError,"far apart"):
            audit_flows(v,AT)

    def test_negative_nan_fee_and_amount_rejected(self):
        for key,value in (("amount_usd","NaN"),("fee_usd","-1"),
                          ("amount_usd","0"),("fee_usd","500")):
            v=journal()
            v["events"][1][key]=value
            with self.subTest(key=key,value=value):
                with self.assertRaises(FlowAuditError):
                    audit_flows(v,AT)

    def test_private_secrets_and_unknown_fields_rejected(self):
        v=journal()
        v["seed_phrase"]="SYNTHETIC NEVER REAL"
        with self.assertRaises(FlowAuditError):
            audit_flows(v,AT)
        v=journal()
        v["events"][1]["recipient_wallet_address"]="0x"+"a"*40
        with self.assertRaises(FlowAuditError):
            audit_flows(v,AT)

    def test_future_snapshot_and_wrong_currency_rejected(self):
        v=journal()
        v["snapshots"][1]["captured_at"]="2026-11-10T12:00:00Z"
        with self.assertRaises(FlowAuditError):
            audit_flows(v,AT)
        v=journal()
        v["currency"]="PLN"
        with self.assertRaises(FlowAuditError):
            audit_flows(v,AT)

    def test_snapshot_older_than_24h_warned_no_accuracy_promised(self):
        v=journal()
        out=audit_flows(v,datetime(2026,10,23,tzinfo=timezone.utc))
        self.assertIn("LAST_BALANCE_SNAPSHOT_OLDER_THAN_24H",out["warnings"])
        self.assertFalse(out["current_holdings_complete"])

    def test_user_supplied_source_not_authenticated(self):
        v=journal()
        for snap in v["snapshots"]:
            snap["valuation_source"]="PRIVATE_USER_SUPPLIED_REFERENCE"
        out=audit_flows(v,AT)
        self.assertIn("USER_SUPPLIED_SNAPSHOTS_NOT_SOURCE_AUTHENTICATED",
                      out["warnings"])
        self.assertFalse(out["all_transfers_independently_verified"])

    def test_markdown_explicitly_not_investment_profit(self):
        doc=render_markdown(audit_flows(journal(),AT))
        self.assertIn("NIE jest to zweryfikowany zysk",doc)
        self.assertIn("Coinbase Exchange",doc)
        self.assertIn("Wallet, wyceniony podzbiór",doc)
        self.assertNotIn("test-move-0002",doc)

    def test_no_side_effect_fields_present(self):
        r=audit_flows(journal(),AT)
        self.assertEqual(r["orders"],0)
        self.assertEqual(r["external_operations"],0)
        self.assertEqual(r["database_writes"],0)

    def test_combined_public_market_can_include_private_flow_audit(self):
        from scripts.read_only_portfolio_monitor import build_report, render_markdown
        data={k:{"symbol":k,"verified_hourly_candles":72,
                 "last_completed_candle_end_utc":"2026-10-21T08:00:00+00:00",
                 "last_closed_price_usd":"100","price_change_24h_pct":"0",
                 "observed_realized_volatility_24h_pct":"1"}
              for k in ("BTC-USD","ETH-USD","ATOM-USD")}
        fx={"usdpln_mid_reference":"3.80","nbp_effective_date":"2026-10-20"}
        flows=audit_flows(journal(),AT)
        report=build_report(AT,data,fx,flow_audit=flows)
        self.assertEqual(report["read_only_flow_audit"]["confirmed_internal_movement_usd"],"40.00")
        self.assertEqual(report["executed_orders"],0)
        self.assertIn("Przepływy kapitału",render_markdown(report))
        self.assertIn("transferu",render_markdown(report))
