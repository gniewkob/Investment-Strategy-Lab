# WTI EIA ↔ Neon STAGING — jeden kontrolowany przebieg, tylko odczyt

## Cel i ograniczenie

Dostarczyć jeden spójny, możliwy do odtworzenia audyt bieżącej oficjalnej
strony EIA WTI i istniejącej historii referencyjnej Neon STAGING w **tym samym
ręcznie uruchomionym procesie**. Narzędzie odczytuje rzeczywiste bajty HTML i
prawdziwy weryfikowany technicznie wyciąg istniejących publicznych cen ze
STAGING. Nie importuje danych i **nie certyfikuje** historycznych dat ich
pierwszej publikacji. Obowiązuje `UNVERIFIED_HISTORICAL_PUBLICATION`.

## Zakres zamrożony przed pobraniem źródła

| Parametr | Wartość |
| --- | --- |
| Instrument | WTI_EIA_USD_BBL |
| Pierwsza obserwacja | 2024-01-02 |
| Ostatnia obserwacja badanego zakresu | 2026-10-14 |
| Ostatnia data już zapisana w Neon | 2026-08-25 |
| Oczekiwane istniejące WTI | 660 |
| Zamrożona liczba luk | 35 |
| Oficjalne wydanie strony EIA | 2026-10-15 |
| Źródło HTTPS | https://www.eia.gov/dnav/pet/hist/RWTCd.htm |

Jeżeli dostawca zmieni datę wydania, zakres lub wartość źródłową, skrypt
odmówi wygenerowania pozytywnego certyfikatu dla STAREGO zamrożonego okna.
Nie wolno cicho nadpisywać parametrów i nazywać nowego pomiaru starym.

## Granica bezpieczeństwa

1. Wykorzystuje **istniejący, już skonfigurowany** sekret GitHub Environment
   `research-staging / NEON_HISTORICAL_READ_DATABASE_URL`; nie tworzy ani
   nie resetuje żadnego hasła. Specjalna rola
   `isl_legacy_history_reader` ma tylko SELECT na
   `investment_lab.price_observations`.
2. Ponownie używa `fetch_staging_history`, który wymaga jednego zatwierdzonego
   hosta, użytkownika i bazy, TLS `sslmode=verify-full`, certyfikatu CA,
   `SET TRANSACTION READ ONLY` oraz weryfikuje ACL i zakaz dostępu do
   `holding_snapshots`, `valuations`, `paper_events`, `agent_cycles`.
3. Lokalny CSV trzech publicznych pól powstaje **tylko tymczasowo** wewnątrz
   joba, z uprawnieniami 0600, jest czytany i SHA-256 liczony z tych samych
   bajtów przez istniejący `read_local_reference_with_digest`, po czym jest
   usuwany przed emisją wyniku. Brak eksportu surowych cen lub HTML.
4. `fetch_official` pobiera tylko stały, dopuszczony URL EIA bez przekierowań
   oraz sprawdza format, kompletność i rzeczywisty hash pierwotnych bajtów HTML.
5. `review_gap` odrzuca ceny różniące się nawet na jednej wspólnej dacie,
   luki przed odcięciem, brak skrajnych dat, zmieniony kalendarz, inny dzień
   wydania EIA i nieoczekiwaną liczbę braków.
6. Ujawniane są wyłącznie liczby, **daty**, SHA-256 surowego HTML, SHA-256
   tymczasowego pliku referencyjnego, rzeczywisty timestamp pobrania i
   jednoznaczne ograniczenia dowodowe. Logi błędów zawierają tylko stały kod
   i nazwę klasy błędu, nie wyjątek libpq / DSN.
7. Brak schedule, brokerskich API, transferów, zmian modeli, importu, backfillu,
   migracji, ACL lub ingerencji w produkcję.

## Testy i uruchomienie

Workflow: [Frozen WTI EIA and Neon STAGING receipt — MANUAL READ ONLY](../.github/workflows/eia-wti-staging-receipt.yml).

PR uruchamia **tylko syntetyczne testy offline, bez sekretów**. Żywy przebieg
wymaga osobnej czynności operatora **po połączeniu zmian do main**:

GitHub → Actions → `Frozen WTI EIA and Neon STAGING receipt — MANUAL READ ONLY`
→ Run workflow → branch `main`.

Weryfikować wynik joba `manual-staging-read-only` i artefakt
`wti-eia-staging-readonly-receipt`. Sukces wymaga:

- `status=WTI_EIA_GAP_REVIEW_PASSED_READ_ONLY`;
- `staging_reference_rows=660`;
- `official_observations_in_window=695`;
- `matched_dates_and_prices=660`;
- `missing_source_dates_after_cutoff=35`, a wszystkie luki po 2026-08-25;
- `source_value_mismatches=0`, `locally_stored_dates_not_at_eia=0`;
- `database_connections=1`, `database_reads=1`, `database_writes=0`;
- `independent_point_in_time_market_data_certified=false`,
  `backfill_authorized=false`, `real_orders=0`,
  `schedule_enabled=false`.

Artefakt JSON jest agregatowy. Hashe bieżącego źródła / referencji poświadczają
**bajty przetworzone w bieżącym jobie**, nie ich dostępność we wcześniejszych
okresach.

## Status i kolejne decyzje

**PR przygotowuje mechanizm; nie jest dowodem rzeczywistego wykonania.**
Po przejściu CI i manualnego rzeczywistego przebiegu można uznać, że
potwierdzono bieżącą integralność istniejącej historii EIA–STAGING oraz
zamrożoną lukę WTI. Issue #22 może być wtedy zaktualizowane dowodem.

Nie zamykać automatycznie [Issue #22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22)
ani [Issue #2](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2):
35 braków nadal nie jest uzupełnionych, a historia autentycznych wczesnych
publikacji i rzetelny PIT pozostają niezweryfikowane. Każdy import i każdy
zapis STAGING wymagają osobnego uzgodnienia. M1/M2/M3: `HOLD_NO_CHANGE`.
