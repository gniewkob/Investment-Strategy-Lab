# Verification report — 2026-10-17 (Neon test branch)

## Environment

- Neon project: `<NEON_PROJECT_ID>`, database `investment_lab`.
- **Temporary branch:** `<NEON_STAGING_BRANCH>` (`<NEON_MIGRATION_BRANCH>`).
- **Production/main:** `<NEON_MAIN_BRANCH>`.
- Prepared migration ID: `26955b3e-286d-4d8c-aa5d-a973be29e7d7`.
- The preparer successfully applied an equivalent compact migration to the temporary branch; no completion/apply to main has occurred.

## Confirmed branch tests

| Check | Observed |
|---|---|
| Legacy rows, production/main | 3711 |
| Legacy rows, temporary branch | 3711 |
| Number of tables, production/main | 16 |
| Number of tables, temporary | 20 |
| Test document publications | Two **synthetic** documents, 2026-09-29 and 2026-10-02 (DAY precision) |
| Test version values | 100 (revision 1), 101 (revision 2), **synthetic** |
| As-of 2026-09-29T23:59:59Z | no visible price |
| As-of 2026-09-30T00:00:00Z | revision 1, price 100 |
| As-of 2026-10-02T23:59:59Z | revision 1, price 100 |
| As-of 2026-10-03T00:00:00Z | revision 2, price 101 |
| Pipeline test | STARTED → SUCCEEDED, rows_received=2, rows_inserted=2, one event |
| Offline Python tests | 15/15 passed |
| Offline fixture execution | DRY_RUN; input checksum produced |

## Acceptance limitations

1. `prices_asof(cutoff)` is **not yet deployed to main**. It will return no records until primary source documents and price revisions are appended with verified publication dates. **Do not auto-backfill legacy 3711 rows with guessed publication timestamps.**
2. `price_observation_versions` intentionally stores revisions separately from legacy observations; chronology enforced by `prices_asof` (computed conservative effective availability). Privilege hardening is still pending — database owners can inspect raw tables.
3. Source-content SHA-256 must be calculated from retrieved source bytes by a future production collector. Tests use dummy hashes and fake URLs on the temporary branch ONLY.
4. No actual scheduled source ingestion or live database integration has been started; GitHub CI is test-only.
5. GitHub project repo does not yet exist among accessible installed repos, and the connector cannot create a repository. Push requires a new private repository.
6. Before a production migration: independent review of schema, rights, backup/restore test, consistency checks and explicit production approval.
7. PostgreSQL schema migration preparation has not been completed; temporary branch stays available for approval/rejection. To apply or discard it, use the paired Neon migration tool rather than manually bypassing its approval workflow.

## Next steps

1. Use existing public GitHub repository, suggested `gniewkob/Investment-Strategy-Lab`.
2. Push this ZIP's content on review branch `sprint1/data-integrity` and run CI.
3. Implement production collector with independently scoped read/write DB roles, real file checksums, retries and run log updates. Until then, no live automation.
4. Review migration in Neon branch and explicitly authorize applying it to `main`.
