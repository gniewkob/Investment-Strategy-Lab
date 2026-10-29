"""Private, dependency-free portfolio observation dashboard.

Present only fields from the existing local read-only report; never request account
data, use network access, or infer permission to trade from a source status.
All dynamic HTML text is escaped. This file is safe for offline synthetic tests.
"""
from html import escape


def render(report):
    """Render the existing private portfolio report as static, local-only HTML."""
    def safe(value):
        return escape("Dane niedostępne" if value is None else str(value), quote=True)

    def cell(value):
        return safe(value) if value is not None else "<span class='muted'>Brak wyceny</span>"

    def plain(value):
        return "Dane niedostępne" if value is None else str(value)

    status = report.get("status") or "UNKNOWN"
    status_class = "good" if status == "OBSERVATION_OK" else "warn"
    sources = report.get("sources") or {}
    ok_sources = sum(1 for source in sources.values()
                     if isinstance(source, dict) and source.get("status") == "OK")
    source_rows = "".join(
        "<tr><th scope='row'>" + safe(name) + "</th><td>" +
        safe(source.get("status", "UNKNOWN") if isinstance(source, dict) else "UNKNOWN") +
        "</td><td>" + safe(source.get("checked_at_utc") if isinstance(source, dict) else None) +
        "</td></tr>" for name, source in sorted(sources.items())
    )
    if not source_rows:
        source_rows = "<tr><td colspan='3'>Brak zweryfikowanych odczytów źródeł.</td></tr>"

    holding_rows = "".join(
        "<tr><td>" + safe(row.get("location")) + "</td><td>" +
        safe(row.get("asset")) + "</td><td class='number'>" +
        safe(row.get("quantity")) + "</td><td class='number'>" +
        cell(row.get("reference_value_pln")) + "</td></tr>"
        for row in report.get("holdings", [])
    )
    if not holding_rows:
        holding_rows = "<tr><td colspan='4'>Brak dostępnych pozycji; nie oznacza to salda zero.</td></tr>"

    fx = report.get("reference_fx") or {}
    fx_note = (
        "Średni kurs NBP USD/PLN " + safe(fx.get("usdpln_mid_reference")) +
        " · data tabeli: " + safe(fx.get("nbp_effective_date")) +
        ". To kurs referencyjny, nie oferta wymiany."
    ) if fx else "Kurs NBP niedostępny — wycena PLN nie jest ustalona."

    coverage = report.get("history_coverage") or {}
    gaps = coverage.get("gap_range_count")
    if gaps is None:
        coverage_status = "Brak potwierdzenia ciągłości"
    elif coverage.get("historical_gap_detected"):
        coverage_status = "Wykryto luki w monitorowanym zakresie"
    else:
        coverage_status = "Bez wykrytej luki od pierwszego kompletnego odczytu"
    backfill = report.get("history_backfill") or {}
    coverage_note = (
        "Pokrycie historii ERC20: " + coverage_status +
        " · liczba przedziałów braków: " + plain(gaps) +
        " · backfill: " + plain(backfill.get("status")) +
        " · odzyskane bloki w cyklu: " +
        plain(backfill.get("recovered_block_count")) +
        ". Nie oznacza to kompletnej historii blockchain."
    )

    alerts = report.get("alerts")
    if alerts is None:
        alert_rows = "<li>Brak danych o alertach.</li>"
    elif alerts:
        alert_rows = "".join("<li>" + safe(item) + "</li>" for item in alerts)
    else:
        alert_rows = "<li>W ostatnim zapisanym cyklu nie zarejestrowano alertów.</li>"

    paper = report.get("paper_simulation") or {}
    # Never present the previous successful simulation as a current market value.
    paper_current = paper.get("status") == "OK" and isinstance(paper.get("data"), dict)
    paper_data = paper.get("data") if paper_current else None
    if paper_data:
        paper_note = (
            "Wartość referencyjna: " + plain(paper_data.get("reference_value_pln")) +
            " PLN · stopa zwrotu w bazie USD: " +
            plain(paper_data.get("reference_return_pct")) +
            "% · zaobserwowane obsunięcie od szczytu: " +
            plain(paper_data.get("observed_drawdown_pct")) + "%."
        )
    else:
        paper_note = "Bieżąca symulacja niedostępna. Poprzedni zapis nie jest aktualnym wynikiem."
    paper_note += (
        " Fikcyjny benchmark 10 000 USD: 50% BTC / 50% ETH, "
        "koszt wejścia 20 pb + poślizg 10 pb. "
        "Wynik w PLN jest jedynie przeliczeniem bieżącej wartości; "
        "brak potwierdzonej przewagi strategii lub ceny wykonania."
    )

    reconcile = report.get("reconciliation") or {}
    reconciliation_note = (
        "Powiązanie Coinbase Exchange z transakcjami na Ethereum/Base nie jest "
        "w pełni zweryfikowane. Zbieżna kwota i czas nie potwierdzają transferu. "
        "Saldo CDP nie jest doliczane ponownie do salda RPC."
        if reconcile.get("full_autonomous_reconciliation_ready") is not True else
        "Odczyt techniczny zgłasza dostępność uzgadniania; nie stanowi to zgody na transfer."
    )

    styles = """
    :root{color-scheme:dark;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
    *{box-sizing:border-box}body{background:#0b1220;color:#e7edf7;max-width:1180px;
    margin:0 auto;padding:28px 22px 70px;line-height:1.55}
    h1{font-size:clamp(1.8rem,4vw,2.7rem);margin:8px 0}
    h2{font-size:1.25rem;margin:0 0 12px}
    p{margin:8px 0}.lead{color:#b9c7d9;max-width:850px}
    .eyebrow{color:#93b8e7;letter-spacing:.12em;text-transform:uppercase;font-size:.75rem;font-weight:700}
    .notice{border-left:4px solid #f5c36b;background:#242336;padding:12px 16px;border-radius:6px;margin:22px 0}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:22px 0}
    .metric,.panel{background:#142036;border:1px solid #2b3d58;border-radius:14px;padding:18px}
    .metric .name{font-size:.84rem;color:#aebdd0}.metric .value{font-size:1.45rem;
    font-weight:750;overflow-wrap:anywhere;margin-top:8px}
    .good{color:#7ce0b2}.warn{color:#ffd18b}.muted{color:#aab7c7}
    .panel{margin:18px 0}.panel p{color:#d0d9e7}
    .table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:580px}
    th,td{text-align:left;padding:12px;border-bottom:1px solid #30425b;vertical-align:top}
    th{font-weight:650;color:#d7e5f6}td{overflow-wrap:anywhere}
    .number{font-variant-numeric:tabular-nums}
    details summary{cursor:pointer;font-weight:650}
    ul{margin:12px 0 0;padding-left:21px}.fine{font-size:.85rem;color:#aabbd1}
    footer{margin-top:24px;border-top:1px solid #30425b;padding-top:18px;color:#aabbd1}
    @media(max-width:600px){body{padding:18px 12px 50px}.metric,.panel{padding:14px}}
    """

    return (
        "<!doctype html><html lang='pl'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='refresh' content='60'>"
        "<meta http-equiv='Content-Security-Policy' "
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        "<title>Investment Strategy Lab — portfolio</title><style>" + styles + "</style></head><body>"
        "<header><div class='eyebrow'>Private observation · research only</div>"
        "<h1>Investment Strategy Lab</h1>"
        "<p class='lead'>Coinbase Exchange i własne portfele Ethereum/Base. "
        "Dane odnoszą się do ostatniego zapisanego cyklu, nie są certyfikacją "
        "pełnego majątku ani rekomendacją inwestycyjną.</p></header>"
        "<div class='notice'><strong>HOLD_NO_CHANGE · Brak autoryzowanej decyzji inwestycyjnej.</strong>"
        "<p>Odczyty i symulacja nie wykonują kupna, sprzedaży ani transferów. "
        "Operacje finansowe w ostatnim cyklu: " + safe(report.get("financial_operations")) + ".</p></div>"
        "<div class='grid' aria-label='Kluczowe wskaźniki'>"
        "<div class='metric'><div class='name'>Status ostatniego cyklu</div><div class='value " +
        status_class + "'>" + safe(status) + "</div></div>"
        "<div class='metric'><div class='name'>Wycena częściowa PLN</div><div class='value number'>" +
        cell(report.get("known_priced_subtotal_pln")) + "</div></div>"
        "<div class='metric'><div class='name'>Źródła ze statusem OK</div><div class='value number'>" +
        safe(ok_sources) + " / " + safe(len(sources)) + "</div></div>"
        "<div class='metric'><div class='name'>Pozycje bez wyceny</div><div class='value number'>" +
        safe(report.get("unpriced_position_count")) + "</div></div></div>"
        "<p class='fine'>Aktualizacja: " + safe(report.get("checked_at_utc")) +
        " · ważne do: " + safe(report.get("expires_at_utc")) +
        ". Po terminie ważności ostatni status nie oznacza, że usługa nadal działa.</p>"
        "<section class='panel'><h2>Znane pozycje</h2>"
        "<p>Wycena częściowa PLN: " + cell(report.get("known_priced_subtotal_pln")) +
        ". Dotyczy tylko obsługiwanych i wycenionych aktywów. "
        "Brak wartości nie oznacza zera. NFT, DeFi i zobowiązania pozostają poza kompletną wyceną.</p>"
        "<p class='fine'>" + fx_note + "</p>"
        "<div class='table-wrap'><table><thead><tr><th>Miejsce</th><th>Aktywo</th>"
        "<th>Ilość</th><th>Wartość referencyjna PLN</th></tr></thead><tbody>" +
        holding_rows + "</tbody></table></div></section>"
        "<section class='panel'><h2>Jakość i świeżość źródeł</h2>"
        "<p class='fine'>Czas kontroli potwierdza wykonanie odczytu, nie kompletność historii źródła.</p>"
        "<div class='table-wrap'><table><thead><tr><th>Źródło</th><th>Status</th>"
        "<th>Czas kontroli UTC</th></tr></thead><tbody>" + source_rows +
        "</tbody></table></div></section>"
        "<section class='panel'><h2>Pokrycie historii i uzgadnianie</h2><p>" +
        safe(coverage_note) + "</p><p>" + safe(reconciliation_note) + "</p></section>"
        "<section class='panel'><h2>Symulacja referencyjna</h2><p>" +
        safe(paper_note) + "</p></section>"
        "<section class='panel'><details><summary>Alerty i wyjątki</summary><ul>" +
        alert_rows + "</ul></details></section>"
        "<footer>Panel prywatny, statyczny, bez zewnętrznych skryptów i zasobów. "
        "Odświeżenie strony wczytuje ostatni zapis; nie odpytuje automatycznie giełdy. "
        "Brak potwierdzonej przewagi strategii, pełnego P&amp;L i zgody na wykonanie transakcji.</footer>"
        "</body></html>"
    )
