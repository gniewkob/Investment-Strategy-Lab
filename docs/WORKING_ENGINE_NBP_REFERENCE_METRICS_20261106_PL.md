# NBP reference intelligence — pierwszy rzeczywisty moduł analityczny (06.11.2026)

## Co działa

Zapytanie `db/nbp_reference_metrics_v01_READONLY.sql` jest wykonywalnym,
odczytowym komponentem silnika. Korzysta wyłącznie z zachowanych
w Neon danych oficjalnych NBP, z kontrolą instrument_code, source_code,
return_basis, interwału 1d i URL `https://api.nbp.pl/api/`.

Dla trzech niezależnych szeregów USD/PLN i EUR/PLN (średni kurs NBP),
oraz złota NBP (PLN za gram, nie instrument inwestycyjny),
zwraca dokładnie jeden rekord na serię, nawet przy brakujących danych:
- 1. i 6. ostatnią dostępną obserwację do obliczenia
  zmiany procentowej w ostatnich pięciu obserwacjach;
- 1. i 21. obserwację do zmiany procentowej w dwudziestu
  odstępach obserwacyjnych;
- rozstęp wartości w ostatnich 21 obserwacjach
  (max/min − 1), nie odchylenie standardowe i nie ryzyko portfela;
- status pokrycia: SOURCE_MISSING, SOURCE_STALE (ponad 7 dni),
  REFERENCE_WINDOW_SHORT albo REFERENCE_RECENT;
- cutoff, ostatnie rzeczywiste daty obserwacji i pozyskania,
  link do źródła i SHA-256 uporządkowanego okna wejściowego.

Wyniki są OPISOWE. Nie powstają sygnały kupna, wybór instrumentu,
P&L, wirtualne zlecenia, realne operacje ani backtest total return.
Nie certyfikujemy oryginalnej godziny publikacji historycznych notowań.

## Potwierdzony wynik na Neon main i testowym Neon

Projekt `red-lake-53043722`, główna gałąź LAB
`br-shy-voice-badzlf0x`, cutoff `2026-11-05 19:00:00Z`.

| Seria | Data ostatnia dostępna przy cutoff | Zmiana 5 obs. | Zmiana 20 obs. | Rozstęp 20 odstępów | Status |
| --- | --- | ---: | ---: | ---: | --- |
| EUR/PLN | 2026-10-16 | −0.2604% | +0.0642% | 1.0055% | SOURCE_STALE |
| Złoto NBP PLN/g | 2026-10-16 | +0.1464% | −1.3811% | 4.6602% | SOURCE_STALE |
| USD/PLN | 2026-10-16 | −0.4997% | +2.1817% | 3.3745% | SOURCE_STALE |

**Ważne rozróżnienie:** stan bazy LAB na 6.11 zawiera NBP
do 5.11 (FX) i 6.11 (złoto), ale przetwarzanie nowych danych
nastąpiło po cutoff 5.11 19:00Z. Obserwacje nie były więc
historycznie dostępne dla poprzedniego cyklu — prawidłowy filtr
`observed_for <= cutoff AND ingested_at <= cutoff` wykluczył je.
Stan bazy dziś SOURCE_RECENT, stan źródeł przy tym cutoff SOURCE_STALE.
Z tego powodu należy pokazywać OBA, a nie zastępować jednego drugim.

Niezależny health v0.2, uruchomiony na izolowanej gałęzi Neon
`br-purple-night-ba3e6uwv`, potwierdził:
ENGINE_OK 3/3, poprawne SHA wejść 3/3,
market_reference_status=SOURCE_RECENT,
market_reference_at_cutoff_status=SOURCE_STALE_AT_CUTOFF.
Zero paper fills i realnych operacji.

## Kod i regresja

- SQL: `db/nbp_reference_metrics_v01_READONLY.sql`.
- Testy PostgreSQL: brak źródeł, 5 i 20 obserwacji,
  zablokowanie przyszłego pobrania, zmiana hash starej ceny,
  oraz odrzucenie URL niepochodzącego z NBP.
- `db/working_engine_v02_health_READONLY.sql` rozdziela
  świeżość obecną i dostępną przy cutoff.
- Testy zdrowia sprawdzają, że świeże DZIŚ dane pobrane PO
  cutoff nie zmieniają historycznego odczytu i nie są udawane
  jako dostępne wczoraj.

Jest to funkcjonalność **engine-first**, nie dashboard.
Nie podłącza jeszcze nowej diagnostyki do automatycznej
decyzji M1/M2/M3: tam nadal potrzebne są kompletne i prawidłowe
szeregi PLN total return. Kontrola automatycznych naturalnych
cykli harmonogramu pozostaje osobnym, nieukończonym odbiorem.

Dowód CI z testów należy dołączyć po ukończeniu workflow dla
ostatniego commitu. Nie przypisywać tu żadnych wyników
akceptacji, których nie zweryfikowano.
