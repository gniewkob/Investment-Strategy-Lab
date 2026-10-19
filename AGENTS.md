# Agent instructions — Investment Strategy Lab

**START HERE:** Read [`docs/SESSION_HANDOFF_PL.md`](docs/SESSION_HANDOFF_PL.md) **in full before proposing or executing any change**. Then read [`docs/HISTORICAL_REFERENCE_BRIDGE_PL.md`](docs/HISTORICAL_REFERENCE_BRIDGE_PL.md), [`docs/OPPORTUNITY_RADAR_PL.md`](docs/OPPORTUNITY_RADAR_PL.md), [Issue #4](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4) and relevant code/tests. This is the durable handoff for new agent sessions, updated 2026-10-19.

## Purpose
Build an **educational, research-only Opportunity & Decision Intelligence lab**. Discover historical market anomalies, test falsifiable hypotheses, document evidence for/against, compare with naive baselines and no-change alternatives. Classifications prioritize **further research**, never recommend purchases/sales or place any trades. A previous experiment used a hypothetical 100 PLN/month budget with three separate virtual models; it is not an authorization to invest real money.

## Non-negotiable invariants
1. **Never interact with real-money execution**, wallets, exchange/broker order APIs, live portfolio rebalancing or financial transfers. Do not generate real-trading instructions or connect actual account credentials. Paper-only and research-only.
2. **Neon production is immutable for this project stage.** Use the explicitly pinned isolated **staging** branch and least-privilege roles. Verify the actual branch/host/role/ACL before any connection; do not grant legacy access to `isl_agent_staging_limited`.
3. **No privilege/role/secret mutation without fresh explicit user authorization**. The SQL under `db/security/legacy_history_reader_STAGING_REVIEW.sql` is **review-only**; tests on disposable PostgreSQL do NOT create a staging Neon role. The dedicated `isl_legacy_history_reader` was NOT present at the early 2026-10-19 snapshot, but was **created later that day on isolated staging as NOLOGIN**, after explicit user authorization. No login/credentials/secret/workflow authorization was given.
4. **Never put secrets, DSNs with passwords, user wallets, private positions, licensed raw price data or private account records into this public repo, GitHub Actions artifacts or logs.** GitHub `research-staging` contains an existing runtime secret for the normal staging research role; do not reveal or repurpose it.
5. **Strict verified TLS** (`sslmode=verify-full` and CA bundle), fixed endpoint/role checks, `READ ONLY` transactions for history export. Preserve boundaries on private holdings tables.
6. **No fictional historical vintages**: a row's `observed_for` date alone does not prove it was available to a model then. Legacy history has `UNVERIFIED_HISTORICAL_PUBLICATION`. Never backdate `retrieved_at` or `recorded_at`. Spot/reference `PRICE_ONLY` is NOT a PLN `TOTAL_RETURN_INDEX` or an executable price.
7. **No auto schedule** without a separate evidence and alerting review. `workflow_dispatch` manually on `main` is the existing pattern. Offline CI does not prove live Neon access.
8. **Do not reinvent** modules already on `main`: radar, non-overlapping validation, evidence ledger, macro/geopolitical context, opportunity pipeline and read-only legacy bridge. Draft PR #1 remains unmerged; check latest HEAD.

## Credential activation update — 2026-10-19 (latest)

After a **second explicit user approval**, executed a fail-closed `ALTER ROLE isl_legacy_history_reader LOGIN` against isolated Neon staging. Direct PostgreSQL verification: `rolcanlogin=true`, `rolpassword IS NOT NULL=false`, SELECT on `price_observations`, no private holdings access, and no administrative flags. The Neon password-reset connector returned an error; separate DB verification confirms **no password was configured**. Do **not** assume PostgreSQL `psql \\password` works on Neon for SQL-created passwordless roles: Neon requires plaintext SQL password input and the initial reset fails; see corrected bootstrap. Neon API/Console-created roles may inherit `neon_superuser`, violating least privilege. Seek provider-supported initial-password handling; any plaintext SQL initialization requires a separate risk review. Neon role metadata may still show `authentication_method=no_login`; treat actual PostgreSQL state and control-plane metadata as not yet reconciled.

**Still blocked:** A trusted interactive operator must set a password without printing it to chat/SQL/query history, and configure the independent `NEON_HISTORICAL_READ_DATABASE_URL` in GitHub Actions Environment `research-staging`. The connected GitHub tool exposes no secret-writing operation. Do **not** invent secret creation, run the bridge, attempt another password reset blindly, or grant any new rights. Follow [credential bootstrap instructions](docs/HISTORICAL_LOGIN_BOOTSTRAP_PL.md) before any manual historical workflow. No production changes.

## Current blocker and first action (updated 2026-10-19)
The separate staging read-only historical-reference role **now exists as NOLOGIN**, after explicit approval and execution of the reviewed SQL. Independent postflight: SELECT only on `investment_lab.price_observations`, no mutations, no schema CREATE, no access to holdings, production role absent, existing journal agent unchanged. The **new blocker is separate approval to enable LOGIN and configure independent secure credentials**; neither has occurred. **Ask the user for fresh, separate explicit authorization** before any login/password/secret operation, then independently recheck ACL and only afterwards consider the existing [manual historical bridge workflow](.github/workflows/legacy-history-research.yml). Do not re-run role-creation SQL, modify production, or enable trading.

## Safe offline verification
```bash
python -m unittest discover -s tests -v
python -m scripts.opportunity_demo_fixture --output /tmp/isl-synthetic.json
python -m scripts.opportunity_research_pipeline --input /tmp/isl-synthetic.json --out-dir /tmp/isl-report
```
The fixture uses **artificial**, not market data. Record actual PR/CI links and update the full handoff after each substantive change.
