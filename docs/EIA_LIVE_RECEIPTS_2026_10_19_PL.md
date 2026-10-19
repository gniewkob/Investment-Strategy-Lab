# EIA: rzeczywiste audyty LIVE z 19.10.2026 — dowody i granica PIT

**Stan:** oba manualne `workflow_dispatch` wykonane przez operatora na `main`, 
commit `33c08aed1a8482902cc6ba50b0f96945a5202b81`. Nie uruchomiono 
żadnego zapisu ani automatycznego importu. Wszystkie czasy poniżej są UTC.

## A. Neon STAGING ↔ EIA WTI: pełne porównanie 695/695

[GitHub Actions run #39330376388](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330376388)
(19.10.2026, od 21:48:38 UTC): `workflow_dispatch`, 
`manual-staging-read-only=SUCCESS`, `offline-regression=SUCCESS`.

**Prawdziwy raport joba:**
- `status=WTI_POSTIMPORT_EIA_STAGING_695_MATCH_READ_ONLY`;
- `official_observations_in_window=695`,
  `staging_observations_in_window=695`,
  `matching_dates_and_prices=695`;
- `source_missing_from_reference=0`,
  `staging_dates_absent_from_official_source=0`, `price_mismatches=0`;
- `previously_stored_rows=660`, `backfilled_rows=35`, 
  `backfill_recorded_date_utc=2026-10-19`;
- `unchanged_prior_660_sha256=2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8`;
- okno obserwacji 02.01.2024–14.10.2026, strona EIA `Release Date=2026-10-15`;
- autentyczny `source_retrieved_at_actual=2026-10-19T21:48:50.066187+00:00`;
- SHA-256 **oryginalnego HTML tego konkretnego żądania** 
  `43723196ad327134040a1718ba5f3d3598bb949c154a6642c5b71c623c4f8981`;
- SHA-256 oryginalnych bajtów tymczasowego CSV odczytu Neon (nie HTML):
  `3fc0ed9cf2e599b87c34131e0fcbd86b5a30c0753226a6a79da078e5dfcb8820`;
- `database_connections=1`, `database_reads=1`, `database_writes=0`;
  `reference_reader_acl_verified=true`;
- `source_publication_vintages_verified=false`,
  `independent_point_in_time_market_data_certified=false`;
  `real_orders=0`, `portfolio_allocations_changed=0`.

[Artifact #12224256765](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330376388/artifacts/12224256765):
nazwa `wti-eia-postimport-staging-readonly-receipt`; wyłącznie agregatowy
JSON, 1007 bajtów ZIP, SHA-256 ZIP artifact 
`1157ac48d625b0266a164af823ac12a1e2ccf3c25f0ec52d016183b085808940`;
ważny według GitHub do **26.10.2026 godz. 21:48:50 UTC**. Dla audytu
długoterminowego zachowano niniejszy tekstowy rejestr parametrów i SHA;
nie stanowi on substytutu niezmiennego archiwum źródłowych bajtów HTML.

## B. Oficjalne aktualne źródła EIA — 3/3 publiczny HTTPS

[GitHub Actions run #39330400127](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330400127):
`workflow_dispatch` na `main`; joby `manual-public-eia-only`, 
`offline-regression-and-no-writer` oraz
`disposable-postgres-synthetic-integration` zakończone **SUCCESS**.

Wszystkie żądania to rzeczywisty publiczny HTTPS; 
`status=EIA_VERSIONED_INGEST_DRY_RUN_NO_DATABASE`;
`database_connections=0`, `database_writes=0`.
Żaden raw HTML ani cena nie jest publikowana w logu.

| Seria | Daty w aktualnym oknie źródła | Obserwacje | Raw HTML SHA-256 | Semantyczny SHA-256 dat i cen |
| --- | --- | ---: | --- | --- |
| WTI | 25.08.2025–14.10.2026 | 285 | `90056f802fdc1023695abdf53c6400e24649c60e74f5399b0078b21ece1e87fa` | `999e76f1d392df75212454a7e149631681104608f9c3b9fe80d623daf17af0dd` |
| Brent | 26.08.2025–14.10.2026 | 289 | `4b294ef02c9e1c3a29379e0dca719bd1e247cb95c096820ca850fdb6fa7f6e0e` | `d5746347f4d6371f9df882ce134bdd8280c226dcb2e557a3627a45537c3a9cd9` |
| Henry Hub | 25.08.2025–14.10.2026 | 283 | `1ea65413b48e42a30a7d63bf55322a62c2666f22506abfc2f5fbb5f0de7c4797` | `b8c21f1fcc89435bbde7db432ff16c6bda2c0e25725079be259b8b1d0e92683a` |

Rzeczywiste czasy ukończenia pobrania:
- WTI `2026-10-19T21:48:56.987993+00:00`;
- Brent `2026-10-19T21:48:57.495438+00:00`;
- Henry Hub `2026-10-19T21:48:57.929006+00:00`.

Wszystkie mają `Release Date=2026-10-15`, precyzja `DAY`;
`current_snapshot_available_not_before` = odpowiedni rzeczywisty
`retrieved_at`; `historical_individual_publication_vintages_verified=false`;
`source_bytes_retained_by_database=false`.

**Ważne:** WTI raw-HTML SHA z joba A i B różnią się, bo dotyczą
**odrębnych żądań** pobranych kilka sekund po sobie. Nie jest to
samo w sobie dowód zmiany cen. Hash semantyczny B obejmuje **285 dat
w ruchomym oknie**, natomiast audyt A porównał **695 dat w dłuższym
zamrożonym oknie**; nie wolno bezpośrednio porównywać obu hashy.
Ostatni manual A dowodzi pełnej zgodności dat i cen dla 695/695.

## C. Niezależny odczyt Neon po obu audytach

`project=red-lake-53043722`, `branch=br-wandering-union-ba6ogf6l`,
`database=investment_lab`: 
- legacy WTI **695** i Brent **706**;
- `source_documents` nadal **3**, z nich EIA **0**;
- `price_observation_versions` nadal **3**, z nich EIA **0**;
- `isl_eia_pit_staging_writer` **nie istnieje**.

Powyższe dowodzi ukończenia etapów **SOURCE VALIDATION** i **LOCAL
STAGING RECONCILIATION**. Nie dowodzi historii PIT.

## D. Bramka następna: archiwizacja + oddzielne zatwierdzenie

**GO:** bieżący publiczny odczyt źródeł EIA; niezależny bezpieczny audyt
STAGING WTI; prace inżynierskie z no-write i syntetycznymi testami.

**NO-GO bez osobnej zgody:** utworzenie nowej roli LOGIN/NOLOGIN, zmiana
ACL, nowe poświadczenia, zapis do `source_documents` lub
`price_observation_versions`, automatyczny harmonogram, produkcja
albo jakiekolwiek wykonywanie zleceń.

Przed pierwszym `INSERT` PIT:
1. Dodać mechanizm niezmiennego zachowania dokładnych oryginalnych
   bajtów EIA związanych z RAW SHA, by można było odtworzyć dowód
   po późniejszej modyfikacji strony; dotychczasowe logi zachowują
   wyłącznie hash/agregaty.
2. Przejrzeć [specyfikację roli STAGING](../db/security/eia_pit_staging_writer_REVIEW_ONLY.sql)
   i upewnić się, że przyszłe połączenie użyje wyłącznie odpowiedniej
   gałęzi, minimalnego SELECT/INSERT i TLS verify-full. Nie ma obecnie
   zatwierdzonej tożsamości zapisującej.
3. Oddzielnie autoryzować pierwszy, ograniczony **bieżący snapshot** na
   STAGING. Każdej obserwacji przypisać datę dostępności **od faktycznego
   pobrania tego snapshotu**, a nie datę jej historycznej obserwacji.
4. Zachować `UNVERIFIED_HISTORICAL_PUBLICATION`,
   `MARKET_DATA_NOT_READY` dla retrospektywnego PIT;
   M1/M2/M3 `HOLD_NO_CHANGE`.

Powiązane: [P0 Issue #2](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2),
[Issue #3](https://github.com/gniewkob/Investment-Strategy-Lab/issues/3),
[Issue #22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22).
