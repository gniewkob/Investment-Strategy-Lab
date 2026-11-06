# Investment Strategy Lab v0.4 — WorldPulse.ai NAV: rzeczywisty audyt dostępności

**Data 2026-11-06. Status: BLOCKED / NOT_RUN.** Skrypt i test sieciowy działają, ale ani JSON, ani CSV nie dostarczyły oryginalnych danych NAV. Nie utworzono nowego szeregu `RESEARCH_PROXY` ani `GLOBAL_EQUITY_TR_PLN`.

## Źródło i rozróżnienie dostawców

- Badany serwis: **WorldPulse.ai**, serwis danych finansowo-ekonomicznych. Strona dokładnej klasy jednostek: https://worldpulse.ai/funds/IE00BK5BQT80
- Strona zawiera prawidłowy ISIN `IE00BK5BQT80`, walutę USD i etykietę `Net Asset Value — VANGUARD`. Ostatnia widoczna wycena to **2026-07-29**, 183.82 USD; jest to treść strony, NIE wynik bieżącego zweryfikowanego API.
- Publicznie podane endpointy kandydackie:
  - `https://api.worldpulse.ai/api/v1/timeseries/canonical/ie00bk5bqt80-nav`
  - `https://api.worldpulse.ai/api/v1/timeseries/canonical/ie00bk5bqt80-nav/csv`
- **Nie mylić z** `world-pulse.io`: jest to inny dostawca (dane o wydarzeniach), a jego zasady użycia, licencje i API nie dotyczą `worldpulse.ai`. Samo podobieństwo marki nie daje prawa do pobierania lub publicznej archiwizacji finansowych NAV.

## Rezultat rzeczywistego uruchomienia GitHub Actions

- [Pierwszy poprawny przebieg #42291637713](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42291637713): SUCCESS audytu; 7/7 testów offline; oba endpointy zgłosiły `URLError` i `TRANSPORT_ERROR`; nie pobrano danych ani nie wyliczono miesięcy.
- [Przebieg #42292056939](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42292056939): SUCCESS audytu; 9/9 testów offline; oba publiczne endpointy ponownie `URLError`, `BLOCKED`, z zerem rekordów zweryfikowanych.
- Status workflow SUCCESS **oznacza wyłącznie poprawne wykonanie audytu**, nie import. Zweryfikowany zakres 36–60 miesięcy: brak; `sha256` rzeczywistej odpowiedzi: brak; `HTTP 200` rzeczywistego źródła: NIEPOTWIERDZONE.
- Dostęp przez bezpośredni podgląd publicznego narzędzia web również nie udostępnił odpowiedzi JSON/CSV. Nie jest to dowód, że API nigdy nie działa; wystarcza do zablokowania wdrożenia przy aktualnym odbiorze.

## Zabezpieczenia implementacyjne

- `scripts/worldpulse_nav_availability_v04.py` to **audyt dostępności**, nie produkcyjny adapter cen.
- Pobiera tylko jawnie opublikowane URL; HTTPS i lista host/path są ściśle ograniczone.
- Rejestruje kody HTTP, typ treści, SHA-256 i długość pobranych bajtów, zgodność schematu, liczbę dat, ciągłość miesięcy i zakres — **nigdy nie publikuje surowych wartości cen NAV**.
- Wymaga **36 kolejnych miesięcy** dla wstępnego `DATA_COVERAGE_CANDIDATE_RIGHTS_UNVERIFIED`; nie akceptuje rozproszonych 36 miesięcy jako jednej spójnej serii.
- Odrzuca błędne źródła, niezidentyfikowane schematy, daty niespełniające ISO, duplikaty, niepoprawne wartości i fałszywą deklarację ISIN.
- Nawet HTTP 200 i 60 kolejnych miesięcy nie uprawniają do `ACCEPTED`: osobno trzeba uzyskać źródłową zgodność z oficjalnym Vanguard i potwierdzić prawo automatycznego odczytu, przetwarzania, przechowywania oraz ewentualnej redystrybucji.
- `.github/workflows/worldpulse-nav-audit-v04.yml` uruchamia test przy zmianach PR, ponieważ nowy `workflow_dispatch` nie jest dostępny przed pojawieniem się definicji na default branch.
- Główny `working-engine-v01-ci.yml` zawiera niezależne testy bez połączenia sieciowego.

## Kryteria przyszłego odbioru

1. Skuteczne rzeczywiste pobranie co najmniej 36, docelowo 60 kolejnych miesięcy do 2026-10, w zakresie dokładnego ISIN i waluty USD.
2. Data, wartość i podstawa `NAV (USD) Accumulating` z jednoznacznym `observed_for`, niezależny cross-check kilku dat z oficjalną tabelą Vanguard.
3. Udokumentowana, obowiązująca dla `worldpulse.ai` i konkretnej serii polityka automatycznego dostępu i przechowywania; oddzielna ocena praw Vanguard, gdy agregator przekazuje dane dostawcy.
4. Kontrola oryginalnych bajtów i SHA-256 w dozwolonym kontekście; brak zapisu surowych danych do publicznego repo bez prawa.
5. Dopiero wtedy adapter NAV/USD→referencja PLN z historycznym NBP, jako **niewykonalna referencja**, bez automatycznej kwalifikacji total return lub ceny zlecenia.

## Alternatywy — odrębne instrumenty, nie zamienniki NAV

Fama–French Developed (https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library/f-f_developed.html) to publiczna akademicka konstrukcja czynników rynków **rozwiniętych**, nie FTSE All-World ani NAV ETF. Według obecnie udokumentowanego zakresu ma miesięczne obserwacje do czerwca 2026, a uprawnienia redystrybucji źródłowych danych wymagają osobnego wyjaśnienia.

Capital Census CC-GMP TR (https://thecapitalcensus.github.io/) jest odrębnym **globalnym indeksem wieloaktywowym**, a nie samym światowym rynkiem akcji. Autor publikuje dane pod CC BY-NC 4.0 dla użytku niekomercyjnego z uznaniem autorstwa, ale historia sprzed sierpnia 2026 ma charakter backtestu. Nie używać jej jako `GLOBAL_EQUITY_TR_PLN`. Odrębne badawcze porównanie wymaga własnego kontraktu metodologicznego.

**Neon LAB main, v0.3 scheduler, paper-events, portfele i realne operacje finansowe — bez zmian.** Projekt nie ma produkcji. Realny M1–M3 backtest pozostaje `NOT_RUN`.
