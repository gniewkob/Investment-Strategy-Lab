# ISL v0.20 — warunkowa analiza M1, rzeczywisty Vanguard NAV/PLN kontra gotówka

**Cel:** uzyskać pierwsze liczbowe, odtwarzalne wyniki referencyjne z rzeczywiście pozyskanego NAV/PLN, bez sugerowania ich wykonalności na rachunku inwestycyjnym. Analiza to wyłącznie edukacyjna symulacja 100 PLN miesięcznie.

## Wejście i integralność

Źródłem jest prywatny raport v0.4 `vanguard-nav-pln-candidate.json`, uprzednio wyliczony z oryginalnego Vanguard FTSE All-World UCITS ETF USD Accumulating XLSX oraz tabeli A NBP USDPLN z *identycznej daty*. Na Mac mini użytkownik potwierdził:
- status `CANDIDATE_NAV_PLN_REFERENCE_READY_FOR_SOURCE_REVIEW`;
- 60/60 kolejnych miesięcy 2021-11..2026-10;
- `missing_exact_day_fx=[]`, `official_extra_fx_reads=1`;
- `evidence_sha256=541518959c1be70cc8d497ba4780a31ad7a6a8f61dbb37a8b2b8286d7cee423c`.

Skrypt `scripts/conditional_m1_nav_diagnostic_v20.py` sprawdza hash całego raportu wejściowego, 60 miesięcy, chronologię, dokładną równość NAV USD × NBP USDPLN = NAV PLN, wymagane hash źródłowe NBP, brak brakujących dat, dodatnie poziomy oraz niekwalifikowany status źródła. Gdy dokument zmieniono, import jest odrzucany zamiast milczącego uzupełniania.

## Algorytm

- Konkurencyjne warianty *tego samego*, alternatywnego budżetu: `CASH_PLN` (wpłata 100 PLN miesięcznie, zero oprocentowania) oraz `VANGUARD_ACC_NAV_REFERENCE_PLN` (teoretyczne ułamkowe jednostki po miesięcznej referencji NAV).
- W obu wariantach 60 wpłat po 100 PLN; w wariancie NAV po każdym miesięcznym poziomie dodawane są teoretyczne jednostki za 100 PLN pomniejszone o koszt według *hipotetycznej* stopy prowizji i poślizgu, standardowo `fee_bps=20` i `slippage_bps=10`. Są to arbitralne założenia, nie historyczne koszty brokera.
- Zwraca końcową wartość referencyjną brutto, netto, łączną kwotę wpłat, hipotetyczne koszty oraz różnicę względem gotówki. Opcjonalna seria `timeline` w funkcji Python jest lokalna; CLI wypisuje **wyłącznie zagregowane liczby**, bez oryginalnej historii poziomów NAV, kursów walut ani tabeli transakcji.
- Ważne: w uproszczeniu teoretyczne jednostki są wyceniane i nabywane po zamkniętym miesięcznym NAV. W realnym świecie historyczny NAV nie był z góry znany i nie jest gwarantowaną ceną, po której można dokonać zlecenia. **Nie używać tej serii do udawania prognozy OOS ani zysku inwestora.**
- Model M1 w ścisłym kontrolerze v0.15 pozostaje **HOLD_CASH** — wynik diagnostyczny v0.20 nie spełnia kwalifikacji `GLOBAL_EQUITY_TR_PLN`.

## Uruchomienie na Mac mini (prywatne wejście)

W aktualnym, przetestowanym checkoutcie wersji v0.20:

```bash
python3 -m scripts.conditional_m1_nav_diagnostic_v20 \
  --nav-receipt "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/v04-20261107T194932Z/vanguard-nav-pln-candidate.json" \
  --fee-bps 20 --slippage-bps 10
```

Nie podawać surowej historii NAV ani prywatnego raportu jako publicznego załącznika do GitHub. Wystarczy linia `ISL_CONDITIONAL_M1_NAV_V20=...` zawierająca agregaty oraz odciski SHA. Moduł nie odczytuje kont, nie wysyła zleceń, nie zapisuje do Neon.

## Odbiór

**TECHNICAL PASS**: pozytywne testy na syntetycznych danych w CI oraz prawidłowy przebieg na wcześniej zweryfikowanym prywatnym raporcie. **RESEARCH RESULT OBSERVED** dopiero po rzeczywistym uruchomieniu modułu na Mac mini. Niezależny audyt praw do danych, punktu dostępności PIT, tożsamości dostawcy i instrumentu oraz rzeczywistej wykonalności nie został zakończony, więc **REAL INVESTABLE M1 / OOS ACCEPTANCE pozostaje BLOCKED**. W szczególności symulowana przewaga albo strata wobec gotówki nie dowodzi alpha ani rentowności przyszłych inwestycji.
