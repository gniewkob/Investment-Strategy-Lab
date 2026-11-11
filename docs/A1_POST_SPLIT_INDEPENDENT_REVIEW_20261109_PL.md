# A1 — niezależny przegląd poprawności i izolacji testów (2026-11-09)

**Zakres:** [Draft PR #98](https://github.com/gniewkob/Investment-Strategy-Lab/pull/98), wyłącznie research-only, bez merge, bez transakcji, bez połączenia z Neon, Coinbase lub dostawcą rynkowym.

## 1. Ustalona luka — destructive disposable PostgreSQL test

Pierwotny test integracyjny w `tests/integration/test_monthly_backtest_v04_readiness.py` akceptował każdą bazę o adresie `localhost` (w tym potencjalny SSH/port-forward), a w `setUp` bezwarunkowo wykonywał `DROP SCHEMA IF EXISTS investment_lab CASCADE`. Zbieżność nazwy schematu z prywatnym LAB zwiększała ciężar pomyłki. **Sama lokalność hosta nie zapewnia disposable isolation.**

Zmiany:
- Dedykowana CI baza `isl_v04_disposable`, użytkownik `isl_v04_ci`; test wymaga jednocześnie zgodności hostname, dokładnej nazwy bazy oraz użytkownika **przed pierwszą operacją na schemacie**. Połączenie do `investment_lab` na `localhost` jest odrzucane.
- Test **nie wykonuje DROP w setUp**. Jeśli schemat `investment_lab` istnieje, test odrzuca taki stan zamiast go usuwać. Tworzy schemat dopiero po sprawdzeniu braku konfliktu.
- `tearDown` usuwa tylko schemat utworzony przez dany przypadek testowy. Jeśli proces przerwie się przed sprzątaniem, następny przebieg powinien zatrzymać się na `pre-existing schema`, a nie usuwać go automatycznie.
- CI preflight niezależnie sprawdza `current_database()`, `current_user` i brak wcześniejszego schematu, zanim uruchomi integrację. Dane uwierzytelniające są wyłącznie syntetyczne, lokalne dla kontenera usługowego.
- Regresje: próba skierowania testów do bazy LAB przez localhost, zdalny host, zła rola, prawidłowy dokładny target oraz drugi fixture wobec istniejącego schematu.

**Ograniczenie:** kontrola nazwy/użytkownika/localhost nie dowodzi matematycznie pochodzenia fizycznego serwera. Łączne zastosowanie osobnego kontenera CI, dokładnych parametrów bazy oraz odmowy kasowania istniejącego schematu zdecydowanie zmniejsza skutki pomyłki. Docelowo test pozostaje ograniczony do dedykowanego joba CI.

## 2. Niezależna kontrola rachunkowości M1–M3

Nowy `tests/test_a1_independent_accounting_review_v01.py` sprawdza bez modyfikowania źródłowego silnika:
1. Płaskie poziomy indeksów + zerowe koszty = brak fikcyjnych zysków i strat dla wszystkich trzech modeli.
2. M1 z zerowymi kosztami: flow-adjusted TWR odpowiada relacji poziomów indeksu, a nie prostemu ROI opartemu na sumie wpłat.
3. Złożenie TWR train/test odpowiada TWR całego szeregu w tolerancji wynikającej z zaokrąglania raportu.
4. Płaskie indeksy + dodatnie koszty: ujemny wynik portfela odpowiada hipotetycznym opłatom/slippage, a nie ruchowi rynku.
5. Podmiana ostatniego znanego poziomu globalnych akcji nie zmienia wcześniej obliczonych ścieżek portfeli.

To są **syntetyczne kontrole arytmetyki**, a nie walidacja źródeł, point-in-time danych, możliwych cen transakcyjnych, przewagi M3 ani przyszłych stóp zwrotu.

## 3. Reconciliacja względem monolitu PR #96

Historyczna informacja o ośmiu identycznych Git blobach odzwierciedla stan **pierwotnego rozdzielenia**. Po tej poprawce oryginalny plik `tests/integration/test_monthly_backtest_v04_readiness.py` został **celowo zmodyfikowany tylko w A1**. Pozostałe 7/8 przeniesionych oryginalnych plików pozostaje niezmienione; dodatkowy skrypt testowy, workflow CI i niniejszy dokument stanowią nowy zakres przeglądu. Nie przepisano surowych źródeł danych, zamrożonych NAV/FX SHA ani kodu modelu.

Przed scaleniem należy niezależnie przejrzeć tę zmianę i ponownie zweryfikować aktualny graf zależności oraz overlap #96/#98. **Brak automatycznego merge, zmiany schedulerów lub aktywacji rynku.**

## 4. Stan odbioru

Decyzja pozostaje `A1_DRAFT_REVIEW_REQUIRED`. Rzeczywiste wyniki nowego CI należy powiązać z **końcowym** SHA gałęzi, nie ze starszym pozytywnym przebiegiem. Nawet PASS nie zamienia hipotetycznego benchmarku w wykonywalną strategię inwestycyjną.
