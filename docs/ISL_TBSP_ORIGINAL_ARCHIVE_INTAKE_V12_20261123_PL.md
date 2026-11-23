# ISL v0.12 — offline oryginalne archiwum TBSP.Index

## Cel

Włączyć polski dochodowy benchmark obligacji skarbowych do przygotowania
badawczego **bez** naruszania warunków wykorzystania danych lub podszywania
się pod wykonalną cenę instrumentu. TBSP.Index ma udokumentowaną definicję
*total return*: obejmuje ceny obligacji, narosłe odsetki i reinwestowane
kupony. Administratorem od grudnia 2019 jest GPW Benchmark.

Źródła pierwotne:

- [Administrator: karta TBSP.Index](https://gpwbenchmark.pl/karta-indeksu?isin=PL9999999474).
- [BondSpot: archiwum pojedynczych dni](https://www.bondspot.pl/tbsp_index_archive_en).
- [BondSpot: opis i zmiana administratora](https://www.bondspot.pl/tbsp_index_description_en).
- [BondSpot: Market Data Policy 2026](https://www.bondspot.pl/pub/Polityka_dan_rynk_tekst_jedn_wer._ang.pdf):
  §2(9) dane opóźnione mogą być udostępniane bez opłaty z zastrzeżeniem §6;
  §6(2) dalsza dystrybucja danych opóźnionych, także ze strony, wymaga
  umowy licencyjnej. §5 dotyczy płatnego wykorzystania *Non-Display Data*.

Nie jest jeszcze niezależnie potwierdzone, czy i na jakich warunkach
licencjonowane mogą być **historyczne wartości samego indeksu**, a nie dane
transakcyjne rynku TBSP. **Nie** implementujemy automatycznego masowego
pobierania, redystrybucji ani płatnego źródła. Prywatna lokalna kopia
przedstawiona do analizy nadal musi być pozyskana w sposób uprawniony.

## Zrealizowany kontrakt

`scripts/tbsp_original_archive_intake_v12.py`:

1. Nie posiada kodu sieciowego, API brokerów, dostępu do Neon ani harmonogramu.
2. Przyjmuje tylko oryginalne kopie HTML z konkretnych dat i adresów
   `https://www.bondspot.pl/tbsp_index_archive_en?date=YYYYMMDD&month=MM&year=YYYY`.
3. Odczytuje strukturalnie dokładnie jedną tabelę `Date / Opening value /
   Closing value`, nie myli jej z widżetem najnowszego notowania w sidebarze.
   Odrzuca duplikaty, dodatkowe tabele, zmieniony układ, nierealne i
   niepoprawne wartości, inne hosty i rozbieżne daty.
4. Kontroluje oryginalny SHA-256 każdej strony z manifestem, odrzuca
   dowiązania symboliczne, wyjście poza katalog, przekroczenie limitu pliku,
   przyszłe znaczniki pobrania i źródła niebędące dniem roboczym.
5. Dla 12–60 **ciągłych** miesięcy (jedna próbka do 7 dni przed końcem
   miesiąca) oblicza fikcyjny 100 PLN/mies. odpowiednik jednostek TBSP.Index
   bez faktycznych transakcji. Nawet ostatni bliski końca miesiąca dzień
   **nie oznacza** niezależnie potwierdzonego ostatniego dnia notowania.
6. Zapisuje tylko agregaty i hash stron w `tbsp_reference_v12.json`.
   Nigdy nie publikuje kompletnych surowych szeregów w repozytorium.

Przykładowy lokalny `manifest.json` obok **uprawnionych** oryginałów:

```json
{
  "retrieved_at": "2026-11-22T11:00:00+00:00",
  "files": [
    {
      "file": "original-2025-01-31.html",
      "source_url": "https://www.bondspot.pl/tbsp_index_archive_en?date=20250131&month=01&year=2025",
      "raw_source_sha256": "<SHA-256 prawdziwego oryginału>"
    }
  ]
}
```

To jest **schemat**, nie kompletna lub rzeczywista próbka. Program wymaga
min. 12 oryginałów dla kolejnych miesięcy. Nie wolno wstawiać
przykładowego hasha ani sztucznych notowań do rzeczywistego raportu.

```bash
python3.12 -m unittest tests.test_tbsp_original_archive_intake_v12 -q
python3.12 -m scripts.tbsp_original_archive_intake_v12 \
  --manifest /tmp/tbsp-approved/manifest.json \
  --out-dir /tmp/tbsp-report-v12
```

## EVIDENCE — 23.11.2026

- **PASS:** 8 syntetycznych testów offline (walidacja zawartości oryginałów,
  format, hash, przerwy miesięczne, brak promowania uprawnień/PIT).
- **PASS, jedno oryginalne źródło (pilot):** strona dla **16.11.2026**
  zwróciła otwarcie `2237.34`, zamknięcie `2238.09`; parser wskazał zamknięcie
  z odpowiedniej tabeli, mimo obecności osobnego widżetu dziennego.
  SHA-256 oryginalnego HTML:
  `9b441099108a68d1a2dd92d06427e4726c3fb75ba5f390d42adc2e49f67db8c8`.
- **NOT RUN:** żaden realny 12/48/60-miesięczny benchmark TBSP;
  brak kompletu autoryzowanych oryginalnych kopii. Wynik testowego
  `1200 PLN → 1420 PLN` jest **wyłącznie syntetyczny**, nie rynkowy.
- **BLOCKED:** pełna licencja/prawo hurtowego dostępu, pierwotne vintage i
  weryfikacja rzeczywistych końców miesięcy. Żaden hash nie stanowi
  samodzielnego dowodu autentyczności lub historycznej dostępności.

Moduł nie kwalifikuje serii do M1/M2/M3:
`source_entitlement_verified=false`, `historical_point_in_time_certified=false`,
`actual_last_trading_day_certified=false`,
`m1_m2_m3=INSUFFICIENT_DATA_HOLD_CASH`, 0 operacji i 0 zapisów bazy.
