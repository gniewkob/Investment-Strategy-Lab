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

**Updated 19 October 2026:** After explicit user approval, the separate least-privilege historical reader `isl_legacy_history_reader` **was created on the isolated Neon staging branch as NOLOGIN**, using the [reviewed SQL](db/security/legacy_history_reader_STAGING_REVIEW.sql). Independent checks confirm SELECT only on `investment_lab.price_observations`, no writes, unchanged operational-agent ACL, and no corresponding production role. **LOGIN/password/GitHub secret/manual historical workflow have NOT been enabled** and require separate explicit authorization. This documentation change does not authorize those actions.

Original virtual models M1/M2/M3 depend on verified PLN total-return equity/bond reference history; legacy `PRICE_ONLY` spot/reference observations cannot substitute for those indices. Retrospective research remains labelled `UNVERIFIED_HISTORICAL_PUBLICATION`.

## New access status (later 19 October 2026)

After a second explicit user approval, `isl_legacy_history_reader` has **PostgreSQL LOGIN enabled on staging**, but **no password** (`rolpassword IS NOT NULL=false`) and **no GitHub environment secret**. The Neon connector password-reset attempt failed and was independently checked; the role still has historical-reference SELECT-only rights. The manual workflow remains **blocked**. See [safe operator credential bootstrap](docs/HISTORICAL_LOGIN_BOOTSTRAP_PL.md) — never paste secrets into this repository or a chat.

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
