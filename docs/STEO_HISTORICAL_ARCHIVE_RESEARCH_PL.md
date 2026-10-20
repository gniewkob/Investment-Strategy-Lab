# Historical STEO vintages — 34 archiwalne wydania EIA (2024–10.2026)

**Status etapu:** katalog i bezpieczny archiwizator lokalny są w kodzie; **nie pobrano jeszcze historycznych arkuszy EIA** i nie policzono błędów prognoz. Używaj wyłącznie do niezależnego researchu, nie do realnych lub wirtualnych zleceń.

## Dane z urzędowego archiwum

Oficjalny <https://www.eia.gov/outlooks/steo/outlook.php> prezentuje daty publikacji i osobne PDF + XLSX dla 34 kolejnych wydań od stycznia 2024 do października 2026 (12 + 12 + 10). Historyczne arkusze udostępniono pod adresem `https://www.eia.gov/outlooks/steo/archives/{issue}_base.xlsx`, np. `jan24_base.xlsx`, `jan25_base.xlsx`, `oct26_base.xlsx`.

Źródło danych jest **inne niż dzienny backfill WTI/Brent/Henry Hub**. Każde oryginalne datowane wydanie STEO opisuje **przeszłą prognozę** na przyszły okres. Możemy ocenić dokładność prognoz historycznych, ale dopiero po odczycie i niezależnym sprawdzeniu właściwych komórek i ich semantyki.

**Zastrzeżenie: podana przez EIA data wydania ≠ potwierdzenie, że bajty historycznego XLSX pobranego dziś były identyczne w dniu wydania.** Archiwizator zapisuje rzeczywisty czas pobrania i nadaje `historical_original_publication_bytes_certified=false`. Dokument PDF lub XLSX mógł zostać później poprawiony; dla silnej historycznej PIT próby szukać niezależnego datowanego snapshotu/digestu.

## Co już można zrobić BEZ sieci i bez zapisów

W katalogu repozytorium Investment Strategy Lab:

```bash
python3 -m scripts.steo_historical_archive catalog
```

Raportuje dokładną datę wydania, URL XLSX/PDF, identyfikator `jan24` ... `oct26` oraz liczbę 34. Bez zapisu plików i jakiegokolwiek połączenia z Neon.

## Opcjonalny rzeczywisty pilotaż: trzy autentyczne, historyczne wydania

Na Mac mini, jeśli zdecydujesz się wykonać pobieranie do **nowego, prywatnego archiwum**, najpierw utwórz katalog poza Git:

```bash
umask 077
mkdir -m 700 -p "$HOME/.isl-steo-archive"
```

Następnie świadomie uruchom pobranie trzech małych, odrębnych vintage XLSX: styczeń 2024, styczeń 2025, październik 2026. Każde zostanie ograniczone do 24 MiB, sprawdzone pod względem ZIP OOXML, otrzyma SHA-256, rzeczywisty `retrieved_at`, osobny prywatny manifest i natychmiastową niezależną weryfikację:

```bash
python3 -m scripts.steo_historical_archive capture \
  --archive-root "$HOME/.isl-steo-archive" \
  --issues jan24,jan25,oct26
```

**Uwaga:** ten krok wykonuje jawne HTTPS na oficjalnych adresach EIA i tworzy prywatne pliki lokalne. Jest to **nowe archiwum STEO**, nie modyfikuje ani nie otwiera ponownie zamkniętego backupu dziennych EIA na MyDevil/Mac.

Po pobraniu, na tej samej maszynie:

```bash
python3 -m scripts.steo_historical_archive verify \
  --archive-root "$HOME/.isl-steo-archive"
```

`verify` jest bez internetu, bez Neon i bez zapisów, sprawdza hash każdego XLSX, tożsamość wydania, czas pozyskania, metadane źródła, listę arkuszy i manifest.

## Następny etap: rzeczywisty parser prognoz

Nie zakładamy z góry układu tabel w `jan24_base.xlsx`, `jan25_base.xlsx` i `oct26_base.xlsx`. Test pilota zwróci realne nazwy arkuszy. Dopiero po ich sprawdzeniu zbudujemy ekstraktor konkretnych `(issue, instrument, target_month, forecast_value, units)`, aby uniknąć pomylenia wartości faktycznych, nowcastu, prognozy lub rocznej średniej. Różne wydania mogą zmieniać układ.

Porównanie metodologicznie powinno używać:
1. Prognozy dla miesiąca **późniejszego niż** data wydania; `as_of` nie wcześniej niż po dacie publikacji STEO z precyzją DAY.
2. Referencji opublikowanej **po zamknięciu prognozowanego miesiąca**, z jawnie wskazaną polityką rewizji wartości rzeczywistych.
3. Bazy porównawczej dostępnej w tym samym raporcie (np. ostatnia historyczna cena w wydaniu), a nie ostatniej ceny znanej dzisiaj.
4. Parowanych zdarzeń dla tych samych `target_month` i horyzontów, porównania MAE/sMAPE, braku nadmiernego dopasowania i testu na innych miesiącach.
5. Żadnych wniosków o realnych zwrotach z inwestycji, dźwigni, sygnałach transakcyjnych ani zmianach M1–M3; dane STEO są prognozami cen spot, nie total-return aktywami w PLN.

**Odseparowane obecne realne Neon STAGING:** `price_observations=3746` dla 12 serii. Bezpośrednia opisowa analiza historyczna jest już możliwa; 34 archiwa STEO rozbudują ją o datowane dawne prognozy, a nie zastąpią istniejących danych. Żadna operacja programu `steo_historical_archive` nie wykonuje zapytań do Neon, nie używa poświadczeń i nie generuje żadnych zleceń.

Źródła oficjalne: <https://www.eia.gov/outlooks/steo/outlook.php>, <https://www.eia.gov/outlooks/steo/archives/jan24_base.xlsx>.
