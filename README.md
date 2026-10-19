# Investment Strategy Lab

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

The **next gate** is to obtain explicit approval for a separate least-privilege read-only **staging** historical-data role. Its [SQL review proposal](db/security/legacy_history_reader_STAGING_REVIEW.sql) and CI exist, but the role had **not been created on Neon** at the last verified snapshot. No credentials or role changes are implied by merging this repository.

Original virtual models M1/M2/M3 depend on verified PLN total-return equity/bond reference history; legacy `PRICE_ONLY` spot/reference observations cannot substitute for those indices. Retrospective research remains labelled `UNVERIFIED_HISTORICAL_PUBLICATION`.

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
