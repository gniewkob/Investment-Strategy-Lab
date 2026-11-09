# C2 — offline source-category gateway and candidate ACWI NETR review

**Date:** 2026-11-09. **Status:** dependency-stacked Draft PR, based on C1 Draft #102 (itself based on B1 #100 and A2 #99). Separate A1 #98 and host installer B2 #101 are not prerequisites.

## Code and evidence boundaries

Four original Python files are copied unchanged from Draft PR #96, with identical Git blob SHAs:
- `scripts/real_reference_gateway_v18.py` and test — reads already-held research NBP/BondSpot monthly reference-calendar artifacts, checks their recorded digest, and passes them to C1's read-only decision pipeline as **NOT QUALIFIED TOTAL_RETURN**. USD/PLN FX_RATE, gold PRICE_ONLY, BondSpot NON_TRADABLE index do not become GLOBAL_EQUITY_TR_PLN, PL_BONDS_TR_PLN, or GOLD_TR_PLN.
- `scripts/acwi_netr_offline_intake_v19.py` and test — interprets a manually provided candidate MSCI ACWI NETR USD export **offline**. It never downloads or redistributes original index data and cannot independently certify its licensing/rights, authenticity, time of publication or derived-use permission. The fixture data in the test is synthetic.

## CI

Dedicated `.github/workflows/isl-c2-source-gateway-offline-ci.yml` tests two source+test pairs on Ubuntu/macOS Python 3.12. Expected **19/19** synthetic, fail-closed tests per platform, Python socket calls blocked. No credentials, remote DB service, provider upload, asset transfer or trade instructions. CI acceptance is source-parser behavior only.

## Strict decision constraints

- All market source categories remain distinct. Provider rights and historical point-in-time source availability need independent verification; a SHA digest is not a trusted timestamp or licensing grant.
- Offline CSV parsing never grants real market-data entitlement or authorizes reproduction, export, or automated execution.
- A2 #99 → B1 #100 → C1 #102 → C2. C2 has no dependency on B2 #101 (file installation/copy).
- Do not merge broad PR #96 wholesale after integrating split PRs. The current C1 and C2 are Draft and must stay so until code/security review and precise diff reconciliation.
- Original v0.9 archive, frozen Vanguard research v0.22–v0.23, live source access and real M1–M3 qualification are unchanged. Any forward status from synthetic fixtures remains research-only; financial operations zero.

**Next technical review:** E decision quality and chronological robustness (v0.26–v0.29) after C2, not market performance certification.
