# Investment Strategy Lab — prywatny wallet on-chain + Coinbase Exchange

**Cel:** rozdzielne monitorowanie środków na giełdzie Coinbase oraz w portfelach samodzielnych na sieciach Ethereum (chain ID 1) i Base (chain ID 8453). A wallet on-chain is **not** the Coinbase Exchange portfolio. This is local, read-only observation — NOT custody, staking withdrawal, signing, swap, trading, or financial advice.

## Zakres i aktualne ograniczenia

- **Wallet name/source-of-truth correction:** historical labels must **never** be treated as evidence that one address is a legacy account and another is the active wallet. The user confirms the current `cb.id` name privately; it must be resolved to a current public address using a CCIP Read-capable ENS resolver before chain-specific balance inspection. [ENS documents Coinbase Wallet `cb.id` as an offchain ENS subname](https://docs.ens.domains/learn/ccip-read/). Public documentation intentionally omits the user's identifier and addresses. A 17 Oct 2026 holding/value is **historical**, not today's wallet balance.
- Current connected Coinbase *exchange* portfolio holdings (which may include staked ETH/ATOM) are separate from EVM wallet balances. A different chain for the same EVM address can contain a **different** asset balance.
- This implementation reads Ethereum and Base public chain explorers **only from a local private CLI process**. The actual wallet addresses are NEVER committed to GitHub, included in public GitHub workflow, put into OpenBrain memory or printed in reports. Browser/Blockscout providers necessarily see public addresses submitted for lookup.
- Provider [Blockscout instance REST API](https://docs.blockscout.com/devs/apis/rest) offers `/api/v2/addresses/{address}` and `/api/v2/addresses/{address}/token-balances` endpoints. Read-only response contracts were tested on synthetic fixtures. Live accessibility of these endpoints for the particular user wallets **has not been verified** in the GitHub Actions environment and is not promised; rate limits, unsupported tokens or stale indexing must fail explicitly. Paid Blockscout PRO API is **not** requested, purchased or configured.
- Native ETH raw `coin_balance` and approved fungible ERC-20 `value` are converted from base units with exact `Decimal` arithmetic; any optional USD `exchange_rate` is **only an explorer estimate, not an executable quote**. ERC-20 asset identities are accepted **only for manually reviewed exact contract addresses on the right chain**, never simply because a token says `cbBTC`, `ETH` or `SHIK`. All other positive-balance tokens are explicitly *UNREVIEWED* and unpriced. NFTs, DeFi/pool/staked protocol contracts and other chains are not fully enumerated.
- Subtotal is **KNOWN PRICED SUBSET** only; neither the wallet module nor the combined report can certify full net worth or spendable crypto. Network congestion, spoof tokens, airdrop spam, hidden unpriced assets and protocol liabilities can affect an explorer summary.

## Private local watchlist — no seeds, private keys, passwords or OAuth

The file below is **fake format documentation only**; all addresses are manufactured. Create a private untracked file outside the repository, e.g. in your home directory with filesystem permissions limited to you. Use your actual previously held public EVM addresses only in that private file.

```json
{
  "mode": "PRIVATE_WALLET_READ_ONLY",
  "watch": [
    {
      "label": "primary",
      "chain_id": 8453,
      "address": "0x1111111111111111111111111111111111111111",
      "verified_token_contracts": ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
    },
    {
      "label": "legacy",
      "chain_id": 1,
      "address": "0x2222222222222222222222222222222222222222",
      "verified_token_contracts": []
    }
  ]
}
```

**Important:** example addresses and contracts are NOT validated personal addresses or endorsed assets. To inspect both of your known wallets on both networks, you can configure four distinct (wallet address, chain ID) entries. Adding the *same* address+chain twice under different aliases fails to prevent inflated totals. For token contracts use only contract addresses you have independently verified from trustworthy sources for the intended blockchain; do not infer contract authenticity from a matching symbol or a Coinbase notification.

## Usage

```bash
# One-time local wallet observation, with private watchlist file:
python3 -m scripts.private_wallet_chain_monitor --watchlist /PRIVATE/PATH/wallet-watch.private.json

# One-time *combined* market + wallet monitoring (no CEX account in this example):
python3 -m scripts.read_only_portfolio_monitor --wallet-watchlist /PRIVATE/PATH/wallet-watch.private.json

# Combined CEX + wallet: CEX is an independently read-only user-supplied private snapshot:
python3 -m scripts.read_only_portfolio_monitor \
  --portfolio-file /PRIVATE/PATH/coinbase.portfolio-private.json \
  --wallet-watchlist /PRIVATE/PATH/wallet-watch.private.json
```

### Offline fallback, when the public blockchain explorer is unavailable

A neutral-address Blockscout integration smoke test in [GitHub Actions #39559863580](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39559863580) **FAILED** on an explorer HTTPS request. It contained **no user address** and this does **not** prove any user's wallet is empty or inaccessible. Live reads of the user's wallet remain **UNVERIFIED**. Do not hide this negative source evidence, assume paid API keys, or retry in a tight loop.

The monitor now supports a **private locally exported data snapshot** in the same read-only mode, containing `captured_at` and `address_response` plus `token_balances_response` for each configured address+chain pair. These are the bodies of the two corresponding Blockscout API responses, supplied independently by the operator. Example below is **ENTIRELY FABRICATED** and **NOT a real user's wallet or chain state**:

```json
{
  "mode": "PRIVATE_WALLET_READ_ONLY",
  "captured_at": "2026-10-21T07:00:00Z",
  "watch": [{
    "label": "primary",
    "chain_id": 8453,
    "address": "0x1111111111111111111111111111111111111111",
    "verified_token_contracts": ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
    "address_response": {"coin_balance": "100000000000000000", "exchange_rate": "2000"},
    "token_balances_response": [{
      "value": "100000",
      "token": {
        "type": "ERC-20",
        "address_hash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "symbol": "DEMO",
        "decimals": "8",
        "exchange_rate": "100000"
      }
    }]
  }]
}
```

```bash
# Pure offline, no external network, all wallet data stay in the local file:
python3 -m scripts.private_wallet_chain_monitor --snapshot-file /PRIVATE/PATH/wallet-export.private.json

# Public market report + private historical wallet snapshot:
python3 -m scripts.read_only_portfolio_monitor --wallet-snapshot-file /PRIVATE/PATH/wallet-export.private.json

# Combine with a separately captured Coinbase Exchange account view:
python3 -m scripts.read_only_portfolio_monitor \
  --portfolio-file /PRIVATE/PATH/coinbase.portfolio-private.json \
  --wallet-snapshot-file /PRIVATE/PATH/wallet-export.private.json
```

The snapshot is **not authenticated as having originated from Blockscout** and is not a live blockchain query. The CLI rejects captured times in the future and older than 30 days, and prominently warns when the wallet snapshot is older than 24 hours. Source schema is fail-closed: an absent token response, absent native coin balance, duplicate contract or unapproved token valuation cannot silently imply `0 USD` or a complete portfolio. Wallet addresses never appear in CLI output.

The optional private Coinbase snapshot schema is described in [READ_ONLY_PORTFOLIO_MONITOR_PL.md](READ_ONLY_PORTFOLIO_MONITOR_PL.md). It uses a captured-at UTC timestamp, balance reconciliation and staking categorization, and contains **no** brokerage signing credentials.

The combined report labels separately:
- Exchange reported USD total with its own capture timestamp (when provided).
- Wallet *explorer-priced subtotal* of approved tokens and native ETH.
- Unpriced/unreviewed on-chain positions, NFT/DeFi caveats and chain network scope.
- Sum of **identified USD-valued subsets** only, accompanied by `all_assets_completely_valued=false`, `total_portfolio_net_worth_certified=false`. **No silent Coinbase/wallet double counting.**

## Secrets and safety controls

- Never paste recovery phrases, seed words, private keys, wallet login credentials, signing permissions or 2FA codes into this program or ChatGPT. **Public addresses only.** Code explicitly refuses common secret-bearing fields.
- Never save real wallet addresses to `tests/`, `docs/`, GitHub Issues, Actions workflow inputs, public logs, OpenBrain or CI fixtures. Both the CLI and error handling suppress personal address contents.
- Public GitHub Actions workflow remains **market data only**. It does not fetch personal wallet addresses, and running it does NOT refresh wallet holdings.
- Code never requests blockchain signing, approvals, swaps, withdraws, transfers, stake changes, marketplace actions or paid APIs.
- Wallet source provider may return HTTP 429/403 or altered schema: all such conditions must be reported as failure/unavailable, not last-known wallet value or zero balance.
- The implementation is not a live multi-wallet explorer success claim until tested privately on the user's wallet addresses. No current wallet market-value assertion is certified in this PR.

## Completion criteria and evidence

- Offline tests of EVM network/address uniqueness, anti-spoof ERC-20 identification, stale/unpriced totals, main-account + wallet aggregation, safe redaction, malformed source rejection and zero transactions.
- Full offline Python regression and isolated prior tests on exact PR HEAD; only PR branch code and docs changed.
- **The privacy boundary prohibits a personal wallet-account source integration job in public CI**. Live user wallet reading must be performed only privately from the local CLI through authorized public blockchain explorers. Mark status accordingly.
- User's previously requested simulated M1–M3 remains untouched; Coinbase account staking balance is never assumed immediately liquid.

**No automated trading or real-money execution is implemented or authorized.**
