# Investment Strategy Lab v0.4 — odbiór historii NAV Vanguard

**Stan 6.11.2026: importer i regresja PASS; rzeczywisty pełny eksport NAV nadal BLOCKED; historyczny backtest M1/M2/M3 NOT_RUN.**

## Jedyna brakująca czynność zewnętrzna

Potrzebny jest oryginalny historyczny eksport NAV funduszu
**Vanguard FTSE All-World UCITS ETF (USD) Accumulating,
ISIN IE00BK5BQT80**, optymalnie z pełnymi miesiącami
2021-11 do 2026-10 (60 miesięcy). Wymagamy kolumny NAV
w USD, nie giełdowej ceny rynkowej w EUR lub GBP.

Oficjalna [strona Vanguard dla inwestorów indywidualnych w Polsce](https://www.pl.vanguard/inwestorzy-indywidualni/produkt/etf/akcje/9679/ftse-all-world-ucits-etf-usd-accumulating) może wymagać osobistego potwierdzenia miejsca zamieszkania i zasad dostępu. **Automatyzacja nie składa ani nie obchodzi oświadczeń.** Jeśli dostęp nie jest dozwolony, użyć innego odpowiednio licencjonowanego źródła albo przerwać. Nie zmieniać ręcznie kolumn ani historycznych cen, nie przepisywać wykresu.

Oryginalny plik **nie jest jeszcze dostępny** w repozytorium. Aktualny parser XLSX ma format przetestowany tylko na danych syntetycznych. Jeżeli prawdziwy eksport ma inny układ (albo jest CSV), moduł bezpiecznie zatrzyma pracę do czasu dostosowania do rzeczywistej struktury.

## Gotowe polecenie Mac — pierwszy odczyt bez dodatkowych kursów

~~~bash
cd ~/Repos/Investment-Strategy-Lab
git fetch origin codex/v04-monthly-backtest-engine-20261106
git switch codex/v04-monthly-backtest-engine-20261106
git pull --ff-only

bash scripts/run_local_vanguard_nav_preflight_v04.sh \
  "$HOME/Downloads/ORYGINALNY_PLIK_VANGUARD.xlsx"
~~~

Skrypt:
1. Tworzy prywatny katalog poza Git: w katalogu Library/Application Support/InvestmentStrategyLab/NavResearch użytkownika; uprawnienia 0700, nowe pliki z umask 077.
2. Pobiera zweryfikowane 60-miesięczne archiwum NBP z [GitHub Actions #42228167332](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42228167332). Jeśli czasowy artefakt wygasł, korzysta z oficjalnego publicznego NBP API i zapisuje nową datę oraz hash pobrania.
3. Sprawdza oryginalny XLSX (OOXML, daty, NAV USD, 36–72 kolejnych zakończonych miesięcy, duplikaty, formuły, makra, daty z przyszłości i SHA-256 bajtów).
4. Weryfikuje receipt NBP i wskazuje daty wymagające kursu z dokładnego dnia NAV.

Zapisuje prywatny **vanguard-nav-pln-candidate.json**. Oryginalny XLSX nie jest kopiowany do repozytorium ani przesyłany do Neon.

## Opcjonalny drugi przebieg — rzeczywiste kursy NBP z dat NAV

~~~bash
bash scripts/run_local_vanguard_nav_preflight_v04.sh \
  "$HOME/Downloads/ORYGINALNY_PLIK_VANGUARD.xlsx" \
  --fetch-exact-nbp
~~~

Dodatkowy wariant wykonuje tylko potrzebne zapytania publicznego NBP API o kurs USD/PLN w **dokładnym dniu** NAV. Rejestruje oficjalny URL, SHA-256 surowych odpowiedzi oraz moment pobrania. Jeśli w danym dniu brak publikacji kursu, **kończy pracę błędem** — nie stosuje interpolacji, wartości z późniejszego dnia ani sztucznego forward-fill.

## Interpretacja odbioru

| Kod rezultatu | Znaczenie |
|---|---|
| BLOCKED_NEEDS_EXACT_DAY_NBP_FX | Brak kursów NBP z dokładnych dat NAV, brak pełnej wyceny PLN |
| CANDIDATE_NAV_PLN_REFERENCE_READY_FOR_SOURCE_REVIEW | Arytmetyka NAV USD × NBP USDPLN jest kompletna, ale wymaga niezależnego potwierdzenia oryginalnego pochodzenia |
| InvalidVanguardXLSX | Prawdziwy plik ma inny lub nieobsługiwany układ, brakuje miesięcy albo naruszono kontrolę danych |
| Błąd API 404/429 | Brak wiarygodnej referencji źródłowej, nie powstał wynik zastępczy |
| NOT_RUN_PENDING_ORIGINAL_NAV_PROVENANCE | Realny historyczny backtest M1/M2/M3 nadal nie jest uruchomiony |

**NAV nie jest automatycznie ceną handlową ETF**. Nawet dopasowane 60 miesięcy nie certyfikuje historycznej godziny pierwszej publikacji danych ani wykonalności transakcji po NAV. Matematyczny szereg referencyjny pozostaje odrębny od GLOBAL_EQUITY_TR_PLN i pozostałych inwestowalnych instrumentów.

## Wykonany odbiór techniczny

- Kod XLSX: scripts/vanguard_xlsx_offline_intake_v04.py
- Kompletne przygotowanie NAV+NBP: scripts/vanguard_nav_intake_bundle_v04.py
- Polecenie Mac: scripts/run_local_vanguard_nav_preflight_v04.sh
- Regresja: tests/test_vanguard_nav_intake_bundle_v04.py
- [CI #42270893919](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42270893919): **135/135 PASS**. Testy źródłowe NAV w tej iteracji wykorzystują tylko jawnie syntetyczne XLSX.

Oryginalnego pliku dostawcy **nie commitujemy**, nie umieszczamy w publicznym repozytorium i nie przekazujemy autonomicznym automatyzacjom. Działający v0.3, harmonogram, Neon main, aktywa i portfele pozostają bez zmian. Operacje finansowe: **0**.
