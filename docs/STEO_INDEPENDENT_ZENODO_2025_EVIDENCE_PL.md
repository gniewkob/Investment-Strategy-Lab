# STEO — niezależny depozyt Catalyst Cooperative / Zenodo z 26.05.2025

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
