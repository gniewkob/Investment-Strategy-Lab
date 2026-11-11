# ISL — Eurostat HICP: pierwszy odizolowany, oficjalny tor danych makro

**Data:** 2026-11-10. **Zakres:** publiczny wskaźnik inflacji konsumenckiej Polski, wyłącznie badania edukacyjne i kontekst makro. **Nie** jest to zwrot z akcji, obligacji lub złota. **Nie** zmienia kwalifikacji M1–M3, nie tworzy zleceń ani rozliczeń.

## Prawa i dane źródłowe — fakty vs decyzje projektu

| Element | Oficjalne źródło / dokładne miejsce | Co potwierdza |
|---|---|---|
| Zasady użycia | [Eurostat Copyright notice and free re-use of data](https://ec.europa.eu/eurostat/help/copyright-notice), pkt **General principles 2–4**, **Exceptions** i **How to cite** | Ponowne wykorzystanie statystyk jest dopuszczalne z podaniem źródła, z wyjątkami dla danych o prawach osób trzecich, oznaczonych w konkretnych produktach. Nie ma generalnej potrzeby uzyskiwania pisemnej licencji do własnych statystyk Eurostatu. Wymaga atrybucji i zaznaczenia zmian |
| Oficjalny API | [Eurostat API introduction](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction), „General introduction” | Bezpłatny programistyczny dostęp do statystyk/metadanych. Zbiór zawiera **najnowszą wersję danych**, bez pełnego archiwum historycznych wersji |
| Nowy zbiór HICP | [Eurostat prc_hicp_minr](https://ec.europa.eu/eurostat/databrowser/product/page/prc_hicp_minr), [Eurostat HICP Information on data](https://ec.europa.eu/eurostat/web/hicp/information-data) | Od 2026 ECOICOP ver.2/COICOP 2018, rok odniesienia **2025=100**, nowa tabela \`prc_hicp_minr\` agreguje indeks, r/r, m/m i średnią 12-miesięczną; stary \`prc_hicp_midx\` jest historyczny i zakończony w 2025 r. |
| Polski pierwotny producent | [GUS — HICP, zmiany w 2026](https://stat.gov.pl/en/topics/prices-trade/price-indices/harmonized-indices-of-consumer-prices-hicp%2C15%2C1.html) | HICP Polski jest obliczany z danych o krajowych cenach wg ujednoliconej metodologii, w 2026 zmieniono klasyfikację i bazę; historia została przeliczona |
| Dane pierwszej publikacji | [Eurostat prc_hicp_fpd](https://ec.europa.eu/eurostat/databrowser/product/page/prc_hicp_fpd); [HICP Information on data, „Data revisions”](https://ec.europa.eu/eurostat/web/hicp/information-data) | Eurostat przechowuje oficjalny zbiór „first released data”, od 2024-01 dla ECOICOP ver.2. **Uwaga:** dane pierwszej publikacji dla stycznia 2026 zostały omyłkowo zmienione 03.03.2026 i przywrócone 24.04.2026; porównanie rewizji wymaga traktowania tego zdarzenia osobno. Nie wolno mylić \`updated\` bieżącego API z \`first_available_at\` obserwacji |

## Działający kontrakt v0.1

\`scripts/eurostat_hicp_macro_context_v01.py\`:

- Używa **wyłącznie** \`prc_hicp_minr\`, \`geo=PL\`, \`freq=M\`, \`unit=I25\` (index 2025=100), \`coicop18=TOTAL\` (all items). Nie wolno automatycznie użyć \`CP00\` ze starej klasyfikacji ani \`I15\` (2015=100).
- Odczyt **domyślnie offline** (\`--input-local-json\`) weryfikuje wersję JSON-stat 2.0, dokładne wymiary, pozycje i statusy, kompletną chronologię i wartości liczbowe. Każda brakująca obserwacja to \`BLOCKED_INCOMPLETE_CONTEXT\`, a nie podstawiony indeks.
- Jawny \`--fetch-official\` robi **jedno** anonimowe HTTPS GET do ustalonego, oficjalnego endpointu Eurostat, w oknie maksymalnie 120 miesięcy, bez przekierowania na inne domeny, tokenów, zapisów plików i schedulerów. Ograniczenie odpowiedzi: 1 MB, timeout 15 s. Brak pobierania danych z OECD, FRED, MSCI lub EODHD.
- Raport zawiera miesiące, indeks HICP, atrybucję i hash kanonicznego payloadu, ale **zawsze** \`historical_first_release_captured=false\`, \`historical_point_in_time_certified=false\`, \`qualified_model_series=[]\`, \`paper_candidates=[]\`, \`HOLD_CASH\`, zero zleceń, paper fills i zapisów DB.
- Dane bieżącego \`minr\` reprezentują **najnowszą dostępną wersję**, mogą być zmieniane retrospektywnie. Przeliczenia HICP historycznego w 2026 nie są dowodem, że te same wartości były historycznie znane. Nie używać do rzeczywistych decyzji inwestycyjnych.
- Błąd parsowania, status HTTP inny niż 200, niewłaściwy format, nadmiar wymiarów, błędny indeks, brak okresu → **zatrzymanie** lub \`BLOCKED_INCOMPLETE_CONTEXT\`.

### Komendy

**Offline z legalnie pozyskanego oryginalnego JSON-stat:**
\`\`\`bash
python -m scripts.eurostat_hicp_macro_context_v01 \
  --input-local-json /private/eurostat_prc_hicp_minr_PL.json \
  --since 2026-07 --until 2026-09
\`\`\`

**Jednorazowy read-only smoke dla publicznych danych Eurostat:**
\`\`\`bash
python -m scripts.eurostat_hicp_macro_context_v01 \
  --fetch-official --since 2026-07 --until 2026-09
\`\`\`

To **nie jest** zadanie cykliczne, nie udostępnia danych EODHD i nie wykonuje operacji finansowych.

## Odbiór

\`tests/test_eurostat_hicp_macro_context_v01.py\`: **18 testów na syntetycznych wartościach HICP**, osobno Ubuntu i macOS, wszystkie połączenia Python socket w tych testach zablokowane.

\`.github/workflows/isl-eurostat-hicp-macro-context-ci.yml\` uruchamia powyższe testy oraz **jeden pomocniczy, nieblokujący test żywego oficjalnego endpointu** na Ubuntu z zakresem 2026-07..2026-09. Jego powodzenie ma znaczenie: kod potrafi przetworzyć odpowiedź publicznego źródła. Jego niepowodzenie oznacza \`LIVE_SOURCE_NOT_VERIFIED\`, nawet jeśli testy offline przejdą. Test ten nie zapisuje wartości inflacji w publicznych logach (tylko zakres, liczebność i SHA). Nie upoważnia to do użycia serii w modelach zwrotów.

**Następny logiczny etap:** uzyskać **faktyczny** JSON-stat \`prc_hicp_fpd\` z wymiarem „Release”, osobno zweryfikować jego strukturę i metadane, potem porównać pierwszą publikację z bieżącą tylko dla *tych samych* kraju, jednostki, klasyfikacji i miesiąca. Nie zgadywać wartości \`release\` ani deklarować weryfikacji PIT bez oficjalnego potwierdzenia.

**Stan projektu:** \`MACRO_CONTEXT_INITIAL_RESEARCH_ONLY\`; \`REAL_TOTAL_RETURN_SOURCE_QUALIFIED=0\`, \`M1–M3=INSUFFICIENT_DATA/HOLD_CASH\`; żadne źródło makro nie staje się instrumentem rynkowym.
