# Investment Strategy Lab — v0.7: przekrojowa jakość danych, obrót obligacjami i kontekst makro

**Zakres większego pakietu:** [issue #158](https://github.com/gniewkob/Investment-Strategy-Lab/issues/158), [PR #159](https://github.com/gniewkob/Investment-Strategy-Lab/pull/159). Realny cel to rozwinięcie gotowej infrastruktury NBP, Eurostat i UKNF o 202-miesięczną historię obrotu obligacjami z MF, audyt jakości i wspólny model pochodzenia źródeł. Nie jest to wdrożenie realnego handlu.

## Fakty i źródła pierwotne

| Kontrolowana teza | Źródło i zakres potwierdzenia | Status |
|---|---|---|
| Oficjalny rynek wtórny obligacji, segment międzybankowy, Treasury BondSpot Poland i GPW | [Ministerstwo Finansów: Statystyka rynku wtórnego](https://www.gov.pl/web/finanse/statystyka-rynku-wtornego); okres archiwum XII 2009–IX 2026 w aktualnym wydaniu | Publiczny opis i plik XLSX; nie indeks total-return |
| We wrześniu 2026 r. łączne obroty wyniosły 3 140 385,25 mln PLN: międzybankowy 2 782 687,61; BondSpot 357 071,50; GPW 626,14 | Ta sama [oficjalna strona MF](https://www.gov.pl/web/finanse/statystyka-rynku-wtornego), aktualizacja 30.10.2026 | Konkretna publikacja okresowa; nie własna wycena inwestora |
| MF podaje +16,8% m/m w IX 2026 r. | Ta sama strona, akapit wprowadzający | Tolerancja testu zaokrąglenia ±0,15 pp, nie reguła dla innych okresów |
| Dane KDPW według daty rozliczenia, GPW według daty zawarcia transakcji | Ta sama strona MF, nota pod tabelą | Odrębne zegary zdarzeń; nie interpretować jak synchronicznych transakcji |
| Poprzedni odczyt oryginalnego arkusza MF: jeden arkusz XLSX, 56 050 bajtów, bez makr i zewnętrznych połączeń | [GitHub Actions #43336334638](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/43336334638), SHA-256 5fd7f4fceb1403f1978553079e3a566a70e04d849af29c6a9c7ee41a7d5f42c8 | Zweryfikowana struktura pliku, **nie** jeszcze potwierdzenie wszystkich 202 rekordów |
| UKNF 22 dzienne wyceny jednej podstawowej jednostki PLN za IX 2026, zmiana poziomu NAV -0,4082% | [Rzeczywiste CI #43338359290](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/43338359290), źródło [UKNF API](https://wybieramfundusze-api.knf.gov.pl/documentation.html) | NAV **nie** jest automatycznie total-return; KID dla tej klasy nie znaleziono |
| NBP/Eurostat: 22 dzienne dni publikacji NBP, 13 miesięcy HICP i 59 miesięcy PL 10Y rentowności | [Wspólny realny odczyt v0.5 #43331152053](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/43331152053); [Eurostat konwergencja ESMS](https://ec.europa.eu/eurostat/cache/metadata/en/irt_lt_mcby_esms.htm) §§3.4/4/14.1/17/18 | Referencyjne kursy i ceny, inflacja, **poziom rentowności**; nie indeks dochodowy |

### Podstawa prawna i ograniczenia

[Regulamin UKNF Wybieram Fundusze API](https://wybieramfundusze-api.knf.gov.pl/terms.pdf) §3 ust. 2–5 dopuszcza bezpłatny dostęp i implementację API, wymaga respektowania zakazu przeciążania oraz atrybucji. Nie stanowi przyzwolenia na hurtowe przejmowanie licencjonowanych indeksów GPW/BondSpot. Tekstowe treści gov.pl stosują [warunki portalu](https://www.gov.pl/web/gov/warunki-korzystania), natomiast prawa do poszczególnych arkuszy i źródłowych statystyk należy oceniać zgodnie z ich udostępnieniem. Publiczna możliwość pobrania archiwum nie poświadcza oryginalnych wersji punkt-w-czasie od 2009 r.

## Implementacja i kontrola jakości (jeden pakiet)

**Źródło MF:** skrypt `scripts/mf_bond_market_history_v07.py` otwiera ograniczone rozmiarem archiwum ZIP oryginalnego XLSX, czyta XML przy użyciu biblioteki standardowej, nie wykonuje formuł, VBA, makr ani linków zewnętrznych i udostępnia ograniczony podgląd schematu. Skrypt `scripts/mf_bond_turnover_metrics_v07.py` czyta unikalne miesiące i kanały obrotu w mln PLN, kontroluje nieujemność, sumę kanałów, 202 kolejnych miesięcy XII 2009–IX 2026, wartości IX 2026 zgodne z tekstem MF oraz poziom zmiany m/m zgodny z publikacją po zaokrągleniu. Wyjście to SHA-256, agregaty, pokrycie i metadane — nie cały surowy arkusz w CI.

**Wspólne rozgraniczenie danych:** `scripts/public_first_market_quality_v07.py` łączy trzy **już zweryfikowane** typy odczytów: (1) miesięczny obrót MF, (2) dzienny NAV jednej kategorii funduszu UKNF, (3) dzienne NBP/miesięczne Eurostat z v0.5. Kontroluje zgodność okresu IX 2026, jednostek, fingerprintów źródeł, brak historycznego PIT i brak nieuprawnionego podpięcia KID obcego funduszu. **Zbieżny miesiąc raportowania nie oznacza wspólnej chwili pobrania, jednej częstotliwości, ani podstawy do korelacji/wnioskowania przyczynowego**.

**Rozdzielone miary:** mln PLN obrotu miesięcznego; procentowa zmiana poziomu NAV (bez dystrybucji i opłat); HICP 12m wstecz; rentowność obligacji ~10Y procent p.a. Ich mechaniczne zestawienie nie wylicza stopu zwrotu portfela, kosztu kapitału, rentowności ex ante ani sygnału kupna/sprzedaży.

**Testy:** 24 syntetyczne testy offline na Ubuntu/macOS (ZIP bez makr, brak przyszłych/missing/duplikowanych miesięcy i wartości, poprawność jednostek, matematyka, pochodzenie i zakaz operacji finansowych), plus pełna istniejąca regresja, CodeQL i GitGuardian. Realne źródło MF jest pobierane co najwyżej jeden raz na jednorazowy workflow; przed uznaniem ukończenia wymagany jest PASS jego rzeczywistego parsera, a nie wyłącznie syntezy.

## Stan wykonania i kryterium odbioru

Pierwsza próba uruchomienia nowego PR #159 w GitHub Actions [run #43392165899](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/43392165899) zakończyła się **FAIL przed uruchomieniem kroków**, podobnie istniejące workflow G1 i stack. W logach Jobs brak wykonanych kroków, próba ponowienia pojedynczego joba też zakończyła się przed jego startem. Jest to **nierozstrzygnięty problem uruchamiania GitHub Actions**, nie uzyskano z tej próby danych o poprawności parsera i nie należy na tej podstawie uznać źródła za zweryfikowane. Status PR pozostaje DRAFT do chwili realnego uruchomienia i przejścia testów.

Warunkiem DONE jest 24/24 testów offline, poprawny realny odczyt XLSX i 202 miesięcy, pełne CI + CodeQL i GitGuardian na końcowym SHA, review, merge i regresja na `main`. Jeśli źródło ma układ macierzowy/transponowany, parser ma zgłosić `MF_TABLE_HEADER_UNSUPPORTED`, nie zgadywać kolumn ani publikować błędnych danych. Niezależne issue #116 dotyczące licencji GPW/BondSpot i oryginalnych PIT pozostaje **OPEN**. M1–M3 nadal `HOLD_CASH`, żadnych zleceń, realnego inwestowania, kont, baz danych, harmonogramów ani transferów.

## 5. Dodatkowy defekt jakości NAV wyeliminowany w ramach v0.7

W istniejącym module UKNF v0.6 potwierdzano zgodność daty ostatniej wyceny z podglądem kategorii jednostki, ale nie porównywano bezpośrednio wartości NAV. Po poprawce moduł odrzuca zestawienie, gdy **wycena z podglądu różni się od ostatniego punktu historii dla tej samej daty i klasy** (`HISTORY_PREVIEW_VALUATION_CONFLICT`). Uniemożliwia to niejawne połączenie danych z dwóch wersji tego samego punktu bez rozpoznania rewizji. Test regresyjny używa celowo różniących się wartości. To zabezpieczenie analityczne, **nie** dowód historycznej dostępności oryginalnych wycen.

Dodatkowo kontroler arkusza MF odrzuca niedozwolone elementy binarne ZIP **niezależnie od wielkości liter rozszerzenia** (`.bin`, `.BIN`); dopuszczane pozostają tylko dane ustawień drukarki `xl/printerSettings/`. Nie są wykonywane makra, funkcje Excela ani zewnętrzne łącza.

**Wniosek o statusie:** implementacja v0.7 i zestawy testów są przygotowane na gałęzi PR #159, lecz do czasu realnego startu Actions i otrzymania wyników nie oznaczamy ich jako przetestowanych, zaś historyczne 202 miesiące MF pozostają **SOURCE_LAYOUT_UNVERIFIED**. Nie ma akceptacji do scalania na `main`.

## 6. Lokalny odbiór niezależny od GitHub Actions

Na gałęzi PR #159 dodano bezsieciowy kontroler `scripts/isl_v07_offline_acceptance.py`. Po zaktualizowaniu checkoutu można uruchomić:

```bash
python3 -m scripts.isl_v07_offline_acceptance
```

Po konsolidacji z #161 sprawdza składnię dziewięciu modułów i wykonuje **100 testów syntetycznych offline**, w tym zgodność SHA-256 źródeł, odrzucanie przyszłych obserwacji i powtarzalność raportów JSON/Markdown. Wynik `ISL_V07_OFFLINE_ACCEPTANCE` zawiera status, liczby testów i jawne `network=DENIED`. Jest to **alternatywna weryfikacja kodu**, ale **nie zastępuje** odczytu rzeczywistego oryginalnego skoroszytu MF i nie może samoistnie kwalifikować go do wykorzystania.

GitHub Actions nadal kończy wszystkie hostowane joby przed wykonaniem pierwszego kroku (także niezmienione workflow), więc bez poprawy infrastruktury albo lokalnego dowodu odbioru kod pozostaje **NIE DONE**.

## 7. Konsolidacja MF / UKNF / NBP / Eurostat

Do #159 przeniesiono z [#161](https://github.com/gniewkob/Investment-Strategy-Lab/pull/161) trzy uzupełniające moduły i ich testy: `mf_original_turnover_schema_v07.py` (metadane XLSX, nie zweryfikowany obrót), `knf_one_class_nav_quality_v07.py` (poziomy NAV jednej klasy, nie stopa zwrotu) i `research_readiness_quality_v07.py` (przekrojowy stan gotowości).

Nowy `scripts/public_first_market_research_v07.py` generuje spójne raporty JSON/Markdown z dostarczonych lokalnie pokwitowań:

- `SCHEMA_ONLY`: tylko jakość danych i ograniczenia źródeł; brak agregatów rynku.
- `DESCRIPTIVE_MARKET_CONTEXT`: wymaga również zweryfikowanych metryk MF, oryginalnego UKNF NAV i makro; porównuje SHA-256 *tego samego* XLSX w dwóch odczytach MF i *tej samej* historii UKNF w dwóch odczytach NAV; blokuje przyszłe czasy obserwacji i mieszanie niepełnego zestawu.

**Naprawa regresji #159:** początkowy odbiór offline miał 8/57 niepowodzeń przez wymuszony warunek `nbp_observed_business_days == 22`. Referencja syntetyczna v0.5 zawiera 1 dzień. Walidacja dopuszcza wyłącznie całkowitą liczbę dni z zakresu 1–22 i osobno ujawnia flagę `macro_nbp_full_22_day_coverage`; nie dopisuje ani nie interpoluje obserwacji.

```bash
python3 -m scripts.isl_v07_offline_acceptance
python3 -m scripts.public_first_market_research_v07 \
  --input local-receipts.json \
  --out-dir local-reports \
  --observed-at-utc 2026-11-14T00:00:00+00:00
```

Reporter nie pobiera danych z sieci ani nie dotyka kont czy bazy. SHA-256 jest kontrolą spójności, **nie dowodem autentyczności ani historycznej dostępności źródła**. Zestaw testów: **100/100 PASS lokalnie na syntetycznych danych**. Osobny odczyt rzeczywistego XLSX MF i jego 202 miesięcy przeszedł po naprawie parsera (sekcja 8); hostowane CI na dokładnym SHA nadal pozostaje zablokowane. Dla M1–M3 utrzymujemy `INSUFFICIENT_DATA_HOLD_CASH`, bez żadnych realnych operacji finansowych.

## 8. Dwa błędy parsera ujawnione na oryginalnym XLSX (2026-11-22)

Właściciel odtworzył błąd `MF_DUPLICATE_OR_WIDE_CELL` na pliku MF. Niezależnie pobrano **dokładnie ten sam publiczny XLSX** z oficjalnego `gov.pl`: HTTP 200, 56 050 bajtów, SHA-256 `5fd7f4fceb1403f1978553079e3a566a70e04d849af29c6a9c7ee41a7d5f42c8`. Pozwoliło to odtworzyć błąd bez danych syntetycznych.

1. Wiersze 114 i 144 mają łącznie **8168 komórek wyłącznie z formatowaniem**, od kolumny AW do XFA (bez wartości, formuł i tekstu). Czytnik pomija tylko komórki o pustej strukturze XML z atrybutem stylu w dozwolonym zakresie Excela, z górnym limitem 10 000; **nie** pomija niepustych odległych kolumn ani duplikatów adresów.
2. Oficjalny nagłówek w wierszu 2 zawiera **dwa pola `Razem`**: `E` zamyka tabelę obrotów A–E, `J` zamyka odrębne zestawienie F–J. Dopasowanie semantyczne wybiera teraz wyłącznie jednoznaczny, sąsiadujący układ kolumn daty i trzech kanałów obrotu; nie używa `J` jako sumy rynku.

**PASS realnego źródła:** pełne 202 miesiące XII 2009–IX 2026, oficjalna suma września `3140385.25` mln PLN oraz dotychczasowe kontrole kanałów i dynamiki. Dodatkowe sześć regresji syntetycznych obejmuje dopuszczalne wyłącznie puste formatowanie, odrzucenie formuł i liczb w odległych kolumnach, duplikaty oraz dwa warianty dodatkowego pola `Razem`. **Nie** potwierdza to archiwalnych chwil pierwszej publikacji, praw licencyjnych ani pełnych stóp zwrotu portfela.
