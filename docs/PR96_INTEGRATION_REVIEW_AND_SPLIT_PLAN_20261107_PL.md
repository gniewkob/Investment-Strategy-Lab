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
