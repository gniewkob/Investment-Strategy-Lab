# D2 — offline preflight i prywatna obserwacja NAV/FX (v0.24–v0.25)

**Data: 2026-11-09.** Status: badawczy Draft PR zależny od [D1 #104](https://github.com/gniewkob/Investment-Strategy-Lab/pull/104), pośrednio od [A2 #99](https://github.com/gniewkob/Investment-Strategy-Lab/pull/99). Wersja zamrożonej polityki i oryginalny hash archiwalny pozostają niezmienione.

## Zakres

- `nav_forward_preflight_v24.py` + test: porównuje **ręcznie dostarczone** surowe bajty oryginalnego pliku XLSX i NBP ze źródłami i protokołem zamrożonym przez v0.22/v0.23, bez imputacji dat lub przepisania historii. Przed pojawieniem się poprawnego zamkniętego miesiąca pozostaje `PENDING`.
- `nav_fx_evidence_capture_v25.py` + test: sprawdza, czy dane oryginalnego pliku XLSX nie zrewidowały okresu bazowego. Po jawnej opcji użytkownika może odczytać pojedynczą odpowiedź NBP HTTPS — **nie jest to uruchamiane w CI**. Wydzielony kod zapisuje surową odpowiedź do nowego, prywatnego pliku `0600` przez `os.open(O_EXCL|O_CREAT)`, odmawiając nadpisania lub skierowania na istniejący symlink.

Cztery źródłowe pliki testów i implementacji skopiowano z badawczej gałęzi PR #96 **bez zmian Git blob SHA**. Nowością są jedynie własne CI i ten dokument.

## Granice eksperymentu

- Przypięty oryginalny hash freeze v0.23: `3b8aca44ffa6aa72bf2d3a0b5d49102f0dd857d11191dc10e7d21b5051e704a2`; źródłowy Git blob v0.22 `7a9c7e5cbc643b5ad760ec64d4212468b64a22bf` i v0.23 `d425076ea809f622e5b2c1c4e87ba59fe060f990` nie mogą się niejawnie zmienić.
- Zamknięty listopad 2026 i prawidłowy nowy oryginalny eksport nie zostały w tych testach niezależnie zweryfikowane. **Stan forward PENDING**; nie wolno na tej podstawie twierdzić, że uzyskano listopadowy wynik.
- W CI nie ma rzeczywistego XLSX dostawcy, licencji, oryginalnego SHA surowego eksportu, potwierdzonego vintage PIT, ani ceny wykonania zlecenia. Testy są syntetyczne i mogą jedynie sprawdzić logikę bramek.
- Brak zautomatyzowanej przeglądarki, logowania, cookie, uprawnień do handlu, aktywnego zasilania Neon, portfela, giełdy czy harmonogramu. Nie kopiujemy do D2 żadnych workflowów pobierających surowe pliki z Vanguard; osobny przegląd praw providerów jest nadal otwarty.

## CI i integracja

`.github/workflows/isl-d2-nav-forward-offline-ci.yml` sprawdza cztery oryginalne Git blob SHA v0.22–v0.25 oraz nieruszony anchor, a następnie uruchamia **19 istniejących testów** v0.24/v0.25 na Ubuntu i macOS Python 3.12 z blokadą Python socket. Testy zachowują oryginalne bramki prywatności i test pliku `0600`, `O_EXCL`, symlink i identycznych bajtów.

**Kolejność:** A2 #99 → D1 #104 → D2. Draft #96 zawiera te same pliki i nie może zostać scalony po drodze bez uzgodnienia overlap. Zamrożony hash v0.22/v0.23 pozostaje nietknięty, a wszelkie operacje finansowe są niedozwolone w ramach tego pakietu.
