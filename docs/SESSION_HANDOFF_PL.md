# Investment Strategy Lab — pełne przekazanie kontekstu nowej sesji agenta

> **Snapshot: 19 października 2026, około 07:11 UTC.** Ta strona opisuje stan **zweryfikowany w GitHub oraz Neon**, odróżnia go od planów. Stan może się później zmienić — przed zapisem albo wykonaniem operacji odczytaj aktualny `main`, Issues, PR-y, uprawnienia i historię workflow.  
> **Pierwsza lektura nowego agenta:** [`../AGENTS.md`](../AGENTS.md), potem niniejszy plik, [`HISTORICAL_REFERENCE_BRIDGE_PL.md`](HISTORICAL_REFERENCE_BRIDGE_PL.md) oraz [`OPPORTUNITY_RADAR_PL.md`](OPPORTUNITY_RADAR_PL.md).  
> **Status:** system badawczy / edukacyjne symulacje. **Nie ma zleceń, handlu, realnych inwestycji ani rekomendacji zakupowych.**

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
