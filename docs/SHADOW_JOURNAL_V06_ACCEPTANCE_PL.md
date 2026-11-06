# Investment Strategy Lab — v0.6 shadow journal (2026-11-06)

## Cel
Deterministyczny i odtwarzalny dziennik audytowy wielookresowej ewaluacji edukacyjnej.
**Nie** jest to system inwestycyjny, certyfikat prospektywnej akwizycji ani wynik historycznej strategii.

## Kontrakt
`scripts/shadow_journal_v06.py` czyta lokalny JSON:
```json
{
  "mode": "EDUCATIONAL_SHADOW_JOURNAL_ONLY",
  "entries": [
    {
      "decision": {"...": "pełny oryginalny dokument z v0.5"},
      "forward_reference": {"...": "pełny dokument v0.5 forward"}
    }
  ]
}
```
Każdy wpis przechodzi istniejący `evaluate_forward` weryfikujący odcisk decyzji, daty i deklarowane źródła. Kolejny `decision.as_of_utc` musi następować **po** poprzednim `forward_reference.as_of_utc`. Powtórzenie decyzji, naruszenie chronologii lub zmieniony odcisk decyzji blokują cały dziennik.

Dla każdego wpisu tworzone są: fingerprint pierwotnej decyzji, hash wejścia forward, hash wyniku weryfikacji, hash poprzedniego wpisu i nowy hash SHA-256; końcowy dokument ma osobny `journal_sha256`. Raport zawiera wyłącznie statusy modeli i liczniki, bez surowych cen i bez syntetycznego zysku z `HOLD_CASH`.

Przykładowe uruchomienie (lokalnie, offline):
```bash
python -m scripts.shadow_journal_v06 --input shadow_pairs.json --output shadow_audit.json
python -m unittest discover -s tests -p 'test_shadow_journal_v06.py' -v
```

## Ograniczenia i bramki
1. Hash dowodzi spójności dostarczonych bajtów po kanonizacji, **nie** rzeczywistego historycznego czasu zapisania decyzji. Aby uznać zapis za prospektywny, niezbędny jest niezależny append-only zewnętrzny checkpoint z zaufanym czasem i niezmiennym artefaktem.
2. `source_status`, `rights_status`, `first_usable_at` nadal są deklaracjami; nie zastępują potwierdzenia licencji, oryginalnego vintage i dowodu publikacji.
3. Status `NOT_EVALUABLE_PREVIOUSLY_HOLD_CASH` nie oznacza zerowej stopy zwrotu. Nie powstają Sharpe, drawdown, alfa, paper fills ani zlecenia.
4. Nie dotyka Neon, schedulerów, giełdy ani portfeli. Wymagane dane GLOBAL_EQUITY_TR_PLN, PL_BONDS_TR_PLN i GOLD_TR_PLN nadal nie uzyskały pełnej kwalifikacji.
5. Dane testowe są syntetyczne, CI potwierdza tylko reguły walidacji i deterministyczność.

## Następny gate
Zachować osobno decyzję przed okresem obserwacji oraz późniejszy niezależny artefakt źródłowy, oba ze zweryfikowanym czasem utworzenia, niezmiennymi checksumami i prawami użycia. Dopiero potem prowadzić raport wielookresowej jakości i porównania z baseline.
