# Bezpieczna konfiguracja hasła i GitHub Environment Secret — historyczny czytnik STAGING

**Stan zweryfikowany 19.10.2026 po drugiej autoryzacji użytkownika.** W Neon PostgreSQL na izolowanej gałęzi STAGING rola `isl_legacy_history_reader` ma `LOGIN=true`, jednak `rolpassword IS NOT NULL=false` — brak hasła; nie może autoryzować standardowego połączenia hasłem. Uprawnienia bez zmian: `SELECT` tylko na `investment_lab.price_observations`, bez dostępu do prywatnych pozycji i zapisu. Nowego sekretu GitHub jeszcze nie ma. Próba resetu hasła przez połączony Neon API zakończyła się błędem, a SQL readback potwierdził brak hasła. Neon API `get_postgres_role` nadal wykazywał `authentication_method=no_login`; najważniejszy jest niezależny rzeczywisty odczyt `pg_authid`.

## Zakres i bezpieczeństwo

- **Projekt Neon:** `red-lake-53043722`
- **STAGING branch:** `br-wandering-union-ba6ogf6l` — `mcp-migration-2026-10-17T21-12-05`
- **NIE dotykać PRODUCTION branch:** `br-shy-voice-badzlf0x`
- **Baza i schemat:** `investment_lab`
- **Rola docelowa:** `isl_legacy_history_reader`
- **Direct compute (bez poolera):** `ep-summer-star-ba5trfu5.c-8.eu-central-1.aws.neon.tech:5432`
- **GitHub repo:** `gniewkob/Investment-Strategy-Lab`; **Environment:** `research-staging`
- **Nowy sekret:** `NEON_HISTORICAL_READ_DATABASE_URL`, odrębny od istniejącego `NEON_RESEARCH_DATABASE_URL`.
- Nie kopiować hasła/DSN do ChatGPT, logów, Issues, PR-ów, skryptów, plików, historii poleceń ani publicznych artefaktów.

## Operator-only — co trzeba wykonać w prywatnej sesji

1. **Ustaw hasło do istniejącej roli bez jawnej treści SQL.** W [Neon Console](https://console.neon.tech/) wybierz projekt i **dokładnie staging**. Jeśli `Roles → isl_legacy_history_reader → Reset password` działa, możesz użyć oferowanego formularza. API reset w poprzedniej próbie zgłosiło błąd, więc nie zakładaj, że UI zadziała.

   Jeśli opcja UI nie działa, połącz się prywatnym `psql` z tym staging jako `investment_lab_owner`. Nie przekazuj owner DSN do czatu ani pliku. Wybierz weryfikację pełnego TLS `sslmode=verify-full` i zaufany bundle CA odpowiedni dla swojego systemu. Następnie wewnątrz sesji `psql` uruchom:

   ```text
   \password isl_legacy_history_reader
   ```

   Program zapyta interaktywnie o nowe hasło i powtórzenie (np. z menedżera haseł). Nie wpisuj hasła jako tekstowego `ALTER ROLE ... PASSWORD '...'` w historii SQL/terminala. Zapisz je w menedżerze haseł. Zakończ `psql` poleceniem `\q`. **Nie korzystaj z właścicielskiego hasła jako hasła czytnika.**

2. **Przygotuj jedynie lokalnie DSN** z rolą `isl_legacy_history_reader` i hasłem, poprawnie zakodowanym w URL (procentowe kodowanie znaków specjalnych w password). Neon **Connect** może pokazać gotowy URL dla wskazanej roli; sprawdź uważnie branch, nazwę użytkownika, bazę i brak `-pooler`. Format bez hasła:

   ```text
   postgresql://isl_legacy_history_reader:<URL_ENCODED_PASSWORD>@ep-summer-star-ba5trfu5.c-8.eu-central-1.aws.neon.tech/investment_lab?sslmode=verify-full
   ```

   Nie używaj `sslmode=require`; istniejący kod sprawdza dosłownie `verify-full` oraz hostname, username i database, a GitHub runner ładuje certyfikat CA z systemu. Jeśli kontrolny URL zwraca niedozwolone konto, pooled host albo inną bazę — **przerwij**, nie obchodź walidacji.

3. **Ustaw sekret samodzielnie w GitHub UI:** repo → **Settings → Environments → research-staging → Environment secrets → Add secret**. Nazwa `NEON_HISTORICAL_READ_DATABASE_URL`; wartość to przygotowany DSN. Zapisz. Korzystaj z zabezpieczeń environment (reviewer/rules), jeśli są skonfigurowane. Podłączony obecnie interfejs GitHub nie udostępnia operacji wpisania Environment Secret, dlatego ta część wymaga działania uprawnionego użytkownika. Nie zapisuj DSN jako GitHub Variable ani secret globalny.

4. **Potwierdź tylko status (bez treści sekretu).** Możesz poinformować w rozmowie „hasło i secret ustawione”; nie ujawniaj hasła, linku DSN, poświadczeń ani zrzutów ekranu zawierających URL. Następny etap to odrębny, ręcznie zatwierdzany test historycznego bridge i przegląd agregatowych wyników, **bez automatyzacji harmonogramu i bez transakcji**.

## Gate po konfiguracji (do wykonania po potwierdzeniu sekretu)

- Zweryfikować na **staging**: `rolcanlogin=true`, niepuste hasło (tylko wartość logiczna, nigdy `rolpassword`), brak SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS.
- `SELECT` tylko na `investment_lab.price_observations`, brak odczytu `holding_snapshots`, `valuations`, `paper_events`, brak DML/DDL.
- Istniejąca rola `isl_agent_staging_limited` nadal nie może czytać legacy ani prywatnych pozycji; produkcja pozostaje niezmieniona.
- Po odrębnej decyzji uruchomić ręcznie `.github/workflows/legacy-history-research.yml` z `main`, sprawdzić brak surowych danych/sekretów w raportach, `database_writes=0`, `real_orders=0` i `UNVERIFIED_HISTORICAL_PUBLICATION`.

**Źródła:** [Neon — Manage Roles](https://neon.com/docs/manage/roles), [PostgreSQL — CREATE ROLE/bezpieczne `\password`](https://www.postgresql.org/docs/current/sql-createrole.html), [GitHub — Environment Secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions).
