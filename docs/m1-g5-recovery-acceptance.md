# M1.4 G5 recovery acceptance: second window, no historical reset

**Status:** DRAFT / READ-ONLY. This is an independent acceptance decision,
not a revision of the original G3-based G5 result. No financial operations.

## Why this exists

The initial G5 observation had 1,495+ post-G3 samples, 100 unique natural
supervisor checkpoints, 120 PARTIAL and 144 unhealthy observations, plus
one 122.4-second collector gap. Its result is **REVIEW**, not PASS.

Recorded read-only incident evidence:
- 105 Ethereum RPC PARTIAL samples
- 15 Base RPC UNAVAILABLE samples
- 120 coverage failures
- 144 watchdog mismatch samples, overlapping other failures
- 8 distinct natural checkpoints with PARTIAL observations
- collector gap: **2026-11-01 18:16:48 to 18:18:51 UTC**, measured 122.4s
- subsequent one-hour snapshot: 58 samples, zero unhealthy and zero PARTIAL

Those counts identify symptoms; they do **not** prove that the RPC provider,
rate limits, backfill, macOS scheduling, or supervisor caused them.

## Immutable scope and boundary

- Approved candidate V3: PR #87, SHA `ded973833407532ca6095c50577fbdd046cd536c`.
- Deployed collector-only helper: PR #89, SHA `3e868857c60ac211af214c0b00a8a0c0fe68ca4c`.
- Baseline G4/G5 auditor: PR #90, SHA `270f1bb6aa5f9668c73cb233d882bb2d903663b0`.
- This PR #91 is layered on PR #90 **only for code review**; it must not
  merge or redeploy PR #87 or any active macOS services.
- The new fixed boundary is `2026-11-01T18:18:51Z`, just after the known
  collector interruption. No CLI option can move that start forward.
- The original private G3 receipt `g3-result.log` and the entire existing
  `samples.jsonl` remain untouched. Never recreate or touch the receipt
  to change its mtime.

## Acceptance logic

The auditor prints two **separate** results:
1. `historical_g3_based_acceptance`: the original G3-anchored result
   recalculated from all post-G3 evidence. Historical failures remain visible.
2. `recovery_window`: checks **only** samples strictly after the pinned
   recovery boundary, using the exact evaluator from PR #90.

Recovery PASS requires: at least 86,400 seconds after the fixed boundary;
at least 90 unique *natural* checkpoints; 900–1020s cadence; first/last
checkpoint endpoint coverage; all samples passing the actual V3 health
predicate; no PARTIAL, INVALID or other unhealthy samples; no polling gap
>120s; a fresh latest sample; stable runtime identity/launchagent hashes;
known HTTP429 counters; and zero financial-operations evidence. A missing
or unknown source fails closed. Earlier samples cannot be used to satisfy
the new acceptance window.

Two **separate** incident sections (`prior_incidents` and
`recovery_incidents`) group PARTIAL observations by distinct natural checkpoint,
count fixed-schema RPC/source statuses, watchdog mismatches, and coverage
failures, and give bounded UTC timings/gap summaries. The second section
shows why the fixed recovery attempt fails, including recurring RPC incidents.
No credentials, wallet, provider payload, source file paths, raw notes,
or arbitrary ledger data are echoed.

`g6` remains `BLOCKED_PENDING_FINAL_SIGNOFF` even when recovery G5 is
PASS. The result is local **metadata attestation**, not a provider-side
signature, live-process memory attestation, or permission for financial trades.

## Operator procedure (READ ONLY)

Use a **pinned** source snapshot of PR #91 and the unchanged original,
owner-private G3 receipt. Run with Python bytecode disabled:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests \
  -p 'test_m1_g5_recovery_acceptance_readonly.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  -m scripts.m1_g5_recovery_acceptance_readonly \
  --g3-receipt "$ORIGINAL_G3_RECEIPT"
```

The tool returns 0 for PASS or PENDING_WINDOW, 3 for REVIEW, 2 on rejected
input. Neither exit code 0 nor a successful test run alone establishes G5
PASS: inspect `recovery_window.g5_status` explicitly.

Separate live `isolated-after` metadata attestation remains necessary.
Do not use `--once`, restart launchd, reset a checkpoint, suppress a
PARTIAL sample, delete evidence, modify a signature threshold, run
`--recover-v2`, or perform financial transactions to improve the result.
Document any further incident and begin a separately authorized new window
if the recovery window itself fails.

## Release gates

- **G3:** already executed (documented owner receipt), do not repeat.
- **G4:** historically PASS at 2/2 natural cycles; cumulative later evidence
  degraded to REVIEW. Preserve both observations.
- **G5 original:** REVIEW, historical fact.
- **G5 recovery:** PENDING until this independent fixed window proves PASS.
- **G6:** BLOCKED until valid recovery evidence and explicit acceptance.

Reference: [Issue #80](https://github.com/gniewkob/Investment-Strategy-Lab/issues/80).

### Real recovery attempt receipt (2026-11-02)

The initial exact-head Mac validation of PR #91 `17a7a3e0b2d3e0ccfb024800f75e74aab07100ac`
returned **35/35 offline test PASS**, but the actual fixed recovery window
reported **G5=REVIEW** at 76,181s (~21h10m) and 83 natural checkpoints:
1,226 samples, **75 PARTIAL**, **89 unhealthy**, zero >120s collector gaps
and zero failed natural checkpoint intervals, finance invariant PASS.

The initial recovery result is **not** PENDING_WINDOW: the existing unhealthy
samples already disqualify that fixed attempt, regardless of whether 24h
and 90 checkpoints are later reached. Do not conceal them by adjusting
its recovery start, dropping records, or relabeling the original G5 failure.
This new source revision includes post-recovery incident grouping and extra
tests; it requires fresh exact-head test validation and read-only output
before claiming those new diagnostics work on Mac.
