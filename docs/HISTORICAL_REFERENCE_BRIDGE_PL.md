# Most historyczny — badania retrospektywne (STAGING, READ ONLY)

## Cel

Oddzielić retrospektywne badanie dawnych cen od działającego, ograniczonego agenta `isl_agent_staging_limited`. **Nie zwiększać uprawnień tego agenta.** Nowy most służy jedynie do testów statystycznych, wykrywania nietypowych zmian i generowania pytań badawczych — bez transakcji.

### Stan dostępu (19 października 2026)

- Gałąź Neon staging: `br-wandering-union-ba6ogf6l`; produkcyjna gałąź pozostaje nietknięta.
- Dla `isl_agent_staging_limited`: potwierdzony **brak SELECT** na `investment_lab.price_observations` i brak odczytu `holding_snapshots`. Tak powinno pozostać.
- **Nowa rola `isl_legacy_history_reader` jeszcze nie została skonfigurowana.** Należy utworzyć ją po osobnej autoryzacji dostępu, wyłącznie do odczytu danych referencyjnych w staging. Nie używać hasła roli owner ani danych produkcyjnych.
- GitHub Environment `research-staging`: przyszły niezależny sekret `NEON_HISTORICAL_READ_DATABASE_URL`, **nie** `NEON_RESEARCH_DATABASE_URL`. Nie przesyłać adresu URL z hasłem do rozmowy, kodu, Issues ani logów.

## Minimalny zakres docelowej roli

- **Dozwolone:** CONNECT do `investment_lab`, USAGE schematu `investment_lab`, SELECT wyłącznie na `investment_lab.price_observations`.
- **Zabronione:** SUPERUSER, CREATEROLE, CREATEDB, BYPASSRLS, CREATE, INSERT, UPDATE, DELETE, TRUNCATE, dostęp do `holding_snapshots`, `valuations`, `paper_events`, zapis do `agent_cycles`.
- Wymagane TLS `verify-full`, znany pojedynczy adres compute staging, uwierzytelnianie odrębnym loginem, transakcja `READ ONLY` oraz ograniczenie 15 000 wierszy.
- Proces badań nie uzyska dostępu do prywatnych tabel nawet przy poprawnym haśle: jawnie sprawdza ACL i przerywa, jeżeli rola ma szersze prawa.

## Działanie

`scripts/legacy_history_bridge.py` czyta tylko kody instrumentów, źródła, daty, typy cen i ceny zamknięcia z wcześniej zaimportowanych danych. Weryfikuje dopuszczalne mapowania źródeł, znaczniki czasu i duplikaty, a następnie uruchamia istniejący `scripts/opportunity_research_pipeline.py`.

Wyniki: `research_report.md`, `manifest.json` oraz zbiorcze JSON radaru, walidacji niezależnych okien, dziennika dowodów i kontekstu. **Nie publikuje surowych historycznych cen** jako artefaktu GitHub. Dla każdej analizy rejestruje skrót SHA-256 wejścia oraz oddzielny skrót obejmujący identyfikatory źródeł.

Wszystkie dane historyczne mają etykietę `UNVERIFIED_HISTORICAL_PUBLICATION`. Pobrane w październiku 2026 serie nie zyskują wstecznie wiarygodnej daty publikacji. Backtest pozostaje badaniem retrospektywnym, nie point-in-time-certyfikowaną oceną przewidywania.

## Uruchomienie

Po zatwierdzeniu osobnej roli i bezpiecznym skonfigurowaniu sekretu w GitHub:

1. Uruchomić manualnie workflow `Historical reference research bridge — manual, restricted reader required` z `main`.
2. Sprawdzić `LEGACY_HISTORY_RESEARCH_OK`, zliczenia i skróty dowodów, a także `real_orders=0` oraz `database_writes=0`.
3. Zweryfikować raport i ograniczenia jakości w artefakcie, nie wyciągać wniosków o okazjach inwestycyjnych z pojedynczego historycznego anomalitycznego zdarzenia.

Nie ma harmonogramu, zapisu do Neon, integracji brokerskich ani aktualizacji wirtualnych udziałów portfela. Nie zmieniać uprawnień SQL ani sekretów bez osobnego zatwierdzenia.

## Testy CI

`python -m unittest discover -s tests -v` uruchamia wyłącznie testy offline z fikcyjnymi cenami i hasłami; nie kontaktuje się z Neon. Walidowane są: prawidłowa rola, brak dostępu do portfeli, rygorystyczne TLS, integralność źródeł i chronologii, limity danych, odtwarzalny raport i brak wycieku hasła.


## Oddzielna bramka aktywacji roli — tylko po zatwierdzeniu

W repozytorium znajduje się **wyłącznie propozycja do przeglądu**: `db/security/legacy_history_reader_STAGING_REVIEW.sql`. Jej test w GitHub Actions odbywa się na **jednorazowym PostgreSQL 16** z całkowicie fikcyjnym hasłem. Plik ten nie jest wykonywany w Neon ani przez publiczne CI; po scaleniu nie tworzy sam konta w staging.

Przed jakąkolwiek aktywacją wymagane jest osobne potwierdzenie użytkownika, że chce utworzyć konto odczytowe na konkretnej gałęzi **staging**. Po autoryzacji uprawniony administrator stosuje zweryfikowany SQL na staging, nie produkcji. Skrypt tworzy konto `NOLOGIN` i daje jedynie `SELECT` na `investment_lab.price_observations` oraz wymagany dostęp do schematu i bazy. Test odmowy obejmuje także `holding_snapshots`, `valuations`, `paper_events`, `agent_cycles`, `INSERT` i DDL.

Następnie administrator **interaktywnie** przez `psql` ustawia silne hasło poleceniem `\\password isl_legacy_history_reader` (wyświetli prywatne monity), a osobno zmienia `NOLOGIN` na `LOGIN`. Nie umieszczać hasła w pliku SQL, CLI, terminalowym history ani czacie. Sekret `NEON_HISTORICAL_READ_DATABASE_URL` trafia tylko do GitHub Environment `research-staging`, nie do publicznych PR. Po aktywacji trzeba jeszcze raz sprawdzić rzeczywisty stan roli i historię za pomocą ręcznie uruchomionego, ograniczonego workflow.

Istotne: tabela obejmuje historyczne **referencyjne** ceny. Raport jest retrospektywną analizą, a nie certyfikowanym PIT backtestem; nie wolno na tej podstawie sugerować faktycznych transakcji lub włączać automatycznej alokacji.
