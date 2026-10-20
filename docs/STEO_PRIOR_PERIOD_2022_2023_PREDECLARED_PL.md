# STEO — niezależny okres badawczy 2022–2023: bramka zgodności źródeł

## Etap wdrożenia: walidacja całego wcześniej niewykorzystanego okresu

Po rzeczywistym, udanym pilotażu [GitHub Actions #39431172692](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39431172692): `jan22`, `jan23`, `dec23` to autentyczne EIA XLSX, arkusz `2tab`, WTI `WTIPUUS` rząd 6 oraz Brent `BREPUUS` rząd 7; `jan22` nie ma tekstowego A3 `Forecast date:` i parser **dopuszcza brak tego pomocniczego nagłówka tylko dla wydań 2022**, nigdy nie używając go jako daty dostępności.

Niezależny `scripts/steo_prior_period_validation.py` zachowuje oddzielny `prior_catalog()` z **24 faktycznymi oficjalnymi datami wydania** 2022–2023. Dotychczasowy `steo_historical_archive.catalog()` = 34 wydania 2024–Oct26 nie zmienia się. Do oceny końca 2023 konieczne jest **8 kolejnych wydań Jan–Aug24 jako REFERENCJE JEDYNIE**; nie wchodzą do kohorty prognozowej 2022–2023.

Program wymaga 24 + 8 = 32 poprawnych dokumentów, sprawdza 24 × 2 instrumenty × 3 horyzonty = **144 prognozy retrospektywne**, nie uzupełnia braków syntetycznie, stosuje nieruszane MAE EIA vs simple previous-month naive z TEGO SAMEGO historycznego dokumentu. Podaje źródłowy EIA release day dla 24 prognoz i późniejsze dane referencyjne `>= target_month + 2 miesiące`, a także grupy po roczniku wydania. Zwraca FAIL zamiast uznać niekompletną próbę.

**Uwaga:** 2022–2023 to **wcześniej niezbadana starsza epoka**, a nie przyszły chronologiczny out-of-sample; nie zapewnia niezależnego dowodu realnego zysku, pierwotnego historycznego stanu bajtów, ani inwestowalności WTI/Brent. Wyniki realne zostaną zapisane dopiero po sukcesie publicznego jednorazowego joba `steo-prior-2022-23-fixed-once.yml`. Żadne dane źródłowe XLSX nie są trwale przechowywane przez to uruchomienie.


**Cel:** sprawdzić już sformułowane wnioski z 2024–2026 na nieanalizowanych wcześniej archiwalnych wydaniach EIA. **Nie dopasowujemy zasad po poznaniu wyników.** Rok 2022 stanowi odrębny historyczny okres o silniejszych wahaniach cen energii; 2023 pozwala kontrolować wyniki także po nim. Nie jest to „przyszły out-of-sample” w sensie chronologii, tylko **wcześniej nieużywany okres historyczny**.

## Źródło

Oficjalna tabela archiwów EIA: <https://www.eia.gov/outlooks/steo/outlook.php>. Obejmuje kolejne **24 miesięczne edycje PDF i XLSX** od stycznia 2022 do grudnia 2023, z podaną datą wydania. Datę wewnętrzną `Forecast completed` trzeba rozróżnić od publicznego `Release Date`.

W dotychczasowym kodzie `scripts/steo_historical_archive.py` lista 34 edycji 2024–październik 2026 i wcześniejsze dowody SHA są **zamrożone**. Nie zmieniamy ich ani nie dopisujemy wstecz nowych wydań do poprzedniej próby. Wcześniejszy wynik: dla WTI i Brent prognoza EIA była bliższa późniejszej referencji średnio w horyzoncie 1 miesiąca, prosta prognoza `last month's value` była lepsza przy 3/6 miesiącach; dynamiczny wybór metody nie przebił najlepszego statycznego benchmarku w żadnej z sześciu grup. Odrębny okres pozwala krytycznie ocenić stabilność tego wzorca.

## Pierwszy test — bez raportowania cen i bez trwałego archiwum

Jednorazowy GitHub Actions [`steo-2022-2023-compatibility-once.yml`](../.github/workflows/steo-2022-2023-compatibility-once.yml) pobiera tylko 3 wybrane wcześniej oficjalne XLSX: `jan22_base.xlsx`, `jan23_base.xlsx` i `dec23_base.xlsx`. Czyta bajty do efemerycznej pamięci, sprawdza ograniczenia XLSX/OOXML, SHA-256, liczbę i nazwy arkuszy, a w tabeli `2tab` identyfikuje jedynie pozycje nazw WTI/Brent i nagłówków roku/miesiąca, jeśli są dostępne.

Nie drukuje wartości notowań, nie tworzy artykułów lub wyjściowych plików, nie wykorzystuje poświadczeń i **nie dotyka Neon ani kont aktywów**. Zero nowego abonamentu, zadań harmonogramowych, plików w repozytorium i zmian alokacji wirtualnych.

**Wymóg przed scoringiem:** potwierdzić rzeczywiste pozycje źródeł WTI i Brent oraz zasady przypisywania miesiąca w arkuszach 2022–2023. Jeżeli zmienił się format, nie dopasowujemy po cichu wyników: oddzielny parser musi przejść testy syntetyczne i jawne mapowanie na prawdziwym starym pliku. Dopiero wtedy jednoznacznie wybierzemy ten sam **nieruszany** protokół prognostyczny i ocenimy pełne 24 dawne wydania.

**Ważne ograniczenie:** XLSX pobrany dzisiaj z folderu `archives/2022` nadal nie potwierdza, że identyczne bajty były tam w dniu publikacji. Tego nie nazywamy `PIT_CERTIFIED`; pozostajemy przy opisowym badaniu retrospektywnym. Cena referencyjna WTI/Brent w USD/baryłkę nie stanowi inwestowalnego PLN total-return instrumentu i nie daje podstaw do wykonywania transakcji. M1–M3 `HOLD_NO_CHANGE`.

Dowody wcześniejszej próby: [34 historyczne wydania 2024–2026](STEO_FULL_34_REAL_RESULTS_2026_10_20_PL.md), [prawdziwa walidacja chronologiczna](STEO_REAL_WALKFORWARD_ROBUSTNESS_2026_10_20_PL.md).
