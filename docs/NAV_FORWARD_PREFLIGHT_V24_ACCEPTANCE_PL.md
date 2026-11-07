# ISL v0.24 — offline forward-source preflight i audyt rewizji

**Stan na 2026-11-07:** listopad nie jest zamknięty; bez nowego oryginalnego eksportu status musi pozostać `PENDING_NEXT_COMPLETE_MONTH_OR_NEW_ORIGINAL_EXPORT`. Nie wolno generować listopadowego NAV, kursu NBP ani wyników OOS.

## Co rzeczywiście wykonuje v0.24

`scripts/nav_forward_preflight_v24.py` to read-only audyt dwóch prywatnych plików: manifestu v0.22 i bazowego raportu v0.4. Nie przegląda strony Vanguard, nie potwierdza licencji, nie pobiera lub nie modyfikuje danych w sieci i nie planuje cyklicznych uruchomień. Ponownie weryfikuje hash i spójność wszystkich 60 historycznych miesięcy oraz opublikowaną kotwicę GitHub SHA `3b8aca44ffa6aa72bf2d3a0b5d49102f0dd857d11191dc10e7d21b5051e704a2`.

Po 2026-11-30 można **opcjonalnie** podać nowy, legalnie i ręcznie uzyskany oryginalny XLSX Vanguard, zarchiwizowany oryginalny JSON odpowiedzi z oficjalnego NBP Table A USD dla dnia ostatniego poprawnego NAV i faktyczne czasy ich pozyskania. Skrypt:
- odrzuca niepełny miesiąc i późniejsze dane użyte przed publikacją;
- analizuje nowy XLSX za 61 miesięcy 2021-11..2026-11 i zestawia identyczne historyczne 60 miesięcy z bazowym raportem;
- zgłasza rewizje dat albo kwot NAV w historii; w razie wykrycia daje `BLOCKED_HISTORICAL_SOURCE_REVISIONS_REQUIRE_REVIEW` bez automatycznego akceptowania nowego źródła;
- w przypadku niezmienionej historii weryfikuje nowy listopadowy NAV USD × NBP USDPLN z dokładnego dnia; stosuje reguły v0.23 do sprawdzenia czasu pozyskania oraz zgodności z zamrożonym protokołem;
- wypisuje tylko status, liczbę zmienionych miesięcy, identyfikatory SHA, daty i niewrażliwe metadane; nie wypisuje surowej historii cen ani oryginalnego JSON NBP.

**Wynik po poprawnym, świeżym źródle nadal wymaga odrębnej weryfikacji:** `CANDIDATE_FORWARD_REFERENCE_REQUIRES_INDEPENDENT_SOURCE_REVIEW`, `prospective_eligible_months=0`, `qualified_m1_model_backtest=false`. Niezmieniony stary XLSX nie kwalifikuje się jako nowa obserwacja.

## Bezpieczna kontrola bieżącego stanu Mac mini

```bash
python3 -m scripts.nav_forward_preflight_v24 \
  --freeze "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/forward-freeze-v22-20261107.json" \
  --baseline "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/v04-20261107T194932Z/vanguard-nav-pln-candidate.json"
```

Bieżący test nie wymaga oryginalnego XLSX, internetu ani uruchamiania kontroli cyklicznej.

## Ograniczenia

Nie jest to autonomiczny agent do pobierania Vanguard (może istnieć interaktywny warunek licencji/akceptacji na stronie, którego nie należy automatycznie omijać). Kontrolowane pozyskanie nowych bajtów źródła i odpowiedzi NBP jest osobnym etapem po zamknięciu miesiąca. Weryfikacja rzeczywistych oryginalnych bajtów dostępnych po czasie zamrożenia nie oznacza jeszcze niezależnej atestacji prawa użycia, chwili publikacji, ceny ETF ani wykonalnego wyniku.

M1 pozostaje `HOLD_CASH`, brak transakcji, połączenia z portfelem, nowych zapisów do Neon, harmonogramu lub automatycznej zmiany parametrów strategii.

Dalszy odbiór: syntetyczne testy CI plus faktyczna kontrola stanu `PENDING` na prywatnych plikach Mac. Nie zamieniać wyniku oczekiwania w brak danych historycznych ani zysk forward.
