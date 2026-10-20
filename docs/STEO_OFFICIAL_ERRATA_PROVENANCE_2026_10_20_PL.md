# EIA STEO — oficjalne erraty i stan dowodów historycznej dostępności (20.10.2026)

## Rozdzielenie trzech kategorii dowodów

1. **Oficjalna data wydania** (`Release Date`) z archiwalnego indeksu STEO potwierdza deklarowaną datę wydania *publikacji*. Nie dowodzi, że XLSX aktualnie dostępny pod adresem starego raportu miał **te same bajty** w chwili pierwotnej publikacji.
2. **Oficjalny komunikat o poprawce / repost** potwierdza konkretne zdarzenie lub problem ujawniony przez EIA. **Nie dowodzi automatycznie rewizji `2tab`**, WTI `WTIPUUS` ani Brent `BREPUUS`, zwłaszcza gdy dotyczy innych tabel, tekstu, wyłącznie PDF lub dodatku Winter Fuels Outlook.
3. **Niezależny historyczny snapshot bajtów źródłowego XLSX**, z niezależnym znacznikiem czasu i wiarygodnym hash/dokumentem z epoki, byłby silniejszą podstawą weryfikacji `as-published` vintage. Takiego potwierdzonego snapshotu **NIE pozyskano ani nie zweryfikowano w tym etapie**. Próba otwarcia publicznego indeksu Wayback/CDX z tego środowiska nie zakończyła się udanym odczytem; nie oznacza to, że archiwum nie posiada kopii. **Nie przypisujemy mu statusu PASS.**

**Wynik dotyczący obecnych badań:** 34+24 = **58 datowanych historycznych wydań STEO** (2022–październik 2026) już odczytano w badaniach, przy czym osiem plików Jan–Aug2024 użyto ponownie jako późniejsze referencje i porównano ich oryginalne SHA. 172 + 144 = **316 par prognoz i późniejszych referencji** — to nie 316 niezależnych informacji, ponieważ okresy docelowe/horyzonty mogą się nakładać. Żadnej z tych par **nie przeklasyfikowano** na niezależnie `PIT_CERTIFIED`.

## Odkryte oficjalne komunikaty EIA

Poniższy zestaw obejmuje **9 ręcznie sprawdzonych komunikatów** przypisanych do wydań z lat 2022–2025. Rejestr nie jest automatycznym ani wyczerpującym wykazem wszystkich errat EIA.

| Wydanie | Data komunikatu | Charakter i źródłowy zakres | Wniosek dla WTI/Brent Table 2 |
|---|---|---|---|
| `oct22` | 26.10.2022 | Korekta tabeli wydatków na ogrzewanie w **dodatku Winter Fuels Outlook**, nie pierwotnej tabeli 2 STEO. <https://www.eia.gov/outlooks/steo/archives/notice_data_10_26_2022.php> | Nie wykazano rewizji |
| `feb23` | 08.02.2023 | Ponowne wydanie STEO po poprawie **tekstu o produkcji gazu**. <https://www.eia.gov/outlooks/steo/archives/notice_data_02_08_2023.php> | Nie wykazano rewizji |
| `may23` | 09.05.2023 | Ponowne wydanie raportu po poprawce **porównania temperatur w tekście**. <https://www.eia.gov/outlooks/steo/archives/notice_data_05_09_2023.php> | Nie wykazano rewizji |
| `nov23` | 09.11.2023 | Raport pierwotnie wydany 07.11.2023 opublikowany ponownie 09.11 po korekcie **historycznego zużycia produktów naftowych** w tabelach 4a, 3a i 3d. <https://www.eia.gov/outlooks/steo/archives/notice_data_11_09_2023.php> | Zakres wskazanych tabel nie obejmuje Table 2 |
| `jun24` | 27.06.2024 | Ponowne wydanie czerwca STEO po korekcie **tabeli 10b, produkcja gazu łupkowego**. <https://www.eia.gov/outlooks/steo/archives/notice_data_06_27_2024.php> | Zakres innej tabeli |
| `nov24` | 14.11.2024 | Ponowne wydanie listopadowego STEO z poprawkami **tabeli 10b, wydobycie ropy z tight oil i gazu łupkowego**. <https://www.eia.gov/outlooks/steo/archives/notice_data_11_14_2024.php> | Zakres innej tabeli |
| `jan25` | 15.01.2025 | EIA informuje o poprawkach w **tabeli 3e, PKB i indeks USD**; komunikat wspomina błędne dane z listopadowego STEO, a równocześnie mówi o ponownym wydaniu **styczniowego STEO 15.01**. <https://www.eia.gov/outlooks/steo/archives/notice_data_01_15_2025.php> | Zakres tabeli 3e; atrybucję treści między Nov/Jan trzeba rozróżnić przy modelach wieloczynnikowych |
| `feb25` | 12.02.2025 | EIA mówi o ponownym wydaniu **PDF** z powodu **tabeli 3a**; nie stwierdza, że XLSX został zastąpiony. <https://www.eia.gov/outlooks/steo/archives/notice_data_02_12_2025.php> | Brak dowodu zmiany XLSX `2tab` |
| `dec25` | 18.12.2025 | Błąd **przypisania regionalnego historycznej produkcji ropy**; korekta zapowiedziana w wydaniu styczniowym 2026, nie udokumentowano ponownego wydania grudniowego pliku. <https://www.eia.gov/outlooks/steo/archives/notice_data_12_18_2025.php> | Zakres innej tabeli |

Brak komunikatu w naszym **ręcznie kuratorowanym** rejestrze **nie jest** dowodem braku dowolnej innej rewizji. Status `xlsx_reposted_proven=false` oznacza wyłącznie, że *w treści tego komunikatu nie wykazano wyraźnie ponownej publikacji arkusza XLSX*, nawet jeśli cały „raport” został ponownie opublikowany. Nie jest to negacja możliwości wymiany XLSX.

## Wdrożona kontrola w kodzie

`scripts/steo_official_notice_audit.py`:

- offline lista znanych i czytanych oficjalnych komunikatów EIA, każdy z precyzyjnym `issue`, `notice_date`, URL i zakresem tabel;
- jawne rozróżnienie: **repost całego raportu**, **poprawka treści**, **tylko PDF**, **suplement Winter Fuels**, **błąd naprawiany dopiero w kolejnym wydaniu**;
- fail-closed dla daty komunikatu wcześniejszej od oficjalnego wydania, nieznanego kodu, duplikatu, URL poza domeną EIA lub niespójnych stwierdzeń;
- `edition_status(issue)`: czy wymaga indywidualnego przeglądu, ale zawsze `historical_point_in_time_certified=false`;
- `audit_steo_notices()`: zwięzły inwentarz 58 starych miesięcznych wydawnictw, 9 sprawdzonych komunikatów; **0 requestów HTTPS, 0 połączeń/zapisów do bazy, 0 zleceń i zmian alokacji**.

Przykład wykonania z repo:

```bash
python3 -m scripts.steo_official_notice_audit --issue nov23
python3 -m scripts.steo_official_notice_audit
```

**Oczekiwane:** `OFFICIAL_EIA_CORRECTION_NOTICE_REQUIRES_SCOPE_REVIEW` dla `nov23`, `STEO_OFFICIAL_NOTICE_SCOPE_PROVENANCE_READ_ONLY_AUDIT` dla 58 wydań zbiorczo. To nie „czerwony błąd ceny WTI”, tylko znacznik, że dla tego wydania **dokumentowano zmianę części raportu**.

## Czego nie robimy

Nie nadajemy historycznego `PIT_CERTIFIED` ani `source_bytes_as_published_certified` na podstawie informacji o późniejszej poprawce. Nie przypisujemy automatycznie wszystkich komunikatów do Table 2. Nie powtarzamy walidacji wstecznej jako wyszukiwania kolejnej korzystnej reguły. Nie włączamy automatycznych zleceń, usług WORM, Neon, nowych ról, kont, sekretów lub harmonogramów.

**Kolejny zasługujący na osobne zatwierdzenie wysiłek dowodowy:** dla wybranych `nov23`, `nov24`, `jan25` oraz `jan24` poszukać niezależnych kopii dostępnych **w pobliżu historycznego dnia wydania**; dla każdej osobno potwierdzić archiwalny adres, `capture_timestamp`, niezależnego dostawcę i autentyczny SHA-256 pobranych historycznych bajtów. Dopiero porównać wartości `WTIPUUS`/`BREPUUS` z arkusza współcześnie hostowanego na EIA. Jeśli brak autentycznej kopii, **jawny wynik UNKNOWN**, nie `PASS`.

## Źródła i poprzednie badania

Oficjalne [archiwum wydawnictw STEO](https://www.eia.gov/outlooks/steo/outlook.php), [badanie 2022–23](STEO_REAL_2022_2023_FROZEN_HISTORY_2026_10_20_PL.md) i [badanie 2024–26](STEO_FULL_34_REAL_RESULTS_2026_10_20_PL.md). Wyniki regresji opisowe; brak wiarygodnego backtestu inwestowalnego instrumentu total-return w PLN, brak realnych transakcji. M1–M3 `HOLD_NO_CHANGE`.
