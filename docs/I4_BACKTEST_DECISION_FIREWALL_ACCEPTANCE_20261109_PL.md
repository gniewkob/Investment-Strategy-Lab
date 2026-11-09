# Investment Strategy Lab — I4, granica backtest A1 → decyzje C1 (2026-11-09)

**Status:** `DRAFT / OFFLINE_RESEARCH_ONLY`. Kontrakt jest decyzją projektową, **nie** obowiązkiem wynikającym z ISO/NIST czy przepisów finansowych. Nie wydaje poleceń zakupu, sprzedaży ani transferu aktywów.

## 1. Problem i model zagrożenia

A1 `scripts/monthly_proxy_backtest_v04.py` oblicza hipotetyczną wycenę udziałów ułamkowych indeksów o charakterze `NON_EXECUTABLE_FRACTIONAL_TOTAL_RETURN_INDEX_PROXY`. Własne metadane A1 jawnie oznaczają `historical_pit_certified=false`, `investment_performance_proven=false`, a poziomy indeksowe **nie** są cenami wykonania. Nawet status `CONDITIONAL_HISTORICAL_RECONSTRUCTION` nie jest dowodem praw do źródła, historycznej pierwszej publikacji ani poprawnej wyceny przy realnej transakcji.

C1 `scripts/research_decision_pipeline_v16.py` niezależnie interpretuje **inny typ** wejścia: `EDUCATIONAL_SHADOW_ONLY` ze źródłowym manifestem lub zamrożonym archiwum v0.9. Dotychczas brakowało nazwanego interfejsu, który jednoznacznie odpowie użytkownikowi/systemowi „A1 to badanie; brak podstaw do modelowej decyzji” zamiast dopuszczać nieformalny adapter `result → qualified_source`.

**Ryzyko do wyeliminowania:** pozytywny hipotetyczny TWR, kompletne 48 miesięcy danych lub poprawny hash nie może automatycznie oznaczać `RESEARCH_ELIGIBLE_DECLARED`, `PAPER_CANDIDATE_ONLY`, certyfikowanego PIT ani prawa do finansowej realizacji sygnału. Samodzielne deklaracje `source_url`, `source_sha256`, `rights_status` nie są niezależną atestacją.

## 2. Zaimplementowana bramka

`scripts/research_backtest_decision_boundary_v01.py` zawiera niezależną, bezskutkową funkcję `review_backtest(report)`.

- Akceptuje **wyłącznie** kształty wyników A1: `SYNTHETIC_TEST_ONLY`, `CONDITIONAL_HISTORICAL_RECONSTRUCTION`, `NOT_RUN_INSUFFICIENT_DATA`, `NOT_RUN_INSUFFICIENT_HISTORY`. Dokładny zestaw pól; dodatkowe `paper_candidates`, `source_status`, `rights_status` i podobne próby dopisania prawa do promocji są odrzucane.
- Waliduje spójność wariantu raportu, brak samozatwierdzenia PIT/performance, `0` operacji i dostępów DB, zgodny charakter `NON_EXECUTABLE` oraz kompletność trzech modelowych, syntetycznych ścieżek.
- Kontroluje wielkość i kanoniczną reprezentację JSON. Raport otrzymuje osobny SHA-256 potwierdzający **identyczność bajtów znormalizowanego wejścia do bramki**, nie oryginalność ani legalność danych finansowych.
- **Zawsze** zwraca `HOLD_CASH_BACKTEST_NOT_QUALIFIED_SOURCE`: trzy statusy `HOLD_CASH`, `paper_candidates=[]`, `source_manifest_created=false`, `historical_point_in_time_certified=false`, `source_rights_independently_certified=false`, `real_order_authorized=false`, `orders_sent=0`, `paper_fills=0`, `financial_operations=0`, `database_writes=0`.
- Niczego nie pobiera, nie archiwizuje, nie zapisuje do Neon i nie uruchamia sygnałów ani transakcji.

**Interfejs C1:** rozszerzono istniejący `run_cycle(..., backtest_report=...)` oraz opcję CLI `--backtest-report`. Ścieżka A1 **nie wykonuje `decide()`**. Nie pozwala łączyć raportu A1 z manifestem bieżącym/poprzednim lub archiwum; takie kombinacje kończą się wyjątkiem. Stare ścieżki `--current` i `--archived-v09` zachowują swoje dotychczasowe kontrakty.

Przykład demonstracyjny z **lokalnym, syntetycznym plikiem JSON** A1 (bez fetch źródeł):

```bash
python -m scripts.research_decision_pipeline_v16 --backtest-report /path/to/synthetic-a1-report.json
```

To polecenie jedynie ocenia raport i zwraca `ISL_A1_TO_C1_FIREWALL`; nie daje sygnału do inwestycji.

## 3. Testy i odbiór

`tests/test_research_backtest_decision_boundary_v01.py` zawiera 18 testów, w tym:
- syntetyczny raport A1 (18 miesięcy), fikcyjnie skrajnie wysoki wynik, warunkową historyczną rekonstrukcję (48 miesięcy);
- brak serii i niedostateczną długość historii;
- próby sfałszowania PIT, performance, statusu, danych źródłowych i operacji;
- odrzucenie dodatkowych pól z rzekomym prawem wykonania, zmiany identyfikatorów, skróconej osi czasu, NaN i typu bool jako liczby 0;
- zakaz równoczesnego podawania raportu A1 i manifestu źródeł, odmowę przyjęcia A1 jako zwykłego manifestu C1;
- deterministyczny receipt, brak zmian w oryginalnym wejściu oraz regresję starej ścieżki `C1 current`.

`.github/workflows/isl-i4-backtest-decision-firewall-ci.yml` uruchamia **52 testy na Ubuntu i 52 na macOS**: 18 nowych + 13 oryginalnych C1 pipeline + 21 oryginalnych A1, z wyłączonymi połączeniami Python socket. Dodatkowe istniejące workflowy I3 muszą pozostać zielone (A2–C2, G1, A1/SQL). Pełna akceptacja wymaga odczytu **konkretnego nowego HEAD**, a nie wyników starszego I3.

## 4. Ograniczenia, których testy nie rozwiązują

Ta bramka chroni **jawny kanał wejściowy A1 do C1**. Nie poświadcza praw do danych, autentyczności indeksów, daty ich pierwszej publikacji, kosztów ETF, podatków ani wykonalności zleceń. Nie jest ogólną obroną przed dowolnym ręcznie sfałszowanym manifestem `EDUCATIONAL_SHADOW_ONLY`; C1 nadal może wygenerować wyłącznie **deklaratywnych badawczych** kandydatów dla kompletnych manifestów testowych. Z tego powodu w systemie pozostają `historical_point_in_time_certified=false` oraz `real_order_authorized=false` i nie ma połączenia do brokera/wallet.

**Zakaz promocji:** brak automatycznej ścieżki A1 → C1 `PAPER_CANDIDATE_ONLY` lub jakiejkolwiek realnej operacji. Osobna przyszła bramka kwalifikacji praw, oryginalnych źródeł i historycznego PIT jest nadal konieczna.

## 5. Zasady integracji

Zmiana powinna powstać wyłącznie w kolejnym **Draft PR I4** opartym na Draft I3 #111. Nie przepisywać/scalać osobnych Draft #98–#110 i szerokiego PR #96. Nie zmieniać `main`, harmonogramów, providerów, oryginalnego archiwum v0.9 i baz produkcyjnych.

**Decyzja:** `BACKTEST_TO_DECISION_PROMOTION_BLOCKED`. Akceptacja techniczna nie znosi ogólnego statusu `INSUFFICIENT_DATA / HOLD_CASH`.
