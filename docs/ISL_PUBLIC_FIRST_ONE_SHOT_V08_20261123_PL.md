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

Gdy niedostępne są makroźródła (błąd HTTP lub połączenia), można
dodać `--allow-macro-unavailable`. Powstaje wtedy jawny wynik **PARTIAL**:
oddzielne, zweryfikowane MF/UKNF pozostają dostępne, a Eurostat HICP i
Eurostat PL 10Y są dodatkowo weryfikowane niezależnie, bez powtarzania
już podjętych zapytań. Jeśli oba są kompletne, raport zawiera opisową
różnicę nominalnej rentowności od wstecznej inflacji HICP, ale nie łączy
jej z brakującym NBP i nie udaje zwrotu inwestora. Błąd struktury, sum,
identyfikatorów, jednostek lub SHA nadal blokuje raport; brakujące wartości
nie są szacowane. Niezależne Eurostat nie stanowią `PASS` pełnego zestawu.

## Kontrakt i ograniczenia

| Źródło | Pobrania maksymalne | Interpretacja |
|---|---:|---|
| UKNF | 4 | dzienna historia jednej kategorii jednostek PLN, nie total-return |
| MF | 1 | oryginalny XLSX z miesięcznymi obrotami, nie cena obligacji |
| NBP | 6 | trzy autentyczne odpowiedzi każdej rodziny, zakresy 1–10, 11–20, 21–30 września; złoto i średnie USD/EUR w PLN |
| Eurostat | 2 | HICP i nominalna rentowność PL 10Y, nie zwrot z obligacji |

Łącznie **12–13 dozwolonych pobrań**, bez automatycznego ponawiania, bez
harmonogramu, bez płatnych API. Wykorzystane są wyłącznie istniejące
walidatory, limity i allowlisty źródeł z v0.5–v0.7. Stały zakres raportu:
**wrzesień 2026** (historia MF do 2026-09), z dłuższymi archiwami
odpowiednich źródeł. To **nie jest** bieżący listopadowy sygnał rynkowy.

Adapter NBP A2 jest zamrożony i zachował dokładny Git blob
`07f97726687540960bdae2ef93070a86844473bd`. Nowy moduł
`scripts/nbp_reference_chunked_v09.py` wywołuje go dla trzech rozłącznych
okien. Każdy oryginalny URL, `retrieved_at` i SHA-256 faktycznie odebranych
bajtów pozostaje osobnym pokwitowaniem. Wspólny `nbp_fx`/`nbp_gold` w
pokwitowaniu agregacji to **hash kanonicznego manifestu fragmentów**, nie
SHA fikcyjnej odpowiedzi HTTP dla całego miesiąca. Weryfikator odrzuca
zmienione lub nieciągłe zakresy oraz rozbieżność daty/URL/SHA w wierszu.

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

## Rzeczywiste źródła, przebieg 2026-11-23

Odczyt `--allow-macro-unavailable` był `PARTIAL`, ponieważ NBP zwracał
HTTP 404 dla części żądanych zakresów. Pozostałe źródła przeszły własne
walidatory oryginalnych odpowiedzi:

- MF: 202 miesiące; ostatni obrót `3140385.25` mln PLN; SHA XLSX
  `5fd7f4fceb1403f1978553079e3a566a70e04d849af29c6a9c7ee41a7d5f42c8`.
- UKNF: 22 dni NAV jednej klasy; SHA historii
  `cc12a89d7f16bdccf16715427cda76f231ff21af82732e5736641d15264eea85`.
- Eurostat HICP: 13 miesięcy, zmiana roczna 3,9892%; kanoniczny SHA JSON-stat
  `070fa4b19f883f66ca517d29bade6bbfb65117e7b1b899428cd972cbbbfc7a47`.
- Eurostat PL 10Y: 59 miesięcy, wrzesień 2026 `6.23%` nominalnie; SHA raw
  `acc302b641ca981b5c8e22259a613d092e5c12d0cb01e39e7e093c07c59c3abf`.
- Opisowa różnica nominalnej rentowności i rocznej zmiany HICP: `2.2408` p.p.,
  **nie** realny zwrot obligacji.

Brak dowodu pierwszej historycznej publikacji; nie przekształcać tych
poziomów w inwestowalne PLN total-return, nie wykonywać zleceń.
