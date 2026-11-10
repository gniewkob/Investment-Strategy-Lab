# Investment Strategy Lab — Stage 0: EODHD, źródła instrumentów i decyzja GO/NO-GO

**Data analizy:** 2026-11-10  
**Zakres:** publiczne metadane, regulaminy i identyfikacja instrumentów do **edukacyjnej symulacji**; zero integracji API, rzeczywistych historycznych cen, zleceń, transferów, zapisów DB i płatności.  
**Powiązania:** Issue [#117](https://github.com/gniewkob/Investment-Strategy-Lab/issues/117), [#116](https://github.com/gniewkob/Investment-Strategy-Lab/issues/116), [#97](https://github.com/gniewkob/Investment-Strategy-Lab/issues/97), [Draft I7 #115](https://github.com/gniewkob/Investment-Strategy-Lab/pull/115).

## 1. Decyzja

- **GO — dokumentacja/metadane:** EODHD jako **kandydat do prywatnej, wyłącznie badawczej** retrospektywnej analizy EOD. To nie jest autoryzacja indywidualnego użytkownika ani projektu.
- **NO-GO — automatyczny ingest:** brak zweryfikowanego zakresu uprawnień dla konkretnego zastosowania, brak potwierdzenia, że EODHD posiada wszystkie trzy wskazane instrumenty i wymagane obserwacje. **Nie tworzyć tokena, konta, subskrypcji, API fetchera ani harmonogramu w ramach tego etapu.**
- **NO-GO — historyczne PIT:** EODHD jasno opisuje brak wersjonowanej historii stanu na dany dzień; nowe corporate actions i korekty zmieniają historyczne wartości. Dzisiejszego `adjusted_close` nie wolno opisywać jako historycznego `as-of`.
- **NO-GO — kwalifikacja M1–M3:** nadal `QUALIFIED_SERIES=0`, `INSUFFICIENT_DATA/HOLD_CASH`; brak przejścia z metadanych do C1, żadnego sygnału finansowego.

To jest decyzja **projektowa** na podstawie publicznych deklaracji dostawcy, nie porada prawna ani potwierdzenie, że użytkownik ma uprawnienia do usługi.

## 2. Prawa, ograniczenia, metodyka — pierwotne źródła

| Roszczenie / kontrola | Źródło, sekcja | Co faktycznie wspiera | Co nadal nieudowodnione |
|---|---|---|---|
| Prawo do prywatnej analizy | [EODHD Terms](https://eodhd.com/financial-apis/terms-conditions), **PERSONAL AND COMMERCIAL USE OF INFORMATION, §1 Personal Use**; [FAQ Personal use](https://eodhd.com/help/personal-use), „private research, backtesting or paper-trading” | Uprawniony pojedynczy użytkownik niekomercyjny może lokalnie przechowywać, przeliczać i analizować dane dla siebie; nie może przekazywać ich ani dostępu innym | Kwalifikowalność konkretnego użytkownika/konta, warunki konkretnych danych giełdowych, zakres zastosowania poza prywatnym badaniem |
| Prywatna automatyzacja i AI | [EODHD AI tools FAQ](https://eodhd.com/help/ai-tools), sekcje „cloud server”, „private software”, „automate downloads”, „publish source code” | Zgodnie z FAQ prywatne AI/VPS/automatyzacja są dopuszczone w ramach odpowiedniego planu i limitów, gdy dostęp i wyniki pozostają **wyłącznie u jednego uprawnionego użytkownika** | Prawo do publicznego dashboardu, wieloosobowego agenta, publikowania wyników zawierających dane i pobierania w ramach obecnego projektu |
| Retencja | [EODHD Storage FAQ](https://eodhd.com/help/storage), „store locally”, „after cancel or downgrade”, „derived results” | Prywatny użytkownik może zachować uprawnione pobrane dane oraz własne analizy do własnego użycia; zakaz redystrybucji pozostaje | Zezwolenie na wrzucenie tych wartości do publicznego GitHub, CI artifacts, publicznych promptów czy współdzielonej bazy |
| Historia i plan | [EODHD Plans FAQ](https://eodhd.com/help/plans), „Which personal plan”, „complete history” | Free = **1 rok EOD**, nie 36–72 miesięcy; płatny opis „full history” **nie gwarantuje** pokrycia każdego symbolu | Faktyczne 36/60/72 miesiące dla trzech instrumentów oraz dopasowanie pól i dywidend |
| Data semantics | [EODHD Methodology FAQ](https://eodhd.com/help/methodology), „Are open/high/low/close adjusted?”, „Can historical data be corrected?”, „Is the data versioned?” | `close` = surowa cena EOD; `adjusted_close` przelicza splity i dywidendy, także wstecz; vendor przechowuje aktualną wersję, **nie historyczne vintage**, i może korygować rekordy bez znacznika zmian | Historyczna `first_available_at`, brak look-ahead, pełna rynkowa wykonalność ceny i zgodność korekt z metodologią modeli |
| Granice symboli | [EODHD EOD API](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes), „Symbols, Exchanges and History Depth”; [Exchanges API](https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours) | Schemat `SYMBOL.EXCHANGE` z **kodem giełdy dostawcy**, nie zawsze MIC; listy symboli i zakres planu muszą być zweryfikowane | Konkretny `EODHD_SYMBOL` przypisany do każdego ISIN — brak potwierdzenia, nie wolno go zgadywać |

**Ważne:** dostępność serii testowej/demo innego papieru **nie** dowodzi dostępności papierów docelowych. Nie wolno przedstawiać ceny „indicative” lub przeliczonej `adjusted_close` jako ceny wykonanego zlecenia. Osobny `first_observed_at` przyszłego snapshotu jest dowodem czasu **naszego pobrania**, nie dowodem pierwszej publikacji danych przez giełdę lub dostawcę.

## 3. Zamknięta lista kandydatów — identyfikacja u emitenta, nie w EODHD

| Cel edukacyjnego modelu | Przykładowy instrument, emitent i źródło | Zidentyfikowana klasa i notowanie | Stan w EODHD |
|---|---|---|---|
| Global equities — przybliżenie akcji globalnych (NIE MSCI ACWI NETR) | [Vanguard FTSE All-World UCITS ETF (USD) Accumulating](https://www.pl.vanguard/inwestorzy-indywidualni/produkt/etf/akcje/9679/ftse-all-world-ucits-etf-usd-accumulating), **ISIN IE00BK5BQT80** | FTSE All-World, akumulacja; USD share-class/NAV, różne waluty notowań. Przykład: **VWRA na LSE w USD** lub **VWCE na Xetra w EUR** (to ten sam ISIN, ale różne giełdowe szeregi) | `SYMBOL_NOT_VERIFIED`, `COVERAGE_NOT_VERIFIED`, `PIT_NOT_AVAILABLE` |
| Polish gov bonds — przybliżenie notowanego funduszu (NIE sam TBSP.Index) | [BETA ETF TBSP](https://betaetf.pl/nasze-fundusze), **ISIN PLBTBSP00012** | Ticker GPW **ETFBTBSP**, PLN, indeks odniesienia TBSP; fundusz nie jest samym indeksem, koszt/tracking difference oddzielny | `SYMBOL_NOT_VERIFIED`, `COVERAGE_NOT_VERIFIED`, `PIT_NOT_AVAILABLE` |
| Gold — cena zabezpieczonego złotem certyfikatu (NIE NBP gold price) | [Invesco Physical Gold ETC](https://www.invesco.com/uk/en/financial-products/etfs/invesco-physical-gold-etc.html), **ISIN IE00B579F325** | Fizycznie zabezpieczony certyfikat; waluta bazowa USD; możliwe różne giełdy i waluty handlowe. Nie utożsamiać ceny ETC z NBP referencyjną ceną złota | `SYMBOL_NOT_VERIFIED`, `COVERAGE_NOT_VERIFIED`, `PIT_NOT_AVAILABLE` |

Powyższa tabela jest **wyłącznie inwentaryzacją źródeł do porównawczej symulacji**, nie rekomendacją instrumentów lub instrukcją ich zakupu. Każda zamiana benchmarku indeksowego na notowany ETF/ETC oznacza zmianę semantyki i wymaga nowej wersji modelu, etykiety instrumentu i pomiaru różnic.

## 4. Wymagane warunki GO/NO-GO

| Gate | Definicja potwierdzenia | Status 2026-11-10 |
|---|---|---|
| G0: Tożsamość instrumentów | Oficjalne strony emitentów, ISIN, rodzaj i przykładowe notowanie | **PASS METADATA ONLY** |
| G1: Konkretny zakres użytkowania | Warunki EODHD + rzeczywisty, dopuszczony status użytkownika i planu, brak funkcji współdzielenia | **UNVERIFIED** |
| G2: EODHD instrument mapping | Niezależny, uprawniony katalog EODHD: `symbol`, `exchange`, `ISIN`, `currency`, typ instrumentu | **NOT CHECKED — NO PROVIDER API CALL** |
| G3: Pokrycie i kompletność | Faktycznie dostępne 36–72 pełne miesiące na każdy symbol, brak luk, korekt/missing delistings | **NOT CHECKED — NO MARKET DATA FETCH** |
| G4: Semantyka i prawa | `close` vs `adjusted_close`; zasady dywidend/splitów; koszt/proxy mismatch; brak redystrybucji | **PARTIAL, NOT QUALIFIED** |
| G5: Historyczne `as-of` | Źródło z niezależnym historycznym vintage albo jawne, ograniczone do **retrospective latest-vintage** badanie | **PIT CERTIFICATION NO-GO** |
| G6: Produkcyjna integracja/aktywa | Realne zlecenia, brokers, wallet, transfery | **NOT AUTHORIZED, OUT OF SCOPE** |

Dopóki G1–G5 nie są spełnione w jasno określonym, prywatnym badawczym zakresie, żadne z pól `qualified_source_available`, `historical_pit_certified`, `paper_candidates` nie może zmienić statusu tylko dlatego, że istnieje globalne API dostawcy.

## 5. Kolejne kroki

1. Utrzymać Issue #117 jako **BLOCKED FOR PROVIDER INGEST, RESEARCH DOCUMENTED**; nie kupować planu ani nie uruchamiać programu pobierającego pod pretekstem etapów 0–1.
2. Oddzielnie udokumentować rzeczywistą możliwość korzystania z EODHD zgodnie z konkretnym regulaminem i uprawnieniami; zakres publiczny/zespołowy wymaga innych praw niż prywatna analiza.
3. Po niezależnie zatwierdzonym zakresie wykorzystania zbadać **tylko metadane instrumentów** w uprawnionym kanale, przypinając `ISIN + giełda + trading currency`. Do tego czasu `EODHD_SYMBOL = UNKNOWN`.
4. Nie składać fałszywych obietnic pełnej historii; bez uprawnionych rzeczywistych obserwacji 36–72 miesięcy żaden model nie dostaje realnego backtestu. Retrospektywną serię oznaczać `LATEST_VINTAGE_RECONSTRUCTION`, nie `HISTORICAL_PIT_CERTIFIED`.
5. Wszystkie obecne dane i hashe oryginalnych dostawców trzymać poza publicznym repozytorium i workflow. I4, I5, I6, I7 i G1 pozostają bez zmian, a `main` i aktywa nie są dotykane.

**Decyzja końcowa Stage 0:** `RESEARCH_SOURCE_CANDIDATE_ONLY; NO_PROVIDER_INGEST; NO_HISTORICAL_PIT; QUALIFIED_MODEL_SERIES=0; HOLD_CASH`.
