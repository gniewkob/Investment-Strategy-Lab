# Base RPC 429 — consent-based read-source selection and public method probe (24.10.2026)

## Verified incident
Mac acceptance for deployed SHA `892996c42de33230f91137c8b3fe98211e51729e` verified two controlled observation cycles, ongoing Local Canary PARTIAL, and HTTP 429 from `https://mainnet.base.org` on three of three bounded Base attempts. See `docs/MAC_RUNTIME_ACCEPTANCE_2026_10_24_PL.md` at the independent acceptance commit `72627314f27f324cb676787aa9d569b3db252512`. Ethereum/Exchange/CDP/market/NBP had OK source status; Base historical gaps cannot be reconstructed until the provider returns a correct read.

Base officially decreased public `mainnet.base.org` read limits on **2026-10-08 at 12:00 UTC**, and describes that public endpoint as best-effort, not suitable for production. PublicNode publishes the Base mainnet HTTPS RPC `https://base-rpc.publicnode.com` as an alternate, without requiring a paid account for standard reads; archive reachability and ongoing SLA are **not guaranteed**.
- Base rate limits: https://base-l2.statuspage.io/
- Base RPC scope: https://basehub.org/api-reference/rpc-overview/
- PublicNode self-published Base endpoint: https://base.publicnode.com/

## What was implemented

Existing default source remains `OFFICIAL` (`https://mainnet.base.org`), with **zero changes to the deployed environment**. A controlled, explicit runtime opt-in selects `PUBLICNODE` (`https://base-rpc.publicnode.com`):

```sh
# Private Mac operator session: PublicNode only for this command.
ISL_BASE_RPC_SOURCE=PUBLICNODE python3 -m scripts.base_rpc_probe --allow-public-network-probe
```

The probe makes **five JSON-RPC read operations** on Base (chain ID, finalized header, two 80-block-range ERC20 log filters using a fixed **zero address**, then rechecks the source block). It uses the existing bounded retry and exact HTTPS origin check. It does **not** send any account or user-wallet address, retrieve a Coinbase key, place an order, move assets, perform x402, or write to Neon. Exit 0 means the selected provider served this synthetic read shape at that moment. It is **not** assurance that the provider serves a particular historic window, returns valid account history or supports a production SLA. Exit 2 means unavailable/rejected; the cause is redacted.

The selector accepts **only** `OFFICIAL` and `PUBLICNODE`. Invalid values fail closed before network calls. It is resolved once when the Python module is imported; every RPC call in the current process uses the **same pinned source**, avoiding a split-provider observation inside one wallet cycle. Other chains (Ethereum) remain unchanged. There is no automatic multi-host failover, vendor-key handling, external withdrawal endpoint or hidden per-request load balancing.

### Controlled local rollout decision gate

1. Work/operator may run the synthetic PublicNode probe on the Mac **without private wallet data** and without modifying any live LaunchAgent or API permission.
2. Before enabling PublicNode for a wallet observer, evaluate the privacy tradeoff: adding a vendor means that vendor will see public wallet addresses and request metadata. **Require explicit, authorized operator choice**, not an automatic switch after HTTP 429.
3. If authorized, configure the private LaunchAgent environment to `ISL_BASE_RPC_SOURCE=PUBLICNODE` and validate only a single controlled read-only cycle, with existing code rollback and local canary; do not alter wallet watchlist, credentials, private state, provider contracts, or other LaunchAgents. Source provenance in reports shows the selected provider URL.
4. Compare provider finalized head, chain 8453, event/block hashes, 1000-block history status and 80-block backfill behavior using existing safety validation. Keep `PARTIAL` for 429, missing receipts, inconsistent headers, historical log unavailability, or unrecovered gaps. Never infer successful recovery merely because the synthetic zero-address probe returned 200.
5. Re-evaluate long-running reliability over multiple normal 900-second cycles; one probe is not proof of uptime. If PublicNode is still limited on ERC20 logs or archival reads, retain the incident without repeating requests aggressively. A production-grade dedicated RPC provider could require separate vendor/security/privacy approval; do not provision automatically.

No on-host runtime update, live PublicNode probe, or change of the existing deployed SHA is claimed by this repository PR.

## Test acceptance

```sh
python3 -m unittest discover -s tests -p 'test_base_rpc_probe.py' -v
python3 -m unittest discover -s tests -v
```

CI tests source pinning, strict options, method/chain restrictions, HTTPS redirect rejection, fresh finalized head, 80-block log range, synthetic zero-address privacy, explicit CLI consent, error redaction, and no execution APIs.
