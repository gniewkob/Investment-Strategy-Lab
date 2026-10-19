# EIA — walidacja wyłącznie do odczytu (PL)

**Status:** edukacyjny komponent kontroli pochodzenia danych rynkowych. Bez połączenia z Neon, SQL, portfelem czy giełdą. Bez możliwości importu lub modyfikacji danych.

## Źródło kodu

Parser źródeł w ścieżce src/isl_v2/eia_sources.py i jego testy w tests/test_eia_sources.py zostały wydzielone z [Draft PR #1](https://github.com/gniewkob/Investment-Strategy-Lab/pull/1). Parser wykorzystuje oryginalną stronę HTML EIA, wymaga jednej daty publikacji strony Release Date, prawidłowego kalendarza poniedziałek–piątek, pięciu cen w tygodniu, poprawnych wartości i liczy SHA-256 **faktycznie pobranych bajtów HTML**.

Nowy skrypt scripts/eia_readonly_audit.py:
- Czyta oficjalne, dopuszczone adresy HTTPS EIA dla Brent, WTI, Henry Hub; zabrania przekierowań poza dokładny URL, limit 8 MB, wymaga Content-Type text/html.
- Zwraca agregaty: źródło, hash, czas pobrania, dzień bieżącego wydania, daty skrajne i liczbę rekordów, **bez surowych cen**.
- Opcjonalnie porównuje z lokalnym plikiem CSV zawierającym **tylko** trzy pola: instrument_code, observed_for, close_price. Instrument musi odpowiadać źródłu; data to ISO YYYY-MM-DD; wartości muszą być dodatnie, skończone i niepowtarzalne. Porównanie używa dokładnego Decimal.
- Porównuje wyłącznie wspólne okno źródła; osobno liczy obserwacje referencyjne poza oknem. Zwraca tylko daty niezgodności, nie ceny. Nie publikuje ani nie przenosi lokalnego CSV do GitHub.

## Przykładowe uruchomienie (bez bazy i bez zapisu)

    python -m scripts.eia_readonly_audit --source wti
    python -m scripts.eia_readonly_audit --source brent
    python -m scripts.eia_readonly_audit --source henry_hub

Domyślny zakres to ostatnie 420 dni. Szerokie retrospektywne porównanie archiwum jest osobnym, **nie point-in-time** eksperymentem, np.:

    python -m scripts.eia_readonly_audit --source wti --max-age-days 1100

Jeżeli operator ma uprzednio autoryzowany i zweryfikowany **lokalny** wyciąg publicznych cen referencyjnych (bez pozycji prywatnych, kont i portfeli), może wykonać:

    python -m scripts.eia_readonly_audit --source wti --max-age-days 1100 --reference-csv /bezpieczna/sciezka/wti_reference.csv

Wymagany nagłówek pliku: instrument_code,observed_for,close_price. Plik pozostaje lokalny. Nie kopiuj go do publicznego repo lub artifacts.

## Testy i GitHub Actions

    python -m unittest discover -s tests -p 'test_eia*.py' -v

Workflow .github/workflows/eia-readonly-validation.yml uruchamia syntetyczne testy na PR i main. Pobranie danych z oficjalnych publicznych stron EIA jest dostępne **tylko ręcznie**, przez workflow_dispatch (brak schedule). Żaden krok nie korzysta z sekretów GitHub ani połączenia do Neon i niczego nie zapisuje w bazie.

## Ustalenia historyczne, czego walidator NIE dowodzi

[Pełny audyt EIA vs Neon STAGING 19.10.2026](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6270375923): zakres 02.01.2024–14.10.2026. WTI 695 oficjalnych dat i cen, 660 zgodnych z Neon, brak 35 końcowych dat (26.08–14.10.2026), 0 niezgodnych zapisanych cen. Brent 706/706 dokładnych dopasowań. Nie oznacza to znajomości pierwotnych historycznych dat publikacji danych.

W szczególności data rynkowa observed_for to NIE dowód, że cenę faktycznie można było wtedy poznać. Obecna strona EIA jest późniejszym snapshotem; hash jej dzisiejszej reprezentacji nie jest hashem starych publikacji. Nadal obowiązuje source_vintage=UNVERIFIED_HISTORICAL_PUBLICATION. Nie antydatuj publication/retrieval/recorded timestampów.

Ten PR NIE wprowadza uzupełnienia 35 brakujących cen WTI, SQL INSERT/UPDATE, migracji, zmiany Neon ACL, sekretów, harmonogramu, autohandlu ani alokacji. Osobno pozostają [Issue #21](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21) (pełna historia anomalii BTC/ETH) oraz [Issue #23](https://github.com/gniewkob/Investment-Strategy-Lab/issues/23) (syntetyczne fixture vs real PIT). Wirtualne M1/M2/M3 bez zmian: HOLD_NO_CHANGE.
