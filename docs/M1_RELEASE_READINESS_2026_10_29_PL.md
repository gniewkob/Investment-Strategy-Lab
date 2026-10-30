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


## M1.1 — rozpoznany punkt wejścia kolektora (29.10.2026)

Operator potwierdził **jedynie bezpieczne metadane** aktualnego LaunchAgenta:

```text
M1_COLLECTOR_COMMAND_SHAPE=OTHER_ENTRYPOINT
M1_COLLECTOR_INTERVAL_60=True
M1_COLLECTOR_ARG_COUNT=10
M1_FLAG_STATE_DIRECTORY=True
M1_FLAG_OUTPUT=True
M1_FLAG_EXPECTED_COMMIT=True
M1_PREFIX_COUNT=2
M1_ENTRYPOINT_LAYOUT=PYTHON|SCRIPT_FILE
M1_DIAGNOSTIC=READ_ONLY
```

To jednoznacznie wskazuje, że preflight G2 miał niepoprawne założenie
o wyłącznym uruchamianiu `python -m scripts.unattended_acceptance`.
Zainstalowany kolektor działa jako **Python + odrębna kopia pliku .py**.
Nie jest to dowód awarii źródła danych ani procesu, ale też sama
obecność pliku .py nie jest wystarczającą atestacją.

Nowy walidator dopuszcza dokładnie dwie formy:

1. `python -m scripts.unattended_acceptance` — zatwierdzony moduł.
2. `python /absolutna/prywatna/kopia.py` — tylko jeśli zwykły plik
   bez symlinków należy do aktualnego użytkownika, nie ma praw zapisu
   dla grupy/innych, ma bezpieczny limit rozmiaru, a jego **pełne bajty**
   są identyczne z zatwierdzonym `scripts/unattended_acceptance.py`
   (SHA-256 obu plików). Zatwierdzona referencja musi dodatkowo
   posiadać przypięty Git blob `41a8ca1e40af5697f6661b5e158bc205b4fe48ff`,
   zweryfikowany dla PR #81, SHA
   `3122b571b0e5e562ab58dce9981971a122570540`.
   Również plik referencyjny musi być zwykły, należeć do użytkownika
   i nie być zapisywalny przez innych.

W tej formie preflight **nie wykonuje, nie kopiuje ani nie publikuje**
żadnego kodu kolektora. Odczytuje jedynie dwa pliki kodu, nie
konfigurację finansową czy historię. Jeżeli zawartość prywatnej
kopii różni się od wcześniej zatwierdzonego kodu, raportuje wyłącznie
`M1_FAILURE_STAGE=CHECK_COLLECTOR_CODE_IDENTITY`. Nie zmieniamy jej
automatycznie w celu uzyskania PASS.

Testy obejmują prawidłową kopię o innej nazwie, nieznany kod,
niepoprawne prawa zapisu, link symboliczny, względną ścieżkę,
niezatwierdzony interpreter i zmodyfikowaną referencję.
Kolejne kroki G2 (np. odczyt statusu `launchctl`, potwierdzenie
kolektora oraz weryfikacja nowego checkoutu przez canary) mogą nadal
zwrócić NO-GO. Nawet kompletne G2 PASS nie stanowi zgody na restart,
merge, deploy ani automatyczny trading.


## M1.2 — niezależne code review i blokady release (2026-10-29)

W odpowiedzi na `@codex review` dla kandydata
`4d406bb104f0cf87360c47800b33df9cada2d06c` opublikowano dwie
uwagi **P2**, dotyczące przypadków fałszywego `READY`:

1. Samo `python -m scripts.unattended_acceptance` mogło zostać
   zaakceptowane bez weryfikacji, z którego katalogu i przy jakim
   `PYTHONPATH` Python załaduje moduł.
2. Zabrakło sprawdzenia wymaganego argumentu `--runtime`. Bez niego
   rzeczywisty kolektor kończy pracę na walidacji CLI, mimo że
   preflight mógł zgłosić `PASS`.

**Zmiana fail-closed, bez ingerencji w Maca:**

- W M1.2 dopuszczamy wyłącznie udowodnioną lokalnie formę
  `python /abs/path/copied.py` z kontrolą właściciela, uprawnień,
  braku symlinków oraz pełnej zgodności kodu z przypiętym zatwierdzonym
  Git blob. `python -m` jest od tej wersji **celowo odrzucany**,
  dopóki nie istnieje osobna, niezależna atestacja rozwiązywania
  importu; wcześniej wspierany wariant modułowy nie był bezpiecznie
  atestowany.
- Wymagamy pojedynczego `--runtime` z bezwzględną ścieżką równą
  `WorkingDirectory` istniejącego supervisora, oprócz
  `--state-directory`, `--output`, `--expected-commit`.
- Weryfikujemy kompletne 10 argumentów znanego modelu produkcyjnego.
  Nieznany wpis ani brakujący plik kolektora nie wywoła wyjątku
  zdradzającego prywatną ścieżkę w publicznym CLI.

**Dowód poprzedniego M1.1:** Operator uruchomił starszy zweryfikowany
commit `4d406bb104f0cf87360c47800b33df9cada2d06c`, otrzymując
`READY_FOR_RELEASE_REVIEW_NOT_DEPLOYED` i exit `0`. Zapisał
`current_on_disk_runtime_sha=93038ca62edff39492f9b8ddb68d890e3e6e5c45`,
`collector_entrypoint_verified=REVIEWED_COPIED_PYTHON_SCRIPT`,
`financial_operations=0`, `files_changed=0`,
`services_restarted=0`. **Ten wynik dotyczy wyłącznie starego SHA;**
nie jest odbiorem najnowszej poprawki po review.

Bieżące prace odbywają się wyłącznie w Draft PR #87. **Brak
zezwolenia na merge, restart, zmianę LaunchAgent, zapis do Neon
lub operacje finansowe.** Do decyzji G3 pozostaje niezależny
re-review najnowszego commitu, aktualny lokalny preflight
i odczytowe potwierdzenie rzeczywistych kopii rollbacku.


## M1.2 — trzecia uwaga review P2: importy Pythona poza atestowanym skryptem

Po re-review commitu `101047ea1b821cb3ac82789ecc8f1ee9929956df`
zgłoszono kolejny przypadek fałszywego PASS: zatwierdzony bajtowo
plik kolektora może wykonać obcy moduł `argparse.py` (lub inny import)
przez `PYTHONPATH`, mimo że jego własny SHA pozostaje poprawny.
Review z tego commitu nie stanowi więc akceptacji security.

**Nowa kontrola:** wyłącznie bezpośredni, zatwierdzony skrypt Python
uruchamiany w postaci
`python3 -I /absolutna/prywatna/kopia-kolektora.py`,
z czystą pozycją `-I` przed plikiem.
Flaga `-I` wyłącza importy z katalogu skryptu, ignoruje `PYTHON*`
oraz wyłącza pakiety z user-site. Kod źródłowy musi nadal spełniać
warunki przypiętego blobu Git, właściciela i uprawnień pliku.
`python3 script.py`, `python3 -E script.py`,
`python3 -s script.py`, `python3 -m ...` i inne formy są
odrzucane (fail-closed). Oczekujemy **11 zamiast 10** argumentów
`ProgramArguments` w przyszłej zatwierdzonej definicji.

Dodatkowe testy syntetyczne wykazują:
1. odrzucenie nieizolowanego, choć identycznego, zatwierdzonego kodu;
2. uruchomienie Pythona z `-I` ignoruje syntetyczny
   `PYTHONPATH` wskazujący plik `argparse.py` zawierający wyjątek.

**Ważna konsekwencja odbiorowa:** operator wcześniej potwierdził
`M1_PREFIX_COUNT=2` i `M1_ENTRYPOINT_LAYOUT=PYTHON|SCRIPT_FILE`,
a historyczny PASS G2 pochodzi z **poprzedniego** preflightu
`4d406bb...`. Obecne LaunchAgent tego parametru jeszcze nie mają,
więc najnowsze zaostrzone G2 **nie może** uzyskać PASS na Macu bez
zmiany definicji i jej kontrolowanego przeładowania. To **zamierzona
blokada bezpieczeństwa**, nie błąd wykryty w runtime.

Aktualny plan G3 zakłada zachowanie dotychczasowego pełnego
prywatnego ledgeru, osobnej kopii pliku plist i znanego dobrego SHA,
a dopiero po **nowej, osobnej zgodzie operatora** kontrolowane
dodanie `-I` i test postflight. Nie zmieniać LaunchAgentów, PID,
harmonogramu ani kodu działającej produkcji w ramach audytu GitHub.
Do tego czasu cel M1.2 pozostaje `NO-GO`.


## M1.2 — czwarta i piąta uwaga P2: definicja załadowana ≠ plik plist

Kolejny niezależny przegląd commitu
`78080ebb10a1466b6627850c054c25afaaa2f525` ujawnił dwa
mechanizmy fałszywego `READY`:

1. Plik plist na dysku mógł już zawierać wymagane `python -I`,
   ale `launchd` mógł nadal korzystać z poprzedniej,
   **nieizolowanej** listy argumentów (job nie przeładowany).
   Sam `StartInterval=60` nie dowodził tożsamości polecenia.
2. `launchd` pozwala podać osobne `Program`; jeśli nie zgadza się
   z `ProgramArguments[0]`, wykonana zostaje inna binarka.
   Wcześniejszy preflight atestował tylko argumenty.

**Zmiany w walidatorze**: jawnie obecne `Program` musi być identyczne
z zatwierdzonym interpreterem; dodatkowo preflight odczytuje
`launchctl print` dla istniejącego kolektora i żąda pełnej zgodności
załadowanego `program` i **całego** bloku `arguments` z dokładnie
sprawdzoną definicją plist. Nieznany format danych launchctl, brak
bloku, inna binarka lub stare argumenty oznaczają
`CHECK_LOADED_COLLECTOR_COMMAND` i `NO-GO`.
Tekst polecenia z launchd **nie** jest drukowany, cytowany w błędach
ani utrwalany w publicznym dowodzie.

Testy syntetyczne obejmują stary załadowany job bez `-I`
pomimo zaktualizowanego plist, osobny niezgodny `Program`,
nieczytelny format argumentów oraz spójność zmodyfikowanych
fixture'ów. To nie jest odbiór realnej konfiguracji na Macu:
załadowanego formatu launchctl nie zebrano w tej gałęzi,
a poprzedni odczyt z Maca miał `PYTHON|SCRIPT_FILE`
**bez `-I`**.

**Bramki pozostają zamknięte** do niezależnego review bieżącego SHA,
potwierdzenia rollbacku, osobnej zgody operatora na kontrolowaną
zmianę wyłącznie kolektora i nowego realnego preflight/postflight.
Nie wolno wykonywać restartów, przeładowań, zmian LaunchAgent,
operacji finansowych, ani nadpisywać historycznych próbek w celu PASS.


## M1.3 — operator zatwierdził przygotowanie przełączenia kolektora (30.10.2026)

Użytkownik wyraził zgodę na kontynuację kontrolowanego przełączenia
**wyłącznie** kolektora na izolowany Python `-I`, pod warunkiem
weryfikacji kopii rollbacku i wydania. Nie obejmuje to restartu Maca,
supervisora, watchdoga, operacji finansowych ani usuwania dowodów.

Review dokładnego SHA `309839142b62f8ca6641eabaca17adfde2c98daf`
zakończyło się bez nowych usterek; historyczne wątki P2 zamknięto;
CI 4/4 workflowy i Python 621/621 PASS. Osobny status
`security_review` nie został jeszcze potwierdzony.

### G2.2: owner-only backup i projekt nowego plist — bez deploy

`scripts/m1_collector_release_prepare.py` wymaga zgodności
aktywnego `launchctl print` ze starą (nieizolowaną) definicją
LaunchAgent, starego pinu supervisora, bezpiecznych praw plików
oraz zatwierdzonego blobu Git kodu kolektora.
Testuje tylko `python -I zatwierdzony-collector.py --help`.

Następnie w **nowym prywatnym** katalogu (0700) zapisuje
oryginalny plist, oryginalny kod kolektora oraz wariant plist z dodaną
flagą `-I` (pliki 0600). Tworzy manifest SHA256 i ponownie weryfikuje
cały backup. Lokalizacja:
`~/Library/Application Support/InvestmentStrategyLab/M1Rollback`.
Standardowy stdout ujawnia wyłącznie ID bundle, SHA i stałe statusy,
nie ujawnia prywatnych ścieżek, danych środowiskowych, portfela ani
konfiguracji. Nie dotyka pliku plist w `~/Library/LaunchAgents`,
nie przeładowuje usługi i nie zapisuje niczego do istniejących
dzienników kolektora.

```bash
set +x
(
  set -e
  branch="codex/integrate-portfolio-81-85-86-20261029"
  expected="__EXACT_REVIEWED_PR_HEAD__"
  old_runtime="93038ca62edff39492f9b8ddb68d890e3e6e5c45"
  tmp="$(mktemp -d /tmp/isl-m1-prepare.XXXXXXXX)"
  git clone -q --depth 1 --single-branch --branch "$branch" \
      https://github.com/gniewkob/Investment-Strategy-Lab.git "$tmp/repo"
  test "$(git -C "$tmp/repo" rev-parse HEAD)" = "$expected"
  echo "M1_PREPARE_COMMIT_VERIFIED"
  cd "$tmp/repo"
  PYTHONDONTWRITEBYTECODE=1 python3 -B -m \
      scripts.m1_collector_release_prepare \
      --expected-runtime-sha "$old_runtime"
)
```

Sukces: `ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY`, exit 0.
Odrzucenie: `M1_COLLECTOR_ROLLBACK_PREPARE_REJECTED`, exit 2;
nie obchodzić przez reset plików, zmianę pinu ani restart.

Oddzielny odczyt backupu przy użyciu otrzymanego identyfikatora:
`python3 -B -m scripts.m1_collector_release_prepare
--verify-bundle-id "$M1_PRIVATE_BUNDLE_ID"`.

**G3 nie wykonano:** przełączenie i ewentualne odwrócenie wyłącznie
`pl.gniewkob.isl.acceptance` wymaga pozytywnego G2.2,
weryfikacji faktycznej konfiguracji `launchctl`, testu nowych
zapisów i gwarancji zachowania starych dowodów.
`-I` nie może zostać dopisane wyłącznie do pliku plist bez
przeładowania załadowanej definicji. Nowy odbiór 24h zaczyna się
dopiero po pomyślnym G3/G4.


## M1.3 — po realnym przygotowaniu backupu i niezależnym review P1/P2 (30.10.2026)

Operator na Macu wykonał pierwotny etap przygotowania, otrzymując
`ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY` dla backupu
`m1-msmkv_0i`. Kopia zawiera stary `plist`, oryginalny kod
kolektora i staged `plist` z `-I`; raport potwierdził brak
przeładowania i modyfikacji aktywnej definicji. Oznacza to
**zgodność zapisanych plików**, a nie gotowość do wykonania G3.

Niezależny review poprzedniego SHA
`36050db7f9694980bf7d4e14a24e8682038292e4` ujawnił
**2 × P1 i 1 × P2** w skrypcie przygotowania rollbacku:

1. Wcześniejszy `python --help` korzystał z nazwy binarki
   w niezatwierdzonym pliku `plist`; jej podmiana mogła
   wykonać dowolny program z uprawnieniami użytkownika.
2. Skrypt kolektora mógł zostać podmieniony między sprawdzeniem
   jego hashy a rzeczywistym uruchomieniem przez `--help`.
3. Rodzic katalogu backupu mógł być przekierowany przez symlink
   do katalogu, który da się podmienić i utracić kopię.

**Poprawki fail-closed w nowym kodzie:**

- Skrypt przygotowania **NIE wykonuje** ani interpretera wskazanego
  przez `plist`, ani kopii kolektora. Test `--help` został
  usunięty. Zastępuje go statyczne `compile` zatwierdzonych
  bajtów kodu — bez wykonywania importów czy logiki modułu.
  Nie traktujemy tego jako runtime/isolated-mode smoke test.
- Każdy składnik ścieżki do katalogu backupu jest otwierany
  przez `dir_fd` z `O_NOFOLLOW`, sprawdzany pod kątem
  właściciela i praw zapisu; nowy katalog i pliki powstają
  wyłącznie względem przytrzymanych deskryptorów. Wyjątek
  dotyczy root-owned `/tmp` ze sticky bit na potrzeby
  izolowanych testów. Istniejących katalogów nie `chmod`ujemy.
- Weryfikacja kopii czyta pliki z tego samego otwartego
  katalogu przez deskryptor; odmowa przy symlinku, nietypowych
  prawach, niezgodnym SHA-256 lub niepoprawnej strukturze.
- Wynik backupu zwraca `interpreter_binary_attested=false`,
  `isolated_collector_executed=false` oraz
  `restore_rehearsal_completed=false`. Nie są to spełnione
  bramki wydania.
- Stary backup `m1-msmkv_0i` zachowujemy **bez zmian**.
  Po niezależnym review nowego kodu można wyłącznie odczytowo
  zweryfikować go na Macu przez
  `python3 -B -m scripts.m1_collector_release_prepare
  --verify-bundle-id m1-msmkv_0i`. To sprawdzi kopię, a nie
  uruchomienie kolektora.

Wydanie `G3` nadal `NO-GO`: wymaga osobnej atestacji
rzeczywistego interpretera, kontrolowanej próby przywrócenia,
odrębnego bezpiecznego mechanizmu przeładowania tylko
`pl.gniewkob.isl.acceptance` oraz postflight przed rozpoczęciem
nowego okna 24 godzin. Nie uruchamiać starszego `--help`
ani nie przełączać usługi tylko dlatego, że backup istnieje.


## M1.3 — szósta uwaga P1: Git może wykonywać hooki/filtry podczas atestacji

Po ponownej weryfikacji rzeczywistego backupu `m1-msmkv_0i`
(`ROLLBACK_BUNDLE_VERIFIED_NO_DEPLOY` z poprawionego M1 V2,
zero modyfikacji `plist`, zero przeładowań i operacji finansowych)
kolejne code review SHA `174b7693e9c75bf4d9fe8f342a32a808364b9745`
zgłosiło nową uwagę **P1**: `git status` może wykonać
repozytoryjny `core.fsmonitor`, a także zewnętrzne filtry
`filter.*.clean/process`, mimo pozornie odczytowego charakteru
polecenia. Sam czysty wynik `git status --porcelain` nie
jest atestacją bezpieczeństwa lokalnej konfiguracji Git.

**Hardening obu ścieżek M1:** `scripts/m1_predeploy_readiness.py`
oraz `scripts/m1_collector_release_prepare.py` wymagają
owner-controlled, niegrupowo/niepublicznie zapisywalnego katalogu
standalone `.git` i jego lokalnej konfiguracji (bez symlinków),
odrzucają `config.worktree` i konfigurację zawierającą:
`core.fsmonitor`, `core.hooksPath`, zewnętrzne sekcje
`filter`, `diff`, `hook`, `include`, `includeIf`
oraz inne niezatwierdzone punkty wejścia.

Przy faktycznych odczytach z Git stosowany jest systemowy
`/usr/bin/git`, jawnie czyszczone środowisko `GIT_*`,
wyłączone konfiguracje globalna i systemowa, `--no-optional-locks`
oraz ustawienia `core.fsmonitor=false`,
`core.hooksPath=/dev/null`, `core.untrackedCache=false`.
`status` ignoruje submoduły, nie aktualizuje indeksu.
Wszystkie te działania pozostają bramkami **fail-closed**:
jeśli lokalny runtime używa worktree, dowiązań, wykonywalnych
hooków lub filtrów, przygotowanie należy zatrzymać i
ocenić konkretną konfigurację, a nie wyłączać kontrolę.

Dodane testy syntetyczne odrzucają `core.fsmonitor`,
`filter.*`, `hook.*`, `include`, `config.worktree`,
niebezpieczne uprawnienia i symlink pliku konfiguracyjnego.
Dodatkowy test potwierdza izolację argumentów i zmiennych
środowiskowych wywołania Git. Syntetyczne testy nie zastępują
odrębnej atestacji rzeczywistej instalacji Git/interpretera na Macu.

**Status:** G2.2 kopia `m1-msmkv_0i` została zweryfikowana
na Macu, ale nie oznacza udanego przywrócenia. G3 nadal
`NO-GO`, G4/G5 nie wykonane. Nie przeładowano
żadnego LaunchAgenta ani nie wykonano żadnych transakcji.


## M1.3 — review commondir/core.worktree (30.10.2026)

Niezależny przegląd commitu `af8b6af8eb9a16c7abe9a3cc86498ebf15005e62`
wykrył kolejne **P1 + P2** po zabezpieczeniu `git status`:

- Obecność `.git/commondir` pozwala skierować Git do innej
  konfiguracji, zawierającej zewnętrzny filtr/hook, której wcześniejszy
  walidator w ogóle nie odczytywał.
- Zapis `[core] worktree = /decoy` w pojedynczej linii
  pomijał regex na początku osobnej linii, pozwalając
  atestować czystość **innego katalogu niż runtime supervisora**.

Dodatkowe zabezpieczenie M1 w `scripts/m1_predeploy_readiness.py`,
współdzielone przez `scripts/m1_collector_release_prepare.py`:

- odrzuca `.git/commondir` i `.git/config.worktree`
  także jako dangling symlink; dopuszcza tylko standalone `.git`;
- parsuje `.git/config` w rygorystycznym podzbiorze Git config,
  z dopuszczonymi niewykonywalnymi sekcjami/kluczami. Wszystkie
  nieznane sekcje/klucze, wpisy inline po nagłówku,
  kontynuacje linii, filtry, `core.worktree`,
  `core.fsmonitor`, `include`, `hook` są `NO-GO`;
- zachowuje izolowane wywołania systemowego Git z wyłączonymi
  opcjonalnymi zapisami i submodułami.

Testy obejmują zwykłą bezpieczną konfigurację, `commondir`,
dangling symlink `commondir`, dwa warianty `worktree`,
niebezpieczne filtry i kontynuacje. Realne środowisko Mac
nie było ponownie atestowane na tym nowym kodzie, a zgodność
lokalnej konfiguracji Git z allowlistą nie jest jeszcze znana.
Jeśli nowe G2 odrzuci standardową lokalną konfigurację,
nie należy modyfikować repozytorium ani wyłączać walidatora
w celu uzyskania PASS; potrzebna jest tylko zredagowana
diagnostyka metadanych i ocena dozwolonych kluczy.

Backup `m1-msmkv_0i` pozostaje nienaruszony oraz był
zweryfikowany odczytowo przez M1 V2. **Nie** oznacza to
próby przywrócenia, atestacji interpretera, przeładowania kolektora
czy zgody na operacje finansowe. PR #87 pozostaje Draft;
G3 nadal NO-GO do uzyskania niezależnego review, odczytowego
preflightu nowego SHA i próby rollbacku.


## M1.3 — candidate canary: odrębne obejście Git (30.10.2026)

Niezależne review commitu `e1a05c06049142896bfc38950fbd6cec463d2426`
ujawniło **P1**: `portfolio_release_canary.local_code_attestation()`
sprawdzał checkout kandydata przez bezpośrednie polecenia `git`
bez izolowania `GIT_*`, filtrów czy `core.fsmonitor`. W efekcie
dotychczas poprawnie zabezpieczony runtime mógł uzyskać pozytywny
preflight, podczas gdy canary wykonywał niezatwierdzony hook/filtr
z konfiguracji kandydata. Flagi `files_changed=0` i `network_requests=0`
nie dowodziły braku tego wykonania.

**Poprawka:** `scripts/portfolio_release_canary.py` korzysta
teraz z tego samego `assert_trusted_git_checkout` i utwardzonego
`command("git", ...)`, co preflight M1 oraz narzędzie backupu.
Import jest lokalny wewnątrz funkcji, aby uniknąć cyklu importów
(`m1_predeploy_readiness` importuje `portfolio_release_canary`).
Obie operacje sprawdzania HEAD i clean worktree używają chronionych
odczytów Git, z `--ignore-submodules=all`. Błędna, nieznana lub
niebezpieczna konfiguracja jest stałym, zredagowanym `NO-GO`,
bez ujawnienia ścieżek, danych portfela czy outputu Git.

Testy syntetyczne obejmują konfigurowalny `core.fsmonitor`,
filtry, `commondir`, `core.worktree` i `include`;
weryfikują, że blokada następuje **przed** wywołaniem Git.
Osobny test sprawdza wywołania chronionego wrappera, a kontrakt
prawdziwego `git status` jest badany na własnym minimalnym repo
testowym (bez konfiguracji auth generowanej przez GitHub Actions).
Pierwszy przebieg CI na SHA `2ff208d...` był czerwony z powodu
historycznego testu zakładającego zaufanie do konfiguracji checkoutu
GitHub Actions. Test został izolowany bez rozluźniania walidatora;
nie interpretowano tego nieudanego przebiegu jako PASS.

**Bramki:** istniejąca kopia `m1-msmkv_0i` została zweryfikowana,
lecz nie testowano przywrócenia; interpreter i działanie izolowanego
kolektora nie zostały atestowane. G3 pozostaje `NO-GO`, bez
modyfikacji LaunchAgent, restartów, transferów i transakcji.
