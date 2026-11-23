# ISL v0.2 — porównanie fikcyjnych portfeli wieloassetowych

## Kontrakt

`python3 -m scripts.paper_multi_asset_research_v02 --synthetic-demo --out-dir /tmp/isl-v02-synthetic`

Alternatywnie `--input <manifest.json>` z polami `source_class`, `currency`, `simulation_mode`, `monthly_contribution_pln`, `observations` i `strategies`. Dozwolone `source_class`: `SYNTHETIC` lub `UNVERIFIED_EXTERNAL`. Wymagane 36–60 kolejnych miesięcy, wyłącznie poziomy w PLN dla `ASSET_A`, `ASSET_B`, `ASSET_C`. Każda cena ma pole `available_month` nie późniejsze niż `month`. Dokładnie trzy warianty `SIM_M1`, `SIM_M2`, `SIM_M3`, wagi całkowite bps sumujące się do 10000. Symulacja dopuszcza części jednostek i koszty per zlecenie syntetyczne.

Do celów laboratoryjnych, a nie realnych M1/M2/M3. Poziom zamknięcia miesiąca i równoczesny fikcyjny zakup nie stanowią ceny wykonalnej transakcji. Nie certyfikuje PIT, wartości total return, ryzyka płynności, ani historycznej dostępności cen. Obsunięcie wyznaczono na skumulowanej miesięcznej stopie zwrotu przed kolejną wpłatą; nie jest obsunięciem salda, ani dowodem przyszłego ryzyka. Realne M1–M3 pozostają `INSUFFICIENT_DATA_HOLD_CASH`. Zero sieci, DB i realnych transakcji.

## Wynik demo syntetycznego 60 miesięcy (2021–2025)

| Strategia fikcyjna | Stan końcowy | Różnica vs gotówka | Koszty | Obsunięcie flow-adjusted |
|---|---:|---:|---:|---:|
| Gotówka bez odsetek | 6000,00 PLN | 0,00 PLN | 0,00 PLN | 0% |
| SIM_M1 (20/70/10) | 6769,32 PLN | +769,32 PLN | 21,00 PLN | 0,58% |
| SIM_M2 (50/30/20) | 7081,25 PLN | +1081,25 PLN | 21,00 PLN | 2,45% |
| SIM_M3 (80/10/10) | 7431,80 PLN | +1431,80 PLN | 21,00 PLN | 2,92% |

**To w całości wymyślony rynek, nie autentyczne wyniki papierowej strategii, nie rekomendacje alokacji.** Brak zastosowania POLSTR, TBSP, MF/NBP, NAV lub HICP jako cen transakcyjnych.

## Dowody lokalne

- `python3 -m unittest -q tests.test_paper_multi_asset_research_v02`: **10/10 PASS**.
- `python3 -m compileall -q scripts tests`: **PASS**.
- `python3 -m scripts.paper_multi_asset_research_v02 --synthetic-demo --out-dir /mnt/data/isl_v02_demo`: **PASS**, `input_sha256=424d67ece8e305b6e6524df936eaef2f55d040106db1c4724a63ba16421e39bd`.
- **Nie wykonano** pełnej regresji na repo SHA ani merge/deploy, ponieważ ten isolated sandbox nie ma połączenia sieciowego z GitHub.

## Następny etap

Dopasować do realnych, prawidłowo licencjonowanych serii instrumentów i kursów walut oraz weryfikowalnych dat publikacji. Nie przestawiać `model_admitted` lub `HOLD_CASH` na podstawie wyników na danych syntetycznych.