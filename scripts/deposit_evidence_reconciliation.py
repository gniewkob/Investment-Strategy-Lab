"""Offline Coinbase deposit-to-chain reconciliation; never treats balances as deposit proof.

Inputs are caller-provided records. Even a matching record remains SOURCE_UNVERIFIED
until a separate trusted Coinbase connector attests provenance. No network or writes.
"""
from decimal import Decimal, InvalidOperation
import re

HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
ASSETS = {"ETH", "cbBTC"}
NETWORKS = {1, 8453}
CREDITED = {"COMPLETED"}  # Anything else fails closed.

class DepositEvidenceError(ValueError):
    pass

def _require(condition):
    if not condition:
        raise DepositEvidenceError("DEPOSIT_EVIDENCE_REJECTED")

def _amount(value, asset):
    _require(isinstance(value, str) and bool(re.fullmatch(r"(0|[1-9][0-9]*)(\.[0-9]+)?", value)))
    scale = 8 if asset == "cbBTC" else 18
    fractional = value.partition(".")[2].rstrip("0")
    _require(len(fractional) <= scale)
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise DepositEvidenceError("DEPOSIT_EVIDENCE_REJECTED") from None
    _require(result.is_finite() and result > 0)
    return result

def reconcile(network_transfers, deposit_records):
    """Return conservative classifications without enriching or mutating inputs.

    deposit_records schema: source, deposit_id, chain_id, tx_hash, asset,
    amount, recipient, status. Source is explicitly claimed, not authenticated.
    """
    _require(isinstance(network_transfers, list) and isinstance(deposit_records, list))
    _require(len(network_transfers) <= 100 and len(deposit_records) <= 100)
    index = {}
    ids = set()
    for d in deposit_records:
        _require(isinstance(d, dict) and set(d) == {
            "source", "deposit_id", "chain_id", "tx_hash", "asset", "amount", "recipient", "status"})
        _require(d["source"] == "COINBASE_DEPOSIT_RECORD_OPERATOR_SUPPLIED")
        _require(isinstance(d["deposit_id"], str) and bool(re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", d["deposit_id"])))
        _require(d["deposit_id"] not in ids)
        ids.add(d["deposit_id"])
        _require(type(d["chain_id"]) is int and d["chain_id"] in NETWORKS)
        _require(isinstance(d["tx_hash"], str) and bool(HASH.fullmatch(d["tx_hash"])))
        _require(d["asset"] in ASSETS and isinstance(d["recipient"], str) and bool(ADDRESS.fullmatch(d["recipient"])))
        _require(isinstance(d["status"], str) and d["status"] in {"COMPLETED", "PENDING", "FAILED"})
        amt = _amount(d["amount"], d["asset"])
        key = (d["chain_id"], d["tx_hash"].lower())
        _require(key not in index)  # Conflicting or duplicate exchange evidence.
        index[key] = (d, amt)
    result = []
    seen = set()
    for t in network_transfers:
        _require(isinstance(t, dict) and set(t) == {"chain_id", "tx_hash", "asset", "amount", "recipient", "network"})
        _require(type(t["chain_id"]) is int and t["chain_id"] in NETWORKS)
        _require(isinstance(t["tx_hash"], str) and bool(HASH.fullmatch(t["tx_hash"])))
        _require(t["asset"] in ASSETS and isinstance(t["recipient"], str) and bool(ADDRESS.fullmatch(t["recipient"])))
        _require(t["network"] in {"FINALIZED", "INCLUDED", "PENDING", "REVERTED", "UNAVAILABLE"})
        amount = _amount(t["amount"], t["asset"])
        key = (t["chain_id"], t["tx_hash"].lower())
        _require(key not in seen)
        seen.add(key)
        evidence = index.get(key)
        classification = "NO_MATCHING_DEPOSIT_RECORD"
        deposit_id = None
        if evidence:
            d, d_amount = evidence
            deposit_id = d["deposit_id"]
            same = d["asset"] == t["asset"] and d_amount == amount and d["recipient"].lower() == t["recipient"].lower()
            if not same:
                classification = "CONFLICTING_DEPOSIT_RECORD"
            elif t["network"] != "FINALIZED":
                classification = "NETWORK_NOT_FINALIZED"
            elif d["status"] not in CREDITED:
                classification = "DEPOSIT_NOT_COMPLETED"
            else:
                classification = "REPORTED_MATCH_SOURCE_UNVERIFIED"
        result.append({"chain_id":t["chain_id"], "tx_hash":key[1],
                       "deposit_id":deposit_id, "classification":classification,
                       "coinbase_provenance_verified":False,
                       "balance_used_as_proof":False})
    return result
