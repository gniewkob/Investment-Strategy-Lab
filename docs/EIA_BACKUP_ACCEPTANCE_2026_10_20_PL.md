# EIA — backup zakończony i potwierdzony (20.10.2026)

**Status operacyjny: CLOSED / USER-CONFIRMED.** Nie wymagaj ponownie konfiguracji płatnego OVH Object Storage lub osobnego WORM jako warunku dalszej pracy edukacyjnej. Użytkownik potwierdził, że zadbał o backup i polecił oznaczyć ten etap jako zakończony. Zakres potwierdzenia i dowodów opisany poniżej.

## Dowody faktycznie zweryfikowane w wynikach poleceń

- Źródło: MyDevil, prywatne `$HOME/.isl-eia-archive`, trzy rzeczywiste dokumenty EIA + manifesty. Odczyt `du`: **473 KB / 6 plików**. WTI, Brent, Henry Hub przeszły **3 niezależne offline `verify`** z ich oryginalnymi bajtami i manifestami. Każde `verify` zwróciło `EIA_RAW_HTML_ARCHIVE_INDEPENDENT_OFFLINE_VERIFIED`.
- Kopia: Mac mini, prywatna datowana kopia `~/.isl-eia-backups/20261020T093647Z`. Transfer **6 plików**. Użytkownik sprawdził `shasum -a 256` dla wszystkich **3 oryginalnych HTML**: identyczny raw SHA do MyDevil.
- Dodatkowy test Mac `MAC_BACKUP_INTEGRITY_PASS`: trzy pliki HTML, trzy manifesty, dla każdego manifest wskazuje właściwe źródło i raw SHA, a `sha256(raw_html) = manifest.original_html_sha256`. Ten test sprawdza integralność powiązania dokument↔manifest; nie jest pełnym, niezależnym ponownym parsowaniem całej semantyki na Mac.
- **20.10.2026:** użytkownik oświadczył, że zadbał o backup i wyraźnie zlecił zamknięcie tego etapu jako potwierdzonego. Weryfikację przyjmujemy w granicach powyższych testów, bez ponawiania identycznych czynności.

| Dokument | Potwierdzony oryginalny SHA-256 w MyDevil i kopii Mac |
| --- | --- |
| WTI | `4ecd9261dbc6fe1ba583d017af72fb37d2a33d626a11b4ab7940227d1122f489` |
| Brent | `be659c06a7f497afa0e49c976defa774cd70814d04bda7a20afac890d566f2ca` |
| Henry Hub | `70b294c14f1deafbcd9c4b898d5c94ab971857013852197315616a67199d01fc` |

## Decyzja o zakresie zapewnień i pozostałe ograniczenia

**ACCEPTED / CLOSED dla operacyjnego backupu projektu badawczego:** istnieją dwie fizycznie osobne kopie, weryfikacja plików/manifestów zakończona PASS, użytkownik dodatkowo potwierdził ochronę backupu. **Nie jest konieczne utworzenie płatnego bucketu OVH w tej fazie.**

Nie mamy osobnego technicznego dowodu, że skonfigurowano i rzeczywiście wykonano Time Machine, odzyskano kopię po awarii, włączono retencję WORM/Object Lock czy testowano odporność na usunięcie przez administratora. Użytkownik potwierdził zadbanie o backup, ale nie dostarczył wyników tych konkretnych testów. **Nie oznaczać tych niewykonanych testów jako PASS.** WORM pozostaje poza zakresem obecnego, zaakceptowanego ryzyka, nie ma blokować edukacyjnej pracy offline.

## Odrębna bramka danych — bez zmian

**Backup źródła ≠ niezależny historyczny PIT.** Źródłowe HTML pozyskano w dniu 20.10.2026, nie dowodzą kiedy EIA pierwotnie publikowała każdą historyczną obserwację. Historyczne daty publikacji nadal `UNVERIFIED_HISTORICAL_PUBLICATION`, `MARKET_DATA_NOT_READY`; brak zgody na nowe role/ACL/secrets lub zapis versioned EIA do Neon STAGING i zero realnych transakcji. Badawcze wirtualne modele M1/M2/M3 `HOLD_NO_CHANGE`.

**Kolejny etap:** przejść do bezpiecznej, edukacyjnej analizy przyszłych (prospective) snapshotów z wiarygodną datą ich pozyskania; nie wracać do iteracyjnej dyskusji o backupie bez nowego, konkretnego problemu.

Powiązane: [realne dowody archiwizacji EIA](EIA_MYDEVIL_ACTUAL_ARCHIVE_RECEIPTS_2026_10_20_PL.md) i [status projektu](SESSION_HANDOFF_PL.md).
