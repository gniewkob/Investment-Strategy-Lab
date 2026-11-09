# E1 — syntetyczna odporność i chronologia decyzji M1–M3 (v0.26–v0.28)

**2026-11-09. Draft PR** zależny od [C1 #102](https://github.com/gniewkob/Investment-Strategy-Lab/pull/102), pośrednio od B1 #100 i A2 #99. Niezależny od D1/D2 NAV forward, B2 instalacji i C2 weryfikacji źródeł.

## Zależności i zakres

- `research_decision_robustness_v26.py` z testem: pięć jawnie syntetycznych scenariuszy odporności bramek i decyzji, bez danych rynkowych.
- `research_decision_quality_v27.py` z testem: porównanie oczekiwanych **syntetycznych etykiet scenariuszy** z wynikiem kontrolera. Wskaźnik jakości nie jest trafnością prognoz ani dowodem przewagi strategii.
- `research_chronological_decision_audit_v28.py` z testem: szereg **chronologicznie uporządkowanych**, dostarczonych snapshotów (w odróżnieniu od nieuporządkowanych testów v0.26–27). Brak dopasowania do przyszłych stóp zwrotu, autentyczności źródeł czy rzeczywistego OOS.

Sześć oryginalnych plików source/test skopiowano byte-for-byte z dużego Draft PR #96; zachowano Git blob SHA. Baza C1 dostarcza `research_decision_controller_v15`, `research_decision_pipeline_v16`, `research_forward_journal_v17` oraz frozen `shadow_decision_engine_v05` i testowe fixtures.

## CI / metodologia

Nowy workflow `.github/workflows/isl-e1-decision-audit-offline-ci.yml` uruchamia dokładnie **23 oryginalne testy** na Ubuntu i macOS / Python 3.12, jawnie wymusza `-W error::ResourceWarning`, blokuje Python socket, nie uruchamia dostawców i nie zapisuje danych do produkcyjnych baz.

**Techniczne PASS** w tym pakiecie oznacza tylko to, że deterministyczne bramki syntetyczne zachowują się zgodnie z regułami i nie mają ujawnionych wycieków w konkretnym teście. Nie oznacza to praw do danych MSCI/Vanguard/NBP, kwalifikacji źródeł M1–M3, możliwości wykonania transakcji, rzeczywistej OOS rentowności, alfa ani przydatności live.

## Kolejność i granice

A2 #99 → B1 #100 → C1 #102 → E1. E2 v0.29 zostanie osobnym PR zależnym od E1, aby oddzielić testy hipotetyczne od weryfikacji archiwalnego v0.9. Oba pozostają Draft do pełnego review; nie scalać z monolitem #96 bez odjęcia wspólnych plików. Brak merge, rebase, produkcyjnych operacji, kont giełdowych i transferów.
