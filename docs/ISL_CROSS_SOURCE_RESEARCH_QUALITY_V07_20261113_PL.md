# Investment Strategy Lab — public-first v0.7, zintegrowana jakość źródeł

## Zakres dużego pakietu

[Issue #160](https://github.com/gniewkob/Investment-Strategy-Lab/issues/160) i [PR #161](https://github.com/gniewkob/Investment-Strategy-Lab/pull/161) rozwijają **jednocześnie** historyczne źródło obrotów polskimi obligacjami (MF), zmienność obserwowanych poziomów NAV UKNF oraz wspólną kwalifikację NBP/Eurostat. Nie tworzymy osobnych PR-ów dla każdej strony lub dokumentu.

| Obszar | Faktyczne źródło pierwotne | Zweryfikowany stan i świadomie ograniczone wnioski |
|---|---|---|
| UKNF — funduszowa jednostka podstawowa PLN | [Oficjalne API](https://wybieramfundusze-api.knf.gov.pl/documentation.html), [warunki §3](https://wybieramfundusze-api.knf.gov.pl/terms.pdf) | Zweryfikowane wcześniej 22 dni września 2026, oryginalne SHA `cc12a89d7f16bdccf16715427cda76f231ff21af82732e5736641d15264eea85`; NAV-level change `−0,4082%`, **nie** investor total-return ani VaR |
| MF — krajowy rynek wtórny obligacji | [Statystyka MF](https://www.gov.pl/web/finanse/statystyka-rynku-wtornego), [oryginalny XLSX](https://www.gov.pl/attachment/e720fd6f-1bd6-4e2f-87b4-6d05e03473d4) | 56 050 B, 1 arkusz, SHA `5fd7f4fceb1403f1978553079e3a566a70e04d849af29c6a9c7ee41a7d5f42c8`. Nowa struktura arkusza wymaga **rzeczywistego schematu** przed obliczeniem sum. Obrót to nie stopa zwrotu |
| NBP + Eurostat | [NBP API](https://api.nbp.pl/) i [Eurostat API](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction) | Ponowne wykorzystanie działających 5 serii v0.5 (kursy FX, złoto, HICP i rentowność ~10Y) z rozróżnieniem jednostek i dat. Brak PIT oryginalnych historycznych wersji i indeksów TR |

## Funkcjonalności obecnego PR

**1. UKNF — analiza ściśle tej samej klasy jednostki.** `scripts/knf_one_class_nav_quality_v07.py` przyjmuje cztery oryginalne odpowiedzi i uruchamia już istniejącą walidację `evaluate_sample` (identyfikatory funduszu, subfunduszu, klasa jednostki, PLN, pierwotna kategoria, dokładny zakres dat, niepuste i dodatnie wartości, brak przyszłości i błędnego powiązania KID). Oblicza wyłącznie opisowe agregaty kolejnych **zaobserwowanych** zmian poziomów NAV: minimum, maksimum, średnią, odchylenie standardowe bez annualizacji, a także liczbę kalendarzowych dni pon.–pt. bez wyceny. Kalendarzowe braki nie są twierdzeniem o sesjach rynkowych, bo nie znamy świąt. Brak KID => ryzyko i koszty KID `null`; **nie** używamy danych innego funduszu.

**2. MF — oryginalne XLSX bez nieuprawnionych interpretacji.** `scripts/mf_original_turnover_schema_v07.py` otwiera tylko ograniczone bajtowo i uprzednio zweryfikowane archiwum XLSX (bez makr VBA, linków zewnętrznych ani wykonywania treści). Dekoduje standardowe XML `sharedStrings` i arkusz, kontroluje liczbę wierszy, indeksy, wielkość i odrzuca deklaracje encji. W CI wyświetlane są **jedynie** struktura, typy pierwszych 28 wierszy i bezpieczne opisy nagłówków, bez wartości liczbowych z wierszy. Po uzyskaniu konkretnego schematu da się przygotować wyliczenia udziału obrotów według rynku i kompletności okresów, ale nie wolno zgadywać jednostek. Parser sum obrotów nie jest jeszcze kwalifikowany.

**3. Wspólna macierz kwalifikacji.** `scripts/research_readiness_quality_v07.py` tworzy fail-closed rejestr z oryginalnych, uprzednio walidowanych potwierdzeń UKNF, MF i opcjonalnego wcześniejszego v0.5 NBP/Eurostat. Każdy wiersz ma typ danych, SHA, pokrycie (tam gdzie udowodnione), prawa do źródła i jawne `historical_first_publication_certified=false`. Nigdy nie miesza NAV, aktywności rynku i rentowności rocznej jako porównywalnych stóp zwrotu.

## Reguły odbioru, prawa, blokery

- 27 testów negatywnych syntetycznych bez dostępu do sieci (5 MF XML + 11 NAV + 11 macierz) na Ubuntu i macOS, jednorazowy oryginalny odczyt MF, pełna regresja, GitGuardian, CodeQL, governance i stack — **status faktyczny śledzić per SHA w GitHub Actions**.
- **Aktualna blokada CI (13.11.2026):** pierwsza seria workflow #43404004680 (MF), #43404004465 (stack), #43404004415 (G1) zakończyła się błędem przed wykonaniem jakiegokolwiek kroku; `steps=[]`, pobranie logów kończy się GitHub `BlobNotFound`. Retest miał ten sam problem. To na tym etapie *problem uruchamiania Actions do zdiagnozowania*, **nie wynik testów kodu**. Nie ogłaszać zielonych kontroli ani scalenia.
- [P0 #116](https://github.com/gniewkob/Investment-Strategy-Lab/issues/116) nadal otwarty: licencja GPW/BondSpot dla hurtowej historii indeksów, oryginalny first-publication PIT, prawa do całkowitych stóp zwrotu. Publicznie udostępnione ceny/wyceny/obroty nie oznaczają prawa do przeprowadzania operacji inwestycyjnych.
- M1–M3 `INSUFFICIENT_DATA_HOLD_CASH`, zero realnego handlu, portfeli, transferów, zaplanowanych pobrań, zapisów bazy i rachunków.
