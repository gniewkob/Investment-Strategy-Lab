# Investment Strategy Lab — bounded finalized ERC20 backfill (2026-10-24)

## Delivered scope

The private local supervisor retains balances, research and watchlist configuration.
After each successful rolling Ethereum/Base read, it checks **persisted history gaps**
from `history_coverage.advance`. Where a gap exists and current source is healthy,
it attempts to restore **at most one 80-block prefix** across all watched sources
per 900-second supervisor cycle using the current allowlisted public RPC adapter.

- Only verified tokens from `scripts.operational_read_only.TOKENS`; currently registered ERC20 cbBTC.
- Read methods only: `eth_chainId`, `eth_getBlockByNumber`, `eth_getLogs`.
- Provider-finalized head must contain the requested historical end block. End-block
  header is re-read to reject changed identity.
- Existing `_history` validates log address, topic, transaction/block hash, block
  and timestamp, bounded event count, and source block-hash agreement.
- Persist captured private events **before** closing the corresponding gap.
  Evidence is `0600` in a `0700` local subfolder `history-backfill`, with a
  scope-keyed opaque filename (no wallet address). Existing evidence must match
  byte-level canonical content; conflict stops restoration.
- An interrupted run after saving evidence but before updating `portfolio.json`
  re-reads evidence on the next cycle and safely retries. No double counting or
  mutation of Coinbase history, available balance, investments or paper benchmark.
- Recovery exceptions are redacted to `history_backfill.status=UNAVAILABLE`,
  retain the original gap and set `HISTORY_BACKFILL_UNAVAILABLE`.
- The private dashboard summarizes recovered blocks and events. Failed histories
  or a remaining gap keep overall `PARTIAL` and watchdog alerts.
- First observed window is NOT full historical chain coverage. Never infer an
  incoming Coinbase deposit from a blockchain event or from time/amount matching.
- `gap_range_overflow` remains sticky; 64+ historic holes cannot be silently
  reclassified as a continuous archive by repairing only listed gaps.

## Safety and operational constraints

**No orders, transfers, swaps, signing, x402 payments, new credentials, public
webhooks, database writes or remote process control.** All read access is via
the existing provider+network allowlists. No full EVM account transaction history,
internal/native ETH transfers, NFT, DeFi, unrelated networks or exchange↔chain
linkage is certified. Existing user-selected wallet addresses remain private
local configuration, not published to GitHub, CI or OpenBrain.

The Coinbase/Base public RPC may throttle `eth_getLogs`; 80-block slices are
conservative but cannot guarantee availability or eliminate HTTP 429. A provider
can fail to support historical reads. In those cases `PARTIAL` remains correct.
No automated paid RPC subscription or alternative vendor is provisioned.

The new code has no new config flags. Because this is a locally pinned macOS
LaunchAgent, merging to GitHub does **not** automatically deploy it to the Mac.
Deploy only as a reviewed SHA update followed by private smoke checks, healthy
read-only data, local file permissions, watchdog tests and rollback verification.
The first run after deploying can add private evidence and coverage state but
cannot certify historic prior windows.

## Acceptance / tests

```sh
python3 -m unittest discover -s tests -p 'test_history_backfill.py' -v
python3 -m unittest discover -s tests -p 'test_history_coverage.py' -v
python3 -m unittest discover -s tests -p 'test_autonomous_portfolio.py' -v
python3 -m unittest discover -s tests -v
```

Tests use synthetic addresses, source responses and temporary private directories.
Regression must be green on the PR exact-head SHA. An offline PASS **does not**
assert the local Mac is running the updated code or that real Base RPC has
recovered any missing event.

Sources: [Base JSON-RPC](https://docs.base.org/base-chain/api-reference/ethereum-json-rpc-api/eth_chainId),
[Coinbase deposit history](https://docs.cdp.coinbase.com/coinbase-app/track-apis/transactions),
[previous rolling coverage contract](ROLLING_HISTORY_COVERAGE_PL.md).
