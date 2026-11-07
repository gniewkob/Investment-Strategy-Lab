# Investment Strategy Lab v0.19 — kandydat MSCI ACWI NETR USD, legalny offline intake

**Cel:** uruchomić rzeczywistą ścieżkę M1 z indeksem globalnych akcji. Nie uznawać opisu na stronie za pobraną pełną historię ani certyfikat praw do danych.

## Oficjalne źródła i ograniczenie dostępu

- MSCI ACWI, index code na stronie publicznej **892400**, obejmuje duże i średnie spółki rynków rozwiniętych i wschodzących; strona umożliwia wybranie poziomu `Net` i waluty USD: https://www.msci.com/indexes/index/892400/msci-acwi-index
- CFA Institute udostępnia **członkom** miesięczne pliki MSCI z kolumnami `Date` (DD/MM/YYYY), `Code`, `Index name`, `Index variant` (STDR/GRTR/NETR), `Index level`. Wariant NETR obejmuje dywidendy po podatku: https://rpc.cfainstitute.org/msci
- Publiczny serwis MSCI zastrzega prawa kopiowania, redystrybucji i tworzenia pochodnych indeksów/usług bez odpowiedniej zgody: https://www.msci.com/data-and-analytics/index-data
- MSCI oferuje także płatny/kontraktowy Index API z danymi historycznymi, którego dostępności w tym środowisku nie potwierdzono: https://developer.msci.com/apis/index-api

**Wniosek:** samo pojawienie się publicznego poziomu indeksu albo pobranie pliku przez członka nie oznacza automatycznie prawa do dalszej publikacji, użycia w tej aplikacji, przeliczenia na własny benchmark PLN lub redystrybucji. Nie wykonujemy automatycznego pobierania, obchodzenia logowania ani scrapingowej rekonstrukcji 60 miesięcy.

## Implementacja

`scripts/acwi_netr_offline_intake_v19.py` jest odizolowanym offline parserem **tylko oryginalnego pliku CSV pozyskanego dozwoloną drogą**, zewnętrznie dostarczonego operatorowi. Oczekuje wyżej opisanych pięciu nagłówków, wybiera wyłącznie `MSCI ACWI` / `MSCI ACWI INDEX` z wariantem `NETR`, wyklucza STDR/GRTR i inne indeksy; odrzuca duplikaty, luki miesięcy, złą datę, nieprawidłową walutę/semantykę, nieliczbowe/ujemne wartości i przyszłe daty. Liczy hash oryginalnych bajtów.

Dodatkowo odczytuje **osobny oryginalny archiwum NBP** z `scripts/nbp_long_history_monthly.py`, sprawdza `evidence_sha256`, klasyfikuje `USDPLN` jako `FX_RATE` i raportuje, dla ilu dat MSCI istnieje kurs NBP z **tej samej daty**. Nie interpoluje, nie bierze kursu następnego dnia ani kursu bieżącego. To szczególnie ważne, gdy ostatni dzień pracy MSCI i ostatni dzień roboczy NBP są inne. Parser nie tworzy własnego `GLOBAL_EQUITY_TR_PLN` ani zmienionego benchmarku.

Wynik `ISL_ACWI_NETR_INTAKE_V19` zawiera: hash CSV, hash archiwum NBP, liczbę miesięcy, zakres, podsumowanie dopasowania FX, brakujące miesiące dokładnego FX i powody braku kwalifikacji. **Nie wypisuje cen indeksu ani FX**. `eligible_M1=false`, `pln_tr_model_qualification=BLOCKED_UNVERIFIED_RIGHTS_AND_PIT`, `estimated_returns=null` nawet w syntetycznie kompletnym przykładzie.

## Bezpieczne wywołanie — dopiero po legalnym uzyskaniu eksportu

```bash
python3 -m unittest discover -s tests -p 'test_acwi_netr_offline_intake_v19.py' -v
python3 -m scripts.acwi_netr_offline_intake_v19 \
  --msci-csv '/prywatna/sciezka/do/licencjonowanego/oryginalnego-msci.csv' \
  --nbp-archive '/prywatna/sciezka/do/nbp-official-archive.json' \
  --as-of-utc '2026-11-07T16:00:00Z'
```

Nie dodawać pobranych danych do publicznego GitHub, nie podawać loginów ani plików źródłowych w komentarzach PR.

## Odbiór

- **TECHNICAL PASS**: zielona dedykowana regresja i Working Engine na dokładnym SHA.
- **REAL ORIGINAL MSCI CSV**: NOT_RECEIVED / format nieprzetestowany na faktycznym pliku — brak uzasadnienia do statusu źródła `VERIFIED_ORIGINAL`.
- **Legalne prawo przetwarzania i użycia danych**: UNVERIFIED; nie obchodzić tej kwestii przez kopie i mirrory.
- **Historyczne timestamps PIT**: UNVERIFIED; przyszłe pobranie w 2026 nie certyfikuje dawnej daty dostępności.
- **Dokładne daty USDPLN**: zależne od rzeczywistego pliku, nie wolno imputować.
- **M1 real historical acceptance**: BLOCKED.
- **M2/M3 real historical acceptance**: BLOCKED niezależnie z powodu brakujących serii.

**Następny funkcjonalny etap:** pozyskać dozwolony pełny eksport, rozpoznać faktyczny format, niezależnie potwierdzić licencję i własność danych, sprawdzić daty NBP i zbudować odrębny, niewykonalny benchmark PLN; dopiero potem feed do v0.17, bez deklarowania ceny giełdowej ETF ani faktycznego wykonania transakcji. Jeżeli dostępu nie uda się zdobyć, badać alternatywne oficjalne źródła z jasnymi uprawnieniami, nie wykonywać nielegalnej rekonstrukcji.

DR offsite pozostaje LOW/BACKLOG. Realne fundusze, portfele, Neon i scheduler bez zmian.
