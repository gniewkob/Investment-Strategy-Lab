# Investment Strategy Lab — M1–M3 research PR closeout, 11.11.2026

**Decyzja:** `PR_INTEGRATION_DONE`; **`MODULE_DATA_ACCEPTANCE_NOT_DONE`**. Kontrole kodu są odrębne od legalnego prawa do użycia danych, potwierdzonej dostępności historycznej PIT i kwalifikacji danych do modeli.

## Rzeczywisty stan GitHub i integracji

Stan `main` po audycie źródeł: `7ffc43e23d0f4376bcf2c4ea6860c1f88d8772fc`.

| Oryginalne PR | Wynik odbioru i integracji |
| --- | --- |
| #93, #95 | Scalone jako czysta integracja #129, commit `14c8ea4a2188900f324a0b07041c1f81acfa9102`; oryginały zamknięte bez ponownego merge |
| #101 | Scalone bezpośrednio, commit `71554e0b6b7b4be3f3acd6effdac2ff83771592c` |
| #104, #105 | Zastąpione #126, commit `5bfb6df0906b1f832d43b1ee8dac2a52d78aac04`; oryginały zamknięte |
| #106 | Scalone bezpośrednio, commit `9c947becf470f3d1069c7cfc6e1866f19dc9450b` |
| #107 | Zastąpione #125, commit `f9493f3e460cf86ce389f548c7c99ce44e1cce59` |
| #121, #122 | Zastąpione #127, commit `04df063bfd44c49e7a467b701d272b19995b59bc` |
| #124 | Zastąpione #128, commit `7ffc43e23d0f4376bcf2c4ea6860c1f88d8772fc`, 56 oryginalnych blobów i 36 zielonych kontroli |

Wcześniejsze scalone PR: #98, #99, #108, #109, #112, #113, #114, #115, #118 i #119. Wcześniej zamknięte bez scalenia: #96, #100, #102, #103, #110 i #111 — historię ich wyodrębnienia zachowano w oryginalnych PR i rozdzielonych integracjach; nie były ponownie scalane. Siedem otwartych PR infrastruktury Coinbase/Base (#86–#92) pozostaje **poza zakresem** tego modułu.

## Dowody CI (nieprzenoszalne na kwalifikację danych)

- Końcowy `main` `7ffc43e...`: [Full research runner offline regression tests — run 43085587408](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/43085587408): **1 237 testów, OK, skipped=1**.
- Silnik #129: osiem zielonych checków na PR (GitGuardian, G1, PostgreSQL E2E, read-only NBP, Ubuntu/macOS). Dodatkowo na scalonym rodzicu `14c8ea4...` push [Postgres E2E run 43085079129](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/43085079129) i [Data Readiness run 43085079158](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/43085079158): sukces.
- Audyt oryginalnego Swinkels ODS #128: **36/36** kontroli zielonych, w tym Ubuntu/macOS, matematyka niezależna od interpretatora ODF, dowody wersji/dat, testy bezpieczeństwa. Akceptacja dotyczy wyłącznie **retrospektywnego badania oryginalnego źródła**, nie źródłowej historii PIT do decyzji M1–M3.

## Ryzyko bezpieczeństwa i granica operacyjna

Historyczne alerty GitGuardian #95 i #121 wskazywały incydent `22028650` związany ze statycznym hasłem usługi PostgreSQL w workflow **izolowanego CI**. W #129 wprowadzono zmienną wartości testowej zależną od pojedynczego uruchomienia, zachowano kontrolę G1 16 kwarantannowanych nazw workflow, a dotychczasowy zablokowany plik zastąpiono nowym test-only workflow. Nowy GitGuardian dla #129/#127 i #128 jest zielony. **To nie dowodzi, że historyczny incydent został formalnie zamknięty w dashboardzie GitGuardian ani że testowa wartość nigdy nie była użyta gdzie indziej**. Owner musi osobno potwierdzić zakres użycia i oznaczyć incydent zgodnie z dowodami; jeśli wartość była ponownie użyta w realnym systemie, musi zostać unieważniona i wymieniona.

Uruchomiony kod nie tworzył transakcji, nie przenosił aktywów, nie upoważniał do wdrożenia produkcyjnego ani nie podnosił jakości danych do `PIT_QUALIFIED`. Status badawczy modeli pozostaje `INSUFFICIENT_DATA/HOLD_CASH`.

## Zadania P0 niezakończone — nie zamykać bez dowodów

1. [#97](https://github.com/gniewkob/Investment-Strategy-Lab/issues/97): faktyczne oryginalne NAV Vanguard z 60 wymaganymi miesiącami, weryfikacja ISIN, SHA-256 i formatowania, dokładne dopasowanie dat NBP, prawo do konkretnego wykorzystania oraz wynik importerów. Zapis pliku w prywatnej bibliotece lub jego nazwa nie jest dowodem walidacji oryginalnych bajtów.
2. [#116](https://github.com/gniewkob/Investment-Strategy-Lab/issues/116): prawa dostawców, dokładna semantyka indeksu i historyczne wersje publikacji TBSP/global equity/gold — brak dokumentów autoryzujących odpowiednie użycie i niezależnej chronologii. Nie korzystać z kopii obchodzących licencje.
3. [#123](https://github.com/gniewkob/Investment-Strategy-Lab/issues/123): oryginalny Swinkels ODS/README oraz historyczne wzory i 360 obserwacji już zweryfikowane; jednak niepotwierdzona równoważność wersji DOI v6 vs migracja Dataverse i wciąż fail-closed publiczny interfejs statystyk rzeczywistych serii. Nie oznaczać pełnego odbioru do usunięcia tych dwóch luk.

**Exit criteria:** można uznać etap PR za zamknięty. Nie można oznaczyć całego modułu `DONE` bez rozliczenia trzech P0, formalnej triage incydentu bezpieczeństwa, oraz kwalifikacji uprawnionych danych historycznych. Nie zamieniać zielonego CI lub danych referencyjnych w autoryzację obrotu.
