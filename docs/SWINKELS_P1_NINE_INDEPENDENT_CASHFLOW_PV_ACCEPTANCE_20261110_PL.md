# Swinkels P1 — niezależne odtworzenie obligacyjnych stóp zwrotu (2026-11-10)

**Status:** walidacja matematyczna zakresu 2020-01–2022-12 **PASS w środowisku badawczym**; PIT i dopuszczenie do modeli M1–M3 **BLOCKED**. PR #124 pozostaje Draft, bez merge do `main`.

## Oryginalne, przypięte źródło

- Wydawca: DataverseNL, DOI: https://doi.org/10.34894/YWT2IX
- Oryginalny plik: `International Monthly Government Bond Returns.ods`, datafile `512630`; rozmiar **913425 bajtów**; SHA-256 `90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847`.
- Dokument metodologiczny `Readme.pdf`, datafile `512631`; SHA-256 `b4c4b95917fbff72d06c8e3be1364d91d87779c3752d06260775ade45fb41072`.
- Publikacja: Laurens Swinkels (2019), *Treasury Bond Return Data Starting in 1962*, https://doi.org/10.3390/data4030091, §3 (dochód odsetkowy, duration i convexity); **równanie (3) jest wyłącznie referencją dla wariantu `Original_US_1962`**, nie dla wszystkich pozostałych arkuszy.

## Dwa rozłączne warianty matematyczne

**Wariant oryginalny USA, 1962:** test niezależnej wersji równania (3), z duration i convexity wyliczonymi z przepływów obligacyjnych. Na 36 miesiącach 2020–2022 maksymalna różnica zwrotu `6.106e-16`; dowód CI: https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42894126920 .

**Dziewięć pozostałych serii (w tym Improved US):** oryginalny ODS zawiera wspólny, stabilny wzór ceny 10-letniej obligacji par po miesiącu (do wykupu pozostało 9 lat i 11 miesięcy), przy zmianie rynkowej rentowności, plus naliczony miesięcznie dochód odsetkowy. Nie należy utożsamiać go z drugorzędowym przybliżeniem równania (3).

Dla rentowności poprzedniej `p` i bieżącej `y`, **obie w punktach procentowych**, przy `n = 2 × (10 − 1/12)` oraz `r = y/200`:

- Przepływ kuponowy na półrocze względem kapitału nominalnego: `c = p/200`.
- Współczynnik dyskontowy kapitału: `D = (1+r)^(-n)`.
- Wartość bieżąca kuponów w modelu źródłowym: `C = c × (1−D)/r`, z granicą `C → c×n` gdy `r → 0`.
- Miesięczny naliczony dochód: `I = p/1200`.
- Modelowany miesięczny zwrot: `R = D+C+I−1`.

To jest **konwencja modelu źródłowego**, obejmująca ułamkową liczbę okresów kuponowych. Nie jest automatycznie ceną transakcyjną konkretnej obligacji na rynku.

Zastosowano niezależne obliczenie PV wykorzystujące `log1p`/`expm1` i ciągłe przedłużenie dla rentowności zerowych; nie wykonuje ono ani nie parsuje oryginalnego tekstu formuły. Oddzielny, bezpieczny interpreter OpenFormula odtworzył wcześniej zapisane wyniki z tej samej matematyki, ale **ten pierwszy replay nie był niezależnym dowodem ekonomicznym**.

## Dowody i wyniki 2020–2022

| Seria | Miesiące | Maks. błąd niezależnego PV (ułamek zwrotu) | Skumulowany zwrot brutto lokalnego modelu |
|---|---:|---:|---:|
| Improved US | 36 | 7.147e-16 | −11.406% |
| Niemcy | 36 | 1.700e-15 | −22.660% |
| Japonia | 36 | 1.161e-14 | −4.242% |
| Francja | 36 | 2.347e-14 | −23.265% |
| Wielka Brytania | 36 | 9.159e-16 | −20.204% |
| Australia | 36 | 5.967e-16 | −16.751% |
| Kanada | 36 | 3.365e-16 | −8.877% |
| Norwegia | 36 | 4.823e-16 | −9.361% |
| Szwecja | 36 | 6.529e-15 | −18.288% |

**Suma:** 324/324 zweryfikowanych obserwacji dla 9 serii, największy błąd `2.347e-14` przy technicznej tolerancji `1e-10`; oryginalny USA osobno 36/36 → łącznie **360 historycznych obserwacji** z pozytywną walidacją matematyczną w dwóch różnych wariantach.

CI wartości bieżącej: https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42904720290 — testy matematyczne **10/10 PASS na Ubuntu, 10/10 PASS na macOS**, źródłowy test 324 obserwacji PASS. Odrębny replay OpenFormula: https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42904258642 .

**Ostrzeżenie interpretacyjne:** zwroty są historyczne i modelowane dla obligacji danego rynku; nie są stopami zwrotu w PLN, bez kosztów realizacji, spreadów, podatków, ryzyka walutowego czy rebalancingu. Nie stanowią rankingu instrumentów do zakupu ani wyniku inwestycyjnego użytkownika. Dane kończą się w grudniu 2022 r.

## Czego test NIE udowadnia

1. Historycznej dostępności PIT do każdego miesiąca i braku późniejszych rewizji w pliku opublikowanym retrospektywnie.
2. Bezpośredniej wykonalności cen obligacji, dostępności konkretnych ETF-ów albo historycznych kosztów transakcyjnych.
3. Ekonomicznej poprawności i niezależności źródeł `Yield 10Y` wszystkich krajów oraz jednolitej definicji 10-letniej obligacji.
4. Odpowiedniości serii do decyzji portfelowych M1–M3 i aktualności względem 2026 roku.
5. Walidacji portfela, strategii inwestycyjnej, wyników net-of-fees albo realnego handlu.

**Bramki pozostają zamknięte:** `qualified_model_series=[]`, `historical_pit_certified=false`, `INSUFFICIENT_DATA/HOLD_CASH`. Wyłącznie lokalna / CI analiza edukacyjna, bez podłączenia do prawdziwych aktywów i bez zapisu rynkowych danych do trwałego repozytorium.

## Decyzja dla PR

**ACCEPT — research computation** dla dwóch historycznych wzorów (oryginalny USA oraz wspólny model 9 innych arkuszy). **REJECT — PIT/model qualification** do czasu udokumentowania dat publikacji/revizji i niezależnych danych ceny/instrumentu przydatnego dla wybranego silnika. PR #124 pozostaje Draft; rekomendowane dalsze prace to dopięcie evidence contract i oddzielenie historycznych modeli referencyjnych od wejść modelu decyzyjnego.
