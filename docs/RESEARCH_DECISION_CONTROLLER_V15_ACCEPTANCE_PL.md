# Investment Strategy Lab — v0.15 Decision Controller M1–M3

**Cel:** oddzielić generowanie hipotetycznego sygnału badawczego od jego kwalifikacji do porównania papierowych strategii, z jawnie udokumentowaną polityką stanu. v0.15 jest następnym przyrostem **silnika decyzyjnego**, a nie kolejnym adapterem backupowym.

## Architektura działania

`scripts/research_decision_controller_v15.py` korzysta z dotychczasowego `scripts/shadow_decision_engine_v05.py` zamiast kopiować reguły źródłowe. Przyjmuje jawny, kompletny manifest obecnej decyzji i opcjonalny *wcześniejszy* manifest z oddzielnej obserwacji. Najpierw uruchamia pełną kontrolę źródeł v0.5: PLN, 36 kolejnych miesięcy, świeżość, podany SHA-256, zdefiniowany TOTAL_RETURN, brak look-ahead, źródło i deklaracja praw. Każdy wykryty brak albo niekwalifikowana referencja jest powodem `HOLD_CASH`.

| Model | Polityka v0.15 | Status dopuszczalny |
|---|---|---|
| M1 — globalne akcje | Jeśli seria equity przechodzi pełną kontrolę v0.5, dopuszczamy jedynie propozycję badawczą M1 | `PAPER_CANDIDATE_ONLY` |
| M2 — dywersyfikacja | Jeśli wszystkie trzy serie przechodzą kontrole v0.5, dopuszczamy propozycję porównawczą M2 | `PAPER_CANDIDATE_ONLY` |
| M3 — taktyczna | Pełne trzy serie, **dwie zgodne obserwacje kolejnych miesięcy** i niezmieniony historyczny prefiks danych; sygnał risk-on/risk-off musi być taki sam w obu | `PAPER_CANDIDATE_ONLY` albo `HOLD_CASH` |

Dla M3 świeża zmiana reżimu prowadzi do `REGIME_CHANGE_AWAIT_CONFIRMATION`, a korekta starych danych do `HISTORICAL_OBSERVATIONS_REVISED_OR_MISSING`. Brak poprzedniego manifestu lub wcześniejszych kwalifikowanych źródeł także skutkuje `HOLD_CASH`. **Dwumiesięczne potwierdzenie jest arbitralną predeklarowaną hipotezą ograniczenia obrotu**, nie odkrytą statystycznie lepszą regułą. Rozwinięcie M3 może zatem reagować z opóźnieniem.

## Rezultat i ograniczenia

Każda odpowiedź zawiera:

- `model_states`: status, powód, blokady i cel tylko dla kwalifikowanych propozycji badawczych.
- `paper_candidates`: lista modeli dopuszczonych do dalszego eksperymentu, nie ranking przewagi inwestycyjnej.
- `source_blockers`: źródła brakujące, przestarzałe lub niezgodne z wymogiem PLN total return.
- `current_source_manifest_sha256`, `current_v05_receipt_sha256`, opcjonalnie wartości poprzedniej obserwacji oraz `controller_receipt_sha256`.

Nie wykonuje żadnych zleceń, nie tworzy fill ani nie zapisuje do Neon i nie dotyka Coinbase/portfeli. Wszystkie pola `historical_point_in_time_certified`, `source_rights_independently_certified`, `independent_capture_certified`, `investment_performance_proven` i `market_execution_authorized` są **false**. Dane z `example.invalid` w testach są syntetyczne; ich zaliczenie nie nadaje autoryzacji prawnej rzeczywistym źródłom. Identyczność hashów lokalnych danych nie dowodzi niezależności publikacji ani braku retrospektywnych korekt u dostawcy.

## Wywołanie

```bash
python3 -m unittest discover -s tests -p 'test_research_decision_controller_v15.py' -v

# Własne, zweryfikowane, historycznie datowane manifesty badawcze:
python3 -m scripts.research_decision_controller_v15 \
  --current /path/to/current-research-manifest.json \
  --previous /path/to/previous-research-manifest.json
```

Brak `--previous` jest dozwolony: M1/M2 pozostają ograniczone do własnych bramek danych, a M3 przechodzi w `PREVIOUS_SNAPSHOT_MISSING`. Nic nie zostaje automatycznie odczytane z osobistego portfela ani zapisane na dysku przez CLI.

## Kryteria odbioru

Wymagany PASS testów deterministycznych i negatywnych: brak serii, częściowa kompletność, zgodne risk-on/risk-off, zmiana reżimu, korekta historii, niekolejne miesiące, blokada źródeł, ten sam/future as-of, tryb live, PRICE_ONLY, integralność hashy i brak modyfikacji wejścia. Dodatkowo pełna regresja Working Engine E2E na SHA z PR.

**Istotne ograniczenie biznesowe:** nadal nie posiadamy kompletu trzech niezależnie poświadczonych, kwalifikowanych rzeczywistych serii historycznych. Dla archiwów NBP/TBSP uruchamiany dotychczas shadow engine musi raportować `HOLD_CASH`; nie wolno mu promować `PRICE_ONLY` i niehandlowalnego indeksu do `TOTAL_RETURN` instrumentów inwestowalnych. Następny priorytet to podłączenie źródłowych manifestów do kontrolera, walidacja prospektywna i weryfikacja działania kolejnych miesięcznych porównań, zamiast optymalizacji wyników na sztucznej historii.

**Dalsze DR/offsite pozostają LOW/BACKLOG.**
