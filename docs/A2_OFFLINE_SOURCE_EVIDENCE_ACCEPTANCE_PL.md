# ISL A2 — Offline source evidence and date-alignment contracts

**Status:** isolated Draft PR module, educational research only. This is not a live provider integration, market source certification, or authorisation for orders. `M1/M2/M3` qualification remains `BLOCKED` until independent source and point-in-time checks.

## Included dependency-closed scope

- `scripts/vanguard_xlsx_offline_intake_v04.py` — validates manually supplied original OOXML workbook bytes and NAV columns; cannot confirm actual Vanguard provider identity or rights from file content alone. Synthetic XLSX test fixtures are not copies of original provider files.
- `scripts/reference_archive_calendar_v04.py` — checks SHA-256 receipts, original-source origin, month continuity and exact observation dates for reference NBP/BondSpot records. SHA only confirms consistency with evidence recorded in the provided manifest; it cannot independently attest original publication time.
- `scripts/nbp_bondspot_exact_date_v04.py` — matches exact calendar dates, preserves NBP receipts and fails closed rather than imputing values. This function **can optionally call the public NBP API at runtime** when mismatched dates need new sources and no injected fetcher is provided. It has **no scheduled/provider-running workflow in this PR**, and CI always injects synthetic sources and forbids Python socket connections.
- `scripts/vanguard_nav_to_pln_reference_v04.py` — requires raw original NAV CSV bytes (not arbitrary self-declared XLSX CSV-equivalence) and compatible exact-date original NBP receipts before reference USD-to-PLN matching. This is not executable equity total return or an ETF fill.

Each source and test module is copied byte-for-byte from the research PR #96 branch, preserving exact Git blob SHA. **Dependency discovered in the first CI run:** `scripts/nbp_reference_capture.py` is NOT on `main`, although it is imported by `scripts/nbp_bondspot_exact_date_v04.py`. It has now been included unchanged from the source branch; otherwise this Draft PR would fail during import. The source capture helper can access public NBP HTTPS when invoked outside tests, but CI blocks all Python socket connections. No dependency on the A1 backtester or its tests. Test modules:
`test_vanguard_xlsx_offline_intake_v04.py`,
`test_reference_archive_calendar_v04.py`,
`test_vanguard_nav_to_pln_reference_v04.py`.

## CI contract

`.github/workflows/isl-a2-offline-source-evidence-ci.yml` is run on PR changes, with `contents:read`, `persist-credentials:false`, Python 3.12 and no secrets. All three synthetically constructed test suites execute with `socket.socket.connect`, `connect_ex`, and `socket.create_connection` set to fail. These tests cannot silently fetch missing real quotes through normal Python socket APIs.

The job is not a blanket guarantee against hypothetical subprocess/network usage by future code; changes that add different network transports require new review and additional controls.

## Strict evidence boundaries

1. Exact-date matching is a **data integrity prerequisite**, not proof that the data was available to a prospective strategy at the decision as-of.
2. NBP FX and gold PRICE_ONLY, BondSpot non-tradable index, and Vanguard accumulating NAV are different source classes. They must not be silently promoted to a tradable `GLOBAL_EQUITY_TR_PLN` series.
3. The private original XLSX and raw NAV bytes never enter this repository or Actions artifacts. Research source permissions, redistribution rights, first-publication vintage, and historical PIT remain unverified.
4. No trading, wallet, transfer, broker, database writes, no new schedule, no changes to frozen Vanguard forward-v0.22 evidence or anchored policy v0.23.

## PR split dependency / merge policy

This source-checking module is independent of Draft A1 PR #98. Both A1 and A2 are sourced from broad Draft PR #96. Do not merge PR #96 wholesale after merging isolated modules; plan a dependency-aware replacement of the broad PR so the same Git blobs and workflow schedules cannot be merged twice without review. Other online acquisition modules and provider-probing workflows belong to a separate A2-provider review, not to this offline slice.

**Acceptance criteria:** isolated CI PASS for all three synthetic offline suites, exact eight original Git blobs matched against PR #96, separate code/security review, no original provider price artifacts uploaded, no merged state.

## CI correction record

The initial A2 workflow run failed because the referenced `scripts.nbp_reference_capture` was missing from `main` (module import error); 12 XLSX fixture tests passed before the import errors. This is an **incomplete dependency closure**, not evidence of invalid market data. Corrective action: include the exact source module as the eighth original source/test file and extend the workflow path filter; rerun the entire offline suite. Do not reduce coverage or enable provider downloads to repair this.
