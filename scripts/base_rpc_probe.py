"""Public Base RPC availability probe with no account or wallet identifiers.

Probe a bounded zero-address ERC20 log filter. A successful probe only shows
that the selected allowlisted RPC serves the required read methods *now*; it
does not certify wallet history, provider SLA or any trade permission.
"""
from datetime import datetime, timedelta, timezone
import argparse
import json

from scripts import operational_read_only as m

PROBE_MODE = "BASE_PUBLIC_READ_ONLY_RPC_PROBE_V1"
ZERO_ADDRESS_TOPIC = "0x" + "0" * 64


class ProbeError(ValueError):
    pass


def require(ok):
    if not ok:
        raise ProbeError("BASE_READ_PROBE_REJECTED")


def probe(now, *, rpc=m.rpc_read):
    """Two bounded eth_getLogs filters, not a user's address or credential."""
    require(isinstance(now, datetime) and now.tzinfo is not None
            and now.utcoffset() == timedelta(0))
    require(m.RPC_URLS[8453] in m.BASE_RPC_SOURCES.values())
    require(m._hex(rpc(8453, "eth_chainId", [])) == 8453)
    finalized = rpc(8453, "eth_getBlockByNumber", ["finalized", False])
    require(isinstance(finalized, dict)
            and m.HEX32.fullmatch(finalized.get("hash", "")))
    end = m._hex(finalized.get("number"))
    timestamp = datetime.fromtimestamp(
        m._hex(finalized.get("timestamp")), timezone.utc)
    require(timedelta(seconds=-5) <= now - timestamp <= timedelta(hours=1))
    start = max(0, end - 79)
    contract = next(iter(m.TOKENS[8453]))
    for topics in (
        [m.TRANSFER_TOPIC, ZERO_ADDRESS_TOPIC],
        [m.TRANSFER_TOPIC, None, ZERO_ADDRESS_TOPIC],
    ):
        result = rpc(8453, "eth_getLogs", [{
            "address": contract,
            "fromBlock": hex(start),
            "toBlock": hex(end),
            "topics": topics,
        }])
        require(isinstance(result, list) and len(result) <= 5000)
    # The observed head must remain the same finalized hash at the same block.
    check = rpc(8453, "eth_getBlockByNumber", [hex(end), False])
    require(isinstance(check, dict)
            and check.get("hash") == finalized["hash"]
            and m._hex(check.get("number")) == end)
    return {
        "mode": PROBE_MODE,
        "source": ("PUBLICNODE" if
                   m.RPC_URLS[8453] == m.BASE_RPC_SOURCES["PUBLICNODE"]
                   else "OFFICIAL"),
        "status": "PUBLIC_BASE_READ_METHODS_AVAILABLE",
        "log_filter_count": 2,
        "blocks_tested": end - start + 1,
        "wallet_identifiers_sent": False,
        "provider_sla_certified": False,
        "full_wallet_history_certified": False,
        "financial_operations": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Public read-only Base RPC probe")
    parser.add_argument("--allow-public-network-probe", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_public_network_probe:
        print("BASE_READ_PROBE_OPT_IN_REQUIRED")
        return 2
    try:
        result = probe(datetime.now(timezone.utc))
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        print("BASE_READ_PROBE_UNAVAILABLE_OR_REJECTED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
