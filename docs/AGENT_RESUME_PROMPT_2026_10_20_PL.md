# Investment Strategy Lab — punkt wznowienia pracy agenta (20.10.2026)

## Zasada startowa

Zanim wykonasz jakąkolwiek zmianę, odczytaj z aktualnej gałęzi `main` repozytorium `gniewkob/Investment-Strategy-Lab`: `AGENTS.md`, `docs/SESSION_HANDOFF_PL.md`, ten dokument, a następnie najnowsze źródłowe raporty niżej. Wyszukaj w **OpenBrain_remote**, domena `build`, notatkę `Investment Strategy Lab — verified STEO source provenance & agent handoff (2026-10-20)` (memory id `5a8bd21b-f2a6-4bda-9349-2ccb11bdb86f`). Jeśli jeden system jest niedostępny, nie zgaduj jego treści; oznacz lukę i korzystaj z drugiego, jawnie raportując brak weryfikacji. GitHub `main` jest SSOT kodu i wyników, OpenBrain_remote — indeksem trwałego kontekstu.

## Fakty potwierdzone

- **58 wydań EIA STEO Jan2022–Oct2026; 316 par retrospektywnych prognoza–późniejsza referencja** WTI `WTIPUUS`, Brent `BREPUUS`, XLSX Table 2: 24 wydań 2022–23 × 2 surowce × 3 horyzonty = **144 par** (Jan–Aug2024 wyłącznie późniejsze referencje; realny [run 39433488201](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39433488201)); 34 wydań 2024–Oct2026 = **172 pary** (realny [run 39426001269](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39426001269)).
- **Zależność trafności od okresu:** EIA vs naiwne utrzymanie ceny poprzedniego miesiąca *z tego samego historycznego raportu*. W 2022 niższe MAE EIA w 6/6 grup; w 2023 tylko 2/6, a w 2024–26 2/6. As-of walk-forward 104 ocen: przełącznik między EIA i naïve nie pobił najlepszej stałej metody w żadnej z sześciu grup (realny [run 39428981358](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39428981358)). Nakładające się miesiące oznaczają, że pary nie są niezależnymi próbami.
- **Istotny nowy dowód źródłowy:** niezależne archiwum Catalyst Cooperative Zenodo v2.0.0, [record 15386905](https://zenodo.org/records/15386905), opublikowane **26.05.2025**. Trzy roczne paczki ZIP 2022/2023/2024 mają MD5 zgodne z manifestem; **36/36 oryginalnych XLSX = identyczne bajty (SHA-256)** wobec plików EIA pobranych w październiku 2026 (12/12 każdy rok), realny [run 39444963696](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963696), [PR #51](https://github.com/gniewkob/Investment-Strategy-Lab/pull/51) merged. CI: **290/290 offline, 3/3 disposable PostgreSQL PASS**. Manifest i pełne hashe: [docs/STEO_INDEPENDENT_ZENODO_36_BYTE_MATCH_2026_10_20_PL.md](STEO_INDEPENDENT_ZENODO_36_BYTE_MATCH_2026_10_20_PL.md).
- **Granica PIT:** niezależna kopia zdeponowana w maju 2025 NIE dowodzi, że jej bajty były identyczne **w dniu pierwszej publikacji** STEO w latach 2022–2024. Status historycznych oryginalnych publikacji: **PIT_UNVERIFIED**. Oficjalnych 9 errat opisuje [docs/STEO_OFFICIAL_ERRATA_PROVENANCE_2026_10_20_PL.md](STEO_OFFICIAL_ERRATA_PROVENANCE_2026_10_20_PL.md). Żadna z tych notek sama nie dowodzi korekty lub braku korekty cen WTI/Brent Table 2.
- **Zakończone operacyjnie:** wcześniej potwierdzony backup 6 plików archiwum EIA MyDevil + Mac — **CLOSED / USER-CONFIRMED**. Nie powtarzaj bez nowej przyczyny.

## Pliki źródłowe do przeczytania

1. `AGENTS.md` i `docs/SESSION_HANDOFF_PL.md` — najnowszy stan i ograniczenia.
2. `docs/STEO_INDEPENDENT_ZENODO_36_BYTE_MATCH_2026_10_20_PL.md` — 36 pełnych SHA, źródło Zenodo.
3. `docs/STEO_INDEPENDENT_ZENODO_2025_EVIDENCE_PL.md` — przebieg testów i metodologia.
4. `docs/STEO_OFFICIAL_ERRATA_PROVENANCE_2026_10_20_PL.md` — zakres 9 komunikatów EIA.
5. `docs/STEO_REAL_2022_2023_FROZEN_HISTORY_2026_10_20_PL.md` — 144 pary.
6. `docs/STEO_FULL_34_REAL_RESULTS_2026_10_20_PL.md` — 172 pary.
7. `docs/STEO_REAL_WALKFORWARD_ROBUSTNESS_2026_10_20_PL.md` — 104 chronologiczne oceny.
8. `docs/EIA_BACKUP_ACCEPTANCE_2026_10_20_PL.md` — zamknięty backup.

## Następne zadanie i bramki

Priorytet: zweryfikować **niezależne kopie surowych XLSX z datą przechwycenia bliską pierwotnej publikacji** dla konkretnych wydań STEO. Zanotować instytucję archiwizującą, URL, oryginalny moment przechwycenia, SHA-256 pobranych bajtów, datę wydania EIA i ewentualną różnicę semantyczną WTI/Brent. Jeśli dowodu brak, raportować `UNKNOWN` / `PIT_UNVERIFIED`, NIGDY nie pozorować certyfikacji.

Dopuszczalna alternatywa: plan **prospektywnego, datowanego i nieedytowalnego w logice badawczej** rejestrowania przyszłych nowych edycji (nie włączać harmonogramu bez zgody). Nie dopasowuj ponownie modeli na tych samych 316 parach ani nie zamieniaj ceny spot USD/bbl na stopy zwrotu instrumentów inwestowalnych w PLN.

**Twarde ograniczenia:** edukacyjny paper research, bez realnych zleceń, bez zmian alokacji M1/M2/M3 (`HOLD_NO_CHANGE`), bez zapisów Neon, zmian schema/ról/ACL, sekretów, płatnych usług/WORM, nowych harmonogramów czy otwierania zamkniętego backupu bez zgody. Każdy wynik potwierdzaj realnym źródłem i przebiegiem CI. Przed scaleniem zmian przejrzyj diff i testy; podaj dokładnie PASS/FAIL/NOT_VERIFIED oraz linki. Nie podawaj wyników testów syntetycznych jako wyników rynku.

## Procedura wznowienia

Po odczytaniu źródeł: (1) zestaw `HEAD SHA` bieżącego `main` z najnowszym handoff, (2) odczytaj stan ostatnich CI i otwartych PR/Issues, (3) sprawdź OpenBrain_remote lub stwierdź jego brak, (4) wskaż jedną najważniejszą lukę dowodową, (5) wykonaj małą, bezpieczną pracę na gałęzi i zweryfikuj testami, (6) uaktualnij dokumentację oraz OpenBrain_remote z potwierdzonymi faktami. Nie przeprowadzaj transakcji.
