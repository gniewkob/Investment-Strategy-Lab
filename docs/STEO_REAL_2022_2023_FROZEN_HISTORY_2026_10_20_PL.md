# STEO — rzeczywiste starsze wydania 2022–2023, zamrożona metoda, 144 porównania (20.10.2026)

## Dowód sukcesu na prawdziwych oryginalnych XLSX EIA

[Publiczny oficjalny badawczy GitHub Actions #39433488201](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39433488201) — **SUCCESS** po wdrożeniu [PR #46](https://github.com/gniewkob/Investment-Strategy-Lab/pull/46) i naprawie zgodności starszych nagłówków [PR #48](https://github.com/gniewkob/Investment-Strategy-Lab/pull/48). Pobrano i zweryfikowano **32/32 oryginalne, publicznie dostępne XLSX EIA**: **24 miesięczne wydania STEO Jan2022–Dec2023** jako kohortę prognoz i **8 wydań Jan–Aug2024 jako wyłącznie późniejsze referencje** dla prognoz z końca 2023 r. Źródła nie zostały dodane do GitHub ani Neon. Program zakończył `STEO_PREDECLARED_EARLIER_2022_2023_HISTORICAL_SOURCE_VALIDATION`, obejmując **144/144 pary** = 24 edycje × 2 surowce × 3 zamrożone horyzonty.

**Niezależny test integralności:** wszystkie **8/8 SHA-256** arkuszy Jan–Aug2024 z nowej próby jest zgodnych z oryginalnymi wartościami hash z wcześniejszego [34-edycyjnego badania STEO 2024–2026](STEO_FULL_34_REAL_RESULTS_2026_10_20_PL.md). Weryfikuje powtarzalność bajtów pobranych podczas tych odrębnych testów, **nie** niezmienność pliku od jego historycznej daty wydania.

**CI:** poprawka parsera starszych roczników zatwierdzona przez [PR CI #39433327315](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39433327315): **276/276 offline PASS**, **3/3 izolowane PostgreSQL PASS**. Rok bazowy nagłówków źródłowych: rzeczywiste `jan22` = 2018–2023, `jan23` i `dec23` = 2019–2024; brak wewnętrznego pola A3 `Forecast date:` w `jan22` nie służy do wnioskowania o publicznej dostępności. Wzięto formalne `Release Date` z oficjalnego indeksu EIA.

## Zamrożony model porównania: historyczny błąd prognozy ceny miesięcznej USD/baryłkę

Ten sam protokół, który oceniono dla 2024–2026: `WTIPUUS` i `BREPUUS` z `2tab`, prognozy +1/+3/+6 miesięcy od miesiąca oficjalnej daty wydania, porównanie EIA z naiwną wartością poprzedniego miesiąca **w tym samym starym raporcie**. Późniejsza miesięczna referencja to pierwsza spośród badanych edycji co najmniej 2 miesiące po miesiącu docelowym. Bez zmian reguł pod wpływem nowej próby, bez parametrów dostrajanych na 2022–2023. Metoda jest opisowa, nie prognozuje inwestowalnych stóp zwrotu.

### Całe 24 wcześniejsze wydania — MAE USD/bbl

| Surowiec | Horyzont (mies.) | Liczba prognoz | MAE EIA | MAE prosty | Niższy błąd |
| --- | ---: | ---: | ---: | ---: | --- |
| WTI | 1 | 24 | 7,61 | 9,19 | EIA |
| WTI | 3 | 24 | 10,44 | 12,59 | EIA |
| WTI | 6 | 24 | 10,71 | 11,82 | EIA |
| Brent | 1 | 24 | 7,77 | 9,98 | EIA |
| Brent | 3 | 24 | 10,77 | 12,74 | EIA |
| Brent | 6 | 24 | 11,03 | 13,06 | EIA |

**W starszym okresie EIA miała mniejsze średnie błędy w 6/6 grup**. Dla porównania, w latach 2024–Oct2026 EIA miała mniejszy błąd tylko dla horyzontu 1 miesiąca (2/6 grup), a prosty model dla +3 i +6 miesięcy obu surowców (4/6). To **różnice pomiędzy okresami historycznymi**, nie dowód modelu skutecznego w przyszłości. Część z badanego zjawiska jest związana z rozdzieleniem 2022 versus 2023:

### Wyniki osobno dla 2022 i 2023 (12 edycji na każdą grupę roczną)

| Rok wydania | Surowiec | Horyzont | Liczba prognoz | MAE EIA | MAE prosty | Pary z mniejszym błędem EIA |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 2022 | WTI | 1 | 12 | 9,64 | 11,63 | 8/12 |
| 2023 | WTI | 1 | 12 | 5,58 | 6,75 | 8/12 |
| 2022 | WTI | 3 | 12 | 12,19 | 17,47 | 10/12 |
| 2023 | WTI | 3 | 12 | 8,69 | 7,70 | 5/12 |
| 2022 | WTI | 6 | 12 | 16,06 | 19,67 | 6/12 |
| 2023 | WTI | 6 | 12 | 5,36 | 3,97 | 3/12 |
| 2022 | Brent | 1 | 12 | 10,29 | 13,20 | 9/12 |
| 2023 | Brent | 1 | 12 | 5,25 | 6,75 | 10/12 |
| 2022 | Brent | 3 | 12 | 12,89 | 17,97 | 9/12 |
| 2023 | Brent | 3 | 12 | 8,65 | 7,52 | 5/12 |
| 2022 | Brent | 6 | 12 | 16,91 | 21,58 | 7/12 |
| 2023 | Brent | 6 | 12 | 5,14 | 4,53 | 3/12 |

**Zasadniczy wniosek:** W roku **2022** EIA ma niższe średnie błędy w 6/6 grup, a w **2023** tylko w 2/6 grupach (1-miesięczne WTI i Brent). W obu grupach +3 i +6 miesięcy w 2023 lepszy jest baseline `last month`. Całe 2022–2023 uśrednione w jednej tabeli maskuje tę niestabilność, dlatego unikać twierdzenia, że jedna metoda „zawsze wygrywa”.

## Manifest realnie pobranych 32 archiwalnych dokumentów

Poniższe hash-e są autentycznymi SHA-256 **dzisiaj pobranych** XLSX i mogą posłużyć do weryfikacji zmiany zawartości podczas późniejszych pobrań.

| Kod wydania | Formalny dzień EIA | Rola w tym badaniu | SHA-256 oryginalnego XLSX |
| --- | --- | --- | --- |
| `jan22` | 2022-01-11 | Prognoza 2022–2023 | `b60e88599a48cb8f130c464344c0ce5f58de08b3ad92d51e8721cd4449994a49` |
| `feb22` | 2022-02-08 | Prognoza 2022–2023 | `8b4400f482f6359c8cf26d61c1c2fb17dea65dca77ec6b6bdda5f0a1dbc17336` |
| `mar22` | 2022-03-08 | Prognoza 2022–2023 | `55cc3c995dfa86d60d8cd1d8726020cf96acc1917b4187f4017e8dad42a43d7f` |
| `apr22` | 2022-04-12 | Prognoza 2022–2023 | `225e7d8e59931a685811b8f868f28322968a06ea6ffbf94f8e57877e56fb74f6` |
| `may22` | 2022-05-10 | Prognoza 2022–2023 | `80deccb17b45d2426788c398f16b55f924583b2228bb8ec1624dfc0ee1d20683` |
| `jun22` | 2022-06-07 | Prognoza 2022–2023 | `6807e5632b55852f4d1113d0a36ee989bd24e1511cae29a8c6476b87998cb572` |
| `jul22` | 2022-07-12 | Prognoza 2022–2023 | `8555a9e9d04e80e9fec335ca36bb2ce14737a39b552a8f3e890389ee2c62d918` |
| `aug22` | 2022-08-09 | Prognoza 2022–2023 | `8196b5dc6900a0b4159af03578084f9243080e26f1f283ffdd3485babb4b44e3` |
| `sep22` | 2022-09-07 | Prognoza 2022–2023 | `13ee3aec3fc65acacab1d958de3d231d49a6594a5fea70236eb5bd0cf03e9058` |
| `oct22` | 2022-10-12 | Prognoza 2022–2023 | `630ca3fcb12fba4b25c11247895c552d259604f6911794be213716ee3517519f` |
| `nov22` | 2022-11-08 | Prognoza 2022–2023 | `a0a0d4b0cc676aac5eab4f841cdb942c6f3aa6def854c35bd5d5aa8afbaf1c25` |
| `dec22` | 2022-12-06 | Prognoza 2022–2023 | `7cdba7db9a5a3380deb3b6e15b39167e80ed6301427de4e6d5ae008449645db5` |
| `jan23` | 2023-01-10 | Prognoza 2022–2023 | `3e9f69db5383c1b81450a60abdf8e3fbf932ca7d7301a6d516515520c12a799d` |
| `feb23` | 2023-02-07 | Prognoza 2022–2023 | `aeee3b3d69fbc09f7a64091ad1bf5c8582074fdd7e47a4bdd9b5d2c619ec2661` |
| `mar23` | 2023-03-07 | Prognoza 2022–2023 | `dc4661a7f2ffb83e0c78dd350734bcc8307a28886f8ff114343adcc9ea6b2eda` |
| `apr23` | 2023-04-11 | Prognoza 2022–2023 | `ae785b551cfef4cd2f082ccabe1a0189ba8ce273e8b6efc50dfca22ae35fc65f` |
| `may23` | 2023-05-09 | Prognoza 2022–2023 | `c564333f36f85a57f8c96b4deca15a24b935f6d2a2b1b5d472d32245057a6e20` |
| `jun23` | 2023-06-06 | Prognoza 2022–2023 | `0b01e5c4d270c02b4c37e82d73b24afff498bebbe27510cfec5a9b48d3ddba17` |
| `jul23` | 2023-07-11 | Prognoza 2022–2023 | `fdc949682f272ee2235e817c124362fab3b97a6634ea9389dafc5b255ddfb45a` |
| `aug23` | 2023-08-08 | Prognoza 2022–2023 | `a71e1be2e0d28080e1a178aadc85670f3ec75252708f838beb2fe2ee22d2c3cf` |
| `sep23` | 2023-09-12 | Prognoza 2022–2023 | `9afe1f7d73678cfe5c5fc359fd0bbb9d0e3abbe316b0c5ef42643df61aa4ec69` |
| `oct23` | 2023-10-11 | Prognoza 2022–2023 | `9052f233f79c28dcd9a1cd863adc59b2f39f5bcb266b3cbceb6a1579ee93b757` |
| `nov23` | 2023-11-07 | Prognoza 2022–2023 | `1a5b2a74cb04615e111461dc5fb895951dea41787fab4967968d7e1136c6f966` |
| `dec23` | 2023-12-12 | Prognoza 2022–2023 | `b46feff4942376e2537b58c864cfc75e873d73f1a7582f532e3244f777ad6cea` |
| `jan24` | 2024-01-09 | Tylko późniejsza referencja | `663ee3c648d2e88dad48dd1efd2557df99c811afe4afcc2094ed92c988fb53a9` |
| `feb24` | 2024-02-06 | Tylko późniejsza referencja | `dc3742fe43299f5288533d328c86c8435bc8223d92e26ad418ee276b2890aae3` |
| `mar24` | 2024-03-12 | Tylko późniejsza referencja | `0f168cec985f5511c93b6238cfc27cacf4df1f2dd890ce01d23fd1e81c30b513` |
| `apr24` | 2024-04-09 | Tylko późniejsza referencja | `144ffbf52092468b4bccdd58b94dfacf4b603351ec7dba54fafb1d4b8b6a9095` |
| `may24` | 2024-05-07 | Tylko późniejsza referencja | `b26d58c911a0878fd615aedd164a2d4796927146c45654d90edcb457ca57f8ea` |
| `jun24` | 2024-06-11 | Tylko późniejsza referencja | `12cd939ba0d9d6b559d56d40cc0650e99c57d249fff1ecc691af601a2e0de636` |
| `jul24` | 2024-07-09 | Tylko późniejsza referencja | `066eb3d2691a4ace702483ee4a73f64c6d9899a692edb4b9171d94b986b369dd` |
| `aug24` | 2024-08-06 | Tylko późniejsza referencja | `a4679e91622d5d8d414954b988afdb4119690e7d0b1e458e30be0ca7666ca826` |

## Ograniczenia i ryzyko nadinterpretacji

- **NIE** posiadamy niezależnego dowodu, że bajty np. `jan22_base.xlsx` pobrane 20.10.2026 były identyczne 11.01.2022. Oficjalne wydanie jest historycznie datowane, lecz bajty mogły być później zrewidowane. `historical_original_publication_bytes_certified=false`; **to nie jest historyczny PIT certyfikowany przez niezależne archiwum**.
- Nie nazwać lat 2022–2023 „przyszłym out-of-sample”: to wcześniejszy, ale dotąd nieanalizowany okres historyczny względem 2024–2026. Posłużył do badania odporności bez dalszego dostrajania, nie do wyznaczania nowych wag portfela.
- Miesięczne prognozy dla horyzontów 1, 3, 6 i tych samych celów mogą się nakładać; `144 pary` nie oznaczają 144 statystycznie niezależnych przypadków.
- Cena referencyjna EIA WTI/Brent w USD/baryłkę **nie jest produktem total-return w PLN**, ani ceną osiągalną w realnym zleceniu. Mniejsze MAE nie implikuje wyniku finansowego, przewagi transakcyjnej ani „alpha”.
- **Brak skutków ubocznych:** 0 Neon DB connections/writes, 0 real orders, 0 paper allocation changes, 0 schedules, 0 zapisanych surowych XLSX przez jednorazowego runnera; użytkownik wcześniej zamknął operacyjny backup EIA MyDevil/Mac, nie modyfikowano go.

**Decyzja:** wcześniejsza hipoteza „model prosty stabilnie lepszy dla dłuższych horyzontów” **nie jest uniwersalna historycznie**; zależy od epoki. Nie kontynuować strojenia reguł na tych samych danych; kontynuować tylko źródłowo potwierdzony research chronologiczny, bez transakcji.

Źródło oficjalne: <https://www.eia.gov/outlooks/steo/outlook.php>. Protokół predeklarowany [tu](STEO_PRIOR_PERIOD_2022_2023_PREDECLARED_PL.md), wcześniejsza autentyczna weryfikacja 2024–26 [tu](STEO_REAL_WALKFORWARD_ROBUSTNESS_2026_10_20_PL.md).
