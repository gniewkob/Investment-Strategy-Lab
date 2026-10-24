"""Conservative private, offline coverage accounting for rolling finalized ERC20 reads.

Proves neither full chain history nor completeness of any Coinbase account.
No network, wallet, token, database, execution or filesystem operations.
"""
from hashlib import sha256
import json

MODE = "PRIVATE_ERC20_ROLLING_COVERAGE_V1"
MAX_GAPS = 64
MAX_BLOCK = 2**64 - 1


class CoverageError(ValueError):
    pass


def _require(ok):
    if not ok:
        raise CoverageError("HISTORY_COVERAGE_INPUT_REJECTED")


def _block(n):
    _require(type(n) is int and 0 <= n <= MAX_BLOCK)
    return n


def _identity(chain, address, contracts):
    _require(type(chain) is int and chain in (1, 8453))
    _require(isinstance(address, str) and len(address) == 42 and address[:2] == "0x")
    _require(isinstance(contracts, (set, frozenset, list, tuple)))
    return sha256(json.dumps([chain, address.lower(), sorted(contracts)],
                             separators=(",", ":")).encode()).hexdigest()


def _record(entry):
    _require(isinstance(entry, dict) and set(entry) == {
        "identity_sha256", "first_complete_from_block", "last_complete_to_block",
        "gap_ranges", "gap_range_overflow", "latest_status", "scope_reset"})
    _require(isinstance(entry["identity_sha256"], str)
             and len(entry["identity_sha256"]) == 64
             and all(c in "0123456789abcdef" for c in entry["identity_sha256"]))
    first, last = entry["first_complete_from_block"], entry["last_complete_to_block"]
    _require((first is None and last is None) or (first is not None and last is not None))
    if first is not None:
        _require(_block(first) <= _block(last))
    gaps = entry["gap_ranges"]
    _require(isinstance(gaps, list) and len(gaps) <= MAX_GAPS
             and type(entry["gap_range_overflow"]) is bool and type(entry["scope_reset"]) is bool)
    previous_end = -1
    for gap in gaps:
        _require(isinstance(gap, list) and len(gap) == 2)
        lo, hi = gap
        _require(_block(lo) <= _block(hi) and lo > previous_end)
        _require(first is not None and first < lo and hi < last)
        previous_end = hi
    _require(entry["latest_status"] in {
        "COMPLETE_RANGE", "SOURCE_UNAVAILABLE", "BLOCK_REGRESSION",
        "NO_COMPLETE_WINDOW", "IDENTITY_CHANGED"})
    return entry


def advance(previous, entries, sources):
    """Track gaps between successive complete windows of a fixed wallet/token scope.

    A failed RPC read never advances the high watermark. Once a gap exists it
    stays visible; this function never infers that later scans backfilled it.
    """
    _require(isinstance(entries, list) and len(entries) <= 8
             and isinstance(sources, dict))
    old = {}
    if previous is not None:
        _require(isinstance(previous, dict) and set(previous) == {"mode", "streams"}
                 and previous["mode"] == MODE and isinstance(previous["streams"], dict)
                 and len(previous["streams"]) <= 8)
        old = previous["streams"]
        for name, value in old.items():
            _require(isinstance(name, str) and len(name) <= 75)
            _record(value)

    fresh = {}
    for chain, address, label, contracts in entries:
        _require(isinstance(label, str) and label and len(label) <= 29)
        key = f"chain_{label}_{chain}"
        _require(key not in fresh and key in sources)
        identity = _identity(chain, address, contracts)
        original = old.get(key)
        changed = original is not None and original["identity_sha256"] != identity
        prior = original if original and not changed else None
        record = {
            "identity_sha256": identity,
            "first_complete_from_block": prior["first_complete_from_block"] if prior else None,
            "last_complete_to_block": prior["last_complete_to_block"] if prior else None,
            "gap_ranges": [list(g) for g in prior["gap_ranges"]] if prior else [],
            "gap_range_overflow": prior["gap_range_overflow"] if prior else False,
            "latest_status": "IDENTITY_CHANGED" if changed else "SOURCE_UNAVAILABLE",
            "scope_reset": bool(changed),
        }
        source = sources[key]
        _require(isinstance(source, dict) and source.get("status") in
                 {"OK", "PARTIAL", "UNAVAILABLE"})
        if source["status"] == "OK":
            data = source.get("data")
            wallets = data.get("wallets") if isinstance(data, dict) else None
            _require(isinstance(wallets, list) and len(wallets) == 1)
            wallet = wallets[0]
            _require(wallet.get("wallet_label") == label and wallet.get("chain_id") == chain)
            history = wallet.get("history")
            _require(isinstance(history, dict) and
                     history.get("status") == "COMPLETE_REQUESTED_TOKEN_RANGE")
            start, end = _block(history.get("from_block")), _block(history.get("to_block"))
            _require(start <= end and end - start < 1000
                     and _block(wallet.get("source_block_number")) == end)
            if record["last_complete_to_block"] is not None and end < record["last_complete_to_block"]:
                record["latest_status"] = "BLOCK_REGRESSION"
            else:
                if record["first_complete_from_block"] is None:
                    record["first_complete_from_block"] = start
                elif start > record["last_complete_to_block"] + 1:
                    if len(record["gap_ranges"]) < MAX_GAPS:
                        record["gap_ranges"].append(
                            [record["last_complete_to_block"] + 1, start - 1])
                    else:
                        record["gap_range_overflow"] = True
                record["last_complete_to_block"] = end
                record["latest_status"] = "COMPLETE_RANGE"
        elif not changed:
            record["latest_status"] = "SOURCE_UNAVAILABLE"
        _record(record)
        fresh[key] = record

    _require(not (set(old) - set(fresh)) or len(set(old) - set(fresh)) <= 8)
    total_gaps = sum(len(item["gap_ranges"]) for item in fresh.values())
    has_gap = any(item["gap_ranges"] or item["gap_range_overflow"] for item in fresh.values())
    incomplete = any(item["latest_status"] != "COMPLETE_RANGE" for item in fresh.values())
    return {
        "mode": MODE,
        "streams": fresh,
        "gap_range_count": total_gaps,
        "historical_gap_detected": has_gap,
        "latest_source_incomplete": incomplete,
        "coverage_scope": "ONLY_REGISTERED_ERC20_LOGS_SINCE_FIRST_COMPLETE_WINDOW",
        "complete_chain_history_certified": False,
        "account_to_chain_linkage_certified": False,
        "financial_operations": 0,
    }
