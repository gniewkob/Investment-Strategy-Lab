# ISL v0.8 — pojedynczy przebieg publicznych źródeł

**Cel:** zastąpić ręczne przygotowanie pięciu spójnych pokwitowań
jednym odczytowym przebiegiem MF, UKNF, NBP i Eurostat. Jest to
uzupełnienie przekrojowego raportu v0.7 z PR #159, nie silnik inwestycyjny.

## Uruchomienie lokalne

```bash
python3.12 -m scripts.public_first_one_shot_v08 \
  --allow-public-official-read \
  --out-dir /tmp/isl-public-source-report-v08
```

Uruchomienie wymaga świadomej zgody na jeden zestaw publicznych odczytów HTTPS.
Bez flagi program przerywa **przed** jakimkolwiek pobraniem. Docelowy katalog
musi nie istnieć; nie są nadpisywane wcześniejsze wyniki. Do katalogu trafiają:

- `market_research_v07.json` — agregaty i spójne pokwitowania źródłowe;
- `market_research_v07.md` — raport opisowy po polsku;
- `public_source_run_v08.json` — rzeczywisty czas przebiegu, liczba odczytów,
  SHA-256 raportu i potwierdzenie braku operacji finansowych.

Żadne oryginalne XLSX, surowe jednostkowe NAV ani pełne tablice cen nie są
zapisywane do wyników. Domyślnie przy błędzie któregokolwiek źródła katalog
wyniku nie powstaje. Program nie łączy się z Neon, kontem inwestora ani brokerem.

Gdy niedostępne są wyłącznie makroźródła (błąd HTTP lub połączenia), można
dodać `--allow-macro-unavailable`. Powstaje wtedy jawny wynik **PARTIAL**:
oddzielne, zweryfikowane MF/UKNF pozostają dostępne, ale brak jest
przekrojowego porównania MF–UKNF–NBP–Eurostat. Błąd struktury, sum,
identyfikatorów, jednostek lub SHA nadal blokuje raport; brakujące wartości
nie są szacowane.

## Kontrakt i ograniczenia

| Źródło | Pobrania maksymalne | Interpretacja |
|---|---:|---|
| UKNF | 4 | dzienna historia jednej kategorii jednostek PLN, nie total-return |
| MF | 1 | oryginalny XLSX z miesięcznymi obrotami, nie cena obligacji |
| NBP | 2 | złoto i średnie USD/EUR w PLN, ceny referencyjne |
| Eurostat | 2 | HICP i nominalna rentowność PL 10Y, nie zwrot z obligacji |

Łącznie **8–9 dozwolonych pobrań**, bez automatycznego ponawiania, bez
harmonogramu, bez płatnych API. Wykorzystane są wyłącznie istniejące
walidatory, limity i allowlisty źródeł z v0.5–v0.7. Stały zakres raportu:
**wrzesień 2026** (historia MF do 2026-09), z dłuższymi archiwami
odpowiednich źródeł. To **nie jest** bieżący listopadowy sygnał rynkowy.

Prawdziwy odczyt jest udowodniony dopiero, gdy cały przebieg HTTPS i parserów
na konkretnym kodzie zakończy się `PASS`. Testy z fikcyjnymi odpowiedziami
potwierdzają wyłącznie logikę. Hash oznacza spójność odebranych bajtów, nie
autentyczność, brak rewizji ani dostępność historyczną point-in-time.

Modele M1/M2/M3 pozostają `INSUFFICIENT_DATA_HOLD_CASH`: nominalny NAV,
obrót, poziom rentowności i kursy referencyjne **nie są** legalnym substytutem
zweryfikowanych, inwestowalnych serii PLN total-return. Nie powstają
zlecenia, transakcje, transfery, wpisy do bazy ani nowe plany automatyzacji.

## Testy

```bash
python3.12 -m unittest tests.test_public_first_one_shot_v08 -v
python3.12 -m unittest discover -s tests -q
```

Testy obejmują łączenie wszystkich pięciu pokwitowań, limity liczby
zapytań, odrzucenie nieprawidłowych typów danych, zakaz pobierania bez
zgody, ochronę istniejących wyników i brak częściowych wyników po
nieudanym odczycie źródła. Brak potrzeby GitHub Actions do wykonania
testów lokalnych.
