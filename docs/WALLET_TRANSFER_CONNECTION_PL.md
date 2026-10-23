# Lokalny panel podłączenia i transferu portfela

Opcjonalny moduł dodany na wyraźne żądanie użytkownika. Monitory oraz importer historii
pozostają wyłącznie odczytowe. Ten panel może przekazać pojedynczy transfer ETH lub
zatwierdzonego cbBTC do podpisania w portfelu użytkownika. Serwer nie podpisuje,
nie pośredniczy w RPC i nie przechowuje kluczy. Brak zleceń, swapów, mostów,
allowance/approve, session keys, automatycznych ponowień i uprawnień do wydawania.

## Uruchomienie

Wymagania: Node >=20, Python 3.12, lokalny prywatny watchlist zgodny z
`PRIVATE_WALLET_READ_ONLY` (patrz runbook read-only). Nie umieszczaj konfiguracji
osobistej w repozytorium. Pliki muszą należeć do operatora i mieć uprawnienia 0600;
katalog prywatny 0700. Nie podawaj frazy odzyskiwania, klucza ani API secret.

```sh
npm --prefix wallet-portal ci --ignore-scripts
npm --prefix wallet-portal run build
python -m scripts.wallet_transfer_portal --watchlist /PRIVATE/watch.json
```

Otwórz `http://127.0.0.1:8766` w przeglądarce obsługującej Twój portfel. Domyślnie
można jedynie podłączyć jeden adres z prywatnej watchlist. Portal odrzuca watchlist z kilkoma różnymi adresami (monitory odczytowe nadal mogą obserwować wiele kont). Brak konfiguracji transferu blokuje
przygotowanie i podpis. SDK Base Account jest przypięty w lockfile, bundlowany
lokalnie, telemetria wyłączona, tworzenie i finansowanie subkont ustawione ręcznie.
Operator może jawnie uruchomić `--connector injected`, jeżeli właściwy portfel jest dostępny jako rozszerzenie EIP-1193. W interfejsie nie ma wyboru dostawców ani automatycznego fallbacku do mobilnego Coinbase Wallet / starego QR. Panel nie wysyła żądania portfela na starcie.
SDK może utrzymywać własną sesję; panel nie zapisuje adresów i transferów do storage.

## Jedna tożsamość połączenia

`GET /session` zwraca `accounts` z dokładnie jednym adresem oraz `connection`:
`account`, `label` (z prywatnej watchlist), `provider` (`base` domyślnie lub jawny
`injected`) i `chainIds`. Polityka transferu musi wskazywać tę samą tożsamość.
Pełny oczekiwany adres jest widoczny lokalnie przed połączeniem. W trybie podłączenia formularz transferu i jego kroki są ukryte. Nazwa jest tylko
etykietą, nie wynikiem rozwiązywania ENS. Liczy się adres zwrócony przez portfel.

Połączenie zachowuje istniejącą zgodę portfela, a zwrócony adres i sieć nadal
podlegają weryfikacji. Dzięki temu ponowne wczytanie polityki nie wymusza nowego
logowania. „Wyczyść sesję tego panelu” jawnie wywołuje `provider.disconnect()`
i przeładowuje stronę, również podczas oczekiwania na logowanie. Nie usuwa całego localStorage,
kont portfela ani uprawnień on-chain; nie wylogowuje z witryny Coinbase. Reset jest
zablokowany po wysłaniu żądania transferu, gdy wynik jest nieznany lub istnieje hash.

SDK nie udostępnia wymuszenia adresu w QR ani wyboru konta w aplikacji mobilnej.
Jeżeli logowanie zwraca inny adres, panel pokazuje otrzymany i oczekiwany adres,
blokuje transfer i nie przechodzi do innego dostawcy. Wybór właściwego istniejącego
konta należy wykonać w samym portfelu / oknie logowania. Nie twórz nowego konta,
aby „dopasować” adres. Automatyczne testy nie poświadczają logowania do prywatnego
konta w telefonie.

## Włączenie pojedynczej sesji transferu

Najpierw operator musi w Coinbase sprawdzić aktualny adres **Receive**, obsługiwany
asset i sieć. Adres własnego portfela nie jest adresem wpłaty giełdy. Panel nie
potrafi pozyskać ani poświadczyć adresu Coinbase — jawna deklaracja operatora jest
warunkiem uruchomienia, a nie dowodem pochodzenia adresu.

Prywatny plik polityki ma dokładnie poniższe pola (wartości przykładowe należy
zastąpić własnymi; placeholder nie przejdzie walidacji):

```json
{
  "mode": "USER_CONFIRMED_WALLET_TRANSFER",
  "chain_id": 8453,
  "from_label": "base",
  "destination": "[CONFIRMED_COINBASE_RECEIVE_ADDRESS]",
  "asset": "cbBTC",
  "max_amount": "0.00000001",
  "max_execution_fee_wei": "1000000000000000",
  "destination_confirmed_in_coinbase": true,
  "confirmed_at": "[CURRENT_UTC_ISO8601]",
  "expires_at": "[UTC_ISO8601_WITHIN_24_HOURS_OF_CONFIRMATION]"
}
```

`from_label` i chain muszą jednoznacznie wskazać watchlist. cbBTC wymaga kanonicznego
kontraktu w `verified_token_contracts`. Tylko chain 1 i 8453, ETH lub cbBTC.
Konfiguracja starsza niż 24h, pusty limit, źle sformatowany adres, adres własny,
zerowy lub kontrakt tokena są odrzucane. Dodaj opcję:

```sh
python -m scripts.wallet_transfer_portal --watchlist /PRIVATE/watch.json --transfer-policy /PRIVATE/transfer.json
```

1. Podłącz właściwe konto, sprawdź sieć w portfelu.
2. Podaj kwotę w jednostkach tokena. Podgląd sprawdza konto, chain, saldo i gas.
3. Porównaj pełny adres i sieć z Coinbase. Zaznacz potwierdzenie.
4. Otwórz osobnym przyciskiem okno portfela, sprawdź pełne koszty i dopiero tam podpisz.
5. Panel sam sprawdzi receipt; osobno sprawdź uznanie wpłaty w Coinbase. Wpłata nie tworzy `fills`.

## Karta do potwierdzenia

Główny ekran przedstawia pojedynczy transfer. Po podłączeniu ustawienia połączenia
zwijają się; po utracie połączenia rozwijają ponownie. Karta zawiera kwotę, skrócone
źródło, pełny adres odbiorczy, sieć i dokładnie przeliczony koszt wykonania w ETH
(bez zaokrąglania przez floating point). Wycena PLN jest jawnie niedostępna: panel
nie ma zweryfikowanego źródła ceny/FX. Pełna opłata Base pozostaje do sprawdzenia
w portfelu. Limit tokenów i koszt wykonania nie zastępują łącznego budżetu USD.

Podgląd ma widoczne odliczanie 60 sekund. Po wygaśnięciu podglądu lub polityki
potwierdzenie jest wyłączone; zmiana kwoty usuwa wcześniejszy podgląd i zgodę.
Przycisk „Sprawdź w portfelu” wymaga uprzedniego zaznaczenia weryfikacji odbiorcy.
Nie ma automatycznego otwarcia prośby o podpis ani przedłużania polityki.

Po zwróceniu hash przez portfel panel automatycznie wykonuje do sześciu sprawdzeń
receipt, w odstępach 10 sekund po zakończeniu poprzedniego odczytu. Pierwszy odczyt
jest natychmiastowy. Finalizacja albo revert kończą sprawdzanie. Błąd API zatrzymuje
automatyczne odczyty bez retry; przycisk umożliwia pojedynczy kolejny odczyt.
Żaden odczyt nie ponawia wysyłki. Widok pokazuje hash oraz oddzielny, niezweryfikowany
status zaksięgowania Coinbase. Przeładowanie strony kończy odliczanie i odczyty;
nie odtwarza wyniku i nie anuluje transakcji. Testy syntetyczne obejmują finalizację,
limit sześciu odczytów, HTTP429, wygaśnięcie i układ mobilny.

Limit kwoty jest w tokenach, nie USD. **Nie ma automatycznej gwarancji 10 USD
łącznie z opłatami.** Koszt wykonania ma bufor gas 20% i gasPrice 2x; polityka
ogranicza ich iloczyn. Na Base nie obejmuje to całego kosztu L1 ani ewentualnej
zmiany parametrów przez portfel. Pełny koszt musi sprawdzić użytkownik w portfelu.
Brak ETH na Base blokuje transfer cbBTC. Panel nie uzupełnia gas ani nie mostkuje.

Przed otwarciem portfela odczyty są ponawiane. Bieżący szacunek gas i cena gas
muszą mieścić się odpowiednio w zamrożonym gas i gasPrice z zaakceptowanego podglądu.
Nie wymagamy identyczności kolejnych wycen: zmiana mieszcząca się w zatwierdzonym
zapasie nie podnosi limitu. Do portfela trafiają dokładnie pierwotne parametry,
bez automatycznego podbijania opłaty. Przekroczenie któregokolwiek z nich nadal
wymaga nowego podglądu. Niezależne limity polityki, salda i tożsamość są sprawdzane
także przy drugim odczycie.

Po nieznanym wyniku wysyłki panel blokuje ponowienie. Nie otwieraj nowej sesji,
zanim nie sprawdzisz historii portfela. Odmowa podpisu (4001) czyści podgląd.
Podgląd ważny 60s; zmiana konta/sieci go unieważnia. Receipt wymaga właściwego
transferu, statusu success, hash bloku i finalizacji. Nie jest dowodem uznania wpłaty.
Nie odtwarzamy identyfikatora po przeładowaniu strony: historia pozostaje w portfelu.

Po błędzie zwróconym przez interfejs portfela diagnostyka pokazuje wyłącznie
stałą kategorię i opcjonalny standardowy kod numeryczny (np. 4200). Nie zapisuje
treści błędu, adresów, RPC URL, sesji ani treści żądania. Kategorie obejmują brak
obsługi metody, oczekujące żądanie, utratę sesji, timeout i błąd publikacji relay.
Kategoria jest wskazówką diagnostyczną, nie dowodem braku broadcastu. Nieznany
wynik nadal blokuje ponowienie niezależnie od kategorii. Nowa diagnostyka nie
odtwarza błędu wcześniejszej próby i nie odblokowuje istniejącego okna.

## Granice, testy i wycofanie

HTTP: wyłącznie loopback, dokładny Host, same-origin `/session`, brak CORS, no-store,
CSP, brak logów żądań, tylko statyczne zasoby i konfiguracja w pamięci. Brak POST/RPC.
To nie chroni przed złośliwym oprogramowaniem ani rozszerzeniami lokalnego komputera.
Nie publikować serwera w sieci, nie używać reverse proxy lub tunelu.

```sh
npm --prefix wallet-portal test
npm --prefix wallet-portal run test:e2e
python -m unittest discover -s tests
```

Testy portfela używają syntetycznego EIP-1193 bez połączenia z siecią. Testy nie
potwierdzają działania rzeczywistego popupu SDK, podpisu, wysłania lub wpłaty.
Prywatny adres docelowy, aktywna polityka i podpis użytkownika pozostają osobnymi
warunkami rzeczywistego użycia. Zatrzymaj Ctrl+C, usuń prywatną politykę, odłącz
połączenie w ustawieniach portfela. Wycofanie kodu nie cofa wysłanej transakcji.

Źródła: [Base account SDK](https://github.com/base/account-sdk),
[Coinbase Wallet](https://docs.cdp.coinbase.com/coinbase-wallet/overview).

## Wybór właściwego konta portfela

Panel używa Base Account SDK i jednej tożsamości z prywatnej konfiguracji.
Sprawdza adres rzeczywiście zwrócony przez portfel; nazwa `.base.id` nie
zastępuje tego sprawdzenia. Dawna ścieżka mobilnego Coinbase Wallet SDK/QR
została usunięta. Zwykłe podłączenie zachowuje istniejącą sesję SDK; jawny reset
odłącza wyłącznie aktywnego dostawcę. Inne konto zostaje odrzucone, bez obejścia
listy adresów i bez automatycznego przełączenia dostawcy. Nie importuj frazy
odzyskiwania do panelu.

Jeżeli istniejąca sesja portfela zwraca Ethereum, a konfiguracja wymaga Base,
panel pokazuje przycisk „Przełącz portfel na sieć z konfiguracji”. Tylko jawne
kliknięcie wywołuje `wallet_switchEthereumChain`; nie podpisuje transakcji,
nie tworzy sieci i nie wysyła środków. Konto źródłowe jest sprawdzane przed
przełączeniem i po nim, poprzedni podgląd zostaje usunięty. Niepowodzenie
przełączenia pozostawia przygotowanie transferu zablokowane.

Odczyty i podpis mają niezależne ścieżki: `wallet-portal/read-rpc.mjs` używa
stałych publicznych RPC Base/Ethereum, sprawdza chain ID przed każdym odczytem,
ogranicza metody do odczytu/symulacji, a `eth_call` wyłącznie do kanonicznego
cbBTC `balanceOf`. Żądania mają limit czasu, rozmiaru, brak cookies, przekierowań
i automatycznych ponowień. RPC nie ma metody wysłania lub podpisania transakcji.
Adres źródłowy i dane symulacji trafiają do wybranego publicznego RPC; serwer
lokalny nie jest proxy. Portfel nadal niezależnie potwierdza konto i sieć oraz
jest jedyną ścieżką podpisu użytkownika. Błąd odczytu ETH/tokena/estymacji/ceny gas
ma osobny stały komunikat, bez prywatnych szczegółów błędu dostawcy. Niedostępność
źródła nie pozwala pominąć sprawdzenia i odblokować podpisu.

Etap ostatniej próby jest jawny w pamięci sesji (`lastAttempt`) i na ekranie:
preflight, oczekiwanie na portfel, zwrócony hash, odmowa albo nieznany wynik.
Zapis obejmuje wyłącznie etap, czas i informację, czy wywołano żądanie wysyłki;
nie zawiera adresów, sekretów ani surowych błędów dostawcy. Obserwator UI nie może
zmienić przebiegu wysyłki przez zgłoszenie wyjątku. Dowolny błąd **przed**
`eth_sendTransaction` czyści podgląd i raportuje niewykonaną próbę wysyłki.
Po wywołaniu portfela nieznany wynik nadal blokuje powtórzenie; poprawka nie
rozstrzyga wstecznie starych błędów ani nie resetuje istniejącego stanu UNKNOWN.
Zniknięcie powiadomienia na telefonie nie jest dowodem wykonania ani anulowania.
Wygasła konfiguracja nie jest automatycznie odnawiana. Przy braku hash i
nieznanym wyniku najpierw należy uzgodnić stan portfela/odbiorcy oraz zakończyć
starą prośbę w portfelu; nie obchodź blokady przez odświeżanie lub nową sesję.

## Prywatne salda i zarejestrowane zdarzenia

Serwer przyjmuje opcjonalne `--observations /prywatny/katalog/latest.json`.
`GET /observations` wymaga lokalnego Host i tego samego origin co `/session`,
ma `Cache-Control: no-store`. Zwraca 200 `AVAILABLE` lub `NOT_CONFIGURED`;
niepoprawny/nieczytelny plik daje 503 `UNAVAILABLE` bez treści błędu i ścieżek.
Endpoint nie wywołuje Coinbase ani RPC. Zmiana pliku nie wymaga restartu.

Publikowanie odczytu (pliki 0600, katalog 0700):

```sh
python -m scripts.panel_observations --watchlist /private/watch.json \
  --exchange-capture /private/capture.json \
  --registered-transfers /private/cases.json --output-dir /private/observations
```

Capture ma format `COINBASE_CONNECTOR_READ_ONLY_CAPTURE` opisany w dokumentacji
operacyjnego odczytu. CLI nie uwierzytelnia Coinbase: pochodzenie odczytów
z autoryzowanego konektora deklaruje operator. Nigdy nie umieszczaj kluczy w pliku.
CLI sprawdza zgodność portfeli, paginację, dostępne salda i uzgodnienie pozycji.
Zakres ogranicza się do portfeli w capture; nie poświadcza wszystkich kont.

Plik cases ma dokładnie `mode: PRIVATE_REGISTERED_TRANSFERS_V1` oraz `cases`:
lista do 20 obiektów z `chain_id`, pełnym `tx_hash`, `asset` (ETH/cbBTC),
`amount` (łańcuch dziesiętny), `recipient`, `operator_credit_link` (bool),
`operator_asserted_at_utc` (UTC). Jeden przypadek na sieć/hash. Powiązanie wpłaty
jest deklaracją operatora; saldo dostępne nie dowodzi konkretnej wpłaty.
To historia zarejestrowanych przypadków, nie indeks całej historii portfela.
cbBTC wymaga kanonicznego logu Transfer; ETH obsługuje tylko bezpośredni transfer
natywny. Transfer ETH wewnątrz bundla pozostaje nieudowodniony.

CLI zapisuje niezmienne migawki i atomowo podmienia latest.json. Uzgodnienie
sieci sprawdza receipt, hash bloku, kwotę, źródło, odbiorcę i finalized head.
Kopie nie są kryptograficznym dowodem pochodzenia pliku i wymagają ochrony lokalnej.
Odczyty giełdy i portfela wygasają po 15 minutach, czas bloku po 30 minutach;
przeterminowane salda są ukryte. Historyczne potwierdzenie sieci pozostaje z czasem
weryfikacji. Brak danych nie jest zerowym saldem. Nie sumujemy sald i zdarzeń;
przy nakładaniu czasów sald panel pokazuje ostrzeżenie, bez wspólnej wyceny.

Kody CLI: `0` oznacza świeże skonfigurowane salda i odczytaną sieć dla wszystkich
zarejestrowanych przypadków; `3` oznacza zapisaną migawkę częściową (źródło
niedostępne lub przeterminowane); `2` oznacza odrzucone wejście lub błąd publikacji.
`quality=COMPLETE` dotyczy wyłącznie tego zakresu odczytu, nie całej historii,
udowodnienia wpłat ani wszystkich aktywów. Stan PENDING/REVERTED jest prawidłowym
wynikiem odczytu sieci, nie zapewnieniem powodzenia transferu.

Przycisk odświeżenia i odczyt co 30 sekund wczytują lokalny plik. Nie odnawiają
sesji Coinbase, capture ani danych RPC. Operator musi pozyskać nowy autoryzowany
odczyt i ponownie uruchomić CLI. Czas pobrania jest jawny; źródłowy czas danych
Coinbase pozostaje nieznany. Uruchomienie bez polityki transferowej daje panel
wyłącznie odczytowy. Wycofanie: uruchom serwer bez `--observations`; zachowaj
prywatne migawki audytowe według własnych zasad retencji.
