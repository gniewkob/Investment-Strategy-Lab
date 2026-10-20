# STEO — rzeczywiste oficjalne XLSX i mapowanie cen, 20.10.2026

## Zweryfikowane realne odczyty (nie fixture)

Po scaleniu [PR #39](https://github.com/gniewkob/Investment-Strategy-Lab/pull/39) (251/251 testy offline, 3/3 integracyjne PG) i [PR #40](https://github.com/gniewkob/Investment-Strategy-Lab/pull/40) jednorazowy publiczny test [#39409917300](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39409917300) wykonał **rzeczywiste** HTTPS GET do 3 historycznych oficjalnych XLSX EIA; weryfikator ZIP/OOXML zaakceptował każdy plik. Zapisano tylko logi metadanych, **NIE zachowano bajtów XLSX w GitHub**. Brak połączeń z Neon i jakichkolwiek danych klientów.

| Wydanie | Oficjalna data wydania | Raw XLSX SHA-256 przy realnym odczycie | Arkusze | ZIP members |
| --- | --- | --- | ---: | ---: |
| jan24 | 2024-01-09 | `663ee3c648d2e88dad48dd1efd2557df99c811afe4afcc2094ed92c988fb53a9` | 24 | 86 |
| jan25 | 2025-01-14 | `67f9f24b6f0bd074bcc92e47f8f5ea23594f2dd6ccbf31b2dff912621bbb5b22` | 28 | 98 |
| oct26 | 2026-10-06 | `54989362410da4aff5673580396380c3a8f4f111fa6d01c6d4fab05ef90efbf4` | 28 | 98 |

Po [PR #41](https://github.com/gniewkob/Investment-Strategy-Lab/pull/41) (254/254 synthetic offline + 3/3 PG testy PASS) kolejny publiczny test [#39410674417](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39410674417) pobrał te trzy oficjalne wersje jeszcze raz i zweryfikował pozycję nagłówków i identyfikatory szeregów.

## Realne pozycje Table 2 / arkusz `2tab`

Potwierdzone we wszystkich trzech wydaniach:

- Tytuł `B1: Table 2. Energy Prices`; tekst edycji w `B2`.
- `A3: Forecast date`; `A4` podaje dzień zakończenia prognozy, **NIE dzień jej publicznej publikacji**: jan24 `2024-01-04`, jan25 `2025-01-09`, oct26 `2026-10-01`. **Nigdy nie używaj tego dnia jako historycznego czasu dostępności.** Użyj co najmniej *następnego dnia UTC po oficjalnej dacie publikacji* z indexu, z dodatkowym zastrzeżeniem o możliwych współczesnych poprawkach pliku.
- Nagłówki roku w wierszu **3**, angielskie miesiące `Jan`–`Dec` w wierszu **4**.
- `A6 = WTIPUUS`, `B6 = West Texas Intermediate Spot Average` — cena spot WTI w USD/bbl.
- `A7 = BREPUUS`, `B7 = Brent Spot Average` — cena spot Brent w USD/bbl.
- Początek 12 kolumn 2024/2025/2026: w `jan24` rok 2024 rozpoczyna się `AY3`, rok 2025 `BK3`; w `jan25` rok 2024 `AM3`, 2025 `AY3`, 2026 `BK3`; w `oct26` rok 2024 `AA3`, rok 2025 `AM3`, rok 2026 `AY3`, 2027 `BK3`.
- Z tego wynika konieczność mapowania `(year,month)` według wierszy 3 i 4, **nie według stałej kolumny**. Arkusz `2tab` zawiera także gaz ziemny, ale obecny ograniczony log 90 etykiet zakończył się na wierszu 12; jeszcze nie potwierdzono położenia wiersza Henry Hub. Nie zgaduj.
- W żadnym logu nie ujawniono cen, nie wykonano formuł, nie stworzono forecast targetów ani zwrotów portfela.

## Stan faktyczny i co pozostaje

**Etap katalogu i technicznej wiarygodności plików: PASS.** Trzy rzeczywiste historyczne pliki XLSX dostępne i zgodne z OOXML; powtarzalny odczyt SHA; 34 edycje z oficjalnymi datami w allowliście. Edycje różnią się liczbą arkuszy, ale pozycje `WTIPUUS` i `BREPUUS` w Table 2 są zgodne.

**Trafność realnych historycznych prognoz nadal NIEPOLICZONA**, ponieważ nie wykonano jeszcze ekstrakcji odpowiednich liczbowych komórek, porównania z later-published realizacjami ani benchmarku. Miesięczne STEO XLSX mogą zawierać po fakcie zmienione dane, więc historyczny PIT na bajtach z dawnych dat pozostaje `UNVERIFIED`. Archiwalny `Release Date` jest właściwym dolnym ograniczeniem dla publicznej dostępności, nie niezależnym dowodem oryginalnych bajtów.

**Kolejne działanie:** parser konkretnych `(issue,source_code,target_month,forecast_value,unit)` oparty o nazwy `WTIPUUS`/`BREPUUS` i dynamiczną mapę row3/year+row4/month, obowiązkowo testowany na prawdziwych arkuszach i w sztucznych fixture. Następnie ocena wyłącznie historycznych prognoz (nie wyników portfela) z referencjami z późniejszej opublikowanej edycji, w tych samych miesiącach i horyzontach, bez look-ahead.

Dodatkowe źródło: <https://www.eia.gov/outlooks/steo/outlook.php>; [instrukcja prywatnego archiwum](STEO_HISTORICAL_ARCHIVE_RESEARCH_PL.md). Zamknięty backup dziennych cen EIA pozostaje nienaruszony; Neon bez zmian, M1/M2/M3 `HOLD_NO_CHANGE`, real_orders 0.
