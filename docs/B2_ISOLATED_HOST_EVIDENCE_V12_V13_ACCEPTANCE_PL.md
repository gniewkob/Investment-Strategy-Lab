# ISL B2 — izolacja hosta v0.12 i kopia dowodowa v0.13

**Status:** eksperymentalny Draft PR B2, baza [Draft B1 #100](https://github.com/gniewkob/Investment-Strategy-Lab/pull/100), zależny pośrednio od [Draft A2 #99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99). Nie jest to produkcyjne wdrożenie ani potwierdzenie niezależnego storage.

## Co zawiera

- `scripts/deploy_shadow_evidence_mac_v12.py` i jego oryginalny test — odizolowany nowy katalog badawczy, porównanie podanego pełnego commitu Git, walidacja oryginalnego archiwalnego SHA i lokalne sprawdzenie ledger/anchor/backup/restore. Nie wolno modyfikować istniejących katalogów, schedulerów launchd ani sesji portfela.
- `scripts/shadow_offsite_export_v13.py` i test — zapis do jawnie przekazanego prywatnego katalogu, wykluczenie symlinków, zakaz nadpisywania, kontrola digestów i read-back. **Weryfikacja kopii na tym samym komputerze nie dowodzi offsite, oddzielnej domeny awarii, WORM, ani legalnej retencji.**
- Dedykowany CI `.github/workflows/isl-b2-evidence-host-ci.yml`, tylko fixture na `TemporaryDirectory`, Python 3.12 Linux/macOS, połączenia Python socket zabronione, bez tokenów GitHub zapisywalnych i bez produkcyjnych danych.
- Cztery pliki źródłowe/testowe przeniesione byte-for-byte z dużego Draft #96; należy potwierdzić sha ich Git blobów niezależnie.

## Zależności i ograniczenia

B2 korzysta z B1: `shadow_evidence_ledger_v09`, `shadow_external_anchor_v10`, `shadow_backup_restore_v11`, `shadow_decision_engine_v05`, ich testów oraz oryginalnego archiwalnego bundle w `evidence/shadow/v09`. Dla testów z brakiem realnych rynkowych źródeł wszystkie decyzje są `HOLD_CASH`; nic nie jest wykonywane.

Ten PR **nie uruchamia instalatora `main()` na komputerze operatora**, nie podaje prawdziwego `--base-dir`, nie tworzy rzeczywistej lokalizacji offsite, nie ustawia harmonogramów, nie używa Neon, wallet, brokerów ani zewnętrznych danych. Zaliczenie CI oznacza poprawną symulację zachowania operacji na izolowanych testowych katalogach.

Przed jakimkolwiek operacyjnym użyciem wymagane są osobno: weryfikacja ownera i ACL katalogu docelowego, niezależna domena awarii, polityka retencji, monitorowanie ostatniej prawidłowej kopii, prawidłowy test restore oraz potwierdzenie źródłowego hasha i punktu czasowego oryginalnego zapisu. Local SQLite hash chain nadal nie jest WORM.

## Bramka łączenia

B2 jest zależnym Draft, nie wolno go scalać przed B1 i A2. Nakładanie się na duży PR #96 wymaga usunięcia z niego zakresu zastąpionego przez małe PR. Mergowanie nie jest objęte odbiorem. Zamrożony Vanguard v0.22 i v0.23 SHA pozostaje nietknięty; finansowe operacje = 0.
