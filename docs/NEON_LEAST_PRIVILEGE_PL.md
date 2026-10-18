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

Testy w CI potwierdzają deklarowane uprawnienia i działanie rzeczywistych operacji SQL. Niezależny test uprawnień w Neon został następnie wykonany na gałęzi testowej, lecz połączenie z prawdziwym hasłem i uruchomienie produkcyjnego workera nadal nie są potwierdzone.

## Zatrzymanie przed produkcją (P0)

**Nie wykonywać teraz:**
- DDL i ról na produkcyjnej gałęzi Neon.
- Tworzenia produkcyjnego konta login i przekazywania jego hasła do czatu.
- Konfiguracji rzeczywistych giełd, zleceń, przelewów ani zakupów.
- Automatycznego `schedule` dla research workera.

**Warunki kolejnego etapu:**
- [x] Oddzielna autoryzacja i wykonanie skryptów uprawnień na **testowej** gałęzi Neon.
- [ ] Przegląd migracji 007 i 008 oraz przygotowanie procedury odtworzenia.
- [x] Utworzona ograniczona tożsamość SQL testowa, bez neon_superuser i z zablokowanym uwierzytelnieniem hasłem.
- [ ] Potwierdzone prawdziwe połączenie hasłem i start runtime bez eskalacji praw; jeszcze niewykonane.
- [x] Zapis i odczyt syntetycznego cyklu pod `SET ROLE` ograniczonej tożsamości na testowej Neon (nie jest to test połączenia hasłem).
- [ ] Potwierdzone audytowanie błędów i mechanizm powiadamiania.
- [ ] Oddzielna, wyraźna zgoda przed jakąkolwiek zmianą na `main`.

## Kryterium sukcesu

Nie wystarczy, że CI świeci się na zielono. Należy udowodnić, że nawet przy błędnym uruchomieniu agent nie może zmienić ceny historycznej, nadpisać dziennika ani korzystać z konta PostgreSQL właściciela.


## Próba Neon — 18 października 2026

**Uwaga na różnicę pomiędzy Neon API i SQL:** konta tworzone przez Neon Console/API/CLI mogą automatycznie otrzymać `neon_superuser`. Konto stworzone tym sposobem okazało się za szeroko uprzywilejowane. Po zatwierdzeniu użytkownika usunięto je **wyłącznie na gałęzi testowej**. Jest to zgodne z oficjalną [dokumentacją Neon — Manage roles](https://neon.com/docs/manage/roles).

Bezpieczny zamiennik `isl_agent_staging_limited` został utworzony poleceniem SQL jako `NOLOGIN`, z jawnie wyłączonymi `CREATEROLE`, `CREATEDB`, `SUPERUSER`, `REPLICATION`, `BYPASSRLS` i z dziedziczeniem wyłącznie `isl_agent_runtime`. Po testach zmieniono go na `LOGIN PASSWORD NULL CONNECTION LIMIT 2` — typ LOGIN istnieje, ale **nie można jeszcze uwierzytelnić się hasłem**, dopóki upoważniona osoba nie nada silnego sekretu bezpośrednio w kontrolowanym kanale.

Dla tej tożsamości sprawdzono:
- `neon_superuser = false`, `rolcreaterole = false`, `rolcreatedb = false`, `rolsuper = false`.
- `CREATE` dla bazy/schematu: odmowa; `INSERT` do `source_documents`: odmowa; `INSERT` do `agent_cycles`: dozwolony.
- Wykonanie `SET ROLE isl_agent_staging_limited` z tymczasowym prawem przełączenia wyłącznie w transakcji na gałęzi testowej; przywrócenie `SET FALSE` na końcu.
- Uruchomienie dokładnie tej samej kontroli uprawnień, co w `assert_research_runtime()`: `true`.
- Jeden syntetyczny cykl i trzy decyzje `HOLD_CASH`; każda próba odczytu starych zdarzeń portfelowych, aktualizacji dziennika, zapisu importu, zmian cen i DDL: **odrzucona** (pięć testów odmowy).

**Brak rzeczywistego logowania**: `SET ROLE` nie potwierdza działania połączenia SSL z kontem i hasłem. Na tym etapie *nie* tworzono tajnego hasła, GitHub environment secret, automatycznego harmonogramu, wirtualnych zakupów ani żadnych zleceń.

Kolejny krok: nadać silne hasło przez bezpieczny kanał zarządzania SQL/psql (np. interaktywne `\password` w lokalnym `psql`; nie w publicznym pliku SQL), skonfigurować chroniony sekret GitHub tylko dla środowiska testowego, potwierdzić endpoint gałęzi i SSL, następnie wykonać odczyt i jeden testowy cykl. **Nie należy wklejać hasła ani URL zawierającego hasło do czatu, Issue ani Pull Request.**

Produkcja `main` pozostaje bez zmian; osobne zatwierdzenie jest wymagane przed wdrożeniem na produkcję.
