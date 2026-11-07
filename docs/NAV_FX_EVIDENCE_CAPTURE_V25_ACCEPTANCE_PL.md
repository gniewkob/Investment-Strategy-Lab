# ISL v0.25 — kontrolowane pozyskiwanie oryginalnego kursu NBP dla nowego eksportu Vanguard

## Status i rzeczywisty zakres

Zaimplementowano `scripts/nav_fx_evidence_capture_v25.py`: lokalny, bezpieczny proces **manualny oryginalny XLSX Vanguard → kontrola 60 historycznych miesięcy → jawnie opcjonalny jeden GET do oficjalnego API NBP → zapis oryginalnej odpowiedzi JSON**. Nie działa jako autonomiczny downloader Vanguard ani proces cykliczny. W dniu 2026-11-07 poprawny stan to `PENDING_NEW_PROVIDER_EXPORT`; miesięczna obserwacja listopada nie jest zamknięta.

Źródło oficjalnego API: https://api.nbp.pl/ (sekcje: *Pobieranie kursów walut oraz cen złota*, *Opis funkcji API dotyczących kursów walut*, *Zapytania o kompletne tabele*); HTTPS GET `/api/exchangerates/tables/a/{day}/{day}/?format=json` dla **identycznego dnia publikacji**. NBP podaje kurs średni, a nie cenę transakcyjną. Dla dnia bez tabeli API może zwrócić HTTP 404; brak kursu powoduje błąd i nie jest uzupełniany. Pobranie jest tylko po jawnej fladze `--fetch-official-nbp`.

## Bieżąca kontrola — bez internetu i bez nowego eksportu

```bash
python3 -m scripts.nav_fx_evidence_capture_v25 \
  --freeze "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/forward-freeze-v22-20261107.json" \
  --baseline "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/v04-20261107T194932Z/vanguard-nav-pln-candidate.json"
```

Sprawdza obie prywatne, już istniejące referencje i nie łączy się z NBP. Drukuje tylko metadane i skróty SHA.

## Przyszły odczyt po zakończeniu listopada 2026

Gdy został faktycznie uzyskany nowy oryginalny eksport Vanguard przez uprawnioną osobę i jest pełna obserwacja listopada, uruchomić lokalnie **najpierw bez pobierania NBP**:

```bash
python3 -m scripts.nav_fx_evidence_capture_v25 \
  --freeze "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/forward-freeze-v22-20261107.json" \
  --baseline "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/v04-20261107T194932Z/vanguard-nav-pln-candidate.json" \
  --new-xlsx "/prywatna/sciezka/oryginalny-nowy-vanguard.xlsx" \
  --xlsx-retrieved-at-utc "YYYY-MM-DDTHH:MM:SS+00:00"
```

Czas ma pochodzić z rzeczywistego momentu pobrania, nie z wartości wymyślonej lub cofniętej. Zapisany wcześniej XLSX i nowy muszą być różnymi plikami. Skrypt sprawdza datę zamknięcia miesiąca, sha, wszystkie 60 historycznych miesięcy i daty NAV. Rewizje powodują `BLOCKED_PROVIDER_REVISIONS_NEED_REVIEW`; żadnego milczącego zastępowania historii. Bez rewizji stan `READY_FOR_EXPLICIT_NBP_SOURCE_READ`.

Dopiero wtedy można opcjonalnie wykonać:

```bash
python3 -m scripts.nav_fx_evidence_capture_v25 \
  --freeze "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/forward-freeze-v22-20261107.json" \
  --baseline "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/v04-20261107T194932Z/vanguard-nav-pln-candidate.json" \
  --new-xlsx "/prywatna/sciezka/oryginalny-nowy-vanguard.xlsx" \
  --xlsx-retrieved-at-utc "YYYY-MM-DDTHH:MM:SS+00:00" \
  --fetch-official-nbp \
  --private-nbp-out "$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch/nbp-exact-nav-2026-11.json"
```

Jeśli NBP zwróci oryginalną poprawną tabelę A USD dla dnia NAV, skrypt waliduje ją poprzez `v0.24 + v0.23` i zachowuje *oryginalne bajty* w nowym prywatnym pliku JSON, bez nadpisania istniejącej ścieżki (tryb `xb` i uprawnienia docelowe 0600). Nie wyświetla surowych kursów lub NAV w terminalu i nie przekazuje ich na GitHub ani do Neon. Nie należy wykonywać tej komendy, dopóki nie nastąpił prawdziwy eksport po zamknięciu miesiąca.

## Kryteria akceptacji i ograniczenia

Zgodność źródła historycznego: `541518959c1be70cc8d497ba4780a31ad7a6a8f61dbb37a8b2b8286d7cee423c`; zamrożenie v0.22: `3b8aca44ffa6aa72bf2d3a0b5d49102f0dd857d11191dc10e7d21b5051e704a2`.

Po rzeczywistym pozyskaniu kompletnego źródła wynik v0.25 może osiągnąć `PRIVATE_OFFICIAL_NBP_CAPTURED_CANDIDATE_ONLY`, lecz nie potwierdza w pełni źródła Vanguard, licencji, oryginalnego momentu publikacji, wykonalności zlecenia ani jakości wyników prospektywnych. `strict_m1_qualified=false`, `prospective_qualified_months=0`, `financial_operations=0`. Brak operacji handlowych, portfela, Neona, planowania czy wymuszonego dostępu do portalu Vanguard.

CI testuje jedynie syntetyczne źródła i zmockowany jednorazowy GET; rzeczywiste przyjęcie przyszłego źródła pozostaje **PENDING**. Dla precyzyjnego dowodu momentu pobrania należy w przyszłości również zakotwiczyć SHA nowego pliku i odpowiedzi w zewnętrznym dzienniku czasu.
