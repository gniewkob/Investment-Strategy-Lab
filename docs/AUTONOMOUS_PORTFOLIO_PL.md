# Autonomiczny monitoring portfela — kontrakt i wdrożenie

Tryb wyłącznie obserwacyjny. Moduł `scripts.autonomous_portfolio` nie zawiera metod
zleceń, konwersji, transferów, podpisywania blockchain ani płatności x402.
Użycie SDK ogranicza się do podpisywania tokenów JWT dla odczytu API.

## Źródła i zakres

- Coinbase App GET `/v2/accounts`: wszystkie konta udostępnione istniejącemu
  kluczowi View, z pełną ograniczoną paginacją, maksymalnie 100 kont.
- GET `/v2/accounts/{id}/transactions`: osobny prywatny checkpoint, porównanie
  kolejnych historii i stan zdrowia każdego konta. Preflight odrzuca klucz
  z Trade lub Transfer i inny portfolio UUID. Nie zmienia zakresu klucza.
- CDP GET `https://api.cdp.coinbase.com/platform/v2/evm/token-balances/{network}/{address}`:
  ethereum/base, maksymalnie 20 stron i 1000 tokenów. Odpowiedź indeksatora
  pozostaje osobna od potwierdzonego salda. Symbole tokenów nie są zaufane.
- Istniejący `operational_read_only.observe_wallets`: przypięty blok finalized,
  ponowna kontrola hasha bloku, natywny ETH i jawnie zarejestrowany cbBTC;
  ograniczona historia do 1000 bloków wyłącznie tych tokenów ERC20.
- Coinbase publiczne zamknięte świece 1h BTC/ETH/ATOM: 72 godziny,
  walidacja ciągłości, czasu i SHA odpowiedzi w istniejącym module monitoringu.

Kontrakt CDP zweryfikowany z oficjalną dokumentacją oraz Orbit discovery/integrate:
https://docs.cdp.coinbase.com/api-reference/v2/rest-api/evm-token-balances/list-evm-token-balances
Coinbase account history:
https://docs.cdp.coinbase.com/coinbase-app/track-apis/transactions

## Obraz majątku i uzgadnianie

Salda Coinbase i salda własnych adresów są oddzielnymi lokalizacjami.
Salda z CDP nie są ponownie dodawane do sald RPC. Wycena jest częściowa,
referencyjna w USD; brak ceny nie oznacza wartości zero. Nie certyfikujemy
kompletnego majątku: DeFi, NFT i nieznane tokeny nie są kompletnie wycenione.
Użytkownik wskazuje publiczny adres własnego Wallet; samo wskazanie nie jest
kryptograficznym dowodem własności. Nie stosować adresu depozytowego giełdy
jako osobnego majątku — wymaga to poprawnego wyboru operatora.

Uzgadnianie wykorzystuje istniejący konserwatywny silnik `reconcile_events`.
Historia Coinbase nie zapewnia obecnie powiązania receive/tx z siecią, hashem
oraz kontraktem, dlatego `full_autonomous_reconciliation_ready=false`.
Nie zgadujemy tożsamości przelewu po czasie i kwocie. cbBTC nie jest BTC.
Nieobecność receive nie potwierdza braku wpłat. Niesklasyfikowane tx zostają
zachowane w prywatnych checkpointach. Historia ERC20 ma ograniczony zakres,
nie obejmuje natywnych transferów ETH, wewnętrznych wywołań, NFT ani pełnej historii.

## Symulacja i panel

Stały prospektywny benchmark: fikcyjne 10 000 USD, 50% BTC / 50% ETH buy-and-hold,
porównanie z gotówką; założenie kosztu wejścia 20 pb + poślizg 10 pb.
Brak optymalizacji, realnych alokacji i obietnicy rentowności. Znane ceny zamknięcia
są wyłącznie cenami referencyjnymi, nie możliwymi do wykonania zleceniami.
Ten sam znacznik świecy nie powoduje ponownego wejścia ani kosztu. Po awarii
ostatni poprawny stan symulacji jest zachowany; bieżący wynik jest niedostępny.
Panel lokalny `portfolio-state/dashboard.html` ma 0600, nie pobiera zewnętrznych
zasobów, escapuje dane, pokazuje czas wygaśnięcia i odświeża widok co 60 sekund.
Nie wystawia serwera ani publicznego endpointu. Awaria głównego cyklu pozostawia
stary raport z jawnym terminem ważności; niezależny watchdog zgłasza awarię.

## Prywatne uruchomienie

Istniejący reader-config i klucz pozostają lokalnie. Nie commitować wygenerowanych
konfiguracji, adresów, historii, wartości portfela ani raportów do GitHub.

```sh
python -m scripts.autonomous_portfolio --config /PRIVATE/reader-config.json --setup-wallet --enable-live-read
python -m scripts.autonomous_portfolio --config /PRIVATE/portfolio-config.json --enable-live-read --once
python -m scripts.autonomous_portfolio --config /PRIVATE/portfolio-config.json --enable-live-read
python -m scripts.autonomous_portfolio --config /PRIVATE/portfolio-config.json --enable-live-read --check-health
```

Setup natywnym oknem przyjmuje publiczny adres i konfiguruje Base+Ethereum.
Katalog 0700, pliki JSON/HTML 0600; setup nie nadpisuje istniejącej konfiguracji.
Odczyt cykliczny co 900 sekund, oddzielna blokada procesu. Uwierzytelnienie
Coinbase oraz CDP jest rozdzielone po dokładnym hoście i ścieżce. Brak proxy,
przekierowań, przekazywania URL od dostawcy i ujawniania treści błędów.
Każde źródło otrzymuje OK lub UNAVAILABLE, nigdy wymyśloną pustą odpowiedź.

Watchdog uruchamiany osobno co 300 sekund czyta wyłącznie health.json;
termin ważności 30 minut. Powiadamia o zmianie awarii/zakresu brakujących źródeł,
stanie STALE i odzyskaniu zdrowia, a nie o niezmienionych kontrolach.
Nieudane powiadomienie nie zatwierdza znacznika, więc będzie ponowione.

## Kontrole wdrożenia i rollback

1. Pełny offline unittest (zależności testowe zgodne z CI), testy kontraktu CDP,
   uprawnień, paginacji, izolacji błędów, symulacji i watchdoga.
2. Jednorazowa rzeczywista próba GET; publikować tylko statusy źródeł i kontrole.
3. PR i zielone CI przed scaleniem; instalacja kodu z SHA scalonego main.
4. Osobne macOS LaunchAgents procesu i watchdoga; stdout/stderr do /dev/null.
5. Weryfikacja odczytu i kolejnego checkpointu po restarcie procesu.
6. Rollback: zatrzymać wyłącznie nowe zarządzane etykiety portfolio/portfolio-health,
   zachować stan i konfigurację; istniejący czytnik historii i jego watchdog
   działają niezależnie i pozostają nietknięte. Nie usuwać kluczy ani danych.

Nie wdrażamy webhooków: okresowy odczyt wystarcza w tym zakresie, a udostępnienie
publicznego odbiornika nie jest potrzebne. Brak nowych płatnych usług lub subskrypcji.
