# Autonomiczny odczyt Coinbase App — gotowy runtime, aktywacja live osobno

## Wynik i granice

`scripts/autonomous_coinbase_history.py` jest lokalnym procesem cyklicznym,
który sam pobiera historię, sprawdza uprawnienia, obsługuje stronicowanie,
porównuje poprzedni zapis i zapisuje nowy prywatny stan. Nie wymaga kolejnych
poleceń w czacie ani ręcznego dostarczania capture w każdym cyklu.

**Nie jest jeszcze uruchomiony na rzeczywistym koncie.** Konektor Coinbase w tym
czacie nie wystawia List Transactions i nie udostępnia swojego uwierzytelnienia
lokalnemu procesowi. Nie użyto ani nie utworzono rzeczywistych poświadczeń.
Aktywacja live wymaga oddzielnej zgody i lokalnej konfiguracji klucza tylko do
odczytu. Proces nie instaluje sam usługi systemowej ani harmonogramu.

## Zweryfikowany kontrakt dostawcy — 23.10.2026

- [List Transactions](https://docs.cdp.coinbase.com/coinbase-app/track-apis/transactions):
  `GET https://api.coinbase.com/v2/accounts/:account_id/transactions`, `view`.
- [API key permissions](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/data-api/get-api-key-permissions):
  `GET /api/v3/brokerage/key_permissions`. Przed KAŻDYM cyklem wymagane dokładnie
  `can_view=true`, `can_trade=false`, `can_transfer=false` i oczekiwany portfolio UUID.
  Nieznane/brakujące pola, inne portfolio lub szersze uprawnienia blokują historię.
- [Coinbase App authentication](https://docs.cdp.coinbase.com/coinbase-app/authentication-authorization/api-key-authentication):
  ECDSA/ES256, JWT ważny 120 sekund, nowy podpis dla żądania. Użyty jest wyłącznie
  generator JWT oficjalnego SDK, bez jego klienta REST, zleceń i transferów.
  Klucz musi być ECDSA P-256; Ed25519 jest odrzucany mimo wsparcia w ogólnym SDK.
- Orbit wskazał i opisał endpoint uprawnień; jego wynik dla historii obejmował
  także inne produkty (Prime), więc kontrakt Coinbase App sprawdzono bezpośrednio
  w oficjalnej dokumentacji. Prime/Exchange nie zastępują konsumenckiego konta.

## Ograniczenia techniczne i ochrona danych

Klient ma stały host HTTPS i wyłącznie dwie ścieżki GET: uprawnienia i historia
jednego jawnie skonfigurowanego konta. Nie akceptuje metod zapisu, dowolnych URL,
innych kont ani ścieżek z parametrami. Wyłącza automatyczne przekierowania i
proxy z otoczenia; weryfikacja TLS pozostaje domyślna. Kolejne query odtwarza
z dozwolonego kursora zamiast otwierać `next_uri` dostawcy.

Limity: 20 sekund na żądanie, maksymalnie 50 stron / 5000 rekordów, ograniczenie
rozmiaru odpowiedzi i zminimalizowanego capture. Zbyt duży stan jest odrzucany.
Kontrola stron i normalizacja pozostają zgodne z dotychczasowym importerem.
Opisy, kontrahenci, opcjonalne hashe i dodatkowe pola kwot nie są utrwalane.

Katalog stanu musi należeć do użytkownika i mieć 0700. Pliki mają 0600.
Blokada procesu zapobiega równoległemu przetwarzaniu tego samego stanu.
`checkpoint.json` zawiera ostatni zminimalizowany capture i raport, zapisane
razem przez atomową zamianę; nie przybywa kolejnych archiwów na każdy cykl.
Checkpoint jest prywatny i zawiera identyfikatory źródłowe potrzebne do
porównania. Nie publikować go w GitHub, Actions ani publicznym panelu.

Awaria nie nadpisuje poprzedniego checkpointu. `health.json` otrzymuje wtedy
`UNAVAILABLE`. Przy sukcesie `HISTORY_READ_OK` ma czas kontroli i termin ważności
15 minut. Odbiorca musi sprawdzać oba; martwy proces nie daje wiecznie świeżego
wyniku. Odstęp domyślny to 300 sekund (dozwolone 60–86400); okres dłuższy niż
15 minut oznacza przerwy w ważności health. Kolejny cykl ponawia próbę po stałym
odstępie, bez natychmiastowej burzy retry. Po restarcie używany jest checkpoint.
Konsola zawiera wyłącznie stałe kody i informację o zerowych operacjach finansowych.

## Przygotowana konfiguracja — nie wykonywać aktywacji bez zgody

Prywatny plik config (0600, poza repozytorium) zawiera dokładnie:
`account_id`, `portfolio_id`, `credentials_file`, `state_directory`,
`interval_seconds` (zalecane 300). UUID wybiera operator; proces nie zgaduje kont.
`credentials_file` wskazuje prywatny eksport CDP z polami `name` i `privateKey`.
Nigdy nie podawać wartości w czacie, argumentach procesu, logach ani repozytorium.
Klucz jest ładowany raz; rotacja wymaga restartu i ponownego preflightu.

W prywatnym środowisku procesu zainstalować
`requirements-autonomous-history.txt` (oficjalne `coinbase-advanced-py==1.8.4`).
Przygotowane polecenia po zatwierdzeniu konfiguracji:

```sh
python -m scripts.autonomous_coinbase_history --config /PRIVATE_DIR/reader-config.json --enable-live-read --once
python -m scripts.autonomous_coinbase_history --config /PRIVATE_DIR/reader-config.json --enable-live-read
```

Bez `--enable-live-read` program kończy się przed odczytem config/poświadczeń.
Pierwszy live run musi potwierdzić zakres, rzeczywisty kontrakt odpowiedzi,
prywatne pliki i health. Dopiero potem zatwierdzić uruchomienie nadzorowane
przez system operacyjny i kontrolę wygasłego health. Nie twierdzić, że trwały
autostart albo monitoring jest aktywny na podstawie samego kodu pętli.

## Co pozostaje UNKNOWN/PENDING

Automatyczny odczyt historii nie dowodzi dopasowania receive do blockchain.
Dokumentacja nie gwarantuje hasha/sieci/odbiorcy receive. CLI nie tworzy takich
danych, a `blockchain_evidence_status=NOT_CONFIGURED` i
`full_autonomous_reconciliation_ready=false` jawnie zachowują brak tego etapu.
Biblioteczne `run_service(..., evidence_path=...)` może odczytywać istniejący
prywatny plik dowodów operatora, ale nie uwierzytelnia go ani nie odświeża sieci.
Podstawowe CLI nie uruchamia takiego źródła. Żaden wynik nie dodaje nowego
kapitału, nie koryguje sald i nie wykonuje transferu, zakupu ani sprzedaży.

## Faktyczna walidacja i wycofanie

457 testów offline PASS lokalnie. 11 nowych obejmuje prawdziwy generator JWT
na jednorazowym kluczu testowym (bez sieci), odrzucenie Ed25519/szerszych
uprawnień, paginację, prywatność, blokadę, restart i odzyskanie po awarii.
Osobny 3-cyklowy canary z symulowanym transportem i zegarem: sukces → awaria →
odzyskanie, stan zachowany, 0 rzeczywistych HTTP i operacji finansowych.
To potwierdza mechanizm procesu, **nie** prawdziwy dostęp Coinbase ani wdrożenie.
CI musi potwierdzić te wyniki na końcowym commicie PR.

Rollback: zatrzymać proces (Ctrl+C), pozostawić prywatny checkpoint, wycofać PR.
Żaden harmonogram, konto ani uprawnienia nie zostały zmienione. Osobne usunięcie
stanu lub zmiana retencji wymaga świadomej decyzji operatora.
