# EIA STEO: audyt chronologiczny, nakładające się miesiące i rewizje referencji

## Dlaczego

[Poprzedni test rzeczywisty 34/34 XLSX](STEO_FULL_34_REAL_RESULTS_2026_10_20_PL.md) udokumentował 172 pary: dla 1 miesiąca średnio lepsze źródłowe prognozy EIA, dla 3 i 6 miesięcy niższy MAE prostego modelu. Nie możemy z tego wnioskować o statystycznie niezależnych sygnałach: miesiące docelowe powtarzają się **między horyzontami**, a później publikowane ceny referencyjne STEO podlegają rewizjom.

## Dwie odrębne analizy — zero transakcji, wyłącznie historyczna rekonstrukcja

**A. Dynamiczny wybór metody z dojrzałych historycznych wyników** — `walkforward_audit` w `scripts/steo_robustness_audit.py`:

- Sześć osobnych grup: WTI/Brent × horyzont 1/3/6 miesięcy. Żadnego łączenia horyzontów na potrzeby „treningu” ani wyciągania wniosków z 172 pozornie niezależnych prób.
- Przy każdym późniejszym historycznym wydaniu `as_of` uwzględniamy jedynie starsze prognozy, dla których **późniejsza referencyjna wartość została już ujęta w raporcie opublikowanym ściśle PRZED datą rozpatrywanego wydania**. Wprost zakaz używania wyników z przyszłości przy wyborze metody.
- Wymagamy minimum **6 dojrzałych historycznych prognoz dla konkretnej pary instrument–horyzont**. Jeśli jest ich mniej, **brak wyboru i brak oceny**, nie uzupełniamy wyników z przyszłych raportów.
- Z góry ustalona reguła: gdy wcześniejszy średni parowany błąd źródłowy EIA jest mniejszy od średniego błędu prostej prognozy w tym samym zestawie → wybierz EIA; w przeciwnym razie wybierz model „ostatni miesiąc bez zmiany”. Reguła jest zdeterminowana, nieskalibrowana na okresie testowym.
- Każdy wybór zapisuje `latest_matured_reference_day` oraz `forecast_issue_day`; **pierwsza data musi być wcześniejsza**. Wynik porównuje MAE wybranej metody z tymi dwiema metodami zawsze stosowanymi osobno na dokładnie *tych samych kwalifikowanych parach*.
- To **edukacyjny walk-forward datowanego materiału archiwalnego**, NIE certyfikowany backtest w historycznym PIT. Dzisiejsza zawartość starych XLSX może różnić się od bajtów znanych w przeszłości.

**B. Czułość na rewizje historycznych cen referencyjnych** — `reference_revision_audit`:

- Dla każdej prognozy zachowaj pierwszą kwalifikującą się późniejszą referencję z datowanego raportu STEO **co najmniej dwa miesiące po miesiącu docelowym**.
- Jeśli istnieją jeszcze późniejsze archiwalne wydania z referencją na dokładnie ten sam miesiąc, porównaj ją z **ostatnim dostępnym historycznym raportem w próbie**. Liczba i skala zmian między wydaniami oraz MAE liczone przy pierwszej versus najnowszej referencji pokazują zależność oceny prognozy od przyjętej definicji „wartości ostatecznej”.
- Ostatnia edycja nie jest automatycznie ostatecznym wynikiem rynkowym ani niezależnie poświadczoną informacją dostępną w przeszłości.

W obu narzędziach walidowane jest pochodzenie par z faktycznie odtworzonych `source_editions`: `issue`, oficjalny `release_day`, horyzont, miesiąc, źródłowa prognoza, ten sam miesiąc baseline oraz referencja; odrzucane są duplikaty `(instrument,horyzont,target)`, sprzeczne błędy bezwzględne oraz fałszywe twierdzenia o historycznej certyfikacji.

## Status dowodów i ograniczenia

Weryfikacja offline metod na syntetycznych danych odbywa się przez `tests/test_steo_robustness_audit.py`; wyniki rzeczywiste obliczymy w jednorazowej sondzie GitHub Actions na tych samych **34 oficjalnych historycznych XLSX** i osobno udokumentujemy po zakończeniu. Zero danych klientów, sekretów, podłączania do Neon, zleceń, dysków wynikowych i harmonogramów. Nie twierdzić, że istnieje przewaga prognostyczna, zysk/stopa zwrotu ani możliwość inwestowania w referencyjny cenowy szereg WTI/Brent.

**Uwaga o definicji jednostek:** obserwacje historyczne WTI/Brent z STEO to miesięczna referencyjna cena spot USD za baryłkę. To nie instrument „total return” denominowany w PLN, a model naukowy nie jest poradą lub zleceniem transakcyjnym. M1–M3 `HOLD_NO_CHANGE`.

**Dane wejściowe do kompletnej kontroli historycznej:** <https://www.eia.gov/outlooks/steo/outlook.php>, [potwierdzony rejestr 34 pobrań i SHA](STEO_FULL_34_REAL_RESULTS_2026_10_20_PL.md).
