# Investment Strategy Lab — G1: decyzje o źródłach i kontrola aktywacji workflowów

**Data przeglądu:** 2026-11-09. **Zakres:** 16 plików YAML `.github/workflows/` pozostałych w badawczym Draft PR #96 na `codex/v04-monthly-backtest-engine-20261106`; nie są obecne w bazie `main`. Dokument nie uruchamia żadnego źródła ani nie przyznaje licencji, a przegląd nie zastępuje porady prawnej.

## 1. Executive decision

**Nie przenosić wprost żadnego z 16 workflowów PR #96 na `main`.** Podział PR #98–#107 pozwala oceniać moduły offline i syntetyczne osobno. Workflowy pobierające dane oraz rejestrujące dowody z operacyjnymi triggerami mają własną powierzchnię uprawnień, retencji i niejawnego uruchamiania. Każdy z 16 workflowów ma obecnie w rejestrze status `HOLD_FOR_SEPARATE_REVIEW`, bez możliwości zmiany go przez lokalny wynik SHA.

**Dostarczony mechanizm:** `governance/isl_provider_workflow_inventory_v01.json` zawiera 16 ścieżek, oryginalne Git blob SHA-1 i rozpoznane cechy; `scripts/provider_workflow_review_v01.py` porównuje kod w *lokalnym checkout* bez dostępu do internetu. Gdy pliki nie są obecne, raportuje `NOT_PRESENT_IN_CHECKOUT`; gdy są, stwierdza `EXACT_SOURCE_BLOB_FOR_REVIEW_ONLY` lub `SOURCE_BLOB_CHANGED_REVIEW_REQUIRED`. Nawet zgodność 100% oznacza tylko spójność snapshotu, **nigdy** zgodę na pobieranie danych ani merge. Pole `activation_approved=false` jest celowo nieusuwalnym ograniczeniem tego narzędzia.

## 2. Decyzje wymagane według źródła (rodzaj dowodu i status)

| Źródło | Rzeczywisty fakt / źródło | Otwarta decyzja i status |
|---|---|---|
| **Vanguard UK Professional** | Oficjalne Terms and Conditions, sekcja **User license**, podaje licencję na używanie/dostęp osobisty, informacyjny i niekomercyjny, odmiennie regulując inne zastosowania. Wprost ogranicza kopiowanie, dystrybucję oraz powtarzalny zautomatyzowany dostęp poza dopuszczonymi sposobami. [Vanguard UK Professional — Terms](https://www.vanguard.co.uk/professional/terms-and-conditions) | **HOLD: explicit rights review.** Nie wolno z samej dostępności XLSX wywodzić uprawnienia do Playwright scrape i publikowania jego bajtów w GitHub artifacts. Zweryfikować zakres dla konkretnego endpointu i przepływu (lokalne archiwum vs GitHub artifact); jeśli nie ma potwierdzenia, pozostać przy testach syntetycznych. |
| **MSCI ACWI NETR** | [MSCI Index Terms](https://www.msci.com/legal/index-terms), sekcja **Index Terms**, rozróżnia użycie informacyjne niekomercyjne od wymagającego pisemnej zgody wtórnego wykorzystania lub redystrybucji. | **HOLD: prawa do konkretnego indeksu/dostępu.** Parser offline w C2 nie uprawnia do automatycznego pozyskania ani upublicznienia oryginalnego szeregu. |
| **World Bank GEM** | [World Bank — Datasets Terms](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets), sekcje **Datasets** i **Exceptions for Some Third-Party Data**: zasada CC BY 4.0 z wyjątkami dla danych osób trzecich oznaczonymi w metadanych. | **CONDITIONAL REVIEW:** sprawdzić faktyczną licencję dokładnego indikatoru/źródła GEM i atrybucję; nie stwierdzać „każdy indikator jest CC BY”. Sukces API nie oznacza, że jest to global equity TR. |
| **NBP** | [NBP Web API — instrukcja](https://api.nbp.pl/): publiczne GET JSON/XML, historyczne FX i złoto, **HTTPS od 2025-08-01** i najwyżej **93 dni na pojedyncze zapytanie**. | **METADATA-ONLY FIRST:** potwierdzona możliwość odczytu API nie określa wszystkich warunków dalszej redystrybucji i retencji. Zachować `FX_RATE` i `PRICE_ONLY`, rzeczywisty `retrieved_at`, raw digest i dokładną datę. |
| **BondSpot/TBSP** | Kod PR #96 odpytuje `https://www.bondspot.pl/tbsp_index_archive_en` oraz stronicowane archiwum. W tym audycie **nie uzyskano wiążącej, zweryfikowanej zgody/warunków dotyczących automatycznej archiwizacji i redystrybucji**. | **HOLD: rights unknown**, nie importować raw artifacts ani pełnej kopii 60 miesięcy na `main`; osobno potwierdzić status danych, typ indeksu, zakres uprawnień i retencję. |
| **WorldPulse** | Kod `worldpulse_nav_availability_v04.py` oznacza prawa do zapisu i redystrybucji jako `UNVERIFIED`; wynik HTTP służy badaniu dostępności. | **HOLD** do czasu weryfikacji praw konkretnego API i tego, czy cechy źródła odpowiadają badanej klasie aktywa. Nie robić z niego substytutu oryginalnego NAV/total return. |

**Klasy dowodu nie są wymienne:** NBP `FX_RATE` ≠ gold `PRICE_ONLY` ≠ BondSpot `NON_TRADABLE_INDEX` ≠ Vanguard `NAV_REFERENCE` ≠ zakwalifikowana seria `GLOBAL_EQUITY_TR_PLN`. Nawet poprawny hash i historyczny wykres nie dowodzą publikacji danych przed hipotetyczną decyzją (*point-in-time*) ani możliwej ceny realizacji zlecenia.

## 3. Kontrola workflowów — konkretne istotne ustalenia

| Workflow / faktyczny kod w PR #96 | Wynik technicznego przeglądu | Decyzja |
|---|---|---|
| `v04-vanguard-official-nav-export.yml`, `v04-vanguard-retail-nav-probe.yml` | Oba `workflow_dispatch`, Playwright/Chromium; `actions/upload-artifact@v4` przenosi potencjalnie **oryginalny eksport** na 7 dni | **Nie integrować** do czasu praw do automatycznego pobrania i przechowywania RAW; dopuszczalny osobny offline fixture-only test |
| `shadow-capture-v07.yml` | `pull_request`, `workflow_dispatch`, **`schedule` poniedziałek 06:17 UTC**; artefakt 90 dni | Wyraźny review bramki cyklicznej. **Nie wnosić harmonogramu** do `main` przez przypadkowy merge |
| `shadow-source-receipt-v05.yml`, `v04-nbp-bondspot-calendar-e2e.yml` | W kodzie występują **identyfikatory konkretnych starszych GitHub Actions runów** pobieranych przez `gh run download`. Część pierwotnych artefaktów retencjonowana 14 dni. | Zastąpić zależność od krótkotrwałego run ID manifestem SHA + zweryfikowaną trwałą kopią, ale **nie nadpisywać oryginalnych receipt**. Brak kopii = `SOURCE_MISSING`, bez rekonstrukcji z przyszłości |
| `github-checkpoint-audit-v08.yml` | Na PR pobiera metadane i artefakty wcześniejszego runu; upload audytu/backup testów 90 dni | Metadane API ≠ trusted timestamp; osobno przejrzeć artefakty, prawo do retencji i integralność odczytu |
| `world-bank-gem-audit-v04.yml`, `working-engine-v01-ci.yml` | `actions/checkout@v4` **bez** `persist-credentials:false` (pozostałe w tej grupie zwykle wyłączają) | Przed integracją dodać `persist-credentials:false` i ponowną regresję; w pierwszym workflow zachować ograniczenie uprawnień `contents:read` |
| `nbp-long-history-v04.yml`, `tbsp-official-60months-v04.yml`, `bondspot-monthly-source-probe-v04.yml` | Dostęp do oficjalnych/publicznych stron i API, zapisy metadanych/original-derived evidence w artefaktach 14 dni | Przed aktywacją: endpoint allowlist, klasy źródeł, prawa retencji, mechanizm source checkpoint, osobny dostawca/daty |
| `world-bank-gem-audit-v04.yml`, `worldpulse-nav-audit-v04.yml`, `official-market-source-probe-v04.yml` | Dodatkowe aktywne opt-in odczyty źródłowe; brak związku z automatyczną kwalifikacją TR | Priorytet metadata-only po sprawdzeniu praw i zakresu, bez importu oryginalnych danych do `main` |
| `shadow-mac-install-canary-v12.yml`, `pr96-combined-tree-regression.yml`, `working-engine-v01-ci.yml` | CI/fixture i izolowane środowisko; brak powodu by kopiować do nowego kodu wszystkie monolityczne ścieżki naraz | Oddzielne CI cleanup i analiza bezpieczeństwa tokenów. Wdrażać tylko potrzebne checks ze split PR |

**Nie są to wszystkie możliwe zagrożenia.** Przegląd 16 nazwanych workflowów nie zastępuje pełnej inspekcji wszystkich obecnych i przyszłych konfiguracji w repozytorium ani analizy wykonanych operacji z historii GitHub.

## 4. Kontrole źródłowe a wybór polityki projektu

1. **Minimalny token i izolacja:** [GitHub Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use), **Writing workflows → Use secrets for sensitive information**, rekomenduje least privilege i ostrożne traktowanie kodu nieufnego. **Nasza decyzja:** wyłączać utrwalanie credentiali checkout, `permissions: contents:read`, bez sekretów źródłowych w PR i bez dostępu do produkcji.
2. **Retencja artefaktów:** [GitHub Store and share data](https://docs.github.com/en/actions/tutorials/store-and-share-data), **Configuring a custom artifact retention period**, opisuje `retention-days`. **Nie przyznaje licencji na materiały dostawców.** Nasza decyzja: oryginalnych licencjonowanych bajtów nie umieszczać w GitHub artifacts, zanim uprawnienie, krąg odbiorców i retencja nie zostaną potwierdzone.
3. **Dane innych dostawców:** cytowane powyżej źródła Vanguard UK, MSCI, World Bank, NBP określają różne modele dostępu. **Własny standard projektu:** osobno przechowywać `source_uri`, `licence_evidence_uri`, `dataset_or_indicator_id`, `original_checksum`, `retrieved_at`, `original_publication_at` (jeśli niezależnie udokumentowany), `rights_scope`, `data_kind`, `retention_policy` i `provenance_status`. Brak niektórych pól ma skutkować `RESEARCH_ONLY / PIT_UNVERIFIED`, nie domyślnym uznaniem uprawnień.
4. **Niezależna atestacja:** Git hash, zapis w repo, SQLite hash chain i metadane GitHub Actions pozwalają sprawdzać określone aspekty spójności. **Nie są** automatycznie WORM, TSA ani gwarancją niezmienności oryginalnego czasu publikacji.
5. **Blokada realnego wykonywania:** żaden wynik tych kontroli nie autoryzuje operacji inwestycyjnych. M1–M3 pozostają `HOLD_CASH / SOURCE_GATES_BLOCKED` bez oryginalnych, niezależnie zakwalifikowanych szeregów total return; zamrożony listopadowy eksperyment NAV pozostaje `PENDING`.

## 5. Kolejność review i integracji — propozycja techniczna

| Kolejność | PR / pakiet | Gate do rozpoczęcia review / ewentualnego retarget |
|---|---|---|
| 0 | G1 (ten dokument + manifest + skrypt offline) | Code review, testy Linux/macOS, brak nowego źródła i runtime schedule |
| 1 | A1 #98 | Niezależny review syntetycznego backtestu i lokalnego disposable PostgreSQL; sprawdzenie branch protections |
| 2 | A2 #99 | Przegląd parserów offline i `nbp_reference_capture`; zero zgody na uruchomienie dostawcy wywodzonej z testu |
| 3 | B1 #100 | Po A2: kontrola archiwalnego v0.9, SHA, lokalnego ledger; bez WORM claim |
| 4a | B2 #101 | Po B1: instalacja fixture-only, uprawnienia POSIX i brak schedulera |
| 4b | C1 #102 | Po B1: niezależnie od B2, tylko decyzje i journal |
| 5 | C2 #103 oraz E1 #106 | Po C1: oddzielny przegląd klasy źródeł i syntetycznej jakości |
| 6 | E2 #107 | Po E1: odtwarzanie istniejącego dowodu i SQLite read-only |
| 7 | D1 #104, potem D2 #105 | Po A2: samodzielny review frozen v0.22/v0.23 i `0600/O_EXCL`; bez praw do RAW |
| 8 | Online źródła | **Osobny nowy PR dla pojedynczego dostawcy, dopiero po source rights, retention, endpoint review i potrzebie biznesowej** |
| 9 | Duży PR #96 | **Nie scalać.** Dopiero po odjęciu overlap i udokumentowaniu zamknięcia albo migracji pozostałych plików rozważyć zamknięcie PR jako superseded. Nie przepisywać zamrożonej historii |

Kolejność 4a i 4b może być równoległa. Po retargetowaniu PR nie wystarczy poprzedni CI SHA — wymagane są ponowne testy dokładnego połączonego drzewa i aktualne checks. Włączanie aktywnego dostawcy i próba mierzenia realnego performance to osobne, niezależne procesy; jedno nie dowodzi drugiego.

## 6. Odbiór narzędzia offline na osobnym checkout

Na kopii repo z gałęzią badawczą:

```bash
python -m scripts.provider_workflow_review_v01 \
  --inventory governance/isl_provider_workflow_inventory_v01.json \
  --source-root /path/to/checkout-of-research-pr96 \
  --require-all
```

To **tylko odczyt lokalnych plików**; oczekiwany wynik jeśli snapshot jest zgodny to `present_count=16`, `changed_count=0`, `activation_approved=false`. Brak jednego pliku lub zmiana SHA zwraca exit 2 i `SNAPSHOT_INCOMPLETE_OR_CHANGED`. Nie wykonuje sieci, git fetch, zmiany branch/ref ani danych finansowych. G1 sam jest oddzielnym Draft PR i nie instaluje ani nie uruchamia żadnego workflowu z PR #96.

## 7. Pozostające ustalenia do udokumentowania przed operacyjnym pilotem

- Zweryfikować prawa i warunki **konkretnych** endpointów/datasetów, osoby uprawnione do dostępu, zakres zapisu i przechowywania bajtów. Dla BondSpot/WorldPulse status brak potwierdzenia. Dla World Bank sprawdzić konkretną licencję GEM w metadanych.
- Potwierdzić, że przyszły provider workflow jest `workflow_dispatch` i domyślnie nie dostarcza danych do modelu bez niezależnej kwalifikacji.
- Uzgodnić miejsce prywatnego archiwum oryginałów poza GitHub repo/artifacts, zakres dostępu oraz test retencji/restore; dotyczy wyłącznie źródeł, dla których prawa zostały potwierdzone.
- Usunąć zależności od wygasających numerów przebiegów po niezależnym zarchiwizowaniu już istniejących evidence; brak historycznego oryginału nie jest naprawiany przez przyszłe próby pobrania.
- Wymagać osobnej decyzji dla ewentualnego harmonogramu `shadow-capture` i jawnie odróżnić licencję/API/techniczne czytanie od historycznego PIT i dopuszczenia badań.

**Status końcowy G1:** analiza i techniczna kontrola integralności workflowu — tak; aktywacja źródeł — **NIE**; realna inwestycja — **NIE**.


## 8. Odbiór G1 i rozróżnienie dwóch rodzajów kontroli

- **Kontrola snapshotu źródłowego:** niezależnie od skryptu audytowego odczytano przez GitHub **wszystkie 16 oryginalnych plików YAML** na research branch `codex/v04-monthly-backtest-engine-20261106`, a każde `git_blob_sha1` w `governance/isl_provider_workflow_inventory_v01.json` okazało się identyczne z API GitHub (**16/16 MATCH**). To oznacza zgodność inwentaryzacji z kodem na wskazanej gałęzi w momencie sprawdzenia, **nie** weryfikuje licencji, API prawa ani wykonania.
- **Rzeczywisty CI nowego G1 na main-based Draft:** [GitHub Actions run #42647907196](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42647907196) **PASS 2/2**: Python 3.12 **9/9 testów Ubuntu i 9/9 macOS**; `ResourceWarning` nie zgłoszono. Na tym nowym niezależnym branchu żaden z 16 pierwotnych workflowów nie występuje (`ISL_G1_SNAPSHOT_PATHS_PRESENT=0`), co jest **oczekiwanym zachowaniem**, a nie dowodem, że skrypt odczytał source branch. Testuje się tam wyłącznie jego semantykę na fixture oraz poprawność manifestu.
- **Dodatkowy odbiór Mac/research checkout (opcjonalny, wymagany przy zmianie oryginalnego branch):** uruchomić polecenie z §6 na świeżym worktree, gdzie wszystkie 16 plików są obecne, i zachować JSON z dokładnymi SHA; nie wymaga to GitHub tokenów ani dostępu do dostawców.
- **Decyzja:** `G1_CODE_AND_MANIFEST_CI_PASS` oraz `ACTIVATION_NOT_AUTHORIZED`. Draft #108 nadal wymaga niezależnego review, by mógł być rozpatrywany do merge; nie przenosi w sobie żadnego providera.
