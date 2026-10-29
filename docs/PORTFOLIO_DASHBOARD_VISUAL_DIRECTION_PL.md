# ISL — projekt wizualny prywatnego panelu (WDI / apple-design)

Data decyzji: 2026-10-29. Dotyczy **jedynie** lokalnego, statycznego renderer-a
`scripts/private_portfolio_dashboard.py` w integracyjnym PR #87.

## Cel i nienaruszalny kontrakt

Ułatwić szybki odczyt stanu systemu obserwacyjnego: najpierw wiarygodność
i zakres wyceny, później pozycje, źródła, ciągłość historii, RPC i wynik
fikcyjnej symulacji. Nie zmienia się żadna operacja Coinbase/Wallet, RPC,
Neon, harmonogram, klucz, API, output path ani mechanizm zapisu 0600.

`apple-design` jest już dostępny jako skill w zainstalowanej wtyczce
`web-design-intelligence`. Zastosowane zasady: przejrzysta hierarchia,
proporcjonalne odstępy, subtelne warstwy, konsekwentne typografie systemowe,
wskazanie aktualnego stanu bez dekoracyjnego ruchu. Nie kopiujemy
chronionych elementów UI Apple i nie instalujemy nowego frameworka.

## Kierunki i wybór

- Alternatywa A — klasyczny ciemny ekran telemetryczny z gęstymi tabelami,
  mało miejsca na objaśnienia. Odrzucona: zbyt łatwo pomylić „OK” z dowodem
  pełnej wartości portfela.
- Alternatywa B — cichy, warstwowy research workspace z częściową wyceną
  na pierwszym planie, statusem oddzielnie, jasnymi objaśnieniami zakresu
  i dużą nawigacją do szczegółów. **Wybrana**.

Kolejność: nagłówek/nawigacja → częściowa wycena + ostatni status →
liczba źródeł, nieznanych cen i alertów → HOLD_NO_CHANGE →
pozycje → integralność wyceny → źródła → historia/RPC →
paper benchmark → alerty.

## Tokeny / komponenty

- Kolory semantyczne o wysokiej czytelności: ciemny grafitowy canvas,
  neutralne powierzchnie i granatowe obramowania, jeden błękitny akcent,
  zielony dla OK i bursztynowy dla PARTIAL/ostrzeżeń.
- Automatyczny jasny wariant przez `prefers-color-scheme:light`.
  Preferencja urządzenia, bez JavaScript i trwałych ustawień użytkownika.
- Typografia: wyłącznie fonty systemowe; numery tabularne;
  rozmiary płynne `clamp`; bez CDN/fontów zewnętrznych.
- Układ: maksymalna szerokość 1240px, wyróżniona pierwsza karta,
  siatka 2 kolumny dla treści i 3 mini-KPI, zejście do jednej
  kolumny <=900px i 2 mini-KPI <=620px.
- Statyczna nawigacja kotwicami HTML; `skip link`, semantyczne
  `main`, `section`, `nav`, `h1/h2`, tabele z nagłówkami,
  regiony przewijane poziomo dostępne klawiaturą, czytelny focus.
- Ruch: tylko dyskretne podświetlenie pozycji nawigacji i zwykły
  przewijanie do kotwicy; wyłączane przy `prefers-reduced-motion`.
- Żadnych wykresów z wymyślonymi danymi, interaktywnych fikcyjnych
  przycisków, dźwięków, zewnętrznej telemetrii ani nowych requestów.
- Statyczny CSP `default-src 'none'; style-src 'unsafe-inline'`;
  zachowano 60-sekundowe odświeżanie zawartości pliku.

## Obowiązkowa uczciwość danych

- „Wycena częściowa PLN” **nie** jest pełnym net worth.
- Brak wyceny / niezweryfikowane pozycje ≠ 0 PLN.
- Status ma być opisany jako **ostatni zapisany cykl**, nie „teraz online”.
- `rpc_diagnostics` dotyczy tylko ostatniego cyklu Ethereum/Base; brak
  lub zły schemat = UNKNOWN, nie 0 HTTP429.
- `history_failure_categories` są z góry ograniczone przez producenta,
  a renderer również nie pokazuje surowego niebezpiecznego tekstu.
- `paper_simulation` pokazuje dane tylko z bieżącego statusu OK.
- Nienaruszalne `HOLD_NO_CHANGE`; zero operacji finansowych.

## QA / bramki wdrożeniowe

| Kontrola | Dowód / status |
| --- | --- |
| Renderer nie wywołuje sieci i nie wymaga JS | Statyczna kontrola kodu |
| Testy jednostkowe istniejącego kontraktu, XSS i braku wycen | GitHub Actions dla konkretnego SHA |
| HTML landmark, skip link, focus, tabular nums, media queries | Statyczna kontrola i testy |
| Rzeczywisty widok 375/768/1280/1440 px | **DO WYKONANIA** na Macu |
| VoiceOver, zoom 200%, klawiatura, kontrast i forced colors | **DO WYKONANIA** na Macu |
| Rzeczywisty pełny odbiór 24h i deploy | **POZA ZAKRESEM**, nadal PARTIAL |

Dopiero po kontroli rzeczywistego renderu można twierdzić,
że layout został przetestowany wizualnie; zielone CI Python nie
certyfikuje zgodności WCAG ani poprawności we wszystkich przeglądarkach.


## Odbiór Chromium — rzeczywisty render syntetycznego HTML (2026-10-29)

Dodano `scripts/private_dashboard_browser_qa.py` i odizolowany workflow
`.github/workflows/private-dashboard-browser-qa.yml`, uruchamiany w
Playwright/Chromium na Ubuntu 24.04. Jest to **automatyczny test browserowy**
bez podłączenia rzeczywistego `portfolio.json`, Coinbase, Neon, RPC
lub jakichkolwiek poświadczeń. Artefakt z sześcioma zrzutami i
`browser-qa.json`:
https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/40946330926

Przebadane rzeczywiste renderingi: 375×812 dark, 768×1024 dark,
1280×800 dark, 1440×900 dark, 1280×800 light,
375×812 light/reduced-motion. **6/6 PASS**: szerokość dokumentu
nie przekracza viewportu, wszystkie kotwice nawigacji działają i są
widoczne, cele dotykowe >=44 px, brak JS/pageerror i zewnętrznych
HTTP requestów, wskazówki przewijania tabel na małych viewportach,
prawidłowy tryb reduced-motion oraz komplet źródeł.

### Dwie znalezione i naprawione usterki

1. Na pierwotnym renderze przy szerokości 375 px link do
   „Symulacji” był poza widoczną częścią przewijanej poziomo
   nawigacji, bez wskazówki. Menu mobilne zawija się obecnie do
   kolejnego wiersza, wszystkie pięć linków jest widocznych.
   Nowy test `all_nav_links_visible` sprawdza położenie linków
   względem dostępnego obszaru nawigacji.
2. Na pierwotnym renderze 375 px w tabeli RPC nazwy sieci
   „Ethereum” i „Base” zawijały się niemal znak po znaku.
   Dodano `rpc-table`, kolumnę sieci z `white-space:nowrap`,
   `min-width:114px`, przyklejoną do lewej krawędzi przy
   przewijaniu, oraz wyraźną wskazówkę przewijania tabeli.
   Nowy test `rpc_network_names_unwrapped` potwierdza
   jednowierszowe etykiety w sześciu konfiguracjach przeglądarki.

Dokładny commit zamykający te poprawki:
`0966009e6daff8234b0d82ba75d663e60fc00ec2`.
CI pełna regresja offline **597/597 PASS**:
https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/40946330929 .
Trzy pozostałe workflowy, poza Chromium, również SUCCESS.

Po dodatkowym manualnym obejrzeniu wygenerowanych screenshotów
mobile/desktop/light potwierdzono poprawne ułożenie kart i tabel
w tych przykładach. Ten odbiór nie stanowi certyfikacji WCAG 2.2 AA:
VoiceOver, zoom 200%, forced colors i rzeczywiste urządzenia
Apple pozostają **NOT TESTED**. Lokalna produkcja, usługi launchd,
checkpointy i finanse nie były zmieniane. Status 24h pozostaje PARTIAL.
