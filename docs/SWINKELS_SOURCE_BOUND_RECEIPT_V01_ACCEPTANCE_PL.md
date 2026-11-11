# Swinkels — odbiór statystyk oryginalnego źródła, v0.1

**Powiązane:** [Issue #123](https://github.com/gniewkob/Investment-Strategy-Lab/issues/123), [PR #139](https://github.com/gniewkob/Investment-Strategy-Lab/pull/139).

## Zakres akceptacji

Consumer `scripts/swinkels_source_bound_stats_v01.py` nie dopuszcza arbitralnych danych z podanym przez użytkownika opisem metodologii. Wczytuje wyłącznie źródłowy ODS z oficjalnego DataverseNL i przed wydaniem zagregowanego raportu sprawdza pełną zgodność oryginalnych bajtów, liczby obserwacji i niezależnego odtworzenia obliczeń.

| Wymiar | Kryterium |
| --- | --- |
| Wydawca | Oficjalny DataverseNL, DOI [10.34894/YWT2IX](https://doi.org/10.34894/YWT2IX), plik ID `512630` |
| Integralność | 913425 bajtów, SHA-256 `90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847` |
| Zakres | Dokładnie 10 wariantów, po 36 miesięcy 2020-01–2022-12; 360 obserwacji |
| Metodologia | Osobne niezależne wyliczenie równania (3) dla Original US; niezależne PV i cash-flow dla pozostałych 9 wariantów |
| Wyjście | Zagregowane historyczne statystyki edukacyjne, źródłowy SHA, nazwa wariantu i status modelu |
| Odrzucenie | Nieprawidłowy SHA, brakujący miesiąc lub wariant, błędna matematyka, fałszywy PIT albo flaga operacji finansowej |
| Ciągłość | Pełna regresja repozytorium i odizolowane negatywne testy Ubuntu/macOS, osobny prawdziwy odczyt oryginału |

## Granice dowodów

- Dane są **szacowanymi zwrotami obligacji skarbowych z dziewięciu rynków**, a nie polskimi cenami inwestowalnych instrumentów, nie obejmują 2023–2026, nie są wynikami inwestora.
- Licencja źródłowa **CC BY 4.0** wymaga prawidłowego oznaczenia autora; samo posiadanie pliku nie certyfikuje historycznych dat dostępności obserwacji.
- Powiązanie rekordu Erasmus **v6 DOI 10.25397/eur.8152748.v6** z późniejszym DataverseNL nie dowodzi jeszcze równości oryginalnych bajtów ani tożsamości każdej wersji. Nie oznaczać tego pola jako verified bez dodatkowego śladu publikacji.
- Nie przekształcać tego źródła w `PL_BONDS_TR_PLN`, `GLOBAL_EQUITY_TR_PLN` czy `GOLD_TR_PLN`. `historical_point_in_time_certified=false`, `qualified_model_series=[]`, `M1–M3=INSUFFICIENT_DATA/HOLD_CASH`, `financial_operations=0`.

## Odbiór PR i incydent kolejki CI

Odbiór wymaga **zakończonych** testów na dokładnym SHA PR, przeglądu kodu oraz regresji aktualnego `main` po merge. Zarejestrowanie workflow jako `queued` bez jobów **nie oznacza PASS** i nie upoważnia do merge.

Gdy starsze workflow pozostają w takim stanie po incydencie Actions, nowy commit może uruchomić świeże kontrole. Nie wyłączać path filtrów, nie usuwać testów, nie zmieniać zasad fail-closed ani nie wykorzystywać wcześniejszego zielonego SHA jako dowodu dla nowej zmiany.

## Źródła pierwotne

- [Erasmus University Rotterdam: Historical Data — International monthly government bond returns](https://pure.eur.nl/en/datasets/historical-data-international-monthly-government-bond-returns/)
- [Swinkels, Treasury Bond Return Data Starting in 1962, Data 2019, §2–3](https://doi.org/10.3390/data4030091)
- [DataverseNL, oficjalny DOI pakietu](https://doi.org/10.34894/YWT2IX)
