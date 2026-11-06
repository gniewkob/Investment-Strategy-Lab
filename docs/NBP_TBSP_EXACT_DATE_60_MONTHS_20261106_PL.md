# Investment Strategy Lab v0.4 — wspólny kalendarz NBP / TBSP

**Odbiór: PASS dla źródłowej spójności dat. Backtest: NOT_RUN.**
Weryfikacja 6 listopada 2026. Prywatne laboratorium, bez produkcji.

## Rzeczywiste wejście

Dwa oficjalne zestawy referencyjne za 2021-11 do 2026-10:

- NBP (kursy średnie USD/PLN, EUR/PLN i cena złota PLN/g), 60 miesięcy, SHA-256: 58b22c10b7fab1fc09fbf07b1ff627cd8993e9df05b8ec8b308df31cd53b86b3.
- BondSpot TBSP.Index (benchmark dochodowy obligacji, nie instrument transakcyjny), 60 miesięcy, SHA-256: 757dc284d64a472f6d759afa252c5a9b86726b66ac0af9b4137919f735d03d4d.

Oficjalne źródła: https://api.nbp.pl/ oraz https://www.bondspot.pl/tbsp_index_archive_en

## Problem, wykrycie i poprawka

Pierwszy odczyt wykrył **55 miesięcy z identyczną datą notowania** oraz pięć różnych:

| Miesiąc | Ostatni TBSP | Ostatni NBP w pierwotnym archiwum |
|---|---|---|
| 2021-11 | 29.11.2021 | 30.11.2021 |
| 2021-12 | 30.12.2021 | 31.12.2021 |
| 2024-03 | 28.03.2024 | 29.03.2024 |
| 2024-12 | 30.12.2024 | 31.12.2024 |
| 2025-12 | 30.12.2025 | 31.12.2025 |

Nie wolno wykorzystywać kursu NBP z późniejszego dnia jako wyceny wcześniejszego zamknięcia TBSP. Zamiast tego moduł pobiera autentyczne kursy i cenę złota **z dokładnej daty zamknięcia BondSpot**, za pomocą oficjalnego NBP Web API: 5 dat × 2 zapytania (tabela A oraz złoto) = **10 żądań**. Po ich weryfikacji nowy zestaw ma **60/60 identycznych dat kalendarzowych**.

Żadna oryginalna obserwacja nie została nadpisana; nowe, dokładne daty mają własne URL i SHA-256 surowych odpowiedzi. Brak interpolacji, nearest-neighbor i syntetycznych notowań.

## Dowody i testy

- [GitHub Actions — real-source NBP/TBSP E2E #42255251036](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42255251036): 60/60 miesięcy, 5 nowych pobrań dziennych, 10 rzeczywistych odpowiedzi NBP, **11/11 testów offline**, zakończenie SUCCESS.
- SHA-256 nowego audytu z tego konkretnego przebiegu: d1868fa32704ffc1417d86a591efe27c825e7062ffb67e287f49e0fa0feaa6ca. Przy następnym pobraniu timestamp źródła będzie inny, więc zmieni się także ten fingerprint.
- [Pełna regresja Working Engine #42255573722](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42255573722): **108/108 PASS**.
- Kod: scripts/reference_archive_calendar_v04.py i scripts/nbp_bondspot_exact_date_v04.py.
- Testy: tests/test_reference_archive_calendar_v04.py.
- Źródłowy workflow (wyłącznie badawczy): .github/workflows/v04-nbp-bondspot-calendar-e2e.yml.

## Granice interpretacji

Zgodna **data kalendarzowa** nie certyfikuje historycznej godziny pierwszej publikacji, vintage ani możliwości wykonania zlecenia po wskazanej wartości indeksu. TBSP.Index pozostaje **NON_TRADABLE_INDEX**; złoto NBP pozostaje **PRICE_ONLY**, waluty NBP **FX_RATE**. Nie są to trzy inwestowalne serie PLN total return. Status symulacji M1–M3 nadal **NOT_RUN**.

## Vanguard — dokładny stan blokady

Oficjalna strona dla inwestorów indywidualnych:
https://www.pl.vanguard/inwestorzy-indywidualni/produkt/etf/akcje/9679/ftse-all-world-ucits-etf-usd-accumulating

Publiczna tabela NAV (USD) i kontrolka eksportu historii dla ISIN IE00BK5BQT80 są dostępne. W Playwright normalne kliknięcie przycisku pobierania zostało jednak zatrzymane przez widoczny modal NDS. **Nie uzyskano pliku 36+ miesięcy NAV**. Nie zastosowano force-click, manipulacji DOM, niedozwolonego ominięcia potwierdzeń ani logowania.

Dalsze działania dotyczą wyłącznie pozyskania danych zgodnie z normalnym działaniem oficjalnej strony i weryfikacji dat, waluty oraz metodologii, bez deklarowania cen wykonania.

**Neon LAB main, scheduler v0.3 i portfele bez zmian. Operacje finansowe oraz papierowe fill-e: 0.**
