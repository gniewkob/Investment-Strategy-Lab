# Working Engine v0.1 — codzienne cykle prywatnego laboratorium

## Środowiska

Projekt obecnie NIE ma produkcji. GitHub main to główna linia rozwoju,
Neon main \`br-shy-voice-badzlf0x\` to trwała baza prywatnego laboratorium
(projekt \`red-lake-53043722\`, baza \`investment_lab\`), a dodatkowe gałęzie
Neon służą wyłącznie izolowanym testom.

Pierwszy prawdziwy cykl na Neon main z 5.11.2026 (cutoff 19:00Z)
zakończył się pomyślnie: 3 research_runs, 3 signal_events, 3 audyty,
bez transakcji. Powtórzenie nie wstawiło duplikatów.

## Kontrakt zadania cyklicznego

Używaj istniejących, podłączonych narzędzi GitHub i Neon, bez kopiowania
danych dostępowych do repozytorium i bez dodatkowego połączenia do Coinbase.
Cel: automatyczna powtarzalna analiza **EDUKACYJNA**, nigdy realny handel.

1. Pobierz z ustalonego commitu repozytorium skrypt
   \`db/working_engine_v01_research_cycle.sql\`.
2. Wykonaj jeden identyczny, kompletny statement w Neon main; dopuszczalne
   są wyłącznie append-only research_runs, signal_events i audit_events
   przewidziane w tym skrypcie. **Nie** wstawiaj ani nie zmieniaj
   paper_events, contributions, valuations, instruments, permissions, trades.
3. Sprawdź odpowiedź dokładnie trzech modeli M1_GLOBAL_EQ,
   M2_DIVERSIFIED, M3_TACTICAL. Dozwolone persistence_state to
   NEW_RESEARCH_RUN lub IDEMPOTENT_REPLAY. REPLAY_INPUT_COLLISION
   jest błędem wymagającym analizy, nie poprawnym retry.
4. Uruchom odczytowy \`db/working_engine_v01_health_READONLY.sql\`,
   sprawdź ENGINE_OK 3/3, audit_rows=1 i signal_rows=1 dla każdego
   modelu oraz paper_fills=0. Weryfikacja odczytowa ma potwierdzić stan
   Neon, nie tylko status narzędzia.
5. Status SOURCE_STALE/SOURCE_MISSING jest osobnym problemem **źródeł**.
   Nie myl go z awarią silnika. Nie wypełniaj luk danymi syntetycznymi.
6. Raportuj błędy, zmianę statusu i nowe luki. Przy zdrowym cyklu bez
   zmian nie generuj codziennie długich raportów. Tygodniowe wyniki
   pozostają w dotychczasowym raporcie ISL.

Silnik działa na cutoff UTC 19:00 dziennie; domyślna pora kontroli
22:00 Europe/Warsaw to po cutoff także w czasie letnim. Harmonogram
jest zarządzany poza kodem w zleceniu cyklicznym; samo dodanie tego pliku
NIE aktywuje automatyzacji.

## Kryterium odbioru automatyzacji

- zadanie w harmonogramie jest aktywne, a jego termin potwierdzony;
- co najmniej dwa **naturalne** uruchomienia w różnych dniach
  dostarczają nowe research_runs dla 3 modeli albo idempotentne replay
  przy tej samej dacie, z trwałymi odczytami audytu;
- każda awaria connectora, brak cyklu, niezgodność audytu lub konflikt
  wejścia powoduje zrozumiały alert; brak transakcji;
- brak produkcyjnego release, brak ingerencji w historie funduszy.

Ważne: wyniki jednostkowych testów Postgresa i ręczne wywołanie
z 5.11.2026 potwierdzają silnik v0.1, **nie dowodzą dwóch naturalnych
cykli harmonogramu**. Nie ogłaszaj odbioru pracy autonomicznej,
dopóki dwa osobne dni nie zostaną potwierdzone.

## Granice i wstrzymanie

Zatrzymaj/wyłącz zadanie cykliczne, jeżeli potrzebne są zmiany w jego
uprawnieniach, SQL zachowuje się inaczej niż po testach, nie ma
potwierdzonej łączności albo pojawia się jakakolwiek próba operacji
finansowych. Nie usuwaj ani nie zmieniaj istniejących wyników tylko
po to, aby ponownie uruchomić eksperyment. Nie zmieniaj harmonogramu
miesięcznych wpłat wirtualnych — ten należy do osobnego raportu
poniedziałkowego, nie do silnika codziennego.
