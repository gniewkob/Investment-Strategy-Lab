# TBSP.Index — pięcioletnia rzeczywista historia indeksu obligacji

**Data akwizycji:** 6 listopada 2026 (UTC)
**Środowisko:** prywatne laboratorium badawcze; brak produkcji
**Werdykt akwizycji:** PASS dla miesięcznych oficjalnych wartości
**Werdykt inwestycyjny:** NOT_RUN — to indeks benchmarkowy, a nie zlecenie

## Wykonane kroki i niepodważalne dowody

- Oficjalne źródło: [BondSpot — archiwum TBSP.Index](https://www.bondspot.pl/tbsp_index_archiwum)
- Administrator indeksu od 1 grudnia 2019:
  [GPW Benchmark, informacja BondSpot](https://www.bondspot.pl/tbsp_index_opis)
- Oficjalna charakterystyka: indeks total return uwzględniający
  ceny obligacji skarbowych, naliczone odsetki i reinwestowane
  kupony: [opis BondSpot](https://www.bondspot.pl/news?ph_main_content_1_cmn_id=1309&ph_main_content_1_start=show)
- Kod kolektora: \`scripts/tbsp_official_archive_v04.py\`.
- Niezależny scalacz i walidator:
  \`scripts/tbsp_archive_merge_v04.py\`.
- GitHub Actions:
  [run #42230900987](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42230900987).
- 5 odrębnych segmentów po 12 miesięcy: 5/5 SUCCESS.
- Każdy miesiąc pobrano z oficjalnego kalendarza dat i
  **ostatniego dnia z rzeczywiście opublikowaną wartością
  zamknięcia**, a nie z imputacji wartości na koniec miesiąca.
- Wynik: **60 miesięcy od XI 2021 do X 2026, bez luk kalendarza**.
- W każdej obserwacji zapisano oficjalny URL datowanego notowania
  oraz kalendarza, SHA-256 bajtów obu pobranych stron i UTC
  rzeczywistego pobrania.
- Niezależne połączenie pięciu segmentów sprawdza SHA każdego,
  ciągłość dat, poprawną bazę PLN, brak sprzeczności notowania
  z datą źródłowej strony oraz brak uprawnień transakcyjnych.
- 11/11 testów offline parsera na każdym segmencie PASS.
- Scalony artefakt GitHub Actions:
  \`tbsp-60months-verified-reference\`, ID \`13508911315\`,
  oryginalny JSON \`tbsp-5y-nonexecuting-research-evidence.json\`.
  Czas przechowywania w GH: do 20.11.2026 (14 dni).
- SHA-256 kanonicznego JSON z kompletem poświadczeń źródła:
  \`10ad19b119245ed4b07c27ce34daee50970e059476e087b0a9ae20ba66d3f8f5\`.
- Pobrany ZIP i JSON zostały odczytane niezależnie od CI:
  60/60 unikalnych miesięcy, rzeczywista zgodność SHA-256
  z deklarowanym fingerprintem i brak sztucznych wpisów.

## Konkretne obserwacje

| Miesiąc | Faktyczna data notowania | TBSP.Index — wartość zamknięcia |
|---|---|---:|
| XI 2021 | 2021-11-29 | 1872,28 |
| X 2026 | 2026-10-30 | 2230,71 |

Poziom indeksu w tym przedziale wzrósł o **19,144%**.
To zmiana wartości indeksu dochodowego benchmarku; NIE jest
stopą zwrotu możliwą do zagwarantowania z zakupu obligacji lub
funduszu w wybranym rachunku, ani wynikiem wpłat 100 PLN/miesięcznie.

Ważny przypadek źródłowy: **2021-11-30** figuruje w kalendarzu
jako możliwa data, ale datowana strona nie zawierała poprawnej
opublikowanej wartości zamknięcia. Kolektor sprawdził tę stronę,
zachował jej URL oraz SHA-256 i wybrał ostatni wcześniejszy
dzień z rzeczywistym kursem: **2021-11-29**.
To nie jest interpolacja ani uzupełnienie syntetyczne.

## Klasyfikacja i granice

- \`series_id=BONDSPOT_TBSP_CLOSE_PLN\`
- \`currency=PLN\`
- \`basis=BOND_TOTAL_RETURN_BENCHMARK_INDEX\`
- \`instrument_kind=NON_TRADABLE_INDEX\`
- \`historical_pit_certified=false\`
- \`trading_price_proven=false\`
- \`backtest=NOT_RUN_SOURCE_ONLY\`
- \`paper_events_created=0\`, \`financial_operations=0\`

Kluczowe: pobranie **w 2026 r.** potwierdza dzisiejszą historię
publikowaną przez źródło, ale nie dowodzi dokładnej historycznej
godziny pierwszej publikacji ani braku rewizji. Nie ma też dowodu,
że indeks był instrumentem dostępnym do zakupu po jego wartości.

Z tego powodu nawet tak dobra seria historyczna nie może
automatycznie włączyć rzeczywistego paper-fill engine. Zanim
zostanie zaakceptowana jako badawczy \`PL_BONDS_TR_PLN\`,
trzeba jawnie zdefiniować algorytm mapowania i zapisać status
dostępności historycznej. Nie wolno traktować tego jak
ceny obligacji, ETF-u lub kontraktu.

## Status innych serii

- NBP USD/PLN, EUR/PLN i złoto PLN/g: wcześniej pobrane
  i zweryfikowane po 60 miesięcy; klasyfikacja FX_RATE/PRICE_ONLY.
- Vanguard FTSE All-World Accumulating, ISIN IE00BK5BQT80:
  oficjalna strona pokazuje historyczne NAV w USD, ale
  pełnego 60-miesięcznego eksportu nie zweryfikowano na tym etapie.
- \`GLOBAL_EQUITY_TR_PLN\` i \`GOLD_TR_PLN\` nadal nie mają
  kompletnej, wiarygodnej historii według kontraktu Backtest v0.4.
- Główne prywatne Neon nie zostało zmodyfikowane.
  Żadnych nowych transakcji, wpłat ani wirtualnych pozycji.

## Następny odbiór

(1) Zweryfikować oryginalny plik NAV Vanguard i faktyczną
dostępność dat, (2) rozdzielić NAV USD, datowany kurs NBP FX
i historyczną wartość PLN, (3) ustalić badawczą metodologię
ekspozycji na złoto oraz ceny rzeczywistego instrumentu,
(4) dopiero wtedy uruchomić **warunkową symulację** M1/M2/M3
na kompletnych inputach bez wymyślania kosztów lub filli.
