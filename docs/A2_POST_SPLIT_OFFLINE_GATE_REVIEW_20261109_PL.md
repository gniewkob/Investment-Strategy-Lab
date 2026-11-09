# A2 — niezależny review granic sieciowych (2026-11-09)

**Zakres:** [Draft PR #99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99), offline source evidence. Nie jest to dopuszczenie do aktywnego pobierania danych, prowadzenia transakcji ani kwalifikacji M1–M3.

## Ustalona luka

`scripts/nbp_bondspot_exact_date_v04.match` działał jako element pakietu offline, ale gdy źródła NBP/BondSpot miały różne dni publikacji, wywoływał `nbp_reference_capture.capture(day, day)` bez funkcji `fetch`. Ten helper miał domyślny transport `urlopen`, więc **zwykłe wywołanie funkcji poza CI mogło samodzielnie połączyć się z NBP**. Dotychczasowe testy używały stubów albo blokowały gniazda sieciowe tylko na czas CI. Dokumentacja ujawniała ten wyjątek, ale nie ograniczała go w kontrakcie kodu.

To nie był dowód nieautoryzowanego pobierania danych; ryzyko dotyczyło **niejawnego przejścia z offline do online** przy przyszłym użyciu API.

## Poprawka fail-closed

- `match`: jeśli są brakujące dokładne dni i `fetch is None`, zwraca `EXPLICIT_FETCH_REQUIRED` **zanim** wywoła capture. Gdy wszystkie daty są zgodne, funkcja nadal działa lokalnie bez fetchera.
- `capture`: nie ma już domyślnego transportu HTTP. Programista musi podać funkcję pobierającą dane jawnie.
- `nbp_reference_capture` CLI: wymaga jawnej flagi `--allow-public-nbp-fetch`; bez flagi nie pobiera niczego. Techniczna możliwość jawnego odczytu publicznego NBP nie stanowi automatycznej zgody na archiwizację, dalsze wykorzystanie ani promocję serii do total return.
- Nowe testy `tests/test_a2_explicit_source_access_v01.py` weryfikują oba domyślne tryby odmowy, brak requestu przy identycznych datach, nadal działający offline stub oraz bramkę CLI. CI uruchamia je pod blokadą Python socket connections.

## Integralność i reconciliacja względem PR #96

W pierwotnym podziale A2 było **8/8 identycznych oryginalnych Git blobów**. Po tym niezależnym review poprawiono celowo dwa oryginalne źródła (`nbp_bondspot_exact_date_v04.py` i `nbp_reference_capture.py`) **wyłącznie w PR #99**. Pozostałe **6/8 oryginalnych plików** zachowuje pierwotne bajty. Testy offline, pierwotne hash receipts i dane źródłowe nie zostały nadpisane. Wymagane jest odrębne rozstrzygnięcie overlap z #96 przed jakimkolwiek merge.

**Granica:** kontrola funkcji Python i brak domyślnego fetchera nie stanowią firewall sieciowego dla całego repo. Wykonywanie live NBP, reguły licencyjne, zachowanie dat PIT, oryginalna tożsamość dostawcy i źródła TOTAL_RETURN nadal wymagają osobnego procesu. Bez zgody nie uruchamiać CLI w trybie online.

**Status:** `A2_DRAFT_SOURCE_ACCESS_REVIEW_REQUIRED`; wymagane nowe CI na końcowym SHA, niezależny code review i separacja provider workflowów. Zero rzeczywistych operacji finansowych i brak aktywacji schedulera.
