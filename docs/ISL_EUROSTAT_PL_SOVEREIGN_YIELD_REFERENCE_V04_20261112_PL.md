# Public-first v0.4 — Polska: rentowności obligacji 10Y (Eurostat)

**Wątek:** [#152](https://github.com/gniewkob/Investment-Strategy-Lab/issues/152), PR #153. **Data:** 12.11.2026. **Koszt dostępu:** 0 PLN, bez kluczy i subskrypcji.

## Oficjalne pierwotne źródło i rozdzielenie twierdzeń

| Twierdzenie lub ograniczenie | Źródło / sekcja | Ocena |
|---|---|---|
| Eurostat publikuje miesięczne rentowności długoterminowych obligacji skarbowych, wyrażone jako **procent rocznie**, o zapadalności ok. 10 lat | [Eurostat: Maastricht criterion interest rates, ESMS](https://ec.europa.eu/eurostat/cache/metadata/en/irt_lt_mcby_esms.htm), sekcje **3.4**, **4**, **5** | Oficjalna metodologia dotycząca rentowności, **nie** holding-period total return |
| Dane MCBY pozyskiwane przez ECB z krajowych banków centralnych, w tym Polski | Ten sam [Eurostat ESMS](https://ec.europa.eu/eurostat/cache/metadata/en/irt_lt_mcby_esms.htm), sekcja **18.1–18.5** | Źródło pochodzenia statystyki, nie identyfikacja obligacji czy kuponów |
| Dane miesięczne publikowane zwykle po ok. 10 dniach | Ten sam ESMS, sekcja **14.1** | Statystyczna typowa aktualność, **nie** weryfikacja historycznego `first_available_at` dla obserwacji |
| Dane mogą być korygowane zgodnie z polityką ECB | Ten sam ESMS, sekcja **17** | Nie traktować dzisiejszych liczb jak niezmiennych oryginalnych publikacji |
| Ogólna możliwość ponownego wykorzystania statystyk Eurostat z podaniem źródła i wyjątkami | [Eurostat: Copyright notice and free re-use of data](https://ec.europa.eu/eurostat/help/copyright-notice), pkt **2–3** | Ogólna polityka reuse, nie aprobata wszystkich celów AI/automatycznego inwestowania ani praw podmiotów trzecich |

**Identyfikator:** `irt_lt_mcby_m`; `freq=M`, `int_rt=MCBY`, `geo=PL`, `time=2021-11...2026-09`. Kod źródła: `scripts/eurostat_pl_bond_yield_source_probe_v04.py` i `scripts/eurostat_pl_government_bond_yield_context_v04.py`. Jawne `--allow-public-eurostat-read`; odpowiedzi oficjalne HTTPS; brak przekierowań, limit 600 KB.

## Wynik pierwszego rzeczywistego odczytu

[Jednorazowy probe original publisher API w PR #153](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/43324574226) w dniu 12.11.2026 o 22:57:18 UTC potwierdził rzeczywistą strukturę JSON-stat: `[freq,int_rt,geo,time]`, `[1,1,1,59]`, kody `[M,MCBY,PL]`, `2021-11` do `2026-09`. Original-source SHA-256 odpowiedzi: `acc302b641ca981b5c8e22259a613d092e5c12d0cb01e39e7e093c07c59c3abf`. Provider last update: `2026-11-12T11:00:00+0100`. Pierwszy probe potwierdził 59 etykiet czasu, **nie liczbę niepustych wartości**, które są weryfikowane w osobnym typed-parser CI. Nie uzyskano dowodu historycznych oryginalnych wersji.

## Techniczny zakres

- `parse_original_yields` weryfikuje 59 prawdziwych, kolejnych miesięcy, dokładnie 4 wymiary `freq/int_rt/geo/time`, porządek kategorii JSON-stat, wartości procentowe, ewentualne statusy danych i oryginalne raw SHA-256. Brak obserwacji = BLOKADA, nie zero. Fałszywy kraj, `int_rt`, data w przyszłości lub błędne jednostki = BLOKADA.
- Raport ograniczony do **statystyk poziomów rentowności**, nie publikujemy 59 surowych wartości w logach CI. Min, max i średnia procentowa rentowności oraz największa bezwzględna miesięczna różnica poziomów w punktach bazowych; **nie** traktować jej jako rentowności z inwestycji.
- `historical_pit_certified=false`, `bond_holding_period_return_observed=false`, `tbsp_income_index_observed=false`, `qualified_model_series=[]`, `INSUFFICIENT_DATA_HOLD_CASH`.
- **Bez symulacji kupna/sprzedaży, rekomendacji aktywów, importów baz, połączeń portfela ani auto-schedule.** Przetwarzane są tylko oficjalne publiczne dane w kontrolowanym jednorazowym odczycie, offline testy i wersja źródła.

## Rzeczy pozostające poza zakresem

Rentowność w procentach p.a. to nie zrealizowany zwrot z portfela obligacji; brak cen transakcyjnych, kupowanych ISIN, kuponów, reinwestycji, kosztów i różnych terminów zapadalności. Sam hash dzisiejszej odpowiedzi nie dowodzi historycznego stanu `first_available_at`. Nadal otwarty [P0 #116](https://github.com/gniewkob/Investment-Strategy-Lab/issues/116) dotyczący praw do oryginalnego indeksu TR, source vintages i uprawnień. Ta analiza **nie kwalifikuje** `PL_BONDS_TR_PLN` ani M1–M3.

## Faktycznie opublikowane wartości z oryginalnego odczytu — PASS

Zrealizowany [jednorazowy odczyt oficjalnego Eurostat w CI #43325200200](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/43325200200) wykazał **59/59 niepustych miesięcy 2021-11…2026-09**, bez statusów specjalnych (`source_statistical_flags_count={}`). Rzeczywisty SHA-256 pobranych bajtów `acc302b641ca981b5c8e22259a613d092e5c12d0cb01e39e7e093c07c59c3abf`, receipt `4157225ea7cc1f2a5bf9816f9141ab036f098a29f0d5e5f3cfecdda42388b9f6`. Źródło zgłosiło ostatnią aktualizację `2026-11-12T11:00:00+0100`. Zapis **nie** poświadcza dokładnej pierwotnej daty żadnej historycznej obserwacji.

Na oficjalnych liczbach: minimum **3,12% p.a.**, maksimum **7,82% p.a.**, średnia z miesięcznych poziomów **5,6115% p.a.**, największa bezwzględna różnica między poziomami sąsiadujących miesięcy **154 pb** (tj. 1,54 punktu procentowego). Ta różnica **nie jest** stopą zwrotu z obligacji ani maksymalną stratą/zyskiem inwestora. Ani poziom rentowności, ani jego zmiana nie reprezentują realizowalnego indeksu dochodowego.
