"""Private, dependency-free portfolio observation dashboard.

Present only fields from the existing local read-only report; never request account
data, use network access, or infer permission to trade from a source status.
All dynamic HTML text is escaped. This file is safe for offline synthetic tests.
"""
from html import escape
import re


_RPC_COUNTS = (
    "requests", "http_200", "http_429", "http_other", "network_errors",
    "rpc_capacity_errors", "rpc_other_errors", "rejected_responses", "retries",
)


def _rpc_metadata_table(metadata):
    """Render only the exact fixed transport schema introduced by PR #85.

    Older reports, missing producers, invalid counters or unexpected provider
    structures remain UNKNOWN; never turn absent telemetry into zero RPC errors.
    This is presentation only and has no producer/transport side effects.
    """
    unavailable = ("<p class='fine'>Telemetria transportu RPC niedostępna lub "
                   "niezweryfikowana dla tego cyklu. Liczba HTTP 429: nieznana.</p>")
    if not isinstance(metadata, dict) or set(metadata) != {"mode", "scope", "chains"}:
        return unavailable
    if (metadata["mode"] != "SCOPED_RPC_TRANSPORT_METADATA_V1"
            or metadata["scope"] != "ETHEREUM_BASE_RPC_ONLY"):
        return unavailable
    chains = metadata["chains"]
    if not isinstance(chains, dict) or set(chains) != {"1", "8453"}:
        return unavailable
    for counts in chains.values():
        if (not isinstance(counts, dict) or set(counts) != set(_RPC_COUNTS)
                or any(type(counts[k]) is not int or not 0 <= counts[k] <= 1000000000
                       for k in _RPC_COUNTS)):
            return unavailable
    labels = {"1": "Ethereum", "8453": "Base"}
    rows = "".join(
        "<tr><th scope='row'>" + labels[chain] + "</th>" +
        "".join("<td class='number'>" + str(chains[chain][k]) + "</td>"
                for k in _RPC_COUNTS) + "</tr>"
        for chain in ("1", "8453")
    )
    headers = (
        "Żądania", "HTTP 200", "HTTP 429", "Inne HTTP",
        "Błędy sieci", "RPC capacity", "Inne błędy RPC",
        "Odrzucone odpowiedzi", "Ponowienia",
    )
    return ("<p class='scroll-hint'>Tabela RPC jest przewijana poziomo.</p>" +
            "<div class='table-wrap'><table class='rpc-table'><thead><tr><th scope='col'>Sieć</th>" +
            "".join("<th scope='col'>" + h + "</th>" for h in headers) +
            "</tr></thead><tbody>" + rows + "</tbody></table></div>" +
            "<p class='fine'>Liczniki dotyczą tylko RPC Ethereum/Base w ostatnim "
            "zapisanym cyklu, razem z próbami ponowienia i backfill. "
            "HTTP 429 po udanym retry nadal jest liczone. Kategorie błędów mogą "
            "się nakładać. Zero w tym zestawieniu nie oznacza braku błędów "
            "w Coinbase, CDP, danych rynkowych ani w poprzednich cyklach.</p>")


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
    def source_failure(source):
        if not isinstance(source, dict):
            return "—"
        categories = source.get("history_failure_categories")
        if categories is None:
            return "—"
        if (not isinstance(categories, list) or not 1 <= len(categories) <= 8
                or any(type(code) is not str or
                       re.fullmatch(r"[A-Z0-9_]{1,80}", code) is None
                       for code in categories)):
            return "UNKNOWN"
        return ", ".join(categories)

    source_rows = "".join(
        "<tr><th scope='row'>" + safe(name) + "</th><td>" +
        safe(source.get("status", "UNKNOWN") if isinstance(source, dict) else "UNKNOWN") +
        "</td><td>" + safe(source.get("checked_at_utc") if isinstance(source, dict) else None) +
        "</td><td>" + safe(source_failure(source)) +
        "</td></tr>" for name, source in sorted(sources.items())
    )
    if not source_rows:
        source_rows = "<tr><td colspan='4'>Brak zweryfikowanych odczytów źródeł.</td></tr>"

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

    rpc_table = _rpc_metadata_table(report.get("rpc_diagnostics"))

    reconcile = report.get("reconciliation") or {}
    reconciliation_note = (
        "Powiązanie Coinbase Exchange z transakcjami na Ethereum/Base nie jest "
        "w pełni zweryfikowane. Zbieżna kwota i czas nie potwierdzają transferu. "
        "Saldo CDP nie jest doliczane ponownie do salda RPC."
        if reconcile.get("full_autonomous_reconciliation_ready") is not True else
        "Odczyt techniczny zgłasza dostępność uzgadniania; nie stanowi to zgody na transfer."
    )

    # Design direction: quiet finance workspace, explicit uncertainty and evidence.
    # System fonts, local CSS, useful anchor navigation, and no client-side script.
    styles = """
    :root {
      color-scheme: dark;
      --bg:#090e18; --surface:#111a2a; --surface-2:#172237;
      --surface-3:#1b2940; --text:#eef3fc; --secondary:#b1bdd0;
      --muted:#8d9bb0; --border:#2a3851; --accent:#9bb8ff;
      --accent-faint:rgba(155,184,255,.10); --good:#89e2bf;
      --good-faint:rgba(137,226,191,.10); --warn:#f6c98e;
      --warn-faint:rgba(246,201,142,.10); --shadow:0 22px 80px rgba(0,0,0,.16);
      font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",
        "Segoe UI",system-ui,sans-serif;
      font-synthesis:none;
    }
    * { box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body {
      margin:0; min-height:100vh; color:var(--text);
      background:radial-gradient(ellipse 880px 550px at 90% -10%,
        rgba(96,130,228,.14),transparent 70%),
        radial-gradient(ellipse 700px 520px at 0% 50%,
        rgba(71,128,155,.07),transparent 70%),var(--bg);
      line-height:1.55; -webkit-font-smoothing:antialiased;
      font-size:15px;
    }
    .shell { max-width:1240px; margin:0 auto;
      padding:0 clamp(16px,4vw,52px) 64px; }
    .skip-link { position:absolute; top:-100px; left:12px;
      background:var(--text); color:var(--bg); padding:12px 16px;
      z-index:10; border-radius:10px; }
    .skip-link:focus { top:12px; }
    a { color:inherit; text-decoration:none; }
    a:focus-visible, summary:focus-visible, .table-wrap:focus-visible {
      outline:3px solid var(--accent); outline-offset:4px;
    }
    .masthead { display:flex; align-items:center; justify-content:space-between;
      gap:24px; flex-wrap:wrap; min-height:102px;
      border-bottom:1px solid var(--border); }
    .brand { display:flex; align-items:center; gap:13px; min-width:0; }
    .brand-mark { display:grid; place-items:center; width:42px; height:42px;
      flex:none; border:1px solid rgba(155,184,255,.4); border-radius:13px;
      background:linear-gradient(145deg,#354f87,#1b2948); color:#f4f7ff;
      font-size:13px; font-weight:850; letter-spacing:-.04em; }
    .brand-title { font-weight:750; font-size:15px; letter-spacing:-.02em; }
    .brand-subtitle { color:var(--muted); font-size:11px; letter-spacing:.09em;
      font-weight:700; text-transform:uppercase; }
    .nav { display:flex; align-items:center; flex-wrap:wrap; gap:5px; }
    .nav a { display:inline-flex; align-items:center; justify-content:center;
      min-height:44px; font-size:12px; color:var(--secondary); padding:9px 12px;
      border-radius:9px; transition:background .16s ease,color .16s ease; }
    .nav a:hover { color:var(--text); background:var(--surface-2); }
    .intro { padding:42px 0 23px; }
    .eyebrow { font-size:11px; color:var(--accent); font-weight:780;
      text-transform:uppercase; letter-spacing:.17em; }
    h1,h2,h3,p { margin-top:0; }
    h1 { font-size:clamp(2rem,5vw,3.25rem); line-height:1.09;
      letter-spacing:-.055em; font-weight:760; margin:12px 0 13px; }
    h2 { font-size:clamp(1.15rem,2.5vw,1.46rem); line-height:1.2;
      letter-spacing:-.03em; margin:0; }
    .lead { color:var(--secondary); max-width:690px; margin:0;
      font-size:clamp(13px,1.6vw,15px); }
    .hero { display:grid; grid-template-columns:minmax(0,1.45fr) minmax(290px,.9fr);
      gap:16px; margin:16px 0; }
    .hero-main { position:relative; overflow:hidden;
      background:linear-gradient(135deg,#1b2d52 0%,#142139 58%,#101c31 100%);
      border:1px solid #35486b; border-radius:25px; padding:29px 32px 27px;
      box-shadow:var(--shadow); }
    .hero-main:after { content:""; position:absolute; width:280px;
      height:280px; right:-145px; top:-135px; border-radius:50%;
      border:1px solid rgba(195,212,255,.16); box-shadow:0 0 0 42px
      rgba(155,184,255,.025),0 0 0 88px rgba(155,184,255,.018);
      pointer-events:none; }
    .hero-label { color:#c4d2ed; font-size:13px; font-weight:620; }
    .hero-value { color:#fff; font-size:clamp(2rem,4.5vw,3.5rem);
      font-weight:770; line-height:1.18; letter-spacing:-.06em;
      margin:17px 0 6px; overflow-wrap:anywhere; }
    .hero-unit { font-size:.40em; letter-spacing:-.03em; font-weight:650;
      color:#b5c9ef; }
    .hero-main .hero-explain { color:#b5c3da; font-size:12px;
      max-width:450px; margin:8px 0 0; }
    .hero-side { display:flex; flex-direction:column; justify-content:space-between;
      gap:18px; border:1px solid var(--border); border-radius:25px;
      background:var(--surface); padding:27px 26px; }
    .overline { font-size:11px; text-transform:uppercase; font-weight:750;
      letter-spacing:.13em; color:var(--muted); }
    .status-line { display:flex; align-items:center; flex-wrap:wrap;
      gap:9px; margin:12px 0 12px; }
    .status-dot { display:inline-block; width:9px; height:9px;
      border-radius:50%; background:currentColor; box-shadow:0 0 0 5px
      var(--accent-faint); }
    .status-line strong { font-size:clamp(17px,2.4vw,23px);
      letter-spacing:-.025em; overflow-wrap:anywhere; }
    .good { color:var(--good); } .warn { color:var(--warn); }
    .status-line.warn .status-dot { box-shadow:0 0 0 5px var(--warn-faint); }
    .status-line.good .status-dot { box-shadow:0 0 0 5px var(--good-faint); }
    .hero-side p { margin:0; color:var(--secondary); font-size:13px; }
    .timestamp { border-top:1px solid var(--border); padding-top:15px; }
    .timestamp strong { display:block; color:var(--text); font-size:12px;
      overflow-wrap:anywhere; font-weight:620; margin:5px 0; }
    .metric-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr));
      gap:14px; margin-bottom:17px; }
    .metric { background:var(--surface); border:1px solid var(--border);
      border-radius:19px; padding:20px 22px; min-width:0; }
    .metric-label { color:var(--secondary); font-size:12px; font-weight:580; }
    .metric-value { font-size:clamp(21px,3vw,30px); font-weight:740;
      letter-spacing:-.045em; line-height:1.2; margin:10px 0 7px;
      overflow-wrap:anywhere; }
    .metric-note { color:var(--muted); font-size:11px; margin:0; }
    .decision { display:flex; align-items:flex-start; justify-content:space-between;
      flex-wrap:wrap; gap:12px; margin:19px 0 31px; padding:16px 20px;
      background:var(--warn-faint); border:1px solid rgba(246,201,142,.24);
      border-radius:15px; }
    .decision strong { color:var(--warn); font-size:13px; }
    .decision p { color:var(--secondary); font-size:12px;
      margin:5px 0 0; max-width:820px; }
    .decision-icon { border:1px solid rgba(246,201,142,.36);
      color:var(--warn); border-radius:999px; font-size:11px;
      font-weight:750; padding:5px 10px; }
    .content-grid { display:grid; grid-template-columns:minmax(0,1.45fr)
      minmax(290px,.9fr); gap:16px; }
    .panel { min-width:0; background:var(--surface); border:1px solid var(--border);
      border-radius:20px; padding:24px; margin:0 0 16px; }
    .panel-head { display:flex; flex-wrap:wrap; align-items:flex-start;
      justify-content:space-between; gap:11px; margin-bottom:19px; }
    .section-kicker { font-size:10px; font-weight:760; letter-spacing:.15em;
      color:var(--muted); text-transform:uppercase; margin:0 0 7px; }
    .panel-note { color:var(--secondary); font-size:12px; margin:7px 0 15px; }
    .wide { grid-column:1/-1; }
    .mini-label { border:1px solid var(--border); border-radius:999px;
      padding:5px 10px; color:var(--secondary); font-size:11px; }
    .scroll-hint { display:none; font-size:11px; color:var(--muted);
      margin:0 0 9px; }
    .table-wrap { max-width:100%; overflow-x:auto; border:1px solid var(--border);
      border-radius:13px; scrollbar-width:thin; }
    table { width:100%; border-collapse:collapse; min-width:580px; }
    .rpc-table { min-width:990px; }
    .rpc-table tbody th[scope='row'],
    .rpc-table thead th:first-child {
      white-space:nowrap; overflow-wrap:normal; min-width:114px;
      position:sticky; left:0; background:var(--surface); z-index:1;
    }
    .rpc-table thead th:first-child { background:var(--surface-2); z-index:2; }
    th,td { padding:13px 14px; text-align:left; vertical-align:top;
      border-bottom:1px solid var(--border); overflow-wrap:anywhere; }
    thead th { background:var(--surface-2); color:var(--secondary);
      font-size:11px; font-weight:720; white-space:nowrap; }
    tbody th { font-weight:680; } tbody tr:last-child td,
    tbody tr:last-child th { border-bottom:0; }
    tbody tr:hover { background:var(--accent-faint); }
    td { font-size:12px; color:var(--text); } .number { font-variant-numeric:tabular-nums; }
    .muted { color:var(--muted); }
    .body-copy { font-size:13px; line-height:1.7; color:var(--secondary);
      margin:0 0 13px; }
    .rule { height:1px; border:0; background:var(--border); margin:20px 0; }
    .fine { font-size:11px; color:var(--muted); line-height:1.7; }
    .detail-list { margin:0; padding:0; list-style:none; }
    .detail-list li { position:relative; padding:11px 10px 11px 21px;
      border-bottom:1px solid var(--border); overflow-wrap:anywhere; font-size:12px; }
    .detail-list li:last-child { border-bottom:0; }
    .detail-list li:before { content:""; position:absolute; width:5px;
      height:5px; left:5px; top:19px; background:var(--accent);
      border-radius:50%; }
    .paper-line { padding:16px 18px; border:1px solid var(--border);
      border-radius:12px; background:var(--surface-2);
      font-size:13px; color:var(--text); }
    details { border:1px solid var(--border); border-radius:13px;
      padding:0 16px; background:var(--surface-2); }
    summary { cursor:pointer; padding:15px 0; font-weight:650;
      font-size:13px; color:var(--text); }
    details ul { margin:0 0 16px; padding-left:21px; color:var(--secondary);
      font-size:12px; }
    details li { padding:5px 0; overflow-wrap:anywhere; }
    .bottom-note { border-top:1px solid var(--border); padding:20px 0 0;
      color:var(--muted); font-size:11px; line-height:1.8; }
    section[id] { scroll-margin-top:24px; }
    @media (max-width:900px) {
      .masthead { padding:16px 0; min-height:auto; }
      .hero,.content-grid { grid-template-columns:minmax(0,1fr); }
      .metric-grid { grid-template-columns:repeat(3,minmax(0,1fr)); }
      .wide { grid-column:auto; }
    }
    @media (max-width:620px) {
      .shell { padding:0 14px 38px; }
      .masthead { gap:12px; }
      .nav { width:100%; overflow-x:visible; flex-wrap:wrap;
        gap:2px 4px; padding-bottom:2px; }
      .nav a { flex:none; white-space:nowrap; padding:9px 12px; min-height:44px; }
      .intro { padding:29px 2px 17px; }
      .hero { gap:12px; margin-top:12px; }
      .hero-main,.hero-side { border-radius:19px; padding:21px; }
      .hero-main:after { width:140px; height:140px; right:-75px; top:-60px; }
      .metric-grid { grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
      .metric { padding:17px; }
      .metric:last-child { grid-column:1/-1; }
      .panel { padding:18px; border-radius:17px; margin-bottom:12px; }
      h1 { font-size:2.08rem; }
      .decision { margin:14px 0 25px; }
    }
    @media(max-width:740px) {
      .scroll-hint { display:block; }
    }
    @media(prefers-color-scheme:light) {
      :root { color-scheme:light; --bg:#f4f6fb; --surface:#ffffff;
        --surface-2:#f7f9fc; --surface-3:#f1f4fb; --text:#1c2840;
        --secondary:#4d5c73; --muted:#64748b; --border:#dfe5ef;
        --accent:#315bad; --accent-faint:rgba(49,91,173,.07);
        --good:#17684d; --good-faint:rgba(23,104,77,.09);
        --warn:#865618; --warn-faint:rgba(162,112,44,.08);
        --shadow:0 20px 70px rgba(25,42,76,.08); }
      body { background:radial-gradient(ellipse 950px 480px at 95% -5%,
        rgba(141,171,231,.15),transparent 70%),var(--bg); }
      .hero-main { background:linear-gradient(130deg,#244073,#1a315c);
        border-color:#3a5b8e; }
      .hero-main .hero-explain,.hero-label { color:#cfdbf1; }
      .hero-unit { color:#d1def4; }
      .brand-mark { background:linear-gradient(145deg,#3a61a0,#22395e); }
      .nav a:hover { background:var(--surface-2); }
    }
    @media(prefers-contrast:more) {
      :root { --border:#7e90ab; }
      .panel,.metric,.hero-side,.table-wrap { border-width:2px; }
    }
    @media(prefers-reduced-motion:reduce) {
      html { scroll-behavior:auto; }
      .nav a { transition:none; }
    }
    @media print {
      :root { color-scheme:light; --bg:#fff; --surface:#fff;
        --text:#111; --secondary:#444; --muted:#555; --border:#bbb; }
      body { background:#fff; color:#111; }
      .shell { padding:0; }
      .masthead { min-height:auto; }
      .nav,.skip-link { display:none; }
      .hero-main { box-shadow:none; }
      .panel,.metric,.hero-side,.hero-main { break-inside:avoid; }
    }
    """

    alert_count = str(len(alerts)) if isinstance(alerts, list) else "—"
    return (
        "<!doctype html><html lang='pl'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='refresh' content='60'>"
        "<meta http-equiv='Content-Security-Policy' "
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        "<meta name='theme-color' content='#090e18'>"
        "<title>Investment Strategy Lab — portfolio</title><style>" + styles + "</style>"
        "</head><body><a class='skip-link' href='#main'>Przejdź do treści</a>"
        "<div class='shell'><header class='masthead'>"
        "<div class='brand'><div class='brand-mark' aria-hidden='true'>ISL</div>"
        "<div><div class='brand-title'>Investment Strategy Lab</div>"
        "<div class='brand-subtitle'>Private research workspace</div></div></div>"
        "<nav class='nav' aria-label='Sekcje panelu'>"
        "<a href='#overview'>Przegląd</a><a href='#holdings'>Aktywa</a>"
        "<a href='#sources'>Źródła</a><a href='#quality'>Jakość danych</a>"
        "<a href='#research'>Symulacja</a></nav></header>"
        "<main id='main'>"
        "<section class='intro' id='overview' aria-labelledby='page-title'>"
        "<div class='eyebrow'>Obserwacja lokalna / ostatni zapis</div>"
        "<h1 id='page-title'>Portfel pod kontrolą danych.</h1>"
        "<p class='lead'>Coinbase Exchange i własne portfele Ethereum/Base. "
        "Widok pokazuje ostatni zapisany cykl i jego ograniczenia — bez "
        "certyfikacji pełnego majątku ani rekomendacji inwestycyjnych.</p>"
        "</section>"
        "<div class='hero'>"
        "<section class='hero-main' aria-labelledby='valuation-title'>"
        "<div class='hero-label' id='valuation-title'>Znana wycena częściowa</div>"
        "<div class='hero-value number'>" +
        cell(report.get("known_priced_subtotal_pln")) +
        " <span class='hero-unit'>PLN</span></div>"
        "<p class='hero-explain'>To suma wyłącznie rozpoznanych i wycenionych "
        "aktywów. Nie jest to wartość całego portfela ani pełny P&amp;L.</p>"
        "</section>"
        "<section class='hero-side' aria-label='Stan ostatniego odczytu'>"
        "<div><div class='overline'>Status ostatniego cyklu</div>"
        "<div class='status-line " + status_class + "'>"
        "<span class='status-dot' aria-hidden='true'></span>"
        "<strong>" + safe(status) + "</strong></div>"
        "<p>To status zapisany w pliku lokalnym, a nie bieżący test połączenia.</p>"
        "</div><div class='timestamp'><div class='overline'>Ostatni zapis UTC</div>"
        "<strong>" + safe(report.get("checked_at_utc")) + "</strong>"
        "<p>ważne do: " + safe(report.get("expires_at_utc")) +
        ". Po terminie ważności status nie potwierdza pracy usługi.</p>"
        "</div></section></div>"
        "<div class='metric-grid' aria-label='Kluczowe wskaźniki'>"
        "<div class='metric'><div class='metric-label'>Źródła ze statusem OK</div>"
        "<div class='metric-value number'>" + safe(ok_sources) + " / " +
        safe(len(sources)) + "</div>"
        "<p class='metric-note'>Tylko ostatni zapisany cykl</p></div>"
        "<div class='metric'><div class='metric-label'>Pozycje bez wyceny</div>"
        "<div class='metric-value number'>" +
        safe(report.get("unpriced_position_count")) + "</div>"
        "<p class='metric-note'>Brak wyceny nie oznacza wartości zero</p></div>"
        "<div class='metric'><div class='metric-label'>Alerty w raporcie</div>"
        "<div class='metric-value number'>" + safe(alert_count) + "</div>"
        "<p class='metric-note'>Znane ostrzeżenia i braki</p></div></div>"
        "<aside class='decision' aria-label='Zakres operacji'>"
        "<div><strong>HOLD_NO_CHANGE · Brak autoryzowanej decyzji inwestycyjnej.</strong>"
        "<p>Odczyty i symulacja nie wykonują kupna, sprzedaży ani transferów. "
        "Operacje finansowe w ostatnim cyklu: " +
        safe(report.get("financial_operations")) + ".</p></div>"
        "<span class='decision-icon'>RESEARCH ONLY</span></aside>"
        "<div class='content-grid'>"
        "<section id='holdings' class='panel' aria-labelledby='holdings-title'>"
        "<div class='panel-head'><div><div class='section-kicker'>01 / Aktywa</div>"
        "<h2 id='holdings-title'>Znane pozycje</h2></div>"
        "<span class='mini-label'>Wycena częściowa · PLN</span></div>"
        "<p class='panel-note'>Wycena częściowa PLN: " +
        cell(report.get("known_priced_subtotal_pln")) +
        ". Dotyczy tylko obsługiwanych i wycenionych aktywów. "
        "Brak wartości nie oznacza zera. NFT, DeFi i zobowiązania pozostają "
        "poza kompletną wyceną.</p>"
        "<p class='scroll-hint'>Tabela jest przewijana poziomo.</p>"
        "<div class='table-wrap' role='region' tabindex='0' "
        "aria-label='Tabela znanych pozycji, przewijana poziomo'>"
        "<table><thead><tr><th scope='col'>Miejsce</th>"
        "<th scope='col'>Aktywo</th><th scope='col'>Ilość</th>"
        "<th scope='col'>Wartość referencyjna PLN</th></tr></thead><tbody>" +
        holding_rows + "</tbody></table></div>"
        "<p class='fine'>" + fx_note + "</p></section>"
        "<section class='panel' aria-labelledby='integrity-title'>"
        "<div class='panel-head'><div><div class='section-kicker'>02 / Ograniczenia</div>"
        "<h2 id='integrity-title'>Jakość wyceny</h2></div></div>"
        "<p class='body-copy'>Dane służą do obserwacji. Historia EVM, "
        "uzgadnianie między giełdą a portfelem i część cen mogą być niepełne.</p>"
        "<hr class='rule'><div class='section-kicker'>Powiązanie źródeł</div>"
        "<p class='body-copy'>" + safe(reconciliation_note) + "</p>"
        "<hr class='rule'><div class='section-kicker'>Zakres historii</div>"
        "<p class='body-copy'>Pokrycie historii ERC20: dane opisują tylko "
        "monitorowany zakres i nie potwierdzają całego blockchaina.</p>"
        "</section>"
        "<section id='sources' class='panel wide' aria-labelledby='sources-title'>"
        "<div class='panel-head'><div><div class='section-kicker'>03 / Dane</div>"
        "<h2 id='sources-title'>Jakość i świeżość źródeł</h2></div>"
        "<span class='mini-label'>Ostatni cykl</span></div>"
        "<p class='panel-note'>Czas kontroli potwierdza wykonanie odczytu, "
        "nie kompletność historii źródła. Powody niepełnej historii ERC-20 "
        "są dostępne dopiero po ich zapisaniu przez diagnostykę.</p>"
        "<p class='scroll-hint'>Tabela jest przewijana poziomo.</p>"
        "<div class='table-wrap' role='region' tabindex='0' "
        "aria-label='Tabela statusów źródeł, przewijana poziomo'>"
        "<table><thead><tr><th scope='col'>Źródło</th>"
        "<th scope='col'>Status</th><th scope='col'>Czas kontroli UTC</th>"
        "<th scope='col'>Powód niepełnej historii ERC-20</th>"
        "</tr></thead><tbody>" + source_rows + "</tbody></table></div></section>"
        "<section id='quality' class='panel wide' aria-labelledby='quality-title'>"
        "<div class='panel-head'><div><div class='section-kicker'>04 / Monitoring</div>"
        "<h2 id='quality-title'>Pokrycie historii i diagnostyka RPC</h2></div>"
        "<span class='mini-label'>Ethereum + Base</span></div>"
        "<p class='body-copy'>" + safe(coverage_note) + "</p>"
        "<hr class='rule'><div class='section-kicker'>Transport RPC</div>"
        "<h3 style='font-size:15px;letter-spacing:-.02em;margin:7px 0 16px;'>"
        "Diagnostyka Ethereum/Base RPC</h3>"
        + rpc_table + "</section>"
        "<section id='research' class='panel' aria-labelledby='research-title'>"
        "<div class='panel-head'><div><div class='section-kicker'>05 / Badania</div>"
        "<h2 id='research-title'>Symulacja referencyjna</h2></div>"
        "<span class='mini-label'>PAPER ONLY</span></div>"
        "<div class='paper-line'>" + safe(paper_note) + "</div></section>"
        "<section class='panel' aria-labelledby='alert-title'>"
        "<div class='panel-head'><div><div class='section-kicker'>06 / Kontrola</div>"
        "<h2 id='alert-title'>Alerty i wyjątki</h2></div>"
        "<span class='mini-label'>" + safe(alert_count) + " alertów</span></div>"
        "<details open><summary>Lista z ostatniego cyklu</summary><ul>" +
        alert_rows + "</ul></details></section>"
        "</div></main><footer class='bottom-note'>"
        "Panel prywatny, statyczny, bez zewnętrznych skryptów i zasobów. "
        "Odświeżenie strony wczytuje ostatni zapis; nie odpytuje automatycznie giełdy. "
        "Brak potwierdzonej przewagi strategii, pełnego P&amp;L i zgody na "
        "wykonanie transakcji.</footer></div></body></html>"
    )
