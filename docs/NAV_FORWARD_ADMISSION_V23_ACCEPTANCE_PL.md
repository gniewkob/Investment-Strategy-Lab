# ISL v0.23 — kontrola dopuszczenia przyszłej obserwacji NAV (read-only)

**Stan 2026-11-07:** listopad 2026 nie jest jeszcze zamknięty, wobec tego prawidłowy wynik na istniejącym prywatnym manifeście to `PENDING_FIRST_POST_FREEZE_ORIGINAL_MONTH`, bez wyników future / out-of-sample.

## Kontekst i kotwica

Wersja v0.22 została faktycznie uruchomiona lokalnie. Zamrożony manifest SHA:
`3b8aca44ffa6aa72bf2d3a0b5d49102f0dd857d11191dc10e7d21b5051e704a2`.

Zewnętrzny zapis identyfikatora: https://github.com/gniewkob/Investment-Strategy-Lab/issues/97#issuecomment-6712908994 .

Kotwica GitHub potwierdza publiczne ujawnienie skrótu najpóźniej w czasie publikacji komentarza, ale nie dowodzi rzeczywistej tożsamości pliku, licencji ani dokładnego historycznego PIT. Mechanizm v0.23 waliduje SHA prywatnego manifestu i porównuje go z *jawnie wpisanym* opublikowanym skrótem. Nie zmienia oryginalnego manifestu ani nie nadaje mu nowego statusu.

## Reguły

- Domyślnie brak nowej obserwacji → `PENDING_FIRST_POST_FREEZE_ORIGINAL_MONTH`, liczba kwalifikowanych miesięcy forward = 0.
- Tylko pierwszy planowany pełny miesiąc 2026-11 może być przedstawiony jako kandydat. Dopuszczenie informacji przed 2026-12-01 jest zabronione, w tym każda obserwacja częściowa.
- Ewentualny plik kandydata JSON musi zawierać dokładne wartości i daty nowego NAV USD, USDPLN NBP oraz NAV PLN, skrót nowego *oryginalnego* pliku eksportu, skrót odpowiedzi NBP, czas faktycznego pobrania obu oraz URL NBP dla **dokładnego dnia NAV**. Kwoty mają pozostać lokalne.
- Daty pobrania muszą następować po zamrożeniu, a eksport NAV musi być pobrany po dacie obserwacji. Kurs NBP musi być datowany na ten sam dzień; nie wolno interpolować ani podstawiać kursów z innego dnia.
- Nowy eksport musi mieć inny skrót niż przedzamrożeniowy plik z 2026-11-07.
- Poprawny kandydat daje `CANDIDATE_FORWARD_REFERENCE_REQUIRES_INDEPENDENT_SOURCE_REVIEW`, **nadal zero kwalifikowanych okresów**. Skrót i data pobrania podane przez użytkownika nie są niezależną atestacją oryginalności; potrzebny jest odrębny audyt oryginalnych bajtów i danych źródłowych.
- Nie obliczać z nowego NAV bezwarunkowej efektywności, nie odblokowywać `GLOBAL_EQUITY_TR_PLN`, M1, M2 ani M3. Wszystkie wykonania handlowe, zapisy do Neon, transakcje oraz transfery: 0.

## Lokalny odczyt stanu — natychmiast

Uruchomić na przetestowanym SHA v0.23:

```bash
python3 -m scripts.nav_forward_admission_v23 \
  --freeze "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/forward-freeze-v22-20261107.json"
```

CLI nie wykonuje połączeń z GitHub ani źródłami finansowymi; porównuje manifest z zakodowanym hashem opublikowanym wcześniej na GitHub. CLI wypisuje wyłącznie status, skróty i flagi kwalifikacji, nie wartości NAV.

## Granice funkcjonalne

Mechanizm v0.23 jest **walidatorem dopuszczenia**, nie automatycznym pobieraczem nowych notowań ani zewnętrznym audytorem publikacji NAV. Etap po zakończeniu listopada wymaga nowego, legalnie pozyskanego oryginalnego eksportu Vanguard, odpowiedzi NBP z tej samej daty, ich SHA oraz czasu pobrania. Dopiero oddzielny walidator oryginalnych bajtów pozwoli przejść od kandydata do referencyjnej obserwacji forward.

**Odbiór v0.23:** rygorystyczny status PENDING z prawidłową kotwicą; niezmienność protokołu; testy odrzucenia wcześniejszej daty, niepełnego miesiąca, fałszywego SHA, błędnego FX i samodzielnej promocji M1. Testy CI są syntetyczne. Prawdziwy wynik na prywatnym manifeście wymaga osobnego lokalnego uruchomienia.
