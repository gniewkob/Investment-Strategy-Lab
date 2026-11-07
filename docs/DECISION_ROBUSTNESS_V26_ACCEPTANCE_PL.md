# ISL v0.26 — M1–M3: testy odporności sygnałów przy zamrożonej polityce

**Cel:** rozwijać sprawdzalność logiki decyzji niezależnie od oczekiwania na kompletny oryginalny eksport listopada 2026. Wersje v0.20–v0.25 pozostają niezmienione; pierwszy okres prospective Vanguard/NBP to nadal listopad 2026, bez dostępnej obserwacji forward.

## Działający komponent

`scripts/research_decision_robustness_v26.py` nie implementuje nowej strategii ani nie optymalizuje parametrów. Wykorzystuje istniejący `research_decision_controller_v15.decide` i weryfikuje jego decyzje w **jawnych syntetycznych scenariuszach**. Wejście to JSON `{"mode":"SYNTHETIC_DECISION_RESILIENCE_RESEARCH_ONLY","scenarios":[...]}`; każdy scenariusz wymaga unikalnej nazwy, `current`, `previous` (lub null) i dokładnej mapy oczekiwanych statusów M1, M2, M3. Pierwszy przypadek musi mieć nazwę `BASELINE`. Błędy kontraktu i niezgodność wyniku ze spodziewanym statusie kończą test wyjątkiem, bez milczącej zmiany reguł.

Oceniane przypadki syntetyczne w CI:

1. **BASELINE:** komplet trzech serii TR (zadeklarowanych wyłącznie w fixture) i dwa zgodne kolejne miesiące, M1/M2/M3 jako `PAPER_CANDIDATE_ONLY` w świecie fikcyjnego źródła.
2. **MISSING_EQUITY:** brak serii globalnych akcji → `HOLD_CASH` dla wszystkich.
3. **UNVERIFIED_GOLD:** złoto bez potwierdzonych praw → M1 pozostaje wyłącznie syntetycznym kandydatem, M2/M3 wstrzymane.
4. **RISK_OFF_TRANSITION:** zmiana znaku momentum w ostatnim miesiącu → M3 ma `HOLD_CASH` do kolejnego potwierdzenia.
5. **HISTORICAL_REVISION:** skorygowana historyczna wartość akcji → M3 nie przyjmuje niezmienionej historii i pozostaje wstrzymany.

Raport zawiera podsumowanie liczby `HOLD_CASH`, `PAPER_CANDIDATE_ONLY` i zmian hipotetycznego targetu względem baseline, skróty wejść/scenariuszy oraz `research_receipt_sha256`. Nie drukuje surowych poziomów cen. Kontroler nadal wymaga oryginalnych źródeł, return basis TOTAL_RETURN i odpowiednich dat; **testy syntetyczne nie stanowią niezależnej atestacji licencji, PIT ani kwalifikacji do produkcji**.

## Uruchomienie

Po przetestowaniu kodu można uruchomić testy na dowolnym izolowanym worktree:

```bash
python3 -m unittest discover -s tests -p 'test_research_decision_robustness_v26.py' -v
```

Program przyjmuje także plik JSON `--suite /path/to/synthetic-suite.json`, ale nie ma wbudowanego połączenia z prywatnym eksportem NAV. Nie wolno używać tego eksperymentu jako furtki do przekwalifikowania Vanguard NAV (nie jest oficjalnym benchmarkiem globalnych akcji TOTAL_RETURN w PLN). Nie łączy się z brokerem, portfelem, Neon ani z siecią.

**Odbiór:** CI musi przejść testy deterministyczności, oczekiwanych statusów i fail-closed przy rewizji, brakujących danych, przesunięciu dat i próbie zmiany trybu na `LIVE_TRADING`. Wygenerowane liczby są **liczebnością decyzji na scenariuszach syntetycznych**, a nie skutecznością na rynku.

## Kolejny etap

Nie przeprowadzać nieograniczonej optymalizacji wag na danych już znanych (data snooping). Utrzymywać zamrożoną politykę M1–M3, rozwijać szczególnie pokrycie scenariuszy przeciwnych i wspólną ewidencję zamrożonych decyzji. W badaniu Vanguard forward bez nowego eksportu pozostaje `PENDING`, a kwalifikacja źródeł M1 w rzeczywistym kontrolerze pozostaje `HOLD_CASH`.
