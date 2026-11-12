# ISL Public-first v0.3 — prospektywne odczyty NBP + Eurostat

**Data początkowa:** 12.11.2026. **Issue:** [#150](https://github.com/gniewkob/Investment-Strategy-Lab/issues/150). **Cel:** obserwacja publicznych danych bez płatnych API, bez aktywów i bez modelu decyzyjnego.

## Podstawa źródłowa

- [NBP Web API](https://api.nbp.pl/) — oficjalny publiczny interfejs HTTPS: tabela A kursów średnich USD/PLN i EUR/PLN oraz ceny złota w PLN/g. Według dokumentacji zapytania o szeregi nie powinny obejmować okresów powyżej 93 dni. W projekcie dane walutowe to **kursy referencyjne**, złoto to **price-only**, żadne nie reprezentuje automatycznie total-return ani ceny wykonania.
- [Eurostat REST APIs, Introduction](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction) — publiczny, bezpłatny interfejs automatycznych zapytań. **API zawiera bieżącą wersję zbioru, bez historii wersji**, dlatego samo pobranie w 2026 r. nie dowodzi pierwotnego stanu publikacji z 2021 r.
- [Eurostat Copyright and free re-use](https://ec.europa.eu/eurostat/help/copyright-notice) — zwykłe dane statystyczne dostępne do ponownego wykorzystania z atrybucją; możliwe są wyjątki i prawa podmiotów trzecich. Zawsze należy zachować wskazanie Eurostat, identyfikator prc_hicp_minr i datę odczytu.

## Dostarczona funkcja

Nowy moduł scripts/public_first_prospective_source_observation_v03.py korzysta z istniejącego parsera NBP oraz HICP Eurostat. Jednorazowy odczyt zwraca wyłącznie:
- parę zakresów dat;
- **SHA-256 odpowiedzi źródłowych** NBP FX, NBP gold i kanonicznej odpowiedzi Eurostat;
- faktyczne znaczniki zakończenia odczytu według zegara procesu, czas aktualizacji deklarowany przez Eurostat jako osobne pole;
- liczby obserwacji, jawne jednostki i potwierdzone ograniczenia semantyczne;
- samokontrolny SHA-256 całego potwierdzenia (nie podpis kryptograficzny wydawcy).

Czysta funkcja compare_receipts(previous, current) dopuszcza porównanie TYLKO identycznych zakresów i ściśle późniejszego odczytu. Wykrywa CHANGED/UNCHANGED, ale nie wnioskuje o historycznych datach pierwszego udostępnienia ani nie wie, które konkretnie ceny zostały skorygowane. Jeżeli pierwszy odczyt nie istnieje, nie wolno tworzyć fikcyjnej historii. Hashe są wykryciem zmiany bajtów/kanonicznego JSON, nie niezależnym poświadczeniem pochodzenia lub zegara.

**Ważne:** workflow uruchamia jednorazowo publiczne odczyty i loguje tylko metadane. Nie tworzy długoterminowego archiwum oryginalnych bajtów. GitHub Actions mają ograniczoną retencję logów; aby tworzyć trwałą chronologię, trzeba później uruchomić kontrolowaną, append-only archiwizację w prywatnym magazynie, po osobnym przeglądzie bezpieczeństwa i praw do danych. Nie uruchamiamy automatycznego cron w tej zmianie.

## Jednorazowy test z publicznych źródeł

```sh
python3 -m unittest tests.test_public_first_prospective_source_observation_v03 -v

python3 -m scripts.public_first_prospective_source_observation_v03 \
  --nbp-start 2026-09-01 --nbp-end 2026-09-30 \
  --hicp-since 2026-08 --hicp-until 2026-09 \
  --allow-public-source-fetch
```

Wyjście zawiera tylko potwierdzenie ISL_PROSPECTIVE_PUBLIC_SOURCE_RECEIPT i hashe. W celu lokalnego porównania przyszłych potwierdzeń, zachowaj JSON (bez prefiksu tekstowego) w prywatnym pliku z prawami właściciela, a przy kolejnym odczycie tego samego okresu podaj --previous-receipt. Dokumentacja NIE twierdzi, że samo wywołanie tworzy trwały lub uwierzytelniony łańcuch PIT.

## Granice decyzji

Nie wykonujemy transakcji, rekomendacji aktywów, zleceń, operacji na portfelu, DB, tworzenia paper-events, automatycznej kwalifikacji źródeł ani działań na płatnych dostawcach. M1–M3 pozostają INSUFFICIENT_DATA/HOLD_CASH, bo cena złota i kursy walut nie są pełnymi seriami total-return, a HICP jest miarą cen konsumpcyjnych. Issue #116/#97/#123 i oddzielne kwestie bezpieczeństwa #138/#146 pozostają otwarte. To etap **prospektywnego monitorowania wersji danych publicznych**, nie akceptacja historycznej strategii.
