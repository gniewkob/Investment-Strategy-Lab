# ISL — Stage 6: Eurostat `prc_hicp_fpd`, dowód schematu publikacji

**Data:** 2026-11-10  
**Status:** badawcze, publiczne metadane. Brak automatycznych zleceń, brokers, płatnych API, danych o portfelu i handlu.  
**Poprzednik:** Draft [PR #119](https://github.com/gniewkob/Investment-Strategy-Lab/pull/119); [Issue #120](https://github.com/gniewkob/Investment-Strategy-Lab/issues/120).

## 1. Co potwierdzają oficjalne źródła

- [Eurostat `prc_hicp_fpd`](https://ec.europa.eu/eurostat/databrowser/product/page/prc_hicp_fpd) to oficjalny zbiór **HICP pierwszej publikacji**, według ECOICOP v2, zawierający wymiar **Release**; indeksy HICP mają bazę 2025=100 lub 2015=100. Sama etykieta „first released” nie jest dowodem, że lokalna kopia istniejąca dziś była dostępna w identycznej postaci w danej historycznej sekundzie.
- [Eurostat HICP — Information on data, Data revisions](https://ec.europa.eu/eurostat/web/hicp/information-data): dane z pierwszej publikacji za **styczeń 2026** (opublikowane 25 lutego) zostały błędnie zmienione **3 marca 2026**, a ich oryginalną wersję przywrócono **24 kwietnia 2026**. Nie wolno obliczać statystyk rewizji za ten okres bez odrębnego znacznika zdarzenia. Dokumentacja wskazuje także na zmianę klasyfikacji i roku bazowego w 2026 r.
- [Eurostat API — Introduction](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction): bezpłatne odczyty statystyk publicznych; API danych bieżących nie przechowuje kompletnych historycznych wersji **każdego** zbioru. `prc_hicp_fpd` jest odrębnym, opublikowanym zbiorem pierwszych wartości, nie automatyczną funkcją vintage dla `prc_hicp_minr`.
- [Eurostat — Copyright notice](https://ec.europa.eu/eurostat/help/copyright-notice): co do zasady wolno ponownie wykorzystywać publiczne statystyki z atrybucją; należy uwzględnić wyjątki dla praw innych właścicieli oraz oznaczać modyfikacje.

## 2. Ograniczony eksperyment diagnostyczny

`scripts/eurostat_hicp_fpd_schema_probe_v01.py` uruchomiony **domyślnie offline** czyta lokalny plik JSON-stat 2.0. Opcjonalny `--fetch-official` wywołuje **jeden** publiczny URL:

`https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_fpd?geo=PL&freq=M&unit=I25&coicop18=TOTAL&sinceTimePeriod=2026-07&untilTimePeriod=2026-09&lang=EN`

Zapytanie jest anonimowe, bez tokenów, z 20-sekundowym timeoutem i limitem odpowiedzi 2 MB. Brak przekierowań poza URL. Kod analizuje wyłącznie metadane `id`, `size`, `dimension`, `category.index`, `category.label`, `updated`. Dane `value` i `status` mogą być obecne w oryginalnym JSON, ale **nie są kopiowane do raportu ani logów**. Publikowany jest hash lokalnej kanonicznej odpowiedzi i ograniczona lista kodów/etykiet Release. Nie ustalamy a priori, jakie kody Release istnieją.

**Dwa źródła nie są tożsame:**

- `prc_hicp_minr` — bieżący HICP, który przeszedł prawdziwy smoke w poprzednim etapie; identyfikator JSON-stat, `PL`, `M`, `TOTAL`, `I25` i próba 3 miesięcy zostały zweryfikowane w CI PR #119.
- `prc_hicp_fpd` — osobny zbiór z wymiarem `Release`, którego **rzeczywiste kody i relacje obserwacja–publikacja** trzeba potwierdzić zanim będzie można stworzyć jakąkolwiek tabelę rewizji.

## 3. Definicja odbioru

- [ ] **10/10 testów offline PASS** w nowym CI; sztuczne dane nie udają prawdziwego HICP.
- [ ] Jednorazowy, rzeczywisty odczyt publicznego `prc_hicp_fpd` zwraca JSON-stat 2.0 i jednoznacznie rozpoznany wymiar `Release`; dowód w logach bez poziomów indeksu. Jeśli publiczny API różni się od przypuszczalnej struktury, zatrzymać analizę i dopasować parser do udokumentowanej odpowiedzi.
- [ ] Zarejestrować pochodzenie, dokładne kody Release, flagi i ograniczenia porównywalności. Nie domniemywać daty pierwszej publikacji dla każdej obserwacji wyłącznie z kodu kategorii.
- [ ] Zachować `qualified_model_series=[]`, `paper_candidates=[]`, `HOLD_CASH`, 0 transakcji oraz brak dostępu do silnika decyzji A1/C1.
- [ ] Niezmienione Git `main` i wszystkie 16 workflowów kwarantanny G1; niezależne testy A2–C2 i G1, jeśli uruchomią się na PR.

**Wynik wymagany do następnego etapu:** faktyczne, zweryfikowane kody `release` i zasady dopasowania do `time`, przed budową obliczania `latest - first`. Nawet wtedy nie uzyskamy danych `*_TR_PLN` do kwalifikacji M1–M3.

**Uwaga:** sukces probe nie jest certyfikacją historycznych punktów publikacji, warunków dystrybucji, przewagi inwestycyjnej ani zgodą na rzeczywisty handel.
