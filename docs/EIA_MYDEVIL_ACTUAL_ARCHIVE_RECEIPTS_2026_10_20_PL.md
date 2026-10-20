# EIA — rzeczywiste lokalne przechwycenie oryginalnego HTML, 20.10.2026

**Stan:** wszystkie 3 oficjalne źródła EIA zostały przechwycone w istniejącym prywatnym katalogu POSIX na MyDevil (FreeBSD, Python 3.11) za pomocą `python3 -m scripts.eia_archive_local capture`. WTI następnie niezależnie sprawdzono poleceniem `verify` bez połączenia z internetem. Źródło dowodowe: **pełne, rzeczywiste stdout poleceń przesłane przez operatora** w rozmowie, a nie bezpośredni odczyt plików MyDevil przez asystenta. Nie zapisano surowych HTML ani cen na GitHub.

## Stan dokumentów

| Źródło | Rzeczywisty ukończony odbiór UTC | Raw HTML SHA-256 | Semantic date/price SHA-256 | Utworzony object / receipt | Walidacja |
| --- | --- | --- | --- | --- | --- |
| WTI — `eia_wti_daily` | `2026-10-20T09:17:01.691564+00:00` | `4ecd9261dbc6fe1ba583d017af72fb37d2a33d626a11b4ab7940227d1122f489` | `648f3ff4403a2d1ea0232eb1f8ce9b90ae6e41fc31963fc3f59864858c036002` | true / true | `capture: immediate_independent_replay=true`; osobne `verify: EIA_RAW_HTML_ARCHIVE_INDEPENDENT_OFFLINE_VERIFIED` |
| Brent — `eia_brent_daily` | `2026-10-20T09:19:15.240752+00:00` | `be659c06a7f497afa0e49c976defa774cd70814d04bda7a20afac890d566f2ca` | `d5746347f4d6371f9df882ce134bdd8280c226dcb2e557a3627a45537c3a9cd9` | true / true | `capture: immediate_independent_replay=true` |
| Henry Hub — `eia_henryhub_daily` | `2026-10-20T09:19:22.087511+00:00` | `70b294c14f1deafbcd9c4b898d5c94ab971857013852197315616a67199d01fc` | `0f226a4119e91d39d0117ff43f4dfded58d002ae1cc47d35a8306347cf3293c5` | true / true | `capture: immediate_independent_replay=true` |

Każdy `capture` raportował `status=EIA_RAW_HTML_ARCHIVED_LOCAL_STAGING_NOT_WORM`, `archive_backend=PRIVATE_LOCAL_POSIX_STAGING_NOT_WORM`, `database_connections=0`, `database_writes=0`, `immutable_object_storage_certified=false`.

Po `capture` WTI operator wykonał jawnie i niezależnie:

```text
verify --source wti --sha256 4ecd9261dbc6fe1ba583d017af72fb37d2a33d626a11b4ab7940227d1122f489 --retrieved-at 2026-10-20T09:17:01.691564+00:00
status=EIA_RAW_HTML_ARCHIVE_INDEPENDENT_OFFLINE_VERIFIED
```

`verify` też raportował `database_connections=0`, `database_writes=0` i zgodne raw/semantic SHA oraz `immutable_object_storage_certified=false`. Operator nie przekazał jeszcze osobnych `verify` offline dla Brent i Henry Hub. Ich automatyczny readback/reparse w `capture` przeszedł poprawnie.

## Porównanie z pierwszym rzeczywistym live EIA dry-run

[Manual live źródła 19.10.2026 — run #39330400127](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330400127) zawierał semantyczne SHA przy `max_age_days=420`: WTI `999e76f1...`, Brent `d5746347...`, Henry Hub `b8c21f1f...`.

Bieżące archiwum 20.10 zachowuje **identyczny SHA Brent** `d5746347f4d6371f9df882ce134bdd8280c226dcb2e557a3627a45537c3a9cd9`, ale **inne SHA WTI i Henry Hub**. Różnica SHA nie oznacza automatycznie rewizji ceny. `prepare` stosuje **ruchome okno 420 dni** od dnia pobrania: 19.10 cutoff obejmował dzień 25.08.2025, a 20.10 cutoff zaczyna się 26.08.2025; wcześniejszy live run wskazywał WTI/Henry Hub `first_observed=2025-08-25`, Brent `first_observed=2025-08-26`. Zmiana zakresu wejściowych dat jest zatem wystarczającym wyjaśnieniem różnicy SHA WTI/Henry Hub i spójności Brent; aby wykluczyć dodatkowe rewizje cen, porównaj znormalizowane rekordy po ograniczeniu do wspólnego zakresu dat, nie tylko pełne hashe. Bez tego nie deklarować, że ceny nie były rewidowane.

## Czego dowody jeszcze NIE zapewniają

- Nie istnieje niezależna, nieusuwalna retencja WORM/Object Lock. MyDevil jest roboczym, prywatnym archiwum z `O_EXCL` i ograniczeniami 0700/0600; administrator ZFS lub użytkownik może usunąć pliki.
- Snapshot bieżącej oficjalnej strony EIA nie potwierdza rzeczywistych dat pierwszej publikacji cen dla dat z 2025/2026. W manifestach: `UNVERIFIED_HISTORICAL_PUBLICATION`.
- Nie sprawdzono jeszcze szczegółów prywatnego backupu, limitów inode, quota ani odtworzenia po utracie hosta. `fstatvfs` pokazuje wolną przestrzeń całego wspólnego ZFS, a nie rzeczywiste saldo limitu konta MyDevil.
- Nie istnieje dedykowana rola importera Neon ani zgoda na pierwsze `INSERT` do EIA `source_documents` / `price_observation_versions`. **Nie było żadnego Neon WRITE/ACL/secret/schedule, produkcji ani realnych transakcji**.

## Kolejność dalszej pracy

1. Na MyDevil zrobić ręczne osobne, tylko-odczytowe `verify` dla Brent i Henry Hub, używając exact `sha256` i `retrieved_at` z tabeli.
2. Odczytać z **istniejących manifestów JSON** pola `semantic_observation_count`, `first_observed_for`, `last_observed_for`, `max_age_days`, `current_source_release_day`; porównać wspólne okno z 19.10 przed wnioskowaniem o rewizjach cen.
3. Wybrać niezależną retencję z WORM, np. sprawdzony S3-compatible Object Lock na odpowiedniej klasie OVHcloud, z okresem retencji i osobno zatwierdzonymi uprawnieniami; niezależne GET → SHA → wersja obiektu → retain-until.
4. Dopiero po osobnym zatwierdzeniu roli/ACL/poświadczeń i limitowanego pierwszego `INSERT` do Neon STAGING przejść do wersjonowanego repozytorium dowodów.

**Badawcze M1/M2/M3 nadal `HOLD_NO_CHANGE`, historyczne `MARKET_DATA_NOT_READY`.**

Powiązane: [archiwizator](EIA_ORIGINAL_HTML_ARCHIVE_PL.md), [MyDevil/OVH architektura](EIA_MYDEVIL_OVH_ARCHIVE_READINESS_PL.md), [wcześniejsze live receipts](EIA_LIVE_RECEIPTS_2026_10_19_PL.md).
