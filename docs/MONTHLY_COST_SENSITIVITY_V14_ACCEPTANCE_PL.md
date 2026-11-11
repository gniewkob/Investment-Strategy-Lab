# Investment Strategy Lab — v0.14: wrażliwość M1–M3 na koszt hipotetyczny

**Cel:** zbadać, na ile wynik matematycznego benchmark-proxy zależy od arbitralnego założenia prowizji oraz poślizgu. To jest badanie założeń, **nie** porównanie rzeczywistych portfeli, nie rekomendacja transakcyjna i nie sposób ominięcia brakujących źródeł.

## Implementacja i kontrakt

Pliki: `scripts/monthly_cost_sensitivity_v14.py` i `tests/test_monthly_cost_sensitivity_v14.py`.

Narzędzie jest cienką, deterministyczną warstwą na istniejącym `run_backtest` z v0.4. Uruchamia dokładnie cztery predeklarowane założenia:

| Scenariusz | Prowizja (bps) | Poślizg (bps) |
|---|---:|---:|
| ZERO | 0 | 0 |
| BASE_20_10 | 20 | 10 |
| HIGH_50_50 | 50 | 50 |
| STRESS_100_100 | 100 | 100 |

Liczby są scenariuszami badawczymi, **nie** pomiarem rzeczywistych opłat Coinbase, ETF ani spreadów. Każdy scenariusz używa tych samych danych i tych samych z góry określonych modeli M1/M2/M3, zmieniając wyłącznie koszt. Raport zawiera wartość referencyjną końcową, hipotetyczny wynik nominalny, TWR, drawdown, wynik warunkowego OOS i różnicę wartości między zerowymi kosztami a scenariuszem stresowym. Wartość `zero_cost_minus_stress_reference_pln` jest miarą wrażliwości referencyjnej, **nie przewidywaną stratą inwestora**.

## Bramka danych jest nadrzędna

Narzędzie **najpierw** uruchamia pełną walidację oryginalnego manifestu i nie przepisuje nieprawidłowych kosztów wejściowych w celu uzyskania sztucznego PASS. W każdym z czterech wariantów musi zachować wynik bazowego source gate.

- `NOT_RUN_INSUFFICIENT_DATA` lub `NOT_RUN_INSUFFICIENT_HISTORY`: status wyjściowy `NOT_RUN_SOURCE_OR_HISTORY_BLOCKED`, tablice wyników modeli puste, bez ROI/TWR.
- `SYNTHETIC_TEST_ONLY`: wyjściowy `SENSITIVITY_SYNTHETIC_TEST_ONLY`; weryfikuje tylko poprawność mechaniki.
- `CONDITIONAL_HISTORICAL_RECONSTRUCTION`: wyjściowy `SENSITIVITY_CONDITIONAL_HISTORICAL_RECONSTRUCTION`; pozostaje bez niezależnej certyfikacji dat źródeł (PIT).
- Zawsze: `real_orders=0`, `paper_events_created=0`, `database_connections=0`, `database_writes=0`, `historical_pit_certified=false`, `investment_performance_proven=false` i `statistical_edge_proven=false`.

Źródła GOLD NBP `PRICE_ONLY` ani obligacyjny TBSP `NON_TRADABLE_INDEX` **nie są** automatycznie przemianowywane na wymagane `GOLD_TR_PLN` lub `PL_BONDS_TR_PLN`. Brak globalnego equity TR pozostaje głównym powodem `NOT_RUN`.

## Uruchomienie lokalne, bez Neon i połączeń sieciowych

```bash
cd "$HOME/Repos/Investment-Strategy-Lab-shadow-v12"
python3 -m unittest discover -s tests -p 'test_monthly_cost_sensitivity_v14.py' -v

# Tylko gdy istnieje własny jawnie oznaczony manifest v0.4:
python3 -m scripts.monthly_cost_sensitivity_v14 --input /path/to/research-manifest.json
```

Nie jest konieczne kopiowanie żadnych danych konta, kluczy ani credentiali.

## Odbiór i następny krok

Kontrole CI: `Working Engine v0.1 E2E`, dodatkowo dotychczasowe niezależne workflow źródeł. Wymagane PASS testów v0.14 oraz reszty regresji. Nie należy podawać liczb z `fixture()` jako zaobserwowanej rentowności.

**Dalszy zakres równoległy:** automatycznie i legalnie pozyskać oryginalne długie szeregi globalnego equity oraz polskich obligacji i jednoznacznie zdefiniować ekspozycję na złoto. Następnie oddzielnie udokumentować datę udostępnienia, zmianę definicji, surowy SHA-256, rodzaj ceny i ewentualne źródło całkowitej stopy zwrotu. Dopiero przy spełnieniu pełnego kontraktu można wykonać **warunkową**, niecertyfikowaną rekonstrukcję historyczną. Ponowne gromadzenie niezależnych prospektywnych obserwacji OOS jest osobnym wymaganiem.

**Etap offsite DR pozostaje LOW/BACKLOG** zgodnie z decyzją właściciela; działające lokalne zabezpieczenie v0.13 nie jest modyfikowane.
