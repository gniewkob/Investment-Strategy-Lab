# EIA STEO — pierwszy prawdziwy porównawczy test miesięcznych prognoz 20.10.2026

## Rezultat — realny publiczny źródłowy XLSX, nie syntetyczne fixture

**Dowód źródłowy:** [GitHub Actions #39425055719](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39425055719) SUCCESS po scaleniu [PR #42](https://github.com/gniewkob/Investment-Strategy-Lab/pull/42). Rzeczywisty oficjalny HTTPS do plików EIA `jan24_base.xlsx`, `jan25_base.xlsx`, `oct26_base.xlsx`; walidacja OOXML + struktury `2tab` + numerycznych wartości referencyjnych WTI/Brent; **nie zachowano surowych XLSX na GitHub**. 0 połączeń/zapisów do Neon; 0 transakcji; 0 zmian w portfelu.

**3 wydania**: jan24 (oficjalny release 2024-01-09), jan25 (2025-01-14), oct26 (2026-10-06). **Dwanaście sparowanych prognoz**: 2 wydania prognostyczne × 2 surowce × 3 horyzonty (1, 3, 6 miesięcy). Dla jan24 referencją jest jan25; dla jan25 referencją jest oct26. Są to pierwsze **wśród dostarczonych do eksperymentu** późniejsze wydania co najmniej 2 miesiące po zakończeniu okresu celu; NIE są to pierwsze możliwe późniejsze raporty z całego archiwum, finalne oficjalne notowania ani zlecenia.

| Instrument referencyjny | Horyzont | Liczba par | MAE prognozy EIA USD/bbl | MAE „poprzedni miesiąc bez zmian” USD/bbl |
| --- | ---: | ---: | ---: | ---: |
| WTI | 1 miesiąc | 2 | 0.86 | 3.38 |
| WTI | 3 miesiące | 2 | 6.16 | 10.01 |
| WTI | 6 miesięcy | 2 | 2.96 | 5.81 |
| Brent | 1 miesiąc | 2 | 0.52 | 3.72 |
| Brent | 3 miesiące | 2 | 5.90 | 9.02 |
| Brent | 6 miesięcy | 2 | 3.05 | 5.17 |

**Przykłady z rzeczywistych par:**
- WTI prognozowana w jan24 na luty 2024: EIA 78.50 USD/bbl, późniejsze jan25 raportuje 77.25 USD/bbl, bezwzględny błąd 1.25; naive z tego samego jan24 (grudzień 2023) ok. 71.90 USD/bbl, błąd 5.35.
- WTI prognozowana w jan25 na kwiecień 2025: EIA 71.00 USD/bbl, późniejsze oct26 raportuje 63.54 USD/bbl, bezwzględny błąd **7.46**; naive z jan25 ok. 70.12 USD/bbl, błąd **6.58** — pokazuje, że nie każda historyczna prognoza EIA przewyższa naiwną.

### Ograniczenia

- Przy zaledwie dwóch parach na każdy instrument/horyzont, mniejsze średnie MAE EIA **nie dowodzi statystycznie trwałej przewagi, predykcyjnego alpha ani przyszłych zysków**. Próbka jest mała i dobrana wyłącznie jako techniczny pilot.
- Pobrane dziś archiwalne XLSX mogą mieć korekty względem bajtów pierwotnie opublikowanych w latach 2024/2025. `historical_source_as_published_bytes_certified=false` i `original_observation_point_in_time_certified=false`; **nie wolno przypisać retroaktywnie dowodu PIT**.
- „Later edition reference” to referencyjna cena ujęta w późniejszym raporcie STEO. Test trafności prognoz EIA ≠ test inwestowalności, total-return, realnych lub symulowanych zleceń.
- W numerycznych cache XLSX wystąpiły ślady reprezentacji binarnej (np. `71.900000000000006`); należy traktować je jako artefakt zmiennoprzecinkowy arkusza i prezentować zgodnie z dokładnością publikacji USD/bbl, zachowując oryginalne bajty oraz SHA dla kontroli źródła.

## Następna racjonalna faza

Zamiast 3 tylko pilotażowych wydań przetworzyć **wszystkie 34 miesięczne archiwa EIA STEO Jan24–Oct26**, dla tych samych horyzontów i źródłowo parowanego naive. Raportować liczbę par, MAE według rocznika i horyzontu, pominięcia danych, definicję referencji i co najmniej jedną serię z gorszym wynikiem modelu EIA. Nadal będzie to historyczna rekonstrukcja, nie potwierdzona przewaga transakcyjna ani całkowicie niezależne PIT.

Powiązane: [wykryty rzeczywisty układ arkuszy STEO](STEO_REAL_PUBLIC_XLSX_PILOT_2026_10_20_PL.md), [metodologia](STEO_VINTAGE_FORECAST_ERRORS_RESEARCH_PL.md), [status lokalnego backupu](EIA_BACKUP_ACCEPTANCE_2026_10_20_PL.md).
