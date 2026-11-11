# ISL P3 — screening potencjalnych źródeł TR i referencyjnych (11.11.2026)

**Status:** `CANDIDATE_RESEARCH_ONLY` / **zero zatwierdzonych pinów** / `MODEL_ADMISSION_GRANTED=false`. To kontrola adekwatności **danych**, nie wybór instrumentów ani rekomendacja zakupów.

## Udokumentowane źródła i wynik dopasowania

| Wymagany typ ISL | Materiał źródłowy (oficjalny) | Co potwierdzono | Dlaczego NIE trafia do reviewed registry |
|---|---|---|---|
| `BONDS_TR_PLN` | [BondSpot: TBSP.Index](https://www.bondspot.pl/tbsp_index_opis/pub/Regulacje_TBS_Poland/tbsp_index_opis) i [komunikat BondSpot opisujący total return](https://www.bondspot.pl/pressroom?ph_main_content_1_cmn_id=1309&ph_main_content_1_start=show) | Polskie obligacje skarbowe PLN; indeks total return obejmujący zmiany cen, odsetki narosłe i kupony reinwestowane. BondSpot wskazuje GPW Benchmark jako administratora od 01.12.2019. | Nie zweryfikowano praw/licencji dla pobierania i analizy pełnej historii, stabilnego API, dokładnych serii archiwalnych, ich SHA i czasu pierwszej publikacji, ani tego, czy koszyk polskich obligacji spełnia docelowy mandat modelu `M2`. |
| `EQUITY_TR_PLN` | [Vanguard FTSE All-World UCITS ETF USD Accumulating — historyczne NAV](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating) | Oficjalna strona instrumentu podaje NAV **USD**, historyczne notowania i reinwestowanie dywidend klasy Acc. | **To NAV jednostki funduszu, nie opublikowany PLN total-return index.** Wymaga osobnego kontraktu `ACCUMULATING_FUND_NAV`, chronologicznie spójnego kursu USD/PLN, modelu kosztów i wyboru mandatu. Nie wolno automatycznie zmienić typu przez `requirements.basis`. |
| `GOLD_TR_PLN` | [NBP Web API — historyczne ceny złota](https://api.nbp.pl/) | NBP udostępnia oficjalną **cenę 1 g złota w PLN**, dane od 02.01.2013 i API HTTPS; dzień w odpowiedzi jest dniem publikacji. | **Cena spot/referencyjna nie jest indeksem total return.** Wymaga jawnego odrębnego modelu `GOLD_SPOT_REFERENCE_PLN` (plus udokumentowane koszty magazynowania/inwestowalność, jeżeli kiedyś potrzebne) albo innego niezależnie potwierdzonego szeregu TR. Retrospektywne API nie poświadcza pełnych historycznych wersji PIT. |

## Decyzje i granice

1. **Brak automatycznego przyjęcia TBSP.Index:** zgodność klasyfikacji TR i PLN jest tylko pierwszą przesłanką. Potrzebny audyt metodologii aktualnego administratora, licencji, struktury danych i temporalnej dostępności.
2. **Brak przekształcenia NAV funduszu w „indeks” przez zmianę nazwy:** wymaga nowego rodzaju źródła, ceny NAV a nie cen rynkowych, walut oraz wersjonowanych transformacji.
3. **Brak fałszywego `GOLD_TR_PLN`:** NBP ma wartości referencyjne, a nie total return. Przed zmianą definicji M2 należy jawnie zatwierdzić, jak modelować złoto.
4. **Bez source pinów** na tej podstawie: w `src/isl_v2/reviewed_source_registry.py` pozostaje `REVIEWED_SOURCE_PINS={}`, status `PIN_REVIEW_REQUIRED` dla wszystkich trzech pozycji.
5. **Samo istnienie historii cen dzisiaj nie spełnia historycznego PIT.** Potrzebne są źródłowe wersje i metadane wydania, niezależne pobranie i kontrola checksum.

**Wniosek:** P3 wskazuje potencjalny punkt startowy dla obligacji oraz dwie istotne niezgodności semantyki źródeł z obecnym schematem. Dalsza implementacja nie powinna dopuszczać ich do `M1–M3` bez odrębnej recenzji definicji i danych. Brak działań na prawdziwych aktywach, zmian sekretów, ról, baz danych i produkcji.

## Pogłębiona kontrola źródeł pierwotnych — 11.11.2026

### TBSP.Index — rozdzielenie administratora, historii i licencji

- BondSpot wskazuje GPW Benchmark jako administratora indeksu od **01.12.2019**: https://www.bondspot.pl/tbsp_index_description_en
- Oficjalny [archiwum TBSP.Index](https://www.bondspot.pl/tbsp_index_archive_en) zawiera archiwalne komunikaty i kalendarz. Nie jest jeszcze dowodem kompletnej, licencjonowanej serii miesięcznych poziomów 2020–2026.
- Osobna [strona portfeli historycznych](https://www.bondspot.pl/tbsp_index_portfolio_en) wprost obejmuje składy **do grudnia 2019 r.**; nie utożsamiać portfela z szeregiem wartości indeksu.
- [GPW Benchmark — usługa korzystania ze wskaźników referencyjnych](https://gpwbenchmark.pl/stosowanie_stawek_referencyjnych) oraz [BondSpot — Market Data Policy i wzory umów/licencji](https://www.bondspot.pl/1304) to podstawa do **weryfikacji** uprawnień. Istnienie tych warunków nie pozwala stwierdzić bez analizy konkretnej umowy, czy prywatny wewnętrzny odczyt badawczy jest dozwolony, ani czy automatyczny eksport/redystrybucja wymagają odrębnej licencji.
- **Werdykt dla `BONDS_TR_PLN`:** `SEMANTIC_MATCH_SOURCE_UNVERIFIED`. Metodologia i segment PLN są obiecujące, ale `license_reviewed=false`, `source_bytes_authenticated=false`, `historical_pit=false`; **brak pinu**.

### Akcje — lokalny indeks dochodowy nie zastępuje globalnej ekspozycji

- GPW Benchmark opisuje [WIG](https://gpwbenchmark.pl/karta-indeksu?isin=PL9999999995) jako indeks dochodowy uwzględniający dywidendy i prawa poboru.
- Opis [WIG20TR](https://gpwbenchmark.pl/karta-indeksu?isin=PL9999999425) potwierdza typ dochodowy i ekspozycję na 20 największych spółek GPW. Oba reprezentują Polskę, nie globalną serię `EQUITY_TR_PLN`.
- [Vanguard FTSE All-World UCITS ETF USD Accumulating](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating) może dawać **NAV USD klasy akumulującej**, ale nie wolno przepisać go jako indeks TR w PLN bez jawnej transformacji/rozdzielenia definicji.
- **Werdykt:** `GPW_WIG=MANDATE_EXPOSURE_MISMATCH`; `VANGUARD_ALL_WORLD_ACC=NOT_TOTAL_RETURN_INDEX + CURRENCY_TRANSFORMATION_REQUIRED`.

### Złoto — cena referencyjna, nie Total Return

- [NBP API](https://api.nbp.pl/) publikuje ceny referencyjne złota w PLN. To odrębny koncept `GOLD_SPOT_REFERENCE`, nie `TOTAL_RETURN_INDEX`; mechanizm kosztów przechowywania i możliwej realizacji nie wynika z danych NBP.
- **Werdykt:** `NBP_GOLD_PRICE=NOT_TOTAL_RETURN_INDEX` dla obecnego pola `GOLD_TR_PLN`. Nie zmieniono schematu produkcyjnego ani modelu.

### Reprodukowalna kontrola typu źródła

Dodano `src/isl_v2/research_source_candidate_triage.py` oraz `tests/test_research_source_candidate_triage.py`. Cztery pozycje kandydatów są opisane wyłącznie do badań; każdy wynik ma `candidate_source_admitted=false`, `historical_pit_certified=false`, `qualified_model_series=[]` niezależnie od oznaczeń licencji i źródła. Testy wymuszają blokadę niezgodnej waluty, innej kategorii danych i niewłaściwego rynku.

**Wciąż nie ma autentycznych historycznych artefaktów indeksu z niezależnie potwierdzoną datą publikacji i zgodą na użycie.** Nie tworzyć przez to sztucznego `TOTAL_RETURN_INDEX` dla złota/NAV ani automatycznych sygnałów w M1–M3.
