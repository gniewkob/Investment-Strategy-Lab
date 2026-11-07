# Investment Strategy Lab — v0.13: przenośna kopia i test odtworzenia

**Stan: implementacja i testy w PR #96; wdrożenie na niezależnym nośniku wymaga osobnego dowodu.** Ten etap nie modyfikuje aktywnego kolektora, LaunchAgent, Neon, Coinbase ani portfela.

## 1. Dlaczego oddzielny system plików nie wystarcza

Inny katalog, punkt montowania, a nawet inny identyfikator urządzenia (`st_dev`) nie potwierdzają odseparowanej domeny awarii. Dwa wolumeny mogą być na jednym fizycznym dysku, tej samej macierzy albo korzystać z tego samego konta administratora, szyfrowania i mechanizmu usuwania danych. Kopia zasługuje na określenie *offsite/independent* dopiero po osobnej identyfikacji nośnika/usługi, zasad dostępu, polityki retencji i skutecznym teście odtworzenia **z tej lokalizacji**, a nie ze źródłowego Mac mini.

## 2. Kontrakt narzędzia

`scripts/shadow_offsite_export_v13.py` oferuje:

- `export` — wymaga wskazania istniejącej kopii v0.11, jej **wcześniej znanego** SHA-256 manifestu, absolutnej docelowej ścieżki katalogu użytkownika `0700` oraz nowej nazwy eksportu. Tworzy folder `0700` i trzy pliki `0600` przez `O_EXCL` oraz `O_NOFOLLOW`; nie aktualizuje i nie kasuje istniejących eksportów.
- `verify` — sprawdza bajty plików i hashe względem osobnego manifestu, następnie uruchamia kontrolę struktury SQLite oraz zakotwiczonego prefiksu v0.10. Folder jest otwierany po deskryptorze `dir_fd` i sprawdzany ponownie po odczycie. Użyte mechanizmy ograniczają typowe ataki symlink i podmianę ścieżki, ale nie stanowią ochrony przed uprzywilejowanym napastnikiem kontrolującym jednocześnie cały mount.
- Zwraca dokładnie `COPY_READBACK_VERIFIED_FAILURE_DOMAIN_UNVERIFIED`. Pola `independent_failure_domain_verified`, `offsite_verified`, `external_worm_verified` i `trusted_timestamp_verified` pozostają `false` nawet przy pozytywnym odczycie.

Brak automatycznej rotacji, kasowania i okresowego zadania. Nie kopiuje innych danych poza trzema plikami wcześniej zatwierdzonej kopii v0.11. W razie przerwania częściowy katalog jest pozostawiany do diagnostyki — narzędzie nie usuwa go i nie uznaje za poprawną kopię.

## 3. Przykładowy etap na Mac mini

**Bez automatycznego wyboru nośnika.** Operator musi jawnie wskazać istniejący, chroniony katalog na wybranym urządzeniu lub w podmontowanej usłudze, po osobnym sprawdzeniu dostępności i uprawnień. Przykład zawiera jedynie zmienną `DESTINATION`, nie zakłada rzeczywistego istnienia dysku, NAS ani chmury.

```bash
set -euo pipefail
umask 077
cd "$HOME/Repos/Investment-Strategy-Lab-shadow-v12"
# Nie zmieniaj działającego checkoutu. Po sprawdzeniu CI wykonaj osobne
# git fetch + checkout --detach zatwierdzonego SHA PR #96 w tym repo badawczym.

BASE="$HOME/Library/Application Support/InvestmentStrategyLabShadowEvidence"
SNAPSHOT="$BASE/backups/isl-shadow-24cd22787bbf465d80646e4513864809"
MANIFEST_SHA="bcef418b3273a09dfc4034d4f19ab6b639358fc3c5d191db26347f922a783f07"

# Wymaga świadomie wskazanej lokalizacji, uprzednio utworzonej z mode 0700.
DESTINATION="/ABSOLUTNA/SCIEZKA/DO/CHRONIONEGO/KATALOGU"

python3 -m scripts.shadow_offsite_export_v13 export \
  --snapshot "$SNAPSHOT" \
  --manifest-sha256 "$MANIFEST_SHA" \
  --destination-root "$DESTINATION" \
  --name "isl-research-20261107-01"

python3 -m scripts.shadow_offsite_export_v13 verify \
  --manifest-sha256 "$MANIFEST_SHA" \
  --destination-root "$DESTINATION" \
  --name "isl-research-20261107-01"
```

Nie uruchamiaj przykładowej ścieżki dosłownie. Nie używaj `sudo` ani nie zmieniaj uprawnień innych istniejących katalogów tylko dla potrzeb tego narzędzia. Poprawny eksport nie może być powtórzony pod tą samą nazwą — to zamierzona blokada nadpisania.

**Próba odtworzenia z docelowej lokalizacji** (odrębny prywatny katalog staging na Mac, nigdy aktywny rejestr):

```bash
mkdir -p "$BASE/offsite-restore-drills"
chmod 700 "$BASE/offsite-restore-drills"
python3 -m scripts.shadow_backup_restore_v11 restore-drill \
  --snapshot "$DESTINATION/isl-research-20261107-01" \
  --manifest-sha256 "$MANIFEST_SHA" \
  --restore-root "$BASE/offsite-restore-drills"
```

Zachowaj SHA-256 manifestu **w odrębnej domenie administracyjnej**. Dla rzetelnego testu DR nie polegaj wyłącznie na folderze źródłowym ani na kopii z tego samego urządzenia. Wykonaj test z osobnym dostępem do kopii i do przypiętego hasha, z zachowaniem dowodów.

## 4. Kryteria odbioru

| Bramka | Co potwierdza | Czego nie dowodzi |
|---|---|---|
| v0.13 CI unit + macOS | Integralność transferu, odmowę nadpisania, kontrolę symlink/path swap, odtworzenie w izolowanych testach | Że na Mac mini użyto zewnętrznego nośnika |
| Real Mac `export` + `verify` | Bajty skopiowane i odczytane z podanej lokalizacji | Fizyczną niezależność domeny awarii |
| Rzeczywiste odtworzenie z kopii | Techniczną odzyskiwalność | Pełne DR dla aktywnego systemu, ponieważ jest to tylko rejestr badań |
| Oddzielna administracja, trwałość i retencja + zewnętrzny hash | Elementy niezależności dowodowej, jeśli udokumentowane | Automatyczny WORM lub zaufany timestamp |

Nawet dwa różne `st_dev` nie ustawiają `offsite_verified=true`. Weryfikacja wymaga osobnych dowodów operacyjnych, których skrypt nie może wywieść z metadanych filesystemu.

## 5. Źródła

- [Python 3.12 os.open](https://docs.python.org/3.12/library/os.html#os.open) — obsługuje flagi POSIX i `dir_fd` dla otwierania względem katalogu.
- [Python 3.12 os.mkdir](https://docs.python.org/3.12/library/os.html#os.mkdir) — pozwala wskazać `dir_fd`, ale nie dowodzi domeny awarii.
- [SQLite PRAGMA integrity_check](https://www.sqlite.org/pragma.html#pragma_integrity_check) — sprawdza integralność struktury SQLite, nie certyfikuje źródła danych ani ich retencji.
- [NIST SP 800-34 Rev. 1, Section 3.4.1](https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final) — poradnik planowania ciągłości, zawierający strategie backupu i odzyskiwania; nie jest podstawą do twierdzenia, że sama różnica filesystemu dowodzi separacji.

**Operacje finansowe: 0. Brak zmian schedulera, Neon i portfeli.**
