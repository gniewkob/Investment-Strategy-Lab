# Coinbase MCP — przegląd zakresu i kontrakt P0 (2026-10-24)

**Tryb:** wyłącznie analiza metadanych narzędzi. Bez łączenia z kontem, pobierania prywatnych sald, autoryzacji, zapisów do Neon, płatności x402, swapów, zleceń lub transferów.

## Źródła pierwotne

- [Coinbase AI Agents overview](https://docs.cdp.coinbase.com/ai-agents/overview) — trzy odrębne powierzchnie: Coinbase MCP (giełda), Wallet MCP (self-custody), CDP MCP (platforma developerska).
- [Coinbase MCP](https://docs.cdp.coinbase.com/ai-agents/coinbase-for-agents/coinbase-mcp) — tabela narzędzi, nazwy z prefiksem coinbase_, limity portfolio, wewnętrzny zakres \`transfer\`, x402 i ograniczenia klientów.
- [Wallet MCP](https://docs.cdp.coinbase.com/ai-agents/coinbase-for-agents/wallet-mcp) — zapis tylko za zatwierdzeniem; swap tylko na mainnet.
- [Spend Permissions](https://docs.cdp.coinbase.com/wallets/using-wallets/spend-permissions) — Smart Account, spender, token, allowance, period. To **nie** jest ogólny limit giełdowych zleceń.
- [Agentic Wallet MCP FAQ](https://docs.cdp.coinbase.com/agentic-wallet/mcp/faq) — odrębny portfel płatności x402; limity na wywołanie i na sesję ustawia właściciel, nie agent.

## Co zweryfikowano

- MCP/CLI na giełdzie rozróżnia listę narzędzi od rzeczywistych uprawnień użytkownika i wybranego portfolio. Sama obecność funkcji \`coinbase_orders_create\` w katalogu nie potwierdza, że dany klucz może jej użyć.
- Transfer w Coinbase CLI: wyłącznie pomiędzy portfolio giełdowymi; **nie** stanowi ścieżki wypłaty na zewnętrzny wallet.
- Wyodrębnione portfolio agenta obejmuje spot; US futures wymaga domyślnego portfolio i zależy od jurysdykcji.
- \`coinbase_x402_resources\` odkrywa katalog bez płatności; \`coinbase_x402_fetch\` i \`coinbase_x402_pay\` są płatne. Limit 5 USDC / transakcję to **nie** budżet dzienny ani sesyjny. To, czy narzędzia są dostępne, zależy też od klienta i połączenia.
- Wallet MCP wymaga zatwierdzenia każdego zapisu; ten fakt nie oznacza, że proces nadzorczy Investment Strategy Lab ma dostęp do Wallet MCP.
- CDP token-balance indexer i RPC finalized są dwoma źródłami dowodowymi dla portfela; istniejący supervisor ich nie sumuje ponownie.

## Rzeczywisty stan projektu (z ostatnich PR)

- [PR #71](https://github.com/gniewkob/Investment-Strategy-Lab/pull/71): lokalny automatyczny odczyt Coinbase i adresów EVM; prywatne checkpointy, dashboard, watchdog; **bez operacji finansowych i zapisów do Neon**. Udokumentowana częściowa historia Base przy HTTP 429, bez certyfikacji pełnego uzgadniania.
- [PR #72](https://github.com/gniewkob/Investment-Strategy-Lab/pull/72): referencyjna prezentacja w PLN wg datowanej tabeli NBP; raportuje 501 testów offline i 42 testy instalacyjne.
- Zgodnie z [autonomicznym kontraktem portfela](AUTONOMOUS_PORTFOLIO_PL.md) pełna rekonsyliacja Exchange↔Wallet jest \`false\`, bo źródłowe zdarzenia konta nie zapewniają pewnego onchain tx hash / network linkage. Nie dopasowuj przepływów po samej kwocie i czasie.
- Monitoring jest lokalny. Brak dowodu ciągłości działania, gdy komputer jest wyłączony lub uśpiony.

## Artefakt P0 — powtarzalny audyt katalogu narzędzi

\`scripts.coinbase_mcp_capability_audit\` to niezależny moduł **offline**. Przyjmuje lokalny manifest zawierający tylko nazwy narzędzi, podział na odczyt, funkcje płatne, operacje zmieniające stan i nieznane. *Nie uruchamia żadnego narzędzia ani nie sprawdza tokenów, rzeczywistego scope, funkcjonalności API, portfeli czy finansów*. Nie jest runtime policy gateway; nie zapewnia kontroli dostępu na poziomie platformy.

Przykład wyłącznie syntetyczny, bez danych konta:

\`\`\`json
{
  "mode": "COINBASE_MCP_TOOL_INVENTORY_V1",
  "source": "coinbase_mcp",
  "tool_names": [
    "coinbase_balance",
    "coinbase_products_candles",
    "coinbase_transfer",
    "coinbase_x402_fetch"
  ]
}
\`\`\`

Syntetyczny manifest należy zachować w prywatnej lokalizacji, a następnie można uzyskać klasyfikację:

\`\`\`sh
python -m scripts.coinbase_mcp_capability_audit --file /PRIVATE/coinbase-tool-names.json
\`\`\`

Output jawnie zawiera \`account_permissions_verified=false\`, \`portfolio_scope_verified=false\`, \`live_execution_authorized=false\`, \`financial_operations=0\` i \`x402_payments=0\`; jest to **deklaracja braku wykonania**, nie dowód rzeczywistego audytu autoryzacji. Przyszłe narzędzia o nieznanych nazwach pozostają niezaklasyfikowane/niedopuszczone. Manifest z dodatkowymi polami (np. z kluczem dostępu) jest odrzucany.

## Matryca wdrożenia P0–P5 i zaległości

| Etap | Status oparty na kodzie / PR | Nadal nierozwiązane |
| --- | --- | --- |
| P0 dokumentacja i matryca narzędzi | Ten audyt / testy syntetyczne | Rzeczywiste scope istniejącego połączenia muszą być walidowane osobno |
| P1 źródła Coinbase | Istniejące GET Coinbase, CDP, RPC, publiczne świece | Brak pełnego odczytu wszystkich typów aktywów; Base RPC 429 |
| P2 rejestr i uzgadnianie | Prywatne snapshoty/checkpointy; rozdział giełdy i Wallet | Brak pełnego automatycznego łączenia dwóch stron transferów, bez certyfikacji pełnego P&L |
| P3 strategie i ryzyko | Offline research EIA, lokalna prospektywna symulacja, częściowe flagi ryzyka | Brak dowodu przewagi inwestycyjnej i historycznie oryginalnych vintage PIT |
| P4 autoryzacja | Istniejąca ścisła blokada write w supervisorze | Nie wdrażamy mechanizmu wykonywania operacji |
| P5 testowanie i nadzór | 501 offline / 42 smoke raportowane w PR #72 | Nie ma potwierdzonego always-on cloud runtime ani pełnej rekonsyliacji |

**Ważne:** zgłoszenie PR, pozytywny test syntetyczny i lista narzędzi nie są dowodem realizacji całego planu, live deploymentu lub uzyskania dowolnych uprawnień finansowych.
