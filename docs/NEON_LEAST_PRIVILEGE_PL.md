# Bramka bezpieczeństwa — Investment Strategy Lab v2 (Neon / GitHub)

**Stan:** 18.10.2026; faza przeglądu, bez wdrożenia produkcyjnych uprawnień.
PR #1: https://github.com/gniewkob/Investment-Strategy-Lab/pull/1
Issue #3: https://github.com/gniewkob/Investment-Strategy-Lab/issues/3

## Zasada dostępu

Rozdzielić trzy niezależne zestawy uprawnień w PostgreSQL:

| Grupa NOLOGIN | Co wolno | Czego nie wolno |
| --- | --- | --- |
| `isl_eia_ingest` | Czytać katalog instrumentów/źródeł, czytać i dopisywać zweryfikowane dokumenty, wersje cen i audyt importu | Modyfikować lub usuwać dane historyczne, czytać prywatne portfele, zapisywać decyzje agenta |
| `isl_market_reader` | Czytać wyłącznie źródłowe dokumenty i wersje cen oraz wykonywać `prices_asof(cutoff)` | Jakikolwiek zapis do danych rynkowych |
| `isl_journal_append` | Odczytać dziennik badawczy i dopisać nowy cykl, fikcyjną intencję oraz ocenę hipotezy | UPDATE/DELETE/TRUNCATE, zapis danych cenowych, realne zlecenia |
| `isl_agent_runtime` | Połączenie dwóch poprzednich grup: `market_reader` + `journal_append` | CREATE/DDL i wszystkie inne operacje |

Dokładny skrypt przeglądowy: `db/security/least_privilege_roles_CI_REVIEW.sql`.
Tworzy jedynie **NOLOGIN** role/grupy, nie tworzy kont dostępowych, haseł ani tokenów.
Testy w `tests/integration/test_least_privilege_postgres.py` używają `SET ROLE` w jednorazowym PostgreSQL 16, bez dostępu do Neon.

## Połączenia GitHub Actions

- `NEON_RESEARCH_DATABASE_URL`: oddzielny sekret środowiska GitHub `research-staging`, dla użytkownika Neon dziedziczącego tylko `isl_agent_runtime`. Nie używać roli właścicielskiej.
- Przyszłe `NEON_EIA_INGEST_DATABASE_URL`: osobna tożsamość Neon z członkostwem tylko w `isl_eia_ingest`. **Nie jest jeszcze używana przez żaden workflow zapisujący dane.**
- Sekretów NIE umieszczać w kodzie, logach, komentarzach GitHub, plikach .env ani artefaktach raportu.
- Workflow agenta pozostaje **wyłącznie ręczny**, uruchamiany tylko z `main`, z `environment: research-staging`. Dodatkowo Python weryfikuje faktyczne uprawnienia przed pobraniem danych.
- Zanim ustawisz environment secret, w GitHub skonfiguruj `Settings → Environments → research-staging`: odpowiednią ochronę środowiska, uprawnione gałęzie i (jeśli plan pozwala) wymagane zatwierdzenia.
- Publiczne workflow `pull_request`, `push` i `official-eia-source-validation.yml` nie mogą otrzymywać żadnych sekretów; mają wykonywać wyłącznie CI i odczyty HTTPS.

## Co potwierdza GitHub CI

1. PostgreSQL 16 uruchomiony w jednorazowym kontenerze GitHub Actions z syntetycznymi danymi.
2. Skrypt ról tworzy cztery grupy bez uprawnień LOGIN, CREATE/CREATEDB, CREATEROLE ani SUPERUSER.
3. Agent może dopisywać wpisy do dziennika i ponawiać cykl bez UPDATE.
4. Agent nie może zapisywać cen; importer nie może zapisywać dziennika; właściciel jest odrzucany przez `assert_research_runtime()`.
5. Testy sprawdzają odmowę operacji SQL, nie tylko same deklaracje GRANT.
6. Odczyty source PIT i korekt działają wyłącznie na danych dopuszczonych przez bramkę czasu.

Nie dowodzi to jeszcze poprawnego nadania uprawnień w Neon ani udanego startu produkcyjnego workera.

## Zatrzymanie przed produkcją (P0)

**Nie wykonywać teraz:**
- DDL i ról na produkcyjnej gałęzi Neon.
- Tworzenia produkcyjnego konta login i przekazywania jego hasła do czatu.
- Konfiguracji rzeczywistych giełd, zleceń, przelewów ani zakupów.
- Automatycznego `schedule` dla research workera.

**Warunki kolejnego etapu:**
- [ ] Oddzielna autoryzacja na wykonanie skryptów uprawnień na **testowej** gałęzi Neon.
- [ ] Przegląd migracji 007 i 008 oraz przygotowanie procedury odtworzenia.
- [ ] Osobna tożsamość testowa Neon; runtime łączy się bez eskalacji praw.
- [ ] Zapis i odczyt jednego syntetycznego cyklu w testowej Neon pod ograniczoną tożsamością.
- [ ] Potwierdzone audytowanie błędów i mechanizm powiadamiania.
- [ ] Oddzielna, wyraźna zgoda przed jakąkolwiek zmianą na `main`.

## Kryterium sukcesu

Nie wystarczy, że CI świeci się na zielono. Należy udowodnić, że nawet przy błędnym uruchomieniu agent nie może zmienić ceny historycznej, nadpisać dziennika ani korzystać z konta PostgreSQL właściciela.
