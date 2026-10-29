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
