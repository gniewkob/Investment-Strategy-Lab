# ISL v0.3 — OECD share-price Poland: odrębne źródło FRED i opisowy benchmark

## Zakres i poziom dowodów

To **polski miesięczny indeks cen akcji**, **nie** akcje globalne, ETF, NAV, stopa total-return ani cena transakcyjna w PLN. OECD definiuje indeks cen jako odrębny od indeksu dochodowego, a obserwacje miesięczne określa jako *zazwyczaj* średnie dziennych zamknięć. Specyficzna agregacja POL nie została niezależnie potwierdzona.

- Seria wtórna: FRED [`SPASTT01PLM661N`](https://fred.stlouisfed.org/data/SPASTT01PLM661N), źródło wskazane przez FRED: OECD; not seasonally adjusted, frequency monthly, unit `Index 2015=100`, `POL/SHARE/IX`.
- Oryginał OECD: `OECD.SDD.STES:DSD_STES@DF_FINMARK(4.0)/POL.M.SHARE.IX`; badana wcześniej odpowiedź 12 619 bajtów, SHA-256 `d7ece9e69cff2af2709ffb5220e2521c7eb75ac12a636bcf6a87e6a04e607a5b`. **W tej iteracji nie uzyskano oryginalnych bajtów OECD.** Zbieżność identyfikatorów nie zastępuje porównania 48 wartości.
- FRED publikuje tabelę z 48 rzeczywistymi miesiącami 2022-01–2025-12; źródło wtórne jest oznaczone przez FRED jako zaktualizowane **15 czerwca 2026**. To bieżący retrospektywny widok, nie potwierdzony PIT z lat 2022–2025.

## Wykonany test z rzeczywistych obserwacji źródła wtórnego

Jednorazowo odczytano 48 poziomów indeksu widocznych na stronie FRED i przygotowano **lokalną transkrypcję tekstu wyświetlonej tabeli**, nie oryginalną odpowiedź HTTP. Transkrypcja pozostała poza repozytorium. Weryfikacja jej 48 ciągłych miesięcy i obliczenie przez `scripts.fred_pol_oecd_research_v03` zakończyły się powodzeniem:

| Element | Wynik |
|---|---:|
| Zakres | 2022-01–2025-12, 48 miesięcy |
| Fikcyjne wpłaty | 48 × 100 = **4 800,00 PLN** |
| Równoważnik jednostek indeksu na koniec 2025 | **7 512,33 PLN** |
| Zmiana poziomu indeksu między pierwszym i ostatnim miesiącem | **+62,59%** |
| SHA-256 **lokalnej transkrypcji**, nie oryginalnego FRED/HTTP | `af5cd39412bdd2753f9ae77d604a35b912ef1c0f11798fd2aaa98a56a27085bd` |

**NIE JEST TO wynik strategii inwestycyjnej.** Arytmetyka zakłada nabywanie ułamkowych, nieistniejących jednostek indeksu po miesięcznej średniej i porównuje ich poziom z końcową średnią. Nie ma możliwości dokonania transakcji po poziomie takiego indeksu; pominięto dywidendy, prowizje, spready, podatki i dokładne chwile publikacji. Liczby dotyczą wyłącznie tego utrwalonego widoku FRED, nie niezależnie zweryfikowanych oryginalnych 48 bajtowych obserwacji OECD. **Żadna strategia M1/M2/M3 nie została dopuszczona ani zmieniona.**

## Walidacja i integracja

`scripts/fred_pol_oecd_research_v03.py` jest całkowicie offline, bez bibliotek dodatkowych, HTTP, baz danych lub zleceń. Przyjmuje lokalny tekst tabeli FRED z wyraźnymi nagłówkami metadanych i dokładnym SHA-256 dostarczonego tekstu. Weryfikuje serię, typ `SHARE`, bazę 2015, 48 miesięcy bez powtórzeń/luk, dodatnie skończone poziomy i rzeczywisty znacznik czasu UTC. Odrzuca symlinki, duże pliki i nadpisanie wyników. Wygenerowane lokalne JSON + Markdown można dołączyć do istniejącego raportu laboratorium za pomocą `--base-report`; oryginalny raport pozostaje niezmieniony. Brak surowych wartości źródłowych w wynikach.

Opcjonalne parametry `--oecd-csv`, `--oecd-sha256`, `--oecd-retrieved-at-utc` umożliwiają kontrolę oryginalnego pliku OECD przez już istniejący `scripts.oecd_pol_benchmark.parse_csv` i **porównanie wszystkich 48 poziomów z FRED** przy jawnej tolerancji 0,000001 jednostki indeksu. Rozbieżność przerywa wywołanie. **Tej ścieżki nie uruchomiono na realnym pliku OECD** w tej iteracji, więc porównanie pierwotnego i wtórnego źródła jest `NOT_PERFORMED`.

```bash
python3 -m scripts.fred_pol_oecd_research_v03 \
  --fred-table-text /PRIVATE/fred-table-text.txt \
  --text-sha256 '<SHA-256 właściwego lokalnego tekstu>' \
  --retrieved-at-utc 'YYYY-MM-DDTHH:MM:SSZ' \
  --base-report /PRIVATE/isl-research-report.md \
  --out-dir /PRIVATE/isl-fred-research-v03
```

Nie używaj przykładowego znacznika czasu jako rzeczywistego. FRED udostępnia tabelę przez interfejs, ale przepisywanie tekstu nie certyfikuje oryginalnych bajtów; w przyszłości należy zastąpić je autoryzowanym, archiwizowanym źródłem.

## Prawa: ocena i ograniczenia

- OECD [Terms & Conditions §3 Data](https://www.oecd.org/en/about/terms-conditions.html) dopuszczają z atrybucją ekstrakcję i przetwarzanie danych, **o ile** nie obowiązują odrębne warunki i prawa osób trzecich; wprost nakazują sprawdzić źródło/własność danych w metadanych oraz uzyskać wymagane zgody. Nie mamy potwierdzenia właściciela i praw tej konkretnej serii POL.
- FRED [Terms of Use](https://fred.stlouisfed.org/legal/terms/) wskazują, że jego dostęp nie znosi praw właścicieli serii i wymagają zgody na wykorzystanie danych osób trzecich ponad własny użytek osobisty; licencja podstawowa jest ograniczona do korzystania osobistego, niekomercyjnego. Dlatego brak hurtowego pobierania i redystrybucji źródłowych poziomów w publicznym repozytorium.
- OECD [Share prices](https://www.oecd.org/en/data/indicators/share-prices.html) — metodologia ogólna, nie dowód konkretnej metody agregacji POL.

**Zakres dopuszczenia:** naukowe obliczenie offline na lokalnej transkrypcji oraz publikacja kodu, testów na fikcyjnych danych i agregatów opisowych z jasną atrybucją. **Bez deklarowania** licencji na dalszą dystrybucję danych albo gotowości do automatycznej integracji.

## EVIDENCE

- Nowy moduł: **8/8 testów syntetycznych offline PASS** i `py_compile PASS` (ścisły parser, testy błędów, porównanie poziomów, CLI, opcjonalny raport).
- Jeden odczyt tekstowy 48 poziomów z publicznej tabeli FRED i realny lokalny przebieg CLI: **PASS na transkrypcji**, nie na oryginalnym HTML/CSV i bez certyfikowania praw.
- Niewykonane: oryginalny CSV OECD, pełna regresja całego repozytorium na końcowym SHA, wymagane hosted CI, pierwsza historyczna publikacja PIT, wdrożenie, merge, integracja bazodanowa lub jakiekolwiek zlecenia/transakcje.
