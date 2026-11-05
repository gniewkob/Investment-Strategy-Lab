# Working Engine v0.1 — functional E2E acceptance, 2026-11-05

## Scope and verdict

**PASS for one bounded, manually triggered engine cycle using a real Neon
production-derived market snapshot, on an isolated Neon acceptance branch.**
There is no production environment in this project. This is not a live trading engine, a certified
investment strategy or a complete equity/bond backtest. The engine runs one
atomic SQL statement to read market and paper-model inputs, assess the three
alternative models, append research runs, signals and audit entries, then return
one receipt per model. **Zero real operations and zero new paper events.**

Repository branch: codex/working-engine-v01-e2e-20261105 (based on main).
SQL entrypoint: db/working_engine_v01_research_cycle.sql.

Test database:
- Neon project: red-lake-53043722
- Source parent: main (br-shy-voice-badzlf0x)
- Isolated branch: isl-working-engine-v01-acceptance-20261105
  (br-purple-night-ba3e6uwv).
- DB: investment_lab / schema: investment_lab.

The branch was created by copying main at a definite point in time. The cycle
uses only recorded price observations satisfying BOTH
observed_for <= cutoff and ingested_at <= cutoff. The fixed daily cycle cutoff
is 19:00 UTC (previous day's 19:00 UTC if invoked before that time). Later
ingestions do not silently become earlier knowledge. This does not certify
the publisher's original historical release hour or any revised vintage.

## Actual live-source evidence (Neon staging-branch execution)

- UTC cutoff: 2026-11-05 19:00:00Z.
- Eligible price-observation rows at cutoff: **3,777**.
- Latest per-instrument source receipts are embedded in each research_run's
  data_sources JSONB; the SHA-256 fingerprint seals model rules, source
  snapshot, input cutoff, missing series and preexisting paper-event summary.
- Models/version: M1_GLOBAL_EQ / M2_DIVERSIFIED / M3_TACTICAL, all version 1,
  simulation_only, base currency PLN.
- Existing contributions at cutoff: **100 PLN in each alternative model**
  (same hypothetical budget compared in three models, not 300 PLN spent).
- Required monthly PLN total-return series:
  M1 misses GLOBAL_EQUITY_TR_PLN;
  M2 and M3 miss GLOBAL_EQUITY_TR_PLN, PL_BONDS_TR_PLN, GOLD_TR_PLN.
- All three signal verdicts: INSUFFICIENT_DATA, meaning HOLD_CASH.
- First execution: **3 research_runs (COMPLETED as an engine execution),
  3 signal_events, 3 VALIDATION audit_events**. Paper events added: 0.
  Financial operations: 0.
- Exact rerun of the SQL loaded from GitHub returned IDEMPOTENT_REPLAY for
  all three models with **0 new research, signal, audit or paper rows**.
- Independent SQL verification joined research_runs to signals and audits:
  3/3 SHA-256 fingerprints matched; reasons/missing inputs reconstructable.
- After both executions the acceptance branch had 3 research_runs, 6 signals,
  37 audit entries and 3 original contribution-only paper_events.
- Parent main remained unchanged: 0 research_runs, 3 signals, 34 audit entries,
  3 contribution-only paper_events; no paper fills.

## Fail-closed decisions

Engine NEVER issues real account commands. It has no brokerage, wallet,
payment, conversion, order, staking, leverage or funding interfaces.
It also never creates a PAPER_BUY or PAPER_SELL. Even when a total-return
candidate exists, it may at most emit RESEARCH_ONLY; later filled paper events
require verified executable instrument prices and costs in a separate
authorized module. The present run correctly takes no action.

Research_run status COMPLETED denotes successful execution and durable capture;
the separate SIGNAL verdict INSUFFICIENT_DATA denotes insufficient market
evidence. Do not mistake successful execution for a validated investment edge.

The source_prices inventory is a representative latest-per-instrument
snapshot; it does not constitute full historical coverage. Values of
cash_pln_if_no_fills are conditional on no earlier paper fills. No total return
or inflation-adjusted performance is computed without valid sources.

Collision rule: deterministic daily model run_id + input SHA. A same-day
replay with different source/economic input is labelled
REPLAY_INPUT_COLLISION; it does not overwrite or append a conflicting run.
Advancing to a new cutoff permits a new appended snapshot.

## Automated regression

Dedicated CI in .github/workflows/working-engine-v01-ci.yml executes the
same SQL against a disposable postgres:16 service and checks:
- source-ingest after cutoff is not eligible;
- initial insert 3/3/3 and no financial or paper events;
- second identical execution adds no records;
- research/signal/audit input hashes join exactly;
- mutation of an earlier input in disposable test DB causes a collision
  with 0 additional records.

The fixture test drops investment_lab schema **only in disposable localhost
CI PostgreSQL**. It cannot target any Neon hostname. Never reuse the fixture
on main or on the acceptance branch.

## Operational usage (manual, research-only)

Run the complete SQL file using the approved Neon SQL action on the private
laboratory Neon main or its isolated test branch. The acceptance test above
ran on the isolated branch; that does not make Neon main a production system. Read and
inspect the returned persistence_state for each of the three models. Abort if
the result contains REPLAY_INPUT_COLLISION, a missing model, an unexpected
model version or any nonzero paper/financial operations. Verify separately:

- count and fingerprints in investment_lab.research_runs;
- matching signal_event.components.run_id / input_sha256;
- audit_events.record_id / metadata.input_sha256;
- unchanged paper_events count and absence of paper buys/sells.

The canonical Neon main is the private LIVE RESEARCH laboratory, not production.
A recurring research-only cycle is permitted after verifying the runner's
access, evidence receipt, audit and no-financial-operation boundary. The
November 5 acceptance run did not modify Neon main, its permissions,
secrets, schedules or portfolio records.

## What this PASS does NOT mean

- No scheduler/daemon, recurring live ingestion, dashboard or production release.
- No actual paper-trade fill processor or dynamic profit/loss calculation.
- No verified global equity and PLN bond total-return datasets; no M1–M3
  IS/OOS performance comparison, spread, inflation or investment score.
- No certified real-time data delivery SLA or general security sign-off.
- The isolated acceptance branch is a controlled persistence test, not
  the canonical ongoing paper ledger on main.

**Next engineering increment:** connect a recurring research-only trigger
to the canonical live laboratory, refresh real market source captures and add
read-only health/audit replay. Keep all actual and paper fills disabled until
the data and cost evidence required for them are complete.


## Correction of environment labels — 5 November 2026

- GitHub main is the main development line, **not a production release**.
- Neon main is the durable **private LIVE RESEARCH** database, not production.
- Neon acceptance branch is a disposable **test clone** with separate research rows.
- Engine-first roadmap: functional cycle -> repeated live-lab verification -> UX -> production later, only if separately chosen.
- Prior references to a production-readiness approval before running paper research were overly restrictive. Research-only inserts are not production releases; continue to enforce no real finance operations, idempotency and provenance.
