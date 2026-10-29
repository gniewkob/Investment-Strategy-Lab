# M1 — Investment Strategy Lab: release readiness i odbiór 24 h

**Data:** 2026-10-29, raport weryfikacji GitHub + wcześniejszych dowodów Mac.
**Status na moment audytu:** `PREPARED / NO-GO DEPLOYMENT / 24H PARTIAL`.
**Dotyczy:** PR #87, integrujący #81 + #85 + #86; Issue #80.
**Operator:** bez nowej zgody na restart albo wdrożenie Maca. Żadnych operacji
finansowych, zapisów Coinbase/Neon, transferów, kluczy, płatności ani zmian
uprawnień.

## Cel i progi PASS

Milestone **M1** = zidentyfikowane wydanie działającego lokalnego monitoringu,
dowodowo zweryfikowane w co najmniej 24-godzinnym *naturalnym* harmonogramie,
z dostępem do prywatnego panelu i udokumentowanym rollbackiem.

| Bramka | Próg |
| --- | --- |
| G1. Integralność wydania | review diff, dokładny 40-znakowy commit SHA, czysty checkout, pełne CI |
| G2. Bezpieczny preflight | `portfolio_release_canary --phase before` PASS z prywatnymi lokalnymi plikami |
| G3. Autoryzowane przełączenie | osobne potwierdzenie operatora, backup+rollback, jednoznaczny proces/LaunchAgent i pin SHA |
| G4. Postflight i smoke | `--phase after`, jeden proces, watchdog, prawidłowe źródła, co najmniej 2 kolejne naturalne cykle |
| G5. Niezależny odbiór | >=24h rzeczywistych danych kolektora, >=90 unikalnych naturalnych checkpointów, 0 próbek INVALID/PARTIAL, 0 przerw kolektora >120s, 0 opóźnionych cykli poza 900–1020s, 0 nieuzasadnionych restartów, 0 nieznanych liczników HTTP429, wszystkie źródła OK, sprawny watchdog, 0 operacji finansowych |
| G6. Raport i utrwalenie dowodów | zagregowany raport w Issue #80, czasy UTC, SHA, zero ujawnienia danych prywatnych, ocena PASS/FAIL |

G5 ocenia **tylko** obserwowany zakres, nie pełną historię
blockchain, całościowy majątek, dokładny P&L ani wykonanie transakcji.
`HTTP429=0` z ostatniego cyklu nie jest dowodem zera przez dobę.

## Co zostało zweryfikowane

1. **PR #87 OPEN / Draft** (29.10.2026), brak formalnego review,
   GitHub porównanie z `main=d0f001e64e7dc1165caec1a39071f11015b999c7`
   pokazuje 16 plików w integracji. PR nie został scalony.
2. Wcześniejsza dokładna wersja kodu `0966009e6daff8234b0d82ba75d663e60fc00ec2`:
   offline unittest **597/597 PASS**:
   https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/40946330929 ;
   realny Chromium na danych syntetycznych 6/6 PASS:
   https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/40946330926 .
   Późniejszy head `7e07f09e28cb0e3fae43909ac51290284cf1b520`
   został zweryfikowany czterema workflowami SUCCESS. NOWE zmiany
   w tym M1 runbook/skrypcie wymagają pełnego CI na ich dokładnym SHA.
3. Operator uruchomił Mac lokalny ze starszą wersją PR #87:
   `SOURCE_SHA=VERIFIED`, `LOCAL_TESTS=PASS` 594 testy,
   `LIVE_SNAPSHOT_PREVIEW=OPENED`, `PRODUCTION=UNCHANGED`.
   Otwarty lokalnie podgląd nie jest wdrożeniem.
4. Ostatni rzeczywisty audyt runtime 29.10.2026 18:41 UTC:
   supervisor SHA `93038ca62edff39492f9b8ddb68d890e3e6e5c45`,
   PID 38669, najnowsze `OBSERVATION_OK`, zero finansowych operacji;
   24h: 94 naturalne checkpointy, 0 opóźnionych cykli,
   **5 odrębnych Ethereum PARTIAL**, 1 INVALID sample,
   2 luki w próbkowaniu (151,6s i 173,3s), nieprzerwana tożsamość
   właściwych próbek procesu. Pięć częściowych cykli miało 0 HTTP429
   oraz 5–6 HTTP200; historycznej przyczyny nie można odtworzyć.
   **Decyzja: G5 PARTIAL, nie PASS.**
5. `scripts/portfolio_release_canary.py` jest na `main`, nie dzwoni
   do dostawców, nie czyta treści kluczy, nie ingeruje w launchd.
   `--phase before` potwierdza czystość kodu i warunki plików,
   `--phase after` spójność i świeżość ostatniego checkpointu.
   **Żadna faza nie zaświadcza o rzeczywiście uruchomionym SHA**:
   `local_daemon_running_verified=false` jest poprawne.
   Potrzebne niezależne sprawdzenie procesu i świadome przełączenie.
6. Collector `scripts/unattended_acceptance.py` utrwala append-only
   minuty, bez usuwania starych dowodów; `summarize` liczy **cały
   plik** od początku, więc wcześniejsze awarie utrzymują wynik PARTIAL.
   Zabronione jest przepisywanie/kasowanie ledger tylko dla PASS.
   Przy właściwym odbiorze po release uruchomić *nowy* prywatny
   output bez nadpisania archiwum; ustawić pełny `--expected-commit`
   nowo wdrożonego supervisora, po osobnej zgodzie.
7. Przygotowano **nowy, tylko odczytowy** `scripts/m1_readonly_evidence.py`,
   który mierzy ostatnie >=24h starych dowodów i niczego nie zapisuje.
   To pomocniczy audyt historyczny; nie zastępuje G3/G4 ani
   nowego niezależnego okna G5.

## Kolejność następnych działań (bez samowolnego restartu)

### Dostępne już teraz, bez zmian produkcyjnych

- [x] Pobranie aktualnego PR #87 i rozpoznanie zależności #81/#85/#86.
- [x] Weryfikacja wymagań preflight/postflight oraz ograniczeń checkera.
- [x] Weryfikacja wyników 24h i kryteriów PARTIAL bez odrzucania dowodów.
- [x] Opracowanie niezależnego read-only audytu rolling 24h i testów.
- [ ] Ostateczne zielone CI po **ostatnim** commicie M1.
- [ ] Review PR #87 przez właściciela lub niezależnego reviewera.
- [ ] Na prywatnym Macu: dokładny, izolowany checkout zatwierdzonego SHA,
      testy i `portfolio_release_canary --phase before`. Nie udostępniać
      ścieżek, sekretów, sald ani raportów źródłowych.

### Tylko po osobnej, jawnej decyzji o wdrożeniu read-only

- [ ] Lokalny zapis bieżących **hashy i kopii rollback** LaunchAgent,
      stabilnego SHA, statusu procesu i prywatnej kopii konfiguracji.
      Zachować cały historyczny ledger i stan.
- [ ] Kontrolowane przełączenie jedynie monitoringu/health LaunchAgents
      na **reviewowany SHA**, przy zachowaniu zakresu źródeł, adresów,
      harmonogramów i uprawnień; żadnych operacji finansowych.
- [ ] Wykonać release canary AFTER; sprawdzić faktycznie uruchomioną
      tożsamość procesu i statusy dwóch kolejnych naturalnych cykli.
      Nie uznawać `--once` za naturalne cykle.
- [ ] Uruchomić nowe prywatne **oddzielne** okno dowodowe, z pin SHA
      nowego supervisora i niezależnego watchdog checkoutu (ntfy).
      Nie zmieniać historycznej próbki INVALID w poprzednim ledgerze.
- [ ] Po >=24h przeprowadzić audyt zagregowany, zachować
      niepowodzenia i rollback. PASS tylko po spełnieniu G1–G6.

## Bezpieczny odczyt 24h na istniejącym Macu, bez restartów

W **dotychczasowym** checkout kolektora można wykonać tylko odczyt
dziennika przez nowy skrypt na *osobnej, czystej kopii Git* (nie w
katalogu działającego procesu). Polecenie używa **istniejącej** ścieżki
prywatnego `samples.jsonl` z lokalnego LaunchAgenta; nie publikować
jej w rozmowie ani repo.

```sh
python3 -m scripts.m1_readonly_evidence --samples "$PRIVATE_EXISTING_SAMPLES_JSONL"
```

- `status=PASS`, exit 0: tylko obserwacja w wybranym oknie; nie
  certyfikuje nowego wydania ani bezpieczeństwa finansowego.
- `status=PARTIAL`, exit 3: niezrealizowane progi, w tym brak danych.
- `M1_READONLY_EVIDENCE_REJECTED`, exit 2: nieprawidłowy plik, prawa,
  zegar lub niekompletny schemat; fail-closed.

Skrypt nie ma zależności SDK, Coinbase ani bazy, nie wykonuje requestów
i nie tworzy plików. Wypisuje wyłącznie agregaty i stałe kody błędów.

## Ryzyka i jawne blokady

- `PARTIAL` Ethereum ma konkretne historyczne czasy, ale kod
  nie potrafił zapisać pełnej kategorii przyczyny; nowe kategorie
  z PR #87 dopiero **po jego wdrożeniu**.
- Cumulative collector raportuje stare zdarzenia; odbiór wymaga
  wyraźnego okna, a sam rolling 24h to jedynie diagnostyka.
- W PR #87 brak formalnego code review; GitHub `mergeable=true` nie
  stanowi oceny release-ready.
- Nie potwierdzono lokalnego release canary dla nowego SHA ani
  odbioru ntfy przez iPhone; brak świeżego dowodu ciągłości.
- Obecny read-only zakres nie obejmuje kompletnych aktywów NFT/DeFi,
  pełnej historii łańcucha ani uzgodnienia Exchange↔Wallet.

**Decyzja:** M1 po audycie kodowym i przygotowaniu testów może
przejść do *kontrolowanej bramki release*, ale **nie** do deklaracji
`OPERATIONAL_24H_PASS` bez G3–G6 i formalnej decyzji operatora.


## M1.1 — dodatkowy preflight macOS: aktywny proces ≠ kod na dysku

Nowy `scripts/m1_predeploy_readiness.py` działa **wyłącznie odczytowo** na Macu.
Zadaniem jest skojarzenie metadanych z trzech **już istniejących** macOS
LaunchAgents (`portfolio`, `portfolio-health`, `acceptance`) z aktualnym
checkoutem aktywnej usługi i z preflightem **nowego, izolowanego** commitu.
Nie odczytuje zawartości poświadczeń, nie wywołuje providerów i nie restartuje
procesów. Sprawdza:

- `launchctl print` i `ps` dla aktywnego supervisora, zgodność PID, modułu
  i `WorkingDirectory` w metadanych załadowanego zadania;
- `git rev-parse HEAD` i brak lokalnych zmian w checkoutcie istniejącego
  supervisora; tylko kod **na dysku**, bez twierdzenia o wersji modułów
  załadowanych do pamięci wcześniej uruchomionego procesu;
- istniejący watchdog co 300 sekund i kolektor co 60 sekund, z poprawnie
  przypiętym SHA kolektora do starego checkoutu;
- `portfolio_release_canary --phase before` uruchomiony na zatwierdzonej
  wersji kandydata, z zachowaniem prywatnych uprawnień konfiguracji.

### Wykonanie z czystego, odizolowanego katalogu

```bash
set +x
# Pracujemy w czystej kopii WYŁĄCZNIE do audytu.
git clone --depth 1 --branch codex/integrate-portfolio-81-85-86-20261029 \
  https://github.com/gniewkob/Investment-Strategy-Lab.git "$ISOLATED_CLEAN_DIRECTORY"
cd "$ISOLATED_CLEAN_DIRECTORY"
expected="$(git rev-parse HEAD)"
python3 -B -m scripts.m1_predeploy_readiness --expected-commit "$expected"
```

`READY_FOR_RELEASE_REVIEW_NOT_DEPLOYED` oznacza wyłącznie, że kod kandydata,
prywatne metadane i obecna działająca usługa spełniają wstępne wymagania.
**Nie** potwierdza wersji modułów w pamięci, utworzenia backupu ani
zrestartowania usług. Raport celowo zwraca
`active_process_code_in_memory_attested=false` oraz
`rollback_backup_created=false`; bez zatwierdzonego wdrożenia nie mogą
zmienić się na `true`.

`M1_PREDEPLOY_READONLY_REJECTED` oznacza fail-closed, na przykład inny pin
kolektora, brak któregoś z załadowanych LaunchAgentów, niezgodne definicje,
nieczysty stary checkout albo niepoprawne uprawnienia. Tego nie wolno obchodzić
usuwaniem lub resetem stanu. Wtedy potrzebna jest kolejna odczytowa analiza
na konkretnym Macu.

**Zakres niepotwierdzony:** rzeczywiste cykle po nowym deploy,
przywrócenie rollbacku, dostarczenie ntfy na iPhone oraz 24h naturalnej
obserwacji. Preflight nie jest zezwoleniem na transfer ani realny trading.


## Reakcja na blokadę M1 preflight na Macu (29.10.2026)

Operator wykonał pierwszy odczyt na Macu z SHA
`2493a28ae743b93d10592ecac6c93e095ba9cd66`, uzyskując
`M1_CANDIDATE_SHA=VERIFIED` i `M1_PREDEPLOY_READONLY_REJECTED`.
Brak `M1_PREDEPLOY_AUDIT_COMPLETE` wynika z `set -e` w izolowanym
podprocesie. **Nie jest to dowód awarii działającego supervisora ani
wystąpienia transakcji.** Żaden plik produkcyjny nie był zmieniany.

W wersji preflightu dostępnej przy tym odbiorze każdy błąd ze stanu
launchd, pliku plist, pinu kolektora lub `portfolio_release_canary`
dawał identyczny komunikat. Następna wersja skryptu publikuje
wyłącznie `M1_FAILURE_STAGE` z poniższej zamkniętej listy:

| Etap | Kontrola |
| --- | --- |
| `VALIDATE_EXPECTED_SHA` | Format pełnego commitu |
| `READ_LAUNCHAGENT_DEFINITIONS` | Obecność, własność i prawa plików plist |
| `CHECK_SUPERVISOR_DEFINITION` | Program, parametry, konfiguracja i katalog procesu |
| `CHECK_WATCHDOG_COLLECTOR_DEFINITIONS` | Moduły i częstotliwości health/acceptance |
| `CHECK_SUPERVISOR_LAUNCHCTL` | Załadowany proces i jego metadane |
| `CHECK_SUPERVISOR_PROCESS` | Rzeczywisty PID i moduł w `ps` |
| `CHECK_LOADED_PERIODIC_SCHEDULES` | Stan i częstotliwości dwóch zadań okresowych |
| `CHECK_EXISTING_RUNTIME_GIT` | Wersja i czystość aktywnego checkoutu na dysku |
| `CHECK_COLLECTOR_EXPECTED_SHA` | Spójność założeń o starym pinie i katalogach kolektora |
| `CHECK_CANDIDATE_RELEASE_CANARY` | Niezależny preflight prywatnej konfiguracji nowego commitu |

Komunikat `M1_PREDEPLOY_READONLY_REJECTED` pozostaje fail-closed;
skrypt **nie** pokazuje tekstu wyjątku, ścieżek, historii, adresów,
sald ani danych z konfiguracji. W szczególności
`CHECK_COLLECTOR_EXPECTED_SHA` oznacza niezgodność z *założeniem
audytu*, a nie dowód, że obecna usługa operacyjna działa błędnie.

Następny krok to ponowny jednorazowy preflight z nowym dokładnym SHA
PR #87, bez zmieniania nawet jednej definicji launchd. Zachować wynik
próby w Issue #80. **Nie obchodzić testu przez dopasowywanie pinu,
usuwanie próbek, tworzenie plików w katalogu stanu lub restart.**


## M1.1 — drugi rzeczywisty odczyt: definicje watchdog/kolektor

Operator wykonał dokładny izolowany checkout
`d5e192d18b32138d464db20100284be89d272dd4`. Zwrócono
`M1_CANDIDATE_SHA=VERIFIED`,
`M1_PREDEPLOY_READONLY_REJECTED` i
**`M1_FAILURE_STAGE=CHECK_WATCHDOG_COLLECTOR_DEFINITIONS`**.

Jest to dowód rozbieżności co najmniej jednego **założenia preflightu**
w następującej grupie, a nie dowód awarii pracującego procesu:

- obecność flagi `--check-health` w argv watchdoga;
- `StartInterval==300` w jego zapisanej definicji;
- obecność modułu `scripts.unattended_acceptance` jako osobnego
  argumentu programu kolektora;
- `StartInterval==60` w jego zapisanej definicji.

Wszystkie cztery sprawdzenia były wcześniej połączone w jednym warunku.
Nie ma dowodu, które jest niezgodne ani czy rzeczywisty
harmonogram launchd jest uszkodzony. **Nie wolno zmieniać konfiguracji
w celu sztucznego PASS**.

Kolejny read-only preflight rozdziela grupę na osobne bezpieczne
kody `CHECK_WATCHDOG_COMMAND`,
`CHECK_WATCHDOG_INTERVAL`, `CHECK_COLLECTOR_COMMAND`,
`CHECK_COLLECTOR_INTERVAL`. Niezależne testy syntetyczne obejmują
każdy przypadek. Wyświetlane są tylko z góry zdefiniowane nazwy
bramek; nigdy surowa lista argumentów, ścieżki ani zawartość plist.
Po uzyskaniu dokładnego kodu należy sprawdzić zgodność
z udokumentowanym, **obecnym** sposobem uruchamiania, zanim
zaproponujemy jakąkolwiek poprawkę w kodzie albo plan release.

M1 G2 nadal `NO-GO`; G3 deploy nieautoryzowany i niewykonany.
