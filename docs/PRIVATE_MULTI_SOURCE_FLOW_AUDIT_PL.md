# Investment Strategy Lab — Exchange + Wallet: prywatny rejestr przepływów

**Cel:** odczytowo monitorować wartość *znanego, wycenionego podzbioru* aktywów na Coinbase Exchange i w oddzielnym self-custody Wallet oraz poprawnie klasyfikować już zaobserwowane przepływy. To moduł księgowy/dowodowy, **nie mechanizm wykonywania transakcji**.

## Dlaczego ten moduł?

Zmiana łącznej wartości dwóch miejsc przechowywania nie równa się zyskowi inwestycyjnemu. Przykładowo dodatkowy zewnętrzny wpływ zwiększa wartość, ale nie dowodzi rentowności. Wewnętrzne przesunięcie między własnymi źródłami może zmienić każde lokalne saldo, nie zmieniając nominalnej wartości łącznej (poza rzeczywiście poniesionymi kosztami). Oddzielnie występują zmiany wycen rynkowych, niepełne dane, pozycje stakowane, opłaty i opóźnienia indeksowania blockchaina.

W odpowiedzi na możliwość przyszłych kolejnych wpłat system **rejestruje je tylko jako zgłoszone zewnętrzne przepływy**. Nie wylicza kwot przyszłych wpłat, rekomendowanych transakcji ani planu przenoszenia kryptowalut.

## Dostarczona implementacja

`scripts/private_multi_source_flow_audit.py` to deterministyczny parser i analizator **lokalnego prywatnego** pliku z dwoma snapshotami, tj. saldami wymiany i wycenionego podzbioru walleta. Otrzymuje klasyfikację zaobserwowanych zdarzeń:

- `external_inflow`: historyczny zapis kapitału spoza badanych źródeł.
- `external_outflow`: historyczny zapis wyprowadzenia kapitału poza badany zakres.
- `internal_movement`: historyczny zapis przesunięcia Coinbase Exchange ↔ Wallet — **nigdy nie jest traktowane jako nowa wpłata**.
- `fee_usd`: osobno zgłoszony koszt; nie jest automatycznie zakładany na podstawie wartości przeniesienia.

Dwa znaczniki potwierdzenia każdej strony przepływu (`confirmed_source`, `confirmed_destination`) są **tylko deklaracjami w lokalnym rejestrze**, nie weryfikacją API Coinbase czy blockchaina. Niepotwierdzone przepływy pozostają w stanie `PENDING`, a nieobjaśniona różnica wycen nie jest wtedy obliczana. `reference` jest **nieidentyfikującym, lokalnym identyfikatorem dowodu**, nie hasłem, adresem, kluczem czy zleceniem; powtarzające się ID lub referencje są odrzucane. Niewycenione ERC-20/NFT/DeFi nigdy nie są wpisywane jako zera; ich liczba i ograniczenia pozostają jawne.

## Bezpieczny, wyłącznie syntetyczny przykład formatu

Nie stosować poniższych liczb jako sald prawdziwego rachunku. Przykład pokazuje 50 USD nowego kapitału, 40 USD przepływu wewnętrznego i 0,50 USD zgłoszonych opłat. Zidentyfikowana wartość rośnie z 175,00 USD do 224,50 USD, ale 49,50 USD różnicy **nie jest dochodem**.

```json
{
  "mode": "PRIVATE_READ_ONLY_FLOW_AUDIT",
  "currency": "USD",
  "snapshots": [
    {
      "captured_at": "2026-10-01T12:00:00Z",
      "exchange_observed_at": "2026-10-01T11:55:00Z",
      "wallet_observed_at": "2026-10-01T11:55:00Z",
      "exchange_priced_usd": "100.00",
      "wallet_priced_usd": "75.00",
      "wallet_unpriced_count": 1,
      "wallet_coverage": "BASE_ETHEREUM_WALLET_PRICED_SUBSET",
      "valuation_source": "SYNTHETIC_OFFLINE_FIXTURE"
    },
    {
      "captured_at": "2026-10-20T12:00:00Z",
      "exchange_observed_at": "2026-10-20T11:58:00Z",
      "wallet_observed_at": "2026-10-20T11:58:00Z",
      "exchange_priced_usd": "109.50",
      "wallet_priced_usd": "115.00",
      "wallet_unpriced_count": 1,
      "wallet_coverage": "BASE_ETHEREUM_WALLET_PRICED_SUBSET",
      "valuation_source": "SYNTHETIC_OFFLINE_FIXTURE"
    }
  ],
  "events": [
    {
      "id": "funding_one",
      "reference": "synthetic-fund-001",
      "at": "2026-10-10T00:00:00Z",
      "type": "external_inflow",
      "from": "external",
      "to": "exchange",
      "amount_usd": "50.00",
      "fee_usd": "0",
      "confirmed_source": true,
      "confirmed_destination": true
    },
    {
      "id": "movement_one",
      "reference": "synthetic-move-002",
      "at": "2026-10-15T00:00:00Z",
      "type": "internal_movement",
      "from": "exchange",
      "to": "wallet",
      "amount_usd": "40.00",
      "fee_usd": "0.50",
      "confirmed_source": true,
      "confirmed_destination": true
    }
  ]
}
```

W rzeczywistym lokalnym pliku należy użyć etykiety `PRIVATE_USER_SUPPLIED_REFERENCE`, wyłącznie do wcześniej zaobserwowanych rzeczywistych danych. Nigdy nie umieszczać tam seed phrase, kluczy prywatnych, danych uwierzytelniających, pełnych adresów ani numerów rachunków. Jest to zapis diagnostyczny, a nie instrukcja dokonania wpłaty czy transferu.

## Uruchomienie — bez sieci i bez API rachunku

```bash
python3 -m scripts.private_multi_source_flow_audit \
  --file /PRIVATE/PATH/history.flow-private.json --format markdown
```

Wybór `--format json` zwraca te same policzone pola w strukturze maszynowej. Można także dołączyć niezależny lokalny rejestr do istniejącego monitoringu trzech rynków:

```bash
python3 -m scripts.read_only_portfolio_monitor \
  --portfolio-file /PRIVATE/PATH/coinbase.portfolio-private.json \
  --wallet-snapshot-file /PRIVATE/PATH/wallet.wallet-private.json \
  --flow-audit-file /PRIVATE/PATH/history.flow-private.json
```

W tej drugiej wersji monitoring rynku pobiera wyłącznie publiczne dane rynkowe, a pliki prywatne pozostają na urządzeniu operatora. Bez dostępu do danych sald portfela giełdowego i Wallet nie powstaje wiarygodna łączna wartość. Ustawienia `.gitignore` wykluczają prywatne pliki `*.flow-private.json` i `*.cashflow-private.json` z typowego dodawania do repozytorium; ochrona ta nie zastępuje kontroli historii commitów.

## Matematyka i granice

```
Identified Subtotal = Exchange reference value + Wallet priced subset
Delta = Identified Subtotal(last) - Identified Subtotal(first)
Recorded External Net = Inflows - Outflows
Unexplained Reference Change = Delta - Recorded External Net + Recorded Fees
```

**`Unexplained Reference Change` nie oznacza P&L.** Obejmuje potencjalne zmiany cen, zignorowane prowizje, brakujące zdarzenia, różnice kursowe i niekompletność źródeł. Gdy jakiś przepływ jest niepotwierdzony, różnica nie jest raportowana. Jeśli zakres wyceny walleta zmienił się pomiędzy snapshotami, porównanie jest odrzucane. Raport nie certyfikuje pełnej wartości majątku ani płynności, bo środki stakowane, DeFi, NFT i niektóre sieci mogą być poza zakresem.

Nie ma integracji do składania zleceń, transferowania środków, podpisywania transakcji, zarządzania walletowymi uprawnieniami ani zapisywania danych w Neon. GitHub Actions uruchamia wyłącznie testy na fikcyjnych danych i publiczny raport rynku; nie ma dostępu do prywatnego rejestru.

## Kryteria odbioru

1. Testy: równość wpłat i różnic sald, brak podwójnego księgowania transferu, koszt jako oddzielne pole, odrzucenie duplikatów/odwróconej strony/niepełnej wyceny oraz przyszłych lub niezgodnych timestampów.
2. Działający, niezależny moduł CLI i jego dołączenie do istniejącego raportu.
3. Zielona regresja offline na **dokładnym commicie PR**, jawna ochrona przed zleceniami i zapisami do danych produkcyjnych.
4. Brak rzeczywistych sald, adresów, prywatnych historii lub kluczy w dokumentacji i CI.
5. Bez twierdzenia, że przepływy są zweryfikowane przez oba systemy, gdy operator wprowadził je ręcznie.

**Nierozwiązane:** automatyczny i ciągły import historii transferów z Coinbase Exchange oraz blockchaina, ich potwierdzanie po obu stronach i weryfikacja pełnego P&L. Te zakresy nie są wymagane do tego bezpiecznego modułu odczytowego.
