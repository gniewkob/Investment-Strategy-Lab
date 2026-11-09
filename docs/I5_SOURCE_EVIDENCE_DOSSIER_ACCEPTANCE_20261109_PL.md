# Investment Strategy Lab — I5: offline dossier kwalifikacji historycznych źródeł (2026-11-09)

**Rodzaj:** wewnętrzna kontrola projektowa, a nie certyfikacja prawna, audyt dostawcy ani zatwierdzenie do rzeczywistych transakcji. **Status:** `SOURCE_EVIDENCE_REVIEW_REQUIRED`. Powiązane: Draft I3 #111, Draft I4 #112, źródła A2 #99 i C2 #103, kwarantanna G1 #108.

## 1. Cel

Dotychczasowe audytory sprawdzają określone struktury plików, obserwacje i wewnętrzne SHA-256. **Żaden z nich nie dowodzi, że oryginalny dostawca był autentyczny, licencja obejmuje nasze przetwarzanie, dane były dostępne w danej historycznej chwili lub dało się wykonać transakcję po cenie indeksowej.** I5 normalizuje te ustalenia do jednego kontrolowanego, czytelnego rejestru braków.

Konkretne rodziny danych i kontrakty (bez pobierania ani udostępniania oryginalnych szeregów):
- `msci`: raport `ISL_ACWI_NETR_MONTHLY_INTAKE_V19_001`. Pięciokolumnowy CSV **nie zawiera pola waluty**; dopasowanie dat z NBP ma znaczenie wyłącznie diagnostyczne, a deklarowany `NETR` nie jest niezależnie potwierdzony.
- `vanguard`: raport offline audytora XLSX NAV USD `RAW_NAV_XLSX_CANDIDATE_NEEDS_PROVIDER_IDENTITY_ATTESTATION`. `NAV` nie jest automatycznie giełdową ceną wykonania, a 60 miesięcy w syntetycznej fixturze nie jest 60 miesiącami dopuszczonego benchmarku.
- `reference`: raport `ISL_REAL_REFERENCE_GATEWAY_V18_001`. NBP gold price (nie kompletny total return), NBP FX rate i BondSpot TBSP (niewykonywalny indeks) pozostają materiałem referencyjnym.

## 2. Nowy kontrakt

`scripts/source_evidence_dossier_v01.py` przyjmuje **wyniki wcześniejszych lokalnych audytorów**, nie surowy dostęp do MSCI, Vanguard, NBP lub BondSpot. Wszystkie trzy wejścia są opcjonalne — brak danych daje jawne `NO_REPORT_AVAILABLE`, nigdy domyślną zgodę.

Walidator wymaga:
- dokładnej znanej struktury raportu bez dodatkowych pól typu `rights_approved`;
- poprawności **wewnętrznego** SHA-256 raportu oraz jawnego SHA-256 bajtów źródłowych deklarowanego w raporcie;
- prawidłowych statusów `unverified`, zgodności kalendarza i typu danych;
- fałszywych wartości przy wszystkich flagach niezależnej weryfikacji praw, waluty, instrumentu, PIT i wykonania;
- zerowej liczby operacji finansowych lub zapisu bazy.

**Uwaga o dowodach:** każdy może ponownie obliczyć zwykły SHA-256 po zmianie treści. Skrót w raporcie dowodzi więc co najwyżej spójności jego zawartości, **nie** pochodzenia, prawa do korzystania ani pierwszej daty publikacji. I5 nie przyjmuje samodzielnie ustawianej wartości `license_verified=true` jako potwierdzenia.

Wyjście raportuje dla każdej z trzech rodzin aktywów listę wymaganych **niezależnych** dowodów. W razie braku dowodów wszystkie modele mają `HOLD_CASH`; `qualified_model_series=[]`, `paper_candidates=[]`, `source_manifest_created=false`, `market_execution_authorized=false`. Potwierdzane jest również `0` zleceń, transferów, paper fills i zapisów DB.

**Redakcja danych:** dane `monthly[].nav_usd` z wejścia Vanguard nie trafiają do dokumentu wynikowego. W dossier pozostają jedynie typ kandydata, liczba miesięcy, SHA oryginalnego eksportu *według raportu* i SHA wewnętrznego audytu; podobnie nie są kopiowane poziomy indeksu MSCI. Nie zapisywać plików dostawców w GitHub ani w logach CI.

## 3. Lista brakujących dowodów i odpowiedzialność

| Rodzina docelowa | Braki blokujące | Preferowany właściciel dowodu |
|---|---|---|
| `GLOBAL_EQUITY_TR_PLN` | tożsamość indeksu/ETF, prawo do konkretnego datasetu i retencji, waluta i sposób rekonstrukcji TR w PLN, historyczny `first_available_at`, odrębna cena transakcyjna | właściciel danych + reviewer praw/źródła + reviewer modeli |
| `PL_BONDS_TR_PLN` | oficjalna metodologia TBSP i forma oryginału, prawo do danych, transformacja do PLN TR, historyczne vintages, dostępny instrument i koszty | właściciel danych + reviewer źródła + reviewer modeli |
| `GOLD_TR_PLN` | cena referencyjna ≠ pełny return z inwestycji; prawa, model kosztów i PLN total return, historyczna data publikacji, cena realnego instrumentu | właściciel danych + reviewer modeli |

To podział ról **zaproponowany przez projekt**, nie twierdzenie o obowiązku ustawowym lub certyfikacie NIST/ISO.

## 4. Użycie lokalne wyłącznie offline

Po uzyskaniu **uprawnionych** do użycia lokalnie raportów z uprzednio uruchomionych audytorów:

```bash
python -m scripts.source_evidence_dossier_v01 \
  --msci-report /path/to/msci-audit-metadata.json \
  --vanguard-report /path/to/vanguard-audit-metadata.json \
  --reference-report /path/to/nbp-bondspot-gateway-metadata.json
```

Można podać tylko jedną lub dwie opcje, albo żadnej — wtedy braki pozostają widoczne. Polecenie wypisuje jeden rekord `ISL_I5_EVIDENCE_DOSSIER`; **nie wykonuje pobierania, żadnego realnego paper trading ani zleceń**.

## 5. Kryteria odbioru

`tests/test_source_evidence_dossier_v01.py`: 18 testów negatywnych i deterministycznych. Testy generują sztuczne dane MSCI/NBP i sztuczny XLSX Vanguard oraz wykorzystują poprzednie offline audytory. Próby sfałszowania `PIT`, `source rights`, waluty, TR, stanu konta i cen (nawet z poprawnie ponownie policzonym SHA-256) nie dają kwalifikacji. Potwierdzane są: `HOLD_CASH`, brak kopiowania oryginalnych NAV do wyników, brak skutków ubocznych oraz poprawność listy wymagań.

Nowy read-only CI `.github/workflows/isl-i5-source-evidence-dossier-ci.yml` oczekuje **51 testów na Ubuntu i 51 na macOS** (18 I5 + 14 MSCI + 12 Vanguard + 7 NBP/BondSpot), blokuje połączenia Python socket i nie ma `schedule`, `push`, sekretów ani tokena write. **Nie uznawać implementacji za przyjętą przed udanym CI na końcowym SHA.**

## 6. Zasady i źródła pomocnicze

- [MSCI — Terms of Use, sekcja 4 (Restrictions on Use)](https://www.msci.com/legal/terms-of-use): warunki ograniczające nieautoryzowane automatyczne pobieranie i wykorzystanie; należy sprawdzić konkretną umowę/licencję i ścieżkę dostępu.
- [MSCI — Index Terms](https://www.msci.com/legal/index-terms): dodatkowe warunki materiałów indeksowych; sama obecność danych nie jest przyznaniem licencji.
- [Vanguard — Terms and Conditions](https://www.vanguard.co.uk/professional/terms-and-conditions): należy odróżnić możliwość pobrania eksportu od dopuszczalnego zakresu wykorzystania i retencji.
- [Vanguard — FTSE All-World UCITS ETF](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits): osobne kategorie NAV i rynkowej wyceny funduszu.
- [NBP — API](https://api.nbp.pl/), [BondSpot — TBSP](https://www.bondspot.pl/): oficjalne punkty odniesienia do ustalenia kontraktu danych, nie samodzielne dowody prawa do wykonywania strategii po tych cenach.

Wymagania I5 dotyczące dokumentacji uprawnień, rozdzielenia źródła od ceny wykonania i niezależnego historycznego PIT są **naszymi kontrolami projektowymi**. Zbiorczy raport nie certyfikuje prawnego statusu konkretnego eksportu ani nie zastępuje oceny prawnika lub dostawcy.

**Ograniczenie dodatkowe:** I5 chroni określoną ścieżkę metadanych i nie zapobiega temu, że ktoś zbuduje nowy, niezależny adapter o słabszych kontrolach. Z tego powodu istniejące bramki I4 i G1 oraz review kodu nadal pozostają wymagane.

**Decyzja:** `I5_SOURCE_EVIDENCE_GAPS_RECORDED`; `INSUFFICIENT_DATA/HOLD_CASH` do czasu udokumentowania i niezależnej weryfikacji rzeczywistych historycznych źródeł, bez zmiany aktywów.
