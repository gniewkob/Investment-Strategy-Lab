# PR #96 — macierz wydzielenia i bramki integracji (2026-11-09)

**Przedmiot:** [Draft PR #96](https://github.com/gniewkob/Investment-Strategy-Lab/pull/96), `gniewkob/Investment-Strategy-Lab`. Dokument bada rozbicie na małe PR. **Nie jest zgodą na merge lub produkcyjne inwestowanie.**

## 1. Rzeczywiście utworzone zależne Draft PR

| Pakiet | PR | Base / zależność | Kod oryginalny z #96 | CI / oryginalne testy |
|---|---|---|---:|---|
| A1 — backtest v0.4 + koszty v0.14 | [#98](https://github.com/gniewkob/Investment-Strategy-Lab/pull/98) | `main`, niezależny | 8 plików | [38/38 PASS, Linux](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42427944205) (w tym PostgreSQL 16 localhost) |
| A2 — offline source contracts | [#99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99) | `main` | 8 | [32/32 PASS](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42450845898) |
| B1 — v0.5/7–11 ledger/checkpoints | [#100](https://github.com/gniewkob/Investment-Strategy-Lab/pull/100) | #99 | 13 | [47/47 PASS Linux i macOS](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42471064073) |
| B2 — host v0.12/13 | [#101](https://github.com/gniewkob/Investment-Strategy-Lab/pull/101) | #100 | 4 | [16/16 PASS Linux i macOS](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42471266332) |
| C1 — decyzje v0.5/6 i v0.15–17 | [#102](https://github.com/gniewkob/Investment-Strategy-Lab/pull/102) | #100 | 10 | [53/53 PASS Linux i macOS](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42624134958) |
| C2 — source gateway v0.18/19 | [#103](https://github.com/gniewkob/Investment-Strategy-Lab/pull/103) | #102 | 4 | [19/19 PASS Linux i macOS](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42624511327) |
| D1 — NAV analytics / freeze v0.20–23 | [#104](https://github.com/gniewkob/Investment-Strategy-Lab/pull/104) | #99 | 10 | [41/41 PASS Linux i macOS](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42640373249) |
| D2 — prywatny NAV/FX v0.24/25 | [#105](https://github.com/gniewkob/Investment-Strategy-Lab/pull/105) | #104 | 4 | [19/19 PASS Linux i macOS](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42640741885) |
| E1 — syntetyczne testy v0.26–28 | [#106](https://github.com/gniewkob/Investment-Strategy-Lab/pull/106) | #102 | 6 | [23/23 PASS Linux i macOS](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42641455098) |
| E2 — archived v0.9 decision bridge v0.29 | [#107](https://github.com/gniewkob/Investment-Strategy-Lab/pull/107) | #106 | 2 | [8/8 PASS Linux i 8/8 PASS macOS](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42641864529) |

**Razem: 69 oryginalnych plików** z PR #96 wydzielono przez dokładne kopiowanie, a ich zgodność Git blob SHA z badawczą gałęzią niezależnie ponownie odczytano. Nowo dodane w małych PR pliki CI/dokumentacji **nie** są liczone do tych 69. Przed dopisaniem tego raportu PR #96 miał **137 zmienionych plików** (68 nieobjętych opisanymi kopiami). **Po dodaniu tego dokumentu** [aktualna lista GitHub PR](https://github.com/gniewkob/Investment-Strategy-Lab/pull/96/files) pokazuje **138 plików**, z czego **69 pozostaje poza 69 oryginalnymi plikami przeniesionymi do mniejszych PR** (workflowy, źródłowe kolektory i ich testy, audytowe skrypty, raporty/dokumenty). To nie jest podział wszystkich elementów monolitu.

## 2. Graf zależności

```text
main
├── A1 #98
└── A2 #99
    ├── B1 #100
    │   ├── B2 #101         (host / backup, niezależne od C)
    │   └── C1 #102
    │       ├── C2 #103     (reference source category)
    │       └── E1 #106
    │           └── E2 #107
    └── D1 #104
        └── D2 #105         (freeze / forward, bez wykonania)
```

**To gałęzie staged Draft, nie jedna przetestowana zmiana na `main`.** CI mały PR w jego aktualnej bazie nie oznacza, że wszystkie PR można scalić w dowolnej kolejności bez powtórzenia testów.

## 3. Krytyczne dowody niezmienione

- Oryginalny archiwalny bundle v0.9: `evidence/shadow/v09/checkpoint-bundle-run-42305280062.json`, surowy SHA-256 `4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3`. SHA sprawdza spójność zapisanych bajtów, nie stanowi niezależnego dowodu zaufanego czasu.
- Oryginalne kodowe Git blob SHA zamrożonego protokołu: v0.22 `7a9c7e5cbc643b5ad760ec64d4212468b64a22bf`; v0.23 `d425076ea809f622e5b2c1c4e87ba59fe060f990`.
- Freeze/anchor v0.23: `3b8aca44ffa6aa72bf2d3a0b5d49102f0dd857d11191dc10e7d21b5051e704a2` (istniejący Issue #97). Brak nowego, niezależnie kwalifikowanego źródła danych, rzeczywistych forward NAV z listopada, PIT/OOS lub inwestycyjnej realizacji M1–M3. Stan **PENDING / HOLD_CASH**.

## 4. Pozostała niezintegrowana powierzchnia — obowiązkowa separacja

Wśród nieprzeniesionych plików pozostają workflowy `workflow_dispatch` i API/Playwright (Vanguard, BondSpot, NBP, World Bank, WorldPulse), źródłowe adaptery/collectory i testy, pierwotny duży CI, czasem host-specific canary i dokumentacja źródłowa. To **nie** jest automatycznie dopuszczone do użycia produkcyjnego przez zielone CI D1/D2/E1/E2. Szczególnie dwa workflowy Vanguard mają możliwość dołączenia **surowych niezweryfikowanych eksportów** jako GitHub artifacts — aktualny przegląd: [A2 provider workflow risk review](PR96_A2_PROVIDER_WORKFLOW_RISK_REVIEW_20261108_PL.md).

**MUST FIX przed połączeniem małych PR**: (a) niezależny code/security review i branch protection, (b) uporządkowanie kolejności zależności i świeże testy każdej zmiany na aktualnej bazie, (c) konflikt/overlap audit względem #96, (d) zweryfikowanie praw do pozyskania/retencji źródeł i granic danych, (e) odrębne dowody historii PIT i uprawnień — jeśli mają być używane do badań wyników. Po scaleniu małych PR nie scalać monolitu #96 bez ponownego porównania oraz jawnego odjęcia zduplikowanych plików.

## 5. Kontrola zakresu

Wszystkie te pakiety pozostają **Draft**, żadnego merge/rebase do `main`, nowego harmonogramu, połączenia do produkcyjnego Neon, brokerów/wallet, wpłaty, ordera ani transferu. Brak kwalifikacji źródeł dla rzeczywistych decyzji finansowych. Wspomniany lokalny SQLite ledger i SHA-anchor nie tworzą WORM ani niezależnej atestacji czasu.
