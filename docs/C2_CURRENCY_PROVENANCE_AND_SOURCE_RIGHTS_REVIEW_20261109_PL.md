# Investment Strategy Lab — C2: waluta indeksu i prawa do źródeł (2026-11-09)

**Zakres:** odrębna walidacja metadanych dla Draft PR #103, skrypt `scripts/acwi_netr_offline_intake_v19.py`. Kod i testy są offline, syntetyczne, nie zawierają oryginalnych poziomów indeksu MSCI i nie uruchamiają źródeł. **To nie jest ocena licencji użytkownika ani dopuszczenie do obrotu aktywami.**

## 1. Wykryty błąd semantyki źródła — MUST FIX

Wejściowy plik CSV ma dokładnie pięć kolumn: `Date,Code,Index name,Index variant,Index level`. **Nie zawiera waluty ani pisemnego, niezależnego potwierdzenia tożsamości wariantu.** W poprzednim kodzie przy każdym poprawnie sformatowanym CSV wpisywano `claimed_currency = USD`, chociaż ta informacja **nie wynika z pliku**. Dodatkowo zgodność dat z publicznym archiwum NBP `usdpln` mogła sugerować konwersję, mimo że skrypt nie wykonuje takiego przeliczenia.

Takie oznaczenie jest nieprawidłowe także dla syntetycznych fixture'ów. Nawet 36/36 dopasowań dat nie uprawnia do stwierdzenia, że poziom indeksu był w USD, że dostępny kurs reprezentuje historyczną cenę wykonania, ani że można go wykorzystać do polskiego total return.

## 2. Zmiana — fail-closed

- `claimed_currency: UNKNOWN_NOT_IN_SOURCE_CSV`, a także `source_currency_independently_verified: false`. Nie ma automatycznej kwalifikacji pary USD/PLN na podstawie samej nazwy indeksu.
- `usd_pln_conversion_performed: false` oraz `nbp_fx_date_matches_are_diagnostic_only: true`, niezależnie od liczby dopasowań kalendarza.
- `claimed_return_basis: NET_TOTAL_RETURN` pozostaje opisem wariantu `NETR` z treści CSV, **nie** niezależnie uwierzytelnioną informacją — jawne `claimed_return_basis_independently_verified: false`.
- `eligible_M1: false`, `pln_tr_model_qualification: BLOCKED_UNVERIFIED_RIGHTS_AND_PIT`, `estimated_returns: null` pozostają bez zmian; nie powstaje ani jedna decyzja o inwestycji.
- Dodano dwa testy syntetyczne: komplet dat FX i brak dopasowań muszą mieć identyczną, ostrożną kwalifikację waluty. CI na Linux/macOS sprawdza teraz **21 testów**, z wyłączonymi połączeniami Python socket.

## 3. Źródła pierwotne, zakres dowodu i wymagania projektu

| Stwierdzenie | Weryfikowalny dokument | Precyzyjny zakres |
|---|---|---|
| Dane MSCI z witryny są zasadniczo do wykorzystania informacyjnego, niekomercyjnego; powielanie/redystrybucja wymagają odrębnych uprawnień | [MSCI — Index Terms](https://www.msci.com/legal/index-terms), akapity dotyczące **Additional Terms of Use** | Warunki dotyczą danych MSCI na wskazanej witrynie; należy osobno zweryfikować konkretną licencję i ścieżkę dostępu użytkownika |
| Zakaz nieautoryzowanego automatycznego pozyskiwania obejmuje m.in. boty, AI agents i MCP | [MSCI — Terms of use](https://www.msci.com/legal/terms-of-use), wydanie 15.07.2026, **Section 4. Restrictions on Use (viii)** | Nie jest to dowód, że każdy ręczny eksport jest zakazany; jest powodem do **wstrzymania automatycznego pobierania** bez dokumentów uprawniających |
| Ograniczenia wykorzystania informacji MSCI z systemami AI | [MSCI — Notice & Disclaimer](https://www.msci.com/legal/notice-and-disclaimer), akapit **Unless you contact MSCI and receive its prior written permission** | Nie twierdzimy, że sam dostęp do portalu nadaje prawo do wprowadzenia indeksu do aplikacji analitycznej/AI |
| Instrument Vanguard `IE00BK5BQT80` ma osobne dane NAV USD i cenę rynkową w walucie notowania | [Vanguard — FTSE All-World UCITS ETF USD Accumulating](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits) — **Prices and distribution**, **Historical Prices** | NAV funduszu i cena giełdowa to różne typy; ich obecność nie upoważnia do uznania pierwszej za cenę wykonania |
| Materiały Vanguard obejmuje ograniczona licencja informacyjna, z dodatkowymi ograniczeniami automatyzacji i dalszego wykorzystania | [Vanguard UK Professional — Terms and Conditions](https://www.vanguard.co.uk/professional/terms-and-conditions), **User license** | Reguły korzystania z tego serwisu; nie są ogólnym prawem zakazującym wszystkich badań |

**Kontrole projektowe, nie automatyczne obowiązki prawne:** dla rzeczywistych danych wymagać oddzielnego dowodu praw do konkretnego datasetu, źródłowego dokumentu waluty i wariantu indeksu, daty pierwszego dopuszczenia obserwacji, wersji publikacji, oryginalnego checksum oraz precyzyjnego harmonogramu dostępności. Obecny pięciokolumnowy CSV **nie zawiera** wystarczających pól. Nie rozszerzać kontraktu przez wpisanie na sztywno USD ani przez domniemany kurs PLN.

## 4. Rekomendowana sekwencja praktyczna

1. **Bez uruchamiania providerów:** wybrać kandydatów do ręcznej, legalnej oceny danych. Vanguard NAV USD Acc pozostaje warunkowym odniesieniem do badania rachunkowości, nie zakwalifikowanym `GLOBAL_EQUITY_TR_PLN`; MSCI pozostaje kandydatem **rights/PIT HOLD**.
2. Osobno zweryfikować w oficjalnej dokumentacji źródła konkretną walutę/variant, prawo do lokalnego wykorzystania i retencji, oryginalne `available_at` oraz kolejność danych wobec decyzji.
3. Dopiero wtedy rozbudować offline kontrakt o **dokumentowalny** dowód waluty i uprawnień; nie przyjmować samej deklaracji użytkownika jako niezależnej atestacji.
4. Zachować rozdział między badaniem wyników syntetycznych, porównaniem historycznej rekonstrukcji a możliwymi do realizacji cenami transakcyjnymi. Ewentualne rzeczywiste operacje nie są częścią projektu C2.

## 5. Reconciliacja PR

PR #103 jest *stacked* na #102 → #100 → #99; #99 ma nowy HEAD po wcześniejszym zaostrzeniu bramki offline. Testy C2 na jego własnej bazie **nie** dowodzą zgodności z najnowszą bazą #99. Przed merge należy sprawdzić wszystkie zależności, świeży combined tree i powtórzyć CI. Skrypt źródłowy v0.19 celowo przestał być byte-identical z monolitem PR #96: zmiana naprawia oznaczenie waluty, nie przepisuje historycznych źródeł ani zamrożonych anchorów.

**Status:** `C2_SOURCE_CURRENCY_UNVERIFIED_HOLD`, `SOURCE_RIGHTS_UNVERIFIED`, `NO_M1_ADMISSION`; zero połączeń z brokerem, wallet, DB i dostawcami w tym etapie.

## 6. Pierwszy przebieg CI po poprawce

Pierwszy uruchomiony workflow [#42672899142](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/42672899142) miał wynik **workflow = FAILURE**, choć jedyny raportowany przez GitHub API job `source-categories (macos-15)` zakończył się `SUCCESS`; zadanie `ubuntu-24.04` nie pojawiło się na liście jobs (GitHub API: `total_count=1`). **Nie wolno interpretować udanego macOS jako pełnej akceptacji matrix.** Zachowano obie platformy i tę samą liczbę testów. Dodatkowy commit dokumentacyjny wyzwala ponowne wykonanie; ostateczny status wymaga nowego, pełnego wyniku z Ubuntu i macOS.
