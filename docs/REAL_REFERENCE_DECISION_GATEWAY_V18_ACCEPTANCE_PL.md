# Investment Strategy Lab — v0.18: realne źródła do silnika, bez fikcyjnego TOTAL_RETURN

**Data:** 2026-11-07. **Cel:** egzekwować zatwierdzone kryterium odbioru rzeczywistych danych (B) i prospektywnej ewaluacji (C) równolegle z technicznym rozwojem M1–M3. Priorytet: działająca funkcjonalność, bez dodatkowej rozbudowy offsite DR.

## Rzeczywisty przepływ

`scripts/real_reference_gateway_v18.py` przyjmuje zapisany artefakt `nbp-tbsp-exact-day-reference-v04.json` z [read-only workflow #42255251036](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42255251036). Uruchamia niezależny parser źródła `from_reference_archive` z v0.5 (sprawdzający hash wejściowego archiwum, 60 miesięcy i dopasowanie dni), a następnie rzeczywisty `run_cycle` z v0.16. Wymaga jawnego czasu UTC późniejszego niż ostatni ukończony miesiąc, nie fałszuje dat publikacji.

**Wymagany wynik:**
`REFERENCE_DATA_OBSERVED_MODELS_BLOCKED`, 60 miesięcy 2021-11–2026-10, trzy realne rodziny referencji, **zero** kwalifikowanych serii wymaganych dla modeli i wszystkie M1/M2/M3 w `HOLD_CASH`, zero operacji finansowych. Deterministyczny `gateway_receipt_sha256` identyfikuje wynik konkretnego przebiegu przy danym `as_of_utc`.

Nowy krok w `.github/workflows/shadow-source-receipt-v05.yml` pobiera ten **rzeczywisty** artefakt z GitHub Actions, wywołuje gateway i sprawdza wynik. `working-engine-v01-ci.yml` uruchamia również testy offline bramek v0.18. Kod nie ma dostępu do brokera, portfeli ani bazy.

**Ważne:** zgodność hashów utrwalonych artefaktów nie oznacza odrębnej certyfikacji oryginalnych bajtów u każdego dostawcy, pozwolenia licencyjnego, historycznego czasu publikacji PIT, niezmienności serii ani możliwości osiągnięcia indeksowych wyników w faktycznych transakcjach.

## Klasyfikacja rzeczywiście dostępnych wejść

| Rodzina | Dostępny zakres | Podstawa | Rola w silniku |
|---|---|---|---|
| NBP USDPLN | 60 miesięcy oficjalnych obserwacji w zachowanym archiwum | FX_RATE | Referencja FX, **nie** GLOBAL_EQUITY_TR_PLN |
| NBP cena złota | 60 miesięcy oficjalnych obserwacji | PRICE_ONLY PLN/g | Referencja ceny, **nie** GOLD_TR_PLN |
| BondSpot TBSP.Index | 60 miesięcy oficjalnego archiwum | indeks obligacji total return, niepapier wartościowy | Obserwacja benchmarku, **nie** cena wykonalnego zlecenia; bez certyfikowanego historycznego PIT nie podmieniamy PL_BONDS_TR_PLN |

Oficjalny BondSpot opisuje TBSP.Index jako indeks uwzględniający ceny obligacji, narosłe odsetki i reinwestowanie kuponów: https://www.bondspot.pl/pressroom?ph_main_content_1_cmn_id=1309&ph_main_content_1_start=show.

## Nowy kandydat na serię equity: MSCI ACWI net return

Pojawiło się lepsze rozróżnienie między faktycznym **indeksem net total return** a funduszowym NAV. Oficjalna strona MSCI ACWI opisuje indeks globalny i publikuje wyniki w wariancie **Net** oraz walucie USD: https://www.msci.com/indexes/index/892400/msci-acwi-index. CFA Institute udostępnia swoim członkom dostęp do historycznych zbiorów MSCI z końcem miesiąca i wariantami PR/GRTR/NETR, ale wymaga logowania i stosuje warunki licencyjne: https://rpc.cfainstitute.org/msci. Sam fakt dostępności strony albo rocznej stopy zwrotu **nie jest** 36–60 miesiącami poziomów indeksu z certyfikowanym czasem publikacji.

**Następna weryfikacja:** ustalić czy dozwolony eksport konkretnej serii MSCI ACWI NETR posiada nieprzerwany zakres miesiąc po miesiącu, zgodną licencję oraz historycznie dopasowane oficjalne FX USDPLN. Ustalić też, czy bez ryzyka błędnej definicji można utworzyć osobny, jawnie **niewykonalny** benchmark PLN; nigdy nie mylić go z cenami giełdowymi funduszu. Nie uruchamiać handlu ani nie deklarować pełnej kwalifikacji na podstawie potencjalnego źródła.

## Status kryteriów odbioru właściciela

- **A — silnik i deterministyczna ewaluacja:** TECHNICAL PASS dla v0.16–v0.17 po zielonym CI.
- **B — kwalifikowane rzeczywiste serie:** BLOCKED. v0.18 udowadnia realne źródło *referencyjne*, ale **nie** trzy potrzebne serie modelowe.
- **C — kolejne prawdziwe niezależne obserwacje OOS:** BLOCKED. Samo 60-miesięczne archiwum wsteczne i testy na sztucznych poziomach nie mogą udawać prospektywnej ewaluacji.
- **D — izolacja badawcza:** `orders_sent=0`, `paper_fills=0`, `database_writes=0` i żadnych zmian w działających harmonogramach.

**Kolejny etap:** dostępny i dozwolony rzeczywisty miesięczny indeks globalny NETR → datowany kurs FX → sprawdzony manifest; włączyć go do tego samego kontrolera jako *jedną* kwalifikowaną rodzinę tylko po realnym audycie. M2/M3 pozostają HOLD, jeśli inne rodziny są niekompletne. Kontynuować późniejsze zamrażanie i weryfikację decyzji.
