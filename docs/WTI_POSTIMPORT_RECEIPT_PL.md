# EIA WTI — odbiór stanu PO uzupełnieniu 35 cen (STAGING, SELECT ONLY)

## Dlaczego nowe narzędzie?

19.10.2026 wykonano jednorazowe, autoryzowane uzupełnienie 35 referencyjnych
notowań WTI do izolowanej tabeli `investment_lab.price_observations` w
STAGING. Liczba obserwacji wzrosła z 660 do **695**. Poprzedni
`scripts/eia_wti_staging_receipt.py` miał *celowo zamrożony* kontrakt
**660 istniejących + 35 braków**; jest teraz historycznym dowodem i nie
może oceniać aktualnego stanu. Jego kod/testy/artefakt audytu pozostają
nietknięte, aby zachować ślad zdarzenia.

Następca: `scripts/eia_wti_postimport_receipt.py`. W tym samym przebiegu:

1. `fetch_staging_history` na istniejącym, ograniczonym
   `isl_legacy_history_reader` wymaga sprawdzonego hosta, bazy, roli,
   certyfikatu TLS i `SET TRANSACTION READ ONLY`, sprawdza tabelaryczne
   ACL oraz zabrania odczytu portfeli i zapisów do bazy.
2. Kontroluje dokładnie **660 pierwotnych WTI** w zakresie 02.01.2024–25.08.2026.
   Ponownie oblicza niezależny SHA-256 z 660 par `date,price`, taki sam
   jak wcześniej raportowany przez SQL Neon:
   `2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8`.
3. Kontroluje dokładnie **35 dopisanych WTI** w zakresie 26.08–14.10.2026,
   z rzeczywistą datą zapisu 19.10.2026 (UTC); odrzuca antydatowanie
   `ingested_at`, brak/duplikat klucza lub przesunięcie obserwacji.
4. Buduje lokalnie tymczasowy plik CSV 0600, czyta go jednokrotnie
   rygorystycznym parserem i hashuje dokładnie te same bajty.
5. Pobiera oryginalny HTML z **dokładnego dopuszczonego oficjalnego HTTPS EIA**
   `https://www.eia.gov/dnav/pet/hist/RWTCd.htm` i hashuje realne bajty.
   Wymaga `Release Date 2026-10-15` (to przegląd historycznej edycji,
   **nie** zawsze najnowsza dostępna publikacja).
6. Porównuje daty i Decimal bez tolerancji: **695/695** identycznych
   obserwacji, **0** braków, **0** nadmiarowych i **0** zmian cen.
7. Zwraca wyłącznie JSON: agregaty, daty skrajne, SHA i czas rzeczywistego
   odczytu. Żadnych cen, treści źródła, ścieżek prywatnych, DSN lub haseł.
   Nie zapisuje żadnych rekordów DB i nie publikuje historii cen jako artifact.

## Ręczne uruchomienie

GitHub → Actions →
**Post-import WTI EIA and Neon STAGING 695-day receipt — MANUAL READ ONLY**
→ Run workflow → `main`.

Wykorzystuje tylko obecny sekret
`research-staging / NEON_HISTORICAL_READ_DATABASE_URL`. Żadne konta,
ACL, hasła, harmonogramy ani uprawnienia nie zmieniają się.

Bramka CI na `pull_request` uruchamia pełny zestaw testów **offline**,
bez czytania Neon i bez pobierania oficjalnej strony. Dopiero ręczny
`workflow_dispatch` na `main` uruchomi realną walidację i załączy
agregatowy `wti-eia-postimport-staging-readonly-receipt` (retencja 7 dni).

Zaliczenie w realnym przebiegu wymaga:
- `status=WTI_POSTIMPORT_EIA_STAGING_695_MATCH_READ_ONLY`;
- `staging_observations_in_window=695`,
  `official_observations_in_window=695`,
  `matching_dates_and_prices=695`;
- po **660** wcześniejszych i **35** późniejszych obserwacjach;
- oryginalny hash starej części `2014f2ca...`;
- `source_missing_from_reference=0`,
  `staging_dates_absent_from_official_source=0`, `price_mismatches=0`;
- odczyt przez wcześniej autoryzowany reader, `database_writes=0`;
- `versioned_market_documents_created=0`,
  `versioned_market_observations_created=0`,
  `independent_point_in_time_market_data_certified=false`.

Jeśli EIA wyda nowszą edycję, zmieni starą cenę lub otrzymamy inny
zakres, skrypt celowo zgłosi `FAILED` — nie wolno po cichu
przyjąć nowych danych jako potwierdzenia zamrożonego snapshotu.

## Oddzielna bramka P0: faktycznie wersjonowane źródła PIT

**Wciąż nie rozpoczęto pełnoprawnego importu PIT.** Obecny model
`price_observations` zapisuje tylko `observed_for` i realny
`ingested_at`, ale nie przechowuje wersji dokumentu EIA użytego
do pierwszego udostępnienia każdej ceny.

Aktualny snapshot EIA ma `Release Date` z dokładnością do DNIA,
a nie oryginalny `published_at` historycznego notowania.
`source_original_html_sha256` jednoznacznie identyfikuje **bieżącą
reprezentację**, ale nie pierwotną historyczną publikację danej ceny.
Pole `current_source_available_not_before_utc` to późniejsza
z dat: faktyczny `retrieved_at` lub dzień po dacie bieżącego wydania
strony EIA o 00:00 UTC. **Nie jest to historyczna data udostępnienia
pojedynczego notowania.**

Plan P0 #2, na podstawie istniejących już tabel:
- `source_documents`: oryginalny snapshot (bez fałszowania bajtów),
  `sha256_hex` rzeczywistej pobranej reprezentacji, `canonical_url`,
  `published_at` bieżącego wydania (precyzja DAY),
  `retrieved_at` rzeczywistego pobrania, jasna etykieta
  `CURRENT_SNAPSHOT_NOT_ORIGINAL_OBSERVATION_VINTAGE`.
- `price_observation_versions`: każda cena związana z `document_id`,
  wersja `revision_no`, realne `recorded_at`, brak antydatowania
  `available_at` (nie wcześniej niż fakt pobrania i konserwatywna
  granica dnia po wydaniu strony).
- Przy zmianie SHA przy identycznych cenach dokument może być nową wersją
  strony bez korekty ceny. Nie wolno automatycznie wnioskować o
  zmianie kwotowania z samego SHA.
- Do następnego, oddzielnie zatwierdzonego zapisu wersjonowanego
  potrzebne są atomowe testy idempotencji, korekt, izolowanego reader/writer,
  zachowania dokumentu źródłowego, ochrony przed `look-ahead`,
  oraz kontrola migracji i ACL na disposable bazie.
- Historyczny backtest PIT może uwzględniać wyłącznie dane, które
  faktycznie można było znać według wiarygodnego wówczas dostępnego
  dokumentu lub odbioru. Dzisiejszy odczyt historycznych cen nie
  wystarcza. Wciąż `MARKET_DATA_NOT_READY`.

M1/M2/M3 pozostają `HOLD_NO_CHANGE`, brak transakcji i automatycznych
alokacji. [Issue #2](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2)
pozostaje otwarte.
