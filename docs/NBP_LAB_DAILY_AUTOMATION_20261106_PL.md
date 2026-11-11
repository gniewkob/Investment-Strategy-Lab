# Working Engine v0.1 — automatyczny obieg danych NBP (06.11.2026)

## Model działania

W projekcie nie ma jeszcze produkcji. Główne Neon \`main\` jest
trwałym środowiskiem prywatnego laboratorium.

\`\`\`
GitHub Actions na main — codziennie 04:17 UTC
  -> checkout testowanego commitu kodu NBP
  -> oficjalne NBP API (HTTPS, USD/PLN, EUR/PLN, złoto)
  -> walidacja + 14-dniowy research receipt + wygenerowany SQL
  -> wyłącznie log GitHub; brak sekretów i uprawnień Neon
                   |
 istniejąca automatyzacja „Surowce i geopolityka” (~08:21 PL)
  -> GET /actions/runs?event=schedule&per_page=30
  -> ostatni udany run ścieżki isl-nbp-public-daily.yml z main
  -> sprawdza wymagany checkout, job i dwa markery logu
  -> waliduje SOURCE, SHA, tożsamość serii, uprawniony zakres SQL
  -> wykonuje dokładnie wygenerowany SQL przez Neon MCP (LAB main)
  -> sprawdza faktyczne rekordy i audyt po zapisie
  -> dotychczasowy silnik M1/M2/M3 oraz health READONLY
\`\`\`

## Zaplanowane uruchomienia — co zostało wykonane

- Workflow na **GitHub main**:
  \`.github/workflows/isl-nbp-public-daily.yml\`
  commit \`d93e2ac3c5559f0d06f99f8026655905e4a8537d\`.
- Codzienna sesja NBP źródłowa, cron \`17 4 * * *\` (UTC), z
  \`workflow_dispatch\` do diagnostyki; pierwsza sesja z harmonogramu
  po wdrożeniu spodziewana **07.11.2026**, ale wykonania nie
  potwierdzono i GitHub może opóźnić harmonogram.
- Workflow robi checkout niezmiennego commitu
  \`9bebd1aabb66019d3de0556c0ff1733d155bdbc1\`
  (kod z PR #95). Nie ma klienta Neon, sekretów ani zapisów finansowych.
- Okno danych: **14 dni wstecz**, zamiast 31. Gdy wystąpi
  nieobecność dłuższa niż 14 dni, nie nadpisujemy i nie uzupełniamy
  braków syntetycznie — uruchamiamy odrębny kontrolowany backfill.
- Wpisano nowy krok importu NBP do aktywnej automatyzacji
  „Surowce i geopolityka” ID
  \`6ad3d88620708191a2feb6b7a44bf253\`. Narzędzie Automations
  potwierdziło \`success=true\`, bez zmiany harmonogramu, nazwy i
  dotychczasowych zadań. Zajęto 0 nowych slotów automatyzacji.
- Pobieranie i walidacja **jeszcze nie wykazały naturalnego
  harmonogramowego importu przez nowy GitHub workflow**.
  Pierwszy pełny cykl tej automatyzacji wymaga dowodu po 07.11.

## Testy faktycznego pipeline'u

- [CI GitHub #42186722508](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42186722508):
  oficjalne NBP API, PASS; odczyt po zmianie okna:
  31 obserwacji (10 USD/PLN, 10 EUR/PLN, 11 złota)
  w przedziale 23.10–06.11.2026. Generator wygenerował SQL z SHA-256
  \`30d0ac778366c7ed8e4f3df61d88bc4ae2ef21bdd27f739271b9e02b7e1fcbfe\`.
  Live probe i testy offline PASS, żadnego zapisu do Neon z CI.
- [CI #42186722499](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42186722499):
  **20/20 testów PASS** (5 adapter, 5 importer,
  4 harmonogramowe źródło, 6 PostgreSQL e2e).
- Dodatkowy **ręczny E2E smoke** na danych NBP z 06.11:
  odczyt roboczy 31 dni, 70 kandydatów, 69 już w Neon, 1 nowy
  rekord GOLD_NBP_PLN_G z 06.11, 0 konfliktów. SHA-256
  kompletnego wygenerowanego SQL niezależnie policzony w Neon
  i zgodny z nagłówkiem CI.
- Ten sam SQL na osobnej gałęzi testowej, następnie Neon main:
  **1 nowa obserwacja i 1 audyt**, bez ingerencji
  w paper_events i research_runs. Ponowne wykonanie na Neon main:
  0 nowych obserwacji i 0 audytu; brak konfliktów.
- Odczyt po smoke: złoto 06.11.2026, USD/PLN i EUR/PLN
  05.11.2026; 3 zdarzenia wpłat wirtualnych, 0 paper fills,
  3 wcześniej zapisane research_runs.

## Ograniczenia

- Repo PR #95 wciąż jest Draft; harmonogram źródła działa
  z pliku workflow na default branch \`main\`, ale kod źródła
  celowo przypięto do sprawdzonego commitu z PR. W przyszłości
  można przepiąć na stabilną rewizję po testach.
- Data otrzymania w Neon nigdy nie jest traktowana jako wcześniejsza
  od pobrania; historyczne godziny publikacji NBP nie są potwierdzone.
- NBP złoto = cena referencyjna, NIE indeks total return; NBP FX =
  kursy średnie, NIE kurs transakcyjny. Braki TR akcji i obligacji
  nadal blokują wiarygodny backtest, ale nie pracę silnika.
- Nie ma jakichkolwiek wywołań Coinbase do tradingu, zapisów zleceń,
  przelewów, wpłat, pozycji papierowych, konwersji lub dźwigni.
- Plan ChatGPT dopuszcza 5 aktywnych automatyzacji; wykorzystano
  istniejącą, bez zastępowania raportów.

## Następne kryteria odbioru

1. Potwierdzić udany run harmonogramu GitHub na 07.11 oraz SQL
   pochodzący z **tego runu**, nie z ręcznych PR testów.
2. Potwierdzić Neon SQL audit readback, idempotentny import
   (także brak nowych obserwacji jest poprawnym wynikiem).
3. Potwierdzić minimum dwa osobne nowe cutoff M1/M2/M3 z dwóch
   różnych dni, z SHA-256 i audytem, a następnie monitoring trendu
   świeżości i warunki alarmów.

Wynik tej iteracji: kod, źródło, harmonogram i pojedynczy E2E smoke
**PASS**; naturalny autonomiczny import i wielodniowy odbiór pozostają
**PENDING**. Najpierw funkcjonalność i rzeczywiste dowody, nie UX ani
produkcyjny release.
