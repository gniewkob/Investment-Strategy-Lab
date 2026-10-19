# PIT readiness: syntetyczne fixture a rzeczywiste źródła (PL)

**Status:** kontrola inżynierska dla edukacyjnego Investment Strategy Lab. Żadnego handlu, rekomendacji inwestycyjnych, automatycznej alokacji, importu cen lub harmonogramu.

## Dlaczego

Neon STAGING zawiera 3 dokumenty i 3 wersjonowane rekordy `nbp_gold`, wszystkie jawnie oznaczone jako syntetyczne / fixture-only. `investment_lab.prices_asof(now())` prawidłowo dopuszcza jeden rekord, ale **jest to fixture, nie rzeczywisty punkt danych rynkowych**. Jedna inna syntetyczna obserwacja ma celowo przyszłe `recorded_at` i `retrieved_at`; funkcja SQL prawidłowo ją odrzuca.

Poprzedni raport pokazywał `pit_eligible_rows=1` bez wskazania syntetycznego pochodzenia. Poprawka rozróżnia:

- `pit_eligible_rows`: wszystkie rekordy technicznie widoczne w `prices_asof(cutoff)`.
- `pit_fixture_rows`: rekordy powiązane z dokumentami `source_documents.metadata.synthetic=true` lub `fixture_only=true`.
- `pit_nonfixture_rows_unreviewed`: pozostałe technicznie widoczne rekordy, które **nie zostały automatycznie zweryfikowane** jako poprawne historyczne publikacje.
- `publication_vintage_certified=false`: obecna kontrola nie certyfikuje publikacji pierwotnych, nawet gdy pojawiają się źródła nieoznaczone jako fixture.

Liczby fixture i nonfixture muszą sumować się do wszystkich PIT-visible. Jakakolwiek rozbieżność powoduje błąd, nie milczące przejście. Pokrycie miesięczne liczone jest wyłącznie z danych nieoznaczonych jako fixture. Same rekordy nieoznaczone jako fixture nadal **wymagają niezależnego przeglądu źródłowego** i dlatego wynik z kompletnym pokryciem może co najwyżej zwracać `COVERAGE_GATE_PASSED_REVIEW_REQUIRED`, nigdy zatwierdzenie działania agenta.

## Zweryfikowany SELECT z restricted reader na Neon STAGING (19.10.2026)

- `isl_agent_staging_limited` wykonał SELECT `prices_asof(now())` + `source_documents`: **1** fixture, **0** nonfixture.
- Zwrócone pokrycie nonfixture jest puste.
- Danych nie modyfikowano. Nie sprawdzano produkcji.

## Zabezpieczenia

Kontrola zachowuje dokładnie obecny `prices_asof()` i wszystkie wymagania SSL/tożsamości STAGING. `read_snapshot` nadal używa transakcji read-only i tylko agregatów; nie eksportuje notowań, portfeli ani metadanych niejawnych. Odróżnienie syntetyczności służy ocenie *gotowości danych*, nie generowaniu sygnałów rynkowych. Weryfikacja właściwych danych PIT wymaga osobnego procesu pozyskania oryginalnej publikacji, trwałego hasha dokumentu, `published_at`, `retrieved_at` i `recorded_at` — bez antydatowania.

Zakres zadania: [Issue #23](https://github.com/gniewkob/Investment-Strategy-Lab/issues/23). Wyciągi z historycznej tabeli `price_observations` nadal mają `UNVERIFIED_HISTORICAL_PUBLICATION`. Nie są zastępczym źródłem do `prices_asof()`. M1/M2/M3 pozostają `HOLD_NO_CHANGE`.
