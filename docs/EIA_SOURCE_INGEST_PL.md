# EIA — bezpieczna ingesta danych, Investment Strategy Lab 2.0 (PL)

**Status:** kod wdrożony do gałęzi przeglądowej; publikacja tylko research/paper. Import do produkcyjnego Neon nadal WYŁĄCZONY. Brak zleceń lub integracji transakcyjnych.

## Oficjalne źródła

- Brent: https://www.eia.gov/dnav/pet/hist/RBRTED.htm (USD/baryłkę)
- WTI: https://www.eia.gov/dnav/pet/hist/RWTCd.htm (USD/baryłkę)
- Henry Hub: https://www.eia.gov/dnav/ng/hist/rngwhhdD.htm (USD/MMBtu)

`src/isl_v2/eia_sources.py` wymusza dokładną listę URL, nagłówek HTML, pojedynczą **Release Date** (odrębną od **Next Release Date**), daty poniedziałek–piątek, pięć kolumn cen i brak wartości wykraczających poza publikację. Brak cen NIE jest wypełniany. Domyślnie importuje maksymalnie ostatnie 420 dni.

**Ważne:** historyczne ujemne kwotowania WTI z 2020 r. są prawidłowe, ale nie należą do współczesnego okna importu. Obecny schemat PostgreSQL dopuszcza tylko dodatnie `price_value` — gdyby ujemne notowanie wystąpiło w bieżącym zakresie, proces celowo odmówiłby importu zamiast je zniekształcić. Obsługa takich obserwacji wymaga osobnej, zatwierdzonej migracji.

## Wywołanie bez zapisu do Neon

```bash
python -m src.isl_v2.eia_ingest --source brent
python -m src.isl_v2.eia_ingest --source wti
python -m src.isl_v2.eia_ingest --source henry_hub
```

Są to odczyty HTTPS, walidacja i wynik JSON. Nie zapisują dokumentów, notowań ani zdarzeń do bazy. Oddzielny workflow `.github/workflows/official-eia-source-validation.yml` wykonuje te testy na oficjalnych stronach EIA, **bez sekretów**.

## Model wersji i czasu dostępności

`src/isl_v2/eia_ingest.py` przechowuje SHA-256 oryginalnej odpowiedzi HTML, kanoniczny URL i datę wydania całego snapshotu. To NIE jest oryginalna data publikacji każdej historycznej ceny. Nie wolno historycznie traktować dzisiejszego backfillu tak, jakby był dostępny autonomicznemu agentowi kilka lat wcześniej.

- `observed_for`: dzień rynkowej obserwacji, UTC 00:00.
- `published_at`: data publikacji obecnej strony EIA, precyzja DAY.
- `retrieved_at`: rzeczywisty moment pobrania snapshotu.
- `available_at`: późniejszy z momentu pobrania i dnia po publikacji przy konserwatywnej regule UTC.
- `recorded_at`: zapis wersji przez PostgreSQL.
- `prices_asof(cutoff)` i `agent_runner.load_observations()`: uwzględniają również retrieval/recorded timestamps.

Każdy nowy dokument jest identyfikowany przez SHA-256 jego bajtów. Niezmieniona cena nie tworzy nowej wersji, poprawiona cena zwiększa `revision_no`. Idempotentny przebieg dokumentu ma `run_key` oparty o źródło i hash; source-level advisory lock serializuje zapisy.

## Warunki przyszłego importu do gałęzi testowej

Wymaga oddzielnej roli PostgreSQL o ograniczonych prawach, migracji 007, istniejących katalogów EIA w `instruments`/`data_sources`, kontrolowanego sekretu wskazującego **wyłącznie gałąź testową** oraz ręcznego zezwolenia na zapis.

Flaga CLI `--write` jest domyślnie wyłączona. Do jej użycia trzeba oddzielnie ustawić `ISL_ALLOW_STAGING_INGEST=YES` i bezpiecznie dostarczyć `NEON_DATABASE_URL` poza repozytorium; **flaga środowiskowa sama nie potwierdza tożsamości gałęzi**, dlatego wcześniej trzeba zweryfikować connection target i rolę. Nie wolno ustawiać sekretów na publicznych workflow `pull_request` ani `push`.

Planowany odbiór: mały ręczny import do odizolowanej bazy, SQL `SELECT` na wersjach, ponowienie tego samego snapshotu bez duplikatu, kontrola korekty i test odczytu sprzed pobrania. Dopiero potem osobna decyzja o produkcyjnym harmonogramie. Podłączenie realnych kont inwestycyjnych nie wchodzi w zakres.

## Zweryfikowane w CI

1. Testy parsera i idempotencji: dane syntetyczne.
2. Live HTTPS: Brent, WTI i Henry Hub, odczytane przez GitHub Actions, bez zapisu.
3. Izolowany PostgreSQL 16: faktyczna migracja 007, dwa dokumenty z rewizją, brak duplikatów, izolacja `prices_asof`.
4. Zero testowych wpisów do produkcyjnego Neon.

Issue #2 pozostaje **częściowo otwarty** do czasu zatwierdzenia roli i uruchomienia pierwszego kontrolowanego importu do gałęzi testowej.
