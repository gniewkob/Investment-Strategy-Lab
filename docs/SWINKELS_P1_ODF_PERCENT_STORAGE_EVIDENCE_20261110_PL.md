# Swinkels P1 — semantyka procentów ODF i granica kwalifikacji (2026-11-10)

**Repo:** PR #124 (Draft), źródło oryginalne DataverseNL DOI `10.34894/YWT2IX`. **Cel:** odróżnić weryfikację skali przechowywanej wartości od weryfikacji poprawności modelu zwrotu.

## Dowód standardowy

1. OASIS OpenDocument 1.3 Part 4, §4.3.5 Percentage: procent jest podtypem liczby i może być wyświetlany po pomnożeniu wartości liczbowej przez 100 i dodaniu znaku %, zależnie od formatowania komórki: https://oasis-tcs.github.io/odf-tc/odf1.3/content.odf13-formula.html .
2. OASIS OpenDocument, opis `office:value-type=percentage` i `office:value`: wartość procentowa jest kodowana jako liczba (przykład reprezentacji 50%: `office:value=0.50`). Dokument referencyjny: https://docs.oasis-open.org/office/v1.1/OS/OpenDocument-v1.1.pdf ; patrz opis `office:value-type` i pól wartości komórki. Historyczna wersja standardu służy wyłącznie wyjaśnieniu mechanizmu przechowywania.
3. Oryginalny ODS, SHA-256 `90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847`, zweryfikowany workflow https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42861219998: wszystkie 10 arkuszy `Return M` mają `office:value-type=percentage`, `number:percentage-style` i formuły. Sonda nie eksportuje wartości.

## Wniosek dotyczący skali, nie jakości ekonomicznej

Dla oryginalnej komórki ODS ze spójnym typem procentowym jej surowe `office:value` jest **liczbą w skali ułamkowej** (np. 0.01 oznacza 1%), a **nie liczbą punktów procentowych do ponownego podzielenia przez 100**. Formatu procentowego nie należy interpretować jako jednostki wymagającej jeszcze jednej konwersji.

**Dalsza bramka:** audyt rzeczywistych wzorów komórek `Return M`, źródłowych odniesień, zgodności metodologicznej z `Readme.pdf` i artykułem autora, oraz przetestowana implementacja odczytu na przypiętym SHA. Nie można twierdzić, że sama semantyka ODF certyfikuje poprawność formuł lub historycznych zwrotów.

Oryginalny `Readme.pdf`, SHA-256 `b4c4b95917fbff72d06c8e3be1364d91d87779c3752d06260775ade45fb41072`, odczytano w https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42860865427 . Opisuje model total return obligacji oparty na ponownej wycenie przy nowej rentowności. Nie stanowi samodzielnego dowodu historycznej dostępności PIT.

## Granice

- `return_unit` dla realnych komórek nie może pochodzić z tekstu użytkownika ani z automatycznej heurystyki zakresu wartości.
- `validate_monthly_series` i `offline_statistics` pozostają fail-closed do oddzielnego, zrecenzowanego adaptera źródłowego i testów.
- `qualified_model_series=[]`, M1–M3 `INSUFFICIENT_DATA/HOLD_CASH`; brak zleceń, płatności, transferów, harmonogramu kolektora i mergowania `main`.
- Dane obejmują modelowane obligacje innych krajów tylko do 2022 roku — nie są serią polskich obligacji ani instrumentem bezpośrednio zbywalnym.

**Acceptance next:** oryginalna formuła i test zgodności na 36 miesiącach, bez publikacji surowych danych; exact-head CI green Linux/macOS i regresje; tylko wtedy edukacyjny raport offline, nie sygnał inwestycyjny.
