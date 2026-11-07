# Investment Strategy Lab — v0.11: kopia zweryfikowanego rejestru i test odtworzenia

**7 listopada 2026 — wyłącznie warstwa badawcza, bez operacji finansowych.**

## 1. Cel i zakres wdrożenia

`scripts/shadow_backup_restore_v11.py` przygotowuje lokalną kopię rejestru v0.9 z powiązanym plikiem kotwicy v0.10. Odtwarzanie przebiega do NOWEGO katalogu; nigdy nie aktualizuje istniejącego rejestru ani nie aktywuje odtworzonego stanu. Kontrolę danych wykonują dotychczasowe `verify_anchor` (hash kotwicy, liczba rekordów, hash zakotwiczonego prefiksu) i niezależny `sqlite3 PRAGMA integrity_check`.

Pole `offsite_verified` pozostaje `false`. Kopia lokalna na tym samym urządzeniu **nie jest** separacją domen awarii, kopią WORM, certyfikowanym znacznikiem czasu ani wdrożonym mechanizmem Disaster Recovery.

### Kontrakt uruchomieniowy

- `create`: wymaga istniejącej bazy, pliku kotwicy i **osobno uzyskanego** `anchor_sha256`. Korzysta z SQLite `Connection.backup()` oraz tworzy prywatny katalog kopii z `ledger.sqlite3`, `anchor.json` i `manifest.json`. Manifest zawiera SHA-256 obu plików, zakotwiczony head i liczbę wpisów.
- `verify`: wymaga `manifest_sha256` podanego poza kopią; waliduje bajty wszystkich trzech plików, pełną spójność SQLite i zakotwiczony prefiks historii.
- `restore-drill`: wymaga zweryfikowanej kopii i prywatnego katalogu docelowego; odtwarza do nowego folderu `isl-restored-<uuid>`, weryfikuje jeszcze raz i kończy na statusie `RESTORE_VERIFIED_NOT_ACTIVATED`.

Katalogi bazowe muszą istnieć, nie mogą być symlinkami ani mieć dostępu grupy/pozostałych (POSIX `0700`). Pliki powstają z uprawnieniami `0600`. Kopia jest odrzucana w przypadku podmiany hashy, uszkodzenia SQLite, skasowanego ogona historii lub nieautoryzowanego nadpisania danych w testach.

## 2. Odbiór GitHub Actions

- `.github/workflows/working-engine-v01-ci.yml`: testy offline `tests/test_shadow_backup_restore_v11.py`.
- `.github/workflows/github-checkpoint-audit-v08.yml`: po rzeczywistym odczycie v0.7, kwalifikacji v0.8, zapisie do v0.9 i kotwicy v0.10 tworzy kopię v0.11, sprawdza manifest i wykonuje test odtwarzania na **jednorazowym runnerze**.
- Wersjonowany artefakt workflow zawiera komplet trzech plików kopii v0.11 oraz metadane testów. Ustawiona retencja `90` dni nie zastępuje niezależnego archiwum.

Przed produkcyjnym przyjęciem wymagane są: dokładny SHA przetestowanego kodu, wynik finalnego GitHub Actions, weryfikacja pobranego ZIP i osobny backup na wolumenie Mac mini. Nie twierdzimy, że te kroki lokalnego wdrożenia zostały wykonane.

## 3. Instrukcja lokalnego uruchomienia (nie wykonano na Mac mini)

Po sprawdzeniu źródłowego commitu i testów, w dedykowanym klonie repozytorium:

```bash
umask 077
BASE="$HOME/Library/Application Support/InvestmentStrategyLab"
mkdir -p "$BASE/backups" "$BASE/restore-drills"
chmod 700 "$BASE/backups" "$BASE/restore-drills"

# Wstaw wartość SHA kotwicy z OSOBNO zachowanego rekordu audytowego.
python3 -m scripts.shadow_backup_restore_v11 create \
  --ledger "$BASE/ledger/shadow-evidence.sqlite3" \
  --anchor "$BASE/anchor-outbox/isl-shadow-anchor-v10-...json" \
  --anchor-sha256 "<SHA256_KOTWICY>" \
  --destination-root "$BASE/backups"
```

Zapisz `manifest_sha256` z wyniku **poza** katalogiem backupu; najlepiej w niezależnie administracyjnie chronionym, wersjonowanym repozytorium dowodowym. Następnie:

```bash
python3 -m scripts.shadow_backup_restore_v11 verify \
  --snapshot "$BASE/backups/<nazwa-nowej-kopii>" \
  --manifest-sha256 "<SHA256_MANIFESTU>"

python3 -m scripts.shadow_backup_restore_v11 restore-drill \
  --snapshot "$BASE/backups/<nazwa-nowej-kopii>" \
  --manifest-sha256 "<SHA256_MANIFESTU>" \
  --restore-root "$BASE/restore-drills"
```

**Gate odtwarzania:** lokalne odtworzenie nie ustanawia backupu *offsite*. Zweryfikuj ręcznie przechowanie oddzielnej kopii na zaszyfrowanym, niezależnie zarządzanym nośniku oraz jej odczyt. Osobno sprawdź kopię po awarii/symulowanym utraceniu kopii źródłowej. Bez tego deklaracja `DR_READY` byłaby nieuzasadniona.

## 4. Założenia i ograniczenia

- Udokumentowana spójność pliku i odzyskanie w bezpiecznym stagingu, nie niezmienność wobec lokalnego administratora.
- Zapis manifestu w tym samym katalogu nie jest zewnętrznym dowodem; wymagany jest **osobny** pinned SHA-256.
- Brak automatycznego uruchomienia `launchd`, brak kopii do chmury, brak dostępu do Mac mini ani do Neon, Coinbase czy portfeli.
- Nie istnieje jeszcze zatwierdzony komplet serii `GLOBAL_EQUITY_TR_PLN`, `PL_BONDS_TR_PLN` i `GOLD_TR_PLN`; modele M1–M3 pozostają w statusie badawczym bez rzeczywistego backtestu.

## 5. Autorytatywne źródła

| Mechanizm | Dokumentacja pierwotna | Zakres dowodu |
|---|---|---|
| Spójna kopia SQLite | [Python 3.12 `sqlite3.Connection.backup`](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup) | API tworzenia kopii działające również przy jednoczesnym dostępie innych klientów; nie gwarantuje trwałości offsite. |
| Kontrola integralności bazy | [SQLite `PRAGMA integrity_check`](https://www.sqlite.org/pragma.html#pragma_integrity_check) | Sprawdza strukturę bazy i wskazane ograniczenia, ale **nie** integralność względem niepowiązanych dowodów i nie kontroluje kluczy obcych. |
| Czas przechowywania artefaktów CI | [GitHub `upload-artifact` — Retention Period](https://github.com/actions/upload-artifact#retention-period) | Artefakt ma czasową retencję; repo/runner CI nie stanowi automatycznie trwałego archiwum. |

**Status wdrożenia na Mac mini: NIE URUCHOMIONO. Operacje finansowe: 0.**
