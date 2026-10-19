# WTI EIA: zamrożony audyt kompletności źródeł (tylko odczyt)

**Cel:** powtarzalny dowód, że znany zakres 35 brakujących notowań WTI wynika z porównania oficjalnej obecnej tabeli EIA z **lokalnym, wcześniej autoryzowanym** wyciągiem wyłącznie publicznych cen referencyjnych. Bez połączenia z Neon, kopiowania danych portfela i bez zapisywania cen.

## Stan źródeł i wcześniejszy dowód

[Pełne odczytowe porównanie z 19.10.2026](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6270375923) obejmowało 2024-01-02..2026-10-14. Według **obecnej wówczas** tabeli EIA: WTI 695 dat i wartości; zapisane w Neon STAGING 660 zgodnych; dokładnie 35 brakujących obserwacji od 2026-08-26 do 2026-10-14; 0 różnic wartości. Brent 706/706 zgodnych. Nie zidentyfikowano pierwotnej przyczyny zatrzymania wsadu ani daty pierwszej publikacji każdej ceny.

Zobacz również [Source EIA read-only](EIA_READ_ONLY_AUDIT_PL.md). Kod bazuje na tym samym parsowaniu strony i porównaniu dat/cen, bez alternatywnego importera.

## Nowe zabezpieczenie kontraktowe

Skrypt `scripts/eia_wti_gap_receipt.py` wymaga jawnego, **ustalonego przed odczytem**: początku i końca badanej historii, ostatniej daty zapisanej lokalnie, daty konkretnego wydania EIA oraz oczekiwanej liczby braków. Porównuje daty i wartości na całym oknie. Odrzuca:

- choćby jedną nieobecną lub odmienną cenę na dacie *przed* ostatnią zapisaną datą, brak końców okna, ceny poza oficjalnym kalendarzem EIA, dane lokalne po zadeklarowanym końcu lokalnej historii;
- inne niż oczekiwane liczby braków po końcu lokalnej historii albo zmieniony dzień wydania EIA;
- niepoprawny SHA-256, a opcjonalnie także stronę o innym SHA-256 niż zaakceptowany wcześniejszy hash oryginalnego HTML;
- niewłaściwe źródło (Brent zamiast WTI), znacznik pobrania z przyszłości względem wydania, fałszywe daty i błędny format CSV.

Plik wejściowy jest czytany **raz** z limitem 1 MB, parsowany i hashowany SHA-256 z dokładnie tych samych bajtów. To wiąże raport z porównywanym plikiem, ale samo nie dowodzi autentyczności lokalnego CSV. SHA-256 HTML dotyczy oryginalnych bajtów bieżącej oficjalnej odpowiedzi, nie rekonstrukcji dawnego artykułu.

## Wywołanie wyłącznie lokalne

Przykład kontraktu właściwego dla **wydania EIA z 15.10.2026** (gdy strona EIA nadal udostępnia *to samo* wydanie):

    python -m scripts.eia_wti_gap_receipt \
      --reference-csv /local-only/authorized-public-wti-reference.csv \
      --first-observed-for 2024-01-02 \
      --last-observed-for 2026-10-14 \
      --last-stored-observed-for 2026-08-25 \
      --expected-source-release 2026-10-15 \
      --expected-missing 35 \
      --max-age-days 1100

Jeżeli EIA opublikuje nowsze wydanie, powyższy zamrożony kontrakt **celowo nie przejdzie**. Nie należy podmieniać dat po cichu. Nowy kontrakt wymaga świeżego porównania kalendarza i cen, nowych dowodów oraz oznaczenia nowej rewizji. Opcjonalny `--expected-source-sha256` dodatkowo wiąże kontrakt z pierwotnymi bajtami zatwierdzonego pobrania.

Nie wolno podawać do pliku wejściowego sekretów, kont, pozycji, sald ani prywatnych danych portfela. Schemat jest ściśle ograniczony do `instrument_code,observed_for,close_price`. Skrypt nie eksportuje surowych cen. Raport zawiera liczniki, daty braków, SHA-256, faktyczny czas pobrania i datę wydania bieżącej strony.

## Niepotwierdzone w dalszym ciągu

Nie ma **źródłowej historii dat pierwszej publikacji** poszczególnych obserwacji. `observed_for` nie jest `published_at`, a release nowej strony EIA nie dowodzi dostępności ceny w przeszłości. Raport utrzymuje `UNVERIFIED_HISTORICAL_PUBLICATION`, `backfill_authorized=false`, `independent_point_in_time_market_data_certified=false` i 0 zapisów.

Testy PR i na main są syntetyczne/offline. Nowy moduł nie czyta Neon i nie pozyskuje lokalnego CSV z GitHub Actions ani nie uruchamia się według harmonogramu. Przygotowanie źródłowo poświadczonego importu oraz **każdy INSERT do Neon STAGING** wymaga osobnego uzgodnienia. Produkcja, uprawnienia, hasła, portfolio, transakcje i modele M1/M2/M3 pozostają bez zmian (`HOLD_NO_CHANGE`).

Otwarte zadania: [#22 — WTI](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22) i [#2 — oryginalne dokumenty publikacji PIT](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2).
