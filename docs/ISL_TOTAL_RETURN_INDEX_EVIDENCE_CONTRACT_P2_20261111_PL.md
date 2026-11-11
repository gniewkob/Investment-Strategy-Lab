# ISL — kontrakt źródeł TOTAL_RETURN_INDEX, P2 (11.11.2026)

**Decyzja:** `STRUCTURAL_SOURCE_EVIDENCE_PREFLIGHT_PASS` możliwy wyłącznie dla syntetycznej próbki spełniającej reguły. **Nie** oznacza `PIT_VERIFIED`, autentyczności wydawcy ani możliwości tworzenia alokacji. `MODEL_ADMISSION_GRANTED=false`, M1–M3 `HOLD_CASH`, operacje finansowe `0`. PR #124 pozostaje Draft.

## Cel i rozdzielenie kompetencji

W ramach PR #124 naprawiono wcześniej problem, w którym deklaracja `requirements[code].basis=TOTAL_RETURN_INDEX` mogła klasyfikować zwykłe wartości referencyjne jako serię dochodu całkowitego. Obecny `src/isl_v2/provenance.py::select_asof` zachowuje `value_concept`, a `src/isl_v2/autonomous_agent.py::_paper_decisions` wymaga rzeczywistego konceptu obserwacji. Ten koncept **nadal nie został dopuszczony do istniejącego parsera**; żaden model nie jest odblokowany.

Nowy czysty moduł `src/isl_v2/total_return_evidence_preflight.py` służy tylko do testowania **struktury proponowanego kontraktu źródła**, zanim niezależna ścieżka aprobaty go uwierzytelni. Nie jest używany przez `run_cycle` do podejmowania decyzji i nie zmienia modelu bazy danych ani uprawnień.

## Kontrakt pojedynczej obserwacji — wybory projektowe ISL

| Grupa | Wymagane pola | Sprawdzane ograniczenie |
|---|---|---|
| Identyfikacja | `instrument_code`, `source_code`, `official_series_id`, `source_version` | Tylko znane kody `EQUITY_TR_PLN`, `BONDS_TR_PLN`, `GOLD_TR_PLN`, spójny identyfikator na 4 miesiące |
| Typ wartości | `value_concept`, `return_basis`, `currency`, `interval_code` | `TOTAL_RETURN_INDEX`, jawnie `GROSS_TOTAL_RETURN` albo `NET_TOTAL_RETURN`, `PLN`, `1mo`; odrzuca `MONTHLY_AVERAGE` i cenę referencyjną |
| Wartość | `month`, `observed_for`, `price_value` | Miesiąc obserwacji zgodny z datą; indeks dodatni i skończony |
| Pochodzenie | `source_url`, `source_sha256`, `license_url`, `transformation_version` | URL HTTPS bez parametrów klucza, format SHA-256, identyfikator transformacji |
| Dostępność | `first_public_at`, `retrieved_at`, `publication_precision`, parametr `decision_asof` | Wszystkie czasy ze strefą; efektywna publikacja i faktyczny odczyt nie później niż cutoff; publikacja z precyzją tylko dnia — konserwatywnie od początku następnego dnia UTC |

Dodatkowa kontrola: **cztery kolejne miesiące dla każdej z trzech serii**, brak duplikatów i brak podmian źródła w środku okna.

Reguły są **wewnętrznym kontraktem analitycznym ISL**. Nie przypisujemy im statusu wymogu prawnego ani standardu ISO/NIST. Kontrole dostępności odzwierciedlają ten sam zamiar ochrony przed look-ahead bias co istniejący kod `src/isl_v2/provenance.py` i filtr odczytu w `src/isl_v2/agent_runner.py`.

## Granice dowodu — istotniejsze niż syntaktyczny PASS

Nawet jeśli użytkownik prześle komplet poprawnie sformatowanych pól i doda `PIT_VERIFIED=true`, `is_approved=true` lub `provider_trusted=true`, nowa funkcja zwraca:

- `structural_evidence_consistency=PASS` — jedynie zgodność *deklaracji* z regułami;
- `independent_source_authentication=NOT_PERFORMED`;
- `historic_first_publication_verified=false`;
- `historical_pit_certified=false`;
- `model_admission_granted=false`, `qualified_model_series=[]`;
- `research_model_state=HOLD_CASH`, `financial_operations=0`.

**Powód:** podpisany przez dostawcę opis, URL i nawet 64-znakowy zapis SHA nie dowodzą autentyczności zawartości, poprawności licencji ani rzeczywistego `first_public_at`. Nie wolno tego obchodzić przez ustawienie dodatkowej flagi.

## Jak uczynić tę ścieżkę użyteczną później

1. **Niezależny rejestr źródeł:** po ręcznej ocenie umieścić zaakceptowaną parę wydawca / `official_series_id`, definicję total return, walutę, częstotliwość, prawa/licencję i hash podpisanego artefaktu po stronie zaufanego operatora. Nie w danych dostarczanych przez potencjalny model.
2. **Weryfikacja treści:** odczytać oficjalny artefakt z zatwierdzonej domeny, przeliczyć SHA z rzeczywistych bajtów i zapisać zaufany `retrieved_at`, nie przyjmować czasu z niezweryfikowanego payloadu.
3. **Ścieżka PIT:** skojarzyć historyczne wersje (vintage) i momenty pierwszej publikacji z konkretnymi miesiącami; odrzucić późniejsze rewizje oraz archiwum pobrane współcześnie, jeżeli brak niezależnego historycznego snapshotu.
4. **Recenzja danych wejściowych:** potwierdzić `GROSS/NET`, dywidendy, kupony, walutę PLN, rodzaj ceny i instrument możliwy do modelowania; koszty, rozjazdy kalendarza i kompletność historyczna powinny mieć osobne testy.
5. **Odrębna autoryzacja techniczna:** dopiero recenzja i jawne dopuszczenie zaufanego źródła mogłyby uzasadniać zmianę parsera `parse_observation` i `_paper_decisions`. Ta iteracja nie dokonuje takiej zmiany.

Powiązany projekt PIT: `docs/SWINKELS_P1_POINT_IN_TIME_LINEAGE_AUDIT_20261110_PL.md`. Oryginalny retrospektywny ODS DataverseNL opublikowano 22.08.2025, więc jego bieżącej kopii nie wolno używać jako dowodu historycznej dostępności wartości w latach 2020–2022. Wdrożona sonda ALFRED wymaga osobnego klucza `FRED_API_KEY`, którego w GitHub Actions nadal brak (ostatnia potwierdzona próba).

## Testy i odbiór

Moduł `src/isl_v2/total_return_evidence_preflight.py`, testy `tests/test_total_return_evidence_preflight.py` (**23 scenariusze syntetyczne**) i workflow `.github/workflows/isl-total-return-evidence-preflight-ci.yml` działający na Ubuntu/macOS. Pełna regresja `full-agent-staging-canary-ci.yml` uruchamia również pozostałe testy platformy.

**Zakaz utożsamiania:** wynik `CI SUCCESS` oznacza działanie kontroli, nie weryfikację publicznych cen ani certyfikację PIT. Brak nowej integracji z brokerem, zmian w Neon, uprawnień, sekretów lub harmonogramów. Repozytorium pozostaje w fazie badawczej.
