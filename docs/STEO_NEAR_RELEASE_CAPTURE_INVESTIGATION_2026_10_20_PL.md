# STEO: rzeczywiste kopie Wayback 2022–25 i porównanie źródłowe

Zweryfikowano: **2026-10-20**, zakończenie zestawienia `2026-10-20T18:36:27.803698+00:00`. Research only; M1–M3 `HOLD_NO_CHANGE`.

## Nowe ustalenia — zastępują wcześniejszy status braku pobranych bajtów

**48/48 rzeczywistych odpowiedzi XLSX pobranych z Wayback `id_` i zweryfikowanych**, po jednej pierwszej odpowiedzi zwróconej przez kwerendę CDX dla każdego wydania Jan2022–Dec2025. Nie są to linki HTML, współczesne pliki EIA podstawione za replay ani pliki wygenerowane z cen. Każdy replay: HTTP 200, niezmieniony docelowy URL, ZIP/OOXML CRC, dokładny `Memento-Datetime`, zgodny CDX SHA1 payloadu i wyliczony SHA256. Nie pobierano całych kontenerów WARC.

- **2022–24:** 35/36 replay zgodnych SHA256 z istniejącym manifestem 36/36. `jun24` ma inne oryginalne bajty; jest to potwierdzona różnica dwóch archiwalnych wersji, a nie błąd brakującego źródła.
- **2025:** 12/12 replay zgodnych bajtowo ze świeżo pobranym właściwym wydaniem EIA; są **poza zakresem wcześniejszego 36/36**.
- **WTI/Brent:** dla każdego z 48 replay odczytano pełne 72 miesiące × 2 serie = 144 komórki `2tab`. Wszystkie 48 porównań semantycznie zgodne. Przy zgodnym SHA256 zgodność wszystkich komórek wynika też z identyczności bajtowej; dla `jun24` oba pliki parsowano oddzielnie i porównano także niezaokrąglone wartości Decimal.
- **16/48** capture ma opóźnienie 0–31 dni kalendarzowych względem daty wydania w `America/New_York`. Próg 31 dni to wyłącznie opis bliskości, nie kryterium certyfikacji PIT. Pozostałe 32 kopie są późniejsze; ich status near-release pozostaje **UNKNOWN**.
- **Pierwsza wersja w momencie publikacji: UNKNOWN dla wszystkich 48.** Dla `may23` istnieje kopia z tego samego dnia w USA, lecz już po ogłoszonej tekstowej republice raportu. `PASS` dotyczy pozyskania i weryfikacji konkretnych bajtów w konkretnym capture, nigdy automatycznie pierwszej publikacji.

## Przyczyna wcześniejszych pustych wyników i metoda

Oficjalne [archiwum EIA](https://www.eia.gov/outlooks/steo/outlook.php) linkuje `https://www.eia.gov/outlooks/steo/archives/jan24_base.xlsx`, **bez `/2024/`**. Wcześniejsze zapytania o `archives/2024/jan24_base.xlsx` dotyczyły innego URL. To wyjaśnia tamten pusty indeks; nie dowodzi braku kopii poprawnego zasobu.

Rzeczywista [kwerenda CDX](https://web.archive.org/cdx/search/cdx?url=eia.gov%2Foutlooks%2Fsteo%2Farchives%2F%2A&output=json&filter=original%3A.%2A%2822%7C23%7C24%7C25%29_base.xlsx.%2A&collapse=urlkey&fl=timestamp%2Coriginal%2Cstatuscode%2Cmimetype%2Cdigest%2Clength&limit=1000), SHA256 pobranej odpowiedzi indeksu `6f45844e77ff1312f7dd88eb708a5f3663fe8c9b24c20f1894cb30f7083d3861`. Zwróciła 48 rekordów; `collapse=urlkey` wybiera pierwszą odpowiedź zwróconą dla klucza URL, nie stanowi dowodu wyczerpującego przeszukania wszystkich archiwów czy aliasów. Każde `id_` pobierano pod dokładnym capture, bez zaakceptowania przekierowania na inny moment lub live EIA. Przejściowe błędy połączenia ponowiono; do zestawienia zaliczono wyłącznie faktycznie zakończone pobrania. Common Crawl dla poprzedniej błędnej ścieżki zwracał 504; nie dowodzi to braku przechwyceń poprawnego URL.

Parser: standardowy ZIP/XML, `xl/workbook.xml` + relacje ustalają rzeczywistą ścieżkę arkusza o nazwie `2tab` (dla `jun24`: `xl/worksheets/sheet4.xml`; nie zakładano numeru arkusza). Shared strings rozwiązują kody `WTIPUUS` w A6 oraz `BREPUUS` w A7; row3 ustala grupy roku, row4 angielskie miesiące. Czytano zapisane wartości komórek, bez wykonywania makr ani przeliczania formuł. Klucz `CODE:YYYY-MM`, wartości Decimal w USD/bbl; hash semantyczny to SHA256 UTF-8 `json.dumps(values, sort_keys=True, separators=(",", ":"))` po formatowaniu do dwóch miejsc dziesiętnych. Nie uruchamiano modelu ani backtestu.

## Pełny manifest pobranych oryginalnych payloadów

Opóźnienie liczone według dat kalendarzowych `America/New_York`; dokładny capture podano w UTC. Kolumna RAW odnosi się do manifestu 36/36 dla lat 2022–24, a dla 2025 do oddzielnie pobranego live EIA. Każdy wiersz ma 144/144 zgodne wartości WTI/Brent. Bajty XLSX nie są dodane do GitHub.

| Wydanie / rzeczywisty replay | Publikacja EIA | Capture UTC | Dni ET | Bajty XLSX | RAW | SHA256 payloadu |
|---|---|---|---:|---:|---|---|
| [jan22](https://web.archive.org/web/20220402091455id_/https://www.eia.gov/outlooks/steo/archives/jan22_base.xlsx) | 2022-01-11 | 2022-04-02 09:14:55 | 81 | 902717 | MATCH | `b60e88599a48cb8f130c464344c0ce5f58de08b3ad92d51e8721cd4449994a49` |
| [feb22](https://web.archive.org/web/20220402091441id_/https://www.eia.gov/outlooks/steo/archives/feb22_base.xlsx) | 2022-02-08 | 2022-04-02 09:14:41 | 53 | 903361 | MATCH | `8b4400f482f6359c8cf26d61c1c2fb17dea65dca77ec6b6bdda5f0a1dbc17336` |
| [mar22](https://web.archive.org/web/20220402091450id_/https://www.eia.gov/outlooks/steo/archives/mar22_base.xlsx) | 2022-03-08 | 2022-04-02 09:14:50 | 25 | 901520 | MATCH | `55cc3c995dfa86d60d8cd1d8726020cf96acc1917b4187f4017e8dad42a43d7f` |
| [apr22](https://web.archive.org/web/20220607045919id_/https://www.eia.gov/outlooks/steo/archives/apr22_base.xlsx) | 2022-04-12 | 2022-06-07 04:59:19 | 56 | 903248 | MATCH | `225e7d8e59931a685811b8f868f28322968a06ea6ffbf94f8e57877e56fb74f6` |
| [may22](https://web.archive.org/web/20221006011849id_/http://www.eia.gov/outlooks/steo/archives/may22_base.xlsx) | 2022-05-10 | 2022-10-06 01:18:49 | 148 | 906182 | MATCH | `80deccb17b45d2426788c398f16b55f924583b2228bb8ec1624dfc0ee1d20683` |
| [jun22](https://web.archive.org/web/20221006024206id_/http://www.eia.gov/outlooks/steo/archives/jun22_base.xlsx) | 2022-06-07 | 2022-10-06 02:42:06 | 120 | 876082 | MATCH | `6807e5632b55852f4d1113d0a36ee989bd24e1511cae29a8c6476b87998cb572` |
| [jul22](https://web.archive.org/web/20220716151054id_/https://www.eia.gov/outlooks/steo/archives/jul22_base.xlsx) | 2022-07-12 | 2022-07-16 15:10:54 | 4 | 876707 | MATCH | `8555a9e9d04e80e9fec335ca36bb2ce14737a39b552a8f3e890389ee2c62d918` |
| [aug22](https://web.archive.org/web/20221006012013id_/http://www.eia.gov/outlooks/steo/archives/aug22_base.xlsx) | 2022-08-09 | 2022-10-06 01:20:13 | 57 | 875512 | MATCH | `8196b5dc6900a0b4159af03578084f9243080e26f1f283ffdd3485babb4b44e3` |
| [sep22](https://web.archive.org/web/20221006021743id_/http://www.eia.gov/outlooks/steo/archives/sep22_base.xlsx) | 2022-09-07 | 2022-10-06 02:17:43 | 28 | 874738 | MATCH | `13ee3aec3fc65acacab1d958de3d231d49a6594a5fea70236eb5bd0cf03e9058` |
| [oct22](https://web.archive.org/web/20230510003215id_/https://www.eia.gov/outlooks/steo/archives/oct22_base.xlsx) | 2022-10-12 | 2023-05-10 00:32:15 | 209 | 875390 | MATCH | `630ca3fcb12fba4b25c11247895c552d259604f6911794be213716ee3517519f` |
| [nov22](https://web.archive.org/web/20230517064326id_/https://www.eia.gov/outlooks/steo/archives/nov22_base.xlsx) | 2022-11-08 | 2023-05-17 06:43:26 | 190 | 875456 | MATCH | `a0a0d4b0cc676aac5eab4f841cdb942c6f3aa6def854c35bd5d5aa8afbaf1c25` |
| [dec22](https://web.archive.org/web/20230510014714id_/https://www.eia.gov/outlooks/steo/archives/dec22_base.xlsx) | 2022-12-06 | 2023-05-10 01:47:14 | 154 | 873128 | MATCH | `7cdba7db9a5a3380deb3b6e15b39167e80ed6301427de4e6d5ae008449645db5` |
| [jan23](https://web.archive.org/web/20230510051432id_/https://www.eia.gov/outlooks/steo/archives/jan23_base.xlsx) | 2023-01-10 | 2023-05-10 05:14:32 | 120 | 874125 | MATCH | `3e9f69db5383c1b81450a60abdf8e3fbf932ca7d7301a6d516515520c12a799d` |
| [feb23](https://web.archive.org/web/20230510011802id_/https://www.eia.gov/outlooks/steo/archives/feb23_base.xlsx) | 2023-02-07 | 2023-05-10 01:18:02 | 91 | 876910 | MATCH | `aeee3b3d69fbc09f7a64091ad1bf5c8582074fdd7e47a4bdd9b5d2c619ec2661` |
| [mar23](https://web.archive.org/web/20230521080607id_/https://www.eia.gov/outlooks/steo/archives/mar23_base.xlsx) | 2023-03-07 | 2023-05-21 08:06:07 | 75 | 888971 | MATCH | `dc4661a7f2ffb83e0c78dd350734bcc8307a28886f8ff114343adcc9ea6b2eda` |
| [apr23](https://web.archive.org/web/20230510061349id_/https://www.eia.gov/outlooks/steo/archives/apr23_base.xlsx) | 2023-04-11 | 2023-05-10 06:13:49 | 29 | 894441 | MATCH | `ae785b551cfef4cd2f082ccabe1a0189ba8ce273e8b6efc50dfca22ae35fc65f` |
| [may23](https://web.archive.org/web/20230510023812id_/https://www.eia.gov/outlooks/steo/archives/may23_base.xlsx) | 2023-05-09 | 2023-05-10 02:38:12 | 0 | 892322 | MATCH | `c564333f36f85a57f8c96b4deca15a24b935f6d2a2b1b5d472d32245057a6e20` |
| [jun23](https://web.archive.org/web/20230612045620id_/https://www.eia.gov/outlooks/steo/archives/jun23_base.xlsx) | 2023-06-06 | 2023-06-12 04:56:20 | 6 | 891982 | MATCH | `0b01e5c4d270c02b4c37e82d73b24afff498bebbe27510cfec5a9b48d3ddba17` |
| [jul23](https://web.archive.org/web/20230803091522id_/https://www.eia.gov/outlooks/steo/archives/jul23_base.xlsx) | 2023-07-11 | 2023-08-03 09:15:22 | 23 | 888635 | MATCH | `fdc949682f272ee2235e817c124362fab3b97a6634ea9389dafc5b255ddfb45a` |
| [aug23](https://web.archive.org/web/20231107030152id_/https://www.eia.gov/outlooks/steo/archives/aug23_base.xlsx) | 2023-08-08 | 2023-11-07 03:01:52 | 90 | 888819 | MATCH | `a71e1be2e0d28080e1a178aadc85670f3ec75252708f838beb2fe2ee22d2c3cf` |
| [sep23](https://web.archive.org/web/20241001193324id_/https://www.eia.gov/outlooks/steo/archives/sep23_base.xlsx) | 2023-09-12 | 2024-10-01 19:33:24 | 385 | 890187 | MATCH | `9afe1f7d73678cfe5c5fc359fd0bbb9d0e3abbe316b0c5ef42643df61aa4ec69` |
| [oct23](https://web.archive.org/web/20231110041241id_/https://www.eia.gov/outlooks/steo/archives/oct23_base.xlsx) | 2023-10-11 | 2023-11-10 04:12:41 | 29 | 893069 | MATCH | `9052f233f79c28dcd9a1cd863adc59b2f39f5bcb266b3cbceb6a1579ee93b757` |
| [nov23](https://web.archive.org/web/20240930194142id_/https://www.eia.gov/outlooks/steo/archives/nov23_base.xlsx) | 2023-11-07 | 2024-09-30 19:41:42 | 328 | 891248 | MATCH | `1a5b2a74cb04615e111461dc5fb895951dea41787fab4967968d7e1136c6f966` |
| [dec23](https://web.archive.org/web/20241001124403id_/https://www.eia.gov/outlooks/steo/archives/dec23_base.xlsx) | 2023-12-12 | 2024-10-01 12:44:03 | 294 | 890298 | MATCH | `b46feff4942376e2537b58c864cfc75e873d73f1a7582f532e3244f777ad6cea` |
| [jan24](https://web.archive.org/web/20240124194116id_/https://www.eia.gov/outlooks/steo/archives/jan24_base.xlsx) | 2024-01-09 | 2024-01-24 19:41:16 | 15 | 895354 | MATCH | `663ee3c648d2e88dad48dd1efd2557df99c811afe4afcc2094ed92c988fb53a9` |
| [feb24](https://web.archive.org/web/20241002055014id_/https://www.eia.gov/outlooks/steo/archives/feb24_base.xlsx) | 2024-02-06 | 2024-10-02 05:50:14 | 239 | 895087 | MATCH | `dc3742fe43299f5288533d328c86c8435bc8223d92e26ad418ee276b2890aae3` |
| [mar24](https://web.archive.org/web/20241003114641id_/https://www.eia.gov/outlooks/steo/archives/mar24_base.xlsx) | 2024-03-12 | 2024-10-03 11:46:41 | 205 | 893332 | MATCH | `0f168cec985f5511c93b6238cfc27cacf4df1f2dd890ce01d23fd1e81c30b513` |
| [apr24](https://web.archive.org/web/20240929171341id_/https://www.eia.gov/outlooks/steo/archives/apr24_base.xlsx) | 2024-04-09 | 2024-09-29 17:13:41 | 173 | 889282 | MATCH | `144ffbf52092468b4bccdd58b94dfacf4b603351ec7dba54fafb1d4b8b6a9095` |
| [may24](https://web.archive.org/web/20240531043235id_/https://www.eia.gov/outlooks/steo/archives/may24_base.xlsx) | 2024-05-07 | 2024-05-31 04:32:35 | 24 | 918789 | MATCH | `b26d58c911a0878fd615aedd164a2d4796927146c45654d90edcb457ca57f8ea` |
| [jun24](https://web.archive.org/web/20240613190415id_/https://www.eia.gov/outlooks/steo/archives/jun24_base.xlsx) | 2024-06-11 | 2024-06-13 19:04:15 | 2 | 1024116 | DIFFERENT | `dde84a2e66e7652b75a2db8f6e24059e05d105a4d2dcce59dc1f920a717487c7` |
| [jul24](https://web.archive.org/web/20240930013959id_/https://www.eia.gov/outlooks/steo/archives/jul24_base.xlsx) | 2024-07-09 | 2024-09-30 01:39:59 | 82 | 1029673 | MATCH | `066eb3d2691a4ace702483ee4a73f64c6d9899a692edb4b9171d94b986b369dd` |
| [aug24](https://web.archive.org/web/20241003114640id_/https://www.eia.gov/outlooks/steo/archives/aug24_base.xlsx) | 2024-08-06 | 2024-10-03 11:46:40 | 58 | 1036675 | MATCH | `a4679e91622d5d8d414954b988afdb4119690e7d0b1e458e30be0ca7666ca826` |
| [sep24](https://web.archive.org/web/20241001190233id_/https://www.eia.gov/outlooks/steo/archives/sep24_base.xlsx) | 2024-09-10 | 2024-10-01 19:02:33 | 21 | 1077707 | MATCH | `3b663f40f03a86483340e9cb7fd66c6e05e0b5acd2771c56497728fcb478a7dd` |
| [oct24](https://web.archive.org/web/20241101032537id_/https://www.eia.gov/outlooks/steo/archives/oct24_base.xlsx) | 2024-10-08 | 2024-11-01 03:25:37 | 23 | 1073890 | MATCH | `3825256dd82e3347df45632c1320e73d38acb82e4a5f2ebe5197148844dc9ba4` |
| [nov24](https://web.archive.org/web/20241128134841id_/https://www.eia.gov/outlooks/steo/archives/nov24_base.xlsx) | 2024-11-13 | 2024-11-28 13:48:41 | 15 | 1071832 | MATCH | `0aea752a8bd2991df43b028a9d10d673ee98710a99cd9e1864d936ba9b7059bb` |
| [dec24](https://web.archive.org/web/20250203023401id_/https://www.eia.gov/outlooks/steo/archives/dec24_base.xlsx) | 2024-12-10 | 2025-02-03 02:34:01 | 54 | 1072290 | MATCH | `b650cb965a38a67e8b5e2f4d8df794b8ddfab6a429fca551cc1c7ff404ffb396` |
| [jan25](https://web.archive.org/web/20250203023502id_/https://www.eia.gov/outlooks/steo/archives/jan25_base.xlsx) | 2025-01-14 | 2025-02-03 02:35:02 | 19 | 1062694 | MATCH | `67f9f24b6f0bd074bcc92e47f8f5ea23594f2dd6ccbf31b2dff912621bbb5b22` |
| [feb25](https://web.archive.org/web/20250317135224id_/https://www.eia.gov/outlooks/steo/archives/feb25_base.xlsx) | 2025-02-11 | 2025-03-17 13:52:24 | 34 | 1066543 | MATCH | `64ac0e0d1d7e084745ebd88b4a234c57f7fdc3a6c652a91c79147d199bbbdb01` |
| [mar25](https://web.archive.org/web/20251128183926id_/https://www.eia.gov/outlooks/steo/archives/mar25_base.xlsx) | 2025-03-11 | 2025-11-28 18:39:26 | 262 | 1066400 | MATCH | `62dc490de708892d24411fe7e6902cc57ad63b60e5c8b864d9f3bdaeea89ce29` |
| [apr25](https://web.archive.org/web/20251127223628id_/https://www.eia.gov/outlooks/steo/archives/apr25_base.xlsx) | 2025-04-10 | 2025-11-27 22:36:28 | 231 | 1066920 | MATCH | `b3dab5214dcc1c3dae3cea87431e6a781769996adc702b21d35eb254c0345ad4` |
| [may25](https://web.archive.org/web/20251127235501id_/https://www.eia.gov/outlooks/steo/archives/may25_base.xlsx) | 2025-05-06 | 2025-11-27 23:55:01 | 205 | 1070549 | MATCH | `ea81918222483bafd3bcbdd98f52c2b1f17cb6470c3830a6a0deb8bd213fe228` |
| [jun25](https://web.archive.org/web/20251127221020id_/https://www.eia.gov/outlooks/steo/archives/jun25_base.xlsx) | 2025-06-10 | 2025-11-27 22:10:20 | 170 | 1072200 | MATCH | `332f761e85c7ab3d5f4eded212f30987a409cb19042072e90b3af9bd9bcf5164` |
| [jul25](https://web.archive.org/web/20251130081851id_/https://www.eia.gov/outlooks/steo/archives/jul25_base.xlsx) | 2025-07-08 | 2025-11-30 08:18:51 | 145 | 1074641 | MATCH | `4231a27728d8c6f99dda0e51796e3b7a18e39f4fdcd2edfb4d8a43eadb0e850e` |
| [aug25](https://web.archive.org/web/20251127225537id_/https://www.eia.gov/outlooks/steo/archives/aug25_base.xlsx) | 2025-08-12 | 2025-11-27 22:55:37 | 107 | 1082741 | MATCH | `31e4bec79e50872816cf7c300501e0a462b50f7316eba7011ae4cec3e2b8e64f` |
| [sep25](https://web.archive.org/web/20251130064458id_/https://www.eia.gov/outlooks/steo/archives/sep25_base.xlsx) | 2025-09-09 | 2025-11-30 06:44:58 | 82 | 1084923 | MATCH | `8f1665eebc7fda9f4bd67c53e6b0e3452f777247d292be4ffbbb9644a03e742e` |
| [oct25](https://web.archive.org/web/20251128000646id_/https://www.eia.gov/outlooks/steo/archives/oct25_base.xlsx) | 2025-10-07 | 2025-11-28 00:06:46 | 51 | 1085972 | MATCH | `01aba5772bdeb3d07ee7b5381bfb0dda6f14275f3ec11c05b9e09f2f8cff24b6` |
| [nov25](https://web.archive.org/web/20251127220432id_/https://www.eia.gov/outlooks/steo/archives/nov25_base.xlsx) | 2025-11-12 | 2025-11-27 22:04:32 | 15 | 1083120 | MATCH | `23f7044def86525fefcef30dce3e4aeec6b46cf1f56ad9809eb91455f8daceef` |
| [dec25](https://web.archive.org/web/20260505013924id_/https://www.eia.gov/outlooks/steo/archives/dec25_base.xlsx) | 2025-12-09 | 2026-05-05 01:39:24 | 146 | 1083990 | MATCH | `0531b7d5f0d1af686fd7afcc91461dcb4a4960d3f76ebb673776946df383253e` |

## Near-release: 16 konkretnych łańcuchów dowodowych

WARC source poniżej to rzeczywisty nagłówek replay `x-archive-src`; CDX SHA1 jest base32 i został porównany z hashem pobranej treści. Bezpośrednia próba pobrania publicznego indeksu `.warc.os.cdx.gz` dla `jul22` zwracała HTTP 401; nie pobierano raw kontenera ani jego WARC-Record-ID/offsetu. Nie mylić tego ograniczenia z brakiem zweryfikowanego oryginalnego payloadu replay.

| Wydanie | CDX SHA1 payloadu (zweryfikowany) | `x-archive-src` |
|---|---|---|
| `mar22` | `QCKCQKZ4EBL6FQL7BYIYRQRXQ37PUCE5` | `archiveteam_urls_20220402100613_14fee060/urls_20220402100613_14fee060.1606352862.megawarc.warc.zst` |
| `jul22` | `XXIP6MC6VMSW6WBN77MZ4LYMESRN5ANK` | `spn-outlinks-20220716142010-crawl409/spn-outlinks-20220716145739-16314.warc.gz` |
| `sep22` | `JOC2SRR4UO6DVEQIQA5433DGF4PJKS36` | `archiveteam_urls_20221006022320_c5d47496/urls_20221006022320_c5d47496.1650286618.megawarc.warc.zst` |
| `apr23` | `ZKWPMS3X4J7MJQK4KC3NB3KSXX5M4N3C` | `archiveteam_urls_20230510062125_bbfa9c71/urls_20230510062125_bbfa9c71.1650286618.megawarc.warc.zst` |
| `may23` | `NDTBAEMJ4WIHZC2ZYUVELWLRZJ6OSDLQ` | `archiveteam_urls_20230510024510_e6c6960a/urls_20230510024510_e6c6960a.1650286618.megawarc.warc.zst` |
| `jun23` | `SHGB4J6ONCO2WPILI4WZQV5NHQYZPMP5` | `archiveteam_urls_20230612050450_29912e4b/urls_20230612050450_29912e4b.1650286618.megawarc.warc.zst` |
| `jul23` | `WP4TA5FEU2XPV5KRLR3RGJQDHJDKJAWY` | `archiveteam_urls_20230803091642_5b2acd7e/urls_20230803091642_5b2acd7e.1650286618.megawarc.warc.zst` |
| `oct23` | `BIHINYDJYDJHKAOPNIFWMYLAAR5YCQAA` | `archiveteam_urls_20231110041403_014cea0f/urls_20231110041403_014cea0f.1650286618.megawarc.warc.zst` |
| `jan24` | `6STOG6XMWFFGG7IJOYT5RISH4PHUSM6S` | `archiveteam_urls_20240124194356_3295b2db/urls_20240124194356_3295b2db.1650286618.megawarc.warc.zst` |
| `may24` | `7ON7RODXWQLY4GIWNGITNLRVKKTDVHEQ` | `archiveteam_urls_20240531043628_13db412d/urls_20240531043628_13db412d.1715702844.megawarc.warc.zst` |
| `jun24` | `OT4GG6FWT6W4LEUVTSLFRWQ4KLB6BDPT` | `archiveteam_urls_20240613190722_b785a011/urls_20240613190722_b785a011.1715702844.megawarc.warc.zst` |
| `sep24` | `OLXLCCTX5P7UY7BF5NQXWXAXG4DLLQUX` | `EOT24PRE-20241001185155-crawl912/EOT24PRE-20241001185734-12079.warc.gz` |
| `oct24` | `ADPQNQYRIEGABYJGGP3YHVKDO2XZ5TLB` | `archiveteam_urls_20241101034917_c5e897ab/urls_20241101034917_c5e897ab.1726247528.megawarc.warc.zst` |
| `nov24` | `ZBQWRVZTJMS234W6CON3TJKZSHZDUNYT` | `EOT24INTERIM-20241128133829-crawl912/EOT24INTERIM-20241128134609-00791.warc.gz` |
| `jan25` | `5FV4ZQI75255JCS7UIBS6TDSJQTNMXO3` | `archiveteam_archivebot_go_20250203024723_89f30adf/www.eia.gov-inf-20250202-214554-5c9rx-00003.warc.gz` |
| `nov25` | `BPY6I7V2YXH23MP5YNNBH6RUEXITOR72` | `archiveteam_urls_20251127220736_e07f021e/urls_20251127220736_e07f021e.1762161290.megawarc.warc.zst` |

Przykładowe **rzeczywiste** wartości prognoz dla miesiąca następującego po wydaniu; WTI i Brent w USD/bbl. Pełne porównanie obejmowało 144 komórki na wydanie, a nie tylko próbkę.

| Wydanie | Miesiąc docelowy | WTI (komórka) | Brent (komórka) |
|---|---|---|---|
| `mar22` | 2022-04 | 113.00 (`BB6`) | 117.00 (`BB7`) |
| `jul22` | 2022-08 | 98.50 (`BF6`) | 104.00 (`BF7`) |
| `sep22` | 2022-10 | 93.00 (`BH6`) | 99.00 (`BH7`) |
| `apr23` | 2023-05 | 80.00 (`BC6`) | 86.00 (`BC7`) |
| `may23` | 2023-06 | 70.00 (`BD6`) | 75.00 (`BD7`) |
| `jun23` | 2023-07 | 73.00 (`BE6`) | 78.00 (`BE7`) |
| `jul23` | 2023-08 | 73.00 (`BF6`) | 78.00 (`BF7`) |
| `oct23` | 2023-11 | 87.00 (`BI6`) | 91.00 (`BI7`) |
| `jan24` | 2024-02 | 78.50 (`AZ6`) | 83.00 (`AZ7`) |
| `may24` | 2024-06 | 85.50 (`BD6`) | 90.00 (`BD7`) |
| `jun24` | 2024-07 | 76.50 (`BE6`) | 81.00 (`BE7`) |
| `sep24` | 2024-10 | 77.00 (`BH6`) | 81.00 (`BH7`) |
| `oct24` | 2024-11 | 72.00 (`BI6`) | 76.00 (`BI7`) |
| `nov24` | 2024-12 | 73.00 (`BJ6`) | 77.00 (`BJ7`) |
| `jan25` | 2025-02 | 72.00 (`AZ6`) | 76.00 (`AZ7`) |
| `nov25` | 2025-12 | 56.00 (`BJ6`) | 60.00 (`BJ7`) |

## `jun24`: potwierdzona zmiana bajtów; WTI/Brent bez wykrytej zmiany

- Capture [2024-06-13 19:04:15 UTC](https://web.archive.org/web/20240613190415id_/https://www.eia.gov/outlooks/steo/archives/jun24_base.xlsx): **1 024 116 bajtów**, SHA256 `dde84a2e66e7652b75a2db8f6e24059e05d105a4d2dcce59dc1f920a717487c7`.
- Późniejszy, również rzeczywiście pobrany [capture 2024-10-02 19:57:59 UTC](https://web.archive.org/web/20241002195759id_/https://www.eia.gov/outlooks/steo/archives/jun24_base.xlsx): **1 024 084 bajty**, SHA256 `12cd939ba0d9d6b559d56d40cc0650e99c57d249fff1ecc691af601a2e0de636`; ten sam SHA co manifest 36/36 (Zenodo May2025 / EIA Oct2026). CDX SHA1 `QKP2MSDLU66D36THJKJQKM2VG5NVSYNU`, `x-archive-src=EOT24PRE-20241002195040-crawl806/EOT24PRE-20241002195652-05516.warc.gz`.
- Wszystkie **144/144 WTI/Brent** są zgodne nawet jako niezaokrąglone Decimal; 0 różnic ceny. Nie tylko kosmetyczny hash całego ZIP: różni się 29 rozpakowanych komponentów (core properties, workbook XML i 27 worksheet XML), w tym XML właściwego `2tab`. Nie oznacza to zmiany sprawdzonych dwóch serii.
- Hash semantyczny WTI/Brent obu wersji: `265e6e637188629176326c8dc3b07a3064e456e82c4a1a2684350518d8583274`. Przykłady: lipiec 2024 `BE6=76.50`, `BE7=81.00`; wrzesień `BG6=81.50`, `BG7=86.00`; grudzień `BJ6=82.50`, `BJ7=87.00`.
- [Oficjalny notice 2024-06-27](https://www.eia.gov/outlooks/steo/archives/notice_data_06_27_2024.php) wskazuje korektę Table10b i repost raportu. Nie przypisujemy automatycznie całej wykrytej różnicy temu notice; dwa capture wyznaczają tylko granice obserwowanej różnicy. Brak dowodu dokładnego momentu modyfikacji lub niezmienności pomiędzy capture.
- Poprzedni wynik **36/36 May2025 ↔ Oct2026 pozostaje prawdziwy w swoim zakresie**. Nowy wynik **35/36 najwcześniejszych zwróconych kopii Wayback ↔ tamten manifest** ma inny przedział czasowy i ujawnia wcześniejszą wersję `jun24`.

## `may23`: ten sam dzień publikacji w USA, ale po republice

`2023-05-10T02:38:12Z` = **2023-05-09T22:38:12-04:00 America/New_York**, zatem opóźnienie 0 dni ET (1 dzień przy naiwnym liczeniu dat UTC). [Oficjalny notice](https://www.eia.gov/outlooks/steo/archives/notice_data_05_09_2023.php) opisuje wydanie o 12:00 i tekstowy repost o 14:00 dnia 9 maja. Kopia wieczorna jest potwierdzonym plikiem z dnia wydania; nie dowodzi bajtów pierwszej wersji o 12:00 ani tego, że tekstowy repost zmienił XLSX. Availability można kotwiczyć najwcześniej do zweryfikowanego momentu capture, nie cofać jej do południa.

## Wcześniejszy niezależny depozyt Zenodo — rzeczywiste XLSX Jan–Apr2025

[Zenodo 15312755](https://zenodo.org/records/15312755), utworzony `2025-04-30T19:34:05.534618+00:00`, publication date **2025-04-30**. Rzeczywiście pobrano [eiasteo-2025.zip](https://zenodo.org/records/15312755/files/eiasteo-2025.zip?download=1), **31093498 bajtów**, zgodny manifest MD5 `b9a5056188e963bab5f56aa7cbb9af6e`, wyliczony SHA256 `8fe1de89b7491d22f1e51e7fc54fddaab7be833f9b0f744eb46867ebcd2a8dbe`. Odczytano oryginalne miesięczne człony ZIP, nie arkusze wykresów ani odtworzone dane.

| Człon ZIP | Oryginalny SHA256 XLSX | Zgodność raw z live EIA i WTI/Brent |
|---|---|---|
| `2025-01/jan25_base.xlsx` | `67f9f24b6f0bd074bcc92e47f8f5ea23594f2dd6ccbf31b2dff912621bbb5b22` | MATCH; 144/144 |
| `2025-02/feb25_base.xlsx` | `64ac0e0d1d7e084745ebd88b4a234c57f7fdc3a6c652a91c79147d199bbbdb01` | MATCH; 144/144 |
| `2025-03/mar25_base.xlsx` | `62dc490de708892d24411fe7e6902cc57ad63b60e5c8b864d9f3bdaeea89ce29` | MATCH; 144/144 |
| `2025-04/apr25_base.xlsx` | `b3dab5214dcc1c3dae3cea87431e6a781769996adc702b21d35eb254c0345ad4` | MATCH; 144/144 |

**`apr25`**: wydanie 2025-04-10; niezależny depozyt opublikowany 2025-04-30, czyli 20 dni później. Dowód daty depozytu nie podaje dokładnego momentu pierwotnego pobrania XLSX. Maj2025 w `2tab`: WTI `62.00`, Brent `66.00` USD/bbl. `jan25`/`feb25`/`mar25` w tym depozycie są starsze niż 31 dni; nie nazywać ich near-release na podstawie tej daty. `jan25` ma osobno znacznie wcześniejszy Wayback 2025-02-03.

Metadane tego wcześniejszego rekordu mają te same zadeklarowane MD5 rocznych ZIP 2022–24 co rekord 15386905. W tej sesji nie pobierano ponownie tych trzech ZIP z 15312755, więc nie awansujemy automatycznie dowodu pełnych 36 SHA do kwietniowego depozytu.

## Repozytorium, CI, wpływ i dalszy krok

- Sprawdzony `main`: `fe986b23b47d080302b253eb87bbf7a10a93b0d4`. Ostatnie SUCCESS [regression 39444963465](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963465) i [real-source 36/36 39444963696](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963696) są przypisane do **`f4a6bc3f396b6b09c12e98adac700fd3e43c11a2`**, nie do obecnego main. Porównanie GitHub wskazuje 7 późniejszych commitów i wyłącznie pliki Markdown. Lista check-runs na dokładnym obecnym main była pusta.
- PR #52 OPEN, nie scalony; przed tym uzupełnieniem head `5d67ebc750e1a51fd44f383ed6d0a102257679bf`, tylko GitGuardian SUCCESS; API workflow runs dla tego exact SHA zwróciło 0. Review bez uwag dotyczył jeszcze `98683e0`, więc nie jest review nowego raportu. Nie uruchamiano nowych Actions ani nie przedstawiano lokalnego source research jako CI PASS.
- Zmiana tylko w tym raporcie i opisie/komentarzu PR; bez kodu produkcyjnego, ponownego trenowania, backtestów, nowych workflow i harmonogramów, Neon, sekretów, ACL, realnych transakcji i zmian portfela. M1–M3 `HOLD_NO_CHANGE`; zamknięty backup nietknięty.
- Kontrola: 48 URL/capture/digest/payload/OOXML + porównania SHA i 144 wartości, 4 miesięczne oryginalne XLSX z ZIP Zenodo, dodatkowy późniejszy replay `jun24`. Nie dodawano testów dla dokumentacji; nie deklarujemy nowego pełnego CI. Rollback wyłącznie dokumentacji: odwrócenie commita tego raportu; bez skutków w danych/modelach.
- Następny research: dla wydania wymagającego first-release provenance szukać capture **przed znanym repost** oraz sprawdzić aliasy URL i inne archiwa. Dla `nov23` obecna kopia jest dopiero z 2024-09-30, 328 dni po wydaniu; near-release nadal UNKNOWN. Wcześniejsze nieweryfikowane okresy i 316 par nie uzyskują zbiorczo statusu PIT ani alpha. Nie stroić modeli ponownie.

---

## Historyczny dziennik wcześniejszych prób (poniższe UNKNOWN dotyczyło ówczesnego braku bajtów)

## Purpose / boundary
Read-only investigation of **independently timestamped original XLSX captures close to actual STEO publication days**. This note does not certify first-release bytes, claim a tradable backtest, change any strategies, or write Neon. No old models re-fitted. `M1–M3=HOLD_NO_CHANGE`.

## Baseline (already proved, NOT new near-day evidence)
The existing [36/36 report](STEO_INDEPENDENT_ZENODO_36_BYTE_MATCH_2026_10_20_PL.md), [real run 39444963696](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963696), and [Catalyst Cooperative Zenodo record 15386905](https://zenodo.org/records/15386905) demonstrate May-2025 independent ZIP copies identical at original XLSX SHA-256 level to the files downloaded from EIA in October 2026. They do **not** establish raw bytes as actually published on the original 2022–24 release days.

## Candidates reviewed 2026-10-20
| Issue | Official EIA release date | First-issue original SHA-256 from near-day independent capture | WTI/Brent Table 2 comparison | Outcome |
| --- | --- | --- | --- | --- |
| `nov23` | 2023-11-07 | Not recovered | Not possible without captured original workbook | **UNKNOWN** |
| `jan24` | 2024-01-09 | Not recovered | Not possible without captured original workbook | **UNKNOWN** |
| `jan25` | 2025-01-14 (official EIA archive) | Not recovered | Not possible without captured original workbook | **UNKNOWN** |

The [official EIA STEO archive](https://www.eia.gov/outlooks/steo/outlook.php) verifies January 2025 release as **2025-01-14** (with separate official correction notice), in addition to the other dates, and exposes release dates and XLSX links, but contemporaneous web pages are **not** independently timestamped original file captures. The 2023 November notice documents reposting of other tables, without establishing unchanged WTI/Brent Table 2 or original XLSX byte status; see [notice register](STEO_OFFICIAL_ERRATA_PROVENANCE_2026_10_20_PL.md).

**Internet Archive Wayback CDX**: retried public index URL query for `jan24_base.xlsx` in the 2024 window; client returned *not accessible*. **Not evidence that no capture exists**. No replay WARC/HTTP body, timestamp, or binary SHA-256 recovered. Therefore no hash equality or WTI/Brent equivalence conclusion.

**Common Crawl**: [official index catalogue](https://index.commoncrawl.org/collinfo.json) and [format/access documentation](https://www.commoncrawl.org/get-started) confirmed that 2023–2024 index and WARC collections exist and expose timestamped crawls in principle. Attempted `CC-MAIN-2024-10-index` query for the `jan24_base.xlsx` exact URL, but the index query endpoint was not accessible in this browsing client. The mere existence of a crawl index is **not evidence it contains this Excel attachment**. No relevant index record, WARC payload, SHA-256, or Table 2 values were obtained.

Independent [Archive-It CDX/C documentation](https://support.archive-it.org/hc/en-us/articles/115001790023-Access-Archive-It-s-Wayback-index-with-the-CDX-C-API) identifies another collection-scoped archived index with timestamp and WARC retrieval metadata, but no STEO capture verified there. A discovered third-party GitHub STEO scraping project contains processed artefacts, not a verified dated original-month XLSX capture with independent binary receipt. It has **not** been treated as original byte evidence.

## Acceptance gates for any future promotion from UNKNOWN
1. Verify curator independence, actual immutable archive/capture timestamp and canonical captured target URL against official EIA release day; distinguish dated index metadata, redirect, link-only HTML and genuine binary HTTP 200 payload.
2. Retrieve the **actual archived XLSX response body**, not today's live EIA bytes or a regenerated workbook. Preserve response metadata, exact byte length and SHA-256, and evidence URL/record ID.
3. Compare with the published original-source SHA list in [36/36 report](STEO_INDEPENDENT_ZENODO_36_BYTE_MATCH_2026_10_20_PL.md), then parse `2tab` for `WTIPUUS` and `BREPUUS` values using the existing source reader; record distinct byte and semantic comparison outcomes.
4. Only record `PASS` for the narrowly supported claim (for instance, first independently archived copy **after** release), never infer exact day-one publication authenticity from a capture days/weeks later.
5. A missing, unavailable or metadata-only capture stays `UNKNOWN` rather than `PASS` or `FAIL`. Keep historical `PIT_CERTIFIED=false` unless a defensible issue-day provenance chain truly exists.

## End-of-session operational facts
Initial repo head inspected: `fe986b23b47d080302b253eb87bbf7a10a93b0d4`; recent listed actual [source workflow 39444963696](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963696) SUCCESS; [main regression 39444963465](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963465) SUCCESS; [PR CI 39444788790](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444788790) SUCCESS. At inspection, open PR #1; open issues #2, #3, #4, #22. No new data-source CI run launched, no file hash claims invented. This research note is documentation-only, submitted through PR for review. No Neon writes, no permissions/secrets/schedules/paid services, no trades or model tuning. Closed MyDevil+Mac backup unchanged.


## Additional source discovery — same-day continuation

Public search identified later Catalyst Cooperative / Zenodo **records [15877499](https://zenodo.org/records/15877499), [16893042](https://zenodo.org/records/16893042), [17119793](https://zenodo.org/records/17119793)**. Their published annual 2022–24 ZIP MD5 values are the same as May-2025 [record 15386905](https://zenodo.org/records/15386905): 2022 `cff52df8d14f214df0c1a47a0a3185e7`, 2023 `0f59168a86433af4e0e7be53c4684535`, 2024 `21b1dc10ba6503b4446143e212ada2a0`. These are *later versions of the same curator archive*, NOT earlier independent issue-day captures. They add no evidence that 2022–24 source bytes were available on first publication day. Annual ZIP metadata agreement is not an actual per-month replay in this session; the prior 36/36 run remains the supporting actual original-XLSX comparison.

Independent third-party [NatGas-Consumption-Forecast](https://github.com/DamirStyles/NatGas-Consumption-Forecast) README explicitly instructs users to download STEO vintages from PUDL/Zenodo; this is **derivative reuse** and does not furnish an independently captured first-release original XLSX. Older [EIA-STEO scraping project](https://github.com/leachandrew/EIA-STEO) contains processed files and an unrelated `aeso_proj_list.xlsx`, with no demonstrated authentic `jan24_base.xlsx` original from 2024-01-09.

**Result:** extra repositories are not a substitute for contemporaneous WARC payload. Original near-release raw SHA-256 and `WTIPUUS`/`BREPUUS` values continue **UNKNOWN**. No invented attestation, no new real source CI, no model execution.


## Follow-up 2026-10-20 — official correction chronology cross-check (no new XLSX payload claim)

Primary-source [EIA May 9, 2023 notice](https://www.eia.gov/outlooks/steo/archives/notice_data_05_09_2023.php) explicitly dates the original report to **12:00 US Eastern** and the corrected **text** repost to **14:00 US Eastern**. The current earliest verified `may23` XLSX Wayback capture is **22:38:12 EDT**, thus 8h38m12s after the text repost and 10h38m12s after the originally announced report release. These intervals are based on the reported clock times (without evidence of seconds for release/repost). **There is no verified pre-14:00 captured original XLSX in the present evidence set.** Notice concerns erroneous temperature-description text; it does not explicitly state that XLSX was reposted or revised. First-issue raw XLSX remains **UNKNOWN**.

Primary-source [EIA June 27, 2024 notice](https://www.eia.gov/outlooks/steo/archives/notice_data_06_27_2024.php) specifies incorrect **Table 10b** values for `SNGPRPM` and `SNGPRL48`, and repost of the report **June 27 at 13:30 EDT**. The verified `jun24` XLSX Wayback **June 13 19:04:15 UTC = 15:04:15 EDT** predates the notice by almost 14 days; the **Oct 2 19:57:59 UTC = 15:57:59 EDT** replay postdates it. The two observed raw SHA-256 versions are `dde84a2e66e7652b75a2db8f6e24059e05d105a4d2dcce59dc1f920a717487c7` (pre-notice capture) and `12cd939ba0d9d6b559d56d40cc0650e99c57d249fff1ecc691af601a2e0de636` (post-notice capture); `WTIPUUS`/`BREPUUS` 144/144 unchanged. **The notice makes Table 10b an exact targeted next comparison, but does not prove the observed workbook change was caused by that correction.** Compare `10b` `SNGPRPM` and `SNGPRL48` on the existing archived original bytes, with original representations and timestamps, rather than inferring from WTI/Brent.

The [official EIA STEO series-change record](https://www.eia.gov/outlooks/steo/report/changes.php) separately lists additional series introduced **June 11, 2024**, including oil and gas production regional series. Initial schema change on release day, later correction on June 27, and observed byte differences between June13/Oct2 are **three distinct facts**, not proof of one causal event.

**Current evidence decisions:** `may23_first_issue_byte_PIT=UNKNOWN`; `jun24_pre_to_post_byte_change=PASS` for these two actual replay timestamps; `jun24_WTI_Brent_semantic_equality=PASS` limited to verified 144 cells; `jun24_Table10b_changed_cells=UNKNOWN` pending exact raw OOXML value comparison. Historical original publication-day exact byte certification stays **UNKNOWN**, no portfolio or strategy inference. Documentation-only, no new CI passed or dispatched.
