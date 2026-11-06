# Working Engine v0.2 — pełny fingerprint danych wejściowych

**Status: PASS na izolowanym LAB; nieprzełączony scheduler.**

## Naprawiony błąd

Wersja v0.1 budowała reproducibility hash na podstawie najnowszej
obserwacji każdego instrumentu, liczby kwalifikujących się rekordów,
reguł modelu i zdarzeń papierowych. Zmiana ceny **starszej niż najnowsza**
nie zmieniała liczby wierszy ani listy najnowszych wartości. Ponowne
wykonanie mogło zwracać IDEMPOTENT_REPLAY zamiast wykrywać zmianę
danych źródłowych. Jest to defekt odtwarzalności badań, nie dowód
wystąpienia manipulacji w prywatnej bazie.

W v0.2 obliczamy SHA-256 uporządkowanego, pełnego zbioru kwalifikujących
się obserwacji dostępnych w momencie cutoff. Fingerprint obejmuje:
instrument_code, source_code, observed_for, ingested_at, interval_code,
return_basis, close_price i quote_currency. Do fingerprintu nie trafiają
rekordy z ingested_at po cutoff. Hash jest zapisywany w evidence, metrykach
research_runs oraz w odrębnym fingerprint całego wejścia modelu.

**Rozdzielenie wersji:** identyfikatory v0.2 korzystają z osobnej
przestrzeni `isl-engine-v02-*`. Poprzednie v0.1 pozostają w bazie i
nie są nadpisywane. Wersja v0.2 nie tworzy wirtualnych transakcji,
nie uruchamia zleceń i nie zmienia wycen aktywów.

## Nowe komponenty

- `db/working_engine_v02_research_cycle.sql` — cykl badawczy
  z pełnym historycznym fingerprint.
- `db/working_engine_v02_health_READONLY.sql` — niezależny,
  odczytowy przelicznik SHA-256 tego samego zbioru według cutoff
  i porównanie z zapisem research_runs.
- `tests/integration/test_working_engine_v01.py` — dodatkowe
  testy wersji v0.2 (w tej samej jednorazowej bazie PostgreSQL).
- `.github/workflows/working-engine-v01-ci.yml` — obejmuje oba
  nowe pliki oraz testy regresyjne.

## Potwierdzony test na rzeczywistym Neon — wyłącznie test branch

Projekt `red-lake-53043722`, gałąź testowa
`br-purple-night-ba3e6uwv`, baza `investment_lab`.

- Cutoff: 2026-11-05 19:00 UTC.
- 3 777 kwalifikujących się obserwacji.
- Pierwszy cykl v0.2: 3 research_runs + 3 signal_events +
  3 audit_events; 0 paper fills, 0 operacji finansowych.
- Powtórzenie identycznego cyklu: IDEMPOTENT_REPLAY 3/3;
  0 nowych research, signal i audit.
- Odczyt niezależnym health v0.2: ENGINE_OK 3/3,
  hash odtworzonych danych = hash zapisany w research_runs 3/3,
  sygnały i audyt po 1 dla każdego modelu, 0 paper fills.
- Źródłowy hash wspólny dla M1/M2/M3:
  `c0005631a8cccb1659e11b4a0ea9cc689baa89fef58e13a47d2011f690c17cdb`.
- Decyzje pozostają INSUFFICIENT_DATA/HOLD_CASH, gdyż nadal
  brakuje szeregów PLN total return niezbędnych do obliczenia
  sprawdzalnych wyników strategii.

## Testy automatyczne

[GitHub Actions CI #42191961613](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42191961613)
**SUCCESS: 26/26 testów** — 5 przygotowanie NBP, 5 walidacja
SQL, 4 harmonogramowe źródło, 12 integracyjnych PostgreSQL.

Regresja reprodukuje lukę: po zmianie starej ceny v0.1 daje
IDEMPOTENT_REPLAY, ale v0.2 daje REPLAY_INPUT_COLLISION.
Niezależny health v0.2 sygnalizuje wtedy SOURCE_INPUT_CHANGED,
pomimo że historyczne research/signal/audit nie zostały zmienione.
Zmiana wiersza uzyskanego dopiero po cutoff nie powoduje
nieuzasadnionego konfliktu.

## Co wciąż jest otwarte

- Aktywny harmonogram ChatGPT nadal wykorzystuje **przypięte v0.1**
  (commit `e9ca5e9ed37a55775df718cc8bbddc4a00676fb1`).
  Nie przełączać automatycznie kodu na v0.2 podczas weryfikacji
  dwóch naturalnych cykli; nie mylić testu v0.2 z naturalnym runem.
- Pierwszego nowego uruchomienia harmonogramowego NBP
  `isl-nbp-public-daily.yml` nie potwierdzono na dzień 6.11.
  Repo zawiera harmonogram, ale jego skuteczne wykonanie należy
  sprawdzić przez GitHub Actions i niezależny SQL w Neon.
- Kontrola v0.2 wykrywa zmianę zawartości w tabeli źródeł,
  **nie poświadcza** historycznej godziny publikacji przez NBP,
  autentycznego vintage ani kompletności total return.
- Produkcja i UI pozostają poza tą iteracją. Główne Neon main
  to prywatne laboratorium, nie wdrożenie produkcyjne.
