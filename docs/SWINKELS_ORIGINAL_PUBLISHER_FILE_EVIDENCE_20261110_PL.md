# Swinkels — oryginalny miesięczny szereg zwrotów obligacji, audyt dostępu

**Data audytu:** 2026-11-10. **Issue:** [#123](https://github.com/gniewkob/Investment-Strategy-Lab/issues/123). **Zakres:** jeden oryginalny plik badawczy, jawna licencja, kontrola struktury; bez transakcji, płatności, eksportu historycznych stóp zwrotu, integracji portfela i aktualizacji `main`.

## Niezależnie ustalone dane źródłowe

| Roszczenie | Źródło pierwotne lub katalog archiwalny | Co faktycznie potwierdza |
|---|---|---|
| Autor i seria | [Erasmus University Rotterdam — Historical Data: International monthly government bond returns](https://pure.eur.nl/en/datasets/historical-data-international-monthly-government-bond-returns/) | Laurens Swinkels, DOI historycznego wydania `10.25397/eur.8152748.v6`, miesięczne estymowane stopy zwrotu z obligacji skarbowych dziewięciu krajów, bez Polski, dane do grudnia 2022 r. |
| Prawa do danych | Erasmus: pole **Access Dataset / Creative Commons Attribution 4.0 International** | Licencja CC BY 4.0 przy oryginalnym wydaniu. Licencję konkretnego nowego pakietu należy porównać z jego metadanymi i treścią dokumentacji. |
| Aktualny identyfikator archiwalny | [EUDAT B2FIND — ten sam tytuł, DataverseNL](https://b2find.eudat.eu/dataset/e544d6d3-117d-5da3-845b-9f0afd9d0a47), pola **Identifier, Representation, Rights** | DOI `10.34894/YWT2IX`, 1 plik `.ods` około **913425 B** i 1 plik PDF **127043 B**; metadane opisują CC BY 4.0 i brak Polski. **Nie dowodzi to jeszcze**, że plik ODS jest identyczny bajtowo lub wersjonowo z `10.25397/eur.8152748.v6`. |
| Starszy autorski załącznik | [Erasmus — publikacja artykułu 2019, Access to Document](https://pure.eur.nl/en/publications/treasury-bond-return-data-starting-in-1962/) | Istnieje osobny `8152748.zip` (~809 KB), obok artykułu. **Starszy załącznik nie jest automatycznie aktualną wersją v6.** |
| Sposób pobierania z repozytorium | [DataverseNL — dokumentacja pobierania](https://dans.freshdesk.com/en/support/solutions/articles/80001131825-how-to-download-large-files-from-dataversenl-) | Udokumentowane publiczne endpointy Dataverse API do listy plików i pobierania jednego pliku. Nie stanowi to potwierdzenia działającego odczytu konkretnego DOI w obecnym środowisku. |

## Co faktycznie wykonuje jednorazowa próba

`scripts/research_swinkels_original_source_probe_v01.py` używa **wyłącznie** hosta `dataverse.nl` i publicznego identyfikatora `10.34894/YWT2IX`. Pobiera maksymalnie dwa dokumenty metadanych przez publiczny Dataverse API, a **tylko jeśli** otrzyma rzeczywistą listę plików, identyfikuje dokładnie jeden plik ODS i odczytuje jego bytes. Nie przyjmuje klucza, tokena ani ciasteczka; nie wykonuje przekierowania na nieznanego dostawcę. Ograniczenia: metadane 2 MB, plik 5 MB, wypakowane pliki 32 MB.

W raporcie mogą pojawić się **wyłącznie** źródło, wersja raportowana przez repozytorium, nazwy i rozmiary plików, liczba arkuszy / wierszy XML i SHA-256 oryginalnych bajtów. Nie są publikowane historyczne stopy zwrotu, komórki, dane o inwestorach ani wartości ze zdalnego arkusza; plik nie jest zapisywany w GitHub Actions jako artefakt.

Po pozytywnym odczycie nadal wymagane jest sprawdzenie: oryginalnej dokumentacji PDF, jednostek zwrotu, faktycznych dat i braków w konkretnym kraju, historycznej dostępności (*point-in-time*) i relacji DOI 2025 ↔ 2023. Sama suma kontrolna i liczba wierszy **nie oznaczają**, że istnieje 36 kompletnych miesięcy lub że dane są odpowiednie do celów M1–M3.

Po nieudanym odczycie workflow jest **czerwony**, a stan `OFFICIAL_ORIGINAL_READ=BLOCKED`. Nie tworzy fikcyjnych obserwacji ani nie korzysta z mirrorów.

## Granice wykorzystania

- Dane z dziewięciu rozwiniętych gospodarek nie są zwrotami polskich obligacji; **nie** nadajemy im etykiety `PL_BONDS_TR_PLN`.
- Miesięczne zwroty są estymatami na podstawie dochodowości obligacji i formuł opisanych w [Swinkels (2019), Data 4(3), 91](https://doi.org/10.3390/data4030091); nie są ceną wykonalnego zlecenia.
- Ostatnia obserwacja według wydawcy to grudzień 2022 r.; nie ma danych za 2023–2026.
- Brak wyjaśnionego łańcucha historycznych publikacji nie pozwala nadawać etykiety `HISTORICAL_PIT_CERTIFIED`.
- Nie zmieniać kontrolera M1–M3, G1, kodu operacji finansowych, ustawień sekretów, harmonogramów ani `main`.

**Decyzja na etapie utworzenia Draft:** oryginalny format ODS i DOI potwierdzone w metadanych zewnętrznych, **oryginalne bajty pliku jeszcze niepotwierdzone**. Końcowy wynik musi pochodzić z prawdziwego odczytu CI na dokładnym SHA.
