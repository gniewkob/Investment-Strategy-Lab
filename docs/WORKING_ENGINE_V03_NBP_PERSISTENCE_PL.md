# Working Engine v0.3 — persisted M1/M2/M3 context, 6 November 2026

## Functional objective

The private Investment Strategy Lab has NO production environment.
v0.3 brings already verified NBP descriptive 5/20-observation changes
and the full virtual-contribution event ledger into the same immutable
research record as the model result. Previously, these NBP metrics were
available only as a separate read-only query, unlinked to research_runs.

New files:
- db/working_engine_v03_research_cycle.sql — atomically records
  research_runs, signal_events and audit_events for all three models;
- db/working_engine_v03_health_READONLY.sql — recomputes the same
  as-of input and checks reproducibility hash, persisted NBP context,
  full virtual ledger, signal and audit; writes nothing.

The full market SHA-256 now includes source_url; the paper-event ledger
has its own SHA-256 and records event IDs, times, kind, amount and fee.
Immutable v03 run/signal identifiers keep earlier v0.1/v0.2 results
untouched. Historical source references are strictly ingested_at and
observed_for <= the cycle cutoff, and only officially sourced NBP
references appear in the descriptive context.

## Verified real-source integration — ISOLATED Neon branch ONLY

Project red-lake-53043722, test branch br-purple-night-ba3e6uwv,
DB investment_lab; cutoff 2026-11-05 19:00 UTC.

- Eligible as-of price records: 3,777.
- Models: M1_GLOBAL_EQ, M2_DIVERSIFIED, M3_TACTICAL, version 1;
  each model has its own alternative 100 PLN virtual contribution.
- First run: 3 research_runs, 3 signal_events and 3 validation audits;
  0 paper events created; 0 financial operations.
- Same-cutoff replay: 3 IDEMPOTENT_REPLAY, zero new records.
- Independent post-run readback: 3/3 matching market input hash,
  complete paper-ledger hash, signal input hash and audit input hash.
- Independent v03 read-only health: ENGINE_OK 3/3; one signal
  and one audit per model; zero paper fills.
- Market-row SHA-256:
  44b7dddb0286552d90a3137a77ee259e69b4b8638278351caeb337ae2fdeac7d.
- NBP context at cutoff:
  REFERENCE_INCOMPLETE_AT_CUTOFF, because last NBP as-of observations
  are dated 2026-10-16. The current LAB database has newer NBP values,
  but they were ingested AFTER the historical cutoff and do not leak
  into the historical model result.
- Descriptive reference 5/20-observation changes:
  EURPLN -0.2604% / +0.0642%;
  USDPLN -0.4997% / +2.1817%;
  NBP gold (PLN per gram) +0.1464% / -1.3811%.
- Model verdicts: INSUFFICIENT_DATA / HOLD_CASH for all three.
  NBP mid FX rates and reference gold are NOT equity/bond total
  return and are not executable portfolio-fill prices.

## Automated regression

GitHub Actions:
https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42197735658

SUCCESS: 39/39 tests (5 NBP source, 5 NBP SQL compiler,
4 scheduled-source controls, 25 PostgreSQL integration tests).

New tests validate successful atomic persistence and exact replay,
no-lookahead for NBP, 5/20-observation metrics, rejection of
non-official NBP URLs, full paper-event fingerprinting, and
read-only health detecting a changed historical price-provenance URL
or a changed virtual-contribution event timestamp.
A nontrading and read-only health check remains enforced.

## Boundaries and pending work

- Neon main is the private live research laboratory, NOT production.
  It was NOT modified by this v0.3 iteration.
- Active scheduled model job stays pinned to v0.1, not v0.3.
- PR #95 is Draft, unmerged.
- First natural GitHub scheduled NBP ingestion (expected 7 November)
  and two separate new-day scheduled model cutoffs remain PENDING
  until verified from independent GitHub/Neon records.
- No UI, production setup, brokerage calls, wallets, financial
  transactions, additional paper contributions or fills.
- This confirms a functional persisted research-evidence engine,
  NOT complete source total-return coverage or proven investment
  performance, profitability, or predictive alpha.


## LAB-main activation on 2026-11-06 — confirmed

After 39/39 tests passed in GitHub Actions run 42198032915,
Working Engine v0.3 was invoked in the private LAB Neon main:
project red-lake-53043722, branch br-shy-voice-badzlf0x,
database investment_lab. This is NOT a production release.

Both SQL files were fetched from immutable repository commit
3072044c25958774930ddd697aadbb0fa282869b:
- db/working_engine_v03_research_cycle.sql
  Git blob SHA d59e2cf07773039235dab242c641c8c5f266e10a
- db/working_engine_v03_health_READONLY.sql
  Git blob SHA 5bd9cf7781a7b492e16b34e14e59ee889255f88a

Preflight checked that the research script inserts only into
investment_lab.research_runs, signal_events, and audit_events,
and cannot write to paper_events or execute financial orders.
Before the run Neon main contained 3 research runs (all v0.1)
and 0 v0.3 runs.

Observed live-laboratory SQL receipts for cutoff 2026-11-05
19:00 UTC (3,777 eligible historical market records):
- New v0.3 research_runs: 3, new signals: 3, new audit rows: 3;
  exactly M1_GLOBAL_EQ, M2_DIVERSIFIED, M3_TACTICAL.
- All three verdicts: INSUFFICIENT_DATA / HOLD_CASH;
  NBP research context: REFERENCE_INCOMPLETE_AT_CUTOFF, since
  the later NBP imports were not yet known at this cutoff.
- Same-statement replay: IDEMPOTENT_REPLAY for each model;
  zero new research rows, signals, or audit rows.
- Independent live main health script: ENGINE_OK 3/3, exactly
  one matching signal and one matching audit per model,
  recorded input SHA-256 matches independently recomputed
  input SHA-256 3/3.
- After activation: 6 total research_runs, including 3 v0.3;
  3 preexisting contribution-only paper_events; 0 paper fills;
  price_observations unchanged at 3,820; real operations 0.

The existing active daily automation "Surowce i geopolityka"
(ID 6ad3d88620708191a2feb6b7a44bf253) was updated
successfully through Automations to the immutable v0.3 commit
and the exact two Git blob IDs above. Its original daily schedule
and its NBP capture/ingest instructions were preserved.
The task will now execute v0.3 research and independent v0.3
health verification when it next runs. No new automation was
created, and no trading or paper-fill operations were enabled.

**Acceptance boundary:** this proves one manually executed
live-LAB v0.3 cycle and a verified idempotent replay.
It is NOT evidence of a naturally scheduled v0.3 execution.
The first scheduled NBP GitHub source capture and two separate
new daily research cutoffs still need real execution/audit proof.
