"""Offline Coinbase MCP tool-surface inventory. No MCP, API, wallet or network calls.

Tool discovery is NOT proof of account authorization or portfolio scope.
Classifications only inform the separate read-only research process; they are
not an enforcement point for a live trading application.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

MODE = "COINBASE_MCP_TOOL_INVENTORY_V1"
MAX_MANIFEST_BYTES = 8192
MAX_TOOLS = 80

READ_ONLY = frozenset({
    "coinbase_balance",
    "coinbase_fees",
    "coinbase_portfolios_list",
    "coinbase_portfolios_get",
    "coinbase_products_get",
    "coinbase_products_list",
    "coinbase_products_ticker",
    "coinbase_products_book",
    "coinbase_products_candles",
    "coinbase_products_best_bid_ask",
    "coinbase_orders_preview",
    "coinbase_orders_edit_preview",
    "coinbase_orders_list",
    "coinbase_orders_get",
    "coinbase_orders_fills",
    "coinbase_convert_quote",
    "coinbase_convert_get",
    "coinbase_x402_resources",  # catalog discovery is free; fetch/pay are not
})
PAID = frozenset({"coinbase_x402_fetch", "coinbase_x402_pay"})
STATE_CHANGING = frozenset({
    "coinbase_orders_create",
    "coinbase_orders_edit",
    "coinbase_orders_cancel",
    "coinbase_orders_close_position",
    "coinbase_portfolios_create",
    "coinbase_portfolios_edit",
    "coinbase_portfolios_delete",
    "coinbase_transfer",  # between exchange portfolios, not an external withdrawal
    "coinbase_convert_execute",
    "coinbase_feedback_submit",
})
assert not (READ_ONLY & PAID or READ_ONLY & STATE_CHANGING or PAID & STATE_CHANGING)


class InventoryError(ValueError):
    """Manifest cannot be safely classified."""


def normalized_name(name):
    if not isinstance(name, str):
        raise InventoryError("Invalid tool name")
    prefix = "mcp__Coinbase__"
    if name.startswith(prefix):
        name = name[len(prefix):]
    if not re.fullmatch(r"coinbase_[a-z][a-z0-9_]{1,63}", name):
        raise InventoryError("Invalid tool name")
    return name


def audit(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {"mode", "source", "tool_names"}:
        raise InventoryError("Unexpected manifest fields")
    if manifest["mode"] != MODE or manifest["source"] != "coinbase_mcp":
        raise InventoryError("Unrecognized inventory source")
    tools = manifest["tool_names"]
    if not isinstance(tools, list) or len(tools) > MAX_TOOLS:
        raise InventoryError("Invalid tool list")
    names = [normalized_name(item) for item in tools]
    if len(names) != len(set(names)):
        raise InventoryError("Repeated tool name")
    discovered = set(names)
    unknown = discovered - READ_ONLY - PAID - STATE_CHANGING
    return {
        "mode": "COINBASE_MCP_OFFLINE_RESEARCH_SURFACE_AUDIT",
        "tool_count": len(names),
        "read_only_available": sorted(discovered & READ_ONLY),
        "paid_available_but_not_permitted": sorted(discovered & PAID),
        "state_changing_available_but_not_permitted": sorted(discovered & STATE_CHANGING),
        "unclassified_not_permitted": sorted(unknown),
        "research_inventory_classified": not bool(unknown),
        "account_permissions_verified": False,
        "portfolio_scope_verified": False,
        "remote_tools_invoked": False,
        "financial_operations": 0,
        "x402_payments": 0,
        "live_execution_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline, no-credential tool inventory audit")
    parser.add_argument("--file", required=True, help="Local manifest of tool names only")
    args = parser.parse_args(argv)
    try:
        path = Path(args.file)
        if not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
            raise InventoryError("Invalid manifest size")
        raw = path.read_bytes()
        if len(raw) > MAX_MANIFEST_BYTES:
            raise InventoryError("Invalid manifest size")
        report = audit(json.loads(raw))
    except (OSError, ValueError, UnicodeError, TypeError):
        # Never echo input, private filesystem paths, or provider exception text.
        print("INVENTORY_REJECTED")
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
