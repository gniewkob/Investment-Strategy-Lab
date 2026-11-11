# Investment Strategy Lab — I7: weryfikacja katalogu archiwalnego NBP i katalog dowodów źródłowych

**Data weryfikacji dokumentacji: 10.11.2026**  
**Status:** `DRAFT`, wyłącznie badania offline. Żaden rezultat I7 nie stanowi uprawnienia do użycia licencjonowanego zbioru danych, dowodu historycznej godziny publikacji ani sygnału inwestycyjnego.

## 1. Co dokładnie udało się potwierdzić

| Fakt/roszczenie | Źródło pierwotne i dokładna lokalizacja | Co źródło potwierdza | Czego NIE potwierdza |
|---|---|---|---|
| Archiwum NBP | [NBP — Instrukcja pobierania kursów walut](https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/instrukcja-pobierania-kursow-walut/), sekcja archiwalnych plików i `dirYYYY.txt` | Pliki `dirYYYY.txt` zawierają nazwy tabel z lat wcześniejszych; wzorzec `xnnnzrrmmdd` oznacza typ tabeli, trzycyfrowy numer i datę opublikowania/obowiązywania | Że dany plik był dostępny przed konkretną godziną historycznej decyzji, a lokalna kopia katalogu pochodzi z NBP |
| Data NBP API | [NBP Web API](https://api.nbp.pl/), sekcja opisująca tabelę A i `EffectiveDate` | Dzień publikacji `EffectiveDate`; kurs średni `Mid`, historyczne zapytanie do 93 dni | Podpisane `first_published_at` ani brak późniejszych rewizji |
| Obecny harmonogram | [NBP — Terminy publikacji](https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/informacja-o-terminach-publikacji-kursow-walut/) | Obecnie tabela A aktualizowana w dni robocze w godz. 11:45–12:15; archiwum tabel A do godz. 16:00 | Dokładnej godziny publikacji każdej tabeli w historycznym dniu |
| TBSP.Index jako indeks dochodowy | [BondSpot — Regulamin TBSP.Index z 25.11.2019](https://www.bondspot.pl/pub/Regulacje_TBS_Poland/UZ_271-19-Regulamin_Indeksu_Treasury_BondSpot_Poland_obow._25_11_2019.pdf), pkt **3.1–3.3** na str. 4 | Indeks obejmuje zmiany kursów SPW, narosłe odsetki oraz reinwestycję kuponów; opiera się na kursach referencyjnych | Że indeks jest bezpośrednio kupowalny, można odtworzyć stopę zwrotu inwestora po kosztach lub że znamy prawa do pełnej historii; regulamin z 2019 r. nie zastępuje bieżącej metodologii |
| Administrator TBSP | [BondSpot — TBSP.Index](https://www.bondspot.pl/tbsp_index_opis/pub/Regulacje_TBS_Poland/tbsp_index_opis), informacja o administratorze | Od 01.12.2019 odpowiedzialność za opracowywanie TBSP.Index spoczywa na GPW Benchmark S.A. | Że BondSpot jest aktualnym administratorem lub że publiczny odczyt wartości przyznaje licencję na ich systematyczne przetwarzanie |
| MSCI — automatyczne pobieranie i prawa | [MSCI Terms of Use (15.07.2026)](https://www.msci.com/legal/terms-of-use), **§ 2.1 i § 2.4**, oraz [MSCI Notice & Disclaimer](https://www.msci.com/legal/notice-and-disclaimer) | Ograniczenie praw do korzystania; § 2.4 wymienia nieautoryzowane boty, scrapers, AI agents, MCP servers i connectors; zakres licencji/Order Form ma znaczenie | Że użytkownik lub Investment Strategy Lab posiada odpowiednie osobne uprawnienia do konkretnego eksportu i celu użycia |
| Vanguard — zakres użycia i charakter wyceny | [Vanguard Terms and Conditions](https://www.vanguard.co.uk/professional/terms-and-conditions), sekcja **User license**; [ETF FTSE All-World](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits), sekcje `Prices` i `Historical Prices` | Ograniczona licencja strony (użytek osobisty, informacyjny, niekomercyjny lub odrębne upoważnienie); NAV i market price prezentowane osobno | Że NAV jest rzeczywistą historyczną ceną realizacji zlecenia, a pobranie cennika automatycznie zezwala na tworzenie zbioru pochodnego |

**Ważna korekta taksonomii:** `TBSP.Index` jest **dochodowym benchmarkiem obligacyjnym** według pkt 3.1 regulaminu z 2019 r.; równocześnie pozostaje **niekupowalnym bezpośrednio indeksem referencyjnym**. W systemie należy rozróżniać `benchmark_return_semantics=TOTAL_RETURN_METHODOLOGY_DOCUMENTED_2019` od `executable_price_available=false`. Dokumentacja metodologii to jednak nie dowód możliwości licencjonowanego użycia historycznych wartości lub zgodności point-in-time. Nie zmieniamy statusu kwalifikacji źródeł I5 na `QUALIFIED`.

## 2. Co wykonuje I7

Nowy moduł `scripts/nbp_archive_directory_reconcile_v01.py` przyjmuje dwa **wcześniej uzyskane legalnie lokalne pliki**:

- JSON z tabeli A, kodem USD i polami `rates[].no`, `rates[].effectiveDate`, `rates[].mid` — ten sam format, który waliduje I6;
- `dirYYYY.txt` zgodny z oficjalnym formatem nazw `aNNNzYYMMDD` dla tabeli A (w katalogu mogą znajdować się także B/C/H).

Walidator nie pobiera danych. Weryfikuje numer tabeli, datę, rok i ich zgodność między JSON a katalogiem archiwalnym. Sprawdza tylko jeden rok na raz; mieszane okresy wymagają oddzielnych odczytów. Każdą zmianę, brak lub niezgodność numeru zgłasza jako blokadę (bez domyślnego dopasowania innej daty). Wykorzystuje konserwatywną regułę I6: data D nie przechodzi nawet kontroli badawczej przed 00:00 UTC następnego dnia.

**Kluczowe ograniczenie epistemiczne:** dwie lokalne kopie mogą zostać sfałszowane jednocześnie. Ich zgodność i obliczone SHA-256 potwierdzają **spójność dostarczonych metadanych**, nie niezależną autentykację źródeł, prawa, historyczny czas dostępności, niezmienność od daty publikacji ani wykonalny kurs. Dlatego wszystkie wyjścia mają `source_records_independently_authenticated=false`, `historical_first_publication_timestamp_certified=false`, `source_rights_independently_authorized=false`, `qualified_model_series=[]` i `model_state=HOLD_CASH`. Wartości `mid` i indeksów nigdy nie są wypisywane.

**Użycie offline** po niezależnym uzyskaniu plików i sprawdzeniu warunków:

```bash
python -m scripts.nbp_archive_directory_reconcile_v01 \
  --local-nbp-table-a-usd-json /private/authorized/nbp-2026-usd.json \
  --local-dir-year /private/authorized/dir2026.txt \
  --archive-year 2026 \
  --effective-date 2026-10-30 \
  --decision-at-utc 2026-10-31T00:00:00Z
```

Nie dodawać dostawców ani surowych archiwów do repozytorium, logów CI, dokumentacji czy promptów agentów.

## 3. Plan kwalifikacji danych — konkretne braki

| Priorytet | Zakres | Dowód wymagany do dalszych badań | Stan |
|---|---|---|---|
| P0 | Źródło i prawo dostępu | Dopuszczona metoda uzyskania danych, licencja lub pisemne upoważnienie dla **konkretnego zakresu użycia i przechowywania** (szczególnie MSCI/Vanguard/GPW Benchmark) | NIEPOTWIERDZONE |
| P0 | Metodyka i instrument | Identyfikator instrumentu/indeksu; rzeczywista waluta źródła; podstawa `TOTAL_RETURN` vs NAV vs PRICE_ONLY; dla TBSP aktualny regulamin GPW Benchmark | CZĘŚCIOWO OPISANE; NIEZAKWALIFIKOWANE |
| P0 | Historyczny PIT | Niezależny zapis `first_available_at` i wersji źródła na każdy okres; jawna obsługa rewizji; brak korzystania z danych poznanych później | NIEPOTWIERDZONE |
| P1 | Model cen i kosztów | Osobne, uprawnione dane o instrumentach i założenia kosztowe do **symulacji**, bez mylenia indeksu z ceną transakcyjną | NIEPOTWIERDZONE |
| P1 | Odbiór statystyczny | Podział próby, analiza wrażliwości, benchmark i koszt błędów; żadnego twierdzenia o przewadze przy braku danych P0 | OCZEKUJE |

Nie zakładamy, że uzyskanie historycznych wartości w 2026 r. potwierdza, iż były **znane w historycznym momencie podejmowania decyzji**.

## 4. Kryteria odbioru technicznego

`tests/test_nbp_archive_directory_reconcile_v01.py`: 18 testów syntetycznych, bez prawdziwych wartości walut lub treści archiwalnych, m.in. brak daty, niezgodny numer tabeli, duplikaty, pliki innego roku, niepoprawny format, zbyt duży plik, symlink, zbyt wczesna decyzja i brak wycieku `mid`.

Nowe CI sprawdza I7, istniejące I6, I5 i A2: **60 testów na Ubuntu i 60 na macOS**, z wyłączonymi połączeniami Python socket. Odbiór wymaga zielonego wyniku na ostatnim SHA oraz braku zmian w `main`, G1, I5 i I6. Jest to *software gate*, nie prawna zgoda na przetwarzanie danych.

**Wynik projektowy:** `I7_OFFLINE_DIRECTORY_MATCH_ONLY / HISTORICAL_PIT_UNVERIFIED / LICENCE_UNVERIFIED / MODEL_HOLD_CASH`.
