# M1–M3 working engine: G1-controlled CI integration (2026-11-11)

Source PRs #93 and #95; integration PR #129.

## G1 and provenance

The original `.github/workflows/working-engine-v01-ci.yml` is in the 16-entry quarantined workflow inventory. It remains absent from the integration, and the G1 inventory and `--forbid-present` checks are unchanged. No quarantined workflow is activated by this PR. Instead a separately reviewed, CI-only workflow `.github/workflows/isl-research-engine-postgres-isolated-ci.yml` runs disposable PostgreSQL integration tests with a unique per-run test password, contents:read, no production provider credentials, no schedule and no external writes.

NBP public official-source probes now require `--allow-public-nbp-fetch` on the CLI and an explicitly supplied fetch callback from library callers. They are read-only observations, not original historical PIT timestamps, licensed total-return return series or trading authorization.

The test-only v0.3 21-observation fixture is placed seven calendar days before the cutoff as required by the **unchanged** SQL stale gate (>7 calendar days). No tolerance relaxation.

Acceptance requires new CI on the exact integration commit: G1 quarantine, Linux/macOS, isolated Postgres, read-only NBP, and GitGuardian. No deployment to Neon, broker, wallet, production scheduler, no orders or financial operations are authorized.
