# Investment Strategy Lab 2.0 — autonomiczny agent badawczy (beta)

Stan: **wdrożenie testowe**, 2026-10-17. Cel: autonomiczne, udokumentowane i powtarzalne badania rynkowe z wirtualnymi decyzjami, a NIE zarządzanie pieniędzmi, poradnictwo inwestycyjne lub realny trading.

## Architektura

1. **GitHub Actions** (docelowy harmonogram 07:25 UTC, workflow `autonomous-research.yml`) uruchamia izolowanego workera Python. Jest to obecnie *przygotowany workflow*, nieaktywny dopóki nie ma repozytorium i ograniczonego połączenia do Neon.
2. Worker używa zapytań PIT na `price_observation_versions` i `source_documents`, odrzuca rekordy pobrane po czasie decyzji, generuje hipotezy naukowe i decyzje wirtualne `HOLD_CASH` lub `PAPER_TARGET_INTENT`. Nigdy nie generuje faktycznych zleceń ani wirtualnych realizacji bez osobnego, zweryfikowanego wykonania po dacie sygnału.
3. Neon trwale przechowuje `agent_cycles`, `agent_paper_decisions`, `agent_hypotheses`, `agent_hypothesis_evaluations`, rejestr wersji danych i bibliografię, tylko po wdrożeniu migracji 007/008 na main.
4. ChatGPT plugin `investment-strategy-lab` odczytuje wyniki, wyjaśnia różnicę między obserwacją i hipotezą, generuje raporty, proponuje eksperymenty. Plugin **nie jest** niezależnym procesem w tle.

## Zasady bezpieczeństwa i jakości

- Brak połączeń z API do tworzenia zleceń, brak kluczy Coinbase i innych brokerów. Tylko edukacyjny paper trading.
- M1, M2, M3 zachowują wirtualny model 100 PLN miesięcznie **jako trzy alternatywy**, nigdy 300 PLN rzeczywistych środków.
- Później udostępnione lub poprawione źródło nie może zmienić poprzedniej decyzji. `available_at` i `retrieved_at` chronią przebiegi, a każdy cykl ma hasz wejścia i unikalny klucz idempotentności.
- Źródłowa średnia miedzi World Bank to **notowanie referencyjne**, nie cena wykonania, ETF ani inwestowalny instrument.
- Z powodu braku PLN total-return i wiarygodnych cen wykonania w aktualnej bazie agent **powinien** wygenerować trzy `HOLD_CASH`. Nie jest to awaria.
- Hipotezy geopolityczne nie otrzymują arbitralnych mnożników ceny. Prognozy ilościowe wymagają osobnego holdoutu i lepszego wyniku niż benchmark.

## Wdrożenie

1. Utworzyć **dedykowane publiczne** repozytorium `gniewkob/Investment-Strategy-Lab`; jest utworzone. Przenieść do niego zawartość tego pakietu.
2. Sprawdzić zmiany `db/migrations/007_data_provenance.sql` i `008_autonomous_research.sql` na gałęzi testowej. W Neon przetestowano łącznie 24 tabele na `<NEON_STAGING_BRANCH>`, 1 syntetyczny cykl, 3 `HOLD_CASH`. `main` pozostaje z 16 tabelami; **nie wdrażać bez odbioru migracji**.
3. Wdrożyć migrację 007 **przed** 008 na `main`, po odrębnym potwierdzeniu zgodnym z zasadami Neon. Nie kopiować syntetycznych wpisów z gałęzi testowej.
4. Utworzyć rolę **ograniczoną**: `SELECT` na źródłach, tabelach PIT; `INSERT/SELECT` na `agent_cycles`, `agent_paper_decisions`, `agent_hypotheses`, `agent_hypothesis_evaluations`. Bez `CREATE`, `UPDATE`, `DELETE`, dostępu do brokerów lub kont użytkownika. Wymaga przejrzenia uprawnień i zweryfikowania tabel; nie używać `investment_lab_owner` w workflow.
5. Dodać do GitHub Secrets `NEON_DATABASE_URL` dla ograniczonej roli (nigdy do kodu/ChatGPT). Workflow jawnie kończy się błędem, jeżeli sekret nie istnieje.
6. Test: `python -m unittest discover -s tests -v`. Smoke: `python -m src.isl_v2.agent_cli --input fixtures/autonomous_synthetic.json --out-dir artifacts`.
7. Zweryfikować pierwsze 14 niezależnych przebiegów w `agent_cycles`, logach GitHub Actions i raportach; powiadomienia ChatGPT nie są włączone automatycznie.

## Braki przed produkcyjną autonomią

- Agent nie pobiera sam jeszcze nowych oficjalnych rekordów do schematu 007. Obecne 3711 historycznych rekordów starej tabeli **nie zostały migrowane automatycznie** do wersjonowanej tabeli, ponieważ brakuje wiarygodnych czasów publikacji dla wszystkich pozycji.
- Hipotezy ilościowe dla rynku Brent wymagają dziennego kalendarza notowań; w wersji beta automatyczne testy kierunkowe dotyczą tylko poprawnie udokumentowanych miesięcznych obserwacji (np. miedzi), a ich liczba jest obecnie niewystarczająca na skuteczną walidację.
- Brak backendu rzeczywistych wirtualnych fillów i kosztów; `PAPER_TARGET_INTENT` jest propozycją alokacji **w symulacji**, nie zapisem transakcji.
- GitHub repo i harmonogram nie są jeszcze uruchomione.

## Kryteria odbioru beta

- Testy jednostkowe i PostgreSQL przechodzą, a `main` pozostaje bez zmian podczas przygotowania.
- Każda decyzja ma `as_of`, hash wejścia, brak wycieku przyszłej rewizji i idempotentny zapis.
- Worker ma dostęp jedynie do uprawnień niezbędnych dla analizy.
- W przypadku błędu źródła/sekretu workflow zgłasza awarię, a nie sukces.
- Wyniki raportu jawnie rozróżniają zapis w Neon, dry-run oraz oczekujące wdrożenie.
