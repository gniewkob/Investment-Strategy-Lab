# Investment Strategy Lab — wdrożenie izolowanego rejestru na Mac mini (v0.12)

**Status techniczny: kod gotowy, izolowany canary na macOS PASS. Na prywatnym Mac mini wdrożenie pozostaje NOT VERIFIED, dopóki nie otrzymamy raportu z tego hosta.**

## Cel

Instalacja `scripts/deploy_shadow_evidence_mac_v12.py` zapisuje **wyłącznie oddzielny rejestr dowodowy** bazujący na zweryfikowanym archiwum badawczym z PR #96. Nie wykonuje ani nie planuje transakcji, nie instaluje żadnego `LaunchAgent`, nie zmienia aktywnych procesów, nie korzysta z portfela Coinbase ani nie zapisuje do Neon.

Nowy katalog jest izolowany:

`$HOME/Library/Application Support/InvestmentStrategyLabShadowEvidence`

Kod odmawia działania, gdy katalog już istnieje (także jako symlink). **Nie scala ani nie aktualizuje** wcześniejszych instalacji w `$HOME/Library/Application Support/InvestmentStrategyLab`. Działanie jest w pełni lokalne, nie pobiera market data ani nie wywołuje sieci.

## Co faktycznie robi instalator

1. Sprawdza macOS, brak uprawnień root, dokładny 40-znakowy SHA HEAD, zaufany `origin` repozytorium `gniewkob/Investment-Strategy-Lab`, zgodność skryptu z checkoutem i SHA-256 wersjonowanego źródła `4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3`.
2. Przygotowuje prywatne katalogi `0700` i pliki `0600` w stagingu.
3. Odtwarza **jeden historyczny, badawczy** rekord v0.9 z `evidence/shadow/v09/checkpoint-bundle-run-42305280062.json`.
4. Wystawia kotwicę v0.10, weryfikuje jej SHA-256 oraz hash zrekonstruowanego łańcucha.
5. Tworzy kopię v0.11 z manifestem i wykonuje próbne odtworzenie do odrębnego katalogu.
6. Zapisuje `state/deployment-receipt-v12.json`, przenosi gotowy staging do unikalnego katalogu bazowego i sprawdza wynik.
7. Zwraca status `ISOLATED_RESEARCH_LEDGER_DEPLOYED_NO_SCHEDULE` albo `ISL_V12_BLOCKED`. **Samo CI macOS nie potwierdza instalacji na prywatnym Mac mini.**

Dane zapisane na tym samym urządzeniu **nie są** backupem offsite. Znacznik czasu jest operacyjny, nie certyfikowany.

## Procedura na Mac mini — do wykonania na właściwym hoście

Weryfikacja SHA wprowadzona w tym dokumencie jest przykładowym ograniczeniem wersji. Przy właściwym wdrożeniu wpisz wyłącznie **dokładny, zatwierdzony SHA gałęzi PR #96**, potwierdzony w GitHub i w CI; nie używaj dynamicznego `HEAD` ani głównego checkoutu, do którego przypięto obecne procesy.

```bash
set -euo pipefail
umask 077

# Osobny klon nie dotyka aktualnego checkoutu i działającego LaunchAgent.
mkdir -p "$HOME/Repos"
RESEARCH_CLONE="$HOME/Repos/Investment-Strategy-Lab-shadow-v12"
test ! -e "$RESEARCH_CLONE"
git clone https://github.com/gniewkob/Investment-Strategy-Lab.git "$RESEARCH_CLONE"
cd "$RESEARCH_CLONE"
git fetch origin codex/v04-monthly-backtest-engine-20261106

# Wstaw zweryfikowany SHA commitu z końcowego zielonego CI.
APPROVED_SHA="<40-character-approved-commit-sha>"
git checkout --detach "$APPROVED_SHA"
test "$(git rev-parse HEAD)" = "$APPROVED_SHA"

python3 -m scripts.deploy_shadow_evidence_mac_v12 \
  --repo-root "$RESEARCH_CLONE" \
  --expected-commit "$APPROVED_SHA" --preflight

# Dopiero po preflight: jednorazowa izolowana instalacja dowodowa.
python3 -m scripts.deploy_shadow_evidence_mac_v12 \
  --repo-root "$RESEARCH_CLONE" \
  --expected-commit "$APPROVED_SHA" --apply
```

**Dowód odbioru z Maca:** w raporcie musi być `ISOLATED_RESEARCH_LEDGER_DEPLOYED_NO_SCHEDULE`, `entries=1`, `financial_operations=0`, `active_scheduler_changed=false`, `neon_modified=false`, `offsite_backup_verified=false`. Sprawdź także plik `state/deployment-receipt-v12.json` i hashe za pomocą modułów v0.9–v0.11.

Ponowne uruchomienie `--apply` na tym samym katalogu powinno zakończyć się `ISL_V12_BLOCKED` — **to pożądana blokada**, a nie polecenie skasowania danych. Nie używaj `sudo` i nie usuwaj już istniejących katalogów w celu ponowienia.

## Kolejna bramka po wdrożeniu

- Utworzyć niezależną kopię zabezpieczoną przed modyfikacją na **innym** nośniku lub w innym systemie zarządzania i osobno zachować wartość `backup_manifest_sha256`.
- Przetestować restore z tej niezależnej kopii, nie z bieżącego folderu na tej samej maszynie.
- Określić politykę rotacji/retencji oraz sposób sprawdzania niezależnego hasha checkpointu. Nie wprowadzać harmonogramu automatycznego, dopóki nie przejdzie osobnego przeglądu i akceptacji.

## Granice dowodowe

| Warunek | Status |
|---|---|
| Regresja bezpieczeństwa instalatora | Sprawdzać w CI |
| Izolowana instalacja na runnerze macOS | Sprawdzać w CI |
| Faktyczna instalacja na Mac mini | **WYMAGA DOWODU Z HOSTA** |
| Kopia do niezależnej domeny awarii | **NIE WDROŻONO** |
| Niezmienny WORM / TSA | **NIE CERTYFIKOWANO** |
| Weryfikacja modeli M1–M3 na pełnym PLN total return | **BLOCKED** |
| Zlecenia, płatności, transfery, zmiana portfeli | **0 / zabronione w tym wdrożeniu** |

Oficjalne źródła techniczne: [SQLite backup API](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup), [GitHub Actions checkout i kontekst SHA](https://docs.github.com/en/actions/reference/workflows-and-actions/variables#default-environment-variables), [SQLite PRAGMA integrity_check](https://sqlite.org/pragma.html#pragma_integrity_check).
