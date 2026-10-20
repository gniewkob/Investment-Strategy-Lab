# STEO — niezależny depozyt Catalyst Cooperative / Zenodo z 26.05.2025

## Zweryfikowany rzeczywisty pierwszy pilot — niezależny 2025 ZIP z oryginalnym STEO XLSX

[Jednorazowy GitHub Actions #39443655584](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39443655584) **SUCCESS**. Dokładny ZIP z Zenodo z 26.05.2025: **48,241,045 bajtów**, MD5 `21b1dc10ba6503b4446143e212ada2a0` pokrywa się z opublikowanym manifestem. W środku **12 oryginalnych plików `YYYY-MM/{issue}_base.xlsx`** i **12 pełnych raportów PDF** z każdego miesiąca 2024, bez kolejnego ZIP wewnątrz. Oryginalna paczka ma SHA-256 `08d6e512f4e88eb150116eec23a72943a0f5f6d0891c18e6775eb0e40771c7ab`.

Rzeczywisty SHA-256 niezależnie zdeponowanego w maju 2025 XLSX **zgadza się bajt po bajcie** z wcześniej zweryfikowanymi oryginalnymi plikami EIA pobranymi 20.10.2026:

| Oryginalny plik | SHA-256 bajtów obu kopii (Zenodo 2025 = EIA 2026) |
|---|---|
| `2024-01/jan24_base.xlsx` | `663ee3c648d2e88dad48dd1efd2557df99c811afe4afcc2094ed92c988fb53a9` |
| `2024-11/nov24_base.xlsx` | `0aea752a8bd2991df43b028a9d10d673ee98710a99cd9e1864d936ba9b7059bb` |
| `2024-12/dec24_base.xlsx` | `b650cb965a38a67e8b5e2f4d8df794b8ddfab6a429fca551cc1c7ff404ffb396` |

**Znaczenie:** niezależny depozyt z 2025 zawiera te same *oryginalne bajty XLSX* co obecne EIA. To więcej niż sama zgodność cen, ale **nie** poświadcza treści na dzień pierwszej publikacji w 2024.

## Kontrola pozostałych 36 pierwotnych wydań STEO 2022–2024

Moduł `scripts/steo_zenodo_vintage_crosscheck.py` jest **czystą funkcją offline** do niezależnego porównania zawartości rocznych paczek Zenodo `2022`, `2023`, `2024` — każda ze ścisłą sumą MD5 wersji depozytu z 2025 — z **wcześniej utrwalonymi oryginalnymi EIA XLSX SHA-256 z października 2026**. Nie wymaga osobnego pobierania z EIA, nie przetwarza cen, nie modyfikuje historycznych prognoz.

Nowa jednorazowa sonda `steo-independent-zenodo-36-proof-once.yml` pobierze trzy roczne ZIP do ulotnej pamięci runnera i wyświetli 36 par dowodowych. **Wynik jeszcze nie potwierdzony, zanim uruchomienie publicznych źródeł zakończy się sukcesem.** Każdy niezgodny hash zostanie oznaczony do przeglądu semantycznego, **nie jako automatycznie potwierdzona korekta ceny**. Dla wszystkich wydań `historical_first_publication_point_in_time_certified=false`.


## Ustalony niezależny punkt dowodowy

[Zenodo, DOI 10.5281/zenodo.15386905](https://zenodo.org/records/15386905) to **wersja 2.0.0 EIA STEO — Short-Term Energy Outlook** opublikowana **26 maja 2025 r.** przez **Catalyst Cooperative**, niezależny podmiot archiwizujący źródłowe dane do projektu Public Utility Data Liberation (PUDL). [PUDL opisuje archiwa](https://docs.catalyst.coop/pudl/en/stable/data_access.html) jako minimalnie przetworzone, czasami pogrupowane i skompresowane pliki wejściowe. To nie jest własne archiwum EIA.

Weryfikowalne metadane Zenodo dla interesującej nas paczki `eiasteo-2024.zip`:

- publikacja depozytu: **26.05.2025**, wcześniejsza od pierwszych badań ISL z października 2026;
- rok partycji: **2024**;
- nazwa: `eiasteo-2024.zip`;
- liczba bajtów deklarowana w `datapackage.json`: `48,241,045`;
- suma paczki podana przez Zenodo / `datapackage.json`: **MD5 `21b1dc10ba6503b4446143e212ada2a0`**;
- link oryginalnego zasobu: <https://zenodo.org/records/15386905/files/eiasteo-2024.zip>.

**To nadal nie certyfikuje bajtów `jan24_base.xlsx` w dniu 09.01.2024.** Osobny podmiot mógł pobrać archiwalny plik po korekcie. Przy ewentualnym porównaniu źródłowej zawartości z plikami EIA pobranymi w październiku 2026 rozróżnić:

1. `ZENODO_2025_PACKAGE_MD5_MATCH`: zgodność całej paczki z konkretnym depozytem z maja 2025;
2. `INDEPENDENT_2025_RAW_XLSX_MEMBER_SHA_MATCH`: konkretny oryginalny plik XLSX istnieje wewnątrz depozytu, jego SHA pokrywa się z październikowym EIA. To mocniejszy, ale tylko **2025 snapshot**;
3. `INDEPENDENT_2025_RAW_XLSX_MEMBER_SHA_DIFF`: ten sam plik jest inny; wymaga porównania wartości WTI/Brent oraz określenia, czy różnica jest czysto techniczna, czy semantyczna;
4. `NO_VERIFIED_RAW_XLSX_MEMBER`: depozyt zawiera inne źródła lub format/strukturę nieodczytaną — **nie wolno** oznaczać porównania XLSX jako PASS;
5. `HISTORICAL_ORIGINAL_ISSUE_PIT_CONFIRMED`: zawsze **false**, dopóki nie mamy **wcześniejszego niezależnego dowodu** zgodnego z datą wydania STEO z 2024 r.

## Techniczny pilot bez plików trwałych

Jednorazowy [GitHub Actions `steo-independent-zenodo-proof-once.yml`](../.github/workflows/steo-independent-zenodo-proof-once.yml) pobiera tylko **jeden publiczny ZIP 2024** z konkretnego opublikowanego w maju 2025 depozytu i sprawdza jego deklarowane **MD5** (plus SHA-256 bieżącego pobrania). W pamięci sprawdza listę plików, rozmiary i bezpieczne ścieżki, a następnie szuka bezpośrednich członków `jan24_base.xlsx`, `nov24_base.xlsx`, `dec24_base.xlsx`. Jeżeli znajdzie autentyczny XLSX, policzy jego SHA-256 i zidentyfikuje ścieżkę. Jeśli paczka ma kolejną warstwę ZIP lub inną konwencję nazw, tylko raportuje jej strukturę do dalszej weryfikacji, bez wyciągania wniosków.

**Bez danych numerycznych, bez zapisu RAW do repozytorium, dysku projektu, Neon ani MyDevil; brak sekretów, nowych uprawnień, harmonogramu, zleceń i zmian w portfelach.** Wykonanie tylko przy scaleniu pliku workflow lub świadomym `workflow_dispatch`.

**Status:** jawna kontrola oryginalnej paczki i jej wewnętrznej struktury oczekuje na wynik realnego GitHub Actions. Wcześniejsze STEO 316 par pozostają retrospektywnymi rekonstrukcjami `PIT_UNVERIFIED`. M1/M2/M3 `HOLD_NO_CHANGE`. Backup EIA MyDevil/Mac potwierdzony i zamknięty.

Źródła: [Zenodo v2.0.0](https://zenodo.org/records/15386905), [opis PUDL raw data](https://docs.catalyst.coop/pudl/en/stable/data_access.html), [rejestr korekt STEO](STEO_OFFICIAL_ERRATA_PROVENANCE_2026_10_20_PL.md).
