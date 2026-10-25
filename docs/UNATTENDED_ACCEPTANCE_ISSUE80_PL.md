# Issue #80 — odbiór naturalnych cykli na Macu

## Decyzja na 24.10.2026, 18:10 UTC: PARTIAL

- Rzeczywisty runtime: `c0b543015f61692a85808f11e577c8c13fd4dc8f`, checkout czysty.
- Jeden supervisor `pl.gniewkob.isl.portfolio`, PID **5676**, start **18:00:43 UTC**.
  KeepAlive/RunAtLoad; Base `PUBLICNODE` w środowisku załadowanego joba.
- Konfiguracja: 900 sekund. Kod wykonuje `sleep(900)` **po ukończeniu** odczytu;
  rzeczywiste odstępy obejmują czas wykonania. Watchdog: 300 sekund, ostatni exit 0.
- Checkpoint **18:01:04.030346 UTC**: OBSERVATION_OK; Coinbase, historia kont,
  CDP Ethereum/Base, RPC Ethereum/Base, rynek i NBP: wszystkie OK.
  Ważność do **18:31:04.030346 UTC**; marker watchdoga **18:06:22.458772 UTC**.
- Ethereum pokrycie baseline–ostatni blok **26262198–26264090**;
  Base **53036085–53037084**. Oba COMPLETE_RANGE, zero zapisanych luk,
  brak overflow/reset. Bieżące żądane okna mają po 1000 bloków.
  Backfill NO_ELIGIBLE_GAP, odzyskane bloki 0. Historia sprzed baseline niepotwierdzona.
- Prywatny receipt niezależnego testu **18:00:16.477534 UTC**: 7 × HTTP 200,
  zero 429. To test kontrolowany, a nie dowód harmonogramu.
- Zapisane wcześniejsze receipts `--once` i nadpisywane checkpointy nie tworzą
  archiwum 24h. Nie rekonstruujemy brakujących cykli z uptime ani liczby uruchomień launchd.
- Rollback kodu/definicji istnieje poza Git, 0700/0600. Plist sprzed przełączenia
  dostawcy różni się od obecnego, zgodnie z wcześniejszym rolloutem PublicNode;
  nie deklarujemy ich identyczności. Nic nie cofnięto ani nie nadpisano.
- Brak transakcji i zmian uprawnień. Runtime raportuje financial_operations=0.

## Trwała agregacja

`scripts/unattended_acceptance.py` jest osobnym, standard-library-only kolektorem.
Czyta lokalnie portfolio/health/watchdog i odczytowe metadane git/launchd/ps.
Nie odczytuje kluczy, nie wywołuje sieci, nie uruchamia cyklu ani watchdoga,
nie przejmuje ich blokad i nie zmienia stanu portfela. Nie publikuje danych automatycznie.

Osobny LaunchAgent uruchamia kolektor co 60 sekund, RunAtLoad, bez KeepAlive.
Kod kolektora jest skopiowany do osobnego prywatnego katalogu; nie zależy od
checkoutu roboczego ani nie zmienia przypiętego runtime. Output 0700, pliki 0600:
append-only `samples.jsonl`, atomowy `summary.json`, osobny `collector.lock`.
Każdy zapis jest fsync; nie ma rotacji usuwającej dowody. Limit dziennika 64 MB
zatrzymuje zapis z kodem 2 i wymaga zachowania/przeglądu istniejących dowodów.

Do dziennika trafia stały schemat: czasy, PID/start procesu, SHA, hash obu plistów,
statusy ośmiu grup źródeł, zakresy bloków/liczby luk, limit odzyskania i booleany
świeżości/spójności. Odrzucamy adresy, etykiety portfela, salda, zdarzenia,
identyfikatory zakresów, błędy upstream, alerty jako tekst i prywatne ścieżki.
Pierwszy checkpoint jest baseline'em, nie nowym cyklem naturalnym.
Duplikaty timestampów nie podnoszą liczby checkpointów. Widoczny `--once`, drugi
supervisor, inny SHA, restart, nieaktualność lub niepoprawny odczyt blokują odbiór.
Nie da się wykluczyć krótkiego obcego procesu pomiędzy próbkami; to obserwacja
co minutę, nie instrumentacja wykonania ani niezmienialny zewnętrzny audyt.

Podsumowanie przelicza odbiór po każdej próbce: rzeczywisty początek/koniec UTC,
unikalne nowe checkpointy, statusy, przerwy kolektora >120 s, odstępy cykli
poza 900–1020 s (120 s jawnej tolerancji na wykonanie), zmiany PID/definicji.
Nominalne 900-sekundowe przedziały to punkt odniesienia, nie gwarancja dokładnie
96 cykli na dobę. Akumulacja czasu wykonania jest jawna. Cały dziennik pozostaje
konserwatywny: wcześniejsza awaria nie znika po udanym następnym cyklu; nowy okres
kwalifikacyjny wymaga osobnego outputu z zachowaniem poprzedniego.

## Ograniczenia odbioru automatycznego

**PARTIAL pozostaje prawidłowe także po pełnych 24h**, jeśli brak dowodów wymaganych
przez issue. Obecny runtime nie utrwala liczników odpowiedzi HTTP ani 429:
`http_429_count=null`, nigdy domyślne zero. Udane retry może maskować wcześniejsze 429.
Brak naturalnego recovery/zmiany statusu nie potwierdza rzeczywistych przejść watchdoga;
syntetyczne testy nie są próbą awarii produkcyjnej. Collector dokumentuje przerwy
obserwacji także podczas uśpienia Maca, ale ich nie naprawia restartem.

Aktualne źródła, coverage i backfill mogą być PASS dla bieżącej obserwacji;
nie są certyfikatem pełnej historii, powiązania giełda–chain, P&L czy wartości majątku.
Nie ma rozszerzenia metod RPC ani uprawnień Coinbase. Bez runtime telemetry nie
certyfikujemy zera 429. Nie zmieniamy supervisora tylko dla uzyskania zielonego wyniku.

## Kontrole i rollback

Testy syntetyczne obejmują baseline/duplikaty, pełne 24h bez fałszywego PASS,
restart/przerwę/awarię źródła, `--once`, opóźnione cykle, prywatność projekcji,
rozbieżne checkpointy, limit 80 bloków, watchdog, uprawnienia i symlinki.
Pełna regresja na bazowym SHA + kolektor: wynik zapisany w PR.

Rollback kolektora: bootout **wyłącznie** `pl.gniewkob.isl.acceptance`.
Zachować dziennik, summary i kopię kodu. Supervisor, watchdog, checkpointy,
konfiguracja, klucze i poprzednie rollbacki pozostają nietknięte.
Automatyczny odbiór czyta summary po realnym upływie 24h i raportuje brakujące
warunki; nie interpretuje samego zainstalowania harmonogramu jako wykonania.

## Instalacja i odbiór odroczony

Na Macu uruchomiono `pl.gniewkob.isl.acceptance`; pierwszy rzeczywisty zapis
**2026-10-24 18:12:03.219346 UTC**, exit 0. Okno 24h może zakończyć się najwcześniej
**2026-10-25 18:12:03.219346 UTC**. Instalacja nie jest dowodem całej przyszłej doby.
Osobna automatyzacja Codex `investment-lab-odbi-r-issue-80` jest ACTIVE, co godzinę:
pozostaje cicha bez istotnej zmiany; po upływie 24h odczyta wynik i przekaże jeden
raport, po czym ma się wstrzymać. Wymaga działającego Maca/aplikacji; ciągłość
samego kolektora i automatyzacji musi zostać oceniona z przyszłych zapisów.
To nie jest druga instancja odczytująca Coinbase ani drugi supervisor.

## Ustalenia po pełnym oknie, 25.10.2026

Pierwsze rzeczywiste pełne okno: 24.10 **18:12:03.219346** – 25.10
**18:12:23.877249 UTC**, **86420,657903 s**, 1423 próbki. Nowe naturalne
checkpointy: **94**, w tym **83 OBSERVATION_OK / 11 PARTIAL**, wszystkie PARTIAL
na RPC Ethereum. Pozostałe siedem grup źródeł 94/94 OK. Nominalne przedziały
900 s: 96; odstępy rzeczywistych checkpointów **919,116624–937,510678 s**,
zero ponad 1020 s. Najdłuższy odstęp kolektora **64,901244 s**, zero ponad 120 s.
Zero zapisanych zakresów luk i odzyskanych bloków; nie oznacza pełnej historii.
Zero nieświeżych próbek watchdoga; 20 obserwowanych zmian statusu, bez certyfikacji
dostarczenia powiadomień. HTTP429 nadal UNKNOWN. Wynik całego okna: **PARTIAL**.
SHA-256 pierwszych 1423 dokładnych linii dziennika:
`b6998318bb9b7674768fc845a115ec925b538d83440da854828f45c694d06c89`.
Automatyzację jednorazowego odbioru usunięto po raporcie; kolektor nadal działa.

Zmiana definicji watchdoga zaobserwowana 24.10 **19:38:13.216767 UTC** pochodzi
z osobnego wdrożenia powiadomień ntfy: [PR #82](https://github.com/gniewkob/Investment-Strategy-Lab/pull/82),
merge **fcc7c2cc774b98d29af5a4286278c8ebac432038**, oraz receipt wdrożenia PR #83.
Checkout `notification-app` jest obecnie czysty na tym SHA; supervisor pozostaje
na c0b5430. Poprzednia kontrola kolektora wymagała tego samego checkoutu dla obu
jobów i dlatego błędnie odrzucała poprawny osobny checkout watchdoga.

Poprawiona kontrola akceptuje wyłącznie pierwotny checkout/SHA lub ten konkretny,
zweryfikowany notification checkout/SHA; wymaga zgodności z załadowanym launchd
oraz czystego kodu. Nie czyta configu ntfy, nie wysyła powiadomień. Zmiana definicji
nadal jest faktem historycznym; nie przepisujemy dziennika ani wyniku zakończonego
okna. Poprawka przygotowana do wdrożenia, istniejący kolektor jeszcze jej nie uruchamia.
