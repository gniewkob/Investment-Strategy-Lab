# Oficjalne EIA STEO — realne 34 wydania i 172 porównania WTI/Brent, 20.10.2026

## Zweryfikowane wykonanie

Źródło: [jednorazowy GitHub Actions `#39426001269`](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39426001269) — **SUCCESS** na kodzie [PR #43](https://github.com/gniewkob/Investment-Strategy-Lab/pull/43) (merge `fc342697d97d6fbcc717abe1654edb2d75f94eb1`). Wykonano **34 prawdziwe publiczne HTTPS** do oficjalnych plików `*_base.xlsx` EIA dla wydań od stycznia 2024 do października 2026. Wszystkie oficjalne daty i oryginalne RAW SHA-256 w logach; każdy XLSX przeszedł ZIP/OOXML, `2tab`, `WTIPUUS`, `BREPUUS`, dynamiczne nagłówki `year/month`, odczyt cen miesięcznych. Każdy podawał 72 miesięczne komórki WTI i Brent (nie wszystkie to *dopuszczalne historyczne prognozy*).

**Status:** `STEO_ALL_34_OFFICIAL_HISTORICAL_RELEASES_RETROSPECTIVE_RESEARCH_COMPLETE`. Łącznie **172 parowane prognozy** (86 WTI + 86 Brent), dane historyczne cen miesięcznych referencyjnych, 6 grup instrument × horyzont; **0 połączeń i zapisów do Neon, 0 zmian alokacji, 0 transakcji**, 0 zadań cyklicznych i 0 zapisanych surowych XLSX/artefaktów. [Testy PR #43](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39425896661): **262/262 offline PASS, 3/3 isolated PG PASS**. Wydania w tym badaniu pobrano w dniu wykonania (20.10.2026), a nie w przeszłości.

## Wynik główny: MAE (USD/baryłkę)

| Źródło | Horyzont w miesiącach | Par | EIA MAE | Naiwny MAE | Niższy MAE |
| --- | ---: | ---: | ---: | ---: | --- |
| Brent | 1 | 31 | 7,76 | 8,58 | EIA |
| Brent | 3 | 29 | 12,21 | 10,89 | Model naiwny |
| Brent | 6 | 26 | 16,99 | 12,56 | Model naiwny |
| WTI | 1 | 31 | 6,44 | 7,46 | EIA |
| WTI | 3 | 29 | 10,87 | 10,18 | Model naiwny |
| WTI | 6 | 26 | 15,53 | 12,21 | Model naiwny |

**Wniosek wyłącznie opisowy:** prognoza EIA była średnio bliżej późniejszej wartości referencyjnej w horyzoncie **1 miesiąca** dla WTI i Brent, ale dla **3 oraz 6 miesięcy** niższy MAE osiągnął prosty punkt odniesienia, tj. wartość poprzedniego miesiąca z *tej samej* historycznej edycji EIA. Dane przeczą pochopnemu wnioskowi z 3-edycyjnego pilotażu (12 par), w którym średnie MAE EIA było lepsze we wszystkich 6 grupach. Rozszerzenie próby zmieniło wnioski; nie wyciągamy z tego decyzji o transakcjach ani „alpha”.

### Rozkład według roku wydania

| Rok prognozy | Surowiec | Horyzont | Par | EIA MAE | Naiwny MAE | EIA lepsza w liczbie par |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 2024 | Brent | 1 | 12 | 4,84 | 4,77 | 4/12 |
| 2024 | Brent | 3 | 12 | 6,81 | 5,32 | 2/12 |
| 2024 | Brent | 6 | 12 | 10,46 | 7,57 | 3/12 |
| 2024 | WTI | 1 | 12 | 4,59 | 4,69 | 4/12 |
| 2024 | WTI | 3 | 12 | 6,16 | 6,24 | 4/12 |
| 2024 | WTI | 6 | 12 | 9,87 | 7,93 | 4/12 |
| 2025 | Brent | 1 | 12 | 3,94 | 4,38 | 7/12 |
| 2025 | Brent | 3 | 12 | 10,94 | 8,05 | 4/12 |
| 2025 | Brent | 6 | 12 | 21,04 | 15,82 | 5/12 |
| 2025 | WTI | 1 | 12 | 3,87 | 4,37 | 9/12 |
| 2025 | WTI | 3 | 12 | 9,91 | 7,35 | 5/12 |
| 2025 | WTI | 6 | 12 | 18,78 | 14,67 | 7/12 |
| 2026 | Brent | 1 | 7 | 19,30 | 22,32 | 3/7 |
| 2026 | Brent | 3 | 5 | 28,20 | 31,08 | 2/5 |
| 2026 | Brent | 6 | 2 | 31,92 | 22,85 | 0/2 |
| 2026 | WTI | 1 | 7 | 14,00 | 17,50 | 4/7 |
| 2026 | WTI | 3 | 5 | 24,48 | 26,42 | 2/5 |
| 2026 | WTI | 6 | 2 | 29,93 | 23,18 | 0/2 |

Wyniki 2026 mają **niepełne pokrycie do października 2026**, szczególnie dla horyzontu 6 miesięcy zaledwie **2 pary** na surowiec; nie porównywać tych roczników mechanicznie jak równolicznych okresów. Prognozy kolejnych miesięcznych raportów mogą dotyczyć nakładających się przyszłych miesięcy; 172 pary **nie są 172 niezależnymi próbami statystycznymi**. Nie obliczono ufności/p-value i nie oznaczono przewagi predykcyjnej jako ustalonej.

### Co dokładnie porównano

- `source_forecast_value`: oficjalna historyczna wartość WTI/Brent **na miesiąc przyszły** +1/+3/+6 miesięcy względem miesiąca formalnej daty wydania, pobrana z `2tab` przez dynamiczne nagłówki lat i miesięcy.
- `same_edition_previous_month_naive_value`: cena za poprzedni miesiąc **z tego samego starego raportu** STEO, bez używania później rewidowanych cen do naiwnej prognozy.
- `later_edition_reference_value`: pierwsza **spośród pobranych 34 edycji** opublikowanych co najmniej dwa miesiące kalendarzowe po okresie prognozy, w której ten sam target miesiąca istnieje już jako historyczna cena referencyjna. Nie jest to dokument księgowy realnego wypełnienia zlecenia ani definitywny „close”; wartości nadal podlegają późniejszym rewizjom.
- Błędy obliczano bezwzględnie w USD/baryłkę i parowano dla jednakowych target miesięcy; publiczne wartości z Excel cache normalizowano do dokładności EIA 0,01 USD/baryłkę, **oryginalne SHA dotyczy nietkniętych bajtów**.

### Ograniczenia integralności historycznej

**NIE uzyskano niezależnej certyfikacji, że `jan24_base.xlsx` pobrany dzisiaj ma identyczne bajty jak w styczniu 2024.** Pochodzi z oficjalnego archiwum oznaczonego dawną datą, lecz zawartość mogła być aktualizowana lub poprawiana. Właściwą historyczną datą publicznego wydania jest data `Release Date` z indeksu EIA, nie wewnętrzna data przygotowania `Forecast date`; oryginalny PIT dostępności konkretnych bajtów `false`. Najwcześniej chronologia pozwala na dzień po wskazanej dacie publikacji (DAY), ale **nie gwarantuje autentyczności tamtego konkretnego stanu historycznych wartości**.

Źródłowe WTI i Brent są **miesięcznymi referencyjnymi cenami spot USD/bbl**, nie instrumentami typu total return PLN z możliwym wykonaniem transakcji. Nie wolno przeliczać MAE na prognozowaną stopę zwrotu inwestora bez niezależnych danych o instrumentach, kosztach i metodzie egzekucji. **M1/M2/M3 HOLD_NO_CHANGE.**

## Weryfikowalny manifest 34 autentycznych pobrań

Poniższe hash-e to wyłącznie oryginalne bajty XLSX **pozyskane 20.10.2026**. Nie przechowano pełnych XLSX na GitHub ani dołączonych artefaktów. SHA może zostać użyte do kontroli ewentualnego późniejszego pobrania z EIA; różnica SHA nie oznacza automatycznie rewizji cen.

| Archiwum | Oficjalna data wydania | RAW XLSX SHA-256 pobrany dziś | Miesięczne pola WTI / Brent |
| --- | --- | --- | --- |
| `jan24` | 2024-01-09 | `663ee3c648d2e88dad48dd1efd2557df99c811afe4afcc2094ed92c988fb53a9` | 72 / 72 |
| `feb24` | 2024-02-06 | `dc3742fe43299f5288533d328c86c8435bc8223d92e26ad418ee276b2890aae3` | 72 / 72 |
| `mar24` | 2024-03-12 | `0f168cec985f5511c93b6238cfc27cacf4df1f2dd890ce01d23fd1e81c30b513` | 72 / 72 |
| `apr24` | 2024-04-09 | `144ffbf52092468b4bccdd58b94dfacf4b603351ec7dba54fafb1d4b8b6a9095` | 72 / 72 |
| `may24` | 2024-05-07 | `b26d58c911a0878fd615aedd164a2d4796927146c45654d90edcb457ca57f8ea` | 72 / 72 |
| `jun24` | 2024-06-11 | `12cd939ba0d9d6b559d56d40cc0650e99c57d249fff1ecc691af601a2e0de636` | 72 / 72 |
| `jul24` | 2024-07-09 | `066eb3d2691a4ace702483ee4a73f64c6d9899a692edb4b9171d94b986b369dd` | 72 / 72 |
| `aug24` | 2024-08-06 | `a4679e91622d5d8d414954b988afdb4119690e7d0b1e458e30be0ca7666ca826` | 72 / 72 |
| `sep24` | 2024-09-10 | `3b663f40f03a86483340e9cb7fd66c6e05e0b5acd2771c56497728fcb478a7dd` | 72 / 72 |
| `oct24` | 2024-10-08 | `3825256dd82e3347df45632c1320e73d38acb82e4a5f2ebe5197148844dc9ba4` | 72 / 72 |
| `nov24` | 2024-11-13 | `0aea752a8bd2991df43b028a9d10d673ee98710a99cd9e1864d936ba9b7059bb` | 72 / 72 |
| `dec24` | 2024-12-10 | `b650cb965a38a67e8b5e2f4d8df794b8ddfab6a429fca551cc1c7ff404ffb396` | 72 / 72 |
| `jan25` | 2025-01-14 | `67f9f24b6f0bd074bcc92e47f8f5ea23594f2dd6ccbf31b2dff912621bbb5b22` | 72 / 72 |
| `feb25` | 2025-02-11 | `64ac0e0d1d7e084745ebd88b4a234c57f7fdc3a6c652a91c79147d199bbbdb01` | 72 / 72 |
| `mar25` | 2025-03-11 | `62dc490de708892d24411fe7e6902cc57ad63b60e5c8b864d9f3bdaeea89ce29` | 72 / 72 |
| `apr25` | 2025-04-10 | `b3dab5214dcc1c3dae3cea87431e6a781769996adc702b21d35eb254c0345ad4` | 72 / 72 |
| `may25` | 2025-05-06 | `ea81918222483bafd3bcbdd98f52c2b1f17cb6470c3830a6a0deb8bd213fe228` | 72 / 72 |
| `jun25` | 2025-06-10 | `332f761e85c7ab3d5f4eded212f30987a409cb19042072e90b3af9bd9bcf5164` | 72 / 72 |
| `jul25` | 2025-07-08 | `4231a27728d8c6f99dda0e51796e3b7a18e39f4fdcd2edfb4d8a43eadb0e850e` | 72 / 72 |
| `aug25` | 2025-08-12 | `31e4bec79e50872816cf7c300501e0a462b50f7316eba7011ae4cec3e2b8e64f` | 72 / 72 |
| `sep25` | 2025-09-09 | `8f1665eebc7fda9f4bd67c53e6b0e3452f777247d292be4ffbbb9644a03e742e` | 72 / 72 |
| `oct25` | 2025-10-07 | `01aba5772bdeb3d07ee7b5381bfb0dda6f14275f3ec11c05b9e09f2f8cff24b6` | 72 / 72 |
| `nov25` | 2025-11-12 | `23f7044def86525fefcef30dce3e4aeec6b46cf1f56ad9809eb91455f8daceef` | 72 / 72 |
| `dec25` | 2025-12-09 | `0531b7d5f0d1af686fd7afcc91461dcb4a4960d3f76ebb673776946df383253e` | 72 / 72 |
| `jan26` | 2026-01-13 | `8844e274c26c6d3906bab78c027019e4c39a42322b7a9b911fbe4e19e133f99c` | 72 / 72 |
| `feb26` | 2026-02-10 | `6137d255d2d794a8862b96b5234a33f8a3e52d2633dff546c82e511fb85847d8` | 72 / 72 |
| `mar26` | 2026-03-10 | `0cd3cb78a681757e1ad954e20e061fd04e4e8d14099ab24d9554620c0204badf` | 72 / 72 |
| `apr26` | 2026-04-07 | `54bec64cfb767ecdfb490ab9e20986610dbaf865dc933baef6c4657ccc8d248f` | 72 / 72 |
| `may26` | 2026-05-12 | `713b1a01e46bc8d00c6795fd4d668c9635977631e4071e0819349a151dbd07e2` | 72 / 72 |
| `jun26` | 2026-06-09 | `ad3fc1618a0fa0b17e4b31d04bacf69c06677387b879f8e1858f1f895a9994c8` | 72 / 72 |
| `jul26` | 2026-07-07 | `67741610f3bb74e011a55a40d9cb571f5ea9108a96ef7d144e65519abd72f490` | 72 / 72 |
| `aug26` | 2026-08-11 | `2f58e3cee31c68b395bbc468673a887e5691b91bfad2c1676f2e58f5fe84b1d1` | 72 / 72 |
| `sep26` | 2026-09-09 | `c06a15243b0d972045ecc59cf9376885f68c7c306c581de5d01e6b8ac1a236c5` | 72 / 72 |
| `oct26` | 2026-10-06 | `54989362410da4aff5673580396380c3a8f4f111fa6d01c6d4fab05ef90efbf4` | 72 / 72 |

**Kolejny racjonalny krok:** statystyczna stabilność względem okresu i benchmarku, kontrola nakładania się targetów, źródłowa kontrola drastycznych wyników 2026, test prostych modeli na odrębnym okresie i docelowo prospektywny eksperyment na rzeczywiście niezależnych od siebie historycznych raportach. Żaden z powyższych błędów w cenach referencyjnych nie daje automatycznie podstaw do transakcji.

Zobacz: [pierwszy 12-parowy pilot](STEO_REAL_FORECAST_ERRORS_2026_10_20_PL.md), [metodologia pełnej próby](STEO_FULL_34_HISTORICAL_RESEARCH_PL.md).
