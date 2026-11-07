# ISL v0.28 — chronologiczny dziennik stabilności decyzji M1–M3

## Cel

v0.27 porównywał niezależne scenariusze syntetyczne i **nie mógł** mierzyć częstotliwości zmian w czasie. v0.28 rozlicza **kolejne miesiące decyzji** za pomocą istniejącego kontrolera v0.15 i łańcucha SHA dziennika v0.17. Wstępne testy używają danych wyłącznie syntetycznych; nie są to pomiary efektywności rzeczywistego rynku.

## Wejście / wyjście

`scripts/research_chronological_decision_audit_v28.py` przyjmuje JSON z dokładnymi polami:

```json
{
  "mode": "EDUCATIONAL_CHRONOLOGICAL_DECISIONS_ONLY",
  "source_kind": "SYNTHETIC_FIXTURE",
  "snapshots": ["...dwa lub więcej kolejnych manifestów v0.5..."]
}
```

`source_kind` alternatywnie `UNQUALIFIED_SOURCE_RESEARCH`; jest to jedynie etykieta deklaracyjna, nie certyfikat źródła. Każdy snapshot to standardowy manifest `EDUCATIONAL_SHADOW_ONLY` z datą as-of i seriami. Dokładny format jest walidowany przez dotychczasowy `research_decision_controller_v15`, nie przez nowy niesprawdzony schemat.

Wersja dopuszcza 2–36 kolejnych **miesięcy decyzji**. Odrzuca duplikaty, brakujące miesiące, cofnięcie daty, przyszłe czasowo niedostępne dane oraz rewizje wspólnych miesięcznych prefiksów źródeł. Jeżeli źródło znika, odpowiedni model może przejść do `HOLD_CASH` — nie wolno dorabiać nieistniejących poziomów.

Ponownie wykorzystuje `research_forward_journal_v17.run_journal` z `forward_reference=null` we wszystkich cyklach. Nie wymyśla zwrotów referencyjnych ani fillów. Sprawdza zgodność statusów M1–M3 z niezależnym odtworzeniem kontrolera i wiąże każdy cykl w łańcuch SHA-256.

Wynik `ISL_CHRONOLOGICAL_DECISION_V28` zawiera:
- `hold_months` i `candidate_months` dla każdego modelu;
- `status_transitions` (zmiana statusu między kolejnymi miesiącami);
- `target_changes` (zmiana wirtualnego targetu między miesiącami);
- `candidate_regime_changes` M3 **tylko gdy oba sąsiednie snapshoty są kandydatami**;
- SHA wszystkich wejść, wyników kontrolera, cykli v0.17 i łańcucha v0.28.

Nie oznacza to rzeczywistego obrotu portfolio, kosztów rebalancingu, money-weighted return, historycznej ani prospektywnej trafności kierunku.

## Testy syntetyczne

Testy pokrywają:
- dwa kolejne miesiące, pierwszy `M3 HOLD_CASH`, drugi `M3 PAPER_CANDIDATE_ONLY` po potwierdzeniu;
- trzeci miesiąc z utrzymanym reżimem;
- nową zmianę reżimu na RISK_OFF bez drugiego potwierdzenia → M3 HOLD;
- brak źródła globalnych akcji → kontroler wstrzymuje odpowiednie modele;
- błędną chronologię, rewizję historii, powtórzony miesiąc, future retrieval, LIVE_TRADING i dodatkowe pola;
- deterministyczność, niezmienność manifestów i zero operacji finansowych.

```bash
python3 -m unittest discover -s tests -p 'test_research_chronological_decision_audit_v28.py' -v
```

## Dalsze kroki i status

Kod może zostać użyty do retrospektywnego audytu **rzeczywiście zapisanych później** kolejnych decyzji, jeżeli będą miały niezależny punkt czasowy i zweryfikowaną historię źródła. Nie wolno sztucznie odtwarzać starego as-of na podstawie danych pozyskanych po czasie. Dodanie danych `UNQUALIFIED_SOURCE_RESEARCH` nie promuje kwalifikacji modelu ani legalności użycia.

Vanguard/NBP forward listopad 2026 pozostaje `PENDING` do końca miesiąca i nowego oryginalnego źródła. Formalne bramki M1–M3 na obecnych rzeczywistych źródłach pozostają `HOLD_CASH`. Projekt nie ma uprawnienia do transakcji, zapisów do Neon ani pracy na zasobach portfela.
