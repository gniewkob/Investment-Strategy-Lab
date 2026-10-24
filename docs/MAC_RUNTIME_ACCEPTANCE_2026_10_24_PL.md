# Odbiór rzeczywistego runtime Mac — issue #77

Stan sprawdzony 2026-10-24, 15:10 UTC. **Wdrożenie wykonane; jakość obserwacji PARTIAL.**
Raport zawiera wyłącznie wersje, czasy i statusy. Prywatna konfiguracja, identyfikatory,
salda, historie źródłowe i poświadczenia pozostają na hoście.

## Decyzja i wersje

- Zadanie: https://github.com/gniewkob/Investment-Strategy-Lab/issues/77.
- Początkowy czysty checkout deweloperski: `25b2451a4c139dc525c546b9b650efde0c913198`.
- Początkowy czysty checkout uruchamianej aplikacji: `3ed150133dbd44c0f4ad2fd50751f1cba36001f1`.
- Pierwszy wdrożony release: `a3b24a7afced5e51d12d04cbe93c072bb74fe52c`.
  Rzeczywisty canary `after` odrzucił metadane; nie uznano go za PASS.
- Końcowy wdrożony release: **`892996c42de33230f91137c8b3fe98211e51729e`**,
  scalony [PR #78](https://github.com/gniewkob/Investment-Strategy-Lab/pull/78).
- Runtime: macOS `27.0.1`, Python `3.15.0`, `coinbase-advanced-py==1.8.4`.
  Izolowane środowisko pełnych lokalnych testów: Python `3.12.12`, zgodny z linią CI.

## Znalezione i naprawione awarie

1. Dwa odczyty zegara dawały ważność raportu większą niż 30 minut o kilka mikrosekund.
   Ścisły canary i watchdog poprawnie odrzucały taki raport. Wspólny `checked_at`
   przywraca dokładnie 1800 sekund ważności, bez osłabiania walidacji.
2. Domyślne JSON `\u...` w polskim komunikacie powodowało błąd składni AppleScript
   `-2741`. Zachowanie UTF-8 pozwala uruchomić natywne powiadomienie. Potwierdzono
   kod 0 osascript; nie jest to dowód przeczytania powiadomienia przez użytkownika.

Oba nowe testy regresyjne najpierw zawiodły dla właściwej przyczyny, następnie przeszły.
Zmiana produkcyjna obejmuje wyłącznie znacznik czasu i kodowanie stałego komunikatu.
Przejrzano pełny diff; nie zmieniono dostawców, zakresu API, kluczy ani uprawnień.

## Dowody odbioru

| Obszar | Wynik | Dowód |
|---|---|---|
| HEAD / checkout | PASS | Rzeczywisty checkout runtime czysty, przypięty do końcowego SHA powyżej |
| Config / permissions | PASS | Config/watchlist: te same SHA-256 przed i po; metadane poświadczeń bez zmian; pliki stanu 0600, katalogi 0700, zero symlinków i odchyleń |
| Rzeczywisty proces / LaunchAgents | PASS | `pl.gniewkob.isl.portfolio`: running, PID 86272, start 17:07:46 Europe/Warsaw; interpreter, moduł, konfiguracja i cwd zgodne z instalacją; jeden supervisor |
| Definicje launchd | PASS | Obie definicje identyczne bajtowo z prywatnym rollbackiem; supervisor KeepAlive, watchdog co 300 s |
| Canary before | PASS | Końcowy SHA, exit 0, READY_FOR_CONTROLLED_READ_ONLY_CANARY, w rzeczywistym checkout runtime |
| Cykl 1 | PARTIAL | Checkpoint 15:07:21.641308 UTC; świeży portfolio/health, zgodne pola; ważność dokładnie 1800 s; exit 2 |
| Cykl 2 | PARTIAL | Checkpoint 15:07:46.206007 UTC; nowszy od cyklu 1, spójne portfolio/health; ważność dokładnie 1800 s; exit 2 |
| Canary after obu cykli i uruchomionego demona | PARTIAL | Exit 3, LOCAL_METADATA_CANARY_PARTIAL; brak odrzucenia walidacji |
| Niezależny watchdog | PASS | PORTFOLIO_WATCHDOG_PARTIAL, exit 2 zgodny z jawną degradacją; poprawnie zapisany prywatny marker, ostatnia kontrola 15:10:51 UTC; powtórne kontrole bez błędu startu |
| Cykl po wznowieniu launchd | PARTIAL | Nowy checkpoint demona 15:08:11.345739 UTC; zgodne health/portfolio; finansowe operacje 0 |
| Coverage / backfill | PARTIAL | Ethereum COMPLETE_RANGE; Base SOURCE_UNAVAILABLE; latest_source_incomplete=true; zero zapisanych zakresów luk, NO_ELIGIBLE_GAP; odzyskane bloki 0 |
| Public RPC | PARTIAL | Ethereum finalized + publiczny test 80 bloków logów PASS; Base HTTP 429 w 3/3 ograniczonych próbach również przy 80 blokach |
| Exchange ↔ wallet | BLOCKED | full_autonomous_reconciliation_ready=false; brak zweryfikowanego source-side linkage, nie dopasowywano po kwocie/czasie |
| Pełna regresja | PASS | 539/539 lokalnie na czystym SHA poprawki oraz w rzeczywistym checkout scalonego release; 78/78 testów monitoringu pod interpreterem runtime |
| finance_ops | PASS | 0 we wszystkich rzeczywistych raportach i backfill; nie wywoływano operacji finansowych |

Cykl 1 i 2 to dwa kolejne kontrolowane `--once`, z odczytem i zachowaniem tego
samego prywatnego stanu. Następnie przywrócono właściwe LaunchAgenty i potwierdzono
nowy checkpoint ich demona. Nie deklarujemy obserwacji dwóch pełnych odstępów
900-sekundowego harmonogramu ani długoterminowego SLA. Watchdog jest jobem okresowym;
stan `not running` pomiędzy wywołaniami jest prawidłowy, ostatni exit 2 oznacza PARTIAL.

W obu końcowych cyklach: Exchange OK, historia kont OK, CDP Ethereum/Base OK,
Ethereum RPC OK, rynek OK, NBP OK; Base RPC PARTIAL. Historia kont OK oznacza
udany odczyt w zaimplementowanym zakresie, nie certyfikację pełnej historii konta.

## CI na dokładnych commitach

- Początkowy main `a3b24a7...`: [40104969457](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/40104969457), 537/537 PASS.
- PR exact head `00288bddb4031a79e6433a54613fe49556bf3421`:
  [40105387378](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/40105387378), 539/539 PASS przed scaleniem.
- Scalony i wdrożony main `892996c...`:
  [40105470963](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/40105470963), 539/539 PASS.
- Pierwsza próba pełnej regresji w venv usługi ujawniła brak testowego `psycopg`.
  Pełną regresję wykonano z zależnościami CI w odrębnym venv; nie zmieniono venv usługi.

## Ochrona danych, recovery i rollback

Zatrzymywano wyłącznie dwa wymienione joby portfela; nie uruchamiano drugiego
supervisora równolegle. Oryginalny commit oraz kopie obu plistów są dostępne
w prywatnym rollbacku 0700/0600 poza repo. Nie kopiowano kluczy. Po aktualizacji
zachowano wszystkie pliki stanu istniejące przed zmianą. Sprawdzono ich retencję
i uprawnienia; raport nie deklaruje niezależnej kryptograficznej certyfikacji każdego
historycznego rekordu. Lokalnie zachowano zanonimizowane receipts cykli i procesu.

Bezpieczny rollback: zatrzymać tylko `pl.gniewkob.isl.portfolio` i
`pl.gniewkob.isl.portfolio-health`, przypiąć uprzednio zapisany commit runtime,
przywrócić zapisane plisty wyłącznie gdy były zmienione, następnie bootstrap tych
dwóch jobów. Nie usuwać ani nie cofać prywatnego stanu, historii lub poświadczeń.
Pierwotna wersja ma opisane błędy czasów/powiadomień; jej przywrócenie nie oznacza
odzyskania zdrowia. Nie było potrzeby rollbacku końcowego release.

Testy syntetyczne istniejącego backfill potwierdziły limit 80 bloków łącznie na cykl,
zapis evidence przed zamknięciem luki, idempotentne retry przy rosnącym finalized head,
zachowanie luki przy błędzie/konflikcie i brak podwójnego liczenia. Nie tworzono
sztucznej luki w prywatnych danych. Brak zapisanej luki nie oznacza pełnej historii:
Base nie ma poprawnego początkowego okna coverage, więc rzeczywistego odzyskania
historii Base nie potwierdzono. Ethereum zweryfikowano w bieżącym ograniczonym oknie.

## Pozostałe ograniczenia i następne działania

- Base publiczny RPC nadal ogranicza odczyty. Istniejące deterministyczne zapytania,
  maksymalnie 3 próby, ograniczony backoff i limit Retry-After pozostają aktywne;
  nie zmieniano dostawcy ani nie kupowano RPC. Runtime ponawia odczyt w kolejnych
  cyklach i zachowuje PARTIAL; dalszy odbiór recovery wymaga udanego odczytu dostawcy.
- Nie certyfikujemy natywnych/internal transferów ETH, NFT/DeFi, pełnej historii
  Ethereum/Base, pełnej wyceny majątku, P&L ani EIA PIT. Nie dodajemy CDP do RPC
  ani podsumowań giełdy do sald kont.
- Bezpieczna kontynuacja przez operatora/agent: sprawdzić kolejny prawdziwy checkpoint
  po ustąpieniu 429; jeśli powstanie kwalifikująca luka, przyjąć recovery dopiero
  po trwałym evidence i spadku zakresu luki, najwyżej 80 bloków na cykl.
- Issue #77 pozostaje częściowo odebrane; PR i wdrożenie nie usuwają ograniczeń
  dostawcy ani brakującego linkage. Dostęp do Maca i autoryzacja wykonanych kroków
  nie są blockerem. Nie jest obecnie potrzebna decyzja techniczna użytkownika.

Ten dokument jest receipt odbioru, niezależny od przypiętego checkout runtime.
