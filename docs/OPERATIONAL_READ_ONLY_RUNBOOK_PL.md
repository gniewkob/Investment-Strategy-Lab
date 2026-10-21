# Operacyjny monitoring odczytowy — operator i handoff, 2026-10-21

## Stan i granice

Bazą jest rzeczywisty `main` po PR #59, commit
`68ca2c235ca39f40d53dcaf857eeee5c853c3195`.
Nowy moduł: `python -m scripts.operational_read_only` (Python 3.12+, POSIX).
Zachowuje dotychczasowe trzy monitory bez zmiany ich kontraktów.

To działający **jednorazowy CLI**, nie uruchomiony daemon ani harmonogram.
Nie ma wykonywania operacji finansowych, podpisów, zleceń, swapów, transferów,
zmian uprawnień/kluczy ani zapisu do Neon. Ograniczenie to jest bezwzględne.
Odczyt salda nie jest uprawnieniem do jego przeniesienia.

| Bramka | Dowód / ograniczenie z tej sesji |
|---|---|
| Coinbase — autoryzowany odczyt | PASS: istniejący konektor zwrócił listę, breakdown i salda jednego autoryzowanego portfela; dane prywatne nie są w Git |
| Coinbase → CLI | PASS: rzeczywisty capture przeszedł normalizację i CLI; CLI nie uwierzytelnia się sam do Coinbase |
| Wallet Ethereum/Base | PASS: wspólny rzeczywisty raport CLI z ETH i jawnym kontraktem cbBTC obu sieci, sfinalizowane bloki, bez adresów kont w wyniku |
| Historia Ethereum | PASS dla małego zakresu (ostatnia próba: 10 sfinalizowanych bloków); nie dowodzi kompletności wcześniejszych zdarzeń |
| Historia Base | PENDING: publiczne RPC odrzuciło odczyt logów HTTP (także 429 w ponownej próbie); saldo odczytano niezależnie |
| Historia wpłat/wypłat Coinbase | PENDING: dostępny konektor nie wystawia tej operacji; fills nie zastępują historii transferów |
| Uzgadnianie transferów | PASS offline dla syntetycznych par; PENDING live, brak autoryzowanej historii obu stron |
| Coinbase publiczne OHLCV + NBP | PASS: rzeczywiste pobranie trzech zakresów 72h i datowanego USD/PLN przez istniejące moduły |
| Testy | 384 offline testów PASS w Pythonie 3.12 z istniejącą zależnością psycopg; w tym 20 nowych testów, subprocess CLI i wspólna ścieżka CLI z kontrolowanym RPC |
| Pełna wycena majątku / P&L | UNKNOWN: brak pełnej enumeracji tokenów, DeFi/NFT, innych sieci i historycznych kosztów; nie wyliczamy pełnego USD total |

Udany odczyt sald obu sieci użył sfinalizowanych bloków Ethereum **26239845**
(czas bloku **2026-10-21T08:41:59Z**) i Base **52891368**
(**2026-10-21T08:41:23Z**). To dowód próby z tego dnia, nie stale aktualne saldo.
Późniejszy błąd API nie unieważnia wcześniejszego odczytu, ale nie jest nowym odczytem.

## Kontrakt prywatnego capture Coinbase

Host agent korzysta wyłącznie z istniejących autoryzowanych odczytów:

1. `coinbase_portfolios_list`: zachowaj całą listę dostępnych portfeli.
2. Dla każdego aktywnego UUID: `coinbase_portfolios_get`, `currency=USD`.
3. Dla tego samego UUID: `coinbase_balance`, `limit=250`, `show_zero=true`.
   Przechodź po `cursor` aż `has_next=false`. Nie powtarzaj kursora.
   Konektor czasem pomija flagę końca: wtedy wymagane są `size`, zgodna liczba
   kont `<250` i brak kursora; nie zgaduj kompletności pełnej strony.
4. Zapisz poniższą kopertę **prywatnie, poza checkoutem**, mode 0600,
   w katalogu 0700. Nie zapisuj odpowiedzi w PR, logach Actions ani OpenBrain.
   Używaj czasu UTC faktycznego pobrania; nie odmładzaj archiwalnej kopii.

```json
{
  "mode": "COINBASE_CONNECTOR_READ_ONLY_CAPTURE",
  "captured_at": "[UTC_RETRIEVAL_TIME]",
  "portfolios": [{"uuid": "[PORTFOLIO_ID]", "deleted": false}],
  "reads": [{
    "portfolio_id": "[PORTFOLIO_ID]",
    "breakdown": "[OBJECT_FROM_PORTFOLIOS_GET]",
    "balance_pages": ["[OBJECT_FROM_EACH_BALANCE_PAGE]"]
  }]
}
```

Placeholdery oznaczają obiekty odpowiedzi, nie literalne stringi w realnym wejściu.
Przykład kompletnych syntetycznych obiektów jest w
`tests/test_operational_read_only.py::capture`.

Capture jest **deklaracją operatora**, nie podpisanym dowodem autentyczności.
CLI sprawdza strukturę, pokrycie UUID, unikalność kont i zgodność wartości,
nie autentyczność źródła. Limit świeżości capture: 15 minut.
Konektor nie podaje czasu źródłowego salda: `source_as_of_utc=null`, a czas
pobrania pozostaje osobnym polem. Nie nazywaj go czasem księgowania.
Nie ma nowej konfiguracji OAuth/API keys ani kopiowania sekretów.

Nie sumuj `balance.available/hold` z `portfolio_balances`: pierwszy to osobny
widok ilości dostępnych/zablokowanych, drugi obejmuje także staking.
Każdy portfel uzgadniany jest osobno; powtórzone ID pozycji/konta powodują błąd.
Portfele z akcjami lub futures są jawnie nieobsługiwane, zamiast pomijane w sumie.

## Prywatny watchlist i CLI

Format watchlist jest zgodny z `private_wallet_chain_monitor`:
`mode=PRIVATE_WALLET_READ_ONLY`, tablica `watch` z `label`, `chain_id`, `address`,
`verified_token_contracts`. Adres podaje operator lokalnie, nigdy w repo.
Sieci: Ethereum 1 i Base 8453. Wbudowany rejestr zawiera cbBTC
`0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf`, 8 miejsc dziesiętnych,
osobno dla obu sieci. Inny kontrakt wymaga osobnej weryfikacji i testów.
ETH jest aktywem natywnym. Brak wykrywania wszystkich tokenów: SHIK i inne
niepotwierdzone kontrakty nie są deklarowane jako zweryfikowane ani wycenione.

```bash
# Katalog i pliki wejściowe przygotowane lokalnie, bez sekretów.
# Podstaw właściwe ścieżki prywatnych wejść; nowa nazwa wyniku przy każdym odczycie.
python -m scripts.operational_read_only \
  --exchange-capture /PRIVATE_DIR/exchange.portfolio-private.json \
  --wallet-watchlist /PRIVATE_DIR/watch.wallet-private.json \
  --public-markets \
  --output /PRIVATE_DIR/report-NEW.private-wallet.json

# Historia to opcjonalny zakres 1..1000 sfinalizowanych bloków.
# Błąd historii przerywa cały ten raport, nie tworzy pozornej kompletności.
python -m scripts.operational_read_only \
  --wallet-watchlist /PRIVATE_DIR/watch.wallet-private.json \
  --history-blocks 100 \
  --output /PRIVATE_DIR/history-NEW.private-wallet.json
```

Opcjonalny tryb odporny na niedostępną historię:

```bash
python -m scripts.operational_read_only \
  --exchange-capture /PRIVATE_DIR/exchange.portfolio-private.json \
  --wallet-watchlist /PRIVATE_DIR/watch.wallet-private.json \
  --history-blocks 10 --allow-partial-history --public-markets \
  --output /PRIVATE_DIR/report-PARTIAL-NEW.private-wallet.json
```

`--allow-partial-history` zachowuje odczytane salda przy błędzie pobrania lub
weryfikacji historii tokenów. Zawsze ponownie weryfikuje blok salda; zmieniony
hash, zła sieć lub niepoprawny zakres nadal przerywają raport.
Niedostępna historia ma `status=UNAVAILABLE`, `event_count=null`, a nie zero.
Raport ma `PRIVATE_READ_ONLY_PARTIAL_OBSERVATION` i kod wyjścia **3**;
uzgadnianie zawiera `wallet_history_coverage=PARTIAL`. Brakujące zdarzenia
pozostają UNKNOWN. Domyślne zachowanie bez flagi nadal przerywa raport.
Nie pomijaj kodu 3 w skryptach operatora. Ten tryb nie maskuje błędów sald,
źródeł rynkowych, konfiguracji ani nie nadaje uprawnień do transferu.

Zweryfikowana próba live nowego trybu (2026-10-21) zachowała odświeżony odczyt
Coinbase, salda Ethereum/Base, trzy zakresy OHLCV i NBP. Historia ostatnich
10 bloków Ethereum została odczytana; historia Base była UNAVAILABLE.
Raport zapisano prywatnie z uprawnieniami 0600 i kodem wyjścia 3.

Bez `--history-blocks` pobierane są tylko salda. Bez `--public-markets` nie ma
żądań OHLCV/NBP. Osobne próby pozwalają badać źródła niezależnie.
`--at` służy tylko replay offline capture, zabronione przy live wallet/market;
raport oznacza taki zegar `OFFLINE_REPLAY`.

Wyjście stdout jest stałym komunikatem, bez sald, adresów, ID i ścieżek.
Exit 0 = zapisano raport w zadeklarowanym zakresie, **nie** pełny majątek;
exit 2 = błąd, nie powstał kompletny raport; exit 3 = zapisano jawny raport częściowy z brakującą historią. Nie włączaj traceback/raw HTTP.
Pliki są wrażliwe mimo braku adresu konta: zawierają salda, bloki, a historia
hash transakcji. Nie publikuj ich ani ich fingerprintów jako „anonimowych”.
Katalog właściciela 0700, wejścia i nowe wyniki 0600, odrzucenie symlinków
plików i nadpisywania. To ochrona lokalna, nie szyfrowanie ani backup.

## RPC, czas i odporność

Allowlista sieci i pięciu metod odczytowych. `eth_call` dopuszcza tylko
`balanceOf` dla kontraktu rejestru — nie dowolne wywołania kontraktów.
Weryfikacja chain ID, `finalized`, numeru/hash/czasu bloku, jawny numer bloku
do wszystkich odczytów sald oraz ponowna kontrola hash na końcu.
Zbyt stary blok (>30 min) przerywa próbę. To stan zgłoszony przez dostawcę,
nie niezależna walidacja konsensusu ani bieżący niesfinalizowany tip.

Timeout 15 s/żądanie, maksymalnie 3 próby, ograniczony rozmiar odpowiedzi,
backoff dla 429/5xx i wybranych błędów pojemności RPC. `Retry-After` liczbowy
lub data HTTP: respektowany do 30 s; większy powoduje przerwanie, bez ponowienia
przed zadanym terminem. 401/403 nie ponawiamy jako błędu przejściowego.
Redirecty blokowane przed wysłaniem kolejnego żądania. Komunikaty błędów RPC
nie trafiają do stdout. Brak fallbacku do niesfinalizowanego `latest`.

## Historia i uzgodnienia

Logi tylko `Transfer` z potwierdzonego kontraktu ERC-20 i skonfigurowanego konta,
w zadanym przedziale. Walidacja topiców, chain/kontraktu, block/log index,
braku `removed`; deduplikacja `(chain, txhash, logIndex)` w obrębie walleta.
Każda strona logu zachowuje lokalną `wallet_label` i ID zależne od tej etykiety,
więc transfer między dwoma obserwowanymi walletami nie przerywa uzgodnienia.
Etykiety powinny być stabilne i nieidentyfikujące; nie są dowodem własności. Nie ma pełnej historii
natywnych transferów/internal calls/NFT/DeFi. Czas zdarzenia pochodzi z jego konkretnego bloku, którego numer i hash muszą
zgadzać się z logiem. Powtarzane bloki są odczytywane raz; maksymalnie 100 bloków
dowodowych (wliczając blok końcowy) na wallet w pojedynczym raporcie.
Brak lub niespójność dowodu czasu/hash przerywa historię; przy jawnej fladze
raport częściowy zachowuje tylko zweryfikowane salda. Nie zastępuj czasu
historycznego bloku czasem pobrania ani czasem bloku końcowego.

Opcjonalny `--exchange-events` przyjmuje **prywatny eksport już zaobserwowanych**
zdarzeń: `mode=PRIVATE_OBSERVED_EXCHANGE_EVENTS`, `events=[...]`.
Każdy event: `event_id`, `chain_id`, `tx_hash`, `contract` (`NATIVE` lub rejestr),
`quantity` (string), `direction` (`in|out|self`), `confirmed` (bool),
`location=exchange`. Syntetyczne przykłady są w testach. To format obserwacji,
nie format żądania transferu; CLI nie potwierdza autentyczności eksportu.

Uzgodnienie tylko dla unikalnej pary exchange+wallet o tym samym chain, txhash,
kontrakcie, dodatniej ilości i przeciwnych kierunkach, potwierdzonej po obu stronach.
Brak dopasowania/więcej niż dwa rekordy = pozostaje nierozstrzygnięte.
Nie zgadujemy opłat, relacji BTC↔cbBTC ani przepływu z samej równości kwot/czasu.
Brak dopasowania nie oznacza zewnętrznego zasilenia. Zdarzenia nigdy nie są
dodawane do aktualnych sald. Pełne funding/P&L nadal UNKNOWN.

## Kontrola, rollback i kolejny operator

- Testy: `python -m unittest discover -s tests -v` po instalacji istniejącej
  zależności CI `psycopg[binary]>=3.2,<4` w izolowanym środowisku.
- CI istniejącego workflow `read-only-portfolio-monitor.yml` obejmuje nowe pliki;
  brak prywatnych danych, sekretów, nowych zadań cyklicznych i artefaktów konta.
- Rollback: odwrócenie commitu PR usuwa nowy CLI; stare trzy monitory bez zmian.
  Prywatne pliki zachowuje/kasuje operator lokalnie zgodnie ze swoją retencją.
- Następny agent: zweryfikuj bieżący main/PR/CI, wykonaj tylko autoryzowane odczyty;
  najpierw odśwież capture, nie przepisuj jego czasu. Zbadaj dostępność historii
  bez zmiany kont, kluczy ani uprawnień. Jeśli potrzebne są nowe uprawnienia,
  pozostaw tę bramkę PENDING. Nie uruchamiaj transakcji ani usług cyklicznych.
- Trwały handoff OpenBrain_remote `build`: tylko kod, PR/CI, zakres prób i bramki;
  bez portfeli, pozycji, adresów, hashy transakcji czy prywatnych plików.

Źródła kontraktów: [Coinbase cbBTC](https://www.coinbase.com/es-es/cbbtc),
[Ethereum JSON-RPC](https://ethereum.org/en/developers/docs/apis/json-rpc/),
[Base public RPC](https://docs.base.org/base-chain/quickstart/connecting-to-base),
[Coinbase portfolios](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/portfolios).
Orbit search/integrate dał tylko częściowe pokrycie i wskazał inne produkty
Coinbase (International/Prime); tych endpointów nie użyto jako zamiennika
Advanced Trade. Użyto kontraktu faktycznie dostępnego konektora i istniejących
walidowanych źródeł publicznych.
