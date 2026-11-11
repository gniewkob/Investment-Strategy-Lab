# Investment Strategy Lab — I6: historyczna dostępność kursów NBP (2026-11-09)

**Status projektu:** kontrola badawcza `DRAFT / OFFLINE / RESEARCH_ONLY`. Celem jest eliminacja wybranych przypadków `look-ahead bias` w przyszłej analizie historycznej USD/PLN, **nie** kwalifikacja oryginalnego zestawu danych do modeli ani realnego inwestowania.

## 1. Fakty i źródła pierwotne

1. **NBP Web API — instrukcja**: <https://api.nbp.pl/> oraz <https://api.nbp.pl/en.html>. Publiczny interfejs obejmuje historyczne kursy walut i ceny referencyjne złota. Tabela A udostępnia kurs średni `Mid`, tabela C `Bid`/`Ask`. Pole `EffectiveDate` jest **datą publikacji**, a nie timestampem z godziną, minutą i sekundą; tabela C ma ponadto `TradingDate`. Dane FX od 2002-01-02; limit pojedynczego zapytania historycznego wynosi **93 dni**. Pełny kontekst, typ dokumentu i możliwość wykorzystania danych należy osobno zweryfikować na podstawie regulaminu NBP.
2. **NBP — informacja o terminach publikacji kursów**: <https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/informacja-o-terminach-publikacji-kursow-walut/>. Według aktualnego harmonogramu tabela A jest aktualizowana w dni robocze w przedziale 11:45–12:15 czasu polskiego. Informacja ta jest przydatna do oceny ostrożnej granicy czasowej, lecz **nie stanowi archiwalnego dowodu dokładnego momentu opublikowania każdego pojedynczego kursu w przeszłości**.
3. **NBP — instrukcja pobierania**: <https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/instrukcja-pobierania-kursow-walut/>. NBP opisuje archiwalne pliki tabel i oficjalne zasady ich publikacji.

**Rozróżnienie normatywne:** NBP opisuje dane i harmonogram; niżej opisana polityka opóźnienia jest **autorską regułą ostrożnościową Investment Strategy Lab**, a nie wymaganiem ustanowionym przez NBP, normę ISO czy prawo.

## 2. Reguła badawcza I6

`scripts/nbp_publication_lag_offline_v01.py` przyjmuje wyłącznie **lokalny JSON odpowiedzi NBP dla `table=A`, `code=USD`**, ze znanymi polami `rates[].no`, `rates[].effectiveDate`, `rates[].mid`. Źródło jest sprawdzane offline pod kątem poprawności danych, numerów publikacji, chronologii i maksymalnego 93-dniowego okna jednego zapytania.

Dla żądanej dokładnej daty publikacji `effectiveDate = D`:

- Wyznaczane jest `research_not_before_utc = 00:00:00Z` **następnego dnia kalendarzowego po D**.
- Decyzja mająca timestamp **przed** `research_not_before_utc` otrzymuje `NOT_YET_PASSED_CONSERVATIVE_NEXT_DAY_LAG`.
- Gdy daty D nie ma w lokalnym JSON, wynik to `NO_EXACT_SOURCE_PUBLICATION_DATE`: **bez uzupełniania poprzednim kursem**, imputacji, przeszukiwania innych źródeł lub udawania pełnego kalendarza.
- Po upływie opóźnienia wynik `DATE_LAG_PASSED_NOT_HISTORICAL_PIT_CERTIFIED` oznacza jedynie, że **lokalna reguła czasowa została spełniona**. To nie jest niezależny dowód, że kurs istniał w danej postaci przed historycznym timestampem.
- W każdym wariancie `same_day_use_allowed=false`, `independently_certified_historical_pit=false`, `independently_certified_source_rights=false`, `fx_conversion_performed=false`, `eligible_as_model_total_return_series=false`, `qualified_model_series=[]`, `paper_candidates=[]`, `model_state=HOLD_CASH`. Zero operacji finansowych i zapisów bazy.

**Ograniczenia:** dane tabeli A nie są rynkowym `Bid/Ask` dostępnym do wykonania wymiany, a kurs USD/PLN nie jest szeregiem `TOTAL_RETURN`. Ta bramka **nie buduje** portfela, nie przelicza indeksu MSCI, nie szacuje ceny ETF ani nie podejmuje decyzji inwestycyjnej.

## 3. Minimalne wykorzystanie offline

```bash
python -m scripts.nbp_publication_lag_offline_v01 \
  --local-nbp-table-a-usd-json /path/to/authorized-local-nbp-json.json \
  --effective-date 2026-10-30 \
  --decision-at-utc 2026-10-30T18:00:00Z
```

Wynik: tylko metadane `ISL_I6_NBP_DATE_LAG_RECEIPT`, stan blokady i kanoniczny SHA-256 lokalnego snapshotu. **Wartości `rates[].mid` nie są kopiowane** do raportu ani logów testowych. Skrót SHA-256 jest kontrolą wewnętrznej tożsamości, a nie potwierdzeniem oryginalności pobrania, praw czy punktu historycznej publikacji.

## 4. Testy i odbiór

`tests/test_nbp_publication_lag_offline_v01.py` — **19 testów syntetycznych**, w tym decyzja w dniu publikacji o 23:00 UTC, pierwszy moment następnego dnia o 00:00 UTC, weekend, brak dokładnej daty, przyszłe daty, błędne oznaczenie tabeli lub waluty, przekłamanie numeru tabeli, duplikaty, błędna kolejność, niewłaściwa strefa UTC, skrajne/nie-JSON kursy, wartości NaN i zbyt szerokie okno >93 dni. Upewniają się, że nawet formalnie poprawny dokument nie staje się źródłem decyzji.

CI `.github/workflows/isl-i6-nbp-publication-lag-offline-ci.yml` uruchamia **31 testów na Ubuntu i 31 na macOS**: 19 I6 + 5 A2 jawnego dostępu do danych + 7 C2 referencyjnego gatewaya. Wszystkie testy korzystają z danych sztucznych i mają zablokowane Python socket connects. Workflow ma tylko `permissions: contents: read`, bez `push`, `schedule` oraz sekretów.

Odbiór wymaga rezultatów CI na **dokładnym ostatnim SHA** Draft I6. Sukces poprzednich etapów I5/I4 i kodu z Ubuntu nie zastępuje testów macOS ani niezależnej kwalifikacji danych.

## 5. Ryzyka niewyeliminowane przez I6

- `EffectiveDate` jest datą opublikowania według NBP, ale dzisiejszy endpoint nie jest sam w sobie zamrożonym dowodem całego łańcucha historycznych wersji i dokładnego czasu udostępnienia.
- Połowa dnia po stronie Polski i daty UTC zależą od strefy; polityka następnego dnia UTC jest celowo opóźniona, **nie** próbuje odgadywać rzeczywistej godziny pobrania i nie jest optymalizacją okazji inwestycyjnych.
- Nie ma dowodu praw do konkretnego zbioru danych dla naszej aplikacji; ewentualne warunki korzystania podlegają oddzielnej weryfikacji.
- Bez autentycznego szeregu globalnych akcji, polskich obligacji i złota w walucie/semantyce `TR PLN`, bez historycznych vintages, bez cen wykonalnych instrumentów i bez oceny kosztów **M1–M3 pozostają `INSUFFICIENT_DATA/HOLD_CASH`**.

**Decyzja:** `I6_REFERENCE_CALENDAR_ONLY_NO_PIT_ATTESTATION`; brak autorizacji `main`, dostępu do płatnych źródeł, automatycznych workflow dostawców i realnych transakcji.
