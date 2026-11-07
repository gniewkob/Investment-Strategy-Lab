# v0.4 — pięcioletnie archiwum referencyjne NBP, 2021–2026

## Odbiór danych źródłowych: PASS

W dniu 6.11.2026 rzeczywisty odczyt API NBP został przeprowadzony
w GitHub Actions na kodzie PR #96:

- [Run #42228167332 — oficjalny odczyt NBP](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42228167332)
- Workflow: .github/workflows/nbp-long-history-v04.yml
- Kod: scripts/nbp_long_history_monthly.py, współdzielący
  sprawdzony scripts/nbp_reference_capture.py
- Zakres: **2021-11-01–2026-10-31**, 60 pełnych miesięcy
- 21 kolejnych niepokrywających się okien do 90 dni,
  razem **42 odczyty HTTPS** oficjalnego API NBP
- 60 końcowych rzeczywiście opublikowanych obserwacji USD/PLN,
  60 EUR/PLN (średni kurs tabeli A) oraz 60 cen 1 g złota
  w PLN: razem **180 miesięcznych rekordów**
- 7/7 testów offline kolektora PASS. Pełna regresja
  repo po dodaniu kolektora: [CI #42228167063](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42228167063) PASS.
- Plik źródłowy (publiczne dane i 42 poświadczenia odpowiedzi)
  jest załączonym artefaktem GitHub Actions
  \`nbp-5y-reference-202111-202610\`, ID \`13506657367\`.
  Data wygaśnięcia artefaktu: **20 listopada 2026**; workflow
  może odtworzyć dane ponownie, ale nowy odczyt będzie miał nowy
  timestamp i potencjalnie inny SHA. Nie traktować nowego retrievalu
  jako tej samej niezmiennej historycznej wersji.

**SHA-256 dokumentu wejściowego** (kanoniczny JSON, bez pola hash):
\`58b22c10b7fab1fc09fbf07b1ff627cd8993e9df05b8ec8b308df31cd53b86b3\`

Po pobraniu artefaktu zweryfikowano osobno:
1. Kanoniczny SHA-256 dokumentu = zapisany fingerprint.
2. 180/180 obserwacji ma poprawną datę zgodną z miesiącem.
3. Każdy wpis wskazuje dokładnie jedno okno źródłowe
   oraz jego rzeczywisty URL, SHA-256 pobranych bajtów
   i timestamp pobrania.
4. 60 różnych uporządkowanych miesięcy na każdą serię;
   żadnych interpolacji, syntetycznych luk ani wartości
   dopisanych w miejsce braku publikacji.
5. Brak dostępu do Neon, Coinbase, kont, portfeli;
   0 transakcji, 0 papierowych filli.

## Konkretne obserwacje — bez sugestii tradingowych

Poniższe zmiany to zmiana **poziomów referencyjnych** między
ostatnim notowaniem listopada 2021 a ostatnim notowaniem
października 2026; NIE są stopą zwrotu inwestora, wynikiem
instrumentu możliwego do kupienia ani wynikiem strategii M1–M3.

| Seria | 30.11.2021 | 30.10.2026 | Zmiana referencji |
|---|---:|---:|---:|
| NBP EUR/PLN tabela A | 4,6834 | 4,3955 | −6,147% |
| NBP USD/PLN tabela A | 4,1214 | 3,9251 | −4,763% |
| Złoto NBP PLN/g | 239,02 zł | 511,29 zł | +113,911% |

Zmianie ceny złota nie towarzyszy założenie o kosztach dostępu,
spreadzie, magazynowaniu, opodatkowaniu ani instrumentach
replikujących. Ceny walut to kursy średnie NBP, nie bid/ask.

## Niezmienione ograniczenia danych i modeli

Oficjalna [instrukcja NBP](https://api.nbp.pl/) potwierdza
archiwum FX od 2002 r., złoto od 2013 r. i maksymalny zakres
93 dni na zapytanie. Kod używa 90 dni dla marginesu bezpieczeństwa.

Obie serie FX mają \`return_basis=FX_RATE\`, a złoto
\`return_basis=PRICE_ONLY\`. Wszystkie należą do
\`NON_EXECUTABLE_REFERENCE_ONLY\`. Faktyczny czas historycznej
pierwszej publikacji i pierwotny vintage nadal nie są poświadczone.
Plik zawiera daty publikacji i rzeczywiste pobranie w 2026 r.,
a nie sfabrykowany historyczny timestamp dostępności.

**Nie wolno mapować** tego archiwum na:
\`GLOBAL_EQUITY_TR_PLN\`, \`PL_BONDS_TR_PLN\` ani
\`GOLD_TR_PLN\`. Wszystkie trzy serie wymagane przez Backtesting
Engine v0.4 są nadal nieobecne w Neon LAB. Historyczny backtest
M1/M2/M3 pozostaje \`NOT_RUN_SERIES_MISSING\`.

Równoległe oficjalne źródła do dalszej pracy:
- [Vanguard — FTSE All-World UCITS ETF, akumulujący,
  ISIN IE00BK5BQT80](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits)
  udostępnia historyczny NAV w USD. Nie jest to cena wykonania
  zlecenia na giełdzie; do PLN potrzebne jest poprawnie dobrane FX.
- [BondSpot — archiwum TBSP.Index](https://www.bondspot.pl/tbsp_index_archiwum?month=1&year=2025)
  i [metodologia indeksu](https://www.bondspot.pl/pub/Regulacje_TBS_Poland/UZ_271-19-Regulamin_Indeksu_Treasury_BondSpot_Poland_obow._25_11_2019.pdf):
  indeks dochodowy polskich obligacji, nie kupowany instrument.
  Nie potwierdzono jeszcze stabilnego 36+ miesięcznego pobrania
  tej serii w postaci danych z oryginalnych wydań.

## Następny krok funkcjonalny

1. Zabezpieczyć reprodukowalny archiwalny zrzut JSON z GitHub
   jako stały dowód referencji (obecny artefakt jest czasowy).
2. Odczytać autentyczne NAV Vanguard w USD i TBSP.Index PLN,
   przetestować parsery na rzeczywistych pobraniach oraz spójny
   wspólny kalendarz z historycznym NBP FX. Nie zakładać
   możliwości trade fill po indeksie.
3. Dopiero po walidacji kompletnych serii i kosztów uruchomić
   edukacyjny porównawczy M1/M2/M3 na odrębnych danych badawczych.
   Nie robić z opisu rynku zmyślonego wyniku inwestycji.

W tej iteracji kod i wszystkie źródłowe odczyty są read-only.
Nie modyfikowano harmonogramu silnika v0.3 ani Neon main.
