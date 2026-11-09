# D1 — warunkowe NAV Vanguard/NBP i zamrożenie reguł forward (v0.20–v0.23)

**Stan:** samodzielny Draft PR zależny od A2 [#99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99). Wyłącznie edukacyjna analiza referencyjna, nie handel ani rynkowa kwalifikacja M1.

## Granica komponentów i zachowanie oryginału

Dziesięć skryptów i testów kopiowanych **bez zmiany Git blob SHA** z historycznej gałęzi PR #96:

- `vanguard_nav_intake_bundle_v04.py` z testem: walidacja ręcznie dostarczonych **oryginalnych** bajtów XLSX i NBP. Domyślnie offline; wywołanie oddzielnego opt-in dokładnego dnia NBP jest możliwe poza tym PR i nie jest testowane na realnej sieci.
- `conditional_m1_nav_diagnostic_v20.py` z testem: hipotetyczny NAV/PLN vs gotówka. To **model referencyjny**, nie możliwa do uzyskania cena zamknięcia zlecenia.
- `conditional_m1_nav_analytics_v21.py` z testem: modelowe XIRR, drawdown oraz wpływ kosztów; ujęcie retrospektywne, nie OOS.
- `nav_forward_freeze_v22.py` z testem: niezmienny protokół źródeł i warunków obserwacji z wyprzedzeniem.
- `nav_forward_admission_v23.py` z testem: sprawdzenie zgodności z przypiętym oryginalnym SHA freeze i statusu `PENDING`, bez uznania samodzielnie zadeklarowanych praw do źródeł czy czasu publikacji.

**Przypięte oryginalne bajty kodu:** Git blob SHA v0.22 `7a9c7e5cbc643b5ad760ec64d4212468b64a22bf`, v0.23 `d425076ea809f622e5b2c1c4e87ba59fe060f990`. **Przypięty eksperyment**: `ANCHORED_FREEZE_SHA=3b8aca44ffa6aa72bf2d3a0b5d49102f0dd857d11191dc10e7d21b5051e704a2`, istniejący link do Issue #97. Przy wydzielaniu Git commit SHA może się zmienić; nie wolno podmieniać w źródłach zakotwiczonego SHA ani przepisywać założenia na nowy eksperyment bez jawnego oznaczenia.

## CI i ograniczenia dowodowe

Dedykowany `.github/workflows/isl-d1-nav-freeze-offline-ci.yml`: Python 3.12 Linux/macOS, oczekiwane **41 testów** na system, weryfikacja Git blob v22/v23 i przypiętego SHA oraz blokowanie Python socket. Brak dostępu do Neon, brokerów, portfela, tokenów dostawcy, oryginalnego eksportu funduszu oraz harmonogramów pobierania. Testy są syntetyczne; nie dowodzą rzeczywistego prawa do redystrybucji oryginalnego NAV, historycznego `point-in-time`, możliwości historycznej realizacji po NAV czy OOS rentowności.

D1 nie zapisuje nowego zaakceptowanego źródła `GLOBAL_EQUITY_TR_PLN` i nie znosi statusu `HOLD_CASH` systemu M1–M3. NBP `FX_RATE` oraz Vanguard `NAV_REFERENCE` nie są automatycznie historią inwestowalnej całkowitej stopy zwrotu.

## Kolejny etap / merge policy

D2 (v0.24 i v0.25) wymaga D1 oraz A2, zostanie wydzielony osobno. Nie przenosić workflowów Playwright Vanguard do D1; ich prawa i przechowywanie RAW artifacts są otwartym punktem w `docs/PR96_A2_PROVIDER_WORKFLOW_RISK_REVIEW_20261108_PL.md`.

Draft zostaje nie scalony. Zakres D1 współwystępuje w monolicie #96, więc przed jakimkolwiek merge należy zrekompensować overlap i sprawdzić aktualne branch protection. Zachować oryginalne archiwum v0.9 i wszystkie dowody v0.22/v0.23. Zero rzeczywistych operacji finansowych.
