# Offline deposit evidence reconciliation (23 October 2026)

`scripts/deposit_evidence_reconciliation.py` implements a standalone, side-effect-free comparison of finalized Ethereum/Base transactions against operator-supplied Coinbase deposit records.

The eight required deposit fields are `source`, `deposit_id`, `chain_id`, `tx_hash`, `asset`, `amount`, `recipient`, `status`. The explicitly claimed source is `COINBASE_DEPOSIT_RECORD_OPERATOR_SUPPLIED`, **not** authenticated Coinbase API provenance. Expected assets: ETH or cbBTC; networks: Ethereum (1), Base (8453). Quantities are checked using decimal arithmetic, with exact token precision. Record IDs must be unique. A single chain/hash may not have conflicting evidence rows.

Result categories: `NO_MATCHING_DEPOSIT_RECORD`, `CONFLICTING_DEPOSIT_RECORD`, `NETWORK_NOT_FINALIZED`, `DEPOSIT_NOT_COMPLETED`, and `REPORTED_MATCH_SOURCE_UNVERIFIED`. All result rows include `coinbase_provenance_verified=false` and `balance_used_as_proof=false`. A match requires network FINALIZED and Coinbase status COMPLETED, exact chain/hash, asset, quantity, recipient, but still does **not** prove the source record originated from Coinbase.

This does not connect to Coinbase or enrich the local portal. The next integration must establish actual authorized Coinbase deposit-history access and validate the provider's real response schema and provenance before any stronger classification is introduced. Neither a Coinbase balance nor manual assertion proves a credited deposit. Never use this output to automatically retry, transfer, invest or book newly contributed capital.

Run `python -m unittest tests.test_deposit_evidence_reconciliation` from the repository root. All fixtures are synthetic and no wallet address, credential, request or trading operation is used.
