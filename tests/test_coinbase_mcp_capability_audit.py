"""Synthetic, offline regression for MCP tool-inventory classifications."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import coinbase_mcp_capability_audit as m


class InventoryTests(unittest.TestCase):
    def fixture(self, tools):
        return {"mode": m.MODE, "source": "coinbase_mcp", "tool_names": tools}

    def test_connector_tool_inventory_is_fully_classified(self):
        # Actual exposed tool NAMES checked 2026-10-24, not scopes or successful calls.
        surfaced = {
            "coinbase_balance", "coinbase_convert_execute",
            "coinbase_convert_get", "coinbase_convert_quote",
            "coinbase_feedback_submit", "coinbase_fees",
            "coinbase_orders_cancel", "coinbase_orders_close_position",
            "coinbase_orders_create", "coinbase_orders_edit",
            "coinbase_orders_edit_preview", "coinbase_orders_fills",
            "coinbase_orders_get", "coinbase_orders_list",
            "coinbase_orders_preview", "coinbase_portfolios_create",
            "coinbase_portfolios_delete", "coinbase_portfolios_edit",
            "coinbase_portfolios_get", "coinbase_portfolios_list",
            "coinbase_products_best_bid_ask", "coinbase_products_book",
            "coinbase_products_candles", "coinbase_products_get",
            "coinbase_products_list", "coinbase_products_ticker",
            "coinbase_transfer", "coinbase_x402_fetch",
            "coinbase_x402_pay", "coinbase_x402_resources",
        }
        r = m.audit(self.fixture(["mcp__Coinbase__" + s for s in sorted(surfaced)]))
        self.assertTrue(r["research_inventory_classified"])
        self.assertEqual(r["unclassified_not_permitted"], [])
        self.assertEqual(set(r["read_only_available"]), surfaced & m.READ_ONLY)
        self.assertEqual(set(r["paid_available_but_not_permitted"]), surfaced & m.PAID)
        self.assertEqual(set(r["state_changing_available_but_not_permitted"]),
                         surfaced & m.STATE_CHANGING)
        self.assertFalse(r["account_permissions_verified"])
        self.assertFalse(r["portfolio_scope_verified"])
        self.assertFalse(r["live_execution_authorized"])
        self.assertEqual(r["financial_operations"], 0)

    def test_payment_and_portfolio_transfer_are_never_read_only(self):
        r = m.audit(self.fixture(["coinbase_x402_resources", "coinbase_x402_fetch",
                                  "coinbase_x402_pay", "coinbase_transfer"]))
        self.assertEqual(r["read_only_available"], ["coinbase_x402_resources"])
        self.assertEqual(r["paid_available_but_not_permitted"],
                         ["coinbase_x402_fetch", "coinbase_x402_pay"])
        self.assertEqual(r["state_changing_available_but_not_permitted"],
                         ["coinbase_transfer"])
        self.assertEqual(r["x402_payments"], 0)

    def test_unknown_tools_are_not_permitted_by_prefix(self):
        r = m.audit(self.fixture(["coinbase_balance", "coinbase_wallet_sweep",
                                  "coinbase_orders_execute_something_new"]))
        self.assertFalse(r["research_inventory_classified"])
        self.assertEqual(r["read_only_available"], ["coinbase_balance"])
        self.assertEqual(len(r["unclassified_not_permitted"]), 2)

    def test_duplicate_short_and_namespaced_names_rejected(self):
        with self.assertRaises(m.InventoryError):
            m.audit(self.fixture(["coinbase_balance", "mcp__Coinbase__coinbase_balance"]))

    def test_strict_schema_blocks_untrusted_payloads(self):
        for bad in (
            {"mode": m.MODE, "source": "coinbase_mcp",
             "tool_names": ["coinbase_balance"], "api_key": "private"},
            {"mode": m.MODE, "source": "wallet_mcp", "tool_names": []},
            self.fixture(["coinbase_balance;rm"]),
            self.fixture([None]),
            self.fixture(["coinbase_balance"] * 81),
            self.fixture("coinbase_balance"),
        ):
            with self.subTest(bad=str(type(bad))):
                with self.assertRaises(m.InventoryError):
                    m.audit(bad)

    def test_cli_synthetic_manifest_and_generic_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text(json.dumps(self.fixture(["coinbase_products_candles",
                                                  "coinbase_orders_create"])))
            cmd = [sys.executable, "-m", "scripts.coinbase_mcp_capability_audit",
                   "--file", str(p)]
            good = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(good.returncode, 0)
            body = json.loads(good.stdout)
            self.assertEqual(body["read_only_available"], ["coinbase_products_candles"])
            self.assertEqual(body["state_changing_available_but_not_permitted"],
                             ["coinbase_orders_create"])
            self.assertFalse(body["remote_tools_invoked"])
            p.write_text(json.dumps({"secret": "THIS_MUST_NOT_LEAK"}))
            bad = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(bad.stdout.strip(), "INVENTORY_REJECTED")
            self.assertNotIn("THIS_MUST_NOT_LEAK", bad.stdout + bad.stderr)


if __name__ == "__main__":
    unittest.main()
