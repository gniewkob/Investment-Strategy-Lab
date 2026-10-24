"""Bounded, read-only repair of previously detected ERC20 monitoring gaps.

Only registered Ethereum/Base ERC20 logs. Not a full chain-history importer,
financial execution path, receipt authenticator or Coinbase-to-chain join.
Persist an exact source-specific evidence file BEFORE reducing a gap.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path

from scripts import history_coverage as coverage
from scripts.autonomous_coinbase_history import private_directory
from scripts.operational_read_only import (
    _hex, _history, rpc_read, read_private, write_private, HEX32, TOKENS,
)

MAX_BLOCKS_PER_CYCLE = 80
MAX_CAPTURED_EVENTS = 1000
CAPTURE_MODE = "PRIVATE_ERC20_BACKFILL_EVIDENCE_V1"


class RecoveryError(ValueError):
    pass


def _require(ok):
    if not ok:
        raise RecoveryError("READ_ONLY_HISTORY_BACKFILL_REJECTED")


def restore(known, stream, scope, start, end, evidence_sha256):
    """Acknowledge precisely one persisted, fully checked prefix of oldest gap."""
    _require(isinstance(known, dict)
             and known.get("mode") == coverage.MODE
             and isinstance(known.get("streams"), dict)
             and isinstance(stream, str) and stream in known["streams"])
    previous = known["streams"][stream]
    coverage._record(previous)
    _require(previous["identity_sha256"] == scope
             and previous["latest_status"] == "COMPLETE_RANGE"
             and not previous["scope_reset"]
             and len(previous["gap_ranges"]) > 0
             and type(start) is int and type(end) is int
             and 0 <= start <= end <= coverage.MAX_BLOCK
             and end - start < MAX_BLOCKS_PER_CYCLE
             and isinstance(evidence_sha256, str)
             and len(evidence_sha256) == 64
             and all(ch in "0123456789abcdef" for ch in evidence_sha256))
    lo, hi = previous["gap_ranges"][0]
    _require(start == lo and end <= hi)
    result = deepcopy(known)
    record = result["streams"][stream]
    if end == hi:
        record["gap_ranges"].pop(0)
    else:
        record["gap_ranges"][0][0] = end + 1
    coverage._record(record)
    result["gap_range_count"] = sum(
        len(s["gap_ranges"]) for s in result["streams"].values())
    result["historical_gap_detected"] = any(
        s["gap_ranges"] or s["gap_range_overflow"]
        for s in result["streams"].values())
    result["latest_source_incomplete"] = any(
        s["latest_status"] != "COMPLETE_RANGE"
        for s in result["streams"].values())
    return result


def recover_one(current, entries, sources, state, *, rpc=rpc_read):
    """At most one 80-block window per supervisor cycle across all wallets.

    Fails closed: exceptions propagate to supervisor for redacted status.
    Only scopes with a successful latest source window are considered.
    """
    _require(isinstance(current, dict) and current.get("mode") == coverage.MODE
             and isinstance(current.get("streams"), dict)
             and isinstance(entries, list) and len(entries) <= 8
             and isinstance(sources, dict))
    candidates = []
    for chain, address, label, contracts in entries:
        key = f"chain_{label}_{chain}"
        row = current["streams"].get(key)
        if not row:
            continue
        coverage._record(row)
        if (row["gap_ranges"] and row["latest_status"] == "COMPLETE_RANGE"
                and not row["scope_reset"]
                and sources.get(key, {}).get("status") == "OK"):
            _require(row["identity_sha256"] == coverage._identity(
                chain, address, contracts) and contracts.issubset(TOKENS[chain]))
            candidates.append((key, chain, address, label, contracts, row))
    if not candidates:
        return {"status": "NO_ELIGIBLE_GAP", "coverage": current,
                "recovered_block_count": 0, "events_saved": 0,
                "financial_operations": 0}
    # Deterministic selection prevents multiple expensive RPC scans per cycle.
    key, chain, address, label, contracts, row = sorted(candidates)[0]
    start, oldest_end = row["gap_ranges"][0]
    end = min(oldest_end, start + MAX_BLOCKS_PER_CYCLE - 1)
    # An authenticated chain ID and provider-finalized head are required.
    _require(_hex(rpc(chain, "eth_chainId", [])) == chain)
    finalized = rpc(chain, "eth_getBlockByNumber", ["finalized", False])
    _require(isinstance(finalized, dict)
             and _hex(finalized.get("number")) >= end
             and HEX32.fullmatch(finalized.get("hash", "")))
    boundary = rpc(chain, "eth_getBlockByNumber", [hex(end), False])
    _require(isinstance(boundary, dict)
             and _hex(boundary.get("number")) == end
             and HEX32.fullmatch(boundary.get("hash", ""))
             and _hex(boundary.get("timestamp")) <= _hex(finalized.get("timestamp")))
    history = _history(chain, address, contracts, end, end - start + 1, rpc, boundary)
    _require(history.get("status") == "COMPLETE_REQUESTED_TOKEN_RANGE"
             and history.get("from_block") == start
             and history.get("to_block") == end
             and type(history.get("event_count")) is int
             and history["event_count"] <= MAX_CAPTURED_EVENTS
             and len(history.get("events", [])) == history["event_count"])
    repeat = rpc(chain, "eth_getBlockByNumber", [hex(end), False])
    _require(isinstance(repeat, dict) and repeat.get("hash") == boundary["hash"]
             and _hex(repeat.get("number")) == end)
    # Public chain events are still private local portfolio history.
    events = []
    for event in history["events"]:
        _require(event.get("chain_id") == chain and
                 event.get("contract") in contracts and
                 start <= event.get("block_number", -1) <= end)
        events.append({**event, "wallet_label": label,
            "event_id": sha256((label + ":" + event["event_id"]).encode()).hexdigest()})
    events.sort(key=lambda e: (e["block_number"], e["tx_hash"], e["event_id"]))
    evidence = {"mode": CAPTURE_MODE, "stream": key,
                "scope_sha256": row["identity_sha256"], "chain_id": chain,
                "from_block": start, "to_block": end,
                "finalized_head_number_at_read": _hex(finalized["number"]),
                "end_block_hash": boundary["hash"], "events": events,
                "event_count": len(events),
                "provider_finality_not_independent_consensus": True,
                "coinbase_linkage_verified": False, "financial_operations": 0}
    raw = json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    _require(len(raw) <= 1_500_000)
    evidence_sha = sha256(raw).hexdigest()
    # Never persist wallet addresses in file names. Caller holds supervisor lock.
    folder = private_directory(Path(state) / "history-backfill")
    basename = sha256(
        f"{key}:{row['identity_sha256']}:{start}:{end}".encode()).hexdigest()
    path = folder / (basename + ".json")
    if os.path.lexists(path):
        persisted = read_private(path)
        # Head height legitimately advances between retries. The original
        # evidence stays immutable; require every invariant besides the
        # originally observed (still >= requested end) finalized head height.
        _require(isinstance(persisted, dict)
                 and set(persisted) == set(evidence)
                 and type(persisted.get("finalized_head_number_at_read")) is int
                 and persisted["finalized_head_number_at_read"] >= end
                 and {k: v for k, v in persisted.items()
                      if k != "finalized_head_number_at_read"} ==
                     {k: v for k, v in evidence.items()
                      if k != "finalized_head_number_at_read"})
        raw = json.dumps(persisted, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        evidence_sha = sha256(raw).hexdigest()
    else:
        write_private(path, evidence)
        fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    # Only durable evidence advances coverage; a crash here is retryable.
    next_coverage = restore(current, key, row["identity_sha256"],
                             start, end, evidence_sha)
    return {"status": "RECOVERED_WINDOW", "coverage": next_coverage,
            "recovered_block_count": end - start + 1,
            "events_saved": len(events), "financial_operations": 0}
