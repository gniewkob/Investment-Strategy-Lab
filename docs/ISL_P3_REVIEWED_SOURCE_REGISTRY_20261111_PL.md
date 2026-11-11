# ISL P3 — rejestr źródeł i wiązanie dowodów z opublikowanym artefaktem

**Data:** 11.11.2026  
**Repozytorium:** `gniewkob/Investment-Strategy-Lab`  
**PR:** #124, Draft  
**Decyzja:** `SOURCE_REGISTRY_SCAFFOLD_ACCEPTED` / `NO_REVIEWED_SOURCES` / `MODEL_ADMISSION_BLOCKED`.

## 1. Kontekst

P2 `src/isl_v2/total_return_evidence_preflight.py` ocenia kompletność, poprawność jednostek i spójność *zadeklarowanej* historii publikacji. Nie uwierzytelnia jednak dostawcy, nie odczytuje źródłowych bajtów i nie ma prawa przyznać statusu PIT. P3 oddziela zaufaną konfigurację źródła od tego, co twierdzi dokument lub operator.

## 2. Stan faktyczny — zero zatwierdzonych źródeł

Nowy moduł `src/isl_v2/reviewed_source_registry.py` przechowuje osobny, niemodyfikowalny w runtime rejestr `REVIEWED_SOURCE_PINS`. Obecnie zawiera **0 rzeczywistych wpisów**. Trzy wymagane pozycje:

| Kod modelu | Obecny status | Co trzeba dostarczyć |
|---|---|---|
| `EQUITY_TR_PLN` | `PIN_REVIEW_REQUIRED` | Tożsamość wydawcy i oznaczenie *total return*, licencja, waluta PLN, oficjalny identyfikator, wydane wersje |
| `BONDS_TR_PLN` | `PIN_REVIEW_REQUIRED` | To samo, dodatkowo metodologia naliczania kuponu i terminu zapadalności |
| `GOLD_TR_PLN` | `PIN_REVIEW_REQUIRED` | To samo, dodatkowo wykazanie, czy jest to **indeks TR**, czy cena spot w PLN (nie utożsamiać) |

Wpisy nie mogą być tworzone na podstawie samej deklaracji dostarczonej z obserwacją; brak przeglądu źródła nie jest zastępowany wpisem `approved=true`.

## 3. Kontrakt przypięcia pojedynczego artefaktu

`ReviewedSourcePin` wiąże kod instrumentu z `source_code`, `official_series_id`, **dokładnym kanonicznym URL HTTPS**, `license_url`, `source_version`, SHA-256 oryginalnych bajtów, znaną datą publikacji `first_public_at`, walutą, typem indeksu, definicją zwrotu i interwałem. Rekord jest immutable (`dataclass(frozen=True)`).

Testowany w izolacji weryfikator:

- odrzuca podmianę serii, indeksu, waluty, domeny i URL, źródła z parametrami uwierzytelnienia, nieprawidłowe identyfikatory, niespójny hash;
- sam **wylicza SHA-256 z bajtów** otrzymanego artefaktu i porównuje z niezależnie przypiętym hashem. Nie ufa polu `source_sha256` z payloadu;
- odrzuca datę publikacji po historycznej decyzji i pobranie/kopię pozyskaną dopiero po niej; daty muszą być jednoznaczne, ze strefą;
- ma limit wielkości wejścia 1 MB, a sam moduł **nie wykonuje żadnego HTTP, nie używa sekretów ani nie zapisuje danych**.

**Precyzyjne ograniczenie:** jeśli dane bajty odpowiadają pinowi, wynik mówi tylko `artifact_sha256_matches_reviewed_pin=true`. Weryfikator lokalny nie potrafi sam potwierdzić pochodzenia sieciowego, wiarygodności zegara czy daty pierwszej publicznej dostępności. Z tego powodu zawsze zwraca `source_network_origin_attested=false`, `capture_clock_independently_attested=false`, `historical_pit_certified=false`, `model_admission_granted=false`, `qualified_model_series=[]`.

Publiczny entrypoint `verify_registry_candidate` **zawsze blokuje** obecnie niezatwierdzony wpis przez `NO_REVIEWED_SOURCE_PIN`; prywatny helper do testów syntetycznych nie podłącza niczego do decyzji.

## 4. Co byłoby potrzebne do rzeczywistego wpisu

1. Zidentyfikować niezależnie na stronie wydawcy prawdziwy instrument, jego oficjalną definicję indeksu całkowitego zwrotu, historię metodologii, walutę i prawo użycia danych.
2. W zaufanym, kontrolowanym procesie pobrać oryginalny artefakt ze sprawdzonej domeny, zachować checksumę i podpisaną notatkę z datą faktycznego pobrania.
3. Oddzielnie zebrać dowód oryginalnych historycznych wersji i dat pierwszej dostępności danych. **Dzisiaj pobrany stary plik nie jest dowodem, że był pobrany w przeszłości.**
4. Zweryfikować każdą transformację (np. waluta, ceny, dywidendy, kupony) i pokrycie dla wybranego modelu.
5. Poddać dodanie pinu i dopuszczenie do parsera `parse_observation` **osobnej recenzji i autoryzacji**. Ten PR nie zawiera takich działań.

To wybory metodologiczne ISL, a nie przypisywane bez weryfikacji wymagania ISO, NIST ani ustawodawstwa.

## 5. Odbiór techniczny

- Moduł: `src/isl_v2/reviewed_source_registry.py`.
- Testy: `tests/test_reviewed_source_registry.py` (23 scenariusze syntetyczne: podmiana domeny, identyfikatora i sumy, próby nadania uprawnień przez flagi, niedozwolone daty PIT, błędne URI i 0 prawdziwych zaufanych pinów).
- CI: `.github/workflows/isl-reviewed-source-registry-ci.yml` — Ubuntu i macOS.
- Pełna regresja: `.github/workflows/full-agent-staging-canary-ci.yml`.

Testy dowodzą **stabilności kontroli**, a nie poświadczenia zewnętrznego wydawcy. `REVIEWED_SOURCE_PINS=0` jest świadomym stanem bezpieczeństwa, nie błędem CI.

## 6. Rozstrzygnięcie

Matematyczna zgodność modeli Swinkels pozostaje oddzielnym wynikiem badawczym, a dostęp PIT przez ALFRED pozostaje zablokowany brakiem `FRED_API_KEY`. Niniejszy rejestr nie obchodzi żadnego z tych ograniczeń.

**Bez zmian:** PR #124 Draft, `qualified_model_series=[]`, M1–M3 `INSUFFICIENT_DATA/HOLD_CASH`, brak transakcji, transferów, zmian w Neon, modyfikacji ról lub ustawiania sekretów.
