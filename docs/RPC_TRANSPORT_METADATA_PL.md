# Issue #80 — lokalne metadane transportu RPC

## Problem i kontrakt

W pierwszym rzeczywistym pełnym oknie odbioru zapisano 94 nowe checkpointy:
83 OBSERVATION_OK i 11 PARTIAL na historii Ethereum. Poprzednia implementacja
celowo redagowała błędy; nie zapisywała odpowiedzi HTTP ani przyczyn ponowień.
Nie da się ustalić przyczyny tych dawnych błędów ani odtworzyć liczby HTTP429.
Nie zakładamy, że przyczyną był throttling; utrzymujemy UNKNOWN dla starego okna.

Poprawka dodaje do prywatnego `portfolio.json` pole `rpc_diagnostics`:
`mode=SCOPED_RPC_TRANSPORT_METADATA_V1`, `scope=ETHEREUM_BASE_RPC_ONLY`,
`chains` o stałych kluczach `1` i `8453`. Każdy zawiera wyłącznie liczniki:
`requests`, `http_200`, `http_429`, `http_other`, `network_errors`,
`rpc_capacity_errors`, `rpc_other_errors`, `rejected_responses`, `retries`.

- HTTP429 jest liczony także wtedy, gdy późniejsza próba zakończy się sukcesem.
- Błędy JSON-RPC capacity są odrębne od HTTP429; nie utożsamiamy ich.
- Błąd transportu i odrzucona odpowiedź mają osobne liczniki. Kategorie mogą się
  nakładać: HTTP200 może zawierać błąd JSON-RPC lub niepoprawną odpowiedź.
- Liczniki obejmują odczyty portfela i ograniczony backfill w tym samym cyklu;
  nie obejmują Coinbase, CDP, rynku i NBP. Zero RPC429 nie oznacza zera 429
  we wszystkich integracjach ani braku innych błędów.
- Nie zapisujemy URL, adresów, parametrów/metod żądań, sald, hashy transakcji,
  treści odpowiedzi, komunikatów błędów, tokenów ani poświadczeń.
- ContextVar izoluje cykle i zagnieżdżone konteksty, resetuje się także po wyjątku.
  Bez aktywnego kontekstu snapshot jest None, nie sztucznym zerem.
- Jeżeli cały cykl nie dotrze do zapisu raportu, brak nowego raportu/liczników
  pozostaje brakującym dowodem. Nie publikujemy osobnego pozornie udanego pomiaru.
- Nie zmieniają się metody/hosty RPC, zakres 1000 bloków, limit backfill 80,
  budżet 3 prób, harmonogram, klucze ani uprawnienia. Poprawiono zamykanie
  odpowiedzi HTTP przy niepoprawnym Retry-After; nie zmienia to budżetu retry.

## Walidacja i odbiór

Testy offline odtwarzają 429→200, trzy kolejne 429, sieć, capacity JSON-RPC,
niepoprawny JSON, HTTP403, blokadę write przed transportem, izolację cykli
oraz zamknięcie odpowiedzi przy niepoprawnym Retry-After. Są to fixtures,
nie dowód faktycznej przyczyny błędów PublicNode.

Wdrożenie jest **PENDING**. Kod przygotowany w PR; nie zmieniono działającego
supervisora ani watchdoga. Ze względu na regułę AGENTS.md dotyczącą zmian logowania
przed wdrożeniem nowych zapisów diagnostycznych wymagana jest zgoda właściciela.

Po zgodzie: zachować bieżące definicje i stan, przypiąć zweryfikowany SHA kodu
supervisora, wykonać kontrolowany restart tylko supervisora bez --once, utrzymać
PublicNode i 900 s. Osobny watchdog ntfy pozostaje na zweryfikowanym fcc7c2c.
Kolektor z PR #81 otrzymuje jawny --expected-commit pełnego wdrożonego SHA.
Nowe okno odbioru ma osobny katalog dowodów; starego dziennika nie przepisywać.
Pierwszy checkpoint to baseline, nie cykl naturalny. Rzeczywisty nowy cykl musi
utrwalić liczniki i poprawnie ograniczyć braki. Nie certyfikować nowej doby z góry.

Rollback: powrót supervisora do zachowanego c0b5430 i poprzedniej definicji,
bez cofania danych. Zachować nowe pola/liczniki i dotychczasowy dziennik; stare
wydanie pomija dodatkowe pole. Nie zmieniać ntfy, poświadczeń ani watchlisty.


## Uzupełnienie diagnostyki ERC-20 w PR #87 (29.10.2026)

Rzeczywista doba na Macu 28–29.10 dała pięć odrębnych cykli historii
Ethereum PARTIAL w ostatnim wycinku diagnostycznym; w tych pięciu cyklach
liczniki HTTP429, network i JSON-RPC capacity wyniosły 0, a liczba
HTTP200 wynosiła 5–6. Nie wolno z tego wywnioskować konkretnej przyczyny
bez danych o lokalnej walidacji logów i etapie niepowodzenia.

Kod `observe_wallets(...allow_partial_history=True)` pozostawia poprawnie
potwierdzone salda i oznacza historię UNAVAILABLE. Teraz dodaje do tej
historii **tylko** `failure_category`: stałą wartość z zamkniętej listy
kodów `ReadOnlyError`, m.in. `UNCONFIRMED_OR_INVALID_LOG`,
`HISTORY_BLOCK_EVIDENCE_MISMATCH`, `RPC_HTTP_FAILURE` lub
`RPC_UPSTREAM_ERROR`. Nieznana wartość, wyjątek z danymi źródłowymi lub
niestandardowy komunikat daje `UNKNOWN`, bez zapisu oryginału.
`error_code=READ_ONLY_HISTORY_SOURCE_UNAVAILABLE` jest zachowany dla
zgodności. Supervisor dodaje do źródła PARTIAL jedynie
`history_failure_categories`, również zwalidowane względem listy.
Nie ma nowych żądań, uprawnień, metod, zmian w harmonogramie ani operacji
finansowych.

Dopiero **kolejny rzeczywisty** cykl po świadomie zatwierdzonym wdrożeniu
tej wersji może dostarczyć wiarygodnej kategorii. Stare historyczne
checkpointy nie zawierają tej kategorii i nie będą retroaktywnie
poprawiane. Bieżący supervisor na Macu pozostaje przypięty do #85;
ten projektowy PR #87 nie jest wdrożeniem. Odbiór pozostaje PARTIAL,
bez certyfikacji historii EVM lub całego majątku.
