# Investment Strategy Lab — Eurostat HICP: first FIN vs latest, badanie rewizji

**10 listopada 2026 | Typ:** edukacyjny moduł kontekstu makroekonomicznego. **Status:** Draft; testy na końcowym SHA konieczne. Nie jest to licencjonowany szereg stóp zwrotu, model handlowy ani rekomendacja inwestycyjna.

## 1. Materiał źródłowy i dokładna semantyka

- [Eurostat first released HICP \`prc_hicp_fpd\`](https://ec.europa.eu/eurostat/databrowser/product/page/prc_hicp_fpd) przechowuje pierwsze wartości opublikowane dla danych HICP, z wymiarem \`Release\`. **Rzeczywisty odczyt oficjalnej struktury** wykonano w [CI Draft #121, run 42826214217](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42826214217), na SHA \`db81dceaa68a14d33a96d9e6db5524a09e95f97f\`: \`freq,unit,coicop18,release,geo,time\`, \`FIN=Final\`, \`FLS=Flash\`. Nie są to kody zgadnięte.
- [Eurostat current HICP \`prc_hicp_minr\`](https://ec.europa.eu/eurostat/databrowser/product/page/prc_hicp_minr) zawiera aktualnie dostępną wersję indeksu; uprzedni realny odczyt trzech miesięcy Polski przeszedł w [CI Draft #119](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42822942523).
- [Eurostat HICP revision policy](https://ec.europa.eu/eurostat/web/hicp/information-data), sekcja **Data revisions**, dokumentuje zdarzenia **dotyczące agregatów strefy euro**: 3.03.2026 korektę błędu technicznego związanego z włączeniem Bułgarii do agregatu oraz 24.04.2026 przywrócenie archiwum pierwszych publikacji za styczeń 2026 po błędnej aktualizacji z 3.03.2026. **Źródło nie potwierdza nieprawidłowości krajowego HICP Polski za styczeń 2026**. Automatyczne wykluczenie Polski z tego powodu było nadmiernym rozszerzeniem zakresu incydentu.
- [Eurostat HICP improvements 2026](https://ec.europa.eu/eurostat/web/hicp/information-data), **Indices and rates of change**: klasyfikacja ECOICOP ver. 2 i rok referencyjny **2025=100**, a nie porównywanie bezpośrednio ze starą ECOICOP v1 czy poziomami 2015=100.
- [Eurostat API introduction](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction): API jest bezpłatne i udostępnia aktualne wartości; brak pełnego wersjonowania historycznych API wyników. [Eurostat copyright and reuse](https://ec.europa.eu/eurostat/help/copyright-notice): publiczne statystyki można zasadniczo ponownie wykorzystywać po atrybucji, pod warunkiem weryfikacji wyjątków i praw osób trzecich.

## 2. Cel i odizolowane wejścia

Moduł \`scripts/eurostat_hicp_fpd_revision_research_v01.py\` **nie** podejmuje decyzji o aktywach. Porównuje wyłącznie dwie oficjalne serie:

| Kontrola | Pierwsza publikacja finalna | Bieżąca wersja |
|---|---|---|
| Dataset | \`prc_hicp_fpd\` | \`prc_hicp_minr\` |
| Release | \`FIN\` = Final; wyklucza \`FLS\` = Flash | Bez wymiaru release |
| Geografia | \`PL\` | \`PL\` |
| Częstotliwość | \`M\` | \`M\` |
| Klasyfikacja | \`coicop18=TOTAL\` | \`coicop18=TOTAL\` |
| Indeks | \`I25\`, 2025=100 | \`I25\`, 2025=100 |
| Datowanie | Wspólny miesiąc obserwacji | Ten sam miesiąc; *latest vintage* |

**Różnica w punktach indeksowych:** \`revision_points = latest_HICP_index - FPD_FIN_first_final_HICP_index\`. **Nie** jest to stopa zwrotu, różnica procentowa, wielkość zmiany inflacji r/r, zysk z transakcji ani dowód dostępności historycznej w konkretnym momencie. Początkowy zakres realnego testu: lipiec–wrzesień 2026.

Walidator wymaga kodów `FIN/Final`, `FLS/Flash`, sześciu wymiarów FPD oraz pięciu wymiarów aktualnego HICP, spójnej chronologii i dodatnich/skończonych wartości. Brak obserwacji blokuje porównanie, bez forward fill. Styczeń 2026 **dla geo=PL** pozostaje porównywalny przy kompletnych źródłach; `euro_area_archive_notice_months_context_only` sygnalizuje wyłącznie kontekst z agregatów strefy euro, a nie błąd danych Polski.

## 3. Dostęp do oficjalnego źródła

**Tryb domyślny, offline:**
\`\`\`bash
python -m scripts.eurostat_hicp_fpd_revision_research_v01 \
  --fpd-local-json /private/eurostat_hicp_fpd.json \
  --current-local-json /private/eurostat_hicp_minr.json \
  --since 2026-07 --until 2026-09 \
  --observed-at-utc 2026-11-10T12:00:00Z
\`\`\`

**Jeden jawny test publicznego źródła:**
\`\`\`bash
python -m scripts.eurostat_hicp_fpd_revision_research_v01 \
  --fetch-official --since 2026-07 --until 2026-09
\`\`\`

Ten drugi tryb wykonuje **dokładnie dwa** ograniczone, anonimowe GET do publicznego Eurostat API (\`prc_hicp_fpd\` + \`prc_hicp_minr\`), bez redirectów, tokenów, zapisu do bazy, harmonogramów i transferów. Zakres to maksymalnie 24 miesiące od stycznia 2026, z ograniczeniem 2 MB dla FPD i 1 MB dla najnowszego HICP. Wynikowy raport zawiera miesiące i **różnice punktowe**, nie zawiera oryginalnych poziomów indeksów. W logu CI pojawia się jedynie suma kontroli, liczba porównanych miesięcy, liczba niezerowych korekt, maksymalna bezwzględna różnica oraz hashe źródeł.

## 4. Kryteria odbioru i rozdział od M1–M3

- **44 testy offline na Ubuntu i 44 na macOS**, w tym 16 nowych testów rewizji + 10 testów FPD schema + 18 testów HICP current. W testach sieć jest zablokowana; wszystkie wartości są syntetyczne.
- **Realny smoke:** dwa źródła Eurostat, ten sam kwartał, wymiar FIN zweryfikowany, kompletne trzy miesiące, bez zgadywania kodów, zero nieuprawnionej interpolacji.
- **Kontrola G1 i full-stack:** oryginalne 16 workflowów dostawców nadal objęte kwarantanną; istniejące A2–C2 i G1 mają pozostać zielone.
- **Brak promocji danych:** \`qualified_model_series=[]\`, \`paper_candidates=[]\`, \`source_manifest_created=false\`, \`market_execution_authorized=false\`, \`historical_point_in_time_certified=false\`, \`model_state=HOLD_CASH\`; zawsze 0 operacji finansowych i zapisów DB.
- **Granica historyczna:** archiwalna wartość FIN z Eurostat jest dowodem statystycznej **deklaracji pierwszej publikacji**, nie podpisanym \`first_available_at\` każdej obserwacji. Nie udowadnia niezmienności całego zestawu historycznych wersji, ani skuteczności strategii inwestycyjnych.

**Wynik:** \`EUROSTAT_REAL_INFLATION_REVISIONS_RESEARCH_ONLY\`; \`GLOBAL_EQUITY_TR_PLN, PL_BONDS_TR_PLN, GOLD_TR_PLN\` wciąż nie mają kwalifikowanych realnych szeregów \`PIT\`. Żadne źródło inflacyjne nie jest instrumentem finansowym.

## Korekta zakresu incydentu i dodatkowy odczyt — 10.11.2026

**Fakt ze źródła:** w [oficjalnej tabeli rewizji Eurostat, sekcja Data revisions](https://ec.europa.eu/eurostat/web/hicp/information-data) poprawka z 3 marca 2026 r. oraz przywrócenie archiwum *first released* 24 kwietnia 2026 r. mają jawnie określony zasięg **Euro area**, czyli agregat strefy euro. Jest to inny zakres geograficzny niż `geo=PL`. Nie ma wystarczającej podstawy, by na tej podstawie twierdzić, że pierwsza krajowa publikacja HICP Polski za styczeń 2026 była nieprawidłowa.

**Zmiana metodologii w kodzie:** usunięto automatyczne wyłączenie polskiego stycznia 2026 z agregatów rewizji. Raport nadal wyświetla pole `euro_area_archive_notice_months_context_only` oraz jawne `euro_area_archive_restoration_notice_scope=EURO_AREA_AGGREGATES_NOT_PL`. Test regresji weryfikuje, że komunikat o agregacie nie powoduje fałszywej blokady narodowego szeregu `PL`. Późniejszy niezależny dowód problemu w danych Polski wymaga osobnego przeglądu.

**Dodatkowy test oficjalnych danych:** osobny jednorazowy job `official-pl-january-2026` wykonuje dwa ograniczone odczyty publicznego API Eurostat (`prc_hicp_fpd` z `release=FIN` oraz `prc_hicp_minr`) dla `2026-01`, `geo=PL`, `M`, `TOTAL`, `I25` (2025=100). Weryfikuje kompletność 1/1, że nie ma fałszywego wyłączenia z powodu incydentu strefy euro i raportuje jedynie liczbę rewizji, maksymalną bezwzględną różnicę punktową oraz skróty SHA-256. Nie wypisuje oryginalnych poziomów indeksu. To **test obserwacji retrospektywnej**, a nie niezależna certyfikacja czasu historycznej dostępności ani dowód, że w innym czasie nie było żadnych korekt.

Odbiór wymaga zielonego testu stycznia, poprzednich 44 testów offline na obu systemach, regresji A2–C2 i G1 na dokładnym końcowym SHA. Wyniki syntetyczne nie zastępują oficjalnego odczytu stycznia.
