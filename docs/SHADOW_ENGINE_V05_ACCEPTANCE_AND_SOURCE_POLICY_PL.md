# Investment Strategy Lab — Shadow Decision Engine v0.5: odbiór i plan

**Data odbioru: 6 listopada 2026. Status: PASS dla niezależnego silnika papierowego i odczytu archiwum; BLOCKED dla rzeczywistej oceny skuteczności inwestycyjnej i niekompletnych źródeł globalnych.**

## 1. Cel i izolacja

Shadow Engine rozwija **silnik decyzyjny równolegle z adapterami źródeł**. Nie potrzebuje kompletnego globalnego indeksu, żeby codziennie wytworzyć poprawny i idempotentny *receipt*: czy dostępne dane mogą zasilić hipotetyczny model, czy trzeba przejść na `HOLD_CASH`. Nie zapisuje do Neon ani do portfeli i **nie uruchamia nawet papierowych zleceń**.

- `scripts/shadow_decision_engine_v05.py`: walidator i deterministyczny model **M1/M2/M3**.
- `scripts/shadow_forward_evaluation_v05.py`: osobna ocena **kolejnego** okresu obserwacji względem wcześniej zamrożonego hipotetycznego celu; żadnego look-ahead.
- `tests/test_shadow_decision_engine_v05.py`: 10 syntetycznych testów zabezpieczeń i decyzji.
- `tests/test_shadow_forward_evaluation_v05.py`: 8 syntetycznych testów ewaluacji przyszłego okresu.
- `.github/workflows/shadow-source-receipt-v05.yml`: niezależny automatyczny test na rzeczywistym utrwalonym archiwum NBP/TBSP.
- `.github/workflows/working-engine-v01-ci.yml`: regresja wszystkich istniejących funkcji i nowych modułów.

## 2. Predeklarowane reguły modeli

| Model | Wymagana seria | Wyłącznie hipotetyczny cel |
|---|---|---|
| M1_GLOBAL_EQ | GLOBAL_EQUITY_TR_PLN | 100% equity |
| M2_DIVERSIFIED | Equity + PL_BONDS_TR_PLN + GOLD_TR_PLN | 60% equity, 30% bonds, 10% gold |
| M3_TACTICAL | Te same trzy serie i historia 3 mies. | Momentum risk-on: 60/30/10; risk-off: 30/30/10 plus 30% cash |

**To cele edukacyjnej symulacji**, nie rekomendacje zakupowe ani transakcje. Model M1 może być poddawany badaniu samodzielnie, jeśli kiedyś otrzyma pełny zweryfikowany equity TR, nawet gdy źródła dla M2/M3 są nadal niekompletne. Nie oznacza to możliwości realnego handlu po cenie indeksu.

## 3. Każda seria musi przejść niezależne bramki

- Co najmniej 36 kolejnych miesięcy datowanych obserwacji, najnowsza nie starsza niż 45 dni.
- Waluta PLN, deklarowany `TOTAL_RETURN` i `NON_EXECUTABLE_BENCHMARK`.
- Surowy hash SHA-256, publiczny URL HTTPS, daty obserwacji i zadeklarowane `first_usable_at`.
- `source_status=VERIFIED_ORIGINAL`, `rights_status=RESEARCH_USE_DOCUMENTED` i właściwy kod serii.
- Brak luk, duplikatów, przyszłych notowań lub rzekomych publikacji po momencie hipotetycznej decyzji.
- Jeżeli bramka odpada, jedyną decyzją jest `HOLD_CASH` ze wskazaniem przyczyn. Nie podstawiamy wskaźnika referencyjnego pod brakującą serię total return.

**Ograniczenie fundamentalne:** statusy w źródłowym manifeście to tylko deklaracje wejściowe; kod nie weryfikuje prawnie licencji ani niezależnie nie poświadcza historycznej pierwszej chwili publikacji danych. Pola `historical_pit_certified`, `provider_license_independently_certified` i `profitability_proven` pozostają `false`.

## 4. Faktyczny test 60 miesięcy na oficjalnych archiwach

[GitHub Actions — shadow real-source receipt #42296514741](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42296514741): **SUCCESS**.

Workflow pobiera zachowany artefakt z [rzeczywistego audytu NBP/TBSP #42255251036](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42255251036) i dodatkowo sprawdza oryginalny fingerprint dokumentu, kompletność 60 miesięcy oraz ścisły brak możliwości podszycia się pod equity total return. Kończy się potwierdzeniem:

- `SHADOW_REFERENCE_OBSERVATION_ONLY`, 60 miesięcy 2021-11 do 2026-10;
- M1, M2, M3: `HOLD_CASH`, ponieważ referencje NBP złoto (PRICE_ONLY), USDPLN (FX_RATE) i BondSpot TBSP.Index (NON_TRADABLE_INDEX) nie wypełniają kontraktu trzech inwestowalnych serii total return;
- 0 zleceń, 0 wirtualnych fill, 0 zapisów do bazy.

Zapisany artefakt `isl-v05-shadow-real-reference-receipt` zawiera **tylko podsumowanie i hashe**, nie surowe kwotowania; ma ograniczoną retencję GitHub.

## 5. Forward-only ewaluacja jako drugi strumień rozwoju

Po zamrożeniu celu silnik zapisuje fingerprint źródeł i hash ostatniego poziomu referencyjnego, nie wymagając publikacji surowych historycznych notowań. Kolejna obserwacja z **następnego miesiąca** musi zweryfikować ten punkt odniesienia oraz datę dostępności — inaczej test się zatrzymuje. Dla modelu, który pozostawał w `HOLD_CASH`, **nie produkuje stopy zwrotu z nieistniejącej pozycji**.

Dopiero prawidłowy kolejny zestaw `TOTAL_RETURN` i `NON_EXECUTABLE_BENCHMARK` pozwala obliczyć *hipotetyczną* zmianę wartości referencyjnej, z jawnie **założonymi**, niezmierzonymi opłatami i poślizgiem. Nie powstaje fill. Pojedynczy miesiąc nie może generować Sharpe, max drawdown ani wniosku o statystycznej przewadze. Testy tej ścieżki są **syntetyczne**, a nie wynikiem istniejącego portfela.

## 6. Równoległy backlog źródeł — polityka kwalifikacji

| Źródło | Rzeczywisty status | Dozwolona rola |
|---|---|---|
| Oficjalne NBP | 60 miesięcy PASS | FX_RATE i GOLD PRICE_ONLY |
| Oficjalny BondSpot TBSP.Index | 60 miesięcy PASS | Referencja indeksu, nie zakup obligacji |
| Vanguard accumulating NAV | BLOCKED za deklaracją dostępu | Nie używać jako potwierdzonego equity TR |
| World Bank GEM World stock | 0/60 dla dwóch kodów, BLOCKED | Badania dostępności, nie globalny benchmark |
| WorldPulse.ai NAV JSON/CSV | Powtarzalne `URLError`, BLOCKED | Wyłącznie audyt źródła, bez danych |
| Kopie/synchronizacje i proxy akademickie | Kandydat, praw i kompletności nie potwierdzono | Tylko po niezależnym źródłowym/kontraktowym audycie |

**Mirrory są dopuszczalne do badawczego porównania dopiero po:** ustaleniu łańcucha pochodzenia i wartości oryginalnych, sprawdzeniu dat oraz hashy, praw do odczytu i utrwalania konkretnej serii i zgodności definicji ekonomicznej. Sposób hostowania nie usuwa ograniczeń praw autorskich źródła pierwotnego.

Powtarzane nieskuteczne testy sieciowe WorldPulse zostały wyłączone z automatycznego PR CI; testy offline pozostają aktywne. Nie uznajemy `SUCCESS` zadania audytu za `PASS` dostępności serii.

## 7. Dowody i decyzja o następnym etapie

[Regresja #42297162110](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42297162110): **165/165 PASS** dla ukończonej wersji silnika i ewaluatora. Wyniki testów strategii i kosztów to syntetyczne potwierdzenie mechaniki, nie dowód przyszłej skuteczności.

Najbliższe zadania: (a) dopracować jeden niezależnie licencjonowany, automatyczny globalny/rozwojowe+wschodzące indeks do badania, nie mieszając nazw serii; (b) rozpocząć wielookresowe, prospektywne archiwizowanie `decision receipts`, a następnie ewaluować je na późniejszych obserwacjach; (c) osobno badać wrażliwość wyników na koszty, zmiany reżimu i jakości źródeł. Bez prospektywnej historii OOS nie deklarować Sharpe ani przewagi.

**Neon LAB main, scheduler v0.3, istniejące paper_events i rachunki — bez zmian. Nie ma produkcji ani realnych operacji finansowych.**
