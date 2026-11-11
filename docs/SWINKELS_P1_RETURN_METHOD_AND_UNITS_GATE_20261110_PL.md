# ISL Swinkels P1 — metodologia, jednostki i bramka statystyk (research-only)

**Status: METHODOLOGY_PARTIAL / RETURN_M_UNITS_NOT_CERTIFIED / NO_PERFORMANCE_RECEIPT.**
**Data przeglądu:** 2026-11-10. **Powiązania:** #123, PR #124. Dokument jest dodatkiem do audytu oryginalnego ODS, nie zastępuje jego dowodu SHA.

## Rozstrzygnięte na podstawie źródła pierwotnego

- Autor: Laurens Swinkels, *Treasury Bond Return Data Starting in 1962*, **Data** 4(3), 91 (2019), sekcje **2. Data Description** i **3. Methods**, https://doi.org/10.3390/data4030091, https://www.mdpi.com/2306-5729/4/3/91.
- Sekcja 2: historyczny arkusz USA przedstawia w kolumnie E **monthly total return for an investor in a 10-year Treasury bond**; w kolumnie F wynik skumulowany od początkowej wartości inwestycji. Opis kolumn w publikacji z 2019 r. **nie certyfikuje automatycznie** jednostki/nazwy kolumny `Return M` ani każdego arkusza w wielokrajowym ODS DataverseNL (2023).
- Sekcja 3, równanie (3): przybliżenie zwrotu w okresie wykorzystuje dochód odpowiadający początkowej rentowności do wykupu, zmianę rentowności skorygowaną modified duration oraz człon convexity. Artykuł jawnie mówi, że pierwszy człon powinien być wyrażony w jednostce okresu zwrotu, a człony zmiany rentowności w spójnych jednostkach rocznych.
- Jest to **modelowana inwestorska stopa zwrotu**, nie gwarancja otrzymanego kuponu, historia notowań konkretnej obligacji ani realnie wykonalna cena transakcji. Metoda opiera się na założeniach dotyczących zapłaty przepływów i przybliżenia duration/convexity.

## Nierozstrzygnięte — wymagają oryginalnego Readme.pdf / arkusza

1. Czy `Return M` w pliku `International Monthly Government Bond Returns.ods` (DataverseNL datafile 512630, SHA-256 `90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847`) jest przechowywany jako decimal (0.01 = 1%) czy jako percent (1 = 1%), i czy styl komórki ukrywa transformację.
2. Czy arkusze poszczególnych państw i oba warianty USA używają identycznej konwencji i formuł; czy wartości są zrealizowanym kuponem, przybliżonym yield accrual, czy odrębnym sposobem reinwestowania.
3. Czy nowy DOI `10.34894/YWT2IX` oznacza bajtowo/wersjonowo tę samą publikację co DOI wydania historycznego `10.25397/eur.8152748.v6`.
4. Czy miesiące 2020–2022 zostały udostępnione w odpowiednich dawnych datach publikacji; **obecny odczyt nie jest dowodem PIT**.

## Gate P1: bezpieczny parser i walidator

- Dopuszczalne źródło danych: tylko oryginalny ODS z potwierdzonym SHA, pobrany w dozwolonym trybie bez sekretów; oryginalne `Readme.pdf` jako podstawa interpretacji formatu.
- Brak automatycznego rozpoznawania jednostek na podstawie zakresu wartości. Wymagana jawnie uzasadniona `return_unit`, z dowodem odniesionym do źródła i przykładowej formuły komórki. Jeśli nie ma dowodu: `UNITS_UNVERIFIED` i brak statystyk stóp zwrotu.
- Każda seria: jawny kraj/wariant, 36 unikalnych miesięcy 2020-01..2022-12, wartości skończone, żadnych dopisanych obserwacji, żadnych syntetycznych wypełnień.
- Po ustaleniu skali, przed kapitalizacją trzeba zweryfikować `1+r > 0`. Obliczenia edukacyjne: `prod(1+r_t)-1`, odchylenie miesięczne, obsunięcie ze skumulowanego indeksu; bez interpolacji, bez przenoszenia wartości do C1/M1–M3.
- Testy obowiązkowe: units percentage-vs-decimal mismatch; błędny kraj/wariant; brak lub duplikat miesiąca; NaN/infinity; return <= -100%; rozbieżność kalkulacji z formułą albo niespójny opis coupon/yield approximation.
- Wynik do logów wyłącznie w postaci informacji o walidacji i hashach albo ograniczonych bezpiecznych statystyk **po potwierdzeniu jednostek**. Nie zapisuj oryginalnego ODS, pełnych szeregów ani pojedynczych obserwacji do GitHub artifacts/logów.

## Granice autoryzacji

Dane są historycznymi, modelowanymi zwrotami obligacji rządowych dziewięciu gospodarek, bez Polski i bez okresu 2023–2026. Nie kwalifikują się do `PL_BONDS_TR_PLN` lub `GLOBAL_EQUITY_TR_PLN`; nie certyfikują PIT i nie mogą tworzyć sygnału ani propozycji zleceń. `qualified_model_series=[]`, `paper_candidates=[]`, M1–M3 `INSUFFICIENT_DATA/HOLD_CASH`. Zakaz połączeń z brokerem, portfelem, transferami, sekretami, bazą transakcyjną lub schedulerem. Nie scalać PR z `main` na podstawie samego dokumentu.

## Kryterium zamknięcia P1

Dopiero odczyt oryginalnego `Readme.pdf`, jednoznaczna kontrola jednostek `Return M` i kontrolowane obliczenia z testami negatywnymi umożliwiają `OFFLINE_HISTORICAL_SOURCE_STATS_ACCEPTED` — co nadal **nie jest** `PIT_QUALIFIED_MODEL_DATA`.
