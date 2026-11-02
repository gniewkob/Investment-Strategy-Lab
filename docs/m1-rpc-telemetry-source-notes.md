# M1.4 RPC method failure telemetry — engineering evidence

Status: DRAFT, no production rollout. The deployed supervisor/collector on Mac
remains exactly as installed. This PR is not authority to change any service,
provider, read window, retry budget, portfolio, wallet or financial assets.

## Source findings

Five independent Ethereum PARTIAL checkpoints each contain one `http_other`,
5–6 HTTP 200, zero 429, network errors, retries and capacity errors; each
contains one incomplete of two history streams but no stored block gap.
The operator's earlier metadata audit did not capture which RPC method failed
or exact HTTP status. All inferences about `eth_getLogs` remain hypotheses.

## Proposed additive contract

Existing `rpc_diagnostics` V1 per-chain numeric counters are **unchanged**
and continue to satisfy the pinned V3 collector schema. A separate optional,
private `rpc_failure_diagnostics` field is added to future supervisor
`portfolio.json` reports. It has a fixed `SCOPED_RPC_METHOD_FAILURE_METADATA_V1`
mode, an `ETHEREUM_BASE_RPC_ONLY` scope, at most 32 bounded failure events
and an overflow flag. Each event may include ONLY chain id (1/8453),
a source-defined allowlisted JSON-RPC read method, a static failure category,
numeric HTTP status 100–599 or null, 1–3 attempt index, and a retry-policy
eligibility classification. **Eligibility means a code matches the existing
retry policy; it is not proof a retry was performed.**

No RPC parameters, wallet addresses, token contracts, hashes, endpoint URLs,
headers, provider response bodies, exception messages or credentials persist
in this new diagnostic field. The existing `history_failure_categories`
and production RPC error / retry / validation behavior are unchanged.
All new metadata resets at the start of each naturally scheduled cycle.

This additive field is **not** automatically recognized or copied by the
existing installed V3 acceptance collector; it would be available in the
supervisor's owner-private portfolio report only *after a separately approved
supervisor release*. No deployment or runtime integration is implied by this PR.

## Evidence and release gates

New code and tests are review candidates only until exact-SHA CI/macOS tests
and an independent code-security review complete. Before any future deployment:
verify old V1 counters, failure categorization, privacy/retention, immutable
rollback, compatibility with existing collector and watchdog, and explicit
service-owner authorization. Do not adjust G5 acceptance rules or erase the
failed original/recovery ledgers. G6 stays blocked.

Reference: [Issue #80](https://github.com/gniewkob/Investment-Strategy-Lab/issues/80).
