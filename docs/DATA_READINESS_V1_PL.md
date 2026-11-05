# Data Readiness v1 — częściowa kontrola offline

Ta iteracja nie wykonuje backtestu ani nie tworzy zdarzeń papierowych. `python -m scripts.data_readiness_v1 manifest.json` sporządza deterministyczny inwentarz i zawsze zwraca INSUFFICIENT_DATA: deklaracja w pliku nie dowodzi licencji, autentyczności, dostępności historycznej ani kompletności. Plik wejściowy jest obiektem o kluczach equity, bonds, gold, usdpln, eurpln, inflation, costs. Każdy zawiera source_url, license_status, instrument_kind, currency, basis oraz observations z observed_for (data), available_at i retrieved_at (czas ze strefą) oraz value. Dla obligacji wymagany market to PLN_POLISH_GOVERNMENT. Brak pól jest luką, nie zerem.

## Źródła i ograniczenia do dalszej weryfikacji

* [NBP API](https://api.nbp.pl/) publikuje kursy i referencyjną cenę złota. Cena złota nie jest stopą zwrotu instrumentu; historyczna data publikacji i warunki ponownego wykorzystania wymagają odrębnego potwierdzenia.
* [GUS API](https://api-sdp.stat.gov.pl/) udostępnia dane CPI; trzeba ustalić właściwą serię, daty publikacji i rewizje oraz [warunki wykorzystania](https://bip.stat.gov.pl/kontakt/ponowne-wykorzystywanie-informacji-sektora-publicznego/).
* [Vanguard FTSE All-World UCITS ETF accumulating](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating) jest kandydatem na proxy funduszu, nie indeksem; dostępna pełna historia, reinwestycje, warunki i koszty historyczne nie zostały zweryfikowane. Nie odejmować drugi raz opłat już ujętych w NAV.
* [MSCI index terms](https://www.msci.com/legal/index-terms) ograniczają użycie danych; brak potwierdzonej licencji i danych historycznych. Nie importować ani publikować danych bez zweryfikowania uprawnień.
* [Regulamin TBSP.Index](https://www.bondspot.pl/pub/Regulacje_TBS_Poland/UZ_271-19-Regulamin_Indeksu_Treasury_BondSpot_Poland_obow._25_11_2019.pdf) opisuje indeks dochodowy uwzględniający narosłe odsetki i reinwestycję kuponów. To kandydat na benchmark polskich obligacji, nie instrument; licencja, pełna historia i koszty dostępnego instrumentu pozostają nieustalone. AGG nie jest polską obligacją.

## Kolejne kroki

Adapter `python -m scripts.nbp_reference_capture 2026-10-01 2026-10-16` odczytuje tabelę A i cenę złota przez publiczne HTTPS API NBP, w przedziale do 93 dni włącznie, i wypisuje lokalnie potwierdzenie z URL, SHA-256 surowych odpowiedzi, datą publikacji i rzeczywistym czasem pobrania. Dokładny czas dostępności i historyczna wersja pozostają nieznane. Błędy HTTP, puste odpowiedzi i niepoprawne rekordy przerywają pobieranie; adapter nie uzupełnia luk i nie zapisuje do bazy. Hash dowodzi integralności pobranych bajtów, nie autentyczności historycznego wydania. Prawa do przechowywania i publikacji danych NBP wymagają weryfikacji przed trwałym udostępnieniem.

Pole `series` z odpowiedzi adaptera można przekazać do kalendarza wraz z niezależnie potwierdzonymi `sessions` i `decision_dates`. `observed_for` oznacza datę publikacji referencji NBP, nie dokładny czas kwotowania rynku. Złoto pozostaje `PRICE_ONLY`, FX pozostaje kursem średnim; obie serie mają niezweryfikowaną licencję i vintage. Konwersja formatu nie oznacza dopuszczenia danych do backtestu.

Potwierdzić prawa i historyczne wersje danych, ustalić harmonogramy publikacji i kompletny wspólny kalendarz, przetestować odrębny silnik na fikcyjnych danych, a następnie wykonać porównanie z prowizją, spreadem, inflacją, obsunięciem i uprzednio ustalonym podziałem IS/OOS. Nie traktować dzisiejszego pobrania jako dowodu historycznej dostępności. Wkłady to ten sam fikcyjny budżet 100 PLN na każdy alternatywny model; listopad 2026 nie wcześniej niż 23.11. Żadnych zapisów do produkcyjnego Neon.


## Iteracja 2026-11-04: wspólny kalendarz PIT (offline)

Moduł scripts/monthly_pit_calendar.py przyjmuje JSON z:
- sessions: uporządkowane daty ISO zweryfikowanych sesji; nie generuje kalendarza świąt;
- decision_dates: podzbiór sessions, identyczny dla M1/M2/M3;
- series: equity, bonds, gold, usdpln, eurpln, inflation, costs. Każdy rekord to observed_for, publication_date, retrieved_at (ISO ze strefą), value, currency, basis, source_url HTTPS, source_sha256, license_status, historical_vintage_verified.

Gdy źródło publikuje tylko dzień, **najwcześniej następna podana
sesja po dniu publikacji** może służyć jako wstępna data użycia.
To reguła konserwatywna, ale NIE dowód rzeczywistej historycznej godziny
publikacji ani oryginalnej wersji danych. Czas pobrania naszej kopii
nie jest historyczną datą pierwszej dostępności.

Kontrole: chronologia, duplikaty, dodatnie wartości (zero dopuszczone
wyłącznie przy costs), SHA-256, HTTPS, pokrycie według wspólnej daty decyzji,
opóźnienie obserwacji w miesiącach. Nie certyfikujemy licencji ani
historycznego point-in-time na podstawie deklaracji z manifestu.
Moduł zawsze kończy jako INSUFFICIENT_DATA / NOT_RUN /
paper_events_created=0. Żadnych zapisów do Neon ani zleceń.

### Kandydaci na dane — jeszcze nie zatwierdzone źródła do backtestu

| Klasa | Oficjalne źródło | Znaczenie i blokady |
|---|---|---|
| Akcje globalne | [Vanguard FTSE All-World UCITS ETF Acc](https://www.pl.vanguard/inwestorzy-indywidualni/produkt/etf/akcje/9679/ftse-all-world-ucits-etf-usd-accumulating) | NAV funduszu w USD to nie indeks ani cena rynkowa ETF; brak zweryfikowanej licencji na pełny historyczny import i vintage. Opłat ujętych w NAV nie odejmować ponownie. |
| Obligacje polskie | [TBSP.Index — BondSpot](https://www.bondspot.pl/tbsp_index_opis/pub/Regulacje_TBS_Poland/tbsp_index_opis) | Benchmark polskich obligacji skarbowych w PLN, administrowany przez GPW Benchmark; to nie instrument transakcyjny. Pełna historia, warunki licencji i point-in-time nadal wymagają potwierdzenia. |
| Inflacja | [GUS — miesięczne CPI od 1982 r.](https://publikacje.new.stat.gov.pl/portal-publikacje/miesieczne-wskazniki-cen-towarow-i-uslug-konsumpcyjnych-od-1982-r) | Tabela CSV/XLSX z różnymi bazami; do miesięcznego łańcuchowania właściwa baza poprzedni miesiąc=100. Sprawdzić daty publikacji historycznych wersji i [warunki ponownego wykorzystania](https://bip.stat.gov.pl/kontakt/ponowne-wykorzystywanie-informacji-sektora-publicznego/). |
| FX/złoto | [NBP API](https://api.nbp.pl/) | Referencyjne kursy i złoto (cena, nie total return), nadal bez dowodu oryginalnej wersji i historycznej godziny dostępności. |

### Warunki odbioru

Zweryfikować dostęp i prawa do kompletnych NAV i TBSP.Index, historyczne
wersje oraz momenty udostępnienia, kalendarz sesji i koszty. Dopiero później
wykonać zamrożony IS/OOS, total return w PLN, FX, inflację, prowizje
i spread na jednakowym harmonogramie M1/M2/M3. Security review
wcześniejszego commitu zwrócił HTTP 400; NIE zaliczono kontroli.
