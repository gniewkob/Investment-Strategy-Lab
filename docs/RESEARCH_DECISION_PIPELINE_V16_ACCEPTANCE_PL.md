# Investment Strategy Lab — v0.16: uruchamialny cykl decyzji badawczych

**Cel: uruchomić rzeczywisty przepływ na dostępnych danych — nie budować kolejnych zabezpieczeń DR przed działającą logiką.** v0.16 nie zastępuje polityk M1–M3: uruchamia v0.15 i v0.5 oraz generuje deterministyczny, porównywalny raport.

## Co działa

`scripts/research_decision_pipeline_v16.py` ma dwa źródła wejścia:

1. `--archived-v09`: odczytuje istniejący plik `evidence/shadow/v09/checkpoint-bundle-run-42305280062.json` z prawdziwego wcześniejszego workflow GitHub. Kontroluje hashe wewnętrznego capture i decyzji, zgodność checkpointu, run ID, head SHA, brak operacji finansowych oraz **ponownie oblicza** oryginalną decyzję v0.5. Ostateczny wynik dla tego archiwum to `HOLD_CASH_SOURCE_OR_CONFIRMATION_BLOCKED`, wszystkie M1–M3 w `HOLD_CASH`, z powodem `SOURCE_MISSING`. Nie oznacza to braku aktywności silnika: to prawidłowy kontrolowany wynik na archiwalnym zdarzeniu bez serii kwalifikowanych total return.
2. `--current` (opcjonalnie `--previous`): bierze dostarczony manifest rzeczywistych lub jawnie syntetycznych danych, uruchamia istniejące źródłowe bramki v0.5 i politykę v0.15, zwraca `PAPER_RESEARCH_CANDIDATES_ONLY` lub `HOLD_CASH_SOURCE_OR_CONFIRMATION_BLOCKED`. M3 wymaga dwóch kolejnych zgodnych miesięcznych obserwacji i niezmienionego historycznego prefiksu danych.

Wyjście zawiera: wynik każdego modelu, kod przyczyny, blokady, hipotetyczne cele, identyfikatory manifestów i kontrolera, pochodzenie archiwum oraz deterministyczne `cycle_receipt_sha256`. Tego receiptu **nie zapisuje automatycznie** do bazy ani brokera. W przypadku syntetycznych manifestów możliwości modelu są demonstracją logiki, nie empiryczną przewagą.

## Realne uruchomienie z dostępnym archiwum

```bash
cd "$HOME/Repos/Investment-Strategy-Lab-shadow-v12"
python3 -m unittest discover -s tests -p 'test_research_decision_pipeline_v16.py' -v
python3 -m scripts.research_decision_pipeline_v16 \
  --archived-v09 evidence/shadow/v09/checkpoint-bundle-run-42305280062.json
```

Są to wyłącznie odczyty offline, bez Neon i Coinbase.

## Ważne ograniczenia

- Archiwum GitHub zawiera 1 potwierdzony rekord decyzji z pustymi seriami — nie można z niego wywnioskować cen, zysków ani okazji. Nie rozciągamy poprawnego testu na rzekomy ciągły monitoring rynkowy.
- Zgodność wewnętrznych hashy i GitHub metadata jest spójnością odczytanych dokumentów, **nie** niezależną autentykacją oryginalnych bajtów artefaktu, certyfikacją czasu PIT ani praw do źródeł.
- Brak kompletu GLOBAL_EQUITY_TR_PLN, PL_BONDS_TR_PLN, GOLD_TR_PLN oznacza `HOLD_CASH`; NBP GOLD `PRICE_ONLY` ani BondSpot TBSP nie mogą być przemianowane na inwestowalne wyniki.
- `PAPER_RESEARCH_CANDIDATES_ONLY` oznacza wyłącznie propozycje edukacyjne, nigdy zlecenia. `orders_sent=0`, `paper_fills=0`, `financial_operations=0`, `database_writes=0`.
- v0.16 nie modyfikuje istniejących lokalnych harmonogramów, backupów, portfeli ani Neon.

## Kolejne funkcjonalne kroki

1. Wprowadzić **rzeczywiste kwalifikowane dane** przez ich jawne manifesty, nie przez samodzielne poświadczenie statusu `VERIFIED_ORIGINAL`. Uruchamiać kontroler na każdej nowej obserwacji.
2. Dodać lokalne, append-only zapisy wielu niezależnych cykli i ewaluację na kolejnej obserwacji; bez automatycznego zapisu do Neon i bez tworzenia zleceń.
3. Na większej, niezależnej próbie porównać M1/M2/M3 i hipotetyczne koszty bez optymalizacji na holdout.
4. Offsite DR/niezależna kopia WORM: LOW/BACKLOG według decyzji właściciela, nie blokuje badawczego cyklu.

**Wniosek:** v0.16 pozwala wykonywać prawdziwy, powtarzalny przepływ decyzji na historycznie zapisanym zdarzeniu. Nie dostarcza jeszcze decyzji o kupnie/sprzedaży ani udokumentowanej skuteczności strategii.
