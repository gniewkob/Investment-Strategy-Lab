# EIA RAW HTML — prywatne archiwum źródła i weryfikacja offline

**Wersja robocza (19.10.2026).** Inżynierska funkcja do zachowania ORYGINALNYCH bajtów oficjalnych HTML EIA razem z rzeczywistym `retrieved_at`, oryginalnym `raw_html_sha256` i niezależnym hashem serii `(observation_date, Decimal price)`. Bez DB, hasła, zleceń, planowania lub automatycznego triggera.

## Dlaczego dwa dowody?

- **`objects/<sha256>.html`**: dokładnie pobrane źródłowe bajty HTML, bez normalizacji, serializacji i zmian.
- **`receipts/<source_code>/<UTC_timestamps>_<sha256>.json`**: odrębny, nieedytowalny przez adapter manifest dla *każdego pobrania* danego dokumentu. Przechowuje deklarowaną bieżącą datę wydania EIA (`DAY`), rzeczywisty czas ukończenia odbioru, okno parsowania, oba SHA, liczbę notowań, zakres dat i `current_snapshot_available_not_before`.
- Zmiana layoutu HTML bez zmiany kwotowań zmienia **raw SHA**, ale pozostawia **semantic SHA**. Ta sama treść pobrana po kilku dniach dostaje **osobny manifest pobrania**, lecz wykorzystuje ten sam obiekt HTML.
- Manifest zawsze zawiera `source_vintage=CURRENT_SNAPSHOT_UNVERIFIED_HISTORICAL_PUBLICATION` i `independent_historical_publication_vintages_verified=false`. Odczyt dokumentu z 2026 nie dowodzi dostępności pojedynczej ceny w 2024.

## Operator: jak bezpiecznie utworzyć lokalne prywatne archiwum

Wykonuj na **trwałym prywatnym wolumenie**, poza repozytorium Git, poza folderami synchronizującymi się publicznie i bez dostępu współdzielonego. Root musi już istnieć, być **absolutną ścieżką**, należeć do użytkownika i mieć brak praw grupy/others (`0700`). Adapter nie tworzy katalogu głównego, odmawia katalogów symlinkowanych, dostępnych dla innych i repozytorium Git. Ścieżki ani bajty HTML nie są drukowane w raportach.

Przykładowa konfiguracja POSIX (zastąp `/private/isl-eia-archive` prawdziwym własnym trwałym wolumenem):

```bash
install -d -m 700 /private/isl-eia-archive
python -m scripts.eia_archive_local capture --source wti --archive-root /private/isl-eia-archive
python -m scripts.eia_archive_local capture --source brent --archive-root /private/isl-eia-archive
python -m scripts.eia_archive_local capture --source henry_hub --archive-root /private/isl-eia-archive
```

Każdy `capture` robi **nowe HTTPS pobranie**, mierzy czas po odebraniu i zamknięciu całej odpowiedzi, waliduje oryginalny URL, treść, daty, SHA i chronologię, zapisuje obiekt + manifest bez możliwości ich nadpisania z poziomu aplikacji, `fsync`-uje plik i katalog, a następnie od razu odtwarza zapis **z samego lokalnego archiwum**. Użytkownik zobaczy tylko SHA, source, realne `retrieved_at`, `object_created`, `receipt_created`, flagę `immediate_independent_replay=true` i **`immutable_object_storage_certified=false`**.

Po zachowaniu wyniku z `capture`, odtwórz konkretne pobranie bez internetu:

```bash
python -m scripts.eia_archive_local verify \
  --source wti \
  --archive-root /private/isl-eia-archive \
  --sha256 <oryginalny_64_znakowy_sha256_z_wyniku_capture> \
  --retrieved-at <pełny_ISO_8601_czas_z_wyniku_capture>
```

Weryfikacja nie korzysta z sieci, Neon, ponownego pobrania EIA, starego `IngestionPlan` ani wcześniejszych cen; odczytuje `html` + manifest, ponownie parsuje oryginalne bajty przy **zapisanej dacie pozyskania**, sprawdza dokładnie oba SHA, serię kwotowań i status `CURRENT_SNAPSHOT_UNVERIFIED_HISTORICAL_PUBLICATION`. Uwaga: lokalne archiwum może zawierać surowe notowania; **nie dodawać tych katalogów do repozytorium lub publicznych GitHub Actions artifacts**.

## Granice trwałości / WORM

Ten etap daje **odtwarzalne prywatne źródłowe bajty i dowód zgodności**, ale **nie** niezależną gwarancję niezmienności. Zwykły system plików nie jest WORM — właściciel lub administrator może usunąć/przepisać obiekt i manifest, a następnie wygenerować inne hashe. `O_EXCL` odmawia nadpisania przez adapter, `O_NOFOLLOW` blokuje symlinki, `0600/0700` ogranicza odczyt, a `fsync` redukuje ryzyko utraty danych w awarii. Żaden z tych mechanizmów nie zastępuje storage-level Object Lock.

**Przed certyfikacją „immutable archive”**: operator powinien wybrać zewnętrzny, niezależny magazyn z niezmienną retencją i audytem, np. S3-compatible Object Lock / WORM, z włączonym versioning, retencją nieusuwalną dla roli ingest, zakazem nadpisania i testem `GET + sha256` po niezależnym odczycie. Klucz `objects/<sha256>.html` musi zawsze odpowiadać oryginalnym bajtom; manifest odbioru powinien zawierać identyfikator wersji obiektu i dowód ustawionej retencji. Okres przechowywania i licencję na archiwizację oryginalnych źródeł należy zatwierdzić osobno. Nie włączono takiego magazynu, sekretów, automatycznej synchronizacji ani retencji.

## Stan rzeczywistego archiwum a stare runy

Realne [WTI↔Neon 695/695 #39330376388](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330376388) oraz [3 oficjalne źródła EIA #39330400127](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330400127) **nie zapisywały oryginalnych bajtów HTML**. Zapisano tylko ich SHA, semantyczne SHA i czasy pobrania. Nie można uczciwie twierdzić, że obecny kod odzyska dokładnie te bajty z tamtych żądań. Kolejny `capture` tworzy **NOWE** źródło/manifest ze swoim czasem i SHA. Nie antydatować `retrieved_at`.

Ten etap NIE nadaje uprawnień nowej roli `isl_eia_pit_staging_writer`, NIE tworzy EIA `source_documents` czy `price_observation_versions` w Neon STAGING, NIE certyfikuje historycznych pierwotnych publikacji EIA i NIE uruchamia automatycznego importu. Modele symulacyjne M1–M3 nadal `HOLD_NO_CHANGE`.

## Warunki odbioru (w kolejności)

1. Testy offline: zapis dokładnych bajtów, pierwsze/ponowne pobranie, odrębne timestamp manifests, hash dla kosmetycznych i realnych zmian, kontrola nieuprawnionych lokalizacji/symlinków, uszkodzenia bajtów, uszkodzenia manifestu i niezależne odtworzenie.
2. Operator wybiera istniejący trwały prywatny lokalny dysk/volumen i uruchamia co najmniej jeden manualny `capture` oraz `verify`; to wciąż **LOCAL STAGING NOT WORM**.
3. Osobna ocena/konfiguracja prawdziwie niezmiennego archiwum docelowego z odczytem po zapisie, retencją i audytem; nie tworzyć sekretów automatycznie.
4. Dopiero potem oddzielna zgoda na rolę/ACL/credentials i pierwszy bounded-versioned `INSERT` wyłącznie Neon STAGING.

Zobacz [dowody live](EIA_LIVE_RECEIPTS_2026_10_19_PL.md), [GO/NO-GO](EIA_FIRST_SNAPSHOT_GO_NO_GO_PL.md) i [Issue #2](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2).
