# ISL v0.22 — zamrożenie przyszłego eksperymentu Vanguard NAV/PLN

## Cel

Rozdzielić **już znaną historię** (Vanguard USD accumulating NAV + dokładne kursy NBP USD/PLN, 60 miesięcy 2021-11..2026-10) od późniejszych obserwacji. Pierwszy planowany okres forward to **2026-11**, którego miesięczna obserwacja w dniu 2026-11-07 jeszcze nie istnieje.

## Kontrakt i metodologia

`scripts/nav_forward_freeze_v22.py` przeprowadza ponowną pełną walidację istniejącego prywatnego raportu v0.4 poprzez sprawdzony v0.21 i v0.20. Następnie atomowo tworzy *nowy* lokalny manifest JSON i nie nadpisuje istniejącego pliku. Protokół zawiera datę utworzenia UTC, identyfikatory SHA oryginalnego eksportu, źródłowego raportu i historycznej analizy v0.21, oraz niezmienny zestaw metod: hipotetyczne 100 PLN miesięcznie, 20 bps prowizji + 10 bps poślizgu w wariancie bazowym, zero-interest PLN cash comparator, ostatni poprawny miesięczny Vanguard NAV + oficjalny NBP USDPLN z identycznej daty.

Warunek rozpoczęcia: **czas rzeczywistego zamrożenia w listopadzie 2026**, po zakończonym październiku i przed zakończeniem listopada. Zamrożony dokument ma `first_forward_month=2026-11`, `forward_qualified_months=0`, `forward_observations=[]`, status `FROZEN_PENDING_FIRST_FUTURE_MONTH`. Niezależny walidator `verify_pending` odrzuca zmianę skrótów SHA, parametrów, wyprzedzanie zegara, rezygnację z HOLD/qualified=false i próby dopisania fikcyjnego wyniku forward.

Ważne: SHA samego pliku i zawarta w nim deklaracja czasu **nie stanowią zewnętrznie poświadczonej daty publikacji**. Niezależna kotwica, np. dopisanie skrótu lokalnego manifestu do GitHub issue w chwili jego utworzenia, byłaby dodatkowym dowodem kolejności, ale nie dowodzi dostępności wczesnych notowań ani uprawnień licencyjnych. W obecnej wersji `independent_time_anchor_verified=false`.

## Uruchomienie na lokalnym Mac mini

```bash
python3 -m scripts.nav_forward_freeze_v22 \
  --nav-receipt "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/v04-20261107T194932Z/vanguard-nav-pln-candidate.json" \
  --out "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/forward-freeze-v22-20261107.json"
```

Uruchomić z zatwierdzonego SHA kodu v0.22. Polecenie nie wykonuje zleceń ani transferów, nie wywołuje sieci, nie zapisuje do repo ani Neon, nie zastępuje prywatnego raportu źródłowego. W terminalu pojawi się `ISL_NAV_FORWARD_FREEZE_V22` z `PENDING_NO_PROSPECTIVE_DATA` i skrótem `freeze_receipt_sha256`.

## Etap następny — jeszcze NIE wdrożony

Po zakończeniu listopada 2026 należy pozyskać **nowy, oryginalny eksport** NAV, nową obserwację miesięczną i oficjalny kurs NBP dokładnie w dniu NAV, następnie odnotować *rzeczywisty czas* otrzymania/publikacji nowego źródła. Oddzielny etap ma sprawdzić, że źródło powstało po zamrożeniu protokołu, że nie użyto listopadowego NAV w październikowej decyzji i że nie zrekonstruowano fikcyjnej skuteczności forward. Dopiero później wolno rozważyć kwalifikację *referencyjnego forward*, nigdy bez dowodu wykonania zlecenia NAV.

## Statusy

- Historyczny warunkowy eksperyment v0.21: PASS (wynik obliczeń z prywatnego pliku, nie performance transakcji).
- v0.22: **PENDING** — przed nadejściem późniejszego okresu nie ma liczbowego wyniku forward.
- Realny model M1 w silniku produkcyjnego kontrolera: **HOLD_CASH**, ponieważ `GLOBAL_EQUITY_TR_PLN`, oryginalna licencja, PIT i wykonalność nie są niezależnie potwierdzone.
- M2/M3: bez zmian.
- Operacje finansowe, konta, zapis DB, transfery: zero.

Każda interpretacja zysków, strat, rocznej XIRR lub obsunięć musi rozróżniać wyłącznie referencyjny NAV od wykonalnej ceny ETF.
