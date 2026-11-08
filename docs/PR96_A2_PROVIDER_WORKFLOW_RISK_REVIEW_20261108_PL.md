# PR #96 / A2 — przegląd workflowów pobierających dane zewnętrzne
**Data:** 2026-11-08. **Zakres:** weryfikacja kodu workflowów GitHub w gałęzi badawczej; nie uruchomiono żadnego dostawcy ani nie pobrano danych.

## Wniosek integracyjny

Parsery i kontrola pochodzenia źródeł są już wydzielone w samodzielnym [Draft PR #99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99). **Nie należy kopiować do niego automatycznie workflowów prowadzących zewnętrzny odczyt**. Obecne workflowy niżej są odrębną operacyjną powierzchnią dostępu, retencji oraz potencjalnych praw do danych. Sam sukces HTTP/eksportu nie dowodzi licencji, punktu czasowego oryginalnej publikacji (PIT), ani dopuszczenia strategii.

| Workflow — rzeczywisty kod źródłowy | Co robi / wyzwalacz | Obszar do review przed integracją |
|---|---|---|
| `.github/workflows/v04-vanguard-official-nav-export.yml` | `workflow_dispatch`; Playwright/Chromium; upload `vanguard-nav-public-probe/*`, 7 dni | Może zachować **surowy eksport** w artifact GitHub. Trzeba potwierdzić uprawnienie do automatycznego pobierania i przechowywania oraz zasady dostępu i retencji; nie aktywować bez decyzji |
| `.github/workflows/v04-vanguard-retail-nav-probe.yml` | `workflow_dispatch`; próby regionów PL i CH; upload `vanguard-nav-retail-evidence-*/*`, 7 dni | Podobny problem surowych źródeł; obie jurysdykcje to różne ścieżki strony i potencjalne warunki dostępu. Obecna nazwa artifact `raw-unverified` nie oznacza zatwierdzenia praw |
| `.github/workflows/v04-official-nav-bond-index-probe.yml` | `workflow_dispatch`; bezpośredni odczyt HTML Vanguard i TBSP | Brak upload oryginalnego NAV w samym workflow, ale to operacyjna próba dostawcy; potencjalne ograniczenia scraping/fair-use wymagają odrębnego review, bez dopowiadania konkretnych zakazów |
| `.github/workflows/nbp-long-history-v04.yml` | `workflow_dispatch`; API NBP, artifact 14 dni | Dla publicznych referencji NBP zachować raw SHA, datę pobrania i typ serii; nie zamieniać FX_RATE ani PRICE_ONLY na inwestycyjny total return |
| `.github/workflows/tbsp-official-60months-v04.yml` | `workflow_dispatch`; 5 zestawów po 12 miesięcy, artifact 14 dni, merge i walidacja | Kontrola dostępności/warunków archiwum BondSpot, spójności pięciu fragmentów; indeks nie jest instrumentem z wykonywalną ceną |
| `.github/workflows/world-bank-gem-audit-v04.yml` | `workflow_dispatch`; API wskaźnika World Bank; artifact 14 dni | Zapis służy diagnostyce dostępności, nie jako automatycznie zakwalifikowany global equity TR. Workflow używa `actions/checkout@v4` bez `persist-credentials:false` — poprawić izolację przed operacyjną integracją |
| `.github/workflows/worldpulse-nav-audit-v04.yml` | `workflow_dispatch`; publiczne kandydackie endpointy, artifact 7 dni | Zadeklarowany wynik metadata-only należy utrzymać i sprawdzić brak surowych cen w artifact; błędy HTTP nie uprawniają do fallbacku z innym providerem bez niezależnej kwalifikacji |
| `.github/workflows/v04-nbp-bondspot-calendar-e2e.yml` | `workflow_dispatch`; pobiera konkretne wcześniejsze artifacts z runów `42228167332` i `42238752683`; pobiera brakujące dokładne dni NBP | Kontrolować niezmienność oryginalnych receipt/hash oraz **retencję starszych artifact**; na dłuższy horyzont jawne SHA+archiwum z uprawnionym storage, bez zastępowania braków nowymi anonimowymi seriami |

## Reguły rekomendowane przed osobnym PR A2-provider

**MUST FIX:** (1) operator musi potwierdzić rzeczywiste warunki użycia/archiwizacji i zakres licencji źródła (zwłaszcza raw Vanguard/BondSpot); (2) rozdzielić artifact **surowy** od metadanych, dostępy i retencję; (3) dla każdego źródła zachować `retrieved_at`, oryginalną ścieżkę, raw checksum, `data_kind`, zastrzeżenie `PIT_UNVERIFIED`; (4) każdy tryb online ma pozostać `workflow_dispatch` i mieć review zakresu połączeń i uprawnień tokena przed merge; (5) nie uruchamiać tych workflowów w Draft PR #99 i nie scalać ich przypadkowo wraz z offline częścią.

**Nie twierdzimy:** że określony dostawca prawnie zabrania pobierania, że dane są w domenie publicznej, że SHA dowodzi autentyczności momentu publikacji, ani że sukces połączenia jest podstawą do rzeczywistych decyzji inwestycyjnych. To są otwarte punkty do weryfikacji z pierwotnymi warunkami źródła.

**Stan A2 offline:** [PR #99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99), 10 plików (8 oryginalnych blobów, dokumentacja, CI), 32/32 synthetic PASS w GitHub Actions [#42450845898](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42450845898). Pierwszy przebieg ujawnił brak `scripts.nbp_reference_capture.py` na main; poprawiono przez przeniesienie niezmienionego pliku, bez obniżania testów. Nie oznacza to realnych kwalifikowanych źródeł.

## Dalsza kolejność

1. Code review Draft #99 i analiza rzeczywistego diffu 10 plików.
2. Oddzielny A2-provider po formalnym zatwierdzeniu uprawnień danych; nie kopiować live workflowów do offline PR.
3. Split B (evidence ledger) i C (decision engine) na podstawie zależności; dopiero potem D (frozen NAV policy) i E (decision studies).
4. Przed merge do `main` uzgodnić overlap PR #96, #98 i #99 oraz repo branch-protection; bez przepisywania dowodów v0.22–v0.23.

Projekt wyłącznie badawczy, bez operacji finansowych.
