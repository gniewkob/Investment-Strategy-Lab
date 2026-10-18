# Wdrożenie publicznego repozytorium – Investment Strategy Lab

Repozytorium źródłowe: `gniewkob/Investment-Strategy-Lab` (publiczne).

1. Prześlij kod na gałąź `feature/autonomous-agent-v2-review`, utwórz Pull Request do `main`.
2. CI uruchamia wyłącznie testy jednostkowe i offline smoke; bez dostępu do bazy czy środków.
3. Workflow `autonomous-research.yml` jest **wyłącznie ręczny** (`workflow_dispatch`), do czasu zamknięcia przeglądu bezpieczeństwa i migracji bazy.
4. Przed jakimikolwiek uruchomieniami z Neon ustanów rolę minimalnych uprawnień (bez CREATE/DDL; tylko wybrane tabele badawcze), ustaw secret `NEON_DATABASE_URL` w GitHub Actions, nigdy w kodzie i logach.
5. Nie używaj zleceń, giełdowych kluczy API, tokenów, adresów portfeli, szczegółów aktywów użytkownika ani danych osobowych w tym publicznym repozytorium.
6. Dopiero po pozytywnej weryfikacji 14 kolejnych cykli i kanału alertowego wolno rozważyć harmonogram automatyczny.
