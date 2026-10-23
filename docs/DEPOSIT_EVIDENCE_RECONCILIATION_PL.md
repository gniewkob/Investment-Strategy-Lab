# Offline deposit evidence reconciliation (23 October 2026)

`scripts/deposit_evidence_reconciliation.py` implements a standalone, side-effect-free comparison of finalized Ethereum/Base transactions against operator-supplied Coinbase deposit records.

The eight required deposit fields are `source`, `deposit_id`, `chain_id`, `tx_hash`, `asset`, `amount`, `recipient`, `status`. The explicitly claimed source is `COINBASE_DEPOSIT_RECORD_OPERATOR_SUPPLIED`, **not** authenticated Coinbase API provenance. Expected assets: ETH or cbBTC; networks: Ethereum (1), Base (8453). Quantities are checked using decimal arithmetic, with exact token precision. Record IDs must be unique. A single chain/hash may not have conflicting evidence rows.

Result categories: `NO_MATCHING_DEPOSIT_RECORD`, `CONFLICTING_DEPOSIT_RECORD`, `NETWORK_NOT_FINALIZED`, `DEPOSIT_NOT_COMPLETED`, and `REPORTED_MATCH_SOURCE_UNVERIFIED`. All result rows include `coinbase_provenance_verified=false` and `balance_used_as_proof=false`. A match requires network FINALIZED and Coinbase status COMPLETED, exact chain/hash, asset, quantity, recipient, but still does **not** prove the source record originated from Coinbase.

This does not connect to Coinbase or enrich the local portal. The next integration must establish actual authorized Coinbase deposit-history access and validate the provider's real response schema and provenance before any stronger classification is introduced. Neither a Coinbase balance nor manual assertion proves a credited deposit. Never use this output to automatically retry, transfer, invest or book newly contributed capital.

Run `python -m unittest tests.test_deposit_evidence_reconciliation` from the repository root. All fixtures are synthetic and no wallet address, credential, request or trading operation is used.

## Review and regression gate (23 October 2026)

PR #63 review added an 80-character quantity bound and explicit string checks so malformed JSON collections fail with a fixed error instead of an incidental TypeError. Nine focused synthetic tests cover these controls, exact decimal validation, ambiguity and input immutability. The PR workflow now installs the existing psycopg test dependency and runs the entire offline suite without account credentials. Initial local full-suite execution was blocked by missing psycopg; this environment failure is not a successful regression result. Merge requires successful rerun on the reviewed head, including CI. Existing panel observations contain additional provenance/time fields; this comparator accepts an explicit six-field transfer projection, not the raw panel snapshot. It does not authenticate that projection.

PR #63 was merged as `bb3cce78b28a655ad6ea5b00933ebd8ab3e9cffd` after **420 offline tests passed locally** and [full offline CI passed on reviewed head b94e452](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39925195281). GitGuardian also passed. These tests do not certify a live database, Coinbase connection or blockchain observation.

## Prywatny odczyt historii wpłat: importer offline

`scripts/coinbase_deposit_history.py` przetwarza zapisane odpowiedzi Coinbase App
**List Transactions**. Nie wykonuje HTTP, nie przyjmuje kluczy i nie uwierzytelnia
pliku. Katalog konektora Coinbase sprawdzony 23.10.2026 zawiera salda i fills,
ale nie zawiera operacji odczytu historii wpłat. Weryfikacja na żywo: **PENDING**.
Nie zastępuj jej odczytem salda, dostępem do zleceń ani nowymi uprawnieniami.

Zweryfikowany [kontrakt Coinbase App](https://docs.cdp.coinbase.com/coinbase-app/track-apis/transactions)
udostępnia `GET /v2/accounts/:account_id/transactions` z zakresem
`wallet:transactions:read` / CDP `view`. `receive` oznacza otrzymanie aktywa;
`fiat_deposit`, transakcje kupna i fills są innymi typami. Dokumentacja opisuje
`network.hash` oraz `network.network_name` tylko dla `send`, a pole `address`
oznacza jako usunięte dla List/Show. Dlatego importer **nigdy nie tworzy dowodu
blockchain z receive**, nawet jeśli plik zawiera opcjonalny hash. Sprawdzony przez
Orbit Coinbase Exchange `GET /accounts/{account_id}/transfers` jest osobnym
produktem z innym uwierzytelnianiem i kontraktem; nie jest zamiennikiem Coinbase App.

Kontrakt pliku capture (wyłącznie prywatny katalog poza repozytorium):

- `mode`: `PRIVATE_COINBASE_APP_TRANSACTIONS_V1`.
- `account_id`: UUID konta, `captured_at`: czas UTC zapisu.
- `pages`: 1–50 elementów `{request_cursor, response}`. Pierwszy cursor to `null`.
- `response.data`: maksymalnie 100 rekordów na stronę, 5000 łącznie;
  `response.pagination` musi zawierać `starting_after`, `ending_before=null`,
  `order=desc`, `limit` 1–100 i `next_uri` (na końcu `null`).
- Kolejny `request_cursor` musi odpowiadać `starting_after` z poprzedniego
  `next_uri`, równemu ID ostatniego rekordu. Dozwolony jest wyłącznie względny
  URI tego samego konta, z parametrami `starting_after`, opcjonalnie `limit/order`.
  Importer waliduje URI, nigdy go nie otwiera. Inne warianty stronicowania wymagają
  osobnego przeglądu kontraktu; są odrzucane.
- Każdy rekord ma UUID `id`, zgodny `resource_path`, `resource=transaction`,
  `type`, `status`, `created_at`. Dla receive wymagane są dodatnia dziesiętna
  kwota `amount.amount` i `amount.currency`. Duplikaty, brak stron, przyszłe
  zdarzenia i błędne kształty danych przerywają import.

Daty zdarzeń dostawcy z jawnym offsetem (np. `-07:00` w przykładzie Coinbase)
są przeliczane na UTC przed sprawdzeniem przyszłych zdarzeń i zapisem wyniku.
Daty bez strefy są odrzucane; lokalny `captured_at` i `--at` nadal wymagają UTC.

Wynik zachowuje tylko receive: pseudonim ID (SHA-256 z konta i ID), czas, symbol,
kwotę i status. Nieznany status pozostaje `UNKNOWN`. Opisy, dane kontrahentów,
surowe identyfikatory, adresy i hash z capture nie trafiają do historii wynikowej.
Pseudonimy i cały raport pozostają prywatne. Kompletność łańcucha stron nie
certyfikuje snapshotu ani całej historii finansowania; źródło pozostaje
nieuwierzytelnione. Kwoty różnych aktywów/statusów nie są sumowane.

CLI przyjmuje bundle z dokładnie czterema polami: `mode` =
`PRIVATE_COINBASE_DEPOSIT_REVIEW_V1`, `history` = capture, `network_transfers`
i `deposit_records` w schematach z początku dokumentu.
Porównanie dowodów operatora jest osobną sekcją wyniku; zgodna historia receive
nie podnosi jego wiarygodności i nie tworzy automatycznego powiązania. Dla raw
wyniku panelu trzeba jawnie wybrać sześć pól transferu; nie dodawać danych
operatora do schematu komparatora ani nie twierdzić, że projekcja uwierzytelnia sieć.

```sh
python -m scripts.coinbase_deposit_history \
  --input /PRIVATE_DIR/deposit-review.json \
  --output /PRIVATE_DIR/deposit-review-result.json
```

Wejście: plik właściciela 0600; katalog wyjściowy 0700. Wyjście jest tworzone
wyłącznie jako nowy plik 0600, bez nadpisywania i podążania za symlinkiem.
Konsola podaje wyłącznie stały kod sukcesu/błędu, bez ścieżek i rekordów.
Raportu nie publikować w GitHub, Actions ani publicznym panelu. `--at` ustawia
czas walidacji do odtwarzalnych testów, nie jest dowodem daty pozyskania danych.

Kontrole: testy syntetyczne importu, prywatnych uprawnień, kursorów, izolacji
źródeł i braków dowodowych; pełna regresja offline w tym samym workflow PR.
Rollback: wycofać commit importera; istniejący panel, salda i comparator PR #63
działają niezależnie. Następny etap wymaga dostępnego, zatwierdzonego odczytu
historii Coinbase i weryfikacji rzeczywistego kontraktu odpowiedzi bez publikacji
prywatnych danych; nie tworzyć sekretów ani wykonywać operacji finansowych.
