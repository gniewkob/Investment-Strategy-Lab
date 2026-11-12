# ISL — Zod wallet dependency release gate (2026-11-12)

**Scope:** security advisory evidence and static release preflight, **not** an authorization to connect, trade, transfer, sign or otherwise use any wallet. Related [issue #146](https://github.com/gniewkob/Investment-Strategy-Lab/issues/146).

## Verified dependency and vendor status

The currently committed `wallet-portal/package-lock.json` resolves:

```text
@base-org/account@2.5.13
  -> @coinbase/cdp-sdk@1.59.0 (zod ^3.25.76)
    -> zod@3.25.76
```

Official [GitHub advisory GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5) identifies versions below 4.6.6 as affected by uncontrolled resource consumption. There is no listed fix on the Zod 3 branch. As inspected on 2026-11-12, official Coinbase `@coinbase/cdp-sdk@1.62.0` **still declares** `zod: ^3.25.76`; [Coinbase #863](https://github.com/coinbase/cdp-sdk/issues/863) is open. The upstream [PR #867](https://github.com/coinbase/cdp-sdk/pull/867) proposes a dual Zod 3/4 dependency range but is **open/unmerged**. Do not misidentify upstream #864 as this vulnerability; it is a separate bundler issue.

## Implementation — fail-closed static lockfile gate

`node wallet-portal/security-zod-gate.mjs` (or `npm --prefix wallet-portal run security:check`) is an **offline** check of the committed lockfile. It:

- verifies the pinned package dependency graph is present, including `@base-org/account` and `@coinbase/cdp-sdk`;
- requires an upstream SDK dependency declaration that *allows Zod 4* (a Zod 3-only declaration remains blocked even if a lockfile is manually forced to 4);
- rejects every installed `node_modules/zod` version earlier than `4.6.6`, any nested vulnerable copy, unknown or prerelease versions, or missing metadata;
- emits a machine-readable status `BLOCKED` (exit **2**) or `PASS_STATIC_LOCKFILE_ONLY` (exit **0**), without network, installation, credentials, or wallet calls.

**A static PASS does not approve any release or establish API compatibility.** It does not verify that the SDK actually accepts Zod 4 at runtime, that an npm audit is clear, or that the browser bundle is safe. The command is an explicit **precondition before any future wallet build promotion** but is **not wired to the ordinary developer `build` script**: existing offline regression/build behavior stays unchanged while the advisory is unresolved.

The separate `npm --prefix wallet-portal run test:security` suite uses synthetic package manifests for both vulnerable and fixed cases. CI runs these negative tests and executes the real lockfile check, reporting an unresolved **warning** on the GitHub job summary while leaving existing functional tests intact. A green *CI job* is not a green *security release decision*.

## Required work before closing #146

1. Upstream Coinbase release must publish a compatible patched Zod 4 range; independently confirm its package metadata. Do not force an unsupported major-version override.
2. Recreate and commit a deterministic lockfile from compatible versions; prove absence of **all** `zod <4.6.6` copies, with `npm ci`, `npm ls zod`, `npm audit --json`, and review of the actual built browser artifact.
3. Run portal unit tests, browser tests, and independent security review in an isolated environment; ensure tests never submit financial actions.
4. Require `security:check` exit 0 plus separate npm-audit/compatibility/security-owner evidence before any release. Close #146 only after evidence and Dependabot disposition.

Issue #138 (historical GitGuardian) and market-data/source-rights #97/#116/#123 are separate. No portfolio operations or live authorizations are part of this change.
