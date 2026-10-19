# Bezpieczna konfiguracja hasła i GitHub Environment Secret — historyczny czytnik STAGING

**Historyczny snapshot przed rozwiązaniem:** W Neon PostgreSQL na izolowanej gałęzi STAGING rola `isl_legacy_history_reader` ma `LOGIN=true`, jednak `rolpassword IS NOT NULL=false` — brak hasła; nie może autoryzować standardowego połączenia hasłem. Uprawnienia bez zmian: `SELECT` tylko na `investment_lab.price_observations`, bez dostępu do prywatnych pozycji i zapisu. Nowego sekretu GitHub jeszcze nie ma. Próba resetu hasła przez połączony Neon API zakończyła się błędem, a SQL readback potwierdził brak hasła. Neon API `get_postgres_role` nadal wykazywał `authentication_method=no_login`; najważniejszy jest niezależny rzeczywisty odczyt `pg_authid`.

## Aktualny stan — 19.10.2026, po poprawnym bootstrapie

Wcześniejsza blokada `PASSWORD NULL` została **usunięta**. `rolcanlogin=true`, `rolpassword IS NOT NULL=true` (potwierdzone bezpośrednio w PostgreSQL). SELECT wyłącznie na `investment_lab.price_observations`, zero praw zapisu/CREATE, brak dostępu do `holding_snapshots`, produkcja bez zmian. **Końcowego hasła z Neon Console i sekretu GitHub jeszcze nie skonfigurowano.** Dalsze kroki to reset hasła w prywatnym UI, konfiguracja sekretu i odrębnie ręczny test.

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

1. **WAŻNE — pierwsze has1. **ZRESETUJ hasło istniejącej roli w Neon Console — inicjalizacja zakończona.** Dnia 19.10.2026 przy wykorzystaniu wcześniejszej metody udokumentowanej w [Issue #3](https://github.com/gniewkob/Investment-Strategy-Lab/issues/3), zrealizowano na staging jednorazowy blok `DO`, który utworzył trzy losowe `gen_random_uuid()` po stronie bazy i ustawił nieujawnione hasło początkowe przez `ALTER ROLE`. Kontrola SQL potwierdziła `rolcanlogin=true` i `rolpassword IS NOT NULL=true`. Uprawnienia historycznego czytnika **nie uległy zmianie**. **Nie wykonuj bootstrap ponownie.**

   Otwórz [Neon Console](https://console.neon.tech/), wybierz projekt `red-lake-53043722`, gałąź `br-wandering-union-ba6ogf6l` i rolę `isl_legacy_history_reader`. Użyj **Reset password** istniejącej roli, tak jak poprzednio dla `isl_agent_staging_limited`. Zapisz nowo wygenerowane końcowe hasło bezpośrednio w menedżerze haseł. Nie ujawniaj hasła ani DSN w rozmowie, narzędziach czy repo. Nie używaj przycisku **Add role**. Reset z poziomu Neon Console nie został jeszcze w tej sesji potwierdzony; jeśli UI nadal zwraca błąd, zatrzymaj się i zgłoś tekst błędu (bez sekretów).

   Technicznie początkowe hasło jest nieznane użytkownikowi i agentowi — to zamierzone. Jego jedyną rolą jest umożliwienie zainicjowania kontrolowanego resetu. Dynamiczny `ALTER ROLE` został wykonany w serwerowym bloku, bez przesyłania hasła do narzędzi ani publicznego kodu. Nie jest to gwarancja braku wpisów w wewnętrznych logach serwera; końcowa rotacja jest wymagana przed użyciem poświadczenia.

okalnie DSN** z rolą `isl_legacy_history_reader` i hasłem, poprawnie zakodowanym w URL (procentowe kodowanie znaków specjalnych w password). Neon **Connect** może pokazać gotowy URL dla wskazanej roli; sprawdź uważnie branch, nazwę użytkownika, bazę i brak `-pooler`. Format bez hasła:

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
