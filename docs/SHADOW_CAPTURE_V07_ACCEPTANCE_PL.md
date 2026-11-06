# Investment Strategy Lab v0.7 — GitHub shadow-capture candidate

**Scope:** educational, read-only decision checkpoint. No trading, account access, portfolio changes, Neon writes, or invented performance.

## Implemented
- `scripts/shadow_capture_v07.py` freezes the decision envelope from v0.5 at the current runner UTC timestamp, binds declared `GITHUB_REPOSITORY`, `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, `GITHUB_SHA` and `GITHUB_EVENT_NAME`, and hashes the complete receipt.
- `.github/workflows/shadow-capture-v07.yml` runs offline tests, refuses hypothetical executable targets, and uploads a bounded JSON receipt as an Actions artifact for 90 days. A weekly default-branch schedule is declared (Monday 06:17 UTC); it cannot run from this PR branch as a default-branch schedule until the workflow is merged.
- Tests reject arbitrary metadata, unsupported events, foreign repository, invalid run IDs, invalid SHA, future-dated capture and nonresearch operation modes.

## Evidence and limitations
This is **NOT** a trustworthy timestamp by itself. Environment fields are declared run context, not signed third-party evidence; SHA-256 guards content integrity, not when it was created. A successful PR workflow is a code-level acceptance result, not an out-of-sample observation.

Receipt deliberately has `github_metadata_independently_verified=false`, `artifact_timestamp_independently_verified=false`, `prospective_timing_certified=false`, `source_rights_independently_certified=false`. The model is explicitly frozen with `series={}`, generating **three HOLD_CASH outputs**, because legitimate global equity/bonds/gold TR series have not been qualified. This is source-readiness auditing, **not a measured strategy return**.

For future prospective evaluation an independent verifier must obtain GitHub run metadata (`created_at`, `run_attempt`, `event`, `head_sha`, `conclusion`) and artifact metadata (`id`, `created_at`, `expired`, `digest` where available) using the official read-only GitHub API; download and hash the actual artifact bytes; match the frozen decision and ensure the artifact existed **before** the forward source observation date. Re-running a job must be treated as a separate attempt; artifacts may expire or be deleted. Neither the API nor retention proves financial data rights or execution costs.

## Next acceptance
1. Verify run and artifact against independent read-only GitHub API response, not just fields in the file.
2. Persist the externally verified receipt into an append-only research evidence ledger with bounded retention/backup.
3. Keep `NOT_EVALUABLE` when source series are missing; only qualified, independent later-month market observations may be evaluated, with no orders or simulated fills.
