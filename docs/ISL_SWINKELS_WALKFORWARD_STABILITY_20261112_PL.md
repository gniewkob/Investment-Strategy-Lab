# ISL: retrospektywna diagnostyka błędów prognoz Swinkels (2026-11-12)

**Zakres:** Issue #148. Wyłącznie badanie historycznych zagregowanych błędów prognoz na ORYGINALNYM, sprawdzonym SHA-256 zbiorze Swinkels CC BY 4.0 (DataverseNL DOI 10.34894/YWT2IX). Bez handlu, alokacji, sygnałów finansowych lub integracji M1–M3.

## Pytanie i metoda

Porównujemy dwie z góry ustalone metody prognozy kolejnej miesięcznej stopy zwrotu obligacji rządowych. Bazowa metoda to średnia wszystkich wcześniejszych dostępnych miesięcy. Kandydat to średnia z sześciu wcześniejszych miesięcy. Prognoza miesiąca t nie może korzystać z jego wyniku ani danych z późniejszego miesiąca. Przed pomiarem używamy pierwszych 12 miesięcy 2020-01..2020-12, po czym raportujemy 24 błędy historyczne 2021-01..2022-12 dla każdego z 10 oryginalnych wariantów (240 par błędów łącznie).

MAE w punktach bazowych to średni bezwzględny błąd prognozy miesięcznej stopy zwrotu, NIE stopa zwrotu strategii, koszt, spread, ani prognoza możliwej do uzyskania rentowności. Różnica MAE bazowej i 6-miesięcznej średniej to diagnostyka modelu, nie dowód przewagi predykcyjnej. Historyczny okres był już analizowany, zatem NIE jest niezależnym prospektywnym holdoutem. Warianty rynków mogą być skorelowane.

## Autentyczność i granice

Źródło: Laurens Swinkels, Historical Data International Monthly Government Bond Returns, DataverseNL DOI 10.34894/YWT2IX; oryginalny ODS datafile 512630, SHA-256 90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847, 913425 bajtów, licencja CC BY 4.0 (wymagana atrybucja). Najpierw sprawdzane są dokładne oryginalne bajty, 360 obserwacji i niezależne wzory zwrotów z wcześniejszego modułu #123. Nie zapisujemy surowych zwrotów, pojedynczych prognoz lub pliku ODS w repozytorium, danych użytkownika, portfela ani zleceń.

Próba nie obejmuje polskich obligacji i kończy się w 2022. Dane zwrotów są szacunkowe i pochodziły z późniejszego, poprawionego zbioru. Starsze Erasmus v6 vs nowe DataverseNL nie ma potwierdzonej tożsamości bajtowej; oryginalne historyczne wersje publikacji/PIT pozostają niepotwierdzone. Żadna ścieżka nie kwalifikuje GLOBAL_EQUITY_TR_PLN, PL_BONDS_TR_PLN ani GOLD_TR_PLN. M1–M3 pozostają INSUFFICIENT_DATA / HOLD_CASH. Nie wykonujemy transferów, płatności, zleceń, operacji finansowych, zapisów do zewnętrznej bazy i cykli produkcyjnych.

## Odbiór

- Network-free 10 testów, Ubuntu i macOS: błędny format, niepełny okres, NaN/Inf, typ bool, warunki lag, brak wycieku informacji z przyszłego miesiąca, nieoryginalne bajty.
- Oficjalny jednorazowy odczyt oryginalnego pliku, wiązanie SHA + 360 wcześniej zweryfikowanych zwrotów, wyłącznie 10 agregatów i 240 ocen jakości błędu.
- Workflow: .github/workflows/isl-swinkels-walkforward-ci.yml. Pełna regresja repo uruchamiana przy zmianie scripts/swinkels_*.py i tests/test_swinkels_*.py.
- Przed merge wymagane: zielone exact-head CI, GitGuardian i niezależny code review, następnie regresja main.

Otwarte odrębne bramki: #123 oryginalna wersja archiwalna, #116 licencje/warianty PIT, #97 NAV Vanguard, #138 historyczny GitGuardian i #146 zależność Zod.
