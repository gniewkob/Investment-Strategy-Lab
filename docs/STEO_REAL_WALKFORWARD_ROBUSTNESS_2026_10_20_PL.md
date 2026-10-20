# STEO — rzeczywista walidacja chronologiczna i rewizje referencji, 20.10.2026

## Potwierdzone wykonanie na oficjalnych danych EIA

[GitHub Actions #39428981358](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39428981358) — **SUCCESS**, po [PR #44](https://github.com/gniewkob/Investment-Strategy-Lab/pull/44) (`30867061830e00f1a62ebb8cdf05fe3a8d4ad18e`). Nowy `scripts/steo_robustness_audit.py` działał na **wszystkich 34/34 prawdziwych archiwalnych plikach XLSX EIA STEO** dla okresu styczeń 2024 – październik 2026; `172` prawdziwe porównania miesięcznych prognoz WTI i Brent. Wszystkie źródła odczytane przez oficjalny HTTPS i ponownie sprawdzone identyfikatorami/SHA.

**Kontrola powtarzalności:** SHA-256 **34/34 oryginalnych bajtów XLSX** w nowym przebiegu zgadza się z 34 wartościami z [pierwszego kompletnego raportu](STEO_FULL_34_REAL_RESULTS_2026_10_20_PL.md). Potwierdza to spójność między dwoma pobraniami z 20.10.2026, **NIE** identyczność bajtów względem lat 2024–2026 w chwili pierwszej publikacji.

**Kod/CI:** [PR #44](https://github.com/gniewkob/Investment-Strategy-Lab/pull/44) merged; [PR CI #39428811876](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39428811876) **269/269 synthetic offline PASS** i **3/3 disposable PostgreSQL PASS**; [main CI #39428981122](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39428981122) PASS. Real-source runner report `STEO_34_EDITION_WALKFORWARD_AND_REVISION_ROBUSTNESS_REAL_SOURCE_PASS`.

## A. Reguła wyboru metody, nigdy bez wyników znanych przed datą prognozy

Założenie: wybór `EIA_STEO` lub `NAIVE_LAST_MONTH` osobno dla instrumentu × horyzont; co najmniej **6 dojrzałych ocen z wcześniejszych raportów**, których oficjalny dzień publikacji był **ściśle wcześniej** niż data ocenianej historycznej prognozy. Inaczej brak decyzji/oceny. Wykonano **104 z 172** porównań spełniających próg, rozdzielonych w 6 grupach.

MAE USD/baryłkę na *identycznych kwalifikujących się obserwacjach*:

| Surowiec | Horyzont mies. | Ocen | Dynamiczny MAE | Zawsze EIA MAE | Zawsze naiwny MAE | Wybór EIA / naiwny | Zakres wydań kwalifikujących się |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| WTI | 1 | 22 | 7,10 | 7,10 | 8,31 | 22 / 0 | oct24–jul26 |
| WTI | 3 | 18 | 12,46 | 13,53 | 12,33 | 10 / 8 | dec24–may26 |
| WTI | 6 | 12 | 17,48 | 23,21 | 17,48 | 0 / 12 | mar25–feb26 |
| Brent | 1 | 22 | 9,20 | 8,79 | 9,81 | 20 / 2 | oct24–jul26 |
| Brent | 3 | 18 | 14,09 | 15,25 | 14,09 | 0 / 18 | dec24–may26 |
| Brent | 6 | 12 | 18,45 | 25,60 | 18,45 | 0 / 12 | mar25–feb26 |

**Podsumowanie:** 0/6 grup dynamicznych miało niższy MAE niż obie metody stosowane zawsze; **2/6** grup dynamicznych miało wyższy MAE niż niższy z dwóch statycznych wyników (Brent +1 miesiąc i WTI +3 miesiące); w pozostałych 4/6 wynik dynamiczny dorównał niższemu MAE jednej metody statycznej. Dynamiczny wybór **nie dowiódł dodatkowej przewagi** w tej retrospektywnej próbie, a wybór najlepszej stałej metody *po fakcie* również nie jest uczciwą decyzją ex ante.

**Nakładanie się obserwacji:** `172` pary to **62 unikalne kombinacje instrument–miesiąc docelowy**, 58 kombinacji jest obecnych w kilku horyzontach. Zatem nie wolno traktować 172 jako niezależnych próbek; model nie uczy się pomiędzy horyzontami. `no_future_labels_used_in_rule_selection=true` sprawdzone dla wszystkich grup.

## B. Późniejsze rewizje ceny referencyjnej tego samego miesiąca

`reference_revision_audit` porównuje historyczną miesięczną referencję z pierwszego kwalifikującego się późniejszego wydania (co najmniej 2 miesiące po celu) z **najpóźniejszym kwalifikującym się wydaniem w tych samych 34 źródłach**. To test zależności wyniku od wybranej późniejszej referencji. **Nie** certyfikuje ostatecznej, dostępnej do handlu ceny.

| Surowiec | Horyzont mies. | Par | Ponownie porównywalnych | Zmienionych par | Max zmiana USD/bbl | EIA MAE pierwsza → ostatnia | Naiwny MAE pierwsza → ostatnia |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| WTI | 1 | 31 | 30 | 1 | 0,10 | 6,44 → 6,44 | 7,46 → 7,46 |
| WTI | 3 | 29 | 28 | 1 | 0,10 | 10,87 → 10,87 | 10,18 → 10,17 |
| WTI | 6 | 26 | 25 | 0 | 0,00 | 15,53 → 15,53 | 12,21 → 12,21 |
| Brent | 1 | 31 | 30 | 0 | 0,00 | 7,76 → 7,76 | 8,58 → 8,58 |
| Brent | 3 | 29 | 28 | 0 | 0,00 | 12,21 → 12,21 | 10,89 → 10,89 |
| Brent | 6 | 26 | 25 | 0 | 0,00 | 16,99 → 16,99 | 12,56 → 12,56 |

W Brent w grupach horyzontów nie odnotowano zmian porównywalnej referencji. W WTI odnotowano **po 1 zmienionej parze** dla horyzontu +1 i +3, o maksymalnie **0,10 USD/bbl**. **Agregaty nie identyfikują miesiąca docelowego tych zmian: nie twierdzić, że to na pewno jeden unikalny miesiąc lub dwie niezależne rewizje.** Inne źródła/edycje poza tym zbiorem i późniejsze aktualizacje mogą dać inne wyniki.

## Istotne ograniczenia

**Historyczne oryginalne bajty w dniu pierwszej publikacji EIA nadal PIT-NIEPOTWIERDZONE.** Porządkujemy źródła według oficjalnych `Release Date`, lecz wydania XLSX pobrane 20 października 2026 mogły być redagowane od dawnych dat. Brak niezależnego archiwum/digestu oryginalnych bajtów z tamtych dni; tzw. walk-forward to **chronologiczna rekonstrukcja badawcza**, a nie audyt informacji naprawdę znanej każdemu hipotetycznemu inwestorowi. Źródłowe historyczne wartości WTI/Brent to **miesięczna cena spot USD/baryłkę**, nie instrument total return w PLN ani realny/cyfrowy obrót aktywami; MAE nie jest zyskiem.

**Zakres operacji:** 0 połączeń/zapisów Neon, 0 realnych zleceń, 0 zmian alokacji wirtualnych M1/M2/M3, 0 sekretów/uprawnień/harmonogramów, oryginalne XLSX jedynie efemerycznie w pamięci runnera, 0 publikowanych surowych plików. Potwierdzony backup poprzedniego archiwum EIA MyDevil/Mac pozostaje **CLOSED**.

## Dalszy priorytet

Oprzeć nowy badawczy benchmark na **dopuszczalnych as-of prognozach dla wyraźnie rozdzielonych okresów**, porównać stabilność sygnałów w innych seriach i niezależnie zweryfikowanych dokumentach archiwalnych; nie włączać automatycznej realokacji na podstawie porównywania publicznych cen spot. Dla tych modeli wynik `DESCRIPTIVE_ONLY_NO_PORTFOLIO_ACTION`.
