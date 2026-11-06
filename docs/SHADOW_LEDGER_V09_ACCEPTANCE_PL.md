# ISL — v0.9 shadow evidence ledger: acceptance and persistence (2026-11-06)

**Scope: RESEARCH ONLY.** No orders, payments, asset transfers, paper fills or live account access.

## Verified actual end-to-end acceptance

- After root-cause correction of `pull_request` temporary merge SHA versus PR head SHA, the v0.7 capture used the PR head identity.
- Live cross-run GitHub API acceptance on PR: [v0.8 run 42305516422](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42305516422) **SUCCESS**. Source capture [run 42305280062](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42305280062), artifact `13545727322`.
- That run independently queried GitHub run/artifact metadata, downloaded the previous capture and produced `GITHUB_API_AND_CAPTURE_MATCHED_NOT_TRUSTED_TIMESTAMP_CERTIFICATE`.
- The v0.9 integration constructed a **minimal evidence bundle** (v0.7 capture, limited GitHub API run/artifact metadata, v0.8 checkpoint) and appended one receipt into disposable local SQLite. Read-back: `entries=1`, `NEW_EVIDENCE`, head SHA-256 `c1947c81a81a2699f59f67f1438eb6950afa1c45e3f34aebc87d62fac604ef66`. Six offline ledger regression tests passed in that same live workflow.
- Exported Actions artifact id `13545961762` (90-day retention), downloaded and separately SHA-256 checked as **`1d4134d00fad8bdcadf1aed5fd5d75fe2a76e33e53fffe7b07fac535daf7646f`**, matching GitHub API artifact `digest`. It contains a 924-byte v0.8 receipt, 3870-byte bounded JSON evidence bundle and a 20480-byte SQLite example database.
- [Full Working Engine CI #42305280176](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42305280176) **SUCCESS**, including six initial v0.9 SQLite tests.
- The source evidence JSON was versioned in Git at `evidence/shadow/v09/checkpoint-bundle-run-42305280062.json` to survive normal Actions artifact expiry **while the Git branch/repository is retained**. The complete source bytes matched their original SHA-256 `4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3`, and the saved bundle reproduced ledger head `c1947c81a81a2699f59f67f1438eb6950afa1c45e3f34aebc87d62fac604ef66`. [Latest full engine CI #42306067897](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42306067897) **SUCCESS**, seven v0.9 tests including this actual archived-bundle regression.

## What append-only means here

`scripts/shadow_evidence_ledger_v09.py` enforces SQLite `BEFORE UPDATE` and `BEFORE DELETE` abort triggers, transactionally appends monotonically numbered entries, cryptographically chains the prior entry SHA-256, rejects conflicting replay for one run/attempt/artifact, and revalidates v0.8 checkpoint + bounded source bundle on every read.

These are **application-level safeguards**, not a legal WORM archive. A privileged DB administrator, filesystem editor, deleted last rows, destroyed file or unbacked-up disk can still bypass or erase evidence. Historical existence is not proven without an externally retained chain-head anchor. A Git commit can preserve hashes but is not itself immutable against privileged history rewrites.

## Safe local operating procedure

The attached Actions artifact can be downloaded from the run page while unexpired; extract the bounded JSON and save it to an owner-controlled persistent location **outside ephemeral CI**.

```bash
python3 -m scripts.shadow_evidence_ledger_v09 \
  --ledger "$HOME/.investment-strategy-lab/shadow-evidence.sqlite3" \
  --append-bundle checkpoint-evidence/checkpoint-bundle-v09.json

python3 -m scripts.shadow_evidence_ledger_v09 \
  --ledger "$HOME/.investment-strategy-lab/shadow-evidence.sqlite3" --verify
```

The Git archived bundle is a **historical API snapshot**, not a live assertion that the source GitHub artifact remains unexpired; the SQLite instance shown in CI is disposable. Do not treat the branch as WORM or assume it survives deletion/rewrite. Use encrypted storage and independently backed-up copies for the database and source bundle. Also keep each accepted `head_sha256` with its capture time in separately administered write-once/version-protected storage. This is a **deployment procedure**, not confirmation that Mac mini persistence or independent WORM anchoring has happened.

## Evidence confidence boundaries

| Claim | Current status |
|---|---|
| Official GitHub run/artifact metadata agreed with captured decision | **PASS**, actual run |
| Archive ZIP SHA-256 matched GitHub's published artifact digest | **PASS**, exact ZIP inspected |
| Full locally generated SQLite record reproduced on read-back | **PASS**, disposable runner |
| Sanitized evidence bundle retained as versioned Git file | **PASS**, conditional on preserving repo/branch history; not WORM |
| SQLite ledger persisted on owner-controlled Mac/offsite storage | **NOT YET**; CI database is disposable |
| Independent trusted-time/TSA attestation | **NOT CERTIFIED** |
| Qualifying equity, bonds, gold PLN TR + legal entitlements | **BLOCKED** |
| Historical investable M1–M3 performance or real trades | **NOT RUN** |

## Authoritative reference

- [GitHub Docs — Actions artifact REST endpoints](https://docs.github.com/en/rest/actions/artifacts): includes run artifact metadata, `digest`, retrieval, expiration and download redirect.
- [GitHub Docs — `pull_request` SHA semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request): `GITHUB_SHA` refers to temporary merge commit; PR head SHA is supplied in the event.
- [GitHub Docs — workflow dispatch requirements](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow): manual dispatch requires workflow on the default branch.

**No changes to Neon LAB main, v0.3 scheduler, Coinbase, wallets, or investment accounts.**
