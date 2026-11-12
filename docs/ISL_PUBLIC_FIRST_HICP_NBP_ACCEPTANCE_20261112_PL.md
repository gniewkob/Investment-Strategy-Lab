# ISL Public-First v0.2 — HICP Eurostat + referencje NBP (2026-11-12)

**Powiązane:** [#144](https://github.com/gniewkob/Investment-Strategy-Lab/issues/144), [#142](https://github.com/gniewkob/Investment-Strategy-Lab/issues/142), PR #143.
**Koszt nowych źródeł:** 0 PLN; bez kont dostępowych. **Cel:** poprawna, nieinwestycyjna analiza inflacyjna danych badawczych.

## 1. Dokładna semantyka

- `scripts/public_first_nbp_reference_research_v01.py` — oficjalne [NBP API](https://api.nbp.pl/) (tabela A USD/PLN, EUR/PLN; cena 1 g złota PLN), wyłącznie ceny referencyjne. Ceny złota **nie** reprezentują funduszu ani indeksu total return; kurs średni waluty **nie** jest ceną transakcyjną.
- `scripts/eurostat_hicp_macro_context_v01.py` — [Eurostat `prc_hicp_minr`](https://ec.europa.eu/eurostat/databrowser/product/page/prc_hicp_minr), `geo=PL,freq=M,coicop18=TOTAL,unit=I25`: HICP Polski, **2025=100, ECOICOP ver.2**, najnowsza wersja z retrospektywnymi przeliczeniami. HICP jest indeksem cen konsumpcyjnych, nie zwrotem z aktywów.
- `scripts/public_first_hicp_nbp_purchasing_power_v01.py` łączy oba **istniejące, typowane adaptery** w odizolowanym raporcie; nie zmienia przyjmowania danych M1–M3 ani modelu decyzyjnego.

**Weryfikacja źródłowa z 12.11.2026:** oficjalne Eurostat API zwróciło 60 etykiet miesięcy (2021-11...2026-10), ale tylko **59 rzeczywiście opublikowanych poziomów** (ostatni 2026-09, wartość `104.27` wobec `76.54` w 2021-11); październik 2026 to brak danych (nie `0`). Datę aktualizacji raportuje jako `2026-11-04T11:00:00+0100`. Dlatego pierwsza spójna analiza ogranicza się do **2021-11 – 2026-09**: 59 miesięcy. Nie wyrównujemy braków przez użycie przyszłych miesięcy.

## 2. Matematyczna interpretacja

Każdy z 59 miesięcy zawiera **osobny, hipotetyczny nominał 100 PLN**, czyli **5 900 PLN łącznie dla każdego alternatywnego wariantu**.

Dla HICP `I_m`, ostatniej publikacji `I_T`, nominalnego scenariusza referencyjnego `V_T` i stałej hipotetycznej wpłaty `C=100`:
- `CPI_matched_cashflows_T = SUM_m(C * I_T / I_m)` — ile nominalnych PLN na koniec okresu ilustruje równoważną siłę nabywczą każdej miesięcznej hipotetycznej kwoty w miesiącu jej odniesienia. **To nie jest strategia ani inwestowalny instrument indeksowany do inflacji.**
- `CPI_reference_difference_T = V_T - CPI_matched_cashflows_T` — różnica dwóch wielkości modelowych w nominalnych PLN na koniec okresu. **Nie oznacza możliwego do zrealizowania zysku/straty ani pokonania inflacji przez faktycznie dostępny produkt.**
- `CPI_change_pct = 100*(I_T/I_0 - 1)` — zmiana bieżącego szeregu poziomów cen od pierwszego do ostatniego badanego miesiąca, na bazie 2025=100; **nie historyczna seria PIT**.

Scenariusze NBP dziedziczą dokładnie założenia #142: hipotetyczne, nieegzekwowalne jednostki referencyjne kupowane matematycznie po końcowych opublikowanych wartościach danego miesiąca. Warianty kosztów `0` i `30 bps` są stałymi założeniami badania, a nie bankowym spreadem ani opłatą. Kontekst kosztów realnej ekspozycji, podatki, realna dostępność ceny transakcyjnej, odsetki od gotówki i ewentualne koszty złota są **poza zakresem**.

## 3. Prawa źródłowe, jakość i warianty czasowe

- [Eurostat Copyright notice, „Free re-use of data” oraz „How to cite”](https://ec.europa.eu/eurostat/help/copyright-notice): publiczne dane Eurostatu można co do zasady ponownie wykorzystać z atrybucją i poszanowaniem wskazanych wyjątków (np. treści osób trzecich). Używamy wyłącznie oficjalnego otwartego datasetu statystycznego; przy raportowaniu: „Source: Eurostat, prc_hicp_minr; NBP, api.nbp.pl”.
- [Eurostat API guide, „general introduction”](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction): bezpłatny REST dostęp do najnowszej wersji danych i metadanych, nie komplet historycznych „as originally released”. Nie utrwalamy sztucznego `first_usable_at` dla miesięcy 2021–2025.
- Dane HICP 2021–2025 zostały później **przebazowane i przeklasyfikowane** przy przejściu na 2025=100/COICOP 2018; nawet prawdziwe poziomy z dzisiejszego API nie musiały być znane historycznie w tej samej formie.
- Powtarzalność matematyki: pierwotne NBP odpowiedzi mają SHA-256 każdej paczki, a Eurostat odpowiedź ma SHA-256 kanonicznego JSON-stat. Żadna suma nie dowodzi autentyczności oryginalnego stanu z 2021–2025.
- Brak pierwszej publikacji października 2026 => `INCOMPLETE_OR_WRONGLY_TYPED_HICP` (nie prezentujemy sześćdziesiątego fikcyjnego miesiąca). Daty z obu źródeł w każdym miesiącu nie muszą być równe (odrębne kalendarze publikacji).

## 4. Nienaruszalne granice

- `PUBLIC_MACRO_REFERENCE_CONTEXT_ONLY`, `historical_point_in_time_certified=false`, `qualified_model_series=[]`, `legacy_m1_m2_m3=NOT_RUN_UNQUALIFIED_TOTAL_RETURN_SERIES`.
- Żadnych transakcji, środków, płatności, portfela, private accounts, nowych licencji, kont, tokenów, sekretów, Neon DB, zleceń, zdarzeń paper-trading i produkcyjnych schedulerów.
- `--allow-public-source-fetch` wymaga jawnego opt-in do publicznego HTTPS. Funkcja `public_purchasing_power_research` działa domyślnie offline na dostarczonym oryginalnym JSON-stat i wstrzykniętej funkcji pobierania NBP.
- Testy offline odcinają ruch sieciowy i weryfikują typ kraju, waluty, `I25`, `TOTAL`, brak danych, nieciągłość, NaN i zgodność okresów. CI produkcyjnie nie zapisuje danych w bazie, harmonogramu ani do repo.
- Nie włączamy HICP jako `GOLD_TR_PLN`, `GLOBAL_EQUITY_TR_PLN`, `PL_BONDS_TR_PLN` ani sygnału transakcyjnego.

## 5. Odbiór

```sh
python -m unittest tests.test_public_first_hicp_nbp_purchasing_power_v01 -v
python -m scripts.public_first_hicp_nbp_purchasing_power_v01 \
  --since 2021-11 --until 2026-09 --allow-public-source-fetch
```

Warunki:
- [ ] 59/59 rzeczywistych poziomów Eurostat HICP PL TOTAL / I25 oraz 59/59 miesięcy NBP, bez interpolacji i pełne dowody SHA.
- [ ] 16/16 syntetycznych testów offline na Ubuntu i macOS; jeden rzeczywisty odczyt tylko z publicznych oryginalnych API.
- [ ] Pełne testy regresyjne repozytorium na dokładnym HEAD, GitGuardian, brak uwag review.
- [ ] PR #143 uprzednio przyjęty i scalony do `main`, następnie PR bieżący może być bazowany na `main`; po jego merge dokładny `main` regression PASS.
- [ ] Model M1–M3, prawa i źródła płatne pozostają odrębne; żadnych operacji finansowych.

**Uwaga implementacyjna:** Rozwój na gałęzi bazującej na HEAD PR #143 umożliwia wcześniejsze testy. Bieżący PR jest **stacked**: nie scalamy go przed przyjęciem PR #143 i potwierdzeniem nowej bazy.
