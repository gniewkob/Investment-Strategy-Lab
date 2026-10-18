# Investment Strategy Lab v2 — Sprint 1

Research and **educational simulation only**. No orders, transfers, portfolio execution or trading credentials.

## Scope

* Original Neon production tables stay untouched. Migration `007_data_provenance.sql` is **additive** and must first be tested on Neon temporary branch.
* `price_observation_versions` + `source_documents` provide historical publication vintages and explicit `available_at`.
* `prices_asof(cutoff)` excludes **all unverified legacy** `price_observations` and all later publications/revisions. This is deliberately conservative.
* `pipeline_runs` + `pipeline_run_events` support operational logging. Existing `research_runs` remains distinct: it records model research, not ingestion jobs.
* Offline fixture pipeline demonstrates deterministic input validation, rerun fingerprint, as-of tests and immutable provenance manifest.
* CI workflow runs tests and fixture smoke on push, manual dispatch and a daily schedule. **It does not fetch external sources or write Neon.** Neon connector/least-privilege secrets require separate setup and review.

## Quick start

```sh
python -m unittest discover -s tests -v
python -m src.isl_v2.pipeline --input fixtures/sample.json --output /tmp/isl-sprint1-result.json
```

## Operational acceptance gate

1. Neon temporary branch includes 4 new tables and `prices_asof` function. No destructive production changes.
2. Confirm `SELECT count(*) FROM investment_lab.prices_asof(now())` is 0 **before** verified publication documents are loaded. Legacy data must remain excluded.
3. SQL tests show a date-only publication dated 2026-10-02 is unavailable throughout 2026-10-02 and available from 2026-10-03 UTC.
4. The same reporting month's corrected publication supersedes an earlier vintage only after the correction's actual availability.
5. 14 completed CI/workflow runs and a real alert channel test are required before claiming production autonomy.
6. The system produces **no** live orders and does not claim model predictive skill.

## GitHub deployment

The public repository contains research-only source code and no credentials. Open a review pull request before enabling workflows. Add workflow secrets **only after** separate least-privilege credentials and a deterministic production ETL have been reviewed. No Neon passwords are included in this deliverable.

## Status

Sprint 1 candidate. Only branch-level schema tests and local unit tests are appropriate before production approval. Pipeline currently runs against verified local fixtures (DRY_RUN), not a live scheduled ingestion.

## Wersja 2.0 beta — autonomiczny agent badawczy

Dodano `src/isl_v2/autonomous_agent.py` (deterministyczny research/paper decision engine),
`agent_runner.py` (opcjonalny worker Neon), `agent_cli.py` (offline raport),
`db/migrations/008_autonomous_research.sql` (trwała pamięć agenta),
`.github/workflows/autonomous-research.yml` (scheduler do późniejszego uruchomienia),
`fixtures/autonomous_synthetic.json` i dodatkowe testy.

Szczegóły, granice bezpieczeństwa i lista blokad wdrożenia:
`docs/AUTONOMOUS_AGENT_V2_PL.md`.
**Stan:** testowe środowisko Neon gotowe; produkcyjny worker NIE jest uruchomiony;
uruchomienie wymaga ograniczonej roli i sekretu w GitHub Actions; harmonogram nie jest jeszcze włączony.
