# Sprint 1 — backlog i kryteria odbioru

**P0 — Wykonane w tej iteracji (test-only)**

- [x] Audyt aktualnego Neon schema (3711 istniejących obserwacji; brak `published_at` dla legacy).
- [x] Przygotowanie niedestrukcyjnej migracji na odrębnej gałęzi Neon.
- [x] Test zachowania wersji danych przed i po publikacji korekty w PostgreSQL.
- [x] Offline walidator daty publikacji, jednostek i rewizji.
- [x] Testowy rejestr przebiegu: STARTED -> SUCCEEDED z eventem.
- [x] CI dla testów i offline DRY_RUN (workflow gotowy w kodzie, NIE opublikowany na GitHub).

**P0 — Pozostało do odbioru Sprint 1**

- [ ] Nowe prywatne repo GitHub i push na osobną gałąź review (repo jeszcze nie istnieje/nie jest udostępnione).
- [ ] Potwierdzony przebieg workflow GitHub Actions (0 potwierdzonych GitHub CI runs).
- [ ] Niezależny review migracji, uprawnień i procedury wycofania; potem oddzielna decyzja o `main`.
- [ ] Ograniczona rola bazy dla pipeline; bez uprawnień do DDL i bez zapisu na realnych portfelach.
- [ ] Wersjonowana strategia backfill z prawdziwym `published_at` i SHA256 surowych plików.
- [ ] Zweryfikowany dry-run niezależnego produkcyjnego kolektora na realnych danych, z dziennikiem błędów i retry.
- [ ] Test końcowy M3 bez wykonania po tej samej cenie, na podstawie której powstał sygnał.

**P1 — Kolejna iteracja**

- [ ] 14 uruchomień niezależnego pipeline, historia statusów i działający kanał alertów.
- [ ] Migrowanie selektywne do `prices_asof` tylko po potwierdzeniu historycznej dostępności.
- [ ] Metryki SLA świeżości źródeł, braków i rewizji.
- [ ] Test odtworzenia Neon z backup/snapshot, bez naruszania `main`.

**Dozwolone granice**: badania edukacyjne i syntetyczne symulacje. Nigdy zlecenia finansowe, transfery, handel na rzeczywistych środkach ani modyfikacje portfela.
