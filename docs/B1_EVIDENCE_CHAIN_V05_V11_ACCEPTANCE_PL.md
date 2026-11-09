# ISL B1 — evidence chain v0.5/v0.7–v0.11: isolated acceptance

**Status:** draft integration slice stacked on [A2 Draft PR #99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99), **not** on merged main. Scope is educational paper research and forensic receipt integrity, never transaction or production-authorization evidence.

## Provenance and dependency boundary

The following modules were copied byte-for-byte from research Draft PR #96, preserving their Git blob SHAs:
1. `shadow_decision_engine_v05.py` + test — non-executable HOLD_CASH fail-close source gate; its test needs `reference_archive_calendar_v04.py` from A2.
2. `shadow_capture_v07.py` + test — prospective **declared** GitHub run capture, not independently authenticated metadata.
3. `github_checkpoint_verify_v08.py` + test — validates independently supplied GitHub run/artifact metadata *if the caller separately fetched it*; receiving local JSON alone does not establish API identity or trusted timestamp.
4. `shadow_evidence_ledger_v09.py` + test — local SQLite hash-chain receipts and tamper checks.
5. `shadow_external_anchor_v10.py` + test — independently pinned SHA comparison on supplied files, not independent time attestation.
6. `shadow_backup_restore_v11.py` + test — private snapshot, checksum, isolation and controlled restore drill.

The original archived fixture `evidence/shadow/v09/checkpoint-bundle-run-42305280062.json` is copied without modification; its **raw file SHA-256 must remain**
`4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3`.
Archive test checks deterministic ledger head and archived bundle identity. No change to original GitHub run IDs or v0.22 frozen Vanguard receipts.

**Stacking:** base branch is `codex/isl-source-evidence-v04-offline-20261108` (Draft PR #99); this supplies `scripts/reference_archive_calendar_v04.py`. After A2 merges, rebase/retarget must be reviewed with the exact SHA and checks; don't merge a stacked PR directly onto main before the base is integrated. PR #98 is independent, no source reuse from it.

## Security properties and limitations

- SQLite trigger rejects accidental UPDATE/DELETE and hashes detect multiple changes, but DB owner/root can replace a local SQLite file, delete tail entries, rewrite entire hash chain, or change metadata. **This is not cryptographic WORM, not immutable storage, not external trusted-time certification.**
- `v0.10` external anchor can detect deletion/tampering only when **an authenticated, independently retained prior anchor** is available; a freshly computed anchor from the same compromised filesystem proves nothing independent.
- Raw artifacts may contain source-derived information, but are evidence candidates. No authorization is derived from SHA alone.
- No workflow schedule, live GH API fetch, provider access, wallet/broker integration, trade, transfer or Neon DB; original source rights/PIT/tradability remain unverified.
- The v0.7 capture workflow from #96 is **not included** in B1. Offline tests use synthetic run metadata, not GitHub-origin claims.
- `v0.12` Mac installation and `v0.13` offsite export are deliberately outside B1: they will be tested separately as B2 because they have filesystem/path and host-specific security consequences.

## CI and review gates

The standalone `.github/workflows/isl-b1-evidence-offline-ci.yml` runs on both ubuntu-24.04 and macos-15 using Python 3.12. It checks the real original archived bundle raw SHA, runs the six source/test suites, and forbids normal Python socket connections during testing. No credentials and `persist-credentials:false`. Green CI demonstrates implementation behavior on synthetic fixtures only, **not** independent provider attestation.

Do not combine/merge #96 and B1 (or #99) independently: overlapping original files need explicit reconciliation. Preflight also requires review of local SQLite resource lifecycle, original v0.9 archive, overwrite protections, permissions, and backup restore semantics before any real private filesystem rollout. Zero financial operations.
