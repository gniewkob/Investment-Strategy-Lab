# Vanguard NAV USD → PLN: protokół badawczy v0.4 (6.11.2026)

**PASS dla adaptera i testów; BLOCKED dla rzeczywistego pełnego eksportu NAV; NOT_RUN dla wyników M1/M2/M3.**

## Oficjalne źródła

- Vanguard FTSE All-World UCITS ETF, USD Accumulating, ISIN IE00BK5BQT80.
- Polska: https://www.pl.vanguard/inwestorzy-indywidualni/produkt/etf/akcje/9679/ftse-all-world-ucits-etf-usd-accumulating
- Szwajcaria, Private Investor: https://www.ch.vanguard/en/private-investor/product/fund/equity/9679/ftse-all-world-ucits-etf-usd-accumulating
- [Test obu stron #42258631757](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42258631757): strony publiczne i przyciski historii NAV widoczne; eksport bez pliku. Polska: zasłaniający modal NDS; Szwajcaria: OneTrust consent overlay. Bez force-click, zmian DOM, uwierzytelniania, fałszywego potwierdzania kategorii inwestora ani obchodzenia zabezpieczeń.

## Dostarczony moduł źródłowy

- scripts/vanguard_nav_to_pln_reference_v04.py — offline, bez sieci, bazy, kont i zleceń.
- tests/test_vanguard_nav_to_pln_reference_v04.py — 9 nowych testów syntetycznych.
- Wejście: deklaracja NAV Vanguard (konkretny ISIN, USD, accumulating NAV), **oryginalne bajty pliku**, ich SHA-256, jawna lista dat i wartości oraz źródłowe archiwum NBP USDPLN.
- Każdy deklarowany miesięczny NAV jest odtwarzany z oryginalnych bajtów; samo dołączenie zgodnego hasha nie certyfikuje wpisanych wartości.
- Ściśle obsługiwany kandydacki format CSV: date,nav_usd. **Podstawowy adapter NAV→PLN nadal nie akceptuje XLSX jako zweryfikowanego źródła.** Dostępny jest natomiast osobny, izolowany od bazy **moduł wstępnej inspekcji XLSX**, który wyłącznie klasyfikuje format i przygotowuje kandydackie dane do weryfikacji po rzeczywistym pobraniu. Testy nie twierdzą, że oficjalny eksport ma ten format.
- Dla każdej daty NAV wymagany jest kurs NBP USDPLN z **identycznej daty** i udowodnionego źródła. Bez interpolacji, forward fill i przeliczania późniejszym kursem.
- Output: VANGUARD_ACC_NAV_REFERENCE_PLN, NON_EXECUTABLE_NAV_REFERENCE, no historical PIT certification, real_backtest=NOT_RUN. Nie należy mapować wyniku automatycznie na GLOBAL_EQUITY_TR_PLN ani na wykonywalne kwotowanie ETF.

## Sprawdzony stan akceptacji

- [Regresja #42259654282](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42259654282): **117/117 PASS**. Nowe testy: zgodne bajty i ceny, hash tamper, zła waluta/basis, brak kursu w dokładnej dacie, błędne źródło, brak miesiąca, niewspierany format XLSX.
- [Real-source NBP+TBSP #42255251036](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42255251036): 60/60 historycznych miesięcy, pięć rozbieżności dat naprawionych wyłącznie 10 rzeczywistymi zapytaniami NBP.
- Brak pełnego potwierdzonego NAV; brak realnych, kompletnych wyników backtestu. Żadne wirtualne fill-e ani realne operacje finansowe nie zostały uruchomione.
- Główne Neon LAB, scheduler v0.3, fundusze i portfele pozostają bez zmian. Projekt nie ma produkcji.

## Kolejny krok

Uzyskać pełny plik NAV zwykłą oficjalną ścieżką, przeanalizować jego prawdziwy format i dopiero wtedy zatwierdzić parser XLSX/CSV oraz daty historycznej dostępności. Nie domniemywać, że NAV jest ceną zlecenia; nie oznaczać źródła jako kompletnego tylko dlatego, że strona internetowa pokazuje bieżące 10 notowań.

## Dodatkowy odbiór — legalny dostęp do eksportu i inspekcja XLSX

Polska publiczna strona Vanguard wymaga potwierdzenia kraju zamieszkania i akceptacji oświadczenia prawnego. Widoczne przyciski to „Nie wyrażam zgody” i „Wyrażam zgodę”. Nie jest to błąd algorytmu. Automatyzacja **nie może składać tego oświadczenia w imieniu użytkownika**. Udostępniony regionalnie serwis przeznaczony tylko dla inwestorów instytucjonalnych lub kwalifikowanych został wykluczony z automatycznych testów.

Nowy skrypt: `scripts/vanguard_xlsx_offline_intake_v04.py`; testy: `tests/test_vanguard_xlsx_offline_intake_v04.py`. Odczyt lokalny bez sieci, kont, Neona, papierowych transakcji i możliwości składania zleceń. Wykrywa jednoznaczne kolumny Date i NAV (USD), odrzuca podstawienie Market price, formuły i makra, rozpoznaje standardowe numery seryjne dat Excel, porównuje ciągłość 36–72 miesięcy, odrzuca duplikaty i zapisuje SHA-256 oryginalnych bajtów.

**To nie jest parser sprawdzony na oryginalnym pliku Vanguard.** Testy używają wyłącznie syntetycznych XLSX. Dla rzeczywistego pliku layout lub arkusz mogą być inne; wtedy skrypt musi zakończyć się błędem i wymagać adaptacji do danych źródłowych. Wynik ma status `RAW_NAV_XLSX_CANDIDATE_NEEDS_PROVIDER_IDENTITY_ATTESTATION`, nie certyfikuje ISIN, historycznego PIT ani ceny transakcyjnej, nie jest automatycznie mapowany na GLOBAL_EQUITY_TR_PLN.

Po zwykłym pobraniu historycznego pliku przez osobę uprawnioną do potwierdzenia wymaganych warunków strony lokalny odczyt można wykonać następująco:

```bash
python -m scripts.vanguard_xlsx_offline_intake_v04 \
  --file /sciezka/do/oryginalnego-eksportu.xlsx \
  --first-month 2021-11 --last-month 2026-10 \
  --out ./vanguard-nav-candidate.json
```

Nie należy przepisywać danych ręcznie, zmieniać dat, zgadywać brakujących wartości ani umieszczać prawnie ograniczonego oryginalnego pliku w publicznym repozytorium.

**Weryfikacja:** [CI #42261852878](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42261852878) SUCCESS **124/124**, w tym 7 nowych testów parsera XLSX. Oficjalny eksport nadal niepobrany. Backtest M1–M3 pozostaje `NOT_RUN`. Laboratorium Neon main i aktywna automatyzacja v0.3 pozostają bez zmian.

## Stabilizacja CI dla publicznych źródeł

Wieloletnie pobrania BondSpot i publiczne testy okien przeglądarki zostały ustawione na `workflow_dispatch` zamiast automatycznego powtarzania przy każdym commicie PR. Wcześniej pojedynczy test BondSpot zakończył się timeoutem TLS, pomimo prawidłowości utrwalonego i zweryfikowanego archiwum. Automatyczne testy offline silnika i parserów pozostają w `working-engine-v01-ci.yml`. Nie zmieniono harmonogramu działającego v0.3.
## Future-date XLSX acceptance — 2026-11-06

Do istniejącego parsera oryginalnego XLSX kandydackiego dodano osobny **no-look-ahead gate**: wymagany zakres miesięczny musi być zakończony względem bieżącej daty UTC, żaden wiersz NAV nie może pochodzić z przyszłości względem daty inspekcji, a daty wcześniejsze niż rozpoczęcie tej klasy jednostek (23.07.2019) są odrzucane. Testy z jawną datą referencyjną (`as_of`) kontrolują zarówno bieżący nieukończony miesiąc, jak i wiersz z przyszłości poza żądanym zakresem. Ten dodatkowy warunek nie certyfikuje legalności dostępu ani poprawności formatu niepobranego jeszcze oryginalnego eksportu.

Oficjalna strona dla inwestorów indywidualnych Vanguard UK:
https://www.vanguardinvestor.co.uk/investments/vanguard-ftse-all-world-ucits-etf-usd-accumulating/overview
opisuje wyniki jako oparte na NAV na koniec miesiąca oraz zaznacza, że NAV nie jest tym samym co cena kupna/sprzedaży ETF. Publicznie widoczne wyjaśnienie metodologii **nie stanowi jednak zweryfikowanego eksportu pełnej 36–60 miesięcznej historii**. Nie tworzono datasetu na podstawie wykresu albo danych z innego funduszu.

Podstawa kodowa: `scripts/vanguard_xlsx_offline_intake_v04.py` i `tests/test_vanguard_xlsx_offline_intake_v04.py`.

**Status NAV z realnego źródła pozostaje BLOCKED.** Główna baza Neon LAB, działający harmonogram v0.3 i portfele bez zmian.