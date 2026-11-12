# Investment Strategy Lab — Public-First v0.1: NBP Gold / FX / Cash (12.11.2026)

**Issue:** [#142](https://github.com/gniewkob/Investment-Strategy-Lab/issues/142)  
**Decyzja kosztowa:** zero nowych opłat za dane. Obecny budżet badawczy 100 PLN/mies. nie uzasadnia dokupowania abonamentów GPW/MSCI, jeżeli silnik może się rozwijać na źródłach publicznych.

## 1. Dane, z których rzeczywiście korzystamy

| Komponent | Pierwotne źródło i zakres | Interpretacja |
|---|---|---|
| `GOLD_NBP_PLN_G` | [NBP API — ceny złota](https://api.nbp.pl/), seria od 2013-01-02 | Cena referencyjna 1 g złota w PLN, **PRICE_ONLY**; bez spreadu, kosztu przechowywania, VAT i ceny zlecenia |
| `USDPLN_NBP` | [NBP API — Tabela A](https://api.nbp.pl/), dostępne kursy od 2002-01-02 | Kurs średni PLN za USD; **nie jest ceną wymiany u brokera ani stopą zwrotu inwestora** |
| `EURPLN_NBP` | [NBP API — Tabela A](https://api.nbp.pl/) | Kurs średni PLN za EUR, tylko odniesienie FX |
| `CASH_PLN` | Założenie porównania, nie seria rynkowa | Nominalna gotówka z zerową stopą procentową |

NBP oficjalnie opisuje publiczne API: odpowiedzi JSON, archiwalne kursy, ceny złota, maksymalnie 93 dni w zapytaniu oraz protokół HTTPS. Wykorzystujemy **do 90 dni** na zapytanie, wyłącznie oficjalną domenę `api.nbp.pl`. Reużywamy parsera `scripts/nbp_reference_capture.py`, nie tworzymy ponownie adaptera ceny czy klucza dostępowego.

### Faktyczna pierwsza próba

Pierwsza próba na **rzeczywistych danych**, bez żadnych statystyk fikcyjnie generowanych, obejmuje 60 zakończonych miesięcy **2021-11 do 2026-10**, po jednej **ostatniej opublikowanej w miesiącu** obserwacji z każdego z 3 szeregów. Nie wymagamy identycznej daty publikacji kursu FX i złota (NBP może stosować różne kalendarze). Brak opublikowanej obserwacji w końcówce miesiąca, duplikaty lub niedopuszczalny typ źródła zatrzymują badanie. Nie wypełniamy luk interpolacją ani przyszłą ceną.

## 2. Przypadki porównawcze — całkowicie nieegzekwowalne

Bez zmiany wcześniejszego silnika M1–M3, porównujemy **odrębne scenariusze**:

1. `CASH_PLN_ZERO_INTEREST_REFERENCE`: 100 PLN hipotetycznie miesięcznie, zero odsetek; nominalna baza porównania.
2. `GOLD_NON_EXECUTABLE_MONTH_END_REFERENCE`: referencyjne frakcyjne jednostki liczone po historycznych cenach NBP z końców miesiąca.
3. `USDPLN_NON_EXECUTABLE_MONTH_END_REFERENCE`: matematyczne referencyjne jednostki przeliczone po średnim USD/PLN NBP.
4. `EURPLN_NON_EXECUTABLE_MONTH_END_REFERENCE`: analogiczna referencja EUR/PLN.

Dla wariantów 2–4 pokazujemy dwa **stałe założenia kosztu**: 0 punktów bazowych (diagnostyka) i 30 bps (stress-test jednokierunkowego kosztu nabycia jednostek referencyjnych). **Nie** są to realne spready ani opłaty konkretnej instytucji. Symulacja nie ma ceny transakcyjnej ani faktycznej daty wykonania. Wpłata w miesiącu `m` nabywa jednostki referencyjne **według końcowego poziomu tego miesiąca** i nie zarabia na zmianie ceny w tym samym miesiącu. W rzeczywistości takiego zlecenia z gwarancją ceny nie da się zrealizować po jej publikacji. Te dane służą tylko ilustracji wrażliwości matematycznej na zmianę wartości, nie prezentacji rzeczywistych wyników inwestowania.

## 3. Dwutorowy model dalszego rozwoju

- **Tor public research (nowy):** `PUBLIC_REFERENCE_RESEARCH_ONLY`. Dopuszcza opisowe statystyki i ograniczone scenariusze matematyczne na oryginalnych publicznych poziomach, bez prognoz lub transakcyjnych decyzji. Wystarczą realne dane i jawna metodologia.
- **Tor qualified M1–M3 (istniejący, bez zmian):** wymaga poprawnie sklasyfikowanych serii `GLOBAL_EQUITY_TR_PLN`, `PL_BONDS_TR_PLN`, `GOLD_TR_PLN` oraz niezależnego przeglądu historycznych wersji i uprawnień. W NBP gold nadal jest `PRICE_ONLY`; `USDPLN_NBP` nie staje się globalnym indeksem akcji; `TBSP.Index` bez prawa ponownego użycia nie jest automatycznie zatwierdzony. `M1–M3=NOT_RUN_UNQUALIFIED_TOTAL_RETURN_SERIES` i `HOLD_CASH` pozostaje w mocy.

**Bardzo istotne:** dzisiejsza odpowiedź API NBP na historyczne daty to odczyt **z dzisiejszego archiwum**. `effectiveDate` i `data` podają dzień publikacji, nie godzinę pierwszej dostępności ani historyczny zapis przed korektami. Dlatego `historical_source_vintage_certified=false` i `historical_publication_hour_certified=false` zawsze. SHA-256 odpowiedzi potwierdza tylko bajty **pobrane teraz**, nie to, że były identyczne przed laty.

## 4. Safety / security / koszt

- Bez nowych licencji, opłat, subskrypcji i API keys.
- Bez zleceń, transferów, sald, portfela, Coinbase, brokera, Neon DB, migracji, produkcyjnych schedulerów, persistencji badań do bazy i zdarzeń paper-account.
- CLI wymaga jawnej flagi `--allow-public-nbp-fetch`. Testy offline nie mogą wykonać żadnego żądania sieciowego.
- Dane oryginalne nie trafiają do repozytorium. Workflow loguje ograniczony dokument pobrania z URL/sha i zagregowane wyniki; nie zachowuje pełnych dziennych wartości.
- Liczba miesięcy wynosi maksymalnie 60, potrzeba co najmniej 12 pełnych; `source_snapshot` jest tylko retrospektywną próbą, bez nieuprawnionej kwalifikacji historycznej PIT.
- Źródła publiczne sprawdzamy zgodnie z ich warunkami; brak subskrypcji nie oznacza automatycznego prawa do wtórnej redystrybucji.

## 5. Powtarzalny test

```sh
python -m unittest tests.test_public_first_nbp_reference_research_v01 -v
python -m scripts.public_first_nbp_reference_research_v01 \
  --start-month 2021-11 --end-month 2026-10 --allow-public-nbp-fetch
```

Pełną regresję uruchamiamy po zmianach w skrypcie i testach, a osobny workflow uruchamia jednorazowo **oryginalny NBP live source** (bez danych dostępowych). Kod jest czystym stdlib Python i wywołuje istniejący `capture`; nie ma żadnej ścieżki do SQL, wallet czy tradingu.

## 6. Kryteria zakończenia #142

- [ ] Prawdziwy, kompletny 60-miesięczny odczyt NBP ze źródłowymi SHA i bez brakujących miesięcy.
- [ ] Dwie konfiguracje kosztów i cztery w pełni oznaczone scenariusze bazowe, wyniki bez twierdzeń o transakcyjnej wykonalności.
- [ ] 14 negatywnych/pozytywnych testów offline Linux i macOS; pełna regresja istniejącego repozytorium.
- [ ] Niezależne review dokładnego SHA PR, zielony GitGuardian; regresja po merge na dokładnym SHA `main`.
- [ ] Zachowana osobna i niezależna kolejka danych źródłowych/licencji #97/#116/#123/#138, niewykonywanie M1–M3.

**Następnie:** dołączać inne *udokumentowane* źródła publiczne w tym samym torze typowanym, a płatny dostęp rozpatrywać dopiero, kiedy precyzyjnie wskażemy brakującą serię i wykażemy wartość biznesowo-badawczą. Nie używać dostępności strony WWW jako domniemanej licencji.