# EIA — wersjonowany importer źródeł: implementacja z bramką bezpieczeństwa

**Stan 19.10.2026:** implementacja przygotowana do przeglądu i syntetycznych
testów, **nie jest autoryzacją do zapisu do Neon**. System służy
wyłącznie badaniom hipotetycznym. Nie podłącza kont ani portfeli.

## Cel P0 Issue #2

Źródłowy dokument EIA i obserwacja cenowa są odrębnymi faktami.

1. Pobierz z oficjalnego HTTPS (WTI, Brent, Henry Hub), bez przekierowań.
   Weryfikuj HTML, limit 8 MB, pojedyncze `Release Date`, tygodniowe
   kolumny, poprawne daty, dodatnie w bieżącym oknie wartości.
2. Hash SHA-256 licz na **tych samych, oryginalnych bajtach HTML**, które
   przetwarza parser. Nie korzystaj z przetworzonego markdown, ponownie
   serializowanej tabeli albo hipotetycznego SHA.
3. Zapis planowany do `source_documents` musi zawierać
   `canonical_url`, `sha256_hex`, bieżące `published_at` (północ UTC dnia
   `Release Date`, `publication_precision=DAY`) oraz rzeczywisty moment
   `retrieved_at`. Obowiązkowe metadane:
   `source_type=EIA_DAILY_SPOT`,
   `source_vintage=CURRENT_SNAPSHOT_UNVERIFIED_HISTORICAL_PUBLICATION`,
   `original_historical_publication_verified=false`.
4. Każda wersja `price_observation_versions` wiąże obserwację dzienną
   `DAILY_SPOT` z konkretnym `document_id`, `revision_no`,
   `price_value`, `available_at` i realnym serwerowym `recorded_at`.
   `available_at=max(retrieved_at, 00:00 UTC dnia po bieżącym Release Date)`.
   Nie antydatować dostępności wiersza z 2024 na podstawie
   `observed_for=2024` z bieżącej strony EIA.
5. Ponowne przetworzenie tego samego dokumentu ma być idempotentne.
   Nowy SHA z niezmienionymi cenami tworzy co najwyżej nową metadaną
   dokumentu, ale **nie pozoruje rewizji notowań**. Zmiana ceny
   w nowszym snapshotcie zapisuje nowy numer rewizji; starszą wersję
   zachowuje. Synthetic fixture nie mogą być po cichu scalane z
   autentycznymi obserwacjami.
6. Transakcję SQL obejmuje lock per source i parametryzowane zapytania.
   Przy jakimkolwiek błędzie **całość wycofuje wywołujący**.
   Funkcja zapisująca nie tworzy połączeń i nie robi `commit`.

## Co obecnie można wykonać

`src/isl_v2/eia_versioned_ingest.py`:

- `prepare(...)`: przyjmuje pierwotne bajty EIA i wyprowadza walidowany
  plan źródła oraz konserwatywną datę dostępności bieżącego dokumentu;
- `fetch_plan(...)`: pobiera wyłącznie dozwolone strony przez HTTPS;
- `dry_run_summary(...)`: zwraca wyłącznie dane opisowe i liczniki,
  bez cen i treści HTML;
- `apply_plan(cursor,plan)`: **nie wywoływana przez CLI ani workflow**,
  kod transakcyjnego, wersjonowanego zapisu po wymaganym zatwierdzeniu
  nowej dedykowanej roli; przy braku roli lub nadmiernych uprawnieniach
  odmawia działania.

Domyślny CLI:

```bash
python -m src.isl_v2.eia_versioned_ingest --source wti
python -m src.isl_v2.eia_versioned_ingest --source brent
python -m src.isl_v2.eia_versioned_ingest --source henry_hub
python -m unittest discover -s tests -v
```

Nie ma flagi `--write`, zmiennej DSN, harmonogramu ani logiki wykonywania
zleceń. Publiczne ręczne EIA HTTPS dry-run jest w
[`.github/workflows/eia-versioned-ingest.yml`](../.github/workflows/eia-versioned-ingest.yml),
ale job wyzwalany automatycznie przez PR uruchamia tylko testy syntetyczne.

## Bramka przed realnym zapisem w Neon STAGING

Dziś **nie istnieje** zatwierdzona rola
`isl_eia_pit_staging_writer`. Przygotowano wyłącznie [projekt SQL NOLOGIN do przeglądu](../db/security/eia_pit_staging_writer_REVIEW_ONLY.sql): przed CREATE/GRANT wymaga dokładnego znanego znacznika izolowanej gałęzi STAGING, odmawia, jeśli rola istnieje, i wykonuje test uprawnień. **Nie uruchomiono tego SQL w Neon**. Istniejące `investment_lab_owner` jest
zbyt szerokie, `isl_agent_staging_limited` nie ma prawa dodawania
źródeł, a `isl_legacy_history_reader` tylko czyta historyczną tabelę.
Żadnego nie zastępuj kontem uprzywilejowanym.

Kolejna osobna decyzja operatora powinna dopuścić jedynie:

- Utworzenie dedykowanej roli na jednoznacznie zweryfikowanej
  izolowanej gałęzi Neon STAGING; pozwól na `SELECT/INSERT` tylko na
  `source_documents` i `price_observation_versions` oraz
  `SELECT` właściwych katalogów `data_sources` i `instruments`.
  Domyślnie odmów `CREATE`, `UPDATE/DELETE/TRUNCATE`, odczytu
  prywatnych portfeli, odczytu/zapisu starej tabeli `price_observations`,
  zapisu do dziennika agenta i admin membership.
- Oddzielne bezpieczne provisionowanie sekretu **poza** publicznym
  repozytorium. Nie powielaj hasła istniejących ról i nie drukuj DSN.
- Testy uprawnień + idempotencji + rewizji i PIT `prices_asof` na
  **jednorazowym PostgreSQL/gałęzi disposable**, przed właściwym
  pierwszym importem. **W CI zaimplementowano rzeczywisty disposable PostgreSQL 16**, odtwarzający istniejącą migrację 007 z PR #1 w izolowanej sztucznej bazie, wykonujący review-only skrypt roli i testujący zapis, idempotencję, korektę, `prices_asof` oraz odmowę po nadaniu nadmiernego odczytu. To **nie jest test połączenia z Neon STAGING**. Testy kursorowe są osobną bramką offline.
- Oddzielną, wyraźną zgodę na pierwszy rzeczywisty INSERT wyłącznie
  STAGING, z limitami wielkości i porównaniem przed/po.
- Dodatkowy przegląd sposobu zachowania oryginalnych bajtów źródła:
  obecna baza przechowuje **hash, URL i metadane**, ale nie same bajty.
  Bez niezmiennego archiwum źródła nie gwarantuje odtworzenia dokumentu
  po późniejszej zmianie treści strony.

Istniejące 695 wierszy referencyjnych WTI pozostają bez zmian.
Obecne 3 `source_documents` i 3 `price_observation_versions` to
wcześniejsze syntetyczne fixture, **nie zweryfikowana historia rynku PIT**.

## Kryteria odbioru

1. Pełne testy offline oraz osobny rzeczywisty **lokalny PostgreSQL 16** przechodzą w CI bez Neon i sekretów. Test PostgreSQL działa wyłącznie na hostcie `127.0.0.1` i bazie `investment_lab` w jednorazowym kontenerze; testowany zestaw ACL pochodzi z projektu review-only.
2. Rzeczywisty, manualny dry-run publicznego EIA pokazuje autentyczne
   oryginalne SHA i czasy pobrania, zero DB writes.
3. Dopiero po oddzielnym zatwierdzeniu nowej roli: niezależny test SQL na
   disposable DB, następnie kontrolowany pierwszy current snapshot
   na STAGING, udokumentowana idempotencja i rewizja.
4. *Obecna seria dokumentów* z data-dostępnością od pobrania może być
   punktem wyjścia dla **przyszłej** walidacji prospektywnej, ale
   **nie tworzy retrospektywnej historii PIT dla lat 2024–2026**.

M1/M2/M3: `HOLD_NO_CHANGE`. Issue #2 pozostaje otwarte.

## Dodatkowe zabezpieczenia źródłowe (19.10.2026 — kolejny PR)

Po sprawdzeniu pierwszej wersji uzupełniono model o **dwa niezależne hashe**:

- `original_html_sha256` — hash dokładnie pobranych oryginalnych bajtów HTML EIA; zmienia się również przy czysto graficznym przekształceniu strony.
- `semantic_observations_sha256` — deterministyczny SHA-256 kanonicznej listy unikalnych `(observed_for, Decimal.price)`, z identyfikatorami serii/źródła i jednostką. Wartość `101.10` oraz `101.1000` jest semantycznie identyczna; modyfikacja samego znacznika HTML nie stanowi rewizji ceny. **To hash treści bieżących notowań, nie historyczny certyfikat dat pierwszych publikacji.**

Fingerprint semantyczny wraz z liczbą rekordów i datami granicznymi trafia do metadanych przyszłego dokumentu; jest też zwracany w suchym raporcie (bez samych cen). **Brakujący trwały, niezmienny magazyn surowych HTML nadal jest osobnym ograniczeniem architektury** — aktualnie przechowujemy jedynie SHA i metadane, nie bajty.

Dodatkowo `prepare()` odrzuca bieżący snapshot EIA, jeżeli od daty pobrania do najnowszej obserwacji albo `Release Date` minęło ponad **14 dni**. Nie pozwala to potraktować bardzo starego katalogu cen jako świeżego źródła prospektywnego. Okres pierwszego wydania pojedynczych historycznych rekordów nadal pozostaje nieznany.

Guard dedykowanej roli odrzuca teraz również **UPDATE, DELETE i TRUNCATE** zarówno `source_documents`, jak i `price_observation_versions`. Rola potrzebuje wyłącznie `SELECT/INSERT` do tych dwóch tabel oraz katalogów; szczegóły w `db/security/eia_pit_staging_writer_REVIEW_ONLY.sql`. Zmiany roli NIE były stosowane w Neon.

**Aktualizacja faktycznego stanu STAGING:** 3 istniejące rekordy `source_documents` należą do `nbp_gold`. Jeden ma jawny `metadata.synthetic=true`, a pozostałe dwa nie mają jawnej wartości tego pola, co **nie pozwala** bez niezależnych dowodów klasyfikować ich jako rzeczywiste dane PIT. Nadal brak autentycznych historycznie wersjonowanych źródeł EIA.



## Dokładny moment pobrania — poprawka zegara HTTPS

`fetch_plan(source, fetched_at)` traktuje `fetched_at` jako rzeczywisty
czas rozpoczęcia żądania, **nie** czas pozyskania dokumentu. Pole
`snapshot.downloaded_at`, `retrieved_at` przyszłego `source_documents`
i `available_at` obserwacji otrzymują dopiero rzeczywisty moment
**po odczytaniu i zamknięciu całej odpowiedzi HTTPS**. Odrzucamy cofnięcie
zegara, znacznik bez strefy czasowej oraz żądania, których czas od startu
do pełnego pobrania przekracza 120 sekund. Specjalny zegar testowy jest
wstrzykiwany wyłącznie w testach syntetycznych; CLI używa rzeczywistego
zegara po zakończeniu odbioru. SHA nadal obejmuje te same dokładne bajty.

Chronologia wyznacza granicę widoczności danych dla **aktualnej** wersji
strony EIA. Nadal nie jest dowodem pierwszej historycznej publikacji ceny.
