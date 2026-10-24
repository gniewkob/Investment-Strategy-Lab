# Portfolio release canary — local controlled rollout (2026-10-24)

## Purpose and scope

GitHub main contains a private read-only portfolio supervisor, Ethereum/Base rolling gap detection (PR #74) and bounded ERC20 backfill (PR #75). These commits do NOT automatically upgrade the Mac's pinned local LaunchAgents.

The new Python module scripts.portfolio_release_canary provides a strictly read-only local acceptance gate. It makes zero network calls, never reads actual credential contents, does not touch launchd, restarts no process, writes no state, and prints no wallet address, balances, private path or credential. A clean checkout and matching commit alone are not proof of a currently running process.

## Gate A: before a controlled rollout

Run from the actual local Git checkout on the Mac, with a reviewed full 40-character main commit:

    python3 -m scripts.portfolio_release_canary --config /PRIVATE/portfolio-config.json --expected-commit FULL_REVIEWED_SHA --phase before

Substitute the already established local config path without publishing it. Requirements: exact expected HEAD SHA, clean working tree, owned private config/watch/credentials files with 0600 permissions, private state and parent directories with 0700 permissions, expected read-only schema, valid watchlist. The credentials file is stat-checked only, never opened.

READY_FOR_CONTROLLED_READ_ONLY_CANARY means the local metadata and code checkout are suitable for a **controlled read-only canary**, not that the LaunchAgent currently runs the code or that an authenticated Coinbase API call succeeded. This program never updates LaunchAgents.

## Gate B: after a private one-shot/regular run

After the existing supervisor has actually run in the approved local environment:

    python3 -m scripts.portfolio_release_canary --config /PRIVATE/portfolio-config.json --expected-commit FULL_REVIEWED_SHA --phase after

Gate B checks recent local portfolio.json and health.json, consistent timestamps/status/alerts, named source statuses, fixed watchlist scope SHA pseudonyms, validated history coverage counters, and bounded history backfill metadata. Values and addresses are not displayed.

- Exit 0 LOCAL_METADATA_CANARY_OK_NOT_PROVIDER_ATTESTED: fresh, internally consistent, no recorded gap. It does not prove provider source authentication or currently running daemon identity.
- Exit 3 LOCAL_METADATA_CANARY_PARTIAL: fresh metadata, but incomplete observation or remaining historical gap.
- Exit 2 PRIVATE_RELEASE_CANARY_REJECTED: wrong SHA/permissions/schema, stale data or other validation failure. Error details are redacted.

## Independent operator deployment tasks not performed by this checker

1. Verify which actual local checkout and LaunchAgent labels are running; preserve rollback information about code and job definitions. Do not upload keys, private state or wallet addresses.
2. Stop only the intended private portfolio and portfolio-health LaunchAgents while updating pinned code. Keep existing private checkpoint files, wallets and keys untouched.
3. Run Gate A, an actual approved read-only supervisor --once cycle, then Gate B.
4. Validate two consecutive private source cycles and watchdog state, including degraded Base RPC behavior. Keep logs private.
5. Restore the previous approved code and job definition on failure. Retain private history and never silently clear gaps.

This release gate is a local validation aid only, not a replacement for genuine provider checks, full blockchain history, complete P&L or financial execution permissions. Do not enable trading, transfers, seed phrases, paid endpoints or public dashboards to make it pass.

## Test contract

    python3 -m unittest discover -s tests -p 'test_portfolio_release_canary.py' -v
    python3 -m unittest discover -s tests -v

Test fixtures use synthetic accounts in private temp directories; no live Coinbase or Mac connection is exercised.

See docs/AUTONOMOUS_PORTFOLIO_PL.md, docs/BOUNDED_HISTORY_BACKFILL_PL.md and docs/ROLLING_HISTORY_COVERAGE_PL.md.
