# Investment Strategy Lab v0.4 — oficjalne 60 miesięcy TBSP.Index

Data odbioru: 6 listopada 2026. **PASS — rzeczywisty zbiór benchmarku. NIE jest to cena wykonania transakcji ani poświadczony historyczny point-in-time.**

## Rzeczywisty odczyt

- Źródło: oficjalne archiwum BondSpot TBSP.Index — https://www.bondspot.pl/tbsp_index_archive_en
- GitHub Actions: https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42238752683 — SUCCESS.
- Zakres: listopad 2021–październik 2026, 60 kolejnych miesięcy, 60 datowanych zamknięć indeksu.
- Pierwszy rekord: 2021-11-29, 1872,28; oficjalny URL https://www.bondspot.pl/tbsp_index_archive_en?date=20211129&month=11&year=2021
- Ostatni rekord: 2026-10-30, 2230,71; oficjalny URL https://www.bondspot.pl/tbsp_index_archive_en?date=20261030&month=10&year=2026
- Ostatnią opublikowaną wartość miesiąca wyszukiwano w ciągu do ośmiu poprzednich dni; bez interpolacji lub syntetycznych wypełnień.
- Każdy rekord zawiera źródłowy HTTPS URL, observed_for, timestamp rzeczywistego pobrania w 2026 r., SHA-256 odpowiedzi, PLN oraz NON_TRADABLE_INDEX.
- Fingerprint kompletnego zbioru: **757dc284d64a472f6d759afa252c5a9b86726b66ac0af9b4137919f735d03d4d**.
- GitHub Actions artifact: bondspot-month-end-source-proof-v04, ID 13514960254; retencja do 20.11.2026.

## Niezależna kontrola pobranego archiwum

ZIP został odczytany niezależnie od logów CI. Zweryfikowano dokładnie 60 rekordów i 60 odrębnych miesięcy; wszystkie daty są zgodne z miesiącem, a wszystkie źródła wskazują oficjalne URL BondSpot. Wszystkie 60 hashy odpowiedzi mają format SHA-256. Kanonicznie przeliczony SHA-256 całego JSON (bez pola evidence_sha256) jest identyczny z zapisanym. Żadna transakcja ani zmiana portfela nie wystąpiła.

[Regresja CI po zmianach](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42239266130): **SUCCESS, 97/97 testów** (5+5+4+11+7+6+7+21+25+6).

## Vanguard — sprawdzony, ale niepobrany eksport

Oficjalna strona https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits pokazuje historyczne NAV (USD) i kontrolkę pobierania. [Test Chromium #42239266328](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42239266328) potwierdził stronę HTTP 200, ISIN IE00BK5BQT80 i przycisk eksportu. Sesja odrzuciła opcjonalne cookies standardowym przyciskiem, ale kolejny modal nadal zasłaniał kontrolkę. Rezultat: DOWNLOAD_CONTROL_DID_NOT_PRODUCE_FILE. Nie obchodzono modala ani nie potwierdzano niezweryfikowanego statusu inwestora.

## Interpretacja i ograniczenia

TBSP.Index jest publikowanym benchmarkiem dochodowym obligacji, ale nie pojedynczym instrumentem, który można kupić po indeksowej wartości zamknięcia. Ewidencja zachowuje BOND_TOTAL_RETURN_BENCHMARK_INDEX i NON_TRADABLE_INDEX. Historyczny rzeczywisty moment pierwotnej publikacji oraz oryginalny vintage pozostają niezależnie NIEPOTWIERDZONE: dzisiejsze pobranie dawnej historii nie dowodzi ówczesnej dostępności.

Nie dokonano mapowania na inwestowalny instrument PL_BONDS_TR_PLN, nie tworzono fikcyjnej wyceny ani wyników M1/M2/M3. NBP gold pozostaje PRICE_ONLY, a brakuje kompletnego oficjalnego szeregu NAV accumulating Vanguard oraz zasad dopasowania walut i kosztów.

**PASS:** oficjalne 60-miesięczne archiwum BondSpot, brak luk, pochodzenie i integralność.

**BLOCKED:** pełny trzyklasowy historyczny backtest v0.4 oraz pobranie 36+ miesięcy NAV z Vanguard.

**NEXT:** oficjalne NAV Vanguard dla inwestora indywidualnego lub autentyczny eksport, źródłowo wierne zestawienie NAV USD + NBP USDPLN, zachowanie oddzielnej serii indeksu BondSpot i rzeczywistego złota NBP, później ostrożna analiza benchmarków bez deklarowania wypełnień transakcji.

Neon LAB main i aktywny scheduler v0.3 pozostały bez zmian. Nie ma produkcji ani realnych operacji finansowych.
