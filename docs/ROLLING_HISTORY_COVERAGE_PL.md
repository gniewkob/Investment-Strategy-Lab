# Rolling ERC20 history coverage — permanent partial-history evidence (24.10.2026)

## Why this exists

The private portfolio supervisor previously checked the newest 1,000 finalized
blocks per wallet/chain and reported whether that **single** bounded request was
complete. A prolonged Base HTTP 429 or a sleeping Mac can result in a missing
intermediate block range. A later healthy rolling request does not retroactively
recover those blocks; marking the stream fully healthy would mask the gap.

This change tracks each configured `chain_label_chainId` **within the private
portfolio state** and never equates a successful latest read with complete
continuous history.

## Contract

`scripts.history_coverage.advance(previous, entries, sources)` is pure and
offline. It consumes the existing validated wallet watchlist entries and the
result of the existing supervisor source cycle:

- A complete range is counted only when the source reports `OK`, exactly one
  requested wallet, the expected label/chain, status
  `COMPLETE_REQUESTED_TOKEN_RANGE` and a bounded 1..1000-block window whose
  end equals the finalized source block number.
- A failed/partial observation **does not advance** the last successful end.
- On the next success, if `new_start > previous_end + 1`, a durable gap
  `[previous_end+1, new_start-1]` is recorded. Overlapping or adjacent
  successful ranges do not create false gaps.
- Any recorded gap persists across later successful cycles. There is **no
  backfill** and no automatic gap repair. At most 64 distinct gaps are listed;
  further omissions preserve a sticky overflow flag, never silent completeness.
- Block regression preserves the last successful watermark and produces an
  explicit alert.
- Changing wallet address or token allowlist under the same label resets the
  coverage epoch and creates a one-cycle `HISTORY_SCOPE_RESET` alert. The new
  epoch does not certify the previous scope.
- The private state stores a SHA-256 scope pseudonym rather than a wallet
  address or contract list. This is **not** an authentication or ownership proof.

Supervisor adds `history_coverage` to private `portfolio.json`, a coverage
message in local HTML, and `HISTORY_COVERAGE_GAP`,
`HISTORY_BLOCK_REGRESSION` or `HISTORY_SCOPE_RESET` as applicable.
`health.json` carries these alert codes to the existing independent watchdog.
A historical gap makes the overall report `PARTIAL` even if all current
source calls succeed. Existing known balances and paper positions remain
unchanged and can still be presented with their original source timing.

## Limitations

- This establishes *observed rolling range continuity* only from the first
  complete read for a fixed address/chain/token allowlist.
- It is **not** a full blockchain history, includes no native ETH/internal
  transactions/NFT/DeFi and does not certify Coinbase-to-blockchain linkage.
- The RPC provider's `finalized` claim is not independent consensus evidence.
- Token history may still be rate limited. The change detects coverage loss
  rather than resolving the 429 problem or reconstructing missing transfers.
- A runtime upgrade with pre-existing private portfolio state creates a new
  coverage epoch. Prior monitoring cannot be retroactively certified.
- Rollback preserves the private JSON. Previous code ignores the additive
  `history_coverage` property. On re-upgrade, every missing run may produce
  a gap; this is preferable to falsely claiming complete history.
- Neither `financial_operations`, Coinbase API scopes, CDP, wallet signing,
  payments nor database persistence are changed.

## Verification

```sh
python -m unittest discover -s tests -p 'test_history_coverage.py' -v
python -m unittest discover -s tests -p 'test_autonomous_portfolio.py' -v
python -m unittest discover -s tests -v
```

All tests use synthetic addresses/blocks and injectable fake readers.
No live account, wallet, Neon, payment, signing or transactions are required.
The deployed Mac LaunchAgent continues using its currently pinned checkout
until an **independent, controlled runtime upgrade** is performed. Merging a
PR does not deploy it to the Mac.
