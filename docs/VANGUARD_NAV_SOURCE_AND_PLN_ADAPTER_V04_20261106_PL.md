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
- Ściśle obsługiwany kandydacki format CSV: date,nav_usd. **XLSX nie jest uznany za obsługiwany** do czasu analizy realnego pliku Vanguard. Testy nie twierdzą, że oficjalny eksport ma ten format.
- Dla każdej daty NAV wymagany jest kurs NBP USDPLN z **identycznej daty** i udowodnionego źródła. Bez interpolacji, forward fill i przeliczania późniejszym kursem.
- Output: VANGUARD_ACC_NAV_REFERENCE_PLN, NON_EXECUTABLE_NAV_REFERENCE, no historical PIT certification, real_backtest=NOT_RUN. Nie należy mapować wyniku automatycznie na GLOBAL_EQUITY_TR_PLN ani na wykonywalne kwotowanie ETF.

## Sprawdzony stan akceptacji

- [Regresja #42259654282](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42259654282): **117/117 PASS**. Nowe testy: zgodne bajty i ceny, hash tamper, zła waluta/basis, brak kursu w dokładnej dacie, błędne źródło, brak miesiąca, niewspierany format XLSX.
- [Real-source NBP+TBSP #42255251036](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42255251036): 60/60 historycznych miesięcy, pięć rozbieżności dat naprawionych wyłącznie 10 rzeczywistymi zapytaniami NBP.
- Brak pełnego potwierdzonego NAV; brak realnych, kompletnych wyników backtestu. Żadne wirtualne fill-e ani realne operacje finansowe nie zostały uruchomione.
- Główne Neon LAB, scheduler v0.3, fundusze i portfele pozostają bez zmian. Projekt nie ma produkcji.

## Kolejny krok

Uzyskać pełny plik NAV zwykłą oficjalną ścieżką, przeanalizować jego prawdziwy format i dopiero wtedy zatwierdzić parser XLSX/CSV oraz daty historycznej dostępności. Nie domniemywać, że NAV jest ceną zlecenia; nie oznaczać źródła jako kompletnego tylko dlatego, że strona internetowa pokazuje bieżące 10 notowań.