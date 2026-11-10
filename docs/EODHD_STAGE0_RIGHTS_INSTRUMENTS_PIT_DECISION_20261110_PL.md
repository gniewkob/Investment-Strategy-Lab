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


## 6. Stage 1 — weryfikacja publicznego katalogu dostawcy (10.11.2026)

**Stan faktyczny:** publiczna dokumentacja EODHD opisuje wyszukiwanie po ISIN, lecz nie przedstawia pełnego zweryfikowanego przypisania naszych trzech ISIN do identyfikatorów dostawcy. Oficjalne [Search API](https://eodhd.com/financial-apis/search-api-for-stocks-etfs-mutual-funds) wymaga osobistego `api_token`, **nie działa z tokenem demonstracyjnym**, i zwraca tylko aktywne instrumenty; [Exchanges API](https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours) także wymaga tokena. Nie został wykonany ani jeden request API; **nie ma dowodu, że EODHD udostępnia te trzy konkretne szeregi**.

**Nie należy utożsamiać trzech różnych identyfikatorów:** (1) ISIN klasy instrumentu, (2) ticker + konkretna giełda i waluta z dokumentu emitenta, (3) kod `SYMBOL.EXCHANGE` używany przez EODHD. Wspólny ISIN może mieć notowania na różnych rynkach i w różnych walutach.

| ISIN emitenta | Potwierdzony wariant giełdowy, bez roszczenia wobec EODHD | Tożsamość instrumentu | Symbol i historia EODHD |
|---|---|---|---|
| `IE00BK5BQT80` | Vanguard `VWRA` — London Stock Exchange, USD; `VWCE` — Deutsche Börse, EUR. [Warianty notowania na stronie emitenta](https://www.pl.vanguard/inwestorzy-indywidualni/produkt/etf/akcje/9679/ftse-all-world-ucits-etf-usd-accumulating). | `ISSUER_CONFIRMED` | `UNVERIFIED` |
| `PLBTBSP00012` | BETA ETF TBSP `ETFBTBSP` — GPW, PLN. [Lista emitenta](https://betaetf.pl/nasze-fundusze). | `ISSUER_CONFIRMED` | `UNVERIFIED` |
| `IE00B579F325` | Invesco Physical Gold ETC `SGLD` — London Stock Exchange, USD. [Emitent](https://www.invesco.com/uk/en/financial-products/etfs/invesco-physical-gold-etc.html), [oficjalny opis rynków notowania](https://www.invesco.com/content/dam/invesco/emea/en/pdf/Invesco_Physical_Gold_ETC_Brochure_EN.pdf). | `ISSUER_CONFIRMED` | `UNVERIFIED` |

**Minimalny dowód od dostawcy, dopiero po niezależnie dopuszczonym dostępie:** z [Search API](https://eodhd.com/financial-apis/search-api-for-stocks-etfs-mutual-funds) uzyskać parę `Code`, `Exchange`, `Currency`, `ISIN`, `Type`, `isPrimary`; powiązać każdą parę z potwierdzonym ISIN emitenta. Gdy `ISIN` jest pusty, nie wystarczy podobna nazwa — potrzebne dodatkowe niezależne potwierdzenie. Następnie osobno sprawdzić, że wariant notowania ma 36–72 kompletne miesiące, właściwe dane o dywidendach/splitach i brak niewyjaśnionych luk; brak lub niezgodność mapowania oznacza `BLOCKED`.

Z [Exchanges API](https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours) wynika dodatkowo, że zapytanie po symbolach może pominąć nierozpoznany symbol bez błędu (HTTP 200); wymagane jest **jawne porównanie zbioru oczekiwanych i zwróconych identyfikatorów**. Sam status HTTP 200, brak błędu lub ticker podobny do zapisu giełdowego nie jest dowodem pokrycia. `Search API` zwraca tylko instrumenty aktywne, dlatego historyczne analizy muszą osobno rozważyć serie delistowane i zmiany symbolu.

### Warunki prawne i architektoniczne, potwierdzone w oficjalnym FAQ

[Warunki EODHD — PERSONAL AND COMMERCIAL USE OF INFORMATION](https://eodhd.com/financial-apis/terms-conditions) i [FAQ Personal Use](https://eodhd.com/help/personal-use) ograniczają niekomercyjną licencję do właściwego użytkownika indywidualnego działającego dla siebie. [FAQ AI/Cloud](https://eodhd.com/help/ai-tools) wyjaśnia, że prywatne AI lub VPS i publikacja **samego kodu** są dopuszczone w określonym zakresie, lecz nie wolno wystawiać pobranych danych, tokenów ani raportów zawierających te dane innym osobom. [FAQ Storage](https://eodhd.com/help/storage) potwierdza możliwość przechowania pobranych danych do dozwolonego prywatnego użytku; to **nie** daje prawa do umieszczenia ich w publicznym repozytorium. Sam profil użytkownika, publiczna strona FAQ ani wcześniejsza zgoda na badania nie stanowią dowodu uprawnienia do usługi.

**Wykonalność zakresu:** [FAQ Plans](https://eodhd.com/help/plans) potwierdza dla Free tylko 12 miesięcy EOD; archiwum 36–72 miesięcy wymagałoby innego *dopuszczonego* zakresu i sprawdzenia każdej serii — bez założenia, że plan gwarantuje dostępność wszystkich instrumentów. Na tym etapie **nie uruchamiamy konta, rejestracji, subskrypcji, zakupów, API ani integracji**.

**Wniosek Stage 1:** `ISSUER_LISTINGS=3_CONFIRMED; EODHD_IDENTIFIERS=0_VERIFIED; AUTHORIZED_DATA_ACCESS=UNVERIFIED; HISTORICAL_MONTHLY_COVERAGE=UNVERIFIED; HISTORICAL_PIT=NOT_CERTIFIED; GO=DOCUMENTATION_ONLY; INGEST=NO_GO`. Nie budować pobierania cen, adaptera notowań ani pełnego backtestu na niezweryfikowanych nazwach.


## 7. Stage 2 — publiczne oficjalne dane bez płatnego feedu (10.11.2026)

**Decyzja:** równoległy tor otwartych statystyk może być rozwijany bez zakupów i bez integracji EODHD, ale wyłącznie jako **kontekst makroekonomiczny i obserwacje PRICE_ONLY**. Nie jest zamiennikiem benchmarków \`GLOBAL_EQUITY_TR_PLN\`, \`PL_BONDS_TR_PLN\`, \`GOLD_TR_PLN\`. Nie wykonano żadnego pobrania z API w tej zmianie; potwierdzono oficjalne metadane i warunki.

| Kandydat / semantyka | Oficjalne źródło | Granice praw i techniki | Decyzja projektowa |
|---|---|---|---|
| **OECD Share prices / PRICE_INDEX** | [OECD indicator: Share prices](https://www.oecd.org/en/data/indicators/share-prices.html); [Data Explorer: Financial market, \`OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0\`](https://data-explorer.oecd.org/vis?df%5Bag%5D=OECD.SDD.STES&df%5Bid%5D=DSD_STES%40DF_FINMARK&df%5Bvs%5D=4.0); [OECD Terms, §3 Data](https://www.oecd.org/en/about/terms-conditions.html) | Definicja OECD wyraźnie rozróżnia indeks **cen akcji** od return index z reinwestowanymi dywidendami. Publikowane dane mogą zawierać **prawa osób trzecich**; OECD wymaga sprawdzenia ich metadanych i ewentualnych odrębnych ograniczeń. Należy wybrać dokładny szereg i licencję przed pobraniem. Dodatkowo krajowy indeks ≠ globalny indeks akcji. | \`CONDITIONAL_OPEN_PRICE_INDICATOR\`; **nie** total return i **nie** M1–M3 input |
| **ECB / ESCB public statistics, FX i stopy** | [ECB policy on reuse of ESCB statistics](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.de.html); [ECB copyright/disclaimer](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html) | ECB pozwala na bezpłatne wykorzystanie **publicznie dostępnych statystyk z podaniem źródła**; obowiązuje zachowanie oryginalnej postaci publikowanych danych i dodatkowe warunki dla danych stron trzecich. Statystyki mogą podlegać rewizjom i nie dają certyfikatu historycznej dostępności w danym momencie. FX/stopy procentowe ≠ stopa zwrotu ETF. | \`CONDITIONAL_OPEN_MACRO_FX_CONTEXT\`; sprawdzić dokładny szereg i sposób prezentacji |
| **Eurostat / CPI, inflacja, stopy makro** | [Eurostat copyright and free re-use](https://ec.europa.eu/eurostat/help/copyright-notice); [Eurostat API docs](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction) | Eurostat zasadniczo dopuszcza ponowne wykorzystanie statystyk z atrybucją, także komercyjnie, **z enumerowanymi wyjątkami** (np. dane innych właścicieli / krajów). API dostarcza **najnowszą** wersję danych, bez oficjalnego archiwum historycznych wersji — ryzyko look-ahead przy retrospektywnej analizie. | \`CONDITIONAL_OPEN_MACRO_CONTEXT\`; nie traktować jako PIT |
| **FRED/ALFRED** | [FRED API Terms, Property Rights](https://fred.stlouisfed.org/docs/api/terms_of_use.html); [FRED API](https://fred.stlouisfed.org/docs/api/fred/) | FRED wymaga sprawdzenia praw właściciela **każdego** szeregu; samo udostępnienie przez Fed nie usuwa ograniczeń stron trzecich. ALFRED pozwala badać vintages dla wybranych danych, ale nie gwarantuje legalnego użycia cudzych indeksów ani ich dostępności. | \`METADATA_RESEARCH_ONLY\` do konkretnej kwalifikacji |
| **Stooq / notowania cenowe** | Oficjalna licencja, zakres automatyzacji i redystrybucji nie zostały tu niezależnie potwierdzone | Dostępność plików CSV lub nieoficjalny wrapper nie stanowią prawa do automatycznego pobierania i publikowania; dane cena-only nie obejmują pełnego TR ani PIT. | \`NO_AUTOMATED_INGEST_UNTIL_TERMS_CONFIRMED\` |

### Wykonalny zakres badań bez mylenia semantyki

1. **Kontekst:** publiczne OECD national share-price indicators, ECB FX i Eurostat CPI mogą być materiałem pomocniczym do badania reżimów rynkowych, wrażliwości inflacyjnej oraz jakości/rewizji danych. To **nie** daje danych do obliczenia zysku portfela w PLN.
2. **Wymagane metadane per seria:** \`source_authority\`, \`dataflow_id\`, \`series_key\`, \`measurement_type\` (PRICE_INDEX, FX_REFERENCE, CPI, POLICY_RATE), \`currency\`, \`frequency\`, \`original_publisher\`, \`third_party_rights_check\`, \`revision_policy\`, \`first_observed_at\`, \`citation\`; każda niewypełniona istotna pozycja daje \`RESEARCH_SOURCE_UNVERIFIED\`.
3. **Rozdział domen:** \`MACRO_CONTEXT_REFERENCE\` nie może być aliasem żadnego z \`*_TR_PLN\`, ani przekazywać się przez I4 jako kwalifikowany backtest lub bezpośredni kandydat C1. \`HOLD_CASH\` pozostaje.
4. **Brak zgody na samoczynny ingest:** nawet otwarte, oficjalne dane wymagają wyboru dokładnego szeregu, sprawdzenia praw stron trzecich, atrybucji i polityki historycznych rewizji. Nie uruchamiać cyklicznych zapytań tylko dlatego, że portal ma publiczne API.
5. **Granica efektu:** w obecnym repo najbardziej uczciwy rezultat to **jawna mapa źródeł i kryteria dostępu**, dopóki nie ma odpowiednio uprawnionych wartości historycznych dla co najmniej jednej klasy aktywów.

### Priorytet wykonania (bez nadmiernego mnożenia kodu i PR)

- **P0:** kwalifikacja **jednego** oficjalnego szeregu kontekstowego, np. OECD \`Share prices\` dla wybranego kraju, po sprawdzeniu jego metadanych i praw źródłowych — bez mylenia z globalnym TR.
- **P0:** rozwijanie zgodnej z prawami, odrębnej ścieżki danych do badań TR tylko po udokumentowaniu historycznej metodologii, FX, dywidend, instrumentu, kosztów i PIT.
- **P1:** przed uruchomieniem adaptera danych kontekstowych określić próbę obserwacji, rewizje, atrybucję, zakres przechowywania i brak wejścia do systemu zleceń. Nie zlecać kolejnego syntetycznego parsera jako substytutu dowodu.

**Stage 2 decision:** \`OFFICIAL_OPEN_MACRO_PATH_FEASIBLE_CONDITIONALLY; OPEN_GLOBAL_ETF_TOTAL_RETURN_NOT_IDENTIFIED; EODHD_NO_PROVIDER_INGEST; MODEL_SERIES_QUALIFIED=0; NO_REAL_FINANCIAL_ACTIONS\`.


## 8. Stage 3 — pierwsza dokładna seria OECD, status praw/PIT (10.11.2026)

**Wybrany, rzeczywisty identyfikator makroekonomicznego szeregu:** \`OECD Financial Market: Share Prices for Poland\`, nie inwestycyjny benchmark total return. Semantyka jest potwierdzona przez [OECD Share prices — Definition](https://www.oecd.org/en/data/indicators/share-prices.html) i publiczne metadane [OECD Financial market Data Explorer](https://data-explorer.oecd.org/vis?df%5Bag%5D=OECD.SDD.STES&df%5Bid%5D=DSD_STES%40DF_FINMARK&df%5Bvs%5D=4.0). Ten indeks **nie uwzględnia reinwestowanych dywidend**, jego miesięczne wartości zwykle stanowią średnią obserwacji cenowych, **nie** cenę zamknięcia z ostatniego dnia miesiąca i **nie** rynkową cenę wykonania zlecenia.

### Identyfikacja serii i granice jej walidacji

| Pole | Wartość i dowód | Poziom pewności |
|---|---|---|
| Agencja i struktura | \`OECD.SDD.STES\`, \`DSD_STES@DF_FINMARK\`, wersja \`4.0\` — oficjalny Data Explorer, „Financial market” | \`VERIFIED_DATAFLOW\` |
| Wymiary | \`REF_AREA=POL\`, \`FREQ=M\`, \`MEASURE=SHARE\`, \`UNIT_MEASURE=IX\`, \`ACTIVITY=_Z\`, \`ADJUSTMENT=_Z\`, \`TRANSFORMATION=_Z\`, \`TIME_HORIZ=_Z\`, \`METHODOLOGY=N\` — metadane [FRED \`SPASTT01PLM661N\`](https://fred.stlouisfed.org/series/SPASTT01PLM661N) odwołujące się do OECD; definicja OECD weryfikuje semantykę \`SHARE\` | \`DIMENSIONS_SECONDARY_CROSSCHECK\` |
| Kandydat na pełny klucz SDMX | \`POL.M.SHARE.IX._Z._Z._Z._Z.N\` złożony z powyższych dziewięciu wymiarów | \`CONSTRUCTED_NOT_HTTP_VERIFIED\` — bezpośrednie wywołanie OECD SDMX nie zostało potwierdzone; nie oznaczać jako ukończonego adaptera |
| Jednostka | \`Index 2015=100\`, ceny akcji, bez korekty sezonowej, częstotliwość miesięczna | \`METADATA_CONFIRMED\` |
| Właściciel praw do oryginalnego indeksu | Na podstawie samej definicji OECD i publicznych filtrów **nie ustalono jednoznacznie praw oryginalnego indeksu** dla tego konkretnego szeregu. Danych FRED nie wolno traktować jako dowodu zgody pierwotnego właściciela. | \`ORIGINAL_DATA_OWNER_UNVERIFIED\` |
| Rewizje i historyczne PIT | FRED opisuje możliwość rewizji serii; dzisiejszy Data Explorer nie dostarczył w tym audycie niezależnej historii \`first_available_at\` dla każdej obserwacji. | \`VINTAGES_NOT_VERIFIED\` |

**Źródła i precyzyjne ograniczenia licencji:**

1. [OECD Terms & Conditions, §3 „Data”, „Permitted Use”](https://www.oecd.org/en/about/terms-conditions.html): OECD dopuszcza szerokie wykorzystanie własnych danych i wymaga atrybucji, ale **wyraźnie wyłącza domniemaną zgodę na wykorzystanie danych, do których prawa mają osoby trzecie**. Przy serii cen akcji, którą OECD może otrzymywać od innych podmiotów, weryfikacja zakładki \`Source\` i konkretnego właściciela jest obowiązkową **kontrolą projektową** przed ingestem; nie ma dziś potwierdzenia własności całej serii przez OECD.
2. [FRED: Financial Market: Share Prices for Poland](https://fred.stlouisfed.org/series/SPASTT01PLM661N), \`Notes\`: pokazuje wymienione wymiary OECD i etykietę **\`Copyrighted: Citation Required\`**; jest to tylko dodatkowa weryfikacja metadanych. [FRED Terms, §II Prohibited Use oraz Additional Terms for API §(k)–(l)](https://fred.stlouisfed.org/legal/terms/) ograniczają użycie usług/treści i API w związku z AI oraz przechowywaniem danych API. **Nie integrować FRED API/MCP z agentem lub repozytorium ISL jako obejścia praw do danych OECD**. FRED nie może przyznać praw do źródła zewnętrznego.
3. [OECD Data Explorer — Financial market](https://data-explorer.oecd.org/vis?df%5Bag%5D=OECD.SDD.STES&df%5Bid%5D=DSD_STES%40DF_FINMARK&df%5Bvs%5D=4.0): właściwa preferowana domena do niezależnego potwierdzenia właściciela, metadanych i polityki rewizji i docelowego kodu. **Zapytanie do oryginalnego endpointu SDMX nie zostało ukończone w obecnym odczycie**, dlatego nie twierdzić, że mamy aktywną serię produkcyjną, potwierdzoną datę publikacji czy kompletne lata danych.

### Decision / action register

- **PASS:** \`SOURCE_FAMILY=OECD_FINMARK\`, \`REFERENCE_AREA=POL\`, \`MEASURE=SHARE_PRICE\`, \`FREQ=M\`, \`UNIT=INDEX_2015_100\`; dokładna dziewięciowymiarowa specyfikacja do ręcznego sprawdzenia.
- **BLOCKED:** \`DIRECT_OECD_RESPONSE_VERIFIED=false\`, \`SERIES_SOURCE_OWNER_CLEARED=false\`, \`THIRD_PARTY_USAGE_RIGHTS_CLEARED=false\`, \`HISTORICAL_VINTAGE_VERIFIED=false\`. Żadnego automatycznego pobrania pełnej serii bez tych dowodów.
- **NEXT P0:** właściciel danych ma sprawdzić w Data Explorer widok \`Source\` i dokument opisujący własność danych; w razie braku jasności zgłosić do kontaktu OECD \`stat.contact@oecd.org\` wskazując cały \`dataflow\`, dziewięć wymiarów, cel prywatnych badań, zakres retencji/AI i pytanie o zgodę właściciela. Przed użyciem zweryfikować odpowiedź i ewentualne warunki stron trzecich.
- **NEXT P1:** po dopuszczeniu konkretnej serii zarejestrować \`retrieved_at\`, źródło, obserwowany okres, rewizję, luki, cytowanie; **bez wartości indeksowych w publicznym GitHub ani w logach CI**, a \`first_observed_at\` nie zastępuje historycznego \`first_published_at\`.
- **HARD BLOCK:** seria \`SHARE_PRICE\` może być tylko \`MACRO_CONTEXT_REFERENCE\`; zakaz aliasu do \`GLOBAL_EQUITY_TR_PLN\`, \`PL_BONDS_TR_PLN\`, \`GOLD_TR_PLN\`, zakaz papierowych kandydatów i realnych operacji. Wpływ na A1/C1: **żaden**. \`INSUFFICIENT_DATA/HOLD_CASH\` bez zmian.

**Stage 3 decision:** \`EXACT_CANDIDATE_METADATA_IDENTIFIED; DIRECT_OECD_SDMX_RESPONSE_UNCONFIRMED; PER_SERIES_THIRD_PARTY_RIGHTS_UNCONFIRMED; NO_AUTOMATED_INGEST; MACRO_REFERENCE_ONLY; QUALIFIED_TR_SERIES=0\`.
