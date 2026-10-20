# Investment Strategy Lab

> **Historical analysis can start NOW (20 Oct 2026):** genuine Neon STAGING market-history data contain 3,746 legacy reference price/FX rows across 12 series; descriptive correlation and anomaly diagnostics already ran READ ONLY, independent first-publication PIT remains unverified. EIA officially lists **34 distinct historical STEO PDF/XLSX monthly releases** from Jan 2024 to Oct 2026. [PR #39](https://github.com/gniewkob/Investment-Strategy-Lab/pull/39) merged after **251/251 offline tests + 3/3 disposable PostgreSQL tests**: `scripts/steo_historical_archive.py` exposes an official release-date catalog, manual bounded EIA XLSX capture to operator-selected private local archive, byte SHA-256 receipts, independent offline replay and sheet-name inventory. **Real archived XLSX extraction/forecast-accuracy scores have NOT been executed yet.** Next operator pilot `jan24,jan25,oct26` and evidence-driven parser design; no Neon writes, no change to M1/M2/M3 paper HOLD_NO_CHANGE. [Manual operator guide](docs/STEO_HISTORICAL_ARCHIVE_RESEARCH_PL.md).


> **Research milestone (20 October 2026):** EIA operational backup is **CLOSED / USER-CONFIRMED** after a 6-file Mac mini copy matched 3/3 original HTML SHA-256 and 3/3 manifests; MyDevil sources passed independent offline verification. No paid OVH bucket required for current simulation. [Backup acceptance and precise limits](docs/EIA_BACKUP_ACCEPTANCE_2026_10_20_PL.md). [PR #38](https://github.com/gniewkob/Investment-Strategy-Lab/pull/38) merged (242/242 offline + 3/3 disposable PG integration PASS): read-only `scripts/eia_prospective_archive_research.py` independently reparses archived official HTML+manifest vintages and compares overlapping date/price revisions **only between truly acquired snapshots**. First captures = baseline only, not historical PIT. [Operator offline runbook](docs/EIA_PROSPECTIVE_ARCHIVE_RESEARCH_PL.md). Virtual M1/M2/M3 remain HOLD_NO_CHANGE; zero Neon writes or orders.


> **Actual 3-source EIA private archive now captured (20 October 2026):** operator on MyDevil FreeBSD confirmed **WTI, Brent and Henry Hub** raw original HTML files + timestamped manifests written to a private local POSIX directory with `immediate_independent_replay=true` for all three; WTI passed an additional separate **offline** `verify`. [Actual SHA-256, acquired-at timestamps and limits](docs/EIA_MYDEVIL_ACTUAL_ARCHIVE_RECEIPTS_2026_10_20_PL.md). These **NEW 20 October** captures are real; earlier **19 October CI source requests still had no retained original HTML**. Private local archive is **NOT WORM**. No Neon source/version writes, roles, credentials, schedule or trades. Historical PIT remains unverified; virtual M1/M2/M3 HOLD_NO_CHANGE.


> **MyDevil archive readiness (20 October 2026):** [PR #37](https://github.com/gniewkob/Investment-Strategy-Lab/pull/37) merged after **235/235 offline + 3/3 disposable PostgreSQL integration tests**. New `scripts/eia_archive_storage_preflight.py` inspects an already existing private POSIX archive root **READ ONLY** without logging paths or creating files. This does **not** verify actual MyDevil quota, ZFS restore, persistence or WORM; SSH unavailable in current runtime, so no MyDevil remote check was performed. OVHcloud Object Storage Object Lock is a candidate independent WORM backend, **not configured or approved**. Live Neon versioned EIA source/price rows 0, writer role absent. [Read-only/MyDevil + OVH plan](docs/EIA_MYDEVIL_OVH_ARCHIVE_READINESS_PL.md).


> **Source-byte provenance upgrade — [PR #36](https://github.com/gniewkob/Investment-Strategy-Lab/pull/36) merged (19 October 2026):** Official EIA original HTML can now be retained in an operator-selected **private local POSIX archive**, keyed by raw SHA-256, with a distinct exact-time acquisition receipt and independent offline replay/semantic SHA. **228/228 offline + 3/3 disposable PostgreSQL tests passed**. Local no-overwrite is **NOT certified WORM**; no historical live EIA bytes have been archived, no Neon source/version writes, no new roles. [Operator capture/verify and limits](docs/EIA_ORIGINAL_HTML_ARCHIVE_PL.md). Virtual models remain HOLD_NO_CHANGE.


> **Actual live EIA receipts completed (2026-10-19):** [WTI ↔ STAGING 695/695 exact matches](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330376388), **0 missing and 0 price mismatches**, historical first-660 SHA unchanged; [all three official EIA snapshots](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330400127) validated via public HTTPS (WTI 285, Brent 289, Henry Hub 283), original HTML and semantic SHA recorded. **No Neon write**: EIA versioned docs/observations both 0, EIA writer role absent. Current-source validation ≠ original historical PIT publication proof; `MARKET_DATA_NOT_READY`, paper M1/M2/M3 `HOLD_NO_CHANGE`. [Complete dated evidence](docs/EIA_LIVE_RECEIPTS_2026_10_19_PL.md).


> **EIA source integrity hardening (19 October 2026):** [PR #33](https://github.com/gniewkob/Investment-Strategy-Lab/pull/33) merged: original HTML SHA and separate canonical date/price SHA, 14-day source freshness rejection, strict NO UPDATE/DELETE/TRUNCATE writer ACL. **210 offline + 3 disposable PostgreSQL tests passed**, main CI green. Actual Neon STAGING READ-ONLY check still 695 WTI, 706 Brent, 3 pre-existing documents and 3 pre-existing version rows; dedicated EIA writer role absent. No new live EIA↔Neon manual 695/695 source receipt, no live versioned ingestion, and no verified historical first-publication vintages. Research-only HOLD_NO_CHANGE. [Handoff](docs/SESSION_HANDOFF_PL.md).


> **Versioned EIA source ingestion core — main, 19 October 2026.** [PR #32](https://github.com/gniewkob/Investment-Strategy-Lab/pull/32) merged: 204/204 synthetic offline and 2/2 isolated PostgreSQL 16 integration tests PASS. The official-source CLI is public HTTPS **dry-run only**; the source/version SQL writer requires a new dedicated least-privilege STAGING role which **does not yet exist** in Neon. No source/version rows were written: WTI 695 legacy, Brent 706, versioned 3 source docs + 3 synthetic price fixtures unchanged. No verified original historical PIT vintages, `MARKET_DATA_NOT_READY`, M1/M2/M3 `HOLD_NO_CHANGE`. [Operator/security review](docs/EIA_VERSIONED_INGEST_GATE_PL.md).


> **Current 695-day WTI audit on main (19 October 2026):** [PR #31](https://github.com/gniewkob/Investment-Strategy-Lab/pull/31) merged after **195/195 offline tests**. The manual-only [post-import WTI EIA ↔ Neon STAGING receipt](docs/WTI_POSTIMPORT_RECEIPT_PL.md) checks 695 exact source/stored date+price matches, immutable original 660-row fingerprint and real 2026-10-19 backfill timestamps. **The live post-import job has not yet been dispatched**; PR CI is not evidence of actual source agreement. No verified historical individual publication vintages or PIT import, `MARKET_DATA_NOT_READY`, M1/M2/M3 `HOLD_NO_CHANGE`.

> **19 October 2026 — STAGING legacy WTI coverage FIXED (not PIT).** With explicit user authorization, 35 missing EIA WTI current-archive reference rows were inserted into the isolated STAGING legacy `investment_lab.price_observations` table. Independent SQL postflight: **695/695 WTI days**, all 35 new prices match the official EIA table, 0 mismatches, original 660-row digest unchanged; Brent 706 unchanged, `price_observation_versions` and `source_documents` remain only the three old synthetic fixtures. **Historical publication vintages still unverified**; `MARKET_DATA_NOT_READY` and M1/M2/M3 `HOLD_NO_CHANGE`. The earlier frozen receipt (expected 660/35 gap) is now ARCHIVAL; do not rerun as a current-state test. [Full handoff](docs/SESSION_HANDOFF_PL.md) / [Issue #22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6274907188).


**Educational, research-only Opportunity & Decision Intelligence.** Reproducible market-data validation, historical anomaly research, falsifiable hypotheses, evidence-for/against and **hypothetical** portfolio comparisons. **No actual trades, brokerage/exchange execution or investment recommendations.**

## For a new ChatGPT / code agent session

**Read [`AGENTS.md`](AGENTS.md), then the complete [session handoff](docs/SESSION_HANDOFF_PL.md).** It contains current verified project state, architecture, Neon staging vs production, GitHub CI runs, key decisions, remaining blockers and a ready-to-reuse continuation prompt.

Supporting documentation:

- [Opportunity Radar and retrospective research](docs/OPPORTUNITY_RADAR_PL.md)
- [Legacy-history read-only bridge and role authorization](docs/HISTORICAL_REFERENCE_BRIDGE_PL.md)
- [Issue #4 — full implementation history and backlog](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4)
- [Draft PR #1 — original full beta package, **not merged**](https://github.com/gniewkob/Investment-Strategy-Lab/pull/1)

## Verified state (19 October 2026)

The repository already contains **Opportunity Radar**, non-overlapping research evaluation, an evidence decision ledger, macro/geopolitical context validation, an aggregate-only historical research bridge, Neon staging preflight, data audit and manual educational research canaries. Real Neon staging read-only/PIT and full research cycle smoke tests have succeeded, but **market-data readiness remains blocked**.

**Updated 19 October 2026:** After explicit user approval, the separate least-privilege historical reader `isl_legacy_history_reader` **was created on the isolated Neon staging branch as NOLOGIN**, using the [reviewed SQL](db/security/legacy_history_reader_STAGING_REVIEW.sql). Independent checks confirm SELECT only on `investment_lab.price_observations`, no writes, unchanged operational-agent ACL, and no corresponding production role. **LOGIN/password/GitHub secret/manual historical workflow have NOT been enabled** and require separate explicit authorization. This documentation change does not authorize those actions.

Original virtual models M1/M2/M3 depend on verified PLN total-return equity/bond reference history; legacy `PRICE_ONLY` spot/reference observations cannot substitute for those indices. Retrospective research remains labelled `UNVERIFIED_HISTORICAL_PUBLICATION`.

## New access status (later 19 October 2026)

After a second explicit user approval, `isl_legacy_history_reader` has **PostgreSQL LOGIN enabled on staging**, but **no password** (`rolpassword IS NOT NULL=false`) and **no GitHub environment secret**. The Neon connector password-reset attempt failed and was independently checked; the role still has historical-reference SELECT-only rights. The manual workflow remains **blocked**. See [safe operator credential bootstrap](docs/HISTORICAL_LOGIN_BOOTSTRAP_PL.md) — never paste secrets into this repository or a chat.

## 19 October — Historical credentials initialized on staging

After user's approval and rediscovery of the successful 18 October bootstrap from [Issue #3](https://github.com/gniewkob/Investment-Strategy-Lab/issues/3), server-side SQL generated an undisclosed random initial password for `isl_legacy_history_reader`. Direct Neon PostgreSQL checks now confirm `LOGIN=true`, **password present=true**, SELECT only on the historical-reference table, no writes/private holdings and production unchanged. **Still pending:** reset this unknown bootstrap password to a private final password in Neon Console, then configure the separate GitHub Environment secret `NEON_HISTORICAL_READ_DATABASE_URL`. No historical workflow, schedules or trades have run. Follow the [operator bootstrap/reset guide](docs/HISTORICAL_LOGIN_BOOTSTRAP_PL.md). Previous status paragraphs are retained as chronological snapshots.

## First live historical-reference research bridge — PASS (19 October 2026)

The manual staging-only GitHub [historical-reference run #39241685091](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39241685091) completed successfully with the dedicated historical reader credentials. The aggregated [research report artifact](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39241685091/artifacts/12181127705) was inspected: 3,711 reference observations, 8 analyzable series, 62 retrospective anomaly candidates, 47 nonoverlapping research windows, four **investigation-only** series (Brent, WTI, Henry Hub, ETH). No validated macro events or predictive performance; historical publication vintages unverified. M1/M2/M3 remain `HOLD_NO_CHANGE`; zero orders, database writes or allocation changes and no recurring schedule. No new credentials or resets needed. Data provenance/benchmarks are the next blockers, not the already-working staging secret. Prior status paragraphs are chronological and may describe earlier blockers.

## Architecture

- **Python:** deterministic historical validation, anomaly detection, evidence grading and hypothesis checks; LLM may assist with *explanations*, not invent source evidence.
- **Neon PostgreSQL:** versioned point-in-time sources, append-only research journal, separate legacy historical reference data.
- **GitHub Actions:** offline regression tests and **manual-only** staging checks; no unattended investment-related schedule.
- **Artifacts:** research-only JSON/Markdown aggregate diagnostics, fingerprints, caveats and benchmark evidence. Never publish raw licensed prices or private positions.

## Security

This repository is **public**. Never commit passwords, DSNs containing credentials, tokens, seed phrases, wallets, account data, private portfolio exports or licensed raw datasets. Production Neon is outside the permitted test scope. Never widen the journal agent role or apply the staged historical-reader role SQL without fresh, explicit approval. Preserve verified TLS, least-privilege ACL and careful publication chronology.

## Safe quickstart (offline, synthetic data)

```bash
python -m unittest discover -s tests -v
python -m scripts.opportunity_demo_fixture --output /tmp/isl-synthetic.json
python -m scripts.opportunity_research_pipeline --input /tmp/isl-synthetic.json --out-dir /tmp/isl-educational-report
```

The sample data above are **entirely artificial**. Passing the offline tests is not proof of forecasting skill or production readiness. Consult the full [session handoff](docs/SESSION_HANDOFF_PL.md) before continuing.
