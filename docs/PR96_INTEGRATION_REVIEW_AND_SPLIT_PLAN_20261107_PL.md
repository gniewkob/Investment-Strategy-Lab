# PR #96 — przegląd integracyjny i plan podziału (2026-11-07)

**Repo:** `gniewkob/Investment-Strategy-Lab`  
**PR:** https://github.com/gniewkob/Investment-Strategy-Lab/pull/96  
**Gałąź:** `codex/v04-monthly-backtest-engine-20261106`  
**Stan testów końcowego SHA:** `8edd0056c1f38135847edede9ff2858282f0b7cb`, 5/5 GitHub Actions PASS; v0.29 8/8 PASS również lokalnie na Mac mini bez `ResourceWarning`.

## 1. Fakty zweryfikowane narzędziami GitHub

- Zmiany w PR: **132 pliki** według pełnej listy nazw z API PR #96.
- Porównanie bieżącej gałęzi do `main`: `diverged`, `ahead_by=305`, `behind_by=2`, `total_commits=305`, **154 pliki w tym osobnym porównaniu**. Liczby 132 i 154 są wynikiem **różnych sposobów wyznaczenia punktu bazowego**, nie należy ich zamieniać. To porównanie użyło gałęzi `main`, a nie potwierdzonego bezpośrednio `base_sha` PR.
- W zestawie PR znajdują się: **15 workflowów GitHub**, **2 pliki SQL**, **39 dokumentów**, 1 archiwalny JSON oraz źródła i testy Python/JavaScript (szczegóły w GitHub Files changed).
- Workflow `working-engine-v01-ci.yml` dodaje kilkadziesiąt ścieżek i testów; główna regresja E2E przechodzi, lecz CI dla **jednego SHA** nie rozstrzyga jakości całej historii 305 commitów.
- Część workflowów jest uruchamiana wyłącznie przez `workflow_dispatch`. Przykłady: `v04-vanguard-official-nav-export.yml` (Playwright oraz upload oryginalnego eksportu, jeśli wystąpi pobranie), `nbp-long-history-v04.yml` (live API NBP), `worldpulse-nav-audit-v04.yml`. Green PR checks **nie oznaczają wykonania tych workflowów z prawdziwymi przyszłymi źródłami**.
- `shadow-mac-install-canary-v12.yml` wykonuje zapis/restore tylko w `RUNNER_TEMP`, z izolowanym `--base-dir`; nie jest równoznaczny z upoważnieniem do operacji na produkcyjnym Mac.

## 2. Mapa zależności do zachowania

| Pakiet | Zależności | Status integracyjny |
|---|---|---|
| A — model bazy / engine v0.1–v0.4, reference archive NBP/TBSP | Istniejące schematy, SQL, źródła i ich testy | Wymaga osobnej regresji integracyjnej i przeglądu SQL |
| B — append-only evidence v0.5–v0.13 | Capture v0.7 → checkpoint v0.8 → SQLite v0.9 → external anchor v0.10 → backup v0.11 → Mac v0.12 / export v0.13 | Testy PASS; weryfikacja faktycznych ograniczeń SQLite i uprawnień plików pozostaje osobnym review |
| C — decision core v0.14–v0.19 | Źródła TOTAL_RETURN/PLN → shadow v0.5 → kontroler v0.15 → pipeline v0.16 → journal v0.17; gateway v0.18 / ACWI v0.19 nie podnoszą automatycznie kwalifikacji | Testy PASS, funkcja research-only, brak rynkowej kwalifikacji |
| D — conditional NAV v0.20–v0.25 | oryginalny offline XLSX Vanguard + NBP → v0.20/21 → freeze v0.22 → GitHub pin v0.23 → preflight v0.24 → NBP capture v0.25 | Lokalnie PASS do stanu PENDING; nie wolno modyfikować zamrożonego SHA/polityki |
| E — decision studies v0.26–v0.29 | v0.26/27 zależne od v0.15; v0.28 zależny od v0.15/16/17; v0.29 zależny od v0.9 i v0.16 | CI PASS, lokalny v0.28 i v0.29 PASS; nie są źródłem decyzji giełdowych |

## 3. Ryzyka i bramki — MUST FIX przed merge do main

**MF-01 — zakres i niezależność review.** 132 pliki / 305 commitów przy rozbieżności gałęzi. Brak punktu odbioru dla review całej zmiany. Nie scalać całego PR #96 automatycznie; przygotować izolowane porcje według A–E, a następnie sprawdzić diff i zależności *każdej* porcji względem aktualnego `main`.

**MF-02 — source integrity and fixed experimental anchor.** `nav_forward_admission_v23.py` zawiera stałą `ANCHORED_FREEZE_SHA` oraz publiczny link do Issue #97. Zmiana wcześniejszej historii przy okazji rebase/cherry-pick nie może niejawnie zmienić ani tego SHA, ani lokalnych dowodów. SHA są dowodem spójności danych, **nie** niezależnym certyfikatem momentu publikacji, prawa do danych ani wyniku inwestycyjnego.

**MF-03 — limited market source provenance.** `v0.25` wymaga ręcznego eksportu źródłowego i ręcznie podanej daty pobrania; tylko NBP może wykonać opt-in HTTPS GET. Brak automatycznej atestacji tożsamości Vanguard, legalności redystrybucji i czasu oryginalnej publikacji. Ograniczenia te muszą pozostać widoczne w PR i w raportach.

**MF-04 — potential local evidence permissions issue.** `nav_fx_evidence_capture_v25.py` zapisuje raw NBP przez `dest.open("xb")`, a dopiero potem wykonuje `dest.chmod(0o600)`. Przy permissive umask może istnieć krótki przedział szerszych uprawnień nowego pliku. Do kontroli przed integracją: utworzenie atomowo z uprawnieniami `0600` *przed* zapisem (np. `os.open(..., O_EXCL|O_CREAT, 0o600)`), test na sztucznych danych. Nie dotykać zamrożonego manifestu v0.22.

**MF-05 — GitHub workflow data surface.** W `v04-vanguard-official-nav-export.yml` upload oryginalnego eksportu jest możliwy jako artifact Actions przez 7 dni; prywatny offline workflow v0.25 zakłada lokalną archiwizację. Przed operacyjnym dispatch/importem wymagany przegląd praw do źródła, prywatności artifacts, retencji i uprawnień GitHub. `workflow_dispatch` ogranicza automatyczne uruchomienie, ale nie rozwiązuje kwestii uprawnień do danych.

**MF-06 — regressions against current main.** Dwie zmiany na `main` nieuwzględnione przez gałąź mogą wpływać na bazowy stan i reguły PR. Wykonać dry-run bez przepisywania dowodów (fresh worktree, merge-base, diff, conflicts), CI na finalnym niezależnym kandydacie integracyjnym. Brak takiego wyniku w aktualnych dowodach.

## 4. Wskazany podział w logicznej kolejności

1. **PR-A (foundation):** v0.4 read-only SQL, NBP/TBSP history/reference + źródłowe parsery; osobno przegląd workflowów live-provider.
2. **PR-B (evidence):** v0.5–v0.13 shadow capture, GitHub checkpoint, SQLite append-only, backup, Mac isolated canary. Zależne od bazowych bibliotek.
3. **PR-C (policy/decision):** v0.14–v0.19 shadow controller + forward journal i source gateway; zależne od PR-A i PR-B tylko w miejscach faktycznego importu.
4. **PR-D (frozen Vanguard research):** v0.20–v0.25 i ich dokumentacja/fixtures; zachować linki i hashe starego freeze; oddzielić ręczne źródło od opcji pobrania NBP.
5. **PR-E (analytics):** v0.26–v0.29 decision robustness/quality/chronological/evidence bridge; zależności PR-B/PR-C; brak live trading.

Nie tworzyć pięciu nowych PR przez ręczne kopiowanie niezweryfikowanej głowicy. Najpierw ustalić rzeczywisty `merge-base` PR #96, granice commitów, obowiązujące ochrony `main`, obecne GitHub review i zgodność z 2 commitami na `main`. Następnie w osobnych worktree sprawdzić reprodukowalność; dopiero potem stworzyć małe gałęzie i PR z jednoznacznym diffem, bez automatycznego merge.

## 5. Stan odbioru / braki dowodowe

**Zakończone:** Mac v0.24/v0.25 PENDING PASS; Mac v0.28 9/9 PASS; Mac v0.29 8/8 PASS bez ResourceWarning; cały CI na `8edd005...` 5/5 PASS.

**Niewykonane:** pełne review kodu wszystkich 132 plików; test potencjalnych konfliktów `main`; rozcięcie PR i indywidualne przetestowanie; niezależne potwierdzenie source rights/PIT/licencji; rzeczywiste forward miesiące listopad 2026+; jakiekolwiek kwalifikowanie aktywnej strategii.

**Decyzja:** `PR_96_INTEGRATION_REVIEW_INCOMPLETE_DO_NOT_MERGE`. Priorytet to MF-04 i separacja workflowów źródłowych, po czym porządkowanie A–E na aktualnej bazie. Z technicznego PASS nie wyciągać wniosku o jakości inwestycyjnej ani dopuszczeniu transakcji.


## 6. Uzupełnienie odbioru — MF-04 naprawione (2026-11-07)

**Zmiana kodu i testów:** `e7c0e188b893c2b965c2492e3400f4df7e86bad5`.

`scripts/nav_fx_evidence_capture_v25.py` tworzy nowy plik przez `os.open(..., os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)`, co uniemożliwia fazę zapisu z uprawnieniami szerszymi niż `0600`, nie nadpisuje istniejących plików/symlinków, a po zapisaniu wykonuje `flush` i `fsync`. W `tests/test_nav_fx_evidence_capture_v25.py` dodano trzy przypadki: umask 000 daje nadal 0600, identyczne oryginalne bajty, katalog prywatny 0700; istniejący plik nie jest nadpisywany; wcześniejszy symlink nie zmienia pliku docelowego.

**CI na dokładnym SHA:** 5/5 workflowów GitHub PASS, Working Engine E2E [#42422706989](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42422706989), dedykowane testy v0.25 PASS. **MF-04 = TECHNICALLY REMEDIATED**, odbiór lokalny tej konkretnej poprawki nie był dotąd osobno wykonywany na Mac. Pozostałe bramki MF-01, MF-02, MF-03, MF-05 i MF-06 pozostają otwarte. Nie wprowadzono zmian w źródłach NAV, zamrożonej polityce, hashach, danych historycznych ani regułach kwalifikacji M1.


## 7. Aktualny punkt wspólny i automatyczny dry-run — 2026-11-07

Dane z dwóch rzeczywistych odpowiedzi GitHub Compare:
- `main` SHA `d93e2ac3c5559f0d06f99f8026655905e4a8537d`.
- Merge-base SHA `f06459a9a2513632497bc2039e4caea90eb8bc05`.
- Research branch SHA w chwili tego porównania `16bc35a5fcbeef631248bfd7556578bd5dba4972`.
- Branch względem `main`: 310 commitów ahead, 2 behind; 155 plików w forward compare. PR API wtedy pokazywał 133 changed files. Liczby mogą się zmienić po dopisaniu audytu.
- Reverse compare research...main: 2 commity zmieniające wyłącznie `.github/workflows/isl-nbp-public-daily.yml`, dodaną po stronie main. To **nie jest plik modyfikowany przez PR #96** — zachodzi zero kolizji ścieżek w porównaniu przy tych SHA. Nie stanowi to jeszcze fizycznego testu algorytmu merge Git.
- Daily workflow NBP z `main` ma harmonogram `17 4 * * *`, używa checkout przypiętego SHA `9bebd1aabb66019d3de0556c0ff1733d155bdbc1`, i nie zapisuje do Neon. Automatyczny merge nie może niejawnie przestawić tego SHA ani harmonogramu.

Nowe narzędzie `scripts/pr96_git_merge_preflight.py` wykonuje lokalnie **Git `merge-tree --write-tree`**, bez checkout, merge, rebase, push i bez zmiany refów. Git może utworzyć *nieosiągalne obiekty tree* w lokalnym object store, ale nie modyfikuje plików roboczych. Raport zawiera rzeczywiste rozstrzygnięcie clean/conflict, wyliczony merge-base, SHA obu gałęzi, liczbę zmian i nakładające się ścieżki. Odpowiedź `CLEAN_TREE_MERGE_ONLY_NOT_TESTED` oznacza wyłącznie zgodność merge-tree; **nie dowodzi pomyślnego CI dla połączonego drzewa**, dopuszczenia market sources ani uprawnień do merge.

### Lokalne wykonanie w Mac mini na świeżych refach

```bash
(
  set -euo pipefail
  cd "$HOME/Repos/Investment-Strategy-Lab-shadow-v12"
  git fetch origin main codex/v04-monthly-backtest-engine-20261106

  SHA="9ed9602487fa5d93a1e9cbb832d5e968f6f6c62b"
  DIR="$(mktemp -d)/lab"
  git worktree add --detach "$DIR" "$SHA"
  cd "$DIR"

  python3 -m scripts.pr96_git_merge_preflight \
    --repo "$HOME/Repos/Investment-Strategy-Lab-shadow-v12" \
    --main-ref origin/main \
    --research-ref origin/codex/v04-monthly-backtest-engine-20261106
)
```

Exit 0 oznacza wyłącznie czyste `merge-tree`; exit 2 konflikt. `git fetch` celowo aktualizuje **wyłącznie lokalne tracking refs**; nie wysyła zmian na GitHub. Narzędzie nie pobiera danych rynku, nie dotyka Neon ani portfeli. Należy zachować pełny wynik JSON i przypięte SHA z przebiegu operatora, zamiast deklarować sukces wyłącznie na podstawie braku kolizji plików.

### Plan po czystym merge-tree

1. Zweryfikować bazę konkretnego PR i ograniczenia branch protection, aby nie pomylić `main` z bazą innego PR.
2. Utworzyć **izolowany testowy merge commit** (zachowując obie historie) tylko w tymczasowej gałęzi i uruchomić testy na jego *rzeczywistym drzewie*, nigdy na starym SHA research.
3. Przygotować mniejsze PR A–E zależne w uporządkowanej kolejności, z osobnymi checks i punktami odbioru.
4. Nie przepisywać zamrożonych `v0.22` receipt SHA, historycznego NAV/NBP ani anchorów Issue #97.


## 8. Odbiór kompletnej regresji jednostkowej na połączonym drzewie — 2026-11-08

**Pierwszy przebieg Mac (Python 3.15.2) nie przeszedł:** 933 testy, 34 błędy, 1 nieudana asercja, 1 pominięty; `ModuleNotFoundError: psycopg` w testach staging, `portfolio_release_canary` odrzucał celowo brudny stan `git merge --no-commit`, a pełny pakiet zgłaszał liczne `ResourceWarning` SQLite oraz niewyczyszczone błędy HTTP.

**Remediacja odbioru bez zmieniania testów lub polityki:**
- Nowy workflow `.github/workflows/pr96-combined-tree-regression.yml`, kod commitu `4ca982211e24bfe937ca43aff489b11a79b13527`.
- Checkout bazowego `main`, fetch dokładnego HEAD PR, walidacja `merge-tree --write-tree`, a następnie lokalny, **tymczasowy czysty commit merge na runnerze bez push**; test atestacji sprawdza rzeczywisty HEAD, zamiast obchodzić kontrolę.
- Python 3.12.16, zainstalowany `psycopg[binary]>=3.1,<4` (w przebiegu 3.3.8); brak usług PostgreSQL i brak podanych sekretów lub DSN.
- **Wynik rzeczywistego CI:** [run #42423630342](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42423630342), **933 testy, 0 błędów, 0 failed, 1 skipped, PASS (15.675 s)**; `ISL_COMBINED_UNIT_TESTS_PASS`. W logu nie odnotowano `ResourceWarning`.
- SHA wynikowego drzewa na tym przebiegu: `f37cbb53d47ca97e88c4e1c079340427c631912d`, tymczasowy commit `a34cdc54bda8e9e07f3cc92984a04ab6f7f222a3`. To nowa wersja drzewa po dodaniu workflowu CI; nie należy utożsamiać jej z poprzednim lokalnym SHA `67dd983...`.

**Granica dowodu:** regresja *unit* połączonego drzewa to PASS w Linux/Python 3.12, lecz pełna integracja SQL na tym połączonym drzewie i niezależny przegląd 133+ plików nie zostały jeszcze zatwierdzone. Testy SQLite/HTTP na Mac Python 3.15 wymagają osobnego porządkowania i nie powinny być ukrywane przez blanket warning filters. SHA sprawdzonego połączonego kodu nie jest kryptograficzną atestacją licencji, PIT ani wydajności rynkowej.

**Decyzja:** `COMBINED_TREE_UNIT_REGRESSION_PASS`; `PR_96_MERGE_STILL_BLOCKED` do zakończenia kontroli MF-01/02/03/05 i bramek PostgreSQL/Workflow.


## 9. PostgreSQL combined tree oraz pierwszy wydzielony Draft PR — 2026-11-08

### Połączone drzewo — niezależne dwie bramki

Rozszerzono `.github/workflows/pr96-combined-tree-regression.yml` o zadanie `combined-tree-postgres`, które pobiera dokładne SHA obu gałęzi, buduje czysty tymczasowy commit łączący, niezależnie porównuje wynik `git merge-tree --write-tree`, podnosi wyłącznie **disposable PostgreSQL 16 na `localhost`** i uruchamia istniejące integracyjne testy SQL. Brak Neon, wallet, broker, secrets, main merge i push. Wprowadzona zmiana: `9dac41a92d7a6c782abeb6fd8bced134fb3e0b82`.

**Rzeczywisty odbiór**: GitHub Actions [#42427650325](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42427650325), dwa zadania SUCCESS na **tym samym tree SHA `b8a4a3c0f90ed109f9b6bf15be434177ac631862`**:
- `combined-tree-unit`: 933 testy, 0 failures/errors, 1 skipped.
- `combined-tree-postgres`: 25 testów `test_working_engine_v01.py` PASS i 6 testów `test_monthly_backtest_v04_readiness.py` PASS.
- `ResourceWarning` w obu logach: 0. To nie potwierdza jeszcze braku ostrzeżeń w macOS/Python 3.15 i nie certyfikuje źródeł/PIT.

Pozostałe 5 workflowów uruchomionych na `9dac...` również SUCCESS. **COMBINED_TREE_UNIT_AND_POSTGRES_REGRESSION_PASS.**

### Draft PR #98 — wydzielony fragment A1, nie zmergowany

[Draft PR #98 — samodzielny engine v0.4 i hipotetyczna wrażliwość kosztów v0.14](https://github.com/gniewkob/Investment-Strategy-Lab/pull/98) w branch `codex/isl-backtest-v04-core-isolated-20261108`, baza `main=d93e2ac3c5559f0d06f99f8026655905e4a8537d`, HEAD `f7e4890337be68ed8ee15bcdea64119449f57da0`.

**9 plików**: cztery source+test do samowystarczalnego Python stdlib backtestu v0.4 i analizy kosztów v0.14, SQL+integracyjny test read-only gotowości źródeł, dwa oryginalne dokumenty oraz dedykowany workflow read-only. Wszystkie **osiem oryginalnych plików ma dokładnie zgodny Git blob SHA** z branch PR #96 — zostało zweryfikowane przez odczyt obu gałęzi. Nowy workflow jest jedynym nowym plikiem niebędącym kopią.

**Niezależne CI:** [run #42427944205](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42427944205), oba zadania SUCCESS: `synthetic-core` 21+11 testów PASS; `disposable-postgres-readiness` 6 testów PASS. Łącznie 38 testów. Brak prawdziwych operacji finansowych i nowych danych rynkowych.

**Wymóg integracyjny: NIE merge PR #96 i #98 wprost jeden po drugim bez reconciliacji.** Osiem plików jest współdzielonych między PR i należy formalnie usunąć je z przyszłego zakresu merge dużego PR albo zastąpić ten PR przez mniejsze, jednoznacznie zależne pakiety. PR #98 pozostaje draft do niezależnego review i kontroli zależności; zielone CI nie jest upoważnieniem do automatycznego merge. Kolejne wycinki A2/B/C/D/E powinny powstawać z nowej gałęzi głównej, po zachowaniu source evidence freeze SHA, bez kopiowania niezweryfikowanych credentials.

**Nadal otwarte:** przegląd 133+ plików i workflowów (MF-01), praw licencyjnych i PIT (MF-03), semantyki live-provider artifacts GitHub (MF-05), uprawnień/ochrony main, lokalne ostrzeżenia SQLite na Python 3.15. Nie dopuszczać realnej realizacji finansowej.


## 10. A2 offline source contracts — rzeczywisty podział i review dostawców (2026-11-08)

- Utworzono [Draft PR #99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99) do `main` (base `d93e2ac3...`) z brancha `codex/isl-source-evidence-v04-offline-20261108`. **10 plików**, w tym 8 source/test oryginalnie skopiowanych bez zmiany blob SHA z PR #96, plus nowy workflow offline i dokument odbioru.
- Dedykowana bramka [GitHub Actions #42450845898](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42450845898) — **32/32 testy PASS** na Python 3.12, z zablokowanymi Python socket connections; brak prawdziwego pozyskania zewnętrznych danych przez testy. Pierwszy run [#42450769068](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42450769068) wykrył brak dependency `scripts.nbp_reference_capture.py` na `main`. Moduł dołączono bez zmiany i cały zestaw wykonano ponownie.
- PR #99 pozostaje Draft, nie ma połączenia z portfelem ani Neon, nie ma automatycznego real source capture, a `historical PIT`, original source identity i prawo do redystrybucji nadal są nieweryfikowane.
- Dokładny przegląd aktualnych *online* workflowów / surowych artifactów opisano w `docs/PR96_A2_PROVIDER_WORKFLOW_RISK_REVIEW_20261108_PL.md` — osobny A2-provider powinien poczekać na formalne uprawnienia do korzystania ze źródeł. Tylko w tym kontekście można rozważyć przenoszenie narzędzi `workflow_dispatch` do oddzielnego review.
- **PR #96, #98 i #99 częściowo zawierają te same oryginalne pliki**. Nie scalać #96 po mniejszych PR bez ponownego przeliczenia oczyszczonego diffu i dependency graph. Nie zmieniać zamrożonych NAV/FX hashów w ramach porządkowania Git. PR #96 nadal BLOCKED dla merge całości.


## 11. Wydzielone B1/B2 — dowody i izolacja hosta, 2026-11-08

Wydzielono dwa **stacked Draft PR** zachowujące zależności źródeł zamiast duplikować poprzednie A2:

- [**Draft B1 #100**](https://github.com/gniewkob/Investment-Strategy-Lab/pull/100), `codex/isl-evidence-ledger-b1-20261108`, base `codex/isl-source-evidence-v04-offline-20261108` (Draft A2 #99), HEAD `ca5ba310451d3fbcfda86d1e2bd38e697c29f6a1`. Zakres: `shadow_decision_engine_v05`, `shadow_capture_v07`, `github_checkpoint_verify_v08`, `shadow_evidence_ledger_v09`, `shadow_external_anchor_v10`, `shadow_backup_restore_v11`, ich 6 testów, oryginalny archived fixture v0.9, dokumentacja, workflow. **15 plików diff**, **13/13 oryginalnych Git blob SHA = identyczne z dużym PR #96** (w tym archive). Oryginalny surowy plik bundle v0.9 SHA-256 `4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3`. [GitHub Actions #42471064073](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42471064073): **47/47 PASS Linux i 47/47 PASS macOS**, Python 3.12, bez połączeń sieciowych i ResourceWarning w logu.
- [**Draft B2 #101**](https://github.com/gniewkob/Investment-Strategy-Lab/pull/101), `codex/isl-evidence-host-b2-20261108`, base `codex/isl-evidence-ledger-b1-20261108` (Draft B1 #100), HEAD `f7fd17001fc9e153d6ab7517c744123188b420c9`. Zakres: `deploy_shadow_evidence_mac_v12` i `shadow_offsite_export_v13`, ich testy + dokumentacja i workflow. **6 plików diff**, **4/4 oryginalnych source/test Git blob SHA identyczne z #96**. [GitHub Actions #42471266332](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42471266332): **16/16 PASS Linux i 16/16 PASS macOS** na izolowanych katalogach tymczasowych, bez live Mac/LaunchAgent, Neon, portfela, zewnętrznego storage ani ResourceWarning w logu.

**Doprecyzowanie zakresu:** `shadow_forward_evaluation_v05.py`, `shadow_journal_v06.py` oraz ich testy **nie są zależnością B1/B2**, lecz obsługują interpretację wyników forward i dziennik badawczy. Należy je objąć przyszłym C/E (decision/forward journal), nie pomijać i nie kopiować w ciemno do obu pakietów.

**Ograniczenie:** B1 zapewnia lokalne dowody kontroli spójności, **nie WORM i nie trusted timestamp**. B2 zapewnia lokalne fixture copy/restore, **nie potwierdzenie fizycznie niezależnego offsite**. Historyczny oryginalny checkpoint zachowano bez zmiany; nie dowodzi to rzeczywistego PIT, OOS skuteczności ani praw licencyjnych do danych.

**Kolejność integracji:** A2 #99 → B1 #100 → B2 #101, po niezależnym review, sprawdzeniu branch protection i domknięciu zależności; A1 #98 pozostaje równoległy. Po każdym etapie ponownie policzyć git diff i wymagane checks. **Nie mergować PR #96 w całości po wydzielonych zmianach** bez reconciliacji nakładających się plików. Zamrożone SHA v0.22/v0.23 nietknięte. Żadnych realnych operacji finansowych.


## 12. Wydzielone C1/C2 — badawczy kontroler decyzji i bramki źródeł (2026-11-09)

- **[Draft PR #102 — C1](https://github.com/gniewkob/Investment-Strategy-Lab/pull/102)**: branch `codex/isl-decision-c1-20261109`, base `codex/isl-evidence-ledger-b1-20261108` (B1 #100), head `b44d23ebb4c1f3ec9974dbeec2b3b85e110e2ba1`, **12 plików** diff: 10 exact original Git blobs z PR #96 + nowy CI/docs. Zakres `shadow_forward_evaluation_v05`, `shadow_journal_v06`, `research_decision_controller_v15`, `research_decision_pipeline_v16`, `research_forward_journal_v17` oraz ich oryginalne testy. NBP/ETF source gate i oryginalny archival v0.9 pozostają bez zmian. [CI #42624134958](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42624134958): **53/53 PASS Ubuntu i 53/53 PASS macOS**, bez ResourceWarning w obu job logach, Python 3.12, zablokowane socket connections, raw SHA-256 oryginalnego v0.9 archiwum `4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3`.
- **[Draft PR #103 — C2](https://github.com/gniewkob/Investment-Strategy-Lab/pull/103)**: branch `codex/isl-source-gateway-c2-20261109`, base `codex/isl-decision-c1-20261109` (C1 #102), head `3aa7f8916b864ff136a2c80ca0d5d1980f6b664b`, **6 plików** diff: 4 exact original Git blobs z PR #96 + nowy CI/docs. Zakres `real_reference_gateway_v18` i `acwi_netr_offline_intake_v19` oraz testy. [CI #42624511327](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42624511327): **19/19 PASS Ubuntu i 19/19 PASS macOS**, obie prace zakończone `success`, bez ResourceWarning w obu logach. Socket blocking, brak prawdziwych uprawnień MSCI/licencji/PIT ani danych transakcyjnych.

**Dependency graph:** A2 #99 → B1 #100 → C1 #102 → C2 #103. B2 #101 to niezależny fork po B1; A1 #98 jest niezależny od C. Żadnego `merge`, `rebase`, zmian w `main` ani w frozen Vanguard v0.22/v0.23. Zakres E (synthetic robustness v0.26–v0.29) potrzebuje B1/C1 i oryginalnych archiwalnych dowodów; zakres D (warunkowy NAV i forward v0.20–v0.25) wymaga osobnego źródłowego review, nie wolno importować przez przypadek workflowów pobierających raw provider data.

**Decyzja:** C1 ACCEPTED technicznie w testach offline, C2 ACCEPTED technicznie offline na Ubuntu i macOS. Oba Draft, merge blocked until independent review, branch protection, overlap reconciliation and genuine data-source licensing/PIT checks. Sintetyczne `HOLD_CASH`, `M3` two-month confirmation i forward evaluator nie są rynkową certyfikacją wyników.


## 13. D1/D2 i E1/E2 — domknięcie wydzielania logiki badawczej (2026-11-09)

Szczegółowy graf, status CI, listę komponentów i krytyczne nierozwiązane bramki zawiera `docs/PR96_SPLIT_RECONCILIATION_20261109_PL.md`.

- **[D1 Draft #104](https://github.com/gniewkob/Investment-Strategy-Lab/pull/104)** — base A2 #99, 12 plików diff; 10 oryginalnych source/test Git blob SHA potwierdzonych identycznych z #96. Conditional NAV v0.20/v0.21, oryginalna polityka freeze v0.22 i admission v0.23, wraz z wymaganym bundle intake i testem. [CI #42640373249](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42640373249) **41/41 PASS Linux i 41/41 PASS macOS**.
- **[D2 Draft #105](https://github.com/gniewkob/Investment-Strategy-Lab/pull/105)** — base D1 #104, 6 plików diff; 4/4 oryginalne bloby; preflight v0.24 i prywatny zapis v0.25 z `O_EXCL` i `0600`. [CI #42640741885](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42640741885) **19/19 PASS Linux i 19/19 PASS macOS**.
- **[E1 Draft #106](https://github.com/gniewkob/Investment-Strategy-Lab/pull/106)** — base C1 #102, 8 plików diff; 6/6 oryginalne bloby; odporność/quality/chronologia v0.26–v0.28 w syntetycznych scenariuszach. [CI #42641455098](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42641455098) **23/23 PASS Linux i 23/23 PASS macOS** przy `-W error::ResourceWarning`.
- **[E2 Draft #107](https://github.com/gniewkob/Investment-Strategy-Lab/pull/107)** — base E1 #106, 4 pliki diff; 2/2 oryginalne bloby; v0.29 read-only archived decision link. [CI #42641864529](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42641864529) **8/8 PASS Linux i 8/8 PASS macOS**, rygorystyczne `ResourceWarning`, oryginalne v0.9 bundle SHA zweryfikowane.

Razem D/E **22/22 Git blob SHA source/test bez zmian** względem PR #96. Zamrożone kodowe v0.22 SHA `7a9c7e5cbc643b5ad760ec64d4212468b64a22bf` oraz v0.23 `d425076ea809f622e5b2c1c4e87ba59fe060f990`; historyczny freeze `3b8aca44ffa6aa72bf2d3a0b5d49102f0dd857d11191dc10e7d21b5051e704a2` niezmieniony. **Nowa rzeczywista listopadowa obserwacja NAV nie została zweryfikowana**; status `PENDING`.

**Łącznie 10 etapowych Draft PR #98–#107**, z **69 oryginalnymi plikami** z PR #96 źródłowo rozdzielonymi i przetestowanymi. **Duży PR #96 nadal ma 137 zmienionych plików i nie jest bezpiecznym kandydatem do automatycznego merge**: nieprzeniesione online workflowy źródeł, raw artifact Vanguard, dodatkowe kolektory, raporty i CI wymagają osobnego przeglądu/rozstrzygnięcia. Zero merge/rebase do `main`, zero operacji finansowych.
