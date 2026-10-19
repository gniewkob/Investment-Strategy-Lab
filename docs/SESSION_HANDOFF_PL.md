## 19.10.2026 — paired benchmark descriptive gate / PR #28

**Dostarczone do `main`:** [PR #28](https://github.com/gniewkob/Investment-Strategy-Lab/pull/28) squash `de1922e3bc3f62ab3f8fc0e9254f1a44be31f3c4`. [PR CI run #39298153706](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39298153706) = SUCCESS, **165/165** syntetycznych testów, pełny edukacyjny pipeline (bez sekretów, bazy i transakcji) przechodzi.

- Nowy `scripts/paired_research_evidence.py` czyta tylko istniejące **zagregowane metadane** `nonoverlap_validation.json` i liczy zdarzenia ocenione na dokładnie tych samych datach: oba trafione, oba błędne, tylko radar, tylko naiwny znak poprzedniego baru. Zwraca jedynie liczniki i parowaną różnicę procentowych punktów, bez cen, bez baz i działań. Zwraca `PAIRED_BASELINE_DESCRIPTIVE_ONLY` i `NO_PREDICTIVE_ADVANTAGE_OR_EQUIVALENCE_CLAIM`, nie estymuje przewagi na rynku.
- **Fail closed**: `robustness.json` dla serii zawiera ostatnie max 12 zdarzeń. Przy większej liczbie niż 12 pełnych zdarzeń skrypt odmawia wyliczenia wyniku na niekompletnym wycinku; testy wykrywają też sfałszowane liczniki/polityki, duplikaty dat i niezgodne horyzonty.
- Naprawiony tekst w `scripts/opportunity_research_pipeline.py`: przy 0 zdarzeń makro informuje, że nie dostarczono niezależnych dowodów zamiast błędnie sugerować obecność oficjalnych dat i kontrargumentów. Rozszerzone CI emituje tylko **syntetyczny** `paired_baseline_diagnostic.json`.
- [Protokół prospektywnej walidacji](PAIRED_BASELINE_PROTOCOL_PL.md) zabrania nazywania wcześniej oglądanych wyników 2024–2026 nowym nietkniętym holdoutem; wymagane są przyszłe rzeczywiste vintages publikacji, wcześniej zamrożone reguły, porównanie parowane oraz kontrola wielokrotnego testowania i zależności szeregowej.
- **Stan realnych danych nadal bez zmian:** ostatnia rzeczywista manualna analiza v0.2 [#39245012461](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39245012461) pokazała 0pp dodatkowej zgodności kierunku względem naiwnej reguły na tych samych zdarzeniach dla wszystkich 8 serii. Nie wykonano po tym PR nowej manualnej analizy rzeczywistych danych; 0 zweryfikowanych rzeczywistych source-vintage PIT (przy 3 testowych wersjach), 35 brakujących cen WTI. Issue #2 i #22 otwarte; #21 i #23 zamknięte.
- **Bezpieczna granica:** wszystkie M1/M2/M3 `HOLD_NO_CHANGE`, źródło `UNVERIFIED_HISTORICAL_PUBLICATION`, nie zmieniano Neon, produkcji, sekretów, ról, schedule, portfela czy zleceń. [Dowód w Issue #4](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4#issuecomment-6273707505).

## 19.10.2026 — Issue #21 zamknięte: pełna historia anomalii BTC/ETH, PR #27

**Działa na `main`:** [PR #27](https://github.com/gniewkob/Investment-Strategy-Lab/pull/27), squash `d3fc37e993150912c4671a1b93e1681fc5c31b03`. Problem P1 `reference_data_quality._extreme_relative_moves` polegał na **zależności warstwy bezpieczeństwa danych od listy ostatnich 10 zdarzeń przeznaczonej tylko do wyświetlania** (`radar.cross_market_btc_eth.recent_divergence_events`). Skutkiem mogło być usunięcie starego skrajnego ostrzeżenia po wystąpieniu 11 późniejszych umiarkowanych odchyleń.

Poprawka liczy |z| ≥ 8 **od nowa na całej poprawnie zwalidowanej historii wspólnych dat BTC/ETH**, ze średnią i populacyjnym odchyleniem standardowym z wyłącznie **20 poprzednich okresów**; 20-bar MAD pozostaje dodatkową diagnostyką. Fingerprint danych i flagi `SOURCE_REVALIDATION_REQUIRED` pozostają, żadne przyszłe obserwacje nie wpływają na starszą punktową wartość. Istniejące podsumowanie `recent_divergence_events` nadal może pokazywać ostatnich 10 — nie ma już roli źródła prawdy dla blokady.

- **Regresje offline syntetyczne:** 1 wczesna skrajna rozbieżność + 11 późniejszych umiarkowanych; stara zostaje pominięta na ekranowej liście 10, lecz jest nadal wykrywana przez quality. Dodatkowo test pustej/sfałszowanej listy prezentacyjnej, braku wpływu przyszłych dat na wcześniejszą punktową ocenę oraz braku fałszywej anomalii dla identycznych ruchów cen.
- **PR CI:** [bridge #39293026553](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39293026553) i [research pipeline #39293026063](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39293026063), oba `SUCCESS`, **154 testy PASS** każdy. **CI po merge na `main`**: [bridge #39293158234](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39293158234) oraz [pipeline #39293158350](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39293158350) oba `SUCCESS`.
- [Issue #21](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21#issuecomment-6273021199) zamknięte `completed`. Użytkownik **nie uruchomił** jeszcze od tego merge nowego rzeczywistego `legacy-history-research.yml`; **nie deklarować** zmierzonych nowych liczników jakości na STAGING z v0.3.
- Wcześniej równolegle [PR #26](https://github.com/gniewkob/Investment-Strategy-Lab/pull/26) scalił silniejszy PIT-fixture gate. Nasz konfliktujący [PR #25](https://github.com/gniewkob/Investment-Strategy-Lab/pull/25) przeszedł CI po poprawce testu, lecz został **zamknięty bez merge** (duplikat). [Issue #23](https://github.com/gniewkob/Investment-Strategy-Lab/issues/23#issuecomment-6273033657) zamknięte jako wykonane w zakresie wiarygodności raportowania, **nie** gotowości realnych danych.
- **Nadal otwarte:** [Issue #22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22) — 35 brakujących notowań WTI 26.08–14.10.2026 wobec EIA, bez backfillu; [Issue #2](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2) — prawdziwe oryginalne źródła PIT, **0 wersjonowanych obserwacji źródłowo zweryfikowanych**. Samo zgodne EIA archiwum nie dowodzi daty pierwszej publikacji.
- **Granica:** badania edukacyjne, `UNVERIFIED_HISTORICAL_PUBLICATION`, 0 nowych zapisów Neon/ACL/sekretów/produkcji, 0 zleceń, 0 zmian wirtualnych alokacji, brak harmonogramów. M1/M2/M3 nadal `HOLD_NO_CHANGE`.

## 19.10.2026 — wskaźniki PIT syntetyczne vs zweryfikowane (PR #26)

**WDROŻONE na `main`:** [PR #26](https://github.com/gniewkob/Investment-Strategy-Lab/pull/26), squash `238b3316581cca992da33ff0d89a08008b7a9a74`. Zmieniono tylko `scripts/staging_data_audit.py` i `tests/test_staging_data_audit.py` w badawczym audycie jakości danych. CI [#39287318533](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39287318533) **SUCCESS**, pełny zestaw **152/152 testów PASS** (w tym nowe testy wykluczania syntetycznych fixture).

- `pit_eligible_rows` jest nadal **techniczną widocznością**, nie liczbą źródłowo uwierzytelnionych obserwacji. Dodano `pit_fixture_rows`, `pit_nonfixture_unverified_rows`, `pit_verified_market_rows` i ostrzeżenia `SYNTHETIC_PIT_FIXTURE_NOT_MARKET_DATA` / `NO_VERIFIED_POINT_IN_TIME_MARKET_EVIDENCE`.
- Odczytowe SQL identyfikuje `metadata.synthetic=true` lub `metadata.fixture_only=true`; źródła bez potwierdzenia nie mogą wypełnić zweryfikowanego minimum. Brak obecnie niezależnego per-row certyfikatu oryginalnej publikacji, dlatego `read_snapshot` zachowawczo przypisuje 0 prawdziwych zweryfikowanych źródeł i pustą serię jakościowo certyfikowaną, bez sztucznego podnoszenia gotowości.
- Niezależny READ-ONLY SQL na odizolowanym Neon STAGING potwierdził `prices_asof(now())=1` technicznie dostępny, dokładnie **1 syntetyczny**, **0 niesyntetycznych**, **0 zweryfikowanych źródłowo**. Historyczna tabela 3711 legacy obserwacji nadal `UNVERIFIED_HISTORICAL_PUBLICATION`. Wcześniejszy przyszły znacznik w jednym z trzech fixture jest zamierzonym testem, **nie usuwać go**.
- `MARKET_DATA_NOT_READY`, 0 zleceń, 0 zapisu bazy, brak harmonogramu, wszystkie M1/M2/M3 `HOLD_NO_CHANGE`. [Issue #23 status weryfikacji](https://github.com/gniewkob/Investment-Strategy-Lab/issues/23#issuecomment-6272267236). **Ręczny realny workflow staging-data-audit po tym commicie nie był jeszcze uruchamiany**, CI jest offline. Po nowym manualnym audycie sprawdzić `audit.json` i `audit.md` oraz liczniki. Issue #2 nadal dotyczy źródłowo uwierzytelnionych realnych PIT.

# Investment Strategy Lab — pełne przekazanie kontekstu nowej sesji agenta

> **Snapshot: 19 października 2026, około 07:11 UTC.** Ta strona opisuje stan **zweryfikowany w GitHub oraz Neon**, odróżnia go od planów. Stan może się później zmienić — przed zapisem albo wykonaniem operacji odczytaj aktualny `main`, Issues, PR-y, uprawnienia i historię workflow.  
> **Pierwsza lektura nowego agenta:** [`../AGENTS.md`](../AGENTS.md), potem niniejszy plik, [`HISTORICAL_REFERENCE_BRIDGE_PL.md`](HISTORICAL_REFERENCE_BRIDGE_PL.md) oraz [`OPPORTUNITY_RADAR_PL.md`](OPPORTUNITY_RADAR_PL.md).  
> **Status:** system badawczy / edukacyjne symulacje. **Nie ma zleceń, handlu, realnych inwestycji ani rekomendacji zakupowych.**

## 19.10.2026 — wydzielony parser EIA bez importu scalony do main (PR #24)

**WDROŻONE NA MAIN:** [PR #24](https://github.com/gniewkob/Investment-Strategy-Lab/pull/24), squash commit `db981d4639d5bc8ed0e5c5e1567bc41f32a982c8`. Reuse istniejącego parsera EIA z Draft PR #1 (`src/isl_v2/eia_sources.py`) i testów, bez kopiowania potencjalnie zapisującego do Neon `eia_ingest.py --write`.

- Nowy wyłącznie odczytowy `scripts/eia_readonly_audit.py`: HTTPS z allowlisty EIA, weryfikacja stałego adresu docelowego, Content-Type HTML, limit 8 MB, oryginalny SHA-256 rzeczywiście pobranego HTML, prawdziwy czas pobrania. Opcjonalne porównanie po dacie i Decimal do LOKALNEGO, publicznego pliku 3 kolumn `instrument_code,observed_for,close_price`, bez bazy, bez zewnętrznego wysyłania cen; wypisuje agregaty i daty różnic, nie ceny.
- Nowe testy syntetyczne `tests/test_eia_readonly_audit.py`; workflow `.github/workflows/eia-readonly-validation.yml` odpala pełną offline suite przy PR/push na main. Żywe zewnętrzne HTTPS do EIA uruchamia WYŁĄCZNIE manualny `workflow_dispatch`, bez sekretów i bez publikacji raw artifacts. **Nie uruchomiono jeszcze tego workflow manualnego na nowym kodzie**; CI PR używało fixture.
- **CI zweryfikowane:** [read-only PR #39276159521](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39276159521) i [full runner PR #39276159468](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39276159468) = PASS; pełny test suite **149/149 PASS**, kontrola statyczna `EIA_VALIDATION_HAS_NO_DATABASE_WRITE_PATH`. Nowy przewodnik [EIA_READ_ONLY_AUDIT_PL.md](EIA_READ_ONLY_AUDIT_PL.md).
- Wykonane wcześniej porównanie EIA vs Neon: WTI oficjalnie 695, zgodne 660, brak 35, różnic wartości 0; Brent 706/706 zgodne. Nie oznacza to gotowości oryginalnych historycznych publikacji ani pozwolenia na ingest. [Issue #22 zapis finalny](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6270654753), [Issue #2 status źródeł](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2#issuecomment-6270658965).
- **OTWARTE:** Issue #21 (radar BTC/ETH lista ucięta do ostatnich 10), Issue #22 (brakujących 35 cen WTI NIE UZUPEŁNIONO), Issue #23 (wszystkie 3 wersjonowane źródła są testowym fixture), Issue #2 (wersjonowane rzeczywiste PIT). Bez zmian Neon, sekretów, ACL, produkcji, harmonogramów, wirtualnych alokacji, bez transakcji. `UNVERIFIED_HISTORICAL_PUBLICATION`, M1/M2/M3 `HOLD_NO_CHANGE`.

## 19.10.2026 — pełna kontrola dzień/cena EIA vs Neon WTI i Brent

**WYKONANE, tylko odczyt:** pobrano opublikowane tabele dzienne EIA WTI Cushing i Brent (obie z nagłówkiem `Release Date: 10/15/2026`), rozpisano faktyczne wiersze tygodniowe na daty dzienne (bez domyślania brakujących komórek), wykonano `FULL OUTER JOIN` po `observed_for::date` i porównano dokładne wartości numeryczne `close_price` z oficjalnymi cenami przy tolerancji 1e-7 w Neon STAGING `br-wandering-union-ba6ogf6l`. Zakres 02.01.2024–14.10.2026:
- **WTI:** 695 dni w obecnej tabeli EIA, 660 dni Neon **zgodnych datą i ceną**, **35 dat EIA tylko** (26.08.2026–14.10.2026), 0 dni Neon tylko, **0 rozbieżnych cen**.
- **Brent:** 706 dni EIA, **706 zgodnych** dat i cen w Neon, **0** braków i rozbieżności.
- Łącznie: **1401** EIA, **1366** zgodnych obecnych w Neon, **35** braków WTI, **0** rozbieżnych cen.
- Bieżąca publiczna strona EIA nie potwierdza źródłowej daty pierwotnej publikacji **każdego** historycznego kursu; nie posiada tu utrwalonego hasha **oryginalnej reprezentacji HTML pobranej w tym audycie**. Nie wolno przypisywać mu historycznej dostepności point-in-time ani SHA-256 wcześniejszego GitHub Actions. Powyższe dowody to audyt **obecnego** oficjalnego archiwum vs **obecna** baza.
- Repo posiada już parser źródeł EIA w niepołączonym Draft PR #1 (testy HTTPS CI, bez DB). Wykorzystać parser w osobnym *reviewed* source-provenance dry-run; **nie** uruchamiać `--write`, nie tworzyć równoległego ETL ani automatycznego backfillu bez osobnej zgody.
- Dokładny wynik i metodologia: [Issue #22 — 2026-10-19 full-date matching](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6270375923). Audyt nie rozstrzyga **przyczyny** ucięcia dawnego wsadu z 17.10; brak dowodu, że WTI było publikowane w obecnej postaci w każdej historycznej dacie obserwacji.
- Dotychczasowe blokady v0.2 `STALE_DATA`, `PEER_COVERAGE_GAP` oraz `UNVERIFIED_HISTORICAL_PUBLICATION` pozostają. **Nie zmieniano** bazy (0 insert/update), uprawnień, produkcji, kodu radaru, sekretów, harmonogramów ani strategii. Wszystkie M1/M2/M3 `HOLD_NO_CHANGE`. Problem prezentacyjnej listy 10 anomalii w Issue #21 nadal nierozwiązany.

## Aktualizacja 19.10.2026 — istniejący parser EIA i potwierdzony deficyt 35 WTI

**Odkrycie:** w [Draft PR #1](https://github.com/gniewkob/Investment-Strategy-Lab/pull/1), poza aktualnym `main`, znajduje się gotowy, przetestowany parser oficjalnego EIA `src/isl_v2/eia_sources.py`, odczytowy CLI `src/isl_v2/eia_ingest.py`, testy i workflow `official-eia-source-validation.yml`. Parser domyślnie analizuje 420 dni, waliduje stronę, datę `Release Date`, kalendarz, wartości i hash SHA256. Odrębna ścieżka `--write` **nie jest zatwierdzona ani uruchomiona na Neon**; nie przenosić jej automatycznie, nie zakładać że wykonała poprzedni import 3711 rekordów.

Wcześniejszy prawdziwy, wyłącznie HTTPS i bez zapisu do bazy [GitHub Actions run #39158580349](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39158580349), 18.10.2026, **SUCCESS**: WTI 285 zweryfikowanych rekordów od 25.08.2025 do 14.10.2026 (source `Release Date=2026-10-15`, SHA256 oryginalnego HTML `715bd983c39901256a5ff95bc3115c3840f3aaeb4d88e71d3756a8df1f2442ac`), Brent 289, Henry Hub 283; wszystkie `DRY_RUN_NO_DATABASE_WRITE`. Test potwierdza, że źródło pozwala odczytać zakres brakujący w historycznej tabeli Neon.

Niezależne **SQL SELECT**, dla identycznego okna 25.08.2025–14.10.2026, w izolowanym Neon STAGING: Brent **289** zapisanych (zgodność *liczebności* ze źródłem, bez potwierdzonej zgodności każdego rekordu), WTI **250** zapisanych (ostatnia data 25.08.2026) vs **285** u parsera EIA, więc **deficyt netto 35 rekordów**. Osobno porównano 10 konkretnych dat EIA: 2 zgodne, 8 następnych nieobecnych. Nie jest znana pierwotna przyczyna ucięcia starego importu; do pełnego dowodu potrzebne porównanie *data-w-data*, bo WTI i Brent mogą różnić się kalendarzem publikacji. [Issue #22 — dowody](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6269888952), [Issue #2 — istniejący parser PIT](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2).

**Rekomendowana ścieżka:** wykorzystać/reviewować istniejący parser EIA wyłącznie w dry-run read-only, z odrębnym jawnie zabezpieczonym etapem przyszłego importu po osobnej zgodzie, poprawnym źródłowym hash i rzeczywistych datach pobrania. Nie backdatować `published_at`, `retrieved_at` ani `recorded_at`. Dane nadal `UNVERIFIED_HISTORICAL_PUBLICATION`. Brak zleceń, alokacji, harmonogramów, zmian Neon i produkcji.

## Aktualizacja 19.10.2026 — syntetyczne źródła PIT, nie błąd przyszłej daty

**Nowy zweryfikowany stan (Neon STAGING, tylko odczyt):** sprawdzono oryginalną implementację `investment_lab.prices_asof(cutoff)`, trzy wpisy `price_observation_versions` oraz trzy powiązane `source_documents`. Wszystkie 3 dokumenty mają w `metadata` jawny znacznik `synthetic` albo `fixture_only`. Wszystkie trzy ceny `GOLD_NBP_PLN_G` są **syntetycznymi przykładami testującymi**; notatki na rekordach to między innymi „Synthetic late ingest PIT fixture; NOT a real market price” oraz „Synthetic data, test branch only…”. Wynik SQL: `total_documents=3`, `fixture_documents=3`, `total_versioned_rows=3`, `fixture_versioned_rows=3`, **`non_fixture_versioned_rows=0`**.

**Korekta wcześniejszej interpretacji:** `retrieved_at=2026-10-20T10:00Z` oraz `recorded_at=2026-10-20T10:00Z` są **celowo przyszłe**, aby testować odrzucanie spóźnionych/przyszłych informacji. To **nie jest wykryty błąd datowania realnych danych** i NIE należy go poprawiać. `prices_asof` stosuje konserwatywne `GREATEST(available_at, published_at+opóźnienie dla DAY, recorded_at, retrieved_at) <= cutoff`. Wyniki `prices_asof` na 28.08 i 30.09 = **0**; na 17.10 i `now()` = **1**, ale to **jedna technicznie widoczna próbka testowa, nie zweryfikowane notowanie**.

**Nowy priorytet jakości:** `scripts/staging_data_audit.py` liczy `pit_eligible_rows=1` bez odróżnienia syntetycznych fixture od realnego pochodzenia. Wymagamy osobnych metryk realnych i technicznie dopuszczonych danych; [Issue #23](https://github.com/gniewkob/Investment-Strategy-Lab/issues/23). Zadanie [#22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6269776862) skorygowano o fakt celowej syntetyczności. Dotychczasowy problem importu WTI i [#21](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21) (ucina 10 zdarzeń w module jakości) pozostają otwarte. Przed jakimkolwiek twierdzeniem o point-in-time dla **prawdziwych** danych konieczne jest rekordowe pochodzenie, data publikacji i retrieval — **0 realnych wersjonowanych obserwacji aktualnie spełnia tę bazę**. Legacy `price_observations=3711` nadal `UNVERIFIED_HISTORICAL_PUBLICATION`.

Nie zmieniano danych, ról, ACL, sekretów, produkcji, harmonogramów, kodu analitycznego, transakcji ani żadnych alokacji. Badania wyłącznie edukacyjne, M1/M2/M3 `HOLD_NO_CHANGE`.

## Kontynuacja P1 — 19.10.2026: diagnostyka read-only bez backfill

Po ponownym sprawdzeniu `main` (przed dopisaniem tej sekcji HEAD `b085d665`) issue [#21](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21) i [#22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22) nadal `OPEN`, brak PR wdrażającego usunięcie błędu i brak zmian w `reference_data_quality.py`. Nie próbować obchodzić poprzedniego zablokowanego zapisu kodu.

**Nowe twarde dowody:**
- Niezależny read-only SQL policzył **15** różnic BTC/ETH z |z| ≥ 2.5 (20 wcześniejszych okresów); radar pokazuje tylko ostatnie **10**; **5** nie jest wyświetlanych. **Jeden** skrajny |z| ≥ 8 (19.08.2026, 16.2658) nadal znajduje się na miejscu **2** najnowszych alarmów; **0** skrajnych zostało dotąd faktycznie pominiętych. Błąd listy 10 jest **potencjalnym przyszłym false negative**, nie udowodnioną aktualną awarią. Pełny dowód w [Issue #21 komentarz](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21#issuecomment-6269596457).
- Oficjalny [EIA Cushing WTI daily](https://www.eia.gov/dnav/pet/hist/RWTCD.htm) vs SELECT LEFT JOIN na Neon STAGING: 24.08 = 86.34 i 25.08 = 83.90 **zgadzają się**; 26.08 = 83.46, 27.08 = 84.81, 28.08 = 84.57, 31.08 = 87.03, 01.09 = 91.48, 02.09 = 92.15, 03.09 = 92.55, 04.09 = 92.69 **brakuje** w Neon. Na 10 porównanych dat: 2 dopasowania, 8 braków; **ZERO insert/update**. Dowód w [Issue #22 komentarz](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6269597149).
- Sprawdzono drzewo `main` (61 pozycji) i GitHub code search: **nie ma w obecnym repo skryptu źródłowego importu/ETL WTI**. Znalezione odniesienia WTI są jedynie w module jakości, radarze, bridge oraz teście. Dlatego **nie ustalono jeszcze przyczyny** ucięcia ETL i nie ma bezpiecznej podstawy do samoczynnego backfillu. Wymagane odnalezienie oryginalnego procesu importu/źródła spoza obecnego kodu, nie tworzenie nowego zapisu w ciemno.
- Wersjonowane provenance dalej: 3 `source_documents`, 3 `price_observation_versions` (wszystkie `nbp_gold`), `prices_asof(now())` = 1, jedna próbka ze znacznikiem `retrieved_at` w przyszłości względem aktualnego czasu serwera, legacy 3711 rekordów bez potwierdzenia PIT. `UNVERIFIED_HISTORICAL_PUBLICATION` bez zmian.

**Granica:** żadnych zapisów bazy, sekretów, schematów, produkcji, uzupełnienia cen, wdrażania strategii, harmonogramów ani handlu. M1/M2/M3 `HOLD_NO_CHANGE`. Priorytet naprawy to rozdzielenie pełnej populacji anomaliów od listy prezentacyjnej i odtworzenie ETL z niezależnym provenance. Nie wolno deklarować CI PASS dla niewdrożonej poprawki.

## Aktualizacja — 19.10.2026, audyt źródeł i blokery P1 (tylko odczyt)

Po pierwszym udanym v0.2 przebiegu ponownie przeprowadzono **wyłącznie odczyt** na izolowanym Neon STAGING `br-wandering-union-ba6ogf6l`; bez zmian produkcji, danych, uprawnień, tokenów, alokacji, harmonogramów i zleceń.

- **Provenance vs legacy:** `investment_lab.price_observations` = 3711 historycznych cen (backfill 17.10), natomiast `source_documents` = 3 oraz `price_observation_versions` = 3, wszystkie wyłącznie `nbp_gold`. `prices_asof(now())` zwróciło **1** dopuszczalny rekord, **1** wersjonowana obserwacja posiada znacznik `retrieved_at > now()` (najpóźniej 20.10.2026), `source_code` mismatch = 0. Prawidłowa walidacja PIT dla historycznego BTC/ETH, ropy i gazu jest nadal **niemożliwa**.
- **WTI:** lokalna tabela zawiera 660 punktów do 25.08.2026; Brent 706 do 14.10.2026. 56 dat Brent nie ma w WTI, z czego 35 po odcięciu serii. Oficjalna [EIA Cushing WTI](https://www.eia.gov/dnav/pet/hist/RWTCD.htm) potwierdza 25.08 = 83.90, 26.08 = 83.46, 27.08 = 84.81 i 28.08 = 84.57 USD/bbl. Przyczyna ucięcia importu nieustalona. Porównanie do kalendarza Brent to proxy, nie kanoniczna lista publikacji WTI.
- **P1 code integrity:** `reference_data_quality._extreme_relative_moves` korzysta z `opportunity_radar._btc_eth_divergence().recent_divergence_events`, ograniczonych do ostatnich **10**. Stara skrajna anomalia może zniknąć z jakości po dodaniu dalszych zwykłych odchyleń. Kontrola jakości powinna badać pełne zweryfikowane wejście niezależnie od listy prezentacyjnej; wymagane synthetic regression, no look-ahead i fingerprint fail closed.
- **Blokada wdrożenia:** poprzednia próba zapisu poprawki do `scripts/reference_data_quality.py` została zablokowana przez mechanizm bezpieczeństwa narzędzia. Nie ma poprawki, testów nowego kodu ani PR/merge. Istnieje niedokończona gałąź `fix/complete-extreme-anomaly-quality-gate` bez poprawki; nie obchodzić blokady narzędzi.
- Dwa dedykowane zadania z wymaganiami odbioru: [Issue #21 — jakość nie może zależeć od listy przyciętej do 10 zdarzeń](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21); [Issue #22 — WTI ETL/provenance/PIT, przyszły retrieval timestamp](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22). W obu **brak zgody na zapisy do Neon i operacje finansowe**. Wszystkie modele M1/M2/M3 pozostają `HOLD_NO_CHANGE`, vintage `UNVERIFIED_HISTORICAL_PUBLICATION`.

## v0.2 — PIERWSZY REALNY STAGING RUN ZALICZONY (19.10.2026)

Po wdrożeniu PR #19 i #20 użytkownik ręcznie uruchomił [GitHub Actions run #39245012461](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39245012461) (commit `fc9c5a2`). Run **SUCCESS**; `LEGACY_HISTORY_RESEARCH_OK observations 3711 series 8 hypotheses_for_review 2 orders 0 database_writes 0`. Pobraną i niezależnie otwartą paczkę [artifact #12182926287](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39245012461/artifacts/12182926287) (ZIP SHA256 `5b02af2eac25e49ac181f6d81934acf53914a06fcc54ee9a8ed750d21f139d19`, 7 plików, expiry 26.10) sprawdzono pod kątem manifestu, quality, ledger i robustness.

- **Dane identyczne z v0.1:** fingerprint `5f2b7f788c9723be729ba6ab612751b0ce11b0901b73a78a0473f4129a6e7798`, 3711 obserwacji, 8 serii analizowanych, 62 anomalie, 47 niepokrywających się zdarzeń, 15 odrzuconych nałożeń. Hipotezy do dalszego badania spadły z **4 do 2** wyłącznie z powodu jakości.
- **Do badania:** Brent (12 niezależnych zdarzeń) i Henry Hub (6), wyłącznie `INVESTIGATE_RESEARCH_ONLY`. To NIE jest potwierdzona przewaga ani zakup.
- **`DATA_QUALITY_BLOCKED`:** WTI (STALE_DATA 55.479 dnia oraz PEER_COVERAGE_GAP: 56 brakujących dat względem Brent, z czego 35 po 25.08.2026), ETH i BTC (SOURCE_REVALIDATION_REQUIRED: rozbieżność 19.08.2026 z |z|=16.2658 i MAD robust |z|=18.32).
- **Niewystarczające dowody:** złoto NBP, EUR/PLN, USD/PLN; BTC miało za mało niezależnych zdarzeń również w poprzednim przebiegu.
- **Kluczowy wynik benchmarku:** naive last-bar sign na *identycznych datach* trafia dokładnie tyle samo co znak z-score dla **każdej z 8 serii**; `event_vs_same_date_naive_consistency_pp=0.0` we wszystkich. Brent 50/50%, Henry Hub 50/50%, ETH 66.67/66.67%, WTI 54.55/54.55%, BTC 75/75%. Na tym materiale **brak dowodu dodatkowej skuteczności kierunkowej ponad banalny znak poprzedniego ruchu**, brak istotności i efektu przyczynowego.
- **Bezpieczeństwo:** `UNVERIFIED_HISTORICAL_PUBLICATION`, 0 macro verified events, 0 writes, 0 orders, 0 virtual allocation changes, brak dostępu do prywatnych portfeli, brak surowych cen w artefakcie, brak scheduler; wszystkie M1/M2/M3 `HOLD_NO_CHANGE`. Test tylko odczytowy; bez zmian konfiguracji i produkcji.
- **Dalsze prace:** zweryfikować WTI z [EIA](https://www.eia.gov/dnav/pet/hist/RWTCD.htm), źródła BTC/ETH i autentyczne daty historycznej publikacji, dopiero potem holdout/cross-validation, bez dopasowywania do wyników in-sample. Nie deklarować przewagi, nie uruchamiać automatycznej alokacji. Szczegóły [Issue #4, zapis weryfikacji](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4#issuecomment-6266207530).

## Wdrożenie v0.2 — 19.10.2026

## 19.10.2026 — Opportunity Radar v0.2 Data Quality & Evidence Gate WDROŻONE (CI-only; live staging nieuruchomiony)

Scalono [PR #19](https://github.com/gniewkob/Investment-Strategy-Lab/pull/19) (squash commit `ff9891bdfaed3c7d92db7b5950db132efcb91dbb`) oraz follow-up [PR #20](https://github.com/gniewkob/Investment-Strategy-Lab/pull/20) (squash `db2da856a4d1a38dae79a4ea581b3321409e2163`). Są już na `main`.

- Nowy czysto offline `scripts/reference_data_quality.py` z kontrolą wieku danych względem `snapshot.as_of`: 4 dni dla dziennego BTC/ETH, 10 dni dla innych dziennych, 75 dni dla miesięcznych. To **lokalnie dobrane progi heurystyczne**, nie regulacyjne; „świeżość” nie potwierdza historycznej daty publikacji.
- Kontrola pokrycia kalendarza referencyjnego EIA WTI względem Brent: 56 dat Brent nieobecnych w WTI (w tym 35 po ostatniej dacie WTI 25.08.2026), niezależnie od przyczyny braku. `STALE_DATA` / `PEER_COVERAGE_GAP` blokują **promocję hipotez badawczych**, nie przeprowadzają importu.
- Ekstremalna rozbieżność BTC/ETH (|z|≥8) dodaje `SOURCE_REVALIDATION_REQUIRED` dla obu serii i diagnostykę odporną na anomalie (MAD). Wcześniejsza niezależna kontrola Neon obliczyła dla 19.08.2026 ok. klasyczne z = -16.266, odporne = -18.32; to nadal **nie jest zweryfikowany sygnał prognostyczny**.
- `evidence_decision_ledger.make_ledger` w pełnym pipeline odczytuje fingerprint-bound quality report i klasyfikuje takie hipotezy `DATA_QUALITY_BLOCKED` / `RESOLVE_DATA_QUALITY`, zamiast `INVESTIGATE_RESEARCH_ONLY`. Nie zmienia decyzji M1/M2/M3 `HOLD_NO_CHANGE`.
- Walidator niepokrywających się okien raportuje teraz banalny benchmark utrzymywania znaku ostatniego ruchu na **tych samych datach** co zdarzenia. Różnice są czysto opisowe, bez deklaracji przewagi lub efektu przyczynowego.
- `opportunity_research_pipeline` dodaje `reference_data_quality.json` i podsumowanie do raportu/manifestu; `legacy_history_bridge.run_and_report` też eksportuje tylko zagregowany `reference_data_quality.json` do istniejącego manualnego artefaktu. Nie publikuje surowych notowań ani sekretów.
- Rozbudowane testy syntetyczne, w tym kontrola WTI, anomalii BTC/ETH, fingerprint fail-closed, niezależności od alokacji i braków uprawnień. **128 testów PASS** w offline CI PR #19; cztery workflow CI na finalnym head oraz na `main` po merge #19 przeszły sukcesem. Uzupełniający bridge CI PR #20 PASS. Zlikwidowano istniejące SyntaxWarning w dwóch raportach Markdown.
- **Nie uruchomiono** po tych zmianach workflow `legacy-history-research.yml` na prawdziwym Neon STAGING. Nie zmieniano produkcji, bazy danych, ACL, ról, haseł, sekretów, cen, wirtualnych alokacji, harmonogramów ani zleceń. `UNVERIFIED_HISTORICAL_PUBLICATION` obowiązuje nadal.

**Kolejny krok:** manualny, osobno zatwierdzony jednorazowy przebieg `legacy-history-research.yml` na `main`, weryfikacja logów i agregatowego artefaktu quality; potem praca nad kompletnością źródła WTI i walidacją dat publikacji Coinbase/EIA. Żadnych zautomatyzowanych działań finansowych.

## STAN NAJNOWSZY — 19.10.2026, pierwszy historyczny bridge na STAGING wykonany pomyślnie

Użytkownik ręcznie uruchomił [Historical reference research bridge, GitHub Actions #39241685091](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39241685091) na `main`, commit `500d87895401d62bf68a7a6a872ffeb51850e166`. Workflow zakończył się **SUCCESS** i wypisał `LEGACY_HISTORY_RESEARCH_OK observations 3711 series 8 hypotheses_for_review 4 orders 0 database_writes 0`. To **rzeczywisty workflow w GitHub z połączeniem do STAGING**, a nie offline CI. Osobny sekret `NEON_HISTORICAL_READ_DATABASE_URL` zadziałał (bez odczytu jego wartości w rozmowie). Znalazł się w chronionym GitHub Environment `research-staging`, nie w repo.

Pobrano i przeanalizowano kompletny agregatowy [artefakt #12181127705](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39241685091/artifacts/12181127705), zawierający `manifest.json`, `radar.json`, `ledger.json`, `robustness.json`, `context.json`, `research_report.md`. Dane: 3711 wierszy, 12 serii referencyjnych, 8 analizowanych. 62 retrospektywne nietypowe zdarzenia, 47 niepokrywających się okien, 15 pominiętych nałożeń. **4 pytania badawcze**: Brent 15 raw/12 nonoverlap, WTI 13/11, Henry Hub 9/6, ETH 7/6. **INSUFFICIENT_EVIDENCE:** BTC 8/4, NBP gold 5/3, EUR/PLN 3/3, USD/PLN 2/2. Brak zweryfikowanych zdarzeń makro/geopolitycznych, brak dowodu na skuteczność predykcyjną. Klasyfikacja **INVESTIGATE_RESEARCH_ONLY to nie wskazanie inwestycyjne**.

Bezpieczeństwo: `source_vintage=UNVERIFIED_HISTORICAL_PUBLICATION`, `raw_price_exported_as_artifact=false`, `portfolio_tables_accessed=false`, `database_writes=0`, `real_orders=0`, `paper_fills=0`, `hypothetical_allocation_changes=0`, `schedule_enabled=false`. Trzy M1/M2/M3: `HOLD_NO_CHANGE`. Brak zmian produkcji, brak eskalacji ACL, brak dostępu do brokera. Artefakt ważny przez 7 dni, do 26.10.2026. Szczegóły i źródła: [Issue #4 — komentarz weryfikacyjny](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4#issuecomment-6265732022).

**Nowy blocker (zamiast credentials):** merytoryczna gotowość danych i metod: rzeczywista chronologia publikacji i wersjonowanie źródeł (legacy nadal unverified), opóźnione WTI (ostatnia data 25.08.2026), walidacja z-score 16+ przy rozbieżności BTC/ETH, zewnętrzne benchmarki/oos, kompletne szeregi PLN total-return i koszty. Sekret i połączenie **zadziałały**, ale nie oznacza to gotowości decyzji ani regularnej automatyzacji. W logach są niewstrzymujące `SyntaxWarning` (escape backticks) i Node20 deprecation GitHub Actions. Historyczne akapity poniżej dokumentują wcześniejsze blokady, aktualnie **rozwiązane**.

## NAJNOWSZY stan — 19.10.2026: skuteczna inicjalizacja pierwszego hasła historycznego czytnika

Użytkownik przypomniał sprawdzone rozwiązanie problemu resetu `PASSWORD NULL`. W [Issue #3](https://github.com/gniewkob/Investment-Strategy-Lab/issues/3) oraz w pierwotnej dokumentacji `NEON_LEAST_PRIVILEGE_PL.md` (gałąź Draft PR #1) odnotowano sukces dla `isl_agent_staging_limited` z 18.10.2026: jednokrotny `DO`, 3 × losowy `gen_random_uuid()` po stronie bazy, dynamiczny `ALTER ROLE`, kontrola `rolpassword IS NOT NULL`. Ten mechanizm **zastosowano teraz po wcześniejszej jawnej zgodzie na aktywację credentials** również do nowej `isl_legacy_history_reader` na staging `br-wandering-union-ba6ogf6l`.

Bezpośredni SQL postflight: `rolcanlogin=true`, **`rolpassword IS NOT NULL=true`**, `rolsuper=false`, `rolcreatedb=false`, `rolcreaterole=false`, `rolbypassrls=false`; SELECT na dokładnie jednym obiekcie `investment_lab.price_observations`, zero write/CREATE, brak `holding_snapshots` SELECT, istniejący agent nie dostał dostępu do legacy. Odczyt produkcji potwierdził brak tej roli na gałęzi `main`. Początkowe hasło jest niedostępne (nie zostało zwrócone, zapisane w repo/rozmowie ani przekazane do narzędzia).

**Blokada pierwszego hasła usunięta.** Wymagane: w Neon Console użyć **Reset password** istniejącej roli (tylko prywatnie), zapisać końcowe hasło w menedżerze, ustawić oddzielny chroniony GitHub Environment Secret `NEON_HISTORICAL_READ_DATABASE_URL`. Podłączony GitHub connector nie wspiera zapisu sekretu. Nie potwierdzono jeszcze finalnego resetu ani sekretu. Nie wysyłać hasła/DSN przez chat; nie przeprowadzać kolejnego bootstrapu. Manualny history bridge nieuruchomiony; brak harmonogramu, zleceń i zmian portfela. Instrukcja: [HISTORICAL_LOGIN_BOOTSTRAP_PL.md](HISTORICAL_LOGIN_BOOTSTRAP_PL.md).

## WCZEŚNIEJSZY stan — 19.10.2026, druga zgoda: LOGIN włączony, poświadczenie NIEGOTOWE

Po jawnej **drugiej zgodzie** użytkownika na aktywację roli i skonfigurowanie poświadczenia w GitHub, wykonano na izolowanej Neon STAGING gałęzi `br-wandering-union-ba6ogf6l` bezpieczny `ALTER ROLE isl_legacy_history_reader LOGIN` z pełnym sprawdzeniem dotychczasowych uprawnień. Bezpośredni odczyt `pg_authid` po operacji potwierdził:

- `rolcanlogin=true`;
- `rolpassword IS NOT NULL=false` (hasło **nie zostało ustawione**);
- pozostałe uprawnienia i bezpieczne ograniczenia bez zmian: SELECT tylko do legacy `price_observations`, brak SELECT do `holding_snapshots`, brak superuser/createdb/createrole/bypassrls.

Wywołanie interfejsu Neon `reset_postgres_role_password` nie powiodło się; późniejsza kontrola SQL potwierdziła brak hasła. Neon control-plane `get_postgres_role` nadal podawał `authentication_method=no_login` pomimo rzeczywistego `rolcanlogin=true`; potrzebna ostrożna weryfikacja tej niespójności przy konfiguracji hasła. GitHub connector nie zapewnia zapisu Environment Secrets, więc `NEON_HISTORICAL_READ_DATABASE_URL` **nie został skonfigurowany**, a żaden manualny workflow nie został uruchomiony. Nie wysyłać sekretów przez czat ani do repo.

Dalszy etap jest opisany w [HISTORICAL_LOGIN_BOOTSTRAP_PL.md](HISTORICAL_LOGIN_BOOTSTRAP_PL.md). **Nie resetować hasła ponownie przez API na ślepo, nie zmieniać ACL, nie uruchamiać bridge przed bezpieczną aktywacją i potwierdzeniem dostępu.** Poniższa sekcja `0. AKTUALIZACJA po snapshot` opisuje wcześniejszy etap `NOLOGIN` i jest zachowana jako historia.

## 0. AKTUALIZACJA po snapshot — 19.10.2026: staging reader utworzony

**To jest nowszy, obowiązujący stan niż poniższy historyczny snapshot z ok. 07:11 UTC.** Użytkownik udzielił jawnej zgody wyłącznie na stworzenie odizolowanej roli `isl_legacy_history_reader` `NOLOGIN` na Neon STAGING (`br-wandering-union-ba6ogf6l`; projekt `red-lake-53043722`; baza `investment_lab`). Zastosowano istniejący przejrzany `db/security/legacy_history_reader_STAGING_REVIEW.sql` jako pojedynczą transakcję PostgreSQL; wszystkie pięć instrukcji zakończyło się bez błędów.

- **Zweryfikowane po wykonaniu:** rola istnieje z `NOLOGIN`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOBYPASSRLS`. W schemacie `investment_lab` efektywny SELECT dotyczy dokładnie **jednej tabeli**: `price_observations`. Zero uprawnień modyfikacji tabel/widoków, brak `CREATE` na schemacie i bazie. Połączenie do bazy i USAGE schematu są przyznane zgodnie z projektem.
- Istniejący `isl_agent_staging_limited` nadal NIE MA SELECT na `price_observations` ani `holding_snapshots`; **na produkcyjnej gałęzi `br-shy-voice-badzlf0x` nowa rola nie istnieje**.
- Systemowa relacja `pg_auth_members`: `investment_lab_owner` jest administracyjnym członkiem nowej roli (grantor `cloud_admin`, `admin_option=true`, `inherit_option=false`, `set_option=false`). Nowa rola nie jest członkiem innych ról. Nie ustanowiono jej osobnego loginu.
- **NIE USTAWIONO** hasła, `LOGIN`, sekretu GitHub `NEON_HISTORICAL_READ_DATABASE_URL`, workflow historycznego, harmonogramu, zleceń, zapisów danych rynkowych ani wirtualnych zmian alokacji.
- Dziennik wykonania: [Issue #4, komentarz 6264735926](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4#issuecomment-6264735926).

**Nowy najbliższy krok:** Uzyskać **świeżą, odrębną zgodę użytkownika** na ewentualne uruchomienie loginu i bezpieczne skonfigurowanie oddzielnych danych uwierzytelniających do staging (nigdy owner DSN). Dopiero później — po ponownej weryfikacji praw/host/CA i sekrecie w chronionym GitHub Environment — możliwy jest **manualny** odczyt raportu z `legacy_history_bridge.py`. Nie wykonywać ponownie `CREATE ROLE`. Pozostałe części niniejszego dokumentu opisują **starszy snapshot**, więc wzmianki o „braku roli” nie są aktualne. Vintage `UNVERIFIED_HISTORICAL_PUBLICATION` pozostaje obowiązujące.

## 1. Co użytkownik faktycznie chce

Docelowy cel to **Opportunity & Decision Intelligence**, nie zwykły automat od równoważenia portfela.

- Identyfikować **potencjalnie interesujące anomalie i rozbieżności** na rynkach w sposób odtwarzalny.
- Łączyć historyczne zachowanie referencyjnych cen, publikowane dane ekonomiczne i udokumentowany kontekst geopolityczny.
- Stawiać **falsyfikowalne hipotezy badawcze**, zbierać dowody za/przeciw i porównywać je z prostymi benchmarkami i scenariuszem **HOLD_NO_CHANGE**.
- Dopiero przy odpowiedniej jakości danych analizować **alternatywne, wirtualne** alokacje i ich hipotetyczne konsekwencje; nie utożsamiać wysokiego z-score ze wskazaniem do zakupu.
- AI/LLM ma pomagać analizować i wyjaśniać dokumentację, **nie wymyślać cen, dat publikacji, prawdopodobieństw sukcesu ani transakcji**.

Wcześniejsza wizja: 3 modele M1/M2/M3, edukacyjny budżet symulacyjny 100 PLN/miesiąc, horyzont badawczy 3–5 lat. Kwota jest **wirtualna** i modele są **alternatywami**, nie trzema równoległymi wpłatami. Obecna wyższa preferencja użytkownika: **radar okazji + retrospektywne testy + uzasadnianie alternatyw**, zamiast sztywnego odtwarzania alokacji.

**Interpretacja klasyfikacji badawczych:** `OBSERVE`, `INVESTIGATE_RESEARCH_ONLY`, `INSUFFICIENT_EVIDENCE`, `HOLD_NO_CHANGE` to etykiety **badań**, nie sygnały finansowe. Obecny kod Opportunity Radar **nie zmienia nawet wirtualnej alokacji**.

## 2. Rejestr systemów i aktualny GitHub

| Komponent | Zweryfikowany stan |
| --- | --- |
| Repozytorium | https://github.com/gniewkob/Investment-Strategy-Lab — **publiczne** |
| `main` w chwili snapshotu | `9e64ae1190c6f9fb9a220bb8b9a4a4223dd6b7cf`, squash PR #17 |
| Pełny PR architektoniczny | [Draft PR #1](https://github.com/gniewkob/Investment-Strategy-Lab/pull/1), gałąź `feature/autonomous-agent-v2-review`, **nie scalony** |
| Główny backlog / dziennik | [Issue #4](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4), zawiera wcześniejsze decyzje i sekwencję PR |
| Kontrole roli i migracji | [Issue #3](https://github.com/gniewkob/Investment-Strategy-Lab/issues/3) |
| Technologia | Python 3.12, `psycopg` 3, GitHub Actions, Neon PostgreSQL, odtwarzalne JSON/Markdown |
| `main` zawiera | Preflight staging, manualny canary dziennika, manualny pełny runner, manualny audyt PIT, Opportunity Radar i evidence ledger, kontekst makro/geopolityczny, walidację niezależnych okien, read-only legacy history bridge oraz **tylko szkic SQL roli** |
| Ostatnie znane CI | [Run 39213233300](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39213233300) — sukces testów ACL na jednorazowym PostgreSQL |
| Automatyczne uruchamianie badanego agenta | **Wyłączone**. Istnieją ręczne `workflow_dispatch`; brak harmonogramu dla pełnego runnera i mostu historycznego. |

**Ważne:** `docs/` na `main` przed tym handoff zawiera `OPPORTUNITY_RADAR_PL.md` oraz `HISTORICAL_REFERENCE_BRIDGE_PL.md`. Inne pliki, np. `AUTONOMOUS_AGENT_V2_PL.md`, `EIA_SOURCE_INGEST_PL.md`, `NEON_LEAST_PRIVILEGE_PL.md`, żyją na **Draft PR #1**, nie udawaj, że są częścią `main`. Kluczowe moduły pełnego runnera przeniesiono na `main` odrębnym PR #10, lecz nie scalono całego PR #1.

## 3. Neon — stan POTWIERDZONY przez odczyt SQL

Projekt Neon: `red-lake-53043722`; baza `investment_lab`.

| Gałąź | ID | Stan |
| --- | --- | --- |
| **PRODUCTION / main** | `br-shy-voice-badzlf0x` | 16 tabel bazowych; **brak `agent_cycles` i schematu agenta v2**; NIE MODYFIKOWAĆ |
| **STAGING** | `br-wandering-union-ba6ogf6l` | 24 tabele; repozytorium prowadzi tu odczyty i kontrolowane eksperymenty |

Odczyt staging z **2026-10-19, 07:11 UTC**:

- `investment_lab.price_observations` — **3711** historycznych wierszy referencyjnych (legacy).
- `investment_lab.price_observation_versions` — **3** wersjonowane rekordy; `prices_asof(now())` — **1** kwalifikujący się rekord PIT.
- `agent_cycles` — **5** zapisanych eksperymentów; `agent_paper_decisions` — **15**; `agent_hypotheses` — **0**.
- `isl_agent_staging_limited` **istnieje** i ma ograniczone prawa do dziennika / źródeł PIT. **Nie ma** dostępu `SELECT` do legacy `price_observations` ani do prywatnych tabel portfeli. Nie zwiększać mu praw.
- `isl_legacy_history_reader` **NIE ISTNIEJE** — odczyt `pg_roles` to potwierdził. Nie zakładać, że istnieje sekret do historycznych danych.

Jedna wersja źródła staging ma `retrieved_at/recorded_at=2026-10-20T10:00:00Z`, czyli wartość **przyszłą** wobec wskazanego wyżej czasu odczytu. Filtr PIT ją wyłącza. To anomalia chronologiczna w danych testowych, a nie przyzwolenie na cofanie dat. Nie usuwać lub „naprawiać” rekordów bez osobnej analizy i zgody.

### Dostępne legacy history — zgrubna mapa pokrycia

| Seria | Liczba historycznych punktów | Typ |
| --- | ---: | --- |
| Brent | 706 | dzienny, referencyjna cena spot |
| WTI | 660 | dzienny, referencyjna cena spot |
| Henry Hub | 695 | dzienny, referencyjna cena spot |
| BTC/USD | 381 | dzienny, referencyjna cena spot |
| ETH/USD | 381 | dzienny, referencyjna cena spot |
| Złoto NBP PLN/g | 264 | dzienny, referencyjna cena/proxy |
| EUR/PLN, USD/PLN | po 264 | dzienny kurs walutowy |
| Miedź, aluminium, nikiel, srebro (World Bank) | po 24 | miesięczne wartości referencyjne |

Sumarycznie 3711 punktów legacy, zaimportowanych do starej tabeli **w październiku 2026**, bez autentycznie odtworzonych historycznych `published_at`/vintage. **Nie** jest to materiał do certyfikowanego PIT backtestu ani automatycznej decyzji o wirtualnej zmianie udziałów. Służy do **retrospektywnego opisu i testowania pytań badawczych**.

Oryginalne wirtualne modele M1/M2/M3 używają `EQUITY_TR_PLN`, `BONDS_TR_PLN`, `GOLD_TR_PLN` i wymagają walidowanych **PLN total-return**. Legacy `PRICE_ONLY` dla BTC/złota/ropy oraz World Bank monthly average nie są takimi szeregami. Również obecny constraint `value_concept` w v2 **nie zawiera** `TOTAL_RETURN_INDEX`; wymaga osobnego przeglądu kontraktu/schema. Nie maskować tego przemianowaniem pól.

## 4. Co już naprawdę działało na staging (historyczne dowody)

Wszystkie poniższe próby wykonano ręcznie, na TESTOWEJ gałęzi i bez brokerów:

1. **Preflight SSL i ACL**, [run #39157477363](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39157477363): `READ_ONLY_TLS_VALIDATED`, `staging_marker_verified=true`, 1 obserwacja PIT, zero zapisów.
2. **Syntetyczny dziennik SQL**, `staging-paper-smoke-2026-10-18-v2`: ograniczona rola dopisała trzy `HOLD_CASH`, zero transakcji, idempotentny replay bez duplikatu.
3. **GitHub syntetyczny canary**, [run #39159505268](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39159505268): wpis `github-staging-canary-2026-10-18-utc07-v1`, 3 `HOLD_CASH`, replay 0 duplikatów, `paper_fills=0`, `real_orders=0`; artefakt raportu.
4. **Rzeczywisty `agent_runner.execute()`**, [run #39160519453](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39160519453): dwa przebiegi przy stałym cutoff `2026-10-18T07:00:00Z`, `daily-research-2026-10-18`, 1 obserwacja PIT, 3 `HOLD_CASH`, 0 hipotez, 0 fills, 0 orders, 0 duplikatów. Raport `cycle.json`, `report.md`, `manifest.json`.
5. **PIT quality audit**, [run #39161607764](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39161607764): workflow technicznie SUCCESS, ale diagnoza **`MARKET_DATA_NOT_READY`**, 1 rekord PIT, 1 przyszła data ingestu i 3 ostrzeżenia. Sukces audytu NIE oznacza gotowości danych do modelowania.

Pozostają NIEPOTWIERDZONE: automatyczny import wiarygodnych vintage, regularne dane typu total-return, 14 niezależnie obserwowanych cykli, aktywne alerty, wiarygodna skuteczność predykcyjna, rzeczywisty historyczny bridge z dedykowaną rolą. **Nie twierdzić, że produkcyjny agent albo autonomiczna strategia są gotowe.**

## 5. Opportunity & Decision Intelligence na `main`

Istniejące moduły, których nowa sesja nie powinna pisać od zera:

| Moduł | Funkcja |
| --- | --- |
| `scripts/opportunity_radar.py` | retrospektywny opis anomalii, chronologiczne okna, bazowy z-score i porównanie referencyjnych zmian |
| `scripts/nonoverlap_validation.py` | ogranicza nachodzenie pięciobarowych okien, porównuje z naiwnym kierunkiem i siatką benchmarku |
| `scripts/evidence_decision_ledger.py` | klasyfikuje **pytania do badania** na podstawie siły dowodów i ich braków |
| `scripts/economic_geopolitical_context.py` | waliduje zadane źródła, daty, kategorie makro/geopolityczne, kontrargumenty; **nie pobiera newsów sam** |
| `scripts/opportunity_research_pipeline.py` | spójny manifest, hash, radar, walidacja, evidence ledger, kontekst, Markdown |
| `scripts/opportunity_demo_fixture.py` | **fikcyjne** deterministyczne ceny do bezpiecznego testu offline |
| `scripts/legacy_history_bridge.py` | odrębny, staging-only, **read-only** most do starszych cen; obecnie zablokowany brakiem dedykowanego konta |
| `scripts/staging_preflight.py` / `staging_data_audit.py` | bramka połączenia/ACL/CA oraz diagnostyka jakości PIT |
| `src/isl_v2/agent_runner.py` i `autonomous_agent.py` | istniejący manualny, ograniczony runner v2 z testowym `HOLD_CASH` |

Wersja Radar v0.1: `20` wcześniejszych stóp zmian, próg `abs(z)>=2.5`, horyzont `5` barów, opisowy podział chronologiczny ok. 65/35. Ledger wymaga min. **5 niepokrywających się zdarzeń** i **12 niezależnych okien gridu** (oraz wcześniej ustalonych progów raw/holdout) do samego priorytetu `INVESTIGATE_RESEARCH_ONLY`. Ani ten próg, ani retrospektywny holdout **nie dowodzą przewagi nad benchmarkiem lub zdolności prognozowania**. Brak prawdziwych cen wykonania, opłat, weryfikowanych vintage i pełnych total-return.

Pipeline z syntetycznym fixture wykazał w CI 2 serie, 8 surowych zdarzeń, **0** pytań przechodzących bramkę odporności, **0** zmian udziałów, 0 DB writes i 0 orders. To fikcyjne testy, nie bieżące odkrycia rynkowe. Osobny diagnostyczny odczyt SQL na realnym legacy policzył historyczne odstępstwa (m.in. Brent 16/243 okien; BTC 8/129; ETH 8/129), **bez dowodu prognostycznej skuteczności**.

### Uruchomienie wyłącznie offline — bez kont i sekretów

```bash
python -m unittest discover -s tests -v
python -m scripts.opportunity_demo_fixture --output /tmp/isl-synthetic-snapshot.json
python -m scripts.opportunity_research_pipeline --input /tmp/isl-synthetic-snapshot.json --out-dir /tmp/isl-educational-report
```

Pliki wyjścia: `radar.json`, `decision_ledger.json`, `economic_geopolitical_context.json`, `nonoverlap_validation.json`, `manifest.json`, `research_report.md`. To **fałszywe ceny**, bez rzeczywistych danych. Nie kopiować raw history z Neon do publicznego repo ani GitHub artifacts.

## 6. Chronologia kluczowych PR i dowodów CI

- **PR #1**: historyczny duży beta pakiet v2 — **Draft, unmerged**.
- **PR #5–8**: preflight i poprawki (dokładny endpoint, pełny TLS z CA, Neon TLS proxy) — przeniesione do `main`.
- **PR #9**: ręczny syntetyczny test zapisu dziennika — merged.
- **PR #10**: wydzielony rzeczywisty runner staging, nadal manualny — merged; 47 testów offline [run #39160285215](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39160285215).
- **PR #11**: manualny data-quality audit — merged, 59 testów offline [run #39161440655](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39161440655).
- **PR #12–15**: Opportunity Radar → ledger → zdarzenia makro/geopolityczne → walidacja niepokrywających się okien — merged; 110 testów pipeline [run #39182839391](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39182839391).
- **PR #16**: `legacy_history_bridge.py`, nowy ręczny workflow i osobny sekret — merged; 121 offline tests [run #39211363418](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39211363418). **Nie uruchomiono przeciw Neon z historyczną rolą**.
- **PR #17**: `db/security/legacy_history_reader_STAGING_REVIEW.sql`, testy ACL wyłącznie na jednorazowym PostgreSQL; merged `9e64ae1`; [run #39213233300](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39213233300) success. **Nie tworzy żadnej roli w Neon.**

Wcześniej wykonane kroki są w opisach PR oraz [Issue #4](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4). Lista powyżej nie upoważnia do wykonywania migracji ani ustawiania sekretów.

## 7. Tożsamości i zasady bezpieczeństwa — NIE NEGOCJOWAĆ

**Publiczny GitHub:** żadnych haseł, prywatnych URL zawierających credentials, kluczy, seed phrase/walletów, realnych sald/portfolio, cen surowych na cudzej licencji, tokenów lub zrzutów poufnych logów.

- GitHub Environment `research-staging`: `NEON_RESEARCH_DATABASE_URL` jest skonfigurowany przez użytkownika (dowodem są udane staging workflows). Nie pobierać ani nie wypisywać wartości. To ograniczony `isl_agent_staging_limited`, nie owner.
- Zaplanowany `NEON_HISTORICAL_READ_DATABASE_URL` jest **oddzielnym** sekretem do `isl_legacy_history_reader`; jego konfiguracja **nie została potwierdzona**, ponieważ sama rola nie istnieje.
- Neon staging direct compute jest zakodowany/allowlistowany w kodzie. Wymagany `sslmode=verify-full`, root CA i host-check; **nie obniżać do `sslmode=require`**. Sekrety wyłącznie w uprawnionym, chronionym środowisku, nie w PR/push.
- `isl_agent_staging_limited` pozostaje bez `SELECT` na legacy `price_observations`; bez zapisu do source evidence i prywatnych tabel. NIE GRANTOWAĆ mu dodatkowych uprawnień.
- PR #17 **jedynie proponuje** `isl_legacy_history_reader NOLOGIN` z SELECT na market reference legacy. `db/security/legacy_history_reader_STAGING_REVIEW.sql` nie jest zaaplikowany do Neon.
- **Osobne, jawne upoważnienie użytkownika** wymagane przed użyciem tego SQL na konkretnym staging, utworzeniem loginu, zmianą haseł, konfiguracją środowiskowego sekretu albo dowolną zmianą ACL. Brak zgody nie oznacza zgody domyślnej.
- Po osobnej autoryzacji sprawdzić ACL przeciw prywatnym `holding_snapshots`, `valuations`, `paper_events`, prawom `CREATE/INSERT/UPDATE/DELETE` oraz staging-only host. Rola read-only nie powinna mieć dostępu do tradingu ani realnych pozycji.
- `production/main` Neon nie jest środowiskiem testowym; nie wykonywać w nim SQL DDL/DML bez zupełnie oddzielnego procesu przeglądu.
- Żadnych integracji do składania zleceń, real-money dynamic allocations, sugestii wykonania inwestycji lub schedulera tradingu. Tylko edukacyjne symulacje i badania.

## 8. Jaki jest **następny**, rzeczywiście otwarty krok?

**Najbliższa bramka: dostęp do historii dla oddzielnej roli bez podnoszenia uprawnień istniejącego agenta.**

1. **Najpierw zapytać użytkownika o osobne zatwierdzenie** utworzenia ograniczonego historycznego konta na staging. Nie utożsamiać `kontynuuj` z wcześniejszym zatwierdzeniem modyfikacji ACL; wskazać, że propozycja SQL i testy są już gotowe, a wymagane jest jawne potwierdzenie.
2. Po zatwierdzeniu: ponownie sprawdzić wskazaną gałąź Neon i aktualne ACL. Użyć wyłącznie recenzowanego skryptu [`../db/security/legacy_history_reader_STAGING_REVIEW.sql`](../db/security/legacy_history_reader_STAGING_REVIEW.sql), wdrażać **wyłącznie na staging** przez uprawniony kanał. Nie wyświetlać haseł. Pamiętać, że to `NOLOGIN`; login/password i secret to osobne, wymagające zgody kroki administracyjne.
3. Gdy dostęp jest realnie gotowy: uruchomić RĘCZNIE z `main` [`Historical reference research bridge`](../.github/workflows/legacy-history-research.yml). Sprawdzić log `LEGACY_HISTORY_RESEARCH_OK`, liczby serii, brak SQL writes, `real_orders=0`, brak surowej historii w artefaktach.
4. Przejrzeć wyniki na realnym legacy: wykryte nietypowe ruchy są **retrospektywnym opisem**, status `UNVERIFIED_HISTORICAL_PUBLICATION`, nie porady ani walidowane sygnały. Zestawić wyniki z baseline, sprawdzić niską liczebność prób, nachodzenie okien, out-of-sample i niepewność.
5. Oddzielny projekt na dalszy etap: autentyczne vintage od oficjalnych dostawców (NBP/EIA/World Bank/ECB, gdy dostępne), weryfikowalne indeksy **total-return** oraz właściwy kontrakt źródeł/ograniczenia schematu. Dopiero na dobrej jakości danych możliwa analiza alternatywnych **wirtualnych** alokacji. Nie cofać `retrieved_at/recorded_at` do fikcyjnych dat.
6. Dopiero po prawdziwym sprawdzeniu systemu błędów/alertów i szeregu niezależnych walidowanych uruchomień rozważyć **badawczy** monitoring cykliczny. Dziś harmonogram jest wyłączony.

### Definicja sukcesu następnego etapu

- Oddzielny staging-only, least-privilege reader zatwierdzony i poprawnie sprawdzony, agent `isl_agent_staging_limited` bez zmian.
- Jednorazowy ręczny history bridge kończy się sukcesem, raportuje ilość danych i hash wejścia, nie ujawnia cen surowych ani sekretów.
- Wyniki dają listę **pytań badawczych** z kontrargumentami, benchmarkiem, liczebnością i ostrzeżeniami.
- W raportach jawnie: `UNVERIFIED_HISTORICAL_PUBLICATION`, `real_orders=0`, `database_writes=0`, `hypothetical_allocation_changes=0`.
- Brak automatycznego planu transakcyjnego; kolejny agent nie „odblokowuje” modelu poprzez pominięcie provenance.

## 9. Przekazanie nowej sesji — gotowy prompt

> Kontynuuj repozytorium `gniewkob/Investment-Strategy-Lab`. Najpierw przeczytaj `AGENTS.md`, następnie `docs/SESSION_HANDOFF_PL.md`, `docs/HISTORICAL_REFERENCE_BRIDGE_PL.md`, `docs/OPPORTUNITY_RADAR_PL.md` i Issue #4. Zweryfikuj aktualny `main` i Neon staging; nie używaj starych statystyk bez ponownego odczytu. Celem jest edukacyjne Opportunity & Decision Intelligence (radar, hipotezy, benchmarki, argumenty za/przeciw, klasyfikacja OBSERVE/INVESTIGATE/HOLD); żadnych rzeczywistych transakcji. Nie duplikuj gotowych modułów PR #12–17. Najbliższa bramka to odrębna rola read-only do legacy na staging, jednak **NIE wykonuj SQL ani nie ustawiaj uprawnień/sekretów bez mojej odrębnej, jawnej zgody**. PR #1 nadal Draft, produkcyjnego Neon nie dotykaj. Zaproponuj najbezpieczniejszy kolejny krok i pokaż wymagane zatwierdzenia.

## 10. Zasady aktualizowania tej strony

- Po każdej większej zmianie dołącz datowany aneks w Issue #4 **i zaktualizuj niniejszy dokument**, szczególnie tabelę aktualnego stanu, rzeczywisty blocker oraz wyniki testów. Nie nadpisuj historycznych dowodów nowymi przypuszczeniami.
- Zawsze linkuj **konkretny GitHub run/PR/commit**; rozdzielaj „offline CI passed” od „rzeczywisty staging workflow przeszedł”. Test CI na disposable PostgreSQL **nie oznacza** uruchomienia SQL na Neon.
- Jeśli aktualny HEAD jest nowszy niż snapshot, sprawdź zmiany i popraw dokument zamiast w ciemno wykonywać kroki.
- Nie wrzucaj prywatnych źródeł lub sekretów do publicznej dokumentacji.
