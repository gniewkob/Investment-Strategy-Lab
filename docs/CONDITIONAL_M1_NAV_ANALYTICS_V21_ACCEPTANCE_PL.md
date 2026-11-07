# ISL v0.21 — M1 Vanguard/NBP: XIRR, koszty i maksymalne obsunięcie referencji

**Data:** 2026-11-07. **Status przed lokalnym odczytem:** algorytm/testy CI do odbioru, prawdziwy wynik XIRR/drawdown **NOT_RUN** do wykonania na prywatnym raporcie v0.4.

## Cel i źródło

Wersja v0.20 została faktycznie uruchomiona na oryginalnym eksporcie historycznego NAV Vanguard FTSE All-World UCITS ETF USD Accumulating przeliczonym po oficjalnym kursie NBP USD/PLN z tych samych dat, 60 miesięcy 2021-11–2026-10. Raport źródłowy SHA `541518959c1be70cc8d497ba4780a31ad7a6a8f61dbb37a8b2b8286d7cee423c` pozostaje lokalny. Referencyjna wartość końcowa v0.20: 8 566,58 PLN w scenariuszu 20 bps/10 bps, 6 000 PLN alternatywnej nieoprocentowanej gotówki. **Nie jest to inwestycyjny zysk ani realna ścieżka zleceń.**

Nowy skrypt `scripts/conditional_m1_nav_analytics_v21.py` używa identycznego, *niezmienionego* prywatnego raportu. Wywołuje istniejący walidator i algorytm v0.20 dla każdego kosztowego wariantu. Żadnych dodatkowych źródeł ani syntetycznych cen w wyniku rzeczywistego lokalnego uruchomienia.

## Metryki

1. **XIRR / money-weighted rate:** 60 ujemnych hipotetycznych przepływów po 100 PLN dokładnie w datach referencyjnego NAV oraz jedna dodatnia hipotetyczna likwidacja w dniu ostatniego NAV. Konwencja `ACT/365.25`, rozwiązanie NPV=0 metodą bisekcji. XIRR gotówki z identycznymi terminami wynosi 0%; **XIRR nie jest TWR**. Nie używać rocznej XIRR jako dowodu alpha ani dostępnego wyniku transakcji, ponieważ data publikacji NAV może być późniejsza niż data referencji.
2. **Maksymalne miesięczne obsunięcie referencji:** wyznaczane z kolejnych poziomów `nav_pln_reference` jako minimum `P_t / max_{s<=t} P_s - 1`, początek serii to pierwszy poziom z 2021-11. Obsunięcie nie jest obsunięciem wartości portfela z wpłatami, nie reprezentuje dziennego ryzyka ani możliwych cen giełdowych.
3. **Cztery stałe scenariusze prowizja/slippage:** 0/0, 20/10, 50/50, 100/100 punktów bazowych naliczane do każdej z 60 hipotetycznych wpłat po 100 PLN. Koszty są założeniem analitycznym, a nie zebranymi opłatami brokera. Wartości netto oraz XIRR muszą być monotoniczne wraz ze wzrostem kosztów dla tego samego datasetu.

Każdy wariant posiada odcisk SHA wyniku v0.20; cały raport generuje osobny `analytics_receipt_sha256`. CLI wypisuje wyłącznie metryki zagregowane, **bez publikowania miesięcznych lub dziennych poziomów NAV i NBP**.

## Uruchomienie na rzeczywistym raporcie Mac mini

Na odpowiednim commicie repo:

```bash
python3 -m scripts.conditional_m1_nav_analytics_v21 \
  --nav-receipt "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/v04-20261107T194932Z/vanguard-nav-pln-candidate.json"
```

Po wykonaniu zachować i porównać `source_evidence_sha256` z uprzednio potwierdzonym hashem. Do PR wrzucić jedynie zagregowaną linię `ISL_CONDITIONAL_M1_ANALYTICS_V21=` oraz właściwy commit i stan CI.

## Granice kwalifikacji

To **CONDITIONAL_NAV_ANALYTICS_RESEARCH_ONLY**. Teoretyczne ułamkowe jednostki NAV zostały w uproszczeniu nabyte po miesięcznej cenie referencyjnej, choć cena nie musiała być dostępna do rzeczywistego wykonania zlecenia w tym momencie. `historical_point_in_time_certified=false`, `executable_fills_verified=false`, `source_rights_independently_certified=false`, `qualified_m1_model_backtest=false`, `prospective_oos_performance_proven=false`. Żadnej zmiany w zatwierdzonych regułach wejścia M1–M3, żadnego handlu, transferów, portfeli, Neona, harmonogramów.

**Acceptance:** wynik analityczny jest odtwarzalnym porównaniem badawczym, ale pełny odbiór wykonania oraz przyszłej walidacji OOS nadal BLOCKED. Kontynuować naturalne prospektywne badanie, nie optymalizować parametrów na historycznej próbce.
