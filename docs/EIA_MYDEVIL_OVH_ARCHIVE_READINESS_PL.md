# EIA — MyDevil + OVHcloud: kontrola archiwum i decyzja o retencji

**Status projektu: 20.10.2026.** Archiwum EIA jest krokiem w projekcie badawczym (bez zleceń, sygnałów transakcyjnych i rzeczywistych inwestycji). [PR #36](../src/isl_v2/eia_raw_archive.py) udostępnia lokalny zapis oryginalnych bajtów i niezależne `verify`, ale nie gwarantuje niezmienności WORM.

## Potwierdzony zakres dostępu — nie zakładać nieistniejących ścieżek

W tej sesji połączenie GitHub i odczyt Neon STAGING są dostępne. **Brak działającego dostępu SSH `ssh devil` w obecnym środowisku wykonawczym**; nie zostały wykonane komendy ani zmiany na serwerze MyDevil. Znany wcześniejszy opis infrastruktury mówi o hostingu **FreeBSD**, `/bin/devil`, SSH, montowanym zasobie kopii i snapshotach ZFS, lecz nie dostarcza potwierdzonej ścieżki prywatnego root archiwum, uprawnień, wolnej przestrzeni ani zasad odtwarzania aktualnych snapshotów. Nie wolno ich zgadywać lub mylić automatycznych kopii z WORM.

Zamiast automatycznego `mkdir`, chmod, synchronizacji albo transferu dowodowych dokumentów, dodano **wyłącznie odczytowy**:

```bash
python3 -m scripts.eia_archive_storage_preflight \
  --archive-root /ABSOLUTNA/ISTNIEJACA/PRYWATNA/SCIEZKA
```

Ten kod wykonuje odczyty metadanych przez `open + fstat + fstatvfs` oraz sprawdza opcjonalne foldery `objects` i `receipts` bez ich tworzenia (`O_NOFOLLOW`). Wymaga istniejącej absolutnej ścieżki właściciela użytkownika z uprawnieniami prywatnymi 0700, poza Git. Zwraca agregat wolnej przestrzeni, stan obu folderów, stan właściciela i politycznie poprawne **`worm_object_lock_verified=false`** / **`zfs_snapshot_and_restore_verified=false`**. Nie drukuje ścieżek, sekretów, cen ani hosta.

`PRIVATE_LOCAL_METADATA_PREFLIGHT_PASS` oznacza **tylko poprawną lokalną konfigurację bezpieczeństwa i odczyt `fstatvfs`** — nie sprawdza quota dostawcy, przypięcia do trwałego wolumenu, backupów, odtwarzalności, rzeczywistego dostępu SSH, możliwości zapisu ani obecności niezależnej kopii danych. Próg domyślny **64 MiB** stanowi małą rezerwę operacyjną, a nie dopuszczenie wydajności lub trwałości. Przed pierwszym `capture` wymagane jest osobne sprawdzenie limitów MyDevil i realnego trwałego katalogu.

## Kolejność na MyDevil — odczyt przed zmianą konfiguracji

Operator uprawniony do konta MyDevil może wykonać **wyłącznie odczytową** diagnostykę po podłączeniu własnego SSH:

```bash
ssh devil 'uname -s; id -un; command -v python3; python3 --version; df -h "$HOME"'
```

Polecenie nie tworzy archiwum ani nie zmienia konfiguracji. Dla wybranego przez operatora, istniejącego katalogu trzeba dodatkowo ustalić: właściciela i uprawnienia, czy katalog jest na trwałym własnym wolumenie, wielkość **rzeczywistego quota**, politykę backup/ZFS, czy można z niego odczytać źródłowe bajty po restarcie i po awarii. **Nie uruchamiać** przykładowej ścieżki z dokumentacji jako rzeczywistej lokalizacji: jest placeholderem. Jeśli interpreter nie jest zgodny z wymaganym Pythonem dla kodu repozytorium, użyć prywatnego przygotowanego środowiska na własnym komputerze, bez instalacji na MyDevil bez zgody.

Dopiero po zaakceptowaniu katalogu:

1. Użyć operatorowego `capture --source wti|brent|henry_hub --archive-root <prywatny_root>` z [runbooka](EIA_ORIGINAL_HTML_ARCHIVE_PL.md). Każde `capture` tworzy **nowy** autentyczny snapshot z chwilą pobrania. Nie rekonstruuje bajtów z poprzednich uruchomień na GitHub.
2. Przetestować `verify --source ... --sha256 ... --retrieved-at ...` niezależnie, bez internetu.
3. Sprawdzić kopię i możliwość odtworzenia z backupu. Sam snapshot ZFS pod wspólną administracją z MyDevil nie zapewnia niezależnego trwałego zatrzymania przed modyfikacją przez administratora.

## Docelowa niezależna retencja: OVHcloud Object Storage Object Lock

OVHcloud dokumentuje obsługę **Object Lock (WORM)** w S3-kompatybilnym Object Storage, lecz **nie dla klasy Cold Archive**. Nie tworzyć na ślepo niewspieranej kombinacji klasy i regionu. Źródło: [FAQ OVHcloud Object Storage](https://help.ovhcloud.com/csm/en-ca-public-cloud-storage-s3-faq?id=kb_article_view&sysparm_article=KB0059673). Dokumentacja OVH opisuje też bucket z Object Lock, versioning i retencją dla backupów: [OVHcloud KB0074619](https://help.ovhcloud.com/csm/pl-nutanix-set-up-pcbr?id=kb_article_view&sysparm_article=KB0074619).

**Rekomendowana architektura docelowa:**

```
EIA official HTTPS (nowe pobranie)
    └─ realny completion_time + original_html_sha256 + semantic_sha256
        ├─ PRIVATE LOCAL POSIX (MyDevil / operator): object HTML + receipt JSON
        └─ ODDZIELNE Object Storage (OVHcloud, WORM/retencja)
              ├─ identyczne original HTML bajty (wersjonowany obiekt)
              └─ oddzielny manifest i version-id / retention proof
                  └─ po niezależnym GET porównaj SHA-256 i retencję
```

Warunki bramki WORM wymagające odrębnej decyzji/konfiguracji:

- S3-compatible bucket na potwierdzonej klasie, Object Lock i versioning faktycznie włączone, **niepubliczny**, odrębna rola do dodawania obiektów i do ich późniejszego audytu.
- Test pełnego `PUT → HEAD/GET konkretnej wersji → SHA-256` oraz odczyt faktycznego `Retention Mode`, `RetainUntilDate` i `VersionId`, z niezależnego konta read-only. Testuj nieodwracalność zgodnie z wybraną polityką, nie wymuszaj destrukcyjnego usuwania danych.
- Wariant `COMPLIANCE` zapewnia silniejszą niezmienność objętej retencją wersji niż `GOVERNANCE`; nie podpisywać nieprzemyślanej wieloletniej retencji bez zatwierdzenia kosztów i okresu przechowywania. Zwróć uwagę, że Object Lock chroni **konkretną wersję obiektu**, nie powstrzymuje utworzenia nowych wersji pod tym samym kluczem. Dokumentacja AWS wyjaśnia semantykę S3 Object Lock: [AWS User Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html).
- Przed udostępnieniem agentowi możliwości zapisu skonfiguruj politykę IAM bez `DELETE`, bez prawa skracania retencji lub omijania `GOVERNANCE`, bez dostępu do innych bucketów; sekret poza repo i logami.
- Zachowuj przy dowodzie EIA dokładny `retrieved_at`, RAW SHA, semantic SHA, identyfikator wersji i retencję. Test na wygasającym obiekcie wykonaj najpierw w osobnym **testowym bucketcie**.

**Nie ma obecnie potwierdzonego docelowego OVHcloud bucketu, retencji, nowych kluczy lub ról.** Sam PR nie tworzy zasobów OVH ani MyDevil, nie korzysta z Neon i nie włącza harmonogramu.

## Następne bramki

| Obszar | Stan |
| --- | --- |
| Dwa rzeczywiste manualne audyty EIA i zgodności WTI | PASS, potwierdzone wcześniej |
| Kod prywatnego `capture + verify` | Na `main`, testowany w CI |
| Sprawdzenie MyDevil przez `ssh devil` | **PENDING — brak dostępu SSH w aktualnym środowisku** |
| Lokalny read-only preflight wybranego root | Kod gotowy, wykonanie na MyDevil PENDING |
| Prywatny `capture + verify` na trwałym root | PENDING |
| Independent WORM-backed Object Storage | PENDING / niezdecydowana konfiguracja |
| Zatwierdzenie roli Neon STAGING i pierwszy `INSERT` | **NO-GO**, wymagane osobne zatwierdzenie |
| Certyfikowane historyczne daty oryginalnej publikacji | **NO-GO** |
| M1/M2/M3 | `HOLD_NO_CHANGE` |

Zasada: nie nazywaj PIT zweryfikowanym tylko dlatego, że bieżąca strona EIA zawiera dawne daty notowań.
