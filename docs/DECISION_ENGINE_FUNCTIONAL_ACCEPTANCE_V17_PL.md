# ISL Decision Engine — kryteria odbioru funkcjonalnego (właściciel, 2026-11-07)

**Cel biznesowy:** ukończyć **działający cykl badawczy**: rzeczywiste kwalifikowane dane rynkowe → reguły M1/M2/M3 → zamrożony, odtwarzalny wynik decyzji → kolejne rzeczywiście późniejsze obserwacje → uczciwe porównanie hipotetycznych wyników i kosztów. Dodatkowy offsite/WORM pozostaje LOW/BACKLOG; nie jest bramką tego odbioru. Istniejącej ochrony danych ani reguł źródłowych nie wolno usuwać.

## Bramka A — działający silnik (techniczna)

Wymagane łącznie:

1. Silnik przyjmuje jawne manifesty i uruchamia zamknięte polityki M1/M2/M3, z `HOLD_CASH` dla brakujących lub niespójnych danych. Każdy model ma status, uzasadnienie i ścieżkę dowodową.
2. Powtarzalny cykl produkuje deterministyczny hash decyzji; nie dopisuje w ukryciu danych, nie zmienia historii i nie polega na danych z przyszłości.
3. Wiele chronologicznych cykli tworzy powiązany łańcuch potwierdzeń, z odrębnymi statusami `PAPER_CANDIDATE_ONLY`, `HOLD_CASH` i `NOT_EVALUABLE`.
4. Ewaluacja celu jest dopuszczalna dopiero po zamknięciu kolejnego miesiąca, ze sprawdzonym wcześniejszym punktem odniesienia. Model zatrzymany przez v0.15 nie może dostać sztucznego forward return mimo obecności teoretycznego celu v0.5.
5. Testy negatywne obejmują brakujące dane, look-ahead, zmieniony fingerprint, chronologię, korekty danych, niekwalifikowaną podstawę `PRICE_ONLY` i próbę ustawienia trybu live.
6. Regresja całego Working Engine i dedykowanych testów przechodzi na **dokładnym commicie**, na którym oparto decyzję odbiorową.

**Stan:** v0.16 potwierdzono w CI na historycznie zachowanym prawdziwym zdarzeniu GitHub bez danych rynkowych (HOLD_CASH); v0.17 dodaje wielookresowy łańcuch i ewaluację forward, których odbiór wymaga zielonego CI. Testy na syntetycznych poziomach nigdy nie są dowodem historycznych wyników rynku.

## Bramka B — rzeczywiste dane wejściowe (materialna, nadal BLOCKED)

Każda z trzech rodzin `GLOBAL_EQUITY_TR_PLN`, `PL_BONDS_TR_PLN`, `GOLD_TR_PLN` wymaga:

- rzeczywiście pozyskanego i zarchiwizowanego szeregu **min. 36 kolejnych miesięcy**, poprawnej waluty PLN, zgodnej definicji wyniku/total return, daty obserwacji oraz momentu dostępności do decyzji;
- weryfikowalnej nazwy oryginalnego dostawcy, wersji, raw-byte SHA-256 i przynależności ekonomicznej (benchmark kontra instrument); rzeczywistego prawnego uprawnienia do danego sposobu wykorzystania danych;
- osobnego wskazania, co zweryfikowano niezależnie, a co tylko zadeklarowano w manifeście. `source_status=VERIFIED_ORIGINAL` to samoopis i **nie** jest wystarczającym dowodem;
- braku cichego przepisania NBP gold `PRICE_ONLY`, FX ani niehandlowalnego TBSP na instrument o rzekomej inwestowalności.

Gdy brakuje którejkolwiek wymaganej rodziny, nie wolno deklarować pełnego `DATA_READY` ani rzeczywistego rankingu M1–M3. Modele z pełnym zbiorem wymagań można oceniać osobno bez wyciągania wniosków o pozostałych.

## Bramka C — rzeczywista ocena kolejnych miesięcy (materialna, nadal BLOCKED)

- Zamrożone sygnały są zapisywane **przed** późniejszą obserwacją; co najmniej **dwa niezależne, chronologicznie późniejsze miesiące** z kwalifikowanymi obserwacjami stanowią minimalny smoke test przepływu OOS (nie próbę dowiedzenia przewagi).
- Dla każdego miesiąca: data decyzji, dostawca, SHA źródła, baza poziomu, późniejsze obserwacje, status `NOT_EVALUABLE` gdy brak danych, osobne koszty jako **założenia**.
- Raport prezentuje liczbę *rzeczywiście* ocenialnych okresów i bez dodatkowej analizy nie deklaruje alpha, Sharpe ani przyszłej rentowności; dwa miesiące nie wystarczą do mocnych wniosków statystycznych.
- Wymagane co najmniej jedno sprawdzone niezależne powtórne uruchomienie na zachowanych rzeczywistych danych, z identycznym hashem wyników. Wyłącznie deklarowany w manifeście timestamp nie dowodzi dostępności point-in-time.

## Bramka D — reżim wykonania

Cały etap pozostaje **edukacyjnym paper research**: nie ma rzeczywistych kupna, sprzedaży, transferu, podłączania portfeli ani wykonywania zleceń. `orders_sent=0`, `paper_fills=0`, `financial_operations=0`, `database_writes=0` w tych modułach. Zmiany działających schedulerów i zapis do Neon nie są tu elementem wdrożenia.

## Mechanizm odbioru

**TECHNICAL_PASS** oznacza zieloną regresję algorytmu i deterministyczny przebieg na prawdziwie zachowanym zdarzeniu; **REAL_DATA_ACCEPTANCE** pozostaje **BLOCKED**, dopóki B+C nie mają niezależnych dowodów. Nie nadawać całości statusu DONE tylko dlatego, że CI przeszło. Raport v0.17 jawnie zwraca `market_data_acceptance=BLOCKED_INDEPENDENT_SOURCE_AND_PIT_EVIDENCE` niezależnie od własnych deklaracji wejścia. Wersja v0.17 umożliwia stopniowe gromadzenie przyszłych dowodów, ale sama ich nie tworzy.

## Najbliższa realizacja

Podłączyć faktyczne historie przez źródłowe adaptery i jawne manifesty, zamrozić pierwszy obserwowalny cykl, odebrać następne zamknięte miesiące bez look-ahead, przeprowadzić odtwarzalną ocenę; raportować osobno poziom jakości źródeł, działanie algorytmu i wyniki hipotetyczne. Nie inwestować dalszego czasu w dodatkowy backup przed tą funkcjonalnością.
