"""PRIVATE local read-only Ethereum/Base wallet observer via public Blockscout instances.

No wallet addresses are hard-coded, stored, or printed. Wallet watchlist lives
only in a LOCAL JSON file. Addresses are sent only to the allowlisted public
block explorer for the requested chain. Never input seeds or private keys.
No trading, signing, token approvals, transfers, blockchain writes or orders.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

CHAINS = {1: ("Ethereum", "eth.blockscout.com"),
          8453: ("Base", "base.blockscout.com")}
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
MAX_RESPONSE = 1_500_000
MAX_CONFIG = 50000


class WalletSourceError(ValueError):
    pass


def _utc(value):
    if not isinstance(value, str):
        raise WalletSourceError("UTC time required")
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WalletSourceError("Invalid ISO UTC time") from exc
    if date.tzinfo is None or date.utcoffset() != timedelta(0):
        raise WalletSourceError("UTC offset must be +00:00")
    return date.astimezone(timezone.utc)


def _decimal(v, *, strictly_positive=False):
    if v is None or isinstance(v, bool):
        raise WalletSourceError("Null/boolean numeric field")
    try:
        n = Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise WalletSourceError("Invalid numeric field") from exc
    if not n.is_finite() or n < 0 or strictly_positive and n == 0:
        raise WalletSourceError("Out of range numeric field")
    return n


def _address(addr):
    if not isinstance(addr, str) or not ADDRESS.fullmatch(addr):
        raise WalletSourceError("Malformed EVM address")
    return addr.lower()


def _private_config(data):
    if not isinstance(data, dict) or data.get("mode") != "PRIVATE_WALLET_READ_ONLY":
        raise WalletSourceError("Explicit private read-only mode required")
    # Do not accept secret-bearing records, even if not used by this module.
    forbidden = ("private_key", "mnemonic", "seed", "secret", "api_key", "password",
                 "keystore", "signing_key", "recovery_phrase")
    if any(x in json.dumps(data, sort_keys=True).lower() for x in forbidden):
        raise WalletSourceError("Secret-like content not permitted")
    watch = data.get("watch")
    if not isinstance(watch, list) or not 1 <= len(watch) <= 8:
        raise WalletSourceError("1-8 private account-chain watch entries required")
    out, seen, labels = [], set(), set()
    for item in watch:
        if not isinstance(item, dict):
            raise WalletSourceError("Invalid wallet watch entry")
        chain = item.get("chain_id")
        if isinstance(chain, bool) or chain not in CHAINS:
            raise WalletSourceError("Only Ethereum 1 and Base 8453 supported")
        addr = _address(item.get("address"))
        label = item.get("label")
        if not isinstance(label, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,28}", label):
            raise WalletSourceError("Safe non-identifying label required")
        if (chain, addr) in seen:
            raise WalletSourceError("Same address+chain specified twice under an alias")
        if (label, chain) in labels:
            raise WalletSourceError("Same label reused on a chain")
        seen.add((chain, addr))
        labels.add((label, chain))
        allow = item.get("verified_token_contracts", [])
        if not isinstance(allow, list) or len(allow) > 60:
            raise WalletSourceError("Unbounded token allowlist")
        approved = [_address(s) for s in allow]
        if len(set(approved)) != len(approved):
            raise WalletSourceError("Repeated token contract in allowlist")
        out.append((chain, addr, label, frozenset(approved)))
    return out


def _fetch_json(chain, addr, path, opener=urlopen):
    name, host = CHAINS[chain]
    expected = "/api/v2/addresses/" + addr + path
    url = "https://" + host + expected
    try:
        with opener(Request(url, headers={"User-Agent": "ISL-Private-ReadOnly-Wallet/1.0",
                                          "Accept": "application/json"}), timeout=35) as response:
            loc = urlparse(response.geturl())
            if (response.status != 200 or loc.scheme != "https" or loc.hostname != host
                    or loc.path.lower() != expected.lower() or loc.query or loc.fragment):
                raise WalletSourceError("Unexpected explorer redirect/HTTP response")
            raw = response.read(MAX_RESPONSE + 1)
    except WalletSourceError:
        raise
    except Exception:
        # urllib HTTPError typically embeds the full URL (wallet address).
        # Do not expose personal wallet identifiers in CLI traceback/logs.
        raise WalletSourceError("Explorer request failed (wallet address redacted)") from None
    if not raw or len(raw) > MAX_RESPONSE:
        raise WalletSourceError("Unbounded explorer response")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise WalletSourceError("Non-JSON explorer response") from exc
    return data, sha256(raw).hexdigest()


def _price_usd(token, balance):
    """Explorer's optional estimated exchange rate, NEVER execution evidence."""
    v = token.get("exchange_rate")
    if v is None:
        return None
    try:
        price = _decimal(v)
    except WalletSourceError:
        return None
    return balance * price if price > 0 else None


def _parse_chain(addr_data, tokens_data, verified_contracts):
    if not isinstance(addr_data, dict) or not isinstance(tokens_data, list):
        raise WalletSourceError("Unexpected Blockscout response shape")
    if len(tokens_data) > 200:
        raise WalletSourceError("Too many token records, cannot prove completeness")
    native_wei = _decimal(addr_data.get("coin_balance"))
    if native_wei != native_wei.to_integral_value():
        raise WalletSourceError("Fractional wei")
    native = native_wei / Decimal(10) ** 18
    values = []
    native_token = {"exchange_rate": addr_data.get("exchange_rate")}
    native_usd = _price_usd(native_token, native)
    if native:
        values.append({"asset": "ETH", "contract": "NATIVE", "quantity": str(native),
                       "usd_estimate": str(native_usd) if native_usd is not None else None,
                       "valuation_status": "EXPLORER_ESTIMATE" if native_usd is not None else "UNPRICED",
                       "trusted_token_identity": True})
    seen = set()
    for row in tokens_data:
        if not isinstance(row, dict) or not isinstance(row.get("token"), dict):
            raise WalletSourceError("Malformed Blockscout token-balance record")
        token = row["token"]
        typ = token.get("type")
        if typ != "ERC-20":
            # NFTs are intentionally out of the fungible-total valuation scope.
            continue
        contract = _address(token.get("address_hash"))
        if contract in seen:
            raise WalletSourceError("Duplicate contract balance row")
        seen.add(contract)
        precision = token.get("decimals")
        if isinstance(precision, bool) or not str(precision).isdigit():
            raise WalletSourceError("Missing token decimals")
        digits = int(precision)
        if digits > 36:
            raise WalletSourceError("Token decimals outside supported range")
        raw = _decimal(row.get("value"))
        if raw != raw.to_integral_value():
            raise WalletSourceError("Noninteger ERC-20 units")
        amount = raw / (Decimal(10) ** digits)
        if amount == 0:
            continue
        approved = contract in verified_contracts
        quoted = _price_usd(token, amount) if approved else None
        symbol = token.get("symbol")
        valid_symbol = isinstance(symbol, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,20}", symbol))
        # Without explicitly verified contract identity, do NOT trust symbols
        # from an arbitrary token (spoofed cbBTC or ETH is possible).
        values.append({"asset": symbol if approved and valid_symbol else "UNREVIEWED_ERC20",
                       "contract": contract if approved else "REDACTED_UNREVIEWED",
                       "quantity": str(amount) if approved else "WITHHELD_UNREVIEWED",
                       "usd_estimate": str(quoted) if quoted is not None else None,
                       "valuation_status": "EXPLORER_ESTIMATE" if quoted is not None else
                                           ("UNPRICED" if approved else "UNREVIEWED_TOKEN"),
                       "trusted_token_identity": approved})
    total = sum((Decimal(p["usd_estimate"]) for p in values if p["usd_estimate"] is not None),
                Decimal(0))
    unknown = sum(1 for p in values if p["usd_estimate"] is None)
    return values, total, unknown


def inspect_wallet_watchlist(config, now=None, fetcher=_fetch_json):
    entries = _private_config(config)
    current = _utc(now) if isinstance(now, str) else (now or datetime.now(timezone.utc))
    if current.tzinfo is None or current.utcoffset() != timedelta(0):
        raise WalletSourceError("UTC snapshot required")
    chain_items = []
    value = Decimal(0)
    unpriced = 0
    for chain, addr, label, contracts in entries:
        primary, sha1 = fetcher(chain, addr, "")
        tokens, sha2 = fetcher(chain, addr, "/token-balances")
        positions, subtotal, unknown = _parse_chain(primary, tokens, contracts)
        value += subtotal
        unpriced += unknown
        chain_items.append({
            "wallet_label": label, "network": CHAINS[chain][0], "chain_id": chain,
            "account_address_redacted": True, "contract_identity_allowlisted": True,
            "positions": positions, "priced_subtotal_usd": str(subtotal),
            "unpriced_or_unreviewed_position_count": unknown,
            "explorer_address_response_sha256": sha1,
            "explorer_token_balances_response_sha256": sha2,
            "complete_fungible_valuation": unknown == 0,
            "NFT_positions_not_included": True,
        })
    return {
        "status": "LOCAL_PRIVATE_WALLET_OBSERVATION",
        "observed_at_utc": current.isoformat(),
        "wallet_account_chain_count": len(chain_items),
        "wallets": chain_items,
        "priced_subtotal_usd": str(value),
        "unpriced_or_unreviewed_position_count": unpriced,
        "complete_fungible_valuation": unpriced == 0,
        "complete_all_assets_valuation": False,  # NFT and DeFi positions not fully enumerated
        "staking_liquidity_unknown": True,
        "source": "PUBLIC_BLOCKSCOUT_EXPLORER_ESTIMATE_ONLY",
        "historical_chain_state_oracle_verified": False,
        "wallet_balance_available_to_trade_verified": False,
        "addresses_or_secrets_persisted": False,
        "financial_operations": 0,
    }


def reconcile_custodial_and_wallet(cex, wallet):
    """Fail closed when source unknown. Distinct CEX/WALLET ledgers, no mixing.

    A self-custody wallet address is not a Coinbase custodial account. ETH on
    Base and Ethereum are separate entries even if the EVM address is the same.
    Do not add the same wallet chain/address twice; done in inspect above.
    """
    if not isinstance(wallet, dict) or wallet.get("status") != "LOCAL_PRIVATE_WALLET_OBSERVATION":
        raise WalletSourceError("Missing verified wallet analysis")
    if cex is not None and (not isinstance(cex, dict) or
                             cex.get("status") != "PRIVATE_READ_ONLY_SNAPSHOT_RISK_REVIEW"):
        raise WalletSourceError("Missing authorized custodial portfolio analysis")
    cex_value = _decimal(cex["reported_total_usd"]) if cex is not None else None
    wallet_value = _decimal(wallet["priced_subtotal_usd"])
    known = wallet_value + (cex_value or Decimal(0))
    return {
        "status": "SEPARATE_LEDGERS_NO_ASSET_DOUBLE_COUNT",
        "coinbase_exchange_reported_total_usd": str(cex_value) if cex_value is not None else None,
        "wallet_explorer_priced_subtotal_usd": str(wallet_value),
        "known_priced_amount_usd": str(known),
        "all_sources_present": cex is not None,
        "all_assets_completely_valued": False,
        "total_portfolio_net_worth_certified": False,
        "scope": "EXCHANGE_ACCOUNT_PLUS_CONFIGURED_ETHEREUM_BASE_ADDRESSES_ONLY",
        "warnings": [
            "KNOWN_PRICED_SUBTOTAL_IS_NOT_COMPLETE_NET_WORTH",
            "UNPRICED_ERC20_NFT_DEFI_AND_OTHER_CHAINS_NOT_INCLUDED",
            "EXPLORER_PRICES_NOT_EXECUTABLE_AND_CAN_BE_INACCURATE",
        ] + (["COINBASE_EXCHANGE_SNAPSHOT_MISSING"] if cex is None else []),
        "transfers_or_trades": 0,
    }



def inspect_local_wallet_snapshot(bundle, now=None):
    """Process private USER-PROVIDED Blockscout-shaped source JSON OFFLINE.

    This cannot establish live chain balances or source authenticity. It does
    permit reproducible exchange+wallet consolidated reviews when public
    explorer services are inaccessible. No network, filesystem, or signing.
    """
    accounts = _private_config(bundle)
    now = _utc(now) if isinstance(now, str) else (now or datetime.now(timezone.utc))
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise WalletSourceError("UTC report clock required")
    captured = _utc(bundle.get("captured_at"))
    age = now - captured
    if age < timedelta(seconds=-5) or age > timedelta(days=30):
        raise WalletSourceError("Future or stale wallet snapshot")
    result = []
    total, unpriced = Decimal(0), 0
    for (chain, addr, label, approved), item in zip(accounts, bundle["watch"]):
        response = item.get("address_response")
        tokens = item.get("token_balances_response")
        positions, subtotal, unknown = _parse_chain(response, tokens, approved)
        total += subtotal
        unpriced += unknown
        canonical = json.dumps([response, tokens], sort_keys=True,
                               separators=(",",":"), allow_nan=False).encode()
        result.append({
            "wallet_label":label, "network":CHAINS[chain][0], "chain_id":chain,
            "account_address_redacted":True, "contract_identity_allowlisted":True,
            "positions":positions, "priced_subtotal_usd":str(subtotal),
            "unpriced_or_unreviewed_position_count":unknown,
            "source_snapshot_sha256":sha256(canonical).hexdigest(),
            "complete_fungible_valuation":unknown == 0,
            "NFT_positions_not_included":True
        })
    return {
        "status":"LOCAL_PRIVATE_WALLET_OBSERVATION",
        "observed_at_utc":captured.isoformat(),
        "wallet_account_chain_count":len(result),
        "wallets":result, "priced_subtotal_usd":str(total),
        "unpriced_or_unreviewed_position_count":unpriced,
        "complete_fungible_valuation":unpriced == 0,
        "complete_all_assets_valuation":False,
        "staking_liquidity_unknown":True,
        "source":"USER_SUPPLIED_LOCAL_EXPORT_NOT_AUTHENTICATED",
        "historical_chain_state_oracle_verified":False,
        "wallet_balance_available_to_trade_verified":False,
        "addresses_or_secrets_persisted":False,
        "snapshot_age_hours":str((Decimal(str(age.total_seconds()))/3600).quantize(Decimal(".1"))),
        "stale_snapshot_warning":age > timedelta(hours=24),
        "financial_operations":0
    }



def main(argv=None):
    parser = argparse.ArgumentParser(description="Local private EVM wallet balance observer only")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--watchlist", type=Path,
                        help="PRIVATE local address list, live public explorer GETs")
    source.add_argument("--snapshot-file", type=Path,
                        help="PRIVATE local archived Blockscout-shaped JSON; OFFLINE, potentially stale")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    source_file = args.watchlist if args.watchlist else args.snapshot_file
    if source_file.stat().st_size > MAX_CONFIG:
        raise WalletSourceError("Wallet local input too large")
    data = json.loads(source_file.read_text(encoding="utf-8"))
    result = (inspect_wallet_watchlist(data) if args.watchlist
              else inspect_local_wallet_snapshot(data))
    if args.format == "json":
        print(json.dumps(result, sort_keys=True))
        return
    print("# Investment Strategy Lab — wyłącznie lokalny wallet on-chain")
    print("Odczyt (UTC):", result["observed_at_utc"])
    for row in result["wallets"]:
        print(f"- {row['wallet_label']} / {row['network']}: "
              f"{row['priced_subtotal_usd']} USD wycenionego podzbioru; "
              f"{row['unpriced_or_unreviewed_position_count']} niewycenionych/niezweryfikowanych pozycji")
    print("Wyceniony podzbiór walleti:", result["priced_subtotal_usd"], "USD")
    print("Nie jest to pełna wartość majątku ani kwota dostępna do transakcji.")
    print("Adresy i prywatne pliki nie są drukowane; brak transakcji.")


if __name__ == "__main__":
    main()
