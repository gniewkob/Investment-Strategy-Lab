# ISL v0.11 — POLSTR CI względem siły nabywczej HICP (PL)

## Zakres

Połączony, oryginalnie źródłowy, **retrospektywny** benchmark 48 osobnych
fikcyjnych wpłat po 100 PLN miesięcznie: **2022-01–2025-12**. Nie są to
rzeczywiste wpłaty, rachunek bankowy, inwestycje ani zlecenia.

Źródła:

- [GPW Benchmark — roczne oryginalne tabele POLSTR CI](https://www.gpwbenchmark.pl/dane_historyczne)
  ([2022](https://www.gpwbenchmark.pl/pub/BENCHMARK/files/Dane/PDF/POLSTR_2022.pdf),
  [2023](https://www.gpwbenchmark.pl/pub/BENCHMARK/files/Dane/PDF/POLSTR_2023.pdf),
  [2024](https://www.gpwbenchmark.pl/pub/BENCHMARK/files/Dane/PDF/POLSTR_2024.pdf),
  [2025](https://www.gpwbenchmark.pl/pub/BENCHMARK/files/Dane/PDF/POLSTR_2025.pdf)).
- [Eurostat HICP `prc_hicp_minr`](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table):
  `geo=PL`, `freq=M`, `coicop18=TOTAL`, `unit=I25`, 2022-01–2025-12.
  Źródło: Eurostat. Publikowane **obecnie** szeregi HICP za lata 2022–2025
  zostały przeliczone według ECOICOP v2 i odniesione do **2025=100**;
  nie są kopiami danych dostępnych w konkretnych historycznych dniach.
  Eurostat udostępnia odrębny szereg *first published* `prc_hicp_fpd`.
  [Metadane HICP](https://ec.europa.eu/eurostat/cache/metadata/en/prc_hicp_esms.htm),
  [zasady ponownego użycia](https://ec.europa.eu/eurostat/help/copyright-notice).

## Metoda

Moduł `scripts/polstr_hicp_purchasing_power_v11.py` uruchamia maksymalnie
pięć odczytów HTTPS: 4 stałe PDF GPW i jedno zapytanie JSON-stat Eurostatu.
Waliduje komplet 48 miesięcy bez interpolacji, odrębne tożsamości wskaźników,
liczby dodatnie i skończone, oraz pochodzenie odpowiedzi.

Na koniec każdego miesiąca przypisuje *wyłącznie matematycznie* 100 PLN do
jednostek POLSTR CI, z poziomem indeksu z ostatniego dostępnego dnia miesiąca:

`POLSTR_ref = Σ[100 × POLSTR_CI(2025-12) / POLSTR_CI(m)]`.

Dla HICP oblicza nominalny odpowiednik siły nabywczej tej samej osobnej
wpłaty, skorygowany do średniego poziomu cen w ostatnim miesiącu:

`HICP_ref = Σ[100 × HICP(2025-12) / HICP(m)]`.

Następnie `POLSTR_ref - HICP_ref` pokazuje **różnicę dwóch teoretycznych
punktów odniesienia**, nie realny zysk. POLSTR ma wartość na koniec miesiąca,
a HICP opisuje **średni poziom cen w miesiącu** — uproszczenie kalendarza.
Wyniki są liczone w `Decimal` przed końcowym zaokrągleniem do 2 miejsc,
co chroni przed błędem o 1 grosz przy odejmowaniu.

## Potwierdzony odczyt 23.11.2026

| Miara | Wynik |
|---|---:|
| Oryginalne PDF GPW | 4/4; 252, 251, 252, 251 wierszy dziennych |
| Eurostat HICP | 48/48 miesięcy, zero braków |
| Łączna liczba żądań źródłowych | 5 |
| Wpłaty fikcyjne nominalne | 4 800,00 PLN |
| Terminalny odpowiednik jednostek POLSTR CI | 5 345,55 PLN |
| Skorygowana HICP równowartość wpłat | 5 188,39 PLN |
| **Różnica odniesienia POLSTR do HICP** | **+157,16 PLN** |
| Brak waloryzacji nominalnych wpłat względem HICP | 388,39 PLN |
| Zmiana HICP: I 2022–XII 2025 | +28,47% |

Hash 4 oryginalnych PDF jest identyczny z niezależnym odczytem v0.10.
SHA-256 **kanonicznego JSON** z Eurostat to
`4efe02361f27fb8d933d7921e406ee280b5f54d03c098b83420223550481b3d2`
(nie hash oryginalnych bajtów HTTP). Wartość `updated` wskazana przez dostawcę:
`2026-11-18T11:00:00+0100`; nie jest timestampem pierwszego wydania
każdego historycznego punktu.
SHA-256 pokwitowania nowego przebiegu:
`d2457ce0de5da523c3b7b474d34b8dde39f953fbb2b575ee0e00803ed1859c75`.

**Ograniczenia krytyczne:** POLSTR CI ma 40 miesięcy wstecznie obliczonych
przed produkcyjnym startem wskaźnika; nie jest lokatą, funduszem, obligacją
ani ceną wykonalnej transakcji. HICP jest indeksem cen konsumpcyjnych,
nie dochodową serią inwestycji. Nie ma opodatkowania, kosztów, cen wykonania
ani certyfikacji point-in-time. M1/M2/M3 nadal
`INSUFFICIENT_DATA_HOLD_CASH`; **0 zapisów DB, 0 zleceń**.
Surowe szeregowe dane nie są publikowane w repo ani zapisane przez moduł.

## Reprodukcja

Wymaga Python 3.12+ oraz systemowego `pdftotext` (Poppler), bez nowych
zależności Python. Katalog wyjściowy nie może istnieć. Domyślnie brak sieci.

```bash
python3.12 -m unittest tests.test_polstr_hicp_purchasing_power_v11 -q
python3.12 -m unittest discover -s tests -q

python3.12 -m scripts.polstr_hicp_purchasing_power_v11 \
  --allow-public-official-read \
  --out-dir /tmp/isl-polstr-hicp-v11
```

Zapisuje wyłącznie agregaty i skróty źródeł w `polstr_hicp_reference_v11.json`
oraz czytelny raport `polstr_hicp_reference_v11.md`. Gdy dowolna walidacja
zawiedzie, nie tworzy katalogu wynikowego. Testy używają tylko syntetycznych
PDF i JSON-stat; nie sprawdzają połączenia z systemem transakcyjnym.
