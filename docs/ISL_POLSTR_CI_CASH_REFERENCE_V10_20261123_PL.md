# ISL v0.10 — oficjalny POLSTR CI jako benchmark gotówkowy

## Cel i granice

Zamiast zakładać fikcyjną stopę procentową dla gotówki, moduł
`scripts/polstr_cash_reference_v10.py` odczytuje i waliduje cztery
**oryginalne roczne pliki PDF administratora GPW Benchmark** za 2022–2025.
Zawierają daty wskaźnika, POLSTR oraz skumulowany indeks `POLSTR_CI`.
Wyniki to wyłącznie historyczne odniesienie badawcze, nie produkt
inwestycyjny, depozyt, fundusz obligacji ani wskazanie do transakcji.

Źródła i podstawa znaczenia indeksu:

- [GPW Benchmark — dane historyczne POLSTR](https://www.gpwbenchmark.pl/dane_historyczne),
  odnośniki do rocznych oryginalnych PDF.
- [POLSTR 2022](https://www.gpwbenchmark.pl/pub/BENCHMARK/files/Dane/PDF/POLSTR_2022.pdf),
  [2023](https://www.gpwbenchmark.pl/pub/BENCHMARK/files/Dane/PDF/POLSTR_2023.pdf),
  [2024](https://www.gpwbenchmark.pl/pub/BENCHMARK/files/Dane/PDF/POLSTR_2024.pdf),
  [2025](https://www.gpwbenchmark.pl/pub/BENCHMARK/files/Dane/PDF/POLSTR_2025.pdf).
- Administrator jednoznacznie oznacza okres sprzed 30.05.2025 jako
  historię **preprodukcyjną**, obliczoną retrospektywnie. Odbycie
  późniejszego pobrania oryginalnego PDF **nie dowodzi**, że te konkretne
  wartości i wersje były dostępne w dniu historycznej decyzji.

## Uruchomienie

```bash
python3.12 -m scripts.polstr_cash_reference_v10 \
  --allow-public-official-read \
  --out-dir /tmp/isl-polstr-reference-v10
```

Wymagane jest dostępne polecenie `pdftotext` (Poppler). Na macOS
można je zainstalować niezależnie od projektu przez `brew install poppler`;
bez niego moduł zwraca jednoznaczny błąd. Nie dodano zależności Python.
Istniejący katalog wynikowy zostaje odrzucony przed odczytem sieci.
Bez flagi odczytowej nie ma żadnego żądania HTTPS.

Przebieg wykonuje maksymalnie **cztery stałe żądania HTTPS**, po jednym na
rok, bez retry. Sprawdza oryginalny nagłówek PDF, limit 2 MB, nagłówek
tabeli, poprawne daty, walutowe poziomy liczbowe, dzienne duplikaty,
minimum 10 obserwacji na miesiąc i obecność notowania blisko jego końca.
Wymaga 12 miesięcy rocznie bez uzupełniania luk. Oryginalne pliki,
dzienne notowania i kompletne miesięczne szeregi są przetwarzane wyłącznie
w pamięci. Lokalne pliki wynikowe to:

- `polstr_reference_v10.json`: agregaty, cztery SHA-256 oryginałów,
  liczności dni, czasy rozpoczęcia/zakończenia i SHA pokwitowania;
- `polstr_reference_v10.md`: krótki opis nominalnego scenariusza.

Obliczenie zakłada fikcyjne 100 PLN *na koniec każdego miesiąca* oraz
ułamkową ilość **niekupowalnych jednostek indeksu**. Końcowy odpowiednik
każdej wpłaty to `100 × (ostatni poziom POLSTR_CI / poziom w miesiącu
wpłaty)`. Suma jest porównywana do 48 × 100 PLN bez odsetek. Nie ma
opodatkowania, rzeczywistych stawek depozytowych, opłat, spreadów,
transakcji ani realnych wpłat. To nie jest zysk możliwy do uzyskania
na rachunku czy strategia paper trading z wykonalnymi zleceniami.

## Dowód z oficjalnych oryginałów — 23.11.2026

| Kontrola | Wynik |
|---|---:|
| Oryginalne PDF | 4/4 |
| Wiersze dzienne 2022, 2023, 2024, 2025 | 252, 251, 252, 251 |
| Ciągłe miesiące | 48, 2022-01 do 2025-12 |
| W tym miesiące przed produkcją POLSTR | 40 |
| Fikcyjne łączne wpłaty | 4 800,00 PLN |
| Końcowa wartość odniesienia indeksowego | 5 345,55 PLN |
| Różnica nominalna, przed podatkami i kosztami | +545,55 PLN |

Oryginalne SHA-256: 2022 `d69590a92521b01642e4d1158413611eddf6d2c8dee59ce29c2b74d78b8b5f18`,
2023 `fa35292f5c4e4f3958b613b95d048775331f79e708fe520c9e20ec996476d1da`,
2024 `0006787d400f5495812ed231a6c734fe012f7f8ebd4121b8a368b5b6dc5b0751`,
2025 `c41783b1b075b28e84985c1c5c5fd2b97b58f142597a5f4a0332acd1e9c91a84`.
Wynik pochodzi z odczytu oficjalnych oryginałów, nie z fixture testowego;
SHA samodzielnie nie potwierdza autentyczności ani historycznej dostępności.

Wszystkie M1/M2/M3 nadal `INSUFFICIENT_DATA_HOLD_CASH` i brak serii
`qualified_total_return_series`; POLSTR CI nie zastępuje akcji globalnych,
polskich obligacji dochodowych ani złota. Wykorzystywanie/rozpowszechnianie
danych referencyjnych poza prywatną analizą wymaga odrębnej oceny warunków
GPW Benchmark. Nie publikujemy kompletnych szeregów oryginalnych danych.

## Testy

```bash
python3.12 -m unittest tests.test_polstr_cash_reference_v10 -q
python3.12 -m unittest discover -s tests -q
```

Testy offline obejmują brak miesiąca, duplikat, niewłaściwy rok,
nieprawidłowe wartości, ucięty koniec miesiąca, brak opt-in, odmowę
nadpisania raportu, brak zapisu oryginalnych szeregów i brak operacji
finansowych. Testy syntetyczne nie są dowodem historycznej dostępności.
