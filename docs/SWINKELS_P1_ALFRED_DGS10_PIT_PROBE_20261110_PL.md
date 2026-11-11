# Investment Strategy Lab — ALFRED DGS10 PIT: kontrolowany odczyt i odbiór (10.11.2026)

**PR:** #124, Draft. **Stan:** gotowa sonda i testy syntetyczne; `BLOCKED_NO_FRED_API_KEY` dla odczytu rzeczywistych historycznych obserwacji na GitHub Actions. `qualified_model_series=[]`, M1–M3 `HOLD_CASH`.

## Rozdzielenie dowodów

| Pytanie | Kontrola | Oczekiwany dowód | Obecny status |
|---|---|---|---|
| Czy oryginalny arkusz Swinkels jest zgodny z jego modelem matematycznym? | Zweryfikowany ODS + niezależne PV i Eq3 | 360 miesięcznych obserwacji badawczych | `RESEARCH_MATH_ACCEPTED` |
| Kiedy opublikowano **ten** plik DataverseNL? | Zestawienie wersji i ID pliku 512630 | Wersja 1.0 z 22.08.2025 | `RELEASE_DATE_VERIFIED` |
| Czy historyczne wartości DGS10 były dostępne w konkretnym dniu? | ALFRED real-time query z `realtime_start=end=asof` | Oficjalny historyczny snapshot z identyfikatorem i datą | **`BLOCKED_NO_FRED_API_KEY`** |
| Czy miesiąc z ODS odpowiada dokładnie odczytowi ALFRED? | Porównanie dziennej obserwacji i `Original_US_1962` | Wartości zgodne na trzech wybranych próbkach | `NOT_RUN` |
| Czy sygnał na koniec miesiąca byłby legalnie/operacyjnie wykonalny? | Daty pierwszej publikacji, znacznik czasu i decyzji, odtworzona metoda miesiąca, koszty | Odrębny kontrakt kompletności PIT 36/36 | `BLOCKED` |

### Oficjalne źródło

- FRED API v1, [API Keys](https://fred.stlouisfed.org/docs/api/api_key.html), parametr `api_key` wymagany w każdym wywołaniu.
- [`fred/series/observations`](https://fred.stlouisfed.org/docs/api/fred/series_observations.html): dostępne `realtime_start`, `realtime_end`, `observation_start`, `observation_end`, `units=lin`, `output_type=1`.
- [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html): FRED domyślnie używa dzisiejszego real-time period; historyczny przekrój wymaga wyraźnego wskazania daty.
- [`series/vintagedates`](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html) pokazuje daty, gdy seria została zmieniona/uzupełniona, ale nie gwarantuje historii publikacji każdej dziennej obserwacji z precyzją intraday.

## Ograniczona próba

Skrypt `scripts/swinkels_alfred_dgs10_pit_probe_v01.py` pyta tylko o trzy pary **daily observation date → historyczne as-of**:

| Miesiąc źródłowy | Obserwacja DGS10 | As-of (data snapshotu) |
|---|---|---|
| 2020-01 | 2020-01-31 | 2020-02-15 |
| 2021-06 | 2021-06-30 | 2021-07-15 |
| 2022-12 | 2022-12-30 | 2023-01-15 |

Są to **daty późniejsze niż koniec miesiąca**, wybrane wyłącznie do diagnostyki historycznej dostępności i spójności danych. Nie dowodzą możliwości podjęcia decyzji na koniec miesiąca, dlatego wynik `historical_pit_certified=false` jest wymuszony w każdym przypadku.

Próbka weryfikuje brak current-mode fallback, właściwe `date`, `realtime_start`, `realtime_end`, odrzuca puste/nienumeryczne dane, niezgodność dat i nieoczekiwane przekierowania API. Porównanie do ODS oznacza `MATCH` / `NOT_MATCHED` i zagregowaną maksymalną różnicę w punktach procentowych, bez publikacji pojedynczych obserwacji.

## Warunek uruchomienia bez ujawniania klucza

Nie zapisujemy sekretów w kodzie, czacie, PR ani artefaktach. W uprawnionym środowisku repozytorium skonfigurować sekret **GitHub Actions → `FRED_API_KEY`** jako wartość klucza wydanego przez [FRED API Keys](https://fred.stlouisfed.org/docs/api/api_key.html). Workflow `.github/workflows/isl-alfred-dgs10-pit-ci.yml` odczytuje wyłącznie to środowisko i nie wyświetla klucza. Brak sekretu jest jawnie oznaczany `BLOCKED_NO_FRED_API_KEY` — job może zakończyć się sukcesem technicznym, ale **nie stanowi to PASS dla źródła**.

W przypadku uzyskania dostępu do ALFRED wykonać osobno 36/36 właściwych miesięcznych odczytów według ustalonych dat decyzji, dopiero po zatwierdzeniu definicji momentu decyzji i metody agregacji dziennej rentowności. Należy potwierdzić źródłowe daty publikacji/wintage; `realtime_start` i `realtime_end` są na poziomie dnia, więc nie zastępują precyzji intraday, jeśli decyzja miała miejsce tego samego dnia.

## Obowiązująca decyzja

Badania historyczne i testy matematyczne pozostają dozwolone. Zweryfikowana publikacja retrospektywna nie stanowi snapshotu PIT dla okresu 2020–2022. Bez dowodów historycznej dostępności wartości wejściowych i ich transformacji **nie kwalifikujemy** obligacyjnych serii Swinkels do M1–M3 ani nie uruchamiamy żadnych operacji finansowych. PR #124 pozostaje Draft.
