# Swinkels — oficjalny crosswalk DataCite: Erasmus v6 → DataverseNL (12.11.2026)

**Zakres:** source-provenance metadata, bez inwestycji, bez pobierania plików ODS, bez kwalifikacji PIT. [Issue #123](https://github.com/gniewkob/Investment-Strategy-Lab/issues/123).

## 1. Niezależne pierwotne źródła

| Fakt | Źródło i dokładne pole | Status |
| --- | --- | --- |
| Historyczne wydanie `10.25397/eur.8152748.v6` | [DataCite old v6](https://api.datacite.org/dois/10.25397%2Feur.8152748.v6), `attributes.doi`; `publicationYear=2023`, rekord utworzony 2023-01-10 | Rejestr DOI zweryfikowany |
| Wydawca i autor starej wersji | Ten sam rekord: `publisher=Erasmus University Rotterdam (EUR)`; `creators[0].name=Swinkels, Laurens` | Zgodne |
| Odesłanie historycznej wersji do bazowego DOI | Stary rekord: `relatedIdentifiers[]` z `relationType=IsIdenticalTo`, `relatedIdentifier=10.25397/eur.8152748` | **Relacja metadanych**, nie hash pliku |
| Przekierowanie dawnego DOI do nowego pakietu | Stary rekord: `attributes.url=https://doi.org/10.34894/YWT2IX` (rekord aktualizowany 2025-10-24) | Oficjalny łańcuch DOI |
| Rejestr nowego DOI | [DataCite DataverseNL](https://api.datacite.org/dois/10.34894%2FYWT2IX), `attributes.doi`, `publisher=DataverseNL`, `publicationYear=2025`, `version=1.0`, `dates[Available]=2025-08-22` | Zgodne; **nie jest datą publikacji miesięcy 2020–2022** |
| Dowód odwrotnego powiązania | Nowy rekord: `alternateIdentifiers[]` i `identifiers[]` wskazują `https://doi.org/10.25397/eur.8152748` | Potwierdzony |
| Identyfikacja twórcy i licencji | Oba rekordy: Laurens Swinkels, identyczny tytuł, `rightsList[].rightsIdentifier=cc-by-4.0` | Zgodne z metadanymi wydawców |
| Rozmiar starego pakietu | Stary rekord: `sizes=["1040468 Bytes"]` | 1 040 468 bajtów |
| Rozmiar nowego pakietu | Nowy rekord: `sizes=["913425","127043"]` | **913 425 + 127 043 = 1 040 468**, zgodność pełnego rozmiaru |
| Operacyjna migracja EDR | [Erasmus University Library, 26.06.2025](https://www.eur.nl/en/library/news/edr-platform-transitioning-figshare-dataversenl): oficjalny komunikat o przejściu z Figshare na DataverseNL, planowane zakończenie 30.10.2025 | Niezależne potwierdzenie procesu migracji |

## 2. Co można stwierdzić

`OFFICIAL_DATASET_IDENTITY_LINEAGE_VERIFIED` — tak, jako formalne powiązanie DOI w rejestrze DataCite. `OLD_NEW_PACKAGE_SIZE_MATCH` — tak. Nowy plik ODS ma niezależnie sprawdzony SHA-256 `90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847`, ale **ten SHA nie pochodzi z archiwum wersji v6**. Oryginalny DataverseNL ODS wraz z README był badany jako odrębnie wydane źródło (PR #139).

**Nie wolno wyprowadzić** `ORIGINAL_V6_BYTES_IDENTICAL=true` tylko z rozmiaru lub identycznych tytułów/DOI. Dwa różne pliki mogą mieć ten sam rozmiar. API starego repozytorium Figshare nie zwróciło możliwej do zweryfikowania listy oryginalnych hashy v6; nie użyto lustrzanych/nieautoryzowanych kopii. Metadane wersji Dataverse 1.0 z 2025 r. nie potwierdzają *point-in-time* dostępności poszczególnych miesięcznych wartości z lat 2020–2022.

## 3. Rozdzielenie odbiorów

**Ukończone:** badanie oryginalnego obecnego DataverseNL ODS, 10 wariantów × 36 miesięcy, niezależne wzory, zagregowany research receipt, CC BY w metadanych, zgodność łańcucha DOI i rozmiaru paczki.

**Otwarte:** porównanie **starego repozytoryjnego pliku v6** z aktualnym ODS i README przy użyciu kontrolnych sum oryginalnych bajtów albo autorytatywnego manifestu migracji. Właściciel archiwum może potwierdzić zakres migracji, oryginalne sumy kontrolne oraz ewentualne transformacje — bez pobierania i rozpowszechniania niesprawdzonych danych.

Oficjalny kontakt do [Erasmus Library Repository Team](https://www.eur.nl/en/library/research-support/eur-data-repository) służy do złożenia zapytania o **manifest/checksum**, a nie zgody na trading czy nieuprawniony dostęp. Żadne zapytanie nie zostało wysłane w ramach tego PR.

## 4. Mechanizm kontroli i odcięcia

`scripts/swinkels_datacite_doi_lineage_v01.py` weryfikuje jednorazowo **tylko dwa JSON DOI rejestru DataCite**, bez pobierania źródłowych danych finansowych. Przy niezgodności DOI, autora, licencji, powiązania dwukierunkowego, wielkości plików albo daty pierwszej dostępnej wersji kończy się `BLOCKED`. Testy syntetyczne na Ubuntu/macOS i osobny jednorazowy odczyt aktualnych metadanych mają własny workflow. Ten test nie tworzy historycznych vintages i nie zmienia źródeł M1–M3.

**Decyzja kwalifikacyjna:** `old_v6_and_new_dataverse_bytes_identical=false` jako **not verified**, nie jako dowód różnicy; `historical_pit_certified=false`; `qualified_model_series=[]`; `M1_M2_M3=INSUFFICIENT_DATA/HOLD_CASH`; `financial_operations=0`.
