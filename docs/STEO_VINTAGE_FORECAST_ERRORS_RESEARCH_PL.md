# STEO — prawdziwe miesięczne prognozy WTI/Brent z wydań historycznych (research only)

## Cel badania

Nie czekamy na przyszłe dane, ponieważ EIA już udostępnia 34 odrębne historyczne wydania raportu STEO z datami publikacji i tabelami prognoz. Celem jest **retrospektywna ocena prognoz cen referencyjnych**, a nie symulacja zysków z handlu czy rekomendacja realokacji kapitału.

Po rzeczywistych testach [#39409917300](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39409917300) i [#39410674417](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39410674417) parser `scripts/steo_monthly_forecast_eval.py` został przygotowany dla WTI i Brent:

- Oryginalne STEO XLSX `2tab`, tabela `Table 2. Energy Prices`.
- WTI `A6=WTIPUUS`, `B6=West Texas Intermediate Spot Average`. Brent `A7=BREPUUS`, `B7=Brent Spot Average`. Jednostka: USD/bbl, **miesięczna cena referencyjna**, nie transakcyjny zwrot.
- Rok odczytywany z nagłówka w wierszu 3, miesiąc Jan–Dec z wiersza 4. Mapa kolumn jest wyznaczana na nowo dla **każdego wydania**; absolutne adresy kolumn są zabronione.
- Wartości są wyłącznie z numerycznych komórek zapisanych w danym pobranym arkuszu (przechowywane w OOXML wartości cache; formuły **nie są wykonywane**); sprawdzenie typu, liczby i jednostki. Jeśli brak źródłowej wartości, parser ją pomija, nie interpoluje i nie wypełnia sztucznie.
- Wybierane są prognozy na miesiące **1, 3 i 6 miesięcy po miesiącu publikacji**. Dane z miesiąca bieżącego są wyłączone (unikamy mieszania aktualizacji, nowcastu i prognozy).
- Dokładne `release_day` z oficjalnego katalogu EIA jest jedyną dopuszczalną datą publikacji; umieszczona w arkuszu data `Forecast date` oznacza wcześniejsze przygotowanie prognozy i nigdy nie może wstecznie przesunąć daty dostępności.
- Baza odniesienia: w **tej samej historycznej edycji** ostatnia wartość za miesiąc poprzedzający wydanie (naive persistence). **Nie** bazujemy jej na zrewidowanych współczesnych szeregach.
- Przyszły wynik: **pierwsze spośród faktycznie przekazanych do porównania** wydań `jan24,jan25,oct26`, którego miesiąc wydania wypada **co najmniej 2 miesiące po prognozowanym miesiącu**. Jest to później podana **historyczna wartość referencyjna** z kolejnego arkusza STEO, nie niezależnie certyfikowane ostateczne zamknięcie rynkowe. Zestaw `3` wydań nie jest pełnym rejestrem wszystkich rewizji.
- Dla par `(wydanie, instrument, horyzont, miesiąc docelowy)` policzyć błąd bezwzględny EIA i naive, parowane MAE, liczebność, jawny `reference_edition`. Różnice MAE przy małej próbie opisujemy **wyłącznie badawczo**, bez wniosków o przewadze predykcyjnej.
- Każda liczba pochodzi z jawnie wskazanego oficjalnego XLSX, nie z danych syntetycznych; testy CI natomiast korzystają tylko z niezależnych fikcyjnych fixture.

## Publiczny pilotaż bez poświadczeń i bez zapisywania źródeł do repozytorium

Jednorazowy przepływ GitHub Actions [STEO historical official XLSX pilot](../.github/workflows/steo-historical-public-probe-once.yml) pobiera tylko trzy jawnie dozwolone pliki XLSX, następnie uruchamia parser oraz metryki parowane. Workflow drukuje publiczne wartości źródłowych prognoz i późniejszych referencji oraz ograniczenia, nie zapisuje źródłowych XLSX, artefaktów ani raportów do GitHub i nie korzysta z Neon/brokera.

Lokalne, wyłącznie badawcze uruchomienie z jawną siecią (po pobraniu najnowszej wersji repozytorium):

```bash
python3 -m scripts.steo_monthly_forecast_eval --issues jan24,jan25,oct26
```

Dostępnych jest dokładnie 34 kodów wydań w `python3 -m scripts.steo_historical_archive catalog`. CLI ogranicza jedną próbę do 2–6 różnych wydawnictw, żeby nie generować niekontrolowanego ruchu HTTP. Dla pełnego materiału prospektywnie dołączyć więcej edycji oraz trwale archiwizować raw XLSX lokalnie przez zatwierdzony wcześniej `steo_historical_archive.py` — na razie nie zlecano takiego archiwizowania.

## Obowiązkowe ostrzeżenie

Historyczne bajty pliku pobranego **teraz**, choć dostępne w oficjalnym katalogu nazwanym `jan24`, mogły zostać skorygowane po styczniu 2024. **Bez niezależnego źródła/pierwotnego digestu nie twierdzić `PIT_CERTIFIED` ani `historical_source_as_published_bytes_certified`.** Chronologia prognoza/późniejszy referencyjny odczyt jest poprawna dla *zrekonstruowanych* edycji, nie jest certyfikacją informacji posiadanej przez hipotetycznego inwestora w dniu historycznym.

WTI/Brent to USD ceny spot bez przepływów pieniężnych, PLN FX, kosztów, prowizji, podatków czy zleceń. Nie wolno zamienić błędu prognozy na stopę zwrotu portfela. M1/M2/M3 w badawczym portfolio pozostają `HOLD_NO_CHANGE`.

**Granice bezpieczeństwa:** tylko allowlisted publiczny HTTPS, zero Neon połączeń/zapisów, zero kluczy/ACL, zero trwałych plików z danymi na GitHub, zero harmonogramów, zero realnych zleceń i zerowe zmiany alokacji, backup MyDevil/Mac EIA pozostaje zamknięty.

Dowody źródłowe: <https://www.eia.gov/outlooks/steo/outlook.php>, [ustalona mapa oficjalnych wydań](STEO_REAL_PUBLIC_XLSX_PILOT_2026_10_20_PL.md).
