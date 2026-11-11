# Swinkels P1 — audyt pochodzenia, wersji i PIT (10.11.2026)

**Werdykt:** `SOURCE_RELEASE_DATE_VERIFIED`; `HISTORICAL_PIT_NOT_EVIDENCED`; `RESEARCH_ONLY / HOLD_CASH`.

## 1. Dowody i chronologia

| Obiekt | Ustalenie | Dowód | Status |
|---|---|---|---|
| Oryginalny DataverseNL ODS | Plik ID `512630`, 913425 bajtów, SHA-256 `90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847` | [DataverseNL dataset DOI](https://doi.org/10.34894/YWT2IX), oryginalny odczyt i SHA w CI | Potwierdzone |
| Historia publikacji DataverseNL | Wersja `1.0`, status `RELEASED`, `releaseTime` w UTC wskazuje **2025-08-22**; lista plików tej wersji zawiera `512630` | Oficjalne [Dataverse Native API — dataset versions](https://guides.dataverse.org/en/6.9/api/native-api.html), workflow `isl-swinkels-dataverse-pit-version-ci.yml` | Potwierdzone |
| Powiązany rekord Erasmus | Dataset opisany jako udostępniony w **2023** i aktualizowany do grudnia 2022, DOI `10.25397/eur.8152748.v6` | [Erasmus University Rotterdam — Historical Data](https://pure.eur.nl/en/datasets/historical-data-international-monthly-government-bond-returns/) | Potwierdzone **dla tego rekordu** |
| Mapowanie Erasmus v6 → oryginalny DataverseNL ODS 512630 | Brak potwierdzonej, kontrolowanej mapy wersji i sum kontrolnych obu publikacji | Nie stwierdzono dowodu równoważności plików | `NOT_VERIFIED` |
| Użycie DataverseNL ODS 512630 jako historycznego vintage na koniec dowolnego miesiąca 2020–2022 | Pierwsza ujawniona data publikacji pliku w oficjalnej historii DataverseNL jest po końcu badanego okna | `releaseTime` + ID pliku w historii wersji | `NOT_PIT_EVIDENCE` |
| Źródłowe rentowności w dacie obserwacji | Brak połączonych `value, observation_date, release/vintage_date` z wersjami wejść przed decyzją | Potrzebny niezależny odczyt archiwalnych wydawnictw | `NOT_VERIFIED` |

**Ostrzeżenie:** 2025-08-22 to data pierwszej wykazanej wersji zawierającej **identyfikator pliku w analizowanym repozytorium DataverseNL**, a nie dowód, że wcześniej nikt nie znał historycznych rentowności. Rekord Erasmus 2023 jest innym DOI, dopóki nie sprawdzimy mapowania wersji i SHA plików.

## 2. Dlaczego zgodność wzorów nie daje PIT

Pierwszy etap P1 matematycznie odtworzył 360 miesięcznych obserwacji (36 oryginalnych USA + 324 pozostałych) za lata 2020–2022. To dowodzi spójności wzorów z danymi zapisanymi w źródle **według obecnej wersji źródłowej**. Nie dowodzi, że takie same dane wejściowe i obliczone zwroty mogły być wykorzystane na koniec każdego miesiąca.

Brak daty dostępności może prowadzić do **look-ahead bias** lub do niedostrzeżonych późniejszych rewizji. To wysokie ryzyko dla backtestu decyzyjnego. Matematyczna precyzja (rzędu 1e-14) nie redukuje tego ryzyka.

## 3. Wymagany kontrakt źródłowy dla późniejszej kwalifikacji

Dla **każdej** miesięcznej wartości rentowności użytej w historycznej decyzji trzeba udokumentować co najmniej:

- identyfikator kraju i oficjalnej serii źródłowej, definicję rentowności, jednostkę i metodę wyznaczenia miesiąca;
- `observation_date`, `release/first_available_at`, `vintage_asof` z jednoznaczną strefą, oraz dowód, że snapshot był publicznie dostępny nie później niż moment decyzji;
- wersję źródła lub snapshot/hash danych oraz dowód braku użycia wartości opublikowanych później;
- mapę transformacji (źródłowa rentowność → zwrot modelu), licencję, wymagane opóźnienia i korekty;
- jednoznaczny wynik `PIT_ACCEPTED` lub `PIT_NOT_EVIDENCED` dla każdego miesiąca/źródła, nie tylko dla zestawu jako całości.

Kwalifikacja do modelu to **nasz kontrakt analityczny**, nie rzekomy wymóg prawny. Musi być potwierdzona dowodami i testami; nie wolno jej nadać przez ręczne ustawienie flagi.

## 4. Dostępne mechanizmy pozyskania dowodów

- **USA — DGS10:** [oficjalny FRED](https://fred.stlouisfed.org/series/DGS10) określa rentowność jako procent i serię dzienną; to **nie** jest jeszcze PIT. [ALFRED](https://fred.stlouisfed.org/docs/api/fred/alfred.html) przechowuje historyczne real-time periods, a [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html) obsługuje `realtime_start`, `realtime_end` i `vintage_dates`. Dopiero rzeczywisty odczyt/weryfikacja konkretnych miesięcy może spełnić część kontroli USA.
- **Pozostałe kraje:** źródła `Yield 10Y` wymagają mapowania do wystawców, identyfikatorów i archiwum publikacji. Samo oznaczenie `Yield 10Y` albo ten sam wzór w ODS nie wystarcza. Do czasu dowodu **brak kwalifikacji**.
- **Repozytorium źródła:** audyt wersji korzysta z publicznego [Dataverse Native API](https://guides.dataverse.org/en/6.9/api/native-api.html), sprawdza tylko opublikowane wersje oraz identyfikator pliku i nigdy nie zmienia oryginalnego SHA przy błędach sieciowych.

## 5. Dowody wykonania

Nowy skrypt: `scripts/swinkels_dataverse_pit_version_audit_v01.py`; testy: `tests/test_swinkels_dataverse_pit_version_audit_v01.py` (11 testów syntetycznych); CI: `.github/workflows/isl-swinkels-dataverse-pit-version-ci.yml`.

Zaliczono **11/11** na Ubuntu i **11/11** na macOS; jednorazowy audyt Dataverse wersji potwierdził 2025-08-22 i nie zakwalifikował żadnej serii do modelu. Wynik weryfikuje SHA oryginalnego ODS, status `RELEASED`, datę wersji i członkostwo ID pliku; nie pobiera snapshotów ALFRED ani innych krajowych danych.

## 6. Decyzja i ograniczenia

- `RESEARCH_MATH_ACCEPTED` — bez zmian dla odtworzonych historycznych wzorów.
- `DATASET_PIT_NOT_EVIDENCED` — **otwarta bramka**, nie gotowy backtest decyzyjny.
- `qualified_model_series=[]` i M1–M3 `INSUFFICIENT_DATA/HOLD_CASH`; brak handlu, transferów i przejścia z Draft PR #124 na `main`.
- Kolejny krok: pierwszy **kontrolowany odczyt DGS10 ALFRED** dla wybranych miesięcy i weryfikacja czasu udostępnienia oraz porównanie wartości do źródła, potem country-by-country lineage. Nie wolno zamieniać daty publikacji archiwalnego ODS na datę dostępności jego historycznych obserwacji.
