# STEO — pełny historyczny eksperyment na 34 archiwalnych wydaniach (2024–2026)

## Zakres

Wszystkie **34 archiwalne miesięczne wydania raportu EIA Short-Term Energy Outlook** (styczeń 2024 – październik 2026) z oryginalnie indeksowanymi datami publikacji. To próba zmniejszenia błędu selekcji przy wcześniejszym 3-edycyjnym pilotażu, nie historyczna certyfikacja immutable PIT.

Wykorzystujemy `scripts/steo_historical_archive.py` do pobrania oryginalnych bajtów XLSX HTTPS tylko spod dozwolonych adresów EIA oraz `scripts/steo_monthly_forecast_eval.py` do parsowania ich wartości WTI/Brent `2tab`. **Każdy oryginalny SHA-256** jest zapisywany wyłącznie jako metadane w logach; całe archiwalne pliki XLSX istnieją tylko w pamięci efemerycznego runnera i nie są udostępniane jako artefakty ani w repozytorium.

## Jak powstaje porównanie

- Prognozy dla dokładnie **1, 3 i 6 miesięcy kalendarzowych naprzód**, licząc względem miesiąca oficjalnej daty `Release Date` wydania.
- Tylko oficjalny identyfikator `WTIPUUS` (WTI) i `BREPUUS` (Brent), monthly energy-spot-price reference USD/bbl; rok/miesiąc z nagłówków `2tab`, nie ze stałego adresu kolumny.
- Późniejsza referencja: pierwsze **z archiwów znajdujących się w próbie** wydanie z datą publikacji **nie wcześniej niż dwa miesiące kalendarzowe po miesiącu docelowym**. To retrospektywne `first sampled reference`, nie niezależnie ostateczna obserwacja rynkowa ani wynik inwestycyjny.
- Porównujemy prognozę EIA z naiwną wartością za miesiąc bezpośrednio przed datą wydania, odczytaną z **tej samej dawnej wersji arkusza** (unika użycia późniejszej wersji dla naiwnego baseline).
- Dla każdej pary i całej próby: błąd bezwzględny, parowane średnie błędy MAE, liczba par, przekroje według roku wydania, instrumentu i horyzontu, liczba indywidualnych wygranych EIA nad naiwną. Żadna wartość MAE nie jest przeliczana na zysk/zlecenie/stopę zwrotu portfela.
- Unikanie pułapki dat: nagłówek arkusza `Forecast date` to data przygotowania prognozy, **nie** data publikacji. Pierwszy dopuszczalny dzień to kolejny dzień UTC po `Release Date` podanej na oficjalnej stronie, **ale historyczna niezmienność pobranych dziś bajtów jest nadal NIEZWERYFIKOWANA**.
- Komórki OOXML `cached numeric` są przyjmowane do zestawienia wyłącznie jako publiczne referencyjne wartości miesięczne; nie uruchamiamy formuł ani zewnętrznych powiązań. Wartości z końcówkami binarnej reprezentacji `71.900000000000006` normalizowane są do **0.01 USD/bbl** (dokładność prezentacji cen w Table 2), a oryginalne bajty są identyfikowane niezależnym SHA-256.

## Jednorazowy publiczny research GitHub Actions

[`.github/workflows/steo-full-archived-research-once.yml`](../.github/workflows/steo-full-archived-research-once.yml) uruchamia się **jednorazowo po scaleniu definicji na `main`** lub świadomie przez `workflow_dispatch`; **nie ma harmonogramu**. Brak sekretów, baz Neon, brokerów, plików wynikowych, źródłowych danych klientów, lokat, realnych transakcji i alokacji.

Wyniki logów:
- `STEO_ARCHIVED_REAL_ISSUE_VERIFIED` — dla każdego prawdziwego wydania identyfikator, oficjalny release day, SHA-256 XLSX w momencie pobrania i liczba odczytanych obserwacji z tabeli 2;
- `STEO_REAL_34_RELEASE_HISTORICAL_FORECAST_RESULT` — liczba rzeczywiście pobranych wydań, łączne parowane MAE oraz podział według rocznika wydania, instrumentu i horyzontu.

**Bramka FAIL-CLOSED:** jeśli dowolne wydanie z 34 nie przejdzie legalnego HTTPS, walidacji OOXML, nagłówka kodów serii lub pobranie się nie powiedzie, test kończy się błędem, raportuje wyłącznie `issue` + typ błędu, nie udaje pełnej analizy; wyniki z niepełnej próby nie są raportowane jako 34/34.

Ten eksperyment jest **wyłącznie retrospektywną analizą jakości archiwalnych prognoz publicznych**, nie dowodem inwestycyjnym. Historyczne pliki dostępne obecnie na EIA mogą różnić się od plików z dawnych dat. Ponadto prognozy różnych miesięcy nakładają się na docelowe okresy, co uniemożliwia naiwne interpretacje liczebności jako liczby niezależnych zdarzeń.

Aktualnie zatwierdzony, rzeczywisty pilotaż 12 par i MAE: [STEO_REAL_FORECAST_ERRORS_2026_10_20_PL.md](STEO_REAL_FORECAST_ERRORS_2026_10_20_PL.md).

Zachowujemy decyzję badawczą `HOLD_NO_CHANGE` dla wirtualnych M1/M2/M3. Backup dotychczasowego EIA MyDevil/Mac pozostaje zakończony.
