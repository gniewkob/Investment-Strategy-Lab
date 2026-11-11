# C1 — Research-only M1–M3 controller and chronological journal

**Date:** 2026-11-09. **Status:** stacked Draft PR on [B1 #100](https://github.com/gniewkob/Investment-Strategy-Lab/pull/100), itself stacked on [A2 #99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99). The independent A1 backtester #98 and B2 host installer #101 are not prerequisites.

## Source-based implementation scope

All **10 Python files** are unchanged copies from the broad research Draft PR #96 with preserved Git blob SHA:
- `shadow_forward_evaluation_v05.py` and test: validates a later synthetic/reference period against an earlier frozen hypothetical target, never treats it as a trade or investor P&L.
- `shadow_journal_v06.py` and test: ordered local research evidence chain. No trusted timestamp or external attestation.
- `research_decision_controller_v15.py` and test: uses the frozen v0.5 source quality gates; M3 momentum-regime change needs **two consecutive provided monthly snapshots** with unchanged prior history. No independent PIT assumption.
- `research_decision_pipeline_v16.py` and test: assembles read-only decisions including replay of original archived v0.9 HOLD_CASH evidence.
- `research_forward_journal_v17.py` and test: chronological, source-gated research-cycle journal and optional strictly later forward evaluation.

**Evidence dependency:** original `evidence/shadow/v09/checkpoint-bundle-run-42305280062.json` is from B1, pinned raw SHA-256 `4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3`. Its replays stay `HOLD_CASH` because qualified source coverage is missing. This is not an independently time-attested monthly market source observation.

## Acceptance and safety boundaries

- Dedicated `.github/workflows/isl-c1-decision-offline-ci.yml` matrix Ubuntu 24.04 + macOS 15 / Python 3.12 runs 5 original test modules, expected **53 tests per platform**, with Python socket connect calls blocked.
- The same pinned original archived bundle SHA is checked before tests. `persist-credentials:false`; no Neon, exchange, wallet, trading API, broker, external provider access, run scheduling or file access outside the runner's isolated test workspace.
- Synthetic test inputs can validate deterministic logic, fail-closed gates, chronology and no-lookahead. They do **not** prove investment performance, source rights, independent historical PIT, authentic external publication time, or forward OOS returns.
- The v0.5 shadow engine's M1/M2/M3 `HOLD_CASH` remains the correct outcome for absent original qualified total-return source series. Successful hypothetical scenario tests cannot change that.
- No real account, order, asset transfer, or production authorization can be derived from technical PASS. The actual source certification and frozen Vanguard forward contract v0.22/23 remain untouched.

## Review / merge sequence

A2 #99 → B1 #100 → **C1**. B2 #101 branches separately from B1 and is not an input to decision logic. C2 (v0.18 real-reference gateway and v0.19 licensed-ACWI offline intake) is planned **on C1**; it must not be confused with independent verified market data. All new PRs are Draft. No merge, rebase, or source hash rewriting.

The source PR #96 overlaps the split and must not be merged wholesale once the dependency-closed slices are integrated. Explicit diff reconciliation and branch-protection review are mandatory.
