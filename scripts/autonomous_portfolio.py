"""Private autonomous portfolio supervisor. No signing or financial execution tools.

CDP token discovery and finalized RPC observations remain distinct evidence layers.
No token symbol alone establishes identity, price, ownership or external funding.
"""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler

from scripts import autonomous_coinbase_history as history
from scripts import history_coverage
from scripts import history_backfill
from scripts import ntfy_notifications
from scripts.coinbase_deposit_history import _cursor
from scripts.operational_read_only import read_private, write_private, observe_wallets, TOKENS, reconcile_events
from scripts.operational_read_only import capture_rpc_metadata, rpc_metadata_snapshot
from scripts.read_only_portfolio_monitor import fetch_markets, fetch_usdpln

NETWORKS = {1: "ethereum", 8453: "base"}
NATIVE = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
MODE = "PRIVATE_AUTONOMOUS_PORTFOLIO_V1"


def quantity(value, signed=False):
    history.require(isinstance(value, str) and len(value) <= 80 and bool(re.fullmatch(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?" if signed else r"(0|[1-9][0-9]*)(\.[0-9]+)?", value)))
    return Decimal(value)


def cdp_signer(credentials):
    # The existing factory validates the private key algorithm and local permissions.
    history.make_sdk_signer(credentials)
    from coinbase import jwt_generator
    key = read_private(credentials)
    return lambda path: jwt_generator.build_rest_jwt(
        "GET api.cdp.coinbase.com" + path, key["name"], key["privateKey"])


class CdpBalances:
    """Only GET to a constructed token-balance path. No caller-selected URL/method."""
    def __init__(self, signer, opener=None):
        self.signer = signer
        self.opener = opener or build_opener(ProxyHandler({}), history.NoRedirect()).open

    def collect(self, chain, address):
        history.require(type(chain) is int and chain in NETWORKS and isinstance(address, str)
                        and re.fullmatch(r"0x[0-9a-fA-F]{40}", address))
        path = f"/platform/v2/evm/token-balances/{NETWORKS[chain]}/{address}"
        cursor, seen, identities, positions = None, set(), set(), []
        proofs = []
        for _ in range(20):
            query = {"pageSize": 100}
            if cursor is not None: query["pageToken"] = cursor
            url = "https://api.cdp.coinbase.com" + path + "?" + urlencode(query)
            try:
                token = self.signer(path)
                history.require(isinstance(token, str) and 0 < len(token) <= 8192
                                and all(32 < ord(c) < 127 for c in token))
                req = Request(url, method="GET", headers={"Authorization": "Bearer " + token,
                    "Accept": "application/json", "User-Agent": "ISL-Read-Only-Portfolio/1.0"})
                with self.opener(req, timeout=20) as response:
                    history.require(response.status == 200 and response.geturl() == url)
                    raw = response.read(2_000_001)
                history.require(isinstance(raw, bytes) and 0 < len(raw) <= 2_000_000)
                body = json.loads(raw)
                history.require(isinstance(body, dict) and isinstance(body.get("balances"), list)
                                and len(body["balances"]) <= 100)
                proofs.append(sha256(raw).hexdigest())
                for row in body["balances"]:
                    token, amount = row["token"], row["amount"]
                    history.require(token["network"] == NETWORKS[chain])
                    contract = token["contractAddress"].lower()
                    history.require(re.fullmatch(r"0x[0-9a-f]{40}", contract) and contract not in identities)
                    identities.add(contract)
                    value, digits = amount["amount"], amount["decimals"]
                    history.require(isinstance(value, str) and re.fullmatch(r"[0-9]{1,78}", value)
                                    and type(digits) is int and 0 <= digits <= 36)
                    # Provider-supplied symbols/names/URLs are deliberately discarded.
                    known = ("ETH", 18) if contract == NATIVE else TOKENS[chain].get(contract)
                    history.require(known is None or digits == known[1])
                    with localcontext() as ctx:
                        ctx.prec = 120
                        display = format(Decimal(value) / Decimal(10)**digits, "f")
                    positions.append({"chain_id": chain, "contract": contract, "quantity": display,
                        "asset": known[0] if known else "UNREVIEWED_TOKEN",
                        "identity_verified": known is not None})
                    history.require(len(positions) <= 1000)
                cursor = body.get("nextPageToken")
                if cursor is None or cursor == "": break
                history.require(isinstance(cursor, str) and len(cursor) <= 2048
                                and all(32 < ord(c) < 127 for c in cursor)
                                and cursor not in seen and body["balances"])
                seen.add(cursor)
            except Exception:
                raise history.AutonomousHistoryError("CDP_BALANCE_READ_REJECTED") from None
        else:
            raise history.AutonomousHistoryError("CDP_BALANCE_PAGE_LIMIT")
        return {"positions": positions, "response_sha256": proofs,
                "finality": "INDEXER_OBSERVATION_NOT_FINALIZED_PROOF", "pages_complete": True}


def exchange_accounts(client):
    client.check_permissions()
    cursor, seen, accounts = None, set(), []
    for _ in range(20):
        body = client.get(client.path, cursor)
        history.require(body.get("proof_token_required") is not True)
        rows, pagination = body.get("data"), body.get("pagination")
        history.require(isinstance(rows, list) and len(rows) <= 100 and isinstance(pagination, dict)
                        and "next_uri" in pagination)
        for row in rows:
            ident = history._uuid(row.get("id"))
            history.require(ident not in seen)
            seen.add(ident)
            currency = row.get("currency")
            if isinstance(currency, dict): currency = currency.get("code")
            history.require(isinstance(currency, str) and re.fullmatch(r"[A-Za-z0-9]{2,12}", currency))
            balance = row.get("balance")
            history.require(isinstance(balance, dict) and balance.get("currency") == currency)
            amount = quantity(balance.get("amount"))
            accounts.append({"id": ident, "asset": currency, "quantity": format(amount, "f")})
            history.require(len(accounts) <= 100)
        next_cursor = _cursor(pagination["next_uri"], client.path)
        if next_cursor is None: break
        history.require(rows and rows[-1].get("id") == next_cursor and next_cursor != cursor)
        cursor = next_cursor
    else:
        raise history.AutonomousHistoryError("PORTFOLIO_ACCOUNT_PAGE_LIMIT")
    history.require(accounts)
    return accounts


def source_read(fn, clock):
    try:
        result = fn()
        return {"status": "OK", "checked_at_utc": clock().isoformat(), "data": result}
    except Exception:
        # Never publish exception text, URLs, wallet addresses, JWTs or provider bodies.
        return {"status": "UNAVAILABLE", "checked_at_utc": clock().isoformat(), "data": None}


def paper_snapshot(previous, market, now):
    """Prospective fixed reference simulation; no retrospective fitting or execution."""
    assets = ("BTC", "ETH")
    prices, times = {}, []
    for asset in assets:
        row = market[asset + "-USD"]
        prices[asset] = quantity(row["last_closed_price_usd"])
        history.require(prices[asset] > 0)
        stamp = datetime.fromisoformat(row["last_completed_candle_end_utc"])
        history.require(stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0)
                        and timedelta(0) <= now - stamp <= timedelta(hours=2))
        times.append(stamp)
    history.require(times[0] == times[1])
    at = times[0].isoformat()
    if previous:
        history.require(previous["mode"] == "PROSPECTIVE_REFERENCE_SIMULATION_V1")
        history.require(at >= previous["last_candle_utc"])
        if at == previous["last_candle_utc"]:
            return previous
        units, entry, peak = previous["units"], previous["entry_observed_at_utc"], quantity(previous["peak_value_usd"])
    else:
        # Fixed fictional 10,000 USD, equal BTC/ETH buy-and-hold vs cash.
        # 20bp fee + 10bp slippage assumptions; no real holdings are allocated.
        with localcontext() as ctx:
            ctx.prec = 100
            units = {asset: format((Decimal("5000") / (prices[asset] * Decimal("1.003"))).quantize(Decimal("0.000000000000000001")), "f") for asset in assets}
        entry, peak = now.isoformat(), Decimal("10000")
    with localcontext() as ctx:
        ctx.prec = 120
        value = sum(quantity(units[asset]) * prices[asset] for asset in assets).quantize(Decimal("0.00000001"))
        peak = max(peak, value)
        return {"mode": "PROSPECTIVE_REFERENCE_SIMULATION_V1", "units": units,
            "entry_observed_at_utc": entry, "last_candle_utc": at,
            "initial_virtual_usd": "10000", "cash_baseline_usd": "10000",
            "reference_value_usd": str(value), "peak_value_usd": str(peak),
            "reference_return_pct": str((value / Decimal("10000") - 1) * 100),
            "observed_drawdown_pct": str((value / peak - 1) * 100),
            "fee_bps_assumed": 20, "slippage_bps_assumed": 10,
            "executable_prices": False, "profitability_proven": False,
            "real_holdings_used": False, "financial_operations": 0}


def reference_fx(now, reader):
    """Reuse the validated NBP adapter; refuse unavailable/stale FX, never assume 1."""
    data = reader(now)
    history.require(isinstance(data, dict))
    rate = quantity(data.get("usdpln_mid_reference"))
    history.require(rate > 0)
    stamp = datetime.fromisoformat(data["assumed_eligible_utc"])
    history.require(stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0)
                    and timedelta(0) <= now - stamp <= timedelta(days=5))
    effective = datetime.strptime(data["nbp_effective_date"], "%Y-%m-%d").date()
    history.require(effective <= stamp.date())
    return data


def pln_values(report, fx):
    """Add display-only PLN fields. Preserve USD basis and paper entry/units."""
    rate = quantity(fx["usdpln_mid_reference"]) if fx else None
    def convert(value):
        if value is None or rate is None:
            return None
        with localcontext() as ctx:
            ctx.prec = 160
            return format((quantity(value) * rate).quantize(Decimal("0.01")), "f")
    report["reference_currency"] = "PLN"
    report["known_priced_subtotal_pln"] = convert(report["known_priced_subtotal_usd"])
    for row in report["holdings"]:
        row["reference_value_pln"] = convert(row["reference_value_usd"])
    paper = report["paper_simulation"]["data"]
    if paper is not None:
        report["paper_simulation"]["data"] = {**paper,
            "reference_value_pln": convert(paper["reference_value_usd"])}
    report["reference_fx"] = fx
    return report


def cycle(config, state, clock, *, signer_factory=history.make_sdk_signer,
          client_factory=history.ReadOnlyClient, cdp_factory=cdp_signer,
          wallet_reader=observe_wallets, market_reader=fetch_markets, fx_reader=fetch_usdpln,
          backfill_runner=history_backfill.recover_one):
    with capture_rpc_metadata():
        return _cycle(config, state, clock, signer_factory=signer_factory,
                      client_factory=client_factory, cdp_factory=cdp_factory,
                      wallet_reader=wallet_reader, market_reader=market_reader,
                      fx_reader=fx_reader, backfill_runner=backfill_runner)


def _cycle(config, state, clock, *, signer_factory=history.make_sdk_signer,
           client_factory=history.ReadOnlyClient, cdp_factory=cdp_signer,
           wallet_reader=observe_wallets, market_reader=fetch_markets, fx_reader=fetch_usdpln,
           backfill_runner=history_backfill.recover_one):
    now = clock()
    history.require(now.tzinfo is not None and now.utcoffset() == timedelta(0))
    signer = signer_factory(config["credentials_file"])
    discovery = client_factory(None, config["portfolio_id"], signer)
    sources = {}
    sources["exchange"] = source_read(lambda: exchange_accounts(discovery), clock)
    account_reports = []
    if sources["exchange"]["status"] == "OK":
        for account in sources["exchange"]["data"]:
            folder = history.private_directory(state / account["id"])
            client = client_factory(account["id"], config["portfolio_id"], signer)
            result = source_read(lambda: history.run_cycle(client, folder, clock), clock)
            # The private per-account checkpoints hold records and change comparisons.
            report = result["data"]
            account_reports.append({"asset": account["asset"], "status": result["status"],
                "schema": report.get("source_schema_status") if report else "UNKNOWN"})
    sources["history"] = {"status": "OK" if account_reports and all(
        row["status"] == "OK" for row in account_reports) else "UNAVAILABLE",
        "checked_at_utc": clock().isoformat(), "data": account_reports}
    watch = read_private(config["watchlist_file"]) if config.get("watchlist_file") else None
    if watch is not None:
        from scripts.private_wallet_chain_monitor import _private_config
        entries = _private_config(watch)
        for chain, address, label, contracts in entries:
            one = {"mode": "PRIVATE_WALLET_READ_ONLY", "watch": [item for item in watch["watch"]
                if item["chain_id"] == chain and item["address"].lower() == address]}
            chain_source = source_read(lambda: wallet_reader(
                one, clock(), history_blocks=1000, allow_partial_history=True), clock)
            if (chain_source["status"] == "OK" and
                    chain_source["data"].get("history_complete_for_requested_range") is not True):
                chain_source["status"] = "PARTIAL"
                chain_source["reason"] = "REQUESTED_TOKEN_HISTORY_UNAVAILABLE"
            sources[f"chain_{label}_{chain}"] = chain_source
            sources[f"cdp_{label}_{chain}"] = source_read(lambda: CdpBalances(
                cdp_factory(config["credentials_file"])).collect(chain, address), clock)
    sources["market"] = source_read(lambda: market_reader(clock()), clock)
    sources["usdpln"] = source_read(lambda: reference_fx(clock(), fx_reader), clock)
    # Treat CEX account totals and wallet locations separately. Never add portfolio
    # summary balances to account balances; never use indexer balances twice.
    holdings = []
    for row in sources["exchange"].get("data") or []:
        holdings.append({"location": "COINBASE", "asset": row["asset"], "quantity": row["quantity"]})
    for key, source in sources.items():
        if key.startswith("chain_") and source["status"] in {"OK", "PARTIAL"}:
            for wallet in source["data"]["wallets"]:
                for position in wallet["positions"]:
                    holdings.append({"location": key, "chain_id": wallet["chain_id"], **position})
    market = sources["market"]["data"] or {}
    priced, unpriced, subtotal = [], 0, Decimal(0)
    with localcontext() as ctx:
        ctx.prec = 120
        for row in holdings:
            price = market.get(row["asset"] + "-USD", {}).get("last_closed_price_usd")
            value = quantity(row["quantity"]) * quantity(price) if price is not None else None
            if value is None: unpriced += 1
            else: subtotal += value
            priced.append({**row, "reference_value_usd": format(value, "f") if value is not None else None})
    wallet_events = []
    for key, source in sources.items():
        if key.startswith("chain_") and source["status"] in {"OK", "PARTIAL"}:
            for wallet in source["data"]["wallets"]:
                wallet_events.extend((wallet.get("history") or {}).get("events", []))
    reconciliation = reconcile_events([], wallet_events)
    reconciliation.update({"status": "BLOCKCHAIN_LINKAGE_NOT_AVAILABLE_IN_ACCOUNT_HISTORY",
        "full_autonomous_reconciliation_ready": False, "unmatched_is_external_funding": False,
        "account_history_checkpoints": "PRIVATE_PER_ACCOUNT_DIRECTORIES"})
    previous = read_private(state / "portfolio.json") if (state / "portfolio.json").exists() else None
    # Rolling 1000-block reads can miss events during a prolonged Base RPC outage.
    # Preserve the last verified covered block, record irreversible gaps, and
    # never conflate recovery of the latest read with continuous history.
    coverage = history_coverage.advance(
        (previous or {}).get("history_coverage"), entries if watch is not None else [],
        sources)
    # A single bounded, read-only backfill per cycle. Persist evidence before
    # updating the private coverage watermark; failures retain the gap.
    try:
        recovery = backfill_runner(coverage, entries if watch is not None else [],
                                   sources, state)
        history.require(recovery["financial_operations"] == 0)
        coverage = recovery["coverage"]
        recovery_summary = {"status": recovery["status"],
                            "recovered_block_count": recovery["recovered_block_count"],
                            "events_saved": recovery["events_saved"],
                            "financial_operations": 0}
    except Exception:
        # Never leak wallet addresses, RPC URLs, hashes, or upstream error text.
        recovery_summary = {"status": "UNAVAILABLE",
                            "recovered_block_count": 0, "events_saved": 0,
                            "financial_operations": 0}
    coverage_alerts = [
        "HISTORY_COVERAGE_GAP" if coverage["historical_gap_detected"] else None,
        "HISTORY_SCOPE_RESET" if any(s["scope_reset"] for s in coverage["streams"].values()) else None,
        "HISTORY_BLOCK_REGRESSION" if any(
            s["latest_status"] == "BLOCK_REGRESSION" for s in coverage["streams"].values()) else None,
    ]
    coverage_alerts = [item for item in coverage_alerts if item]
    prior_paper = (previous or {}).get("paper_last_success")
    paper = source_read(lambda: paper_snapshot(prior_paper, market, clock()), clock)
    ready = (watch is not None and paper["status"] == "OK"
             and all(s["status"] == "OK" for s in sources.values())
             and not coverage_alerts and not coverage["latest_source_incomplete"]
             and recovery_summary["status"] != "UNAVAILABLE")
    missing = [key for key, s in sources.items() if s["status"] != "OK"]
    with localcontext() as ctx:
        ctx.prec = 120
        concentration = {asset: str((sum(quantity(row["reference_value_usd"]) for row in priced
            if row["asset"] == asset and row["reference_value_usd"] is not None) / subtotal * 100).quantize(Decimal("0.01")))
            for asset in {row["asset"] for row in priced if row["reference_value_usd"] is not None}} if subtotal else {}
    checked_at = clock()
    report = {"mode": MODE, "checked_at_utc": checked_at.isoformat(),
        "rpc_diagnostics": rpc_metadata_snapshot(),
        "expires_at_utc": (checked_at + timedelta(minutes=30)).isoformat(),
        "status": "OBSERVATION_OK" if ready else "PARTIAL", "sources": sources,
        "holdings": priced, "known_priced_subtotal_usd": format(subtotal, "f"),
        "unpriced_position_count": unpriced, "complete_net_worth_certified": False,
        "known_priced_concentration_pct": concentration,
        "risk_scope": "PRICED_SUBSET_ONLY_NOT_FULL_PORTFOLIO_RISK",
        "reconciliation": reconciliation,
        "history_coverage": coverage,
        "history_backfill": recovery_summary,
        "paper_simulation": paper,
        "paper_last_success": paper["data"] if paper["status"] == "OK" else (previous or {}).get("paper_last_success"),
        "research": {"mode": "REFERENCE_SIMULATION_ONLY", "profitability_proven": False,
                     "paper_allocations_changed": False},
        "alerts": missing + coverage_alerts +
            (["HISTORY_BACKFILL_UNAVAILABLE"] if recovery_summary["status"] == "UNAVAILABLE" else []) +
            ([] if watch else ["WALLET_NOT_CONFIGURED"])
            + ([] if paper["status"] == "OK" else ["PAPER_SIMULATION_UNAVAILABLE"]),
        "financial_operations": 0}
    pln_values(report, sources["usdpln"]["data"])
    history.atomic_private(state / "portfolio.json", report)
    history.atomic_private(state / "health.json", {k: report[k] for k in (
        "status", "checked_at_utc", "expires_at_utc", "financial_operations", "alerts")})
    return report


def render(report):
    """Render the local observation using the isolated, testable HTML view."""
    from scripts.private_portfolio_dashboard import render as render_private_dashboard
    return render_private_dashboard(report)


def private_html(path, content):
    # Atomic same-directory replacement, no logs and no external assets.
    path = Path(path)
    if os.path.lexists(path):
        info = path.lstat()
        import stat
        history.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077)
    temporary = path.parent / ("pending-" + os.urandom(16).hex() + ".html")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()


def setup_wallet(reader_config, prompt=None):
    root = Path(reader_config).parent
    config = read_private(reader_config)
    def native():
        script = 'text returned of (display dialog "Wklej publiczny adres Coinbase Wallet (0x…). Będzie obserwowany na Base i Ethereum. Bez klucza i frazy odzyskiwania." default answer "" buttons {"Anuluj", "Zapisz"} default button "Zapisz" cancel button "Anuluj")'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        history.require(result.returncode == 0)
        return result.stdout.strip()
    address = (prompt or native)()
    history.require(isinstance(address, str) and re.fullmatch(r"0x[0-9a-fA-F]{40}", address))
    watch_path, config_path = root / "wallet-watch.json", root / "portfolio-config.json"
    history.require(not os.path.lexists(watch_path) and not os.path.lexists(config_path))
    state = history.private_directory(root / "portfolio-state")
    watch = {"mode": "PRIVATE_WALLET_READ_ONLY", "watch": [
        {"label": "coinbase-wallet", "chain_id": chain, "address": address.lower(),
         "verified_token_contracts": sorted(TOKENS[chain])} for chain in NETWORKS]}
    write_private(watch_path, watch)
    try:
        write_private(config_path, {"credentials_file": config["credentials_file"],
            "portfolio_id": config["portfolio_id"], "watchlist_file": str(watch_path),
            "state_directory": str(state), "interval_seconds": 900})
    except Exception:
        watch_path.unlink()
        raise
    return config_path


def run(config, *, once=False, clock=lambda: datetime.now(timezone.utc), sleep=time.sleep):
    history.require(set(config) == {"credentials_file", "portfolio_id", "watchlist_file", "state_directory", "interval_seconds"})
    history._uuid(config["portfolio_id"])
    interval = config["interval_seconds"]
    history.require(type(interval) is int and 300 <= interval <= 86400)
    state = history.private_directory(config["state_directory"])
    with history.process_lock(state):
        while True:
            try:
                report = cycle(config, state, clock)
                private_html(state / "dashboard.html", render(report))
                code = 0 if report["status"] == "OBSERVATION_OK" else 2
            except Exception:
                history.atomic_private(state / "health.json", {"status": "UNAVAILABLE",
                    "checked_at_utc": clock().isoformat(), "financial_operations": 0})
                code = 2
            print("PORTFOLIO_CYCLE_OK" if code == 0 else "PORTFOLIO_CYCLE_PARTIAL_OR_UNAVAILABLE", flush=True)
            if once: return code
            sleep(interval)


def check_health(state, now, notify=None, *, ntfy_config=None):
    """Independent periodic watchdog, consumes metadata only; notify on change."""
    state = Path(state)
    try:
        health = read_private(state / "health.json")
        history.require(health.get("financial_operations") == 0 and type(health["financial_operations"]) is int)
        checked = datetime.fromisoformat(health["checked_at_utc"])
        history.require(checked.tzinfo is not None and checked <= now + timedelta(seconds=5))
        status = health["status"]
        history.require(status in {"OBSERVATION_OK", "PARTIAL", "UNAVAILABLE"})
        if status != "UNAVAILABLE":
            expires = datetime.fromisoformat(health["expires_at_utc"])
            history.require(checked < expires <= checked + timedelta(minutes=30))
            if now >= expires: status = "STALE"
        signature = status + ":" + ",".join(sorted(health.get("alerts", [])))
    except Exception:
        status, signature = "INVALID_OR_MISSING", "INVALID_OR_MISSING"
    marker = state / "watchdog.json"
    old = read_private(marker).get("signature") if marker.exists() else None
    if old != signature and (old is not None or status != "OBSERVATION_OK"):
        if notify is None:
            message = ("Monitoring portfela wznowiony." if status == "OBSERVATION_OK" else
                       "Monitoring portfela: brak danych lub awaria. Sprawdź lokalny panel.")
            def notify(_):
                subprocess.run(["osascript", "-e", 'display notification ' + json.dumps(message, ensure_ascii=False) +
                    ' with title "Investment Strategy Lab"'], check=True, timeout=5,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ntfy_config:
            notify = ntfy_notifications.notifier(ntfy_config, "portfolio", notify)
        notify(status)
    history.atomic_private(marker, {"signature": signature, "checked_at_utc": now.isoformat()})
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private read-only portfolio supervisor")
    parser.add_argument("--config", required=True)
    parser.add_argument("--setup-wallet", action="store_true")
    parser.add_argument("--check-health", action="store_true")
    parser.add_argument("--ntfy-config", help="Private ntfy configuration; enables iOS delivery")
    parser.add_argument("--enable-live-read", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if not args.enable_live_read:
        print("PORTFOLIO_LIVE_READ_NOT_ENABLED"); return 2
    try:
        if args.check_health:
            status = check_health(read_private(args.config)["state_directory"], datetime.now(timezone.utc),
                                  ntfy_config=args.ntfy_config)
            print("PORTFOLIO_WATCHDOG_" + status)
            return 0 if status == "OBSERVATION_OK" else 2
        if args.setup_wallet:
            setup_wallet(args.config)
            print("PORTFOLIO_PRIVATE_SETUP_READY"); return 0
        return run(read_private(args.config), once=args.once)
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("PORTFOLIO_START_REJECTED"); return 2


if __name__ == "__main__":
    raise SystemExit(main())
