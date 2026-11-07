# ISL v0.27 — ocena jakości sygnałów na scenariuszach syntetycznych

## Cel i granice

Celem jest ilościowa ocena **zachowania już zamrożonego kontrolera M1–M3**, a nie estymacja skuteczności strategii rynkowej. Implementacja w `scripts/research_decision_quality_v27.py` korzysta wyłącznie z v0.26, które odtwarza oryginalny kontroler v0.15 na zestawie syntetycznych manifestów. Wszystkie pięć scenariuszy v0.26 zachowuje charakter **fikcyjnych danych referencyjnych**. Nie wykorzystuje nowych notowań, sald portfela ani prawdziwych przyszłych zwrotów.

## Reguły oceny

Każdy scenariusz ma jawnie wpisaną **syntetyczną etykietę reżimu** `RISK_ON` albo `RISK_OFF`. To test fixture / expected test outcome, **nie prawda historyczna ani wynik wykryty na rynku**.

Dla M3 wyliczamy dwuklasową macierz pomyłek wyłącznie wtedy, gdy kontroler dopuścił `PAPER_CANDIDATE_ONLY`. Jeżeli kontroler zwrócił `HOLD_CASH`, zapisujemy **abstencję**, nie automatyczny błąd kierunku. Takie rozdzielenie jest ważne: 100% trafności na jednym ze stu potencjalnych sygnałów nie mówi nic o 99 przypadkach, gdy system się wstrzymał.

Miary: liczba scenariuszy, wyemitowanych wskazań kierunku i abstencji; udział wskazań w scenariuszach (coverage), liczba trafnych i nietrafnych wskazań w scenariuszach; macierz `synthetic_truth × synthetic_prediction`; powody wstrzymań; liczba zmian **targetu** M3 względem scenariusza BASELINE. Ostatnia miara nie jest historyczną częstotliwością zmiany reżimu ani obrotem portfela — scenariusze to niezależne perturbacje, a nie chronologiczne miesiące.

## Wstępne warunki akceptacji badań syntetycznych

Ustalona w kodzie reguła `POLICY` (własne kryteria laboratoryjne, nie wymagania normy):

- Minimum 5 scenariuszy, w tym obowiązkowe BASELINE.
- Kierunkowe coverage co najmniej 20% scenariuszy.
- Brak błędnych kierunkowych wskazań w bazowym zestawie testowym.
- Wymagana abstencja M3 w scenariuszach `MISSING_EQUITY`, `HISTORICAL_REVISION`, `RISK_OFF_TRANSITION`.

Niespełnienie warunków daje jawne `SYNTHETIC_ACCEPTANCE_CHECKS_FAIL`; nie jest to potwierdzenie strat na rynku ani argument za automatyczną optymalizacją wag. Wymagania mają zapewnić ochronę przed regresją programu, a nie udowodnić przewagę inwestycyjną.

## Przykład oczekiwanego wyniku z istniejących syntetycznych danych CI

5 scenariuszy, 1 wskazanie kierunku M3 (BASELINE `RISK_ON`), 4 abstencje, coverage 20%; 1/1 poprawne wskazanie względem zadeklarowanej etykiety fixture. Przy odwróceniu etykiety BASELINE test wymaga błędu i statusu FAIL. Nie raportować 100% jako trafności na rynku ani próbki wystarczającej do wnioskowania statystycznego.

## Testy, deterministyczność i bezpieczeństwo

```bash
python3 -m unittest discover -s tests -p 'test_research_decision_quality_v27.py' -v
```

CLI: `python3 -m scripts.research_decision_quality_v27 --suite <private-synthetic-fixture.json>`, bez sieci. Wymagana jest jawna struktura `{"mode":"SYNTHETIC_DECISION_QUALITY_RESEARCH_ONLY","robustness_suite":<v0.26 suite>,"truth":{"BASELINE":"RISK_ON",...}}`.

Blokady wejścia: nieznane/pominięte etykiety, niezgodność oczekiwanego statusu M1–M3, zmiana na tryb LIVE_TRADING, look-ahead, dodatkowe pola. Niezmienność oryginalnych manifestów kontrolera i SHA-256 raportu. Brak zapisu DB/Neon, brokerów, portfela, uruchamiania schedulerów, zleceń lub paper fills.

**Status realnego przedsięwzięcia:** żaden oryginalny kwalifikowany `GLOBAL_EQUITY_TR_PLN` nie został zintegrowany z kontrolerem; model M1–M3 dla rzeczywistych źródeł pozostaje `HOLD_CASH`. Eksperyment Vanguard/NBP v0.22–v0.25 czeka na nowy eksport po listopadzie 2026, wciąż `PENDING`. Nie ma prospektywnego potwierdzenia skuteczności, praw do źródła, first available PIT ani wykonalnych cen rynku.

## Następne racjonalne kroki

Nie należy optymalizować progów momentum po obserwowaniu wyników testowych. Można rozszerzyć **niezależny, z góry zadeklarowany** zestaw perturbacji i testować chronologiczny, zamrożony dziennik decyzji, gdy dostępne będą prawdziwe, datowane obserwacje. Dopiero wtedy analizować frequency/reversal, błędy i wiarygodność z rozdzieleniem rynku od sztucznych fixture.
