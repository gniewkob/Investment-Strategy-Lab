# NBP — odświeżenie danych w prywatnym laboratorium, 5 listopada 2026

## Rezultat: PASS, rzeczywisty odczyt, rzeczywisty zapis w Neon LAB

Źródło: oficjalne [NBP Web API](https://api.nbp.pl/), wyłącznie HTTPS:
- tabela A: https://api.nbp.pl/api/exchangerates/tables/a/2026-10-17/2026-11-05/?format=json
- cena złota: https://api.nbp.pl/api/cenyzlota/2026-10-17/2026-11-05/?format=json

Wykonanie: [GitHub Actions #42125232416](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42125232416).
Dane pobrano 2026-11-05 około 22:53 UTC i zapisano w głównym
Neon LAB 2026-11-05 22:56:23.935 UTC.

- USD/PLN NBP tabela A: 14 publikacji (19.10–05.11.2026);
- EUR/PLN NBP tabela A: 14 publikacji (19.10–05.11.2026);
- złoto referencyjne NBP, PLN/g: 14 publikacji (19.10–05.11.2026).
- Łącznie: **42 rzeczywiste rekordy**. Przed importem 0 istniejących
  w badanym zakresie; konflikty 0.
- Najpierw import kontrolny w osobnej gałęzi
  \`br-purple-night-ba3e6uwv\`: 42 nowe obserwacje + 1 wpis audytu,
  weryfikacja chronologii 0 naruszeń.
- Następnie identyczny import w głównym prywatnym laboratorium:
  Neon project \`red-lake-53043722\`, branch \`br-shy-voice-badzlf0x\`,
  database/schema \`investment_lab\`, 42 nowe obserwacje + 1 audyt
  (bez UPDATE istniejących cen).
- Identyfikator audytu:
  \`nbp-ref-20261017-20261105-a2b1f2dd0f58-033ac61d4afb\`.
- SHA-256 odpowiedzi RAW FX:
  \`a2b1f2dd0f58e20857ed0adbf52b469e737a958318a78c9545fcdf4a8aba0fa1\`.
- SHA-256 odpowiedzi RAW złoto:
  \`033ac61d4afbebe41d85e24998bbb6f527a90621775bb63ba74d0c0b1b4b8140\`.
- Oryginalna historyczna godzina publikacji i pierwotny vintage
  wciąż NIE są certyfikowane; czas pobrania jest rzeczywisty.
- NBP złoto = cena referencyjna 1 g, a NIE total return;
  kursy NBP FX = kursy średnie tabeli A, a NIE ceny transakcyjne.

## Weryfikacja po wykonaniu

Niezależny SQL na Neon main:
- 14/14/14 rekordów w wskazanym przedziale, ostatnie observed_for 05.11;
- ENGINE_OK 3/3 dla cyklu badawczego, SOURCE_RECENT 3/3 dla
  trzech źródeł NBP (wcześniej SOURCE_STALE);
- research_runs 3 (nie tworzono nowych cykli badawczych podczas importu),
  paper_events 3 (historyczne wkłady), paper_fills 0;
- 1 nowy wpis audytowy NBP z URL, raw hash i datami pobrania;
- żadne zlecenia, przewalutowania, transfery, płatności ani realne
  operacje finansowe nie były wykonywane.

Ważna zasada czasu: import wykonano PO cutoff 2026-11-05 19:00 UTC.
Cykle z takim cutoff nie mogą wykorzystywać tych danych wstecznie.
Pierwszy prawidłowy cutoff obejmujący import to
2026-11-06 19:00 UTC, a poranna automatyzacja może go ocenić
najwcześniej 2026-11-07 czasu Europe/Warsaw.

## Trwała implementacja

- \`scripts/nbp_reference_capture.py\`: współdzielony oficjalny
  adapter NBP z PR #93, włączony do gałęzi silnika PR #95;
- \`scripts/nbp_lab_prepare.py\`: normalizacja faktycznej odpowiedzi
  oraz rejestr źródła i SHA-256, bez dostępu do DB;
- \`scripts/nbp_lab_ingest_sql.py\`: kompilator pojedynczego
  idempotentnego INSERT/ON CONFLICT DO NOTHING + audyt tylko
  faktycznie nowych obserwacji, bez łączności DB;
- \`tests/test_nbp_lab_prepare.py\` i
  \`tests/test_nbp_lab_ingest_sql.py\`: 10 testów offline;
- \`tests/integration/test_working_engine_v01.py\`: test rzeczywistego
  zapisu SQL na jednorazowym PostgreSQL, ponowienia bez duplikatów
  i wykrycia konfliktu, łącznie 6 testów integracyjnych;
- \`working-engine-v01-ci.yml\`: [CI #42126602365](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42126602365)
  SUCCESS (5 + 5 offline + 6 integracyjnych);
- \`nbp-reference-live-probe.yml\`: [CI #42126602540](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42126602540)
  SUCCESS (5 offline i udany read-only live probe).

**Granica automatyzacji:** działające codzienne zadanie
„Surowce i geopolityka” zawiera cykl silnika M1/M2/M3.
Automatyczny, cykliczny IMPORT danych NBP do Neon nie jest jeszcze
samodzielnie potwierdzony. GH workflow w gałęzi Draft PR nie jest
samodzielnym harmonogramem ingestu. Nie twierdzić, że zadziała
bez GitHub runnera/Neon connectora oraz zweryfikowanej ścieżki
uruchomienia z nową datą.

## Odbiór następnego etapu

Dwa naturalne, kolejne cykle badanego silnika z różnych dni,
odczyt ich trzech hashy/audytu z Neon oraz poprawne rozdzielenie
freshness źródeł od \`INSUFFICIENT_DATA\` modeli.
Równolegle uruchomić powtarzalny odczyt i idempotentne uzupełnienie
NBP bez ręcznego przeklejania źródłowej odpowiedzi. Jest to kolejny
komponent funkcjonalności, NIE temat wyglądu czy produkcji.
