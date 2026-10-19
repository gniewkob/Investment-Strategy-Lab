# EIA — pierwsze wersjonowane źródło: kontrola GO/NO-GO (STAGING)

**Stan: 19.10.2026.** Dotyczy wyłącznie edukacyjnego Investment Strategy Lab, danych referencyjnych i prospektywnego testowania historii źródeł. Bez handlu, sygnałów inwestycyjnych, automatycznej alokacji oraz promocji produkcyjnej.

## 1. Potwierdzony wynik w prawdziwym Neon STAGING

Wykonano bez jakiegokolwiek zapisu dokładnie [`db/verify_eia_first_snapshot_READONLY.sql`](../db/verify_eia_first_snapshot_READONLY.sql), wskazując połączeniu Neon jednoznacznie:

- Projekt `red-lake-53043722`
- Gałąź STAGING `br-wandering-union-ba6ogf6l`
- Baza `investment_lab`

Raport `EIA_FIRST_SNAPSHOT_STAGING_PREFLIGHT_V1`:

| Właściwość | Wynik |
| --- | --- |
| Lokalna integralność | `REFERENCE_DATA_PREFLIGHT_PASS` |
| Decyzja o imporcie | `NO_GO_PENDING_LIVE_SOURCE_AND_EXPLICIT_WRITER_APPROVAL` |
| Znacznik STAGING | 1 testowy cykl + 3 decyzje `HOLD_CASH` |
| Katalog źródeł EIA | 3/3 |
| Katalog instrumentów EIA | 3/3 |
| WTI | 695 rekordów, 695 unikalnych dat (02.01.2024–14.10.2026) |
| Zapisane 19.10 uzupełnienie WTI | 35 wierszy |
| SHA-256 zamrożonej pierwszej części 660 WTI | `2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8` |
| Brent | 706 rekordów |
| Dokumenty `source_documents` | 3, z czego EIA: **0**, pozostałe `nbp_gold` |
| `price_observation_versions` | 3, z czego EIA: **0** |
| Dedykowana rola `isl_eia_pit_staging_writer` | **0** |
| Zmiany DB przez kontrolę | **0** |

**Lokalne PASS oznacza wyłącznie spójność istniejącej tabeli referencyjnej STAGING. Nie dowodzi zgodności z aktualnym EIA, jakości PIT ani gotowości uprawnień.** Poza udokumentowanym już uzupełnieniem 35 cen nie zapisywano żadnych nowych danych rynkowych w tym kroku.

## 2. Dwa nierozwiązane ręczne odbiory LIVE

Z poziomu udostępnionego połączenia GitHub nie ma operacji `workflow_dispatch`. Nie uruchamiać tego pozornie przez PR, `push`, dodanie `schedule` ani ponowienie pominiętego joba. Zatwierdzone workflow używają ręcznego bramkowania, dlatego wykonanie wymaga **Run workflow** w GitHub UI, z gałęzi `main`:

1. [Post-import WTI EIA ↔ Neon STAGING 695 dni (READ ONLY)](https://github.com/gniewkob/Investment-Strategy-Lab/actions/workflows/eia-wti-staging-receipt.yml). Spodziewany status: `WTI_POSTIMPORT_EIA_STAGING_695_MATCH_READ_ONLY` plus 695 zgodnych cen i dat, 0 różnic, zamrożony hash 660 oraz brak antydatowania 35 nowych.
2. [Źródła EIA, tylko publiczny HTTPS (NO DATABASE)](https://github.com/gniewkob/Investment-Strategy-Lab/actions/workflows/eia-versioned-ingest.yml). Log ma potwierdzić oryginalne HTML SHA, semantic SHA dat/cen, autentyczny `retrieved_at` po kompletnym pobraniu, wydanie EIA, aktualność, 0 połączeń DB, 0 zapisów.

W obu workflow PR/push uruchamia wyłącznie syntetyczne testy i oznacza job LIVE jako **SKIPPED**. Zielony PR CI albo GitHub push to **nie** taki odbiór. Oba ręczne wyniki rzeczywiste są w tym punkcie **PENDING**.

## 3. Twarda granica zgody i autentycznej chronologii

Nie uruchamiać `apply_plan()` ani [review-only SQL proponującego rolę](../db/security/eia_pit_staging_writer_REVIEW_ONLY.sql) tylko dlatego, że lokalna kontrola danych przeszła. Wciąż wymagane są:

1. Osobny przegląd tożsamości nowej dedykowanej roli bez dostępu do portfela, dzienników, legacy history i uprawnień `UPDATE/DELETE/TRUNCATE`. Hasło oraz sekret wyłącznie poza kodem i logami. Projekt SQL `NOLOGIN` nie wystarczy do połączenia logowalnego.
2. Kontrola projektu/gałęzi Neon na poziomie API oraz TLS `verify-full` w przyszłej ścieżce **tylko STAGING**; samotny marker SQL nie dowodzi tożsamości gałęzi.
3. Rzetelne źródło i niezmienne archiwum **rzeczywistych oryginalnych bajtów HTML**, powiązanych z oboma SHA i czasem pobrania. Repozytorium ma obecnie hashe i metadane, nie implementację trwałej archiwizacji bajtów.
4. Jasny limit pierwszego eksperymentalnego current-snapshot importu, separacja syntetycznych fixture oraz kontrola `prices_asof()` bez look-ahead w jednorazowej gałęzi.
5. **Wyraźna osobna zgoda** na jakikolwiek `CREATE ROLE`, modyfikację ACL, sekret albo pierwszy `INSERT` do Neon. Produkcja zawsze wyłączona.

**Najważniejsze ograniczenie danych:** dzisiejsza publikacja EIA z historycznym szeregiem nie dowodzi, że dana cena z 2024 r. była dostępna w 2024 r. Nawet po przyszłym poprawnym imporcie bieżącego snapshotu pierwotne historyczne `published_at` poszczególnych notowań pozostaną **niezweryfikowane**, a model nie może testować historycznych decyzji przy założeniu dostępności tych danych wcześniej.

## 4. Klasyfikacja na dziś

- **GO** dla dalszych prac inżynierskich i syntetycznych testów.
- **GO** dla tylko odczytu oficjalnego EIA i Neon przy ręcznych bramkach.
- **NO-GO** dla nowego zapisu do Neon, nowych ról, sekretów, harmonogramów oraz promocji produkcyjnej bez wymaganych dowodów i zatwierdzenia.
- **NO-GO** dla historycznych sygnałów i backtestów wykorzystujących niepotwierdzoną dostępność cen.
- M1/M2/M3 pozostają `HOLD_NO_CHANGE` (wyłącznie edukacyjne modele wirtualne).

Powiązane: [Issue #2 — oryginalne publikacje/PIT](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2), [Issue #3 — ACL](https://github.com/gniewkob/Investment-Strategy-Lab/issues/3), [aktualny handoff](SESSION_HANDOFF_PL.md).
