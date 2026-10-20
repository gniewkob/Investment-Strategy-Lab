# EIA — prospektywna analiza wersji źródła, offline, bez sygnałów transakcyjnych

**Cel:** wykorzystać **już istniejące, niezależnie sprawdzone 3 dokumenty EIA** z MyDevil i ich kopię Mac mini do badania różnic między faktycznymi, datowanymi pobraniami. Backup jest [potwierdzony i zamknięty](EIA_BACKUP_ACCEPTANCE_2026_10_20_PL.md) — to nie jest kolejna bramka infrastruktury.

## Pierwszy przebieg: rzeczywista baza porównawcza 20.10.2026

Operator wykonał `capture` dla WTI, Brent i Henry Hub w dniu 20.10.2026 i 3 niezależne offline `verify`. Mac mini ma kopię w prywatnym katalogu `~/.isl-eia-backups/20261020T093647Z` ze zgodnymi raw SHA i manifestami.

Nowy `scripts/eia_prospective_archive_research.py`:

1. Czyta **bez internetu** wszystkie trzy rodziny manifestów w katalogu przekazanym jako `--archive-root`. Nie wymaga sekretnych URL, bazy Neon, połączenia z MyDevil lub innego endpointu.
2. Dla każdej rodziny odtwarza wszystkie pobrania z oryginalnymi bajtami HTML, weryfikuje raw SHA-256, semantic SHA-256 dat/cen, tożsamość źródła, datę `Release Date`, prawdziwy `retrieved_at` i kontrakt parsera. Ogranicza liczbę manifestów do 128 na źródło i odrzuca nieznane nazwy, symlinki, niespójne manifesty oraz powtórzone czasy pobrania ze sprzeczną treścią.
3. Raportuje wyłącznie **metadane**: liczba obserwacji, zakres dat, ukończony czas pozyskania, raw/semantic SHA, liczba wersji, liczba dat wspólnych, nowych w aktualnym oknie, usuniętych z okna i **zmienionych cen dla dokładnie tych samych dat** (tylko po posiadaniu dwóch faktycznych snapshots).
4. Rozróżnia **zmianę formatowania HTML** bez zmiany notowań, **mechaniczne przesunięcie okna 420 dni** i rzeczywistą korektę wartości tej samej obserwacji. Sama różnica w SHA nie jest dowodem korekty cen; porównanie odbywa się wyłącznie w przecięciu dat.
5. Dla jednego `capture` na źródło zwraca `FIRST_SOURCE_CAPTURE_BASELINE_ONLY`, nie „backtest” ani rzekomo znaną cenę z wcześniejszej daty. Późniejsze rzeczywiste pobrania mogą utworzyć **prospektywne, niezależnie datowane porównanie**.
6. Raport nie drukuje cen, oryginalnego HTML, ścieżek prywatnych ani danych uwierzytelniających. Nie tworzy żadnych plików i nie zmienia portfeli, baz, GitHub, harmonogramów, rzeczywistych aktywów.

## Manualna analiza już utworzonej kopii na Mac mini

W katalogu repozytorium `Investment-Strategy-Lab` (nie w innym projekcie):

```bash
python3 -m scripts.eia_prospective_archive_research \
  --archive-root "$HOME/.isl-eia-backups/20261020T093647Z"
```

W razie potrzeby pobrać aktualną gałąź `main` z GitHub przed uruchomieniem. Uruchomienie **nie pobiera nowych EIA źródeł** i nie zapisuje bazy.

Dla aktualnych 3 pojedynczych przechwyceń oczekiwane:
- `status=EIA_PROSPECTIVE_ARCHIVE_DESCRIPTIVE_AUDIT`;
- `archive_sources_verified=3`;
- każda `source_series[].captured_vintages=1`;
- każda `source_series[].research_readiness=FIRST_SOURCE_CAPTURE_BASELINE_ONLY`;
- `virtual_model_allocations_changed=0`, `real_orders=0`, `database_connections=0`, `database_writes=0`, `file_creations=0`.

Po **nowym** rzeczywistym `capture` w tej samej prywatnej lokalizacji, kolejne uruchomienie pokaże historycznie stwierdzalne **różnice między stanami znanymi podczas tych dwóch pobrań**. Nie można wstecznie certyfikować oryginalnej publikacji cen z 2024–2026.

## Oddzielenie od eksperymentów M1/M2/M3

WTI/Brent/Henry Hub to **spot reference PRICE_ONLY**, a nie PLN total-return inwestowalne instrumenty z kosztami i FX. Nie wolno używać ich na podstawie samego `capture` do deklaracji efektywności portfela, symulowania realnych wykonań ani zmian wag M1–M3. Eksperymenty pozostają `HOLD_NO_CHANGE` do czasu odrębnych, zweryfikowanych danych inwestowalnych i prospektywnych obserwacji.

Ten moduł to **pierwszy wiarygodny rejestr porównawczy faktycznych pobrań** wspierający późniejszy niezależny research. Tryb: wyłącznie edukacja, opis retrospektywny i późniejsza prospektywna walidacja; zero automatyzacji transakcyjnej.

Dowody pierwotne: [MyDevil real archive captures](EIA_MYDEVIL_ACTUAL_ARCHIVE_RECEIPTS_2026_10_20_PL.md); [reguły archiwizacji](EIA_ORIGINAL_HTML_ARCHIVE_PL.md).
