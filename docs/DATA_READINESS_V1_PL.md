# Data Readiness v1 — częściowa kontrola offline

Ta iteracja nie wykonuje backtestu ani nie tworzy zdarzeń papierowych. `python -m scripts.data_readiness_v1 manifest.json` sporządza deterministyczny inwentarz i zawsze zwraca INSUFFICIENT_DATA: deklaracja w pliku nie dowodzi licencji, autentyczności, dostępności historycznej ani kompletności. Plik wejściowy jest obiektem o kluczach equity, bonds, gold, usdpln, eurpln, inflation, costs. Każdy zawiera source_url, license_status, instrument_kind, currency, basis oraz observations z observed_for (data), available_at i retrieved_at (czas ze strefą) oraz value. Dla obligacji wymagany market to PLN_POLISH_GOVERNMENT. Brak pól jest luką, nie zerem.

## Źródła i ograniczenia do dalszej weryfikacji

* [NBP API](https://api.nbp.pl/) publikuje kursy i referencyjną cenę złota. Cena złota nie jest stopą zwrotu instrumentu; historyczna data publikacji i warunki ponownego wykorzystania wymagają odrębnego potwierdzenia.
* [GUS API](https://api-sdp.stat.gov.pl/) udostępnia dane CPI; trzeba ustalić właściwą serię, daty publikacji i rewizje oraz [warunki wykorzystania](https://bip.stat.gov.pl/kontakt/ponowne-wykorzystywanie-informacji-sektora-publicznego/).
* [Vanguard FTSE All-World UCITS ETF accumulating](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating) jest kandydatem na proxy funduszu, nie indeksem; dostępna pełna historia, reinwestycje, warunki i koszty historyczne nie zostały zweryfikowane. Nie odejmować drugi raz opłat już ujętych w NAV.
* [MSCI index terms](https://www.msci.com/legal/index-terms) ograniczają użycie danych; brak potwierdzonej licencji i danych historycznych. Nie importować ani publikować danych bez zweryfikowania uprawnień.
* Odpowiedni polski benchmark obligacji i jego licencja, historia total return oraz koszty instrumentu pozostają nieustalone. AGG nie jest polską obligacją.

## Kolejne kroki

Potwierdzić prawa i historyczne wersje danych, ustalić harmonogramy publikacji i kompletny wspólny kalendarz, przetestować odrębny silnik na fikcyjnych danych, a następnie wykonać porównanie z prowizją, spreadem, inflacją, obsunięciem i uprzednio ustalonym podziałem IS/OOS. Nie traktować dzisiejszego pobrania jako dowodu historycznej dostępności. Wkłady to ten sam fikcyjny budżet 100 PLN na każdy alternatywny model; listopad 2026 nie wcześniej niż 23.11. Żadnych zapisów do produkcyjnego Neon.
