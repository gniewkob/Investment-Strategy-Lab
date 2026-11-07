# ISL v0.29 — dowodowe powiązanie archiwum GitHub v0.9 z decyzją M1–M3

## Decyzja architektoniczna

Istniejący moduł v0.17 rejestruje decyzje dla jawnych manifestów źródłowych, a v0.28 liczy zmiany w kolejnych miesiącach. Natomiast **zarchiwizowany pakiet GitHub v0.9 nie zawiera oryginalnych serii miesięcznych**, tylko zarejestrowany i zweryfikowany checkpoint pustego źródłowo cyklu. Takiego archiwum NIE należy konwertować na kwalifikowane miesięczne snapshoty M1–M3. Prawidłowa integracja polega na ponownym wyliczeniu decyzji `HOLD_CASH` i połączeniu jej z dowodem archiwalnym.

Nowy `scripts/research_archived_decision_link_v29.py` to most read-only między istniejącymi `shadow_evidence_ledger_v09`, `research_decision_pipeline_v16` i przyszłym chronologicznym dziennikiem. Bez przeprojektowania istniejącego archiwum.

## Co sprawdza

1. Ponownie weryfikuje oryginalny pakiet archiwalny `capture/run/artifacts/checkpoint`: kanoniczny SHA, GitHub metadata checkpoint, tożsamość zdarzenia i zerowe operacje finansowe.
2. Odtwarza zamrożony kontroler v0.15 z archiwum przez `run_cycle(archived_bundle=...)`. Wynik musi mieć puste źródła i `HOLD_CASH` dla M1/M2/M3.
3. Łączy datę zapisaną w archiwum, wersję polityki `V05_FROZEN_001`, skrót manifestu, skrót decyzji, skrót pakietu, numer wykonania GitHub, numer próby, artifact ID oraz skrót checkpointu.
4. Opcjonalnie `--ledger` weryfikuje cały istniejący lokalny SQLite v0.9 w trybie read-only i dopasowuje dokładnie `run_id/run_attempt/artifact_id` oraz SHA pakietu, łącznie z pozycją i łańcuchem. Brak pliku ledger powoduje błąd, **nie jego utworzenie**.
5. Wyprowadza jawne `suitable_for_v28_chronological_market_journal=false`: samo metadane potwierdzające pojedynczy cykl nie są miesięcznym szeregiem ani prospektywną oceną rynku.

## Komendy odbiorowe

Archiwum projektu — nie wymaga prywatnych NAV:

```bash
python3 -m scripts.research_archived_decision_link_v29 \
  --archived-v09 evidence/shadow/v09/checkpoint-bundle-run-42305280062.json
```

Jeżeli Mac ma działający i niezależnie zweryfikowany lokalny SQLite v0.9, można opcjonalnie dodać `--ledger /prywatna/sciezka/istniejacy-ledger.sqlite`. Nie wolno zgadywać lokalizacji ani tworzyć nowego pustego SQLite jako zastępstwa dowodu.

```bash
python3 -m unittest discover -s tests \
  -p 'test_research_archived_decision_link_v29.py' -v
```

Testy używają faktycznego archiwalnego pakietu metadanych z repozytorium, pomocniczego **tymczasowego testowego** SQLite (nie środowiska użytkownika), a także testów manipulacji checkpointem, danymi, bazą i próbą zamiany na `LIVE_TRADING`.

## Granice dowodu i wymagania przyszłych danych

Zgodny SHA pliku oznacza **zgodność z zapisaną treścią**, nie dowód niezmiennego czasu utworzenia, licencji na dane, oryginalnej tożsamości providera, braku ingerencji administratora w SQLite ani aktualnej dostępności aktywów. v0.10 umożliwia osobną kontrolę zakotwiczonej głowicy ledger; v0.29 nie twierdzi, że przeprowadził taką kontrolę. Wskaźniki `independent_time_attestation_verified=false`, `historical_pit_verified=false`, `qualified_m1_m2_m3=false` są niewyłączalne.

**Reguła rozdzielenia:** archiwalny cykl HOLD pozostaje dowodem działania kontrolera przy braku kwalifikowanych serii. Nigdy nie wolno używać go do sztucznego powiększania statystyki miesięcy M1/M2/M3 w v0.28. Rzeczywisty, chronologiczny audyt wymaga później oryginalnych, niezależnie datowanych źródeł i punktów czasu ich pozyskania.

Projekt pozostaje edukacyjny i read-only. Brak giełdy, wallet, sprzedaży, zakupów, płatności, automatycznej promocji modeli, zapisu Neon i nowych harmonogramów.

## Porządkowanie PR #96

PR #96 jest dużym zbiorczym draftem zawierającym implementacje danych, dowody historyczne, nowe API źródłowe i eksperymenty decyzji od v0.20 do v0.29. Nie należy scalać go automatycznie tylko dlatego, że CI jest zielone; wymagane osobne sprawdzenie zakresu, dowodów, historii commitów i ryzyka złączenia modułów. Wydzielanie do mniejszych PR powinno zachować zależności i istniejące referencje SHA archiwów. W ramach v0.29 nie wykonywano żadnego merge, zmiany bazy PR ani automatycznego przeniesienia commitów.
