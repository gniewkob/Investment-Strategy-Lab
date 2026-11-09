# E2 — połączenie oryginalnego archiwalnego dowodu v0.9 z badawczą decyzją v0.29

**2026-11-09. Draft PR** zależny od [E1 #106](https://github.com/gniewkob/Investment-Strategy-Lab/pull/106) i pośrednio C1 #102/B1 #100/A2 #99. Oryginalny bundle `evidence/shadow/v09/checkpoint-bundle-run-42305280062.json` jest dostarczany przez B1 — nie kopiujemy ani nie modyfikujemy go ponownie.

## Zachowany zakres oryginału

- `scripts/research_archived_decision_link_v29.py` (Git blob `694de8ac036d9109a0e0b8669bd9a7cd92f3771a`) i `tests/test_research_archived_decision_link_v29.py` (Git blob `6f81df40caf1ac6d1390dfe464cdf65dae94e3e8`) są kopiami z PR #96.
- Weryfikacja archiwalnego SHA-256 oryginalnego JSON: `4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3`.
- `v0.29` sprawdza strukturę oryginalnego bundle i odtwarza **HOLD_CASH** przez `research_decision_pipeline_v16`; opcjonalnie odczytuje **już istniejący** SQLite ledger v0.9 do porównania. Nie zakłada nowych plików ledger, nie pisze na produkcyjną bazę ani nie pozyskuje cen rynkowych.

## Ograniczenia

Weryfikowalny hash oryginalnego JSON, test zgodności metadanych API i lokalny SQLite hash-chain **nie są niezależnym kryptograficznym certyfikatem oryginalnego czasu**, nie dowodzą niezaprzeczalności archiwizacji ani zgodności ze standardem WORM. Brak zakwalifikowanego, oryginalnego total-return market source i brak prawdziwej prospektywnej obserwacji oznacza `HOLD_CASH`; testy nie mierzą alpha, OOS ani możliwości realizacji realnego portfela.

## CI

Nowy `.github/workflows/isl-e2-archived-evidence-link-ci.yml` uruchamia **8 istniejących testów** Linux/macOS Python 3.12, `-W error::ResourceWarning`, blokadę Python socket oraz sprawdza Git blob SHA skryptu/testu i oryginalny raw SHA256 bundle. W ramach CI wyłącznie pliki tymczasowe i odczyty; nie powstaje zewnętrzny niezależny anchor, nie używa się brokerów, Neon ani portfela.

**Integracja:** A2 #99 → B1 #100 → C1 #102 → E1 #106 → E2. B2 #101 i C2 #103 są osobnymi gałęziami i nie są wymagane przez E2. Zamrożone Vanguard v0.22/v0.23 pozostają nietknięte. Nie scalać monolitu #96 po częściowych integracjach bez odjęcia duplikujących się plików. Draft pozostaje nieruszony do niezależnego review, rzeczywiste operacje finansowe = 0.
