# ISL — A2 → B1 → C1 → C2, wspólna walidacja drzewa (2026-11-09)

**Właściciel zmiany:** Draft PR [#103](https://github.com/gniewkob/Investment-Strategy-Lab/pull/103) (C2). Stan: `INTEGRATION_RESEARCH_ONLY`. **Brak prawa do merge, aktywacji live providerów, operacji finansowych lub zmiany harmonogramu.**

## 1. Reprodukowalny zestaw wejściowy

| Warstwa | PR | Zatwierdzony do analizy HEAD | Rodzic brancha |
|---|---|---|---|
| A2 — źródła offline | [#99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99) | `3f6c727ccb2598fd4a11a3fee49b98270d2132a0` | `main` |
| B1 — evidence ledger | [#100](https://github.com/gniewkob/Investment-Strategy-Lab/pull/100) | `ca5ba310451d3fbcfda86d1e2bd38e697c29f6a1` | `codex/isl-source-evidence-v04-offline-20261108` |
| C1 — decision/journal | [#102](https://github.com/gniewkob/Investment-Strategy-Lab/pull/102) | `b44d23ebb4c1f3ec9974dbeec2b3b85e110e2ba1` | `codex/isl-evidence-ledger-b1-20261108` |
| C2 — source categories | [#103](https://github.com/gniewkob/Investment-Strategy-Lab/pull/103) | HEAD bieżącej gałęzi | `codex/isl-decision-c1-20261109` |

**Wykryta rozbieżność:** porównanie Git `A2 HEAD...B1 HEAD` miało status `diverged` (B1: `ahead_by=15`, `behind_by=5`, merge-base `8a22682df98c3079c02ee11b3622093b0d4e5a63`). B1 i C1 wciąż są potomkami *starego* A2. To problem grafu commitów niezależny od identyczności plików.

## 2. Zmiany wykonane tylko na C2 (bez rebase parentów)

- Poprzednio przeniesione zabezpieczenia przed niejawnym NBP HTTP: `scripts/nbp_reference_capture.py`, `scripts/nbp_bondspot_exact_date_v04.py`, oraz `tests/test_a2_explicit_source_access_v01.py`.
- Przeniesiono również **aktualny** workflow `.github/workflows/isl-a2-offline-source-evidence-ci.yml` i dokument `docs/A2_POST_SPLIT_OFFLINE_GATE_REVIEW_20261109_PL.md`.
- Niezależny odczyt GitHub contents API wykazał **12/12 identycznych Git blob SHA** pomiędzy aktualnym HEAD #99 i C2 dla kompletu plików należących do PR #99.
- Oryginalne moduły B1 `scripts/shadow_decision_engine_v05.py` i C1 `scripts/research_decision_controller_v15.py` zachowują dokładne blob SHA w porównaniu z oryginalnymi HEAD; pełna identyczność wszystkich plików B1/C1 *nie* jest tu osobno atestowana (opiera się też na niezmienionej historii przodków).
- Archiwum `evidence/shadow/v09/checkpoint-bundle-run-42305280062.json` ma wymagany oryginalny SHA-256: `4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3`.

## 3. Bramki automatyczne

Dodano `scripts/isl_stack_chain_acceptance_v01.py` oraz pięć testów `tests/test_isl_stack_chain_acceptance_v01.py`. Walidator:

1. Przelicza Git blob SHA-1 z rzeczywistych bajtów dla 12 A2 i dwóch kontrolnych plików B1/C1; odrzuca brak, symlink, zbyt duży plik lub zmianę hash.
2. Niezależnie porównuje SHA-256 oryginalnego archiwum v0.9.
3. Ustawia blokadę połączeń Python socket i uruchamia bez wyjątków i pominięć **158 testów** podzielonych na cztery warstwy: A2 **37**, B1 **47**, C1 **53**, C2 **21**; pięć własnych testów bezpieczeństwa uruchamianych jest przed tym zestawem.
4. Rejestruje `integration_to_main_authorized=false`, `historical_pit_certified=false`, `trading_authorized=false`, `provider_fetches=0`, `database_writes=0`, `real_orders=0` w kontrakcie wyniku.
5. Działa w oddzielnych jobach Ubuntu 24.04 i macOS 15, bez danych uwierzytelniających do źródeł zewnętrznych. Są to **ograniczenia sposobu działania kodu testowego**, nie formalna gwarancja dla całej platformy GitHub Actions.

Dedykowany workflow: `.github/workflows/isl-stack-chain-offline-ci.yml`. Odmowa akceptacji, jeśli którykolwiek test/pin jest niezgodny.

## 4. Interpretacja

**Dokładna zgodność kodu A2 w C2 nie usuwa rozbieżności Git parentów.** Testy mają potwierdzić spójność *bieżącego drzewa C2*, ale nie potrafią przewidzieć wyników późniejszego merge/rebase ani potwierdzić legalności źródeł. Zera operacji to stan kontraktu testowego, nie pełny audyt produkcyjnego środowiska użytkownika.

**Nieuzasadnione roszczenia:** dowód poprawnych historycznych źródeł total return, identyfikacja waluty w pięciokolumnowym CSV MSCI, prawa do automatycznego pobierania, zgodność first-publication z decyzją historyczną, rzeczywiste ceny ETF, koszty transakcyjne, przewaga predykcyjna M3.

## 5. Wymagane przed integracją do main

1. Niezależny review A2 #99 i jego offline/rights/PIT gates; w razie zmiany HEAD ponowić pinning i regression check.
2. W osobnym kontrolowanym integration worktree wykonać **rebase B1 na aktualne A2** (lub równoważną zmianę grafu), następnie C1 na B1 i C2 na C1. Nigdy nie robić force-push na cudze zmiany bez osobnej kontroli lease; obecny test nie wykonuje żadnego rebase, cherry-pick ani merge.
3. Zweryfikować aktualny combined tree oraz powtórzyć wszystkie CI; unikać podwójnego merge plików z szerokiego #96.
4. Osobno rozstrzygnąć prawa i rzeczywistą dostępność publicznych źródeł w czasie (PIT), oraz ekonomiczną wykonalność strategii. Do tego czasu `INSUFFICIENT_DATA / HOLD_CASH` jest poprawnym stanem algorytmu.

**Decyzja projektowa:** `DRAFT_INTEGRATION_RESEARCH_ONLY`; zero transakcji, transferów i zleceń.
