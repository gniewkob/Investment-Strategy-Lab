# Investment Strategy Lab — GitHub checkpoint verifier v0.8

**Status:** PR-only implementation. Independent evidence intake is present, but prospective performance, trusted time, and independent source entitlement remain **NOT CERTIFIED**.

## Purpose

The v0.7 capture artifact contains an immutable fingerprint but supplies its own timestamps and workflow context. The new v0.8 process uses a *separate* authenticated GitHub Actions invocation to read the original run and artifact metadata and then download the original capture file. This provides a materially stronger identity/chronology cross-check than accepting the capture's self-declarations.

Modules:
- `scripts/github_checkpoint_verify_v08.py`: no-network validator of a v0.7 capture, independent run metadata, artifact listing, and a declared cutoff.
- `tests/test_github_checkpoint_verify_v08.py`: synthetic tampering, run mismatch, fork/workflow mismatch, artifact expiration and delayed-cutoff tests.
- `.github/workflows/github-checkpoint-audit-v08.yml`: `pull_request` runs tests only; `workflow_dispatch` can fetch an earlier capture via the GitHub API and compare it.

## Verified envelope

The verifier requires:
- Successful, completed original run, exact `run_id`, `run_attempt`, `head_sha`, event, same repository and expected capture workflow path.
- A unique, unexpired artifact for that exact run/attempt, with matching GitHub `workflow_run` identity and SHA.
- Chronology `run.created_at <= run_started_at <= capture.captured_at <= run.updated_at < cutoff`, plus `capture.captured_at <= artifact.created_at < cutoff`.
- Recomputed SHA-256 of the downloaded capture and frozen decision. Three `HOLD_CASH` states, zero orders, zero fills, zero DB writes.
- A cutoff strictly later than the original run and artifact. The cutoff is caller-supplied: **it is not independently trusted**.

Read-only GitHub API references:
- [Get a workflow run](https://docs.github.com/en/rest/actions/workflow-runs#get-a-workflow-run)
- [List workflow run artifacts](https://docs.github.com/en/rest/actions/artifacts#list-workflow-run-artifacts)
- [Download a workflow artifact](https://docs.github.com/en/rest/actions/artifacts#download-an-artifact)

## Operation after workflow is available on the default branch

Dispatch `ISL v0.8 independent GitHub checkpoint audit` with an existing completed v0.7 capture run ID and an ISO 8601 UTC cutoff later than that run's artifact date. The workflow uses read-only Actions permissions, obtains run and artifact metadata through GitHub's own REST API, downloads the matching earlier artifact using `gh run download`, and writes only a bounded audit receipt (no raw market data). Never use a future arbitrary cutoff as evidence a market observation was available later.

**Security caveats:** the GitHub API is an operational metadata source, not a qualified timestamping authority. The verifier cannot prove a file was not replaced within the trusted GitHub workflow boundary; it also does not independently authenticate the GitHub artifact ZIP against GitHub's archive digest. The downloaded file's local fingerprint proves content consistency only. A reusable signed or externally anchored digest + source evidence ledger is still necessary.

## Explicit limits

- The v0.8 output always uses `GITHUB_API_AND_CAPTURE_MATCHED_NOT_TRUSTED_TIMESTAMP_CERTIFICATE`, `artifact_bytes_externally_authenticated=false`, `trusted_timestamp_certified=false`, `prospective_performance_verified=false`.
- No qualifying GLOBAL_EQUITY_TR_PLN, PL_BONDS_TR_PLN or GOLD_TR_PLN. The real historical M1/M2/M3 backtest stays `NOT_RUN`.
- No scheduler, Neon LAB, custody, Coinbase, wallet, or account changes.
