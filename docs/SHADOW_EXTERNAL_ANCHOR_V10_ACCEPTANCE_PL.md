# Investment Strategy Lab — v0.10: evidence-head anchor and tail-truncation detection

**Status: research-only implementation; no production Mac deployment or independent WORM attestation.**

## 1. Why v0.9 alone was insufficient

The v0.9 SQLite ledger validates an ordered SHA-256 chain. If a privileged actor deletes the final entries and preserves the earlier intact prefix, the *shorter* chain remains mathematically consistent. SQLite `UPDATE`/`DELETE` triggers guard normal DML, but may be dropped by privileged access. Neither SQLite nor Git version history proves the record existed at a specific historical time.

v0.10 adds **an independently preservable head anchor**, which identifies both the expected number of entries and the expected head SHA-256. A verifier with a previously pinned anchor checksum can detect truncation or replacement of the anchored prefix, even when the remaining SQLite rows are internally valid.

## 2. Implementation and verification contract

Files:
- `scripts/shadow_external_anchor_v10.py` — verify an existing v0.9 ledger, create a minimal canonical JSON anchor, hard-link it **without overwriting** an old anchor, and read-verify a separately supplied SHA-256 digest.
- `tests/test_shadow_external_anchor_v10.py` — isolated tests for creation, replay, later append, deleted tail, altered history, anchor replacement, invalid checksum, unsupported authority claims and missing evidence.
- `.github/workflows/working-engine-v01-ci.yml` — includes v0.10 offline tests.
- `.github/workflows/github-checkpoint-audit-v08.yml` — uses a real earlier GitHub capture to reconstruct one v0.9 SQLite record, creates a v0.10 anchor and checks it **on the same ephemeral runner**.

Anchor fields include `schema`, `ledger_schema`, `entries`, `head_sha256`, operator-derived UTC timestamp and explicit `false` flags for independently attested time/storage. No market prices, brokerage identifiers, holdings, passwords, orders, wallets or private source observations.

`verify_anchor` first checks an expected SHA-256 supplied by the operator, then the entire SQLite history, then the anchored row's SHA-256. A new append can extend history while preserving the anchored prefix. If the ledger contains fewer entries than the anchor, verification fails closed with `ledger truncated below externally anchored count`.

**Strict claim boundary:** passing the digest to the verifier from the same CI process does **not** make it an independent witness. Its status is intentionally `SUPPLIED_HASH_AND_SQLITE_PREFIX_MATCH_NOT_EXTERNAL_PROOF`. Independent trust begins only after the digest has been retained in a separate, controlled location and later retrieved from there. `trusted_time_verified` and `external_WORM_storage_verified` remain `false`.

## 3. Operating procedure on Mac mini — NOT executed

Use the PR branch only after checking its reviewed SHA and passing CI. The owner needs a persistent owner-controlled directory, with a **separately administered** location for long-term anchor preservation. The following produces a **local staging copy**, not a WORM archive:

```bash
umask 077
BASE="$HOME/Library/Application Support/InvestmentStrategyLab"
mkdir -p "$BASE/ledger" "$BASE/anchor-outbox"

python3 -m scripts.shadow_evidence_ledger_v09 \
  --ledger "$BASE/ledger/shadow-evidence.sqlite3" \
  --append-bundle evidence/shadow/v09/checkpoint-bundle-run-42305280062.json

python3 -m scripts.shadow_evidence_ledger_v09 \
  --ledger "$BASE/ledger/shadow-evidence.sqlite3" --verify

python3 -m scripts.shadow_external_anchor_v10 \
  --ledger "$BASE/ledger/shadow-evidence.sqlite3" \
  --create-in "$BASE/anchor-outbox"
```

Record the printed `anchor_sha256` in a separately retained and access-controlled audit record, and preserve the exact anchor bytes outside the ledger's failure domain. To validate later:

```bash
python3 -m scripts.shadow_external_anchor_v10 \
  --ledger "$BASE/ledger/shadow-evidence.sqlite3" \
  --verify "/path/to/preserved/isl-shadow-anchor-v10-...json" \
  --expected-sha256 "64-character-digest-from-independent-record"
```

Use a verified backup strategy and separately administered, version-protected or immutable storage if operational/forensic immutability is required. These are our project controls, **not claims that SQLite or GitHub provide WORM**. Files in the same mutable home directory do not meet the independent-storage gate.

## 4. Acceptance and what remains open

A successful test on the disposable GitHub runner proves software behavior and reconstruction from actual v0.7/v0.8 evidence. It does not prove multi-week unattended operation, persistence on Mac mini, trusted timestamps, financial source qualification, buy/sell execution readiness or returns.

Next gates:
1. Review PR #96 for merging and release approval; do not auto-merge its dependency chain (#93/#95).
2. Deploy v0.9/v0.10 to a persistent Mac volume **only after a separate reviewed rollout**, with owner-controlled backup and rollback.
3. Independently retain and read back a digest/head anchor outside the CI/repository failure domain. Prove that deleting final rows is detected using that external copy.
4. Continue separate source-rights and total-return-series qualification for M1–M3. Historical performance remains `NOT_RUN`.

## 5. Acceptance evidence — actual GitHub run, 2026-11-07

- [GitHub Actions v0.8+v0.9+v0.10 #42351227610](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42351227610): **SUCCESS**, 10/10 v0.10 tests. The entire Working Engine, v0.7 capture and v0.5 reference workflows also passed on the corresponding code SHA.
- The real audit generated a **one-record** disposable SQLite ledger and the anchor `isl-shadow-anchor-v10-000000001-26cfff7e67648e53.json`.
- Head SHA-256 `26cfff7e67648e53b369a07de2598ff616060f074a84dfd8f5d310d75b210b38`; anchor-file SHA-256 `56ef37ff73f571cff144cad1e0b5a6d955a477bd76a677c577e074cae80c67da`.
- Independently fetched archive artifact `13565902146`: ZIP SHA-256 `4b0d1826b27517cbc4697df4fe79ab0b986f31bc0406be5d6d3d85c06db33a83`, matching GitHub API `digest`. Independently opened ZIP and recomputed SQLite final-row hash; it agreed with the saved anchor and the generation receipt.
- The exact anchor hash and reference SHA values were additionally copied to **OpenBrain_remote build domain** as record `892c4115-181c-4356-8eb2-e0b064d168e1`, separate from this repo/runner. That store declares `mutable=true`; this is **off-run corroboration, not immutable third-party timestamping, WORM or a signed attestation**.
- Latest CI demonstrates correct fail-closed mechanics and one real captured reference receipt. It does NOT demonstrate an owner-controlled Mac deployment, multi-week monitoring or investable source-return series.

## 6. Source evidence — exact claims, not decorative alignment

| Claim | Primary source | What it supports |
|---|---|---|
| SQLite can abort disallowed DML through a trigger | [SQLite: CREATE TRIGGER, section 6 — RAISE()](https://www.sqlite.org/lang_createtrigger.html#the_raise_function) | `RAISE(ABORT,...)` terminates SQL statement; it does **not** make a database tamper-proof. |
| Existing triggers can be dropped by an administrator | [SQLite: CREATE TRIGGER, section 2](https://www.sqlite.org/lang_createtrigger.html) | Triggers are database objects and removable, so privileged access is outside the local defense. |
| Local creation without replacing a target link | [Python 3.12: os.link](https://docs.python.org/3.12/library/os.html#os.link) | Supported hard-link primitive; no entitlement or immutability guarantee. |
| GitHub Actions artifacts have bounded retention | [GitHub: managing Actions settings — artifact retention](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#configuring-the-retention-period-for-github-actions-artifacts-and-logs-in-your-repository) | GitHub permits retention configuration; it is not permanent archival storage. |

**Real financial operations: 0. Neon LAB main, custody, wallet and existing scheduler remain unchanged.**
