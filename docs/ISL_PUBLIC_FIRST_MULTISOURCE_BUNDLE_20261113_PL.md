# Investment Strategy Lab — public-first v0.5: zintegrowany pakiet 5 serii i giełdowa ścieżka licencji

**Zakres:** issue [#154](https://github.com/gniewkob/Investment-Strategy-Lab/issues/154). **Cel:** jedna iteracja obejmująca rzeczywiste źródła, analizę, audyt jakości, ryzyka prawne, CI i merge — bez dzielenia na osobne PR-y dla każdego dokumentu.

## 1. Rzeczywiste źródła publiczne — cztery zapytania w jednym teście

| Seria | Źródło pierwotne | Dane / jednostka | Status |
|---|---|---|---|
| USD/PLN i EUR/PLN | [NBP Web API, tabela A](https://api.nbp.pl/) | kurs średni PLN/1 waluta, **referencyjny**, nie transakcyjny | Pierwotne API, 1 GET, 2026-09 |
| Złoto NBP | [NBP Web API, ceny złota](https://api.nbp.pl/) | PLN/g, **price-only**, nie całkowita stopa zwrotu | Pierwotne API, 1 GET, 2026-09 |
| Inflacja HICP Polski | [Eurostat prc_hicp_minr](https://ec.europa.eu/eurostat/databrowser/product/view/prc_hicp_minr) | miesięczny indeks I25, 2025=100, 13 miesięcy 2025-09…2026-09 | Pierwotne API, 1 GET, historycznie aktualny stan bazy |
| Rentowność długu PL ~10Y | [Eurostat irt_lt_mcby_m](https://ec.europa.eu/eurostat/databrowser/product/view/irt_lt_mcby_m) | procent rocznie, 59 miesięcy 2021-11…2026-09 | Pierwotne API, 1 GET, **nie zwrot posiadacza obligacji** |

Oficjalna [dokumentacja API NBP](https://api.nbp.pl/) wyjaśnia 93-dniowy limit i ceny referencyjne. [Eurostat ESMS — interest rates](https://ec.europa.eu/eurostat/cache/metadata/en/irt_lt_mcby_esms.htm), §§ 3.4, 4, 14.1, 17 i 18: rentowność obligacji o terminie ok. 10 lat to statystyka procentowa roczna, z możliwymi rewizjami, nie indeks dochodowy. [Eurostat API](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction): domyślny odczyt najnowszej wersji, nie historycznych kolejnych wersji danych. [Ogólna polityka reuse Eurostat](https://ec.europa.eu/eurostat/help/copyright-notice) wymaga atrybucji i uwzględnienia wyjątków; nie jest blankietowym pozwoleniem na wszystkie zastosowania.

## 2. Zintegrowana analiza bez transakcji

Z dwóch pierwotnie zweryfikowanych 2026-09 zestawów danych wyliczamy:

- **HICP 12m wstecz** = (indeks HICP 2026-09 / indeks HICP 2025-09 − 1) × 100%.
- **Poziom rentowności nominalnej PL ~10Y w 2026-09** = bezpośrednia wartość pierwotnej statystyki Eurostat, jednostka % rocznie.
- **Luka poziomu nominalnej rentowności i przeszłej inflacji, w punktach procentowych** = rentowność roczna – trailing HICP 12m. To wyłącznie *statystyka opisowa*. Nie jest rzeczywistą stopą zwrotu, zyskiem, stopą realną ex ante, prognozą inflacji, ani serią benchmarku TR.
- **NBP FX + złoto** to niezależne źródłowe konteksty z września 2026; nie są automatycznie składnikami portfela, a obecność danych nie jest dowodem prawa do inwestowania.

Wynik zawiera oryginalne skróty SHA-256 dla czterech odpowiedzi publicznych (2 NBP + 2 Eurostat), UTC odczytu, zakresy, liczbę obserwacji, liczbę serii, zagregowane statystyki oraz jawne statusy NO-PIT/NO-TR. Brak pełnych 59-miesięcznych szeregów w publicznym logu CI. Sam SHA-256 nie poświadcza samodzielnie historycznej godziny pierwszego wydania.

## 3. Odrębna ścieżka danych giełdowych — źródła istnieją, prawa wymagają przeglądu

| Kandydat | Co istnieje | Czy zautomatyzowano pobieranie? | Powód |
|---|---|---|---|
| **TBSP.Index** | [Archiwum BondSpot](https://www.bondspot.pl/tbsp_index_archiwum), np. [2026-11-02](https://www.bondspot.pl/tbsp_index_archiwum?date=20261102&month=11&year=2026) pokazuje rzeczywistą wartość otwarcia i zamknięcia; indeks jest administrowany przez GPW Benchmark od 2019-12-01 [BondSpot](https://www.bondspot.pl/tbsp_index_opis) | **NIE** | [BondSpot polityka danych rynkowych](https://www.bondspot.pl/1303) odsyła do deklaracji użytkownika, umowy licencyjnej i cennika. Publiczny HTML to nie potwierdzenie praw do hurtowego pobierania/AI/replikacji |
| **GPW indeksy akcji** | [GPW archiwum z eksportem XLS](https://www.gpw.pl/archiwum-notowan), [GPW Benchmark notowania](https://gpwbenchmark.pl/notowania) | **NIE** | Do sprawdzenia dokładny indeks, waluta, wariant cenowy/doch. TR, prawa automatyzacji i oryginalna historia publikacji |
| **Vanguard All-World NAV** | Pierwotny prywatny XLSX i preflight **już sprawdzone** w [#97](https://github.com/gniewkob/Investment-Strategy-Lab/issues/97) | **NIE (w ramach pakietu)** | Nie kopiujemy prywatnego surowego XLSX do publicznego repo. NAV ≠ giełdowy fill ≠ MSCI ACWI TR |
| **Swinkels obligacje międzynarodowe** | Historyczny oryginalny plik naukowy, licencja **CC BY 4.0**, szczegóły [#123](https://github.com/gniewkob/Investment-Strategy-Lab/issues/123) | **NIE (ponowny import niepotrzebny)** | Niebędący długiem polskim zbiór 2020–2022; nie zastąpi TBSP i nie zapewnia aktualnego PIT |

**Decyzja wdrożeniowa:** publiczny podgląd wartości indeksu jest dowodem istnienia kanału, nie praw do automatyzacji. Nie korzystamy z nieautoryzowanych mirrorów ani prób omijania rejestracji, limitów i opłat. W rejestrze status takich źródeł to BLOCKED dla kwalifikacji portfelowej, choć publiczne istnienie danych jest zweryfikowane.

## 4. Odbiór całego pakietu

- Jedna komenda CLI `python -m scripts.public_first_multisource_macro_evidence_v05 --allow-public-official-fetch` uruchamia **4 oficjalne GET**, bez sekretów, bez zapisów.
- Testy syntetyczne, network-disabled na Ubuntu + macOS, walidują źródła, zakresy, daty, SHA, prawa, 0 operacji.
- Jeden test oryginalnych, realnych źródeł w GitHub Actions + pełna regresja, GitGuardian i CodeQL.
- Nie wolno zamknąć [#116](https://github.com/gniewkob/Investment-Strategy-Lab/issues/116) na podstawie tego pakietu: `PL_BONDS_TR_PLN`, `GLOBAL_EQUITY_TR_PLN` i `GOLD_TR_PLN` nadal `BLOCKED`, a M1–M3 `INSUFFICIENT_DATA_HOLD_CASH`.

**Zasada:** następne iteracje idą w szerokich, przekrojowych pakietach (źródła + kod + dane + wyniki + odbiór), a nie w poszukiwaniu pojedynczej strony.
