"""One-shot, read-only market and OPTIONAL local portfolio risk briefing.

Public-only mode makes four unauthenticated source GETs (3 Coinbase OHLCV,
1 official NBP table A). A locally supplied Coinbase-like holdings snapshot
never leaves this process or appears in GitHub Actions. No brokerage SDK,
credentials, orders, scheduling, Neon writes, or automatic strategy allocation.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from statistics import pstdev

from scripts.hourly_real_paper_research import _http_exact, fetch_nbp
from scripts.coinbase_public_hourly_research import HOST, PREFIX, MAX_HTTP, SourceError

WATCH = ("BTC-USD", "ETH-USD", "ATOM-USD")
HOURS = 72
NUM = Decimal
ACCOUNT_TYPES_STAKED = frozenset({"ACCOUNT_TYPE_STAKED_FUNDS"})
MAX_ACCOUNT_FILE_BYTES = 120000


class MonitoringError(ValueError):
    pass


def _number(value, label, *, allow_zero=True):
    if isinstance(value, bool) or value is None:
        raise MonitoringError(f"{label} must be a decimal number")
    try:
        v = NUM(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MonitoringError(f"{label} is invalid") from exc
    if not v.is_finite() or v < 0 or (not allow_zero and v == 0):
        raise MonitoringError(f"{label} outside permitted range")
    return v


def _when(value):
    if not isinstance(value, str):
        raise MonitoringError("UTC timestamp string required")
    try:
        v = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MonitoringError("Invalid UTC date") from exc
    if v.tzinfo is None or v.utcoffset() != timedelta(0):
        raise MonitoringError("UTC timestamp required")
    return v.astimezone(timezone.utc)


def _fmt(v, places=2):
    return str(v.quantize(NUM(10) ** (-places)))


def _percent(num, denom):
    return _fmt(NUM(100) * num / denom) if denom else None


def _market_parse(raw, symbol, first, end):
    """Read only CLOSED 1h OHLCV candles, strict exclusive UTC endpoint."""
    if symbol not in WATCH or not isinstance(raw, bytes) or len(raw) > MAX_HTTP:
        raise MonitoringError("Public market source identity/size rejected")
    try:
        envelope = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise MonitoringError("Invalid market JSON") from exc
    items = envelope.get("candles") if isinstance(envelope, dict) else None
    if not isinstance(items, list) or len(items) > HOURS + 2:
        raise MonitoringError("Unexpected candle envelope")
    candles = {}
    for r in items:
        if not isinstance(r, dict):
            raise MonitoringError("Malformed OHLCV candle")
        try:
            t = int(r["start"])
            vals = {k: _number(r[k], k, allow_zero=k == "volume")
                    for k in ("open", "high", "low", "close", "volume")}
        except (TypeError, ValueError, KeyError) as exc:
            raise MonitoringError("Malformed OHLCV numeric fields") from exc
        if t % 3600 or t < first or t > end:
            raise MonitoringError("Unexpected hour")
        if t == end:
            continue   # Coinbase may include an extra open boundary record
        if (t in candles or vals["low"] > min(vals["open"], vals["close"])
                or vals["high"] < max(vals["open"], vals["close"])
                or vals["high"] < vals["low"]):
            raise MonitoringError("Duplicate or invalid OHLCV")
        candles[t] = vals
    times = list(range(first, end, 3600))
    if len(times) != HOURS or set(times) != set(candles):
        raise MonitoringError("Incomplete 72-hour public market history")
    closes = [candles[t]["close"] for t in times]
    pct24 = NUM(100) * (closes[-1] / closes[-25] - 1)
    returns = [float(closes[i] / closes[i-1] - 1) for i in range(1, len(closes))]
    # 24h volatility estimate, not expected future volatility.
    vol_24 = NUM(str(pstdev(returns[-24:]) * (24 ** 0.5) * 100))
    highs = [candles[t]["high"] for t in times[-24:]]
    lows = [candles[t]["low"] for t in times[-24:]]
    import hashlib
    fingerprint = hashlib.sha256(raw).hexdigest()
    return {
        "symbol": symbol,
        "last_completed_candle_utc": datetime.fromtimestamp(end - 3600, timezone.utc).isoformat(),
        "last_completed_candle_end_utc": datetime.fromtimestamp(end, timezone.utc).isoformat(),
        "last_closed_price_usd": str(closes[-1]),
        "price_change_24h_pct": _fmt(pct24),
        "range_24h_high_usd": str(max(highs)),
        "range_24h_low_usd": str(min(lows)),
        "observed_realized_volatility_24h_pct": _fmt(vol_24),
        "verified_hourly_candles": len(times),
        "raw_source_sha256": fingerprint,
        "price_type": "PUBLIC_HOURLY_CLOSE_NOT_EXECUTABLE_BID_ASK",
        "historical_first_publication_certified": False,
    }


def fetch_markets(now, opener=None):
    """Fetch three public 72h source ranges; all return values evidence-based."""
    current = _when(now) if isinstance(now, str) else now
    if current.tzinfo is None or current.utcoffset() != timedelta(0):
        raise MonitoringError("UTC current time required")
    end = int(current.timestamp()) // 3600 * 3600
    first = end - HOURS * 3600
    from urllib.parse import urlencode
    from urllib.request import urlopen
    op = opener or urlopen
    output = {}
    for symbol in WATCH:
        path = PREFIX + symbol + "/candles"
        query = urlencode({"start": str(first), "end": str(end),
                           "granularity": "ONE_HOUR", "limit": "168"})
        url = "https://" + HOST + path + "?" + query
        raw = _http_exact(url, HOST, path, query, MAX_HTTP, op)
        output[symbol] = _market_parse(raw, symbol, first, end)
    return output


def fetch_usdpln(now, fetcher=fetch_nbp):
    """NBP effectiveDate is NOT an actual intraday publication timestamp."""
    day = now.date()
    rates, proof = fetcher(day - timedelta(days=35), day)
    eligible = [(entry["assumed_eligible_utc"], entry) for entry in rates.values()
                if _when(entry["assumed_eligible_utc"]) <= now]
    if not eligible:
        raise MonitoringError("No published, conservatively eligible USDPLN rate")
    eligible.sort(key=lambda x: x[0])
    dt, entry = eligible[-1]
    age = now - _when(dt)
    if age > timedelta(days=5):
        raise MonitoringError("NBP rate too stale for market briefing")
    return {
        "usdpln_mid_reference": entry["mid"],
        "nbp_effective_date": entry["effective_date"],
        "assumed_eligible_utc": dt,
        "age_hours": _fmt(NUM(str(age.total_seconds())) / 3600, 1),
        "publication_time_is_exact": False,
        "market_fx_tradable_quote": False,
        "nbp_source_canonical_sha256": proof["canonical_sha256"],
    }


def analyze_portfolio(payload, report_at):
    """Analyze a manually supplied, private, read-only Coinbase-style snapshot.

    Never assume staking positions are tradable, nor that portfolio holdings
    are fully reconciled with account spot_positions on a stale capture.
    """
    if not isinstance(payload, dict) or payload.get("source") not in (
            "USER_SUPPLIED_READ_ONLY_COINBASE_CAPTURE", "SYNTHETIC_TEST_ONLY"):
        raise MonitoringError("Source must be explicitly labeled")
    captured = _when(payload.get("captured_at"))
    if captured > report_at + timedelta(seconds=5):
        raise MonitoringError("Future-dated account snapshot")
    age = report_at - captured
    if age > timedelta(days=30):
        raise MonitoringError("Unusable stale account snapshot")
    balances = payload.get("portfolio_balances")
    if not isinstance(balances, dict):
        raise MonitoringError("Portfolio balances missing")
    total_node = balances.get("total_balance")
    if not isinstance(total_node, dict) or total_node.get("currency") != "USD":
        raise MonitoringError("Explicit USD portfolio total required")
    reported_total = _number(total_node.get("value"), "total_balance")
    items = payload.get("spot_positions")
    if not isinstance(items, list) or len(items) > 80:
        raise MonitoringError("Positions list missing/oversized")
    per_asset = {}
    staking = NUM(0)
    cash = NUM(0)
    no_liquidity_evidence = []
    summed = NUM(0)
    for item in items:
        if not isinstance(item, dict):
            raise MonitoringError("Invalid position")
        asset = item.get("asset")
        value = item.get("total_balance_fiat")
        if not isinstance(asset, str) or not re.fullmatch(r"[A-Z0-9]{2,12}", asset):
            raise MonitoringError("Unrecognized asset identifier")
        if value is None:
            raise MonitoringError("Position has no USD valuation; refuse silent omission")
        v = _number(value, "asset valuation")
        if v == 0:
            continue
        per_asset[asset] = per_asset.get(asset, NUM(0)) + v
        summed += v
        if item.get("account_type") in ACCOUNT_TYPES_STAKED:
            staking += v
        elif item.get("is_cash") is True:
            cash += v
        elif item.get("available_to_trade_fiat") is None:
            no_liquidity_evidence.append(asset)
    # Account balances may include non-spot or fiat residuals; never silently
    # pretend missing position categories have been priced.
    discrepancy = abs(reported_total - summed)
    tolerance = max(NUM("0.05"), reported_total * NUM(".005"))
    if discrepancy > tolerance:
        raise MonitoringError("Account total and enumerated holdings do not reconcile")
    biggest = max(per_asset.items(), key=lambda kv: kv[1]) if per_asset else ("NONE", NUM(0))
    concentration = _percent(biggest[1], reported_total)
    staked_share = _percent(staking, reported_total)
    flags = []
    if concentration and NUM(concentration) >= 75:
        flags.append("HIGH_SINGLE_ASSET_CONCENTRATION")
    if staked_share and NUM(staked_share) >= 75:
        flags.append("MOST_ASSETS_CLASSIFIED_STAKED_NOT_IMMEDIATELY_LIQUID")
    if age > timedelta(hours=24):
        flags.append("ACCOUNT_CAPTURE_OLDER_THAN_24_HOURS")
    if no_liquidity_evidence:
        flags.append("UNVERIFIED_TRADEABLE_BALANCES")
    return {
        "status": "PRIVATE_READ_ONLY_SNAPSHOT_RISK_REVIEW",
        "source": payload["source"],
        "connected_account_validated_by_cli": False,
        "captured_at_utc": captured.isoformat(),
        "capture_age_hours": _fmt(NUM(str(age.total_seconds())) / 3600, 1),
        "reported_total_usd": _fmt(reported_total, 4),
        "enumerated_position_total_usd": _fmt(summed, 4),
        "asset_values_usd": {k: _fmt(v, 4) for k, v in sorted(per_asset.items())},
        "largest_asset": biggest[0],
        "largest_asset_share_pct": concentration,
        "staked_value_usd": _fmt(staking, 4),
        "staked_share_pct": staked_share,
        "cash_position_value_usd": _fmt(cash, 4),
        "liquidity_not_verified_for": sorted(set(no_liquidity_evidence)),
        "risk_flags": flags,
        "no_tradability_inferred_from_total_balance": True,
    }


def build_report(now, market, usdpln, private_snapshot=None):
    if isinstance(now, str):
        now = _when(now)
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise MonitoringError("Report clock must be UTC")
    if not isinstance(market, dict) or set(market) != set(WATCH):
        raise MonitoringError("Required market sources missing")
    for key, entry in market.items():
        if key != entry.get("symbol") or entry.get("verified_hourly_candles") != HOURS:
            raise MonitoringError("Market snapshot incomplete")
        age = now - _when(entry["last_completed_candle_end_utc"])
        if age < timedelta(0) or age > timedelta(hours=2):
            raise MonitoringError("Market OHLCV too old/new")
    if not isinstance(usdpln, dict) or not usdpln.get("usdpln_mid_reference"):
        raise MonitoringError("Verified NBP reference missing")
    portfolio = analyze_portfolio(private_snapshot, now) if private_snapshot is not None else None
    return {
        "status": "READ_ONLY_MARKET_AND_PORTFOLIO_INTELLIGENCE",
        "generated_at_utc": now.isoformat(),
        "market_prices": market,
        "nbp_usdpln": usdpln,
        "portfolio": portfolio,
        "portfolio_data": "NOT_CONNECTED_TO_CLI" if portfolio is None else "USER_SUPPLIED_PRIVATE_SNAPSHOT",
        "research_assessment": "OBSERVATIONAL_NO_BUY_SELL_SIGNALS",
        "profitability_proven": False,
        "executed_orders": 0,
        "neon_writes": 0,
        "scheduled_runs_created": 0,
        "paper_strategy_allocations_changed": False,
    }


def render_markdown(report):
    lines = [
        "# Investment Strategy Lab — monitoring odczytowy",
        f"Czas raportu (UTC): {report['generated_at_utc']}",
        "",
        "## Rynek — wyłącznie zakończone świece godzinowe Coinbase",
        "| Rynek | Ostatnie zamknięcie (USD) | Zmiana 24 h | Zmienność 24 h (obserwowana) |",
        "|---|---:|---:|---:|",
    ]
    for symbol in WATCH:
        row = report["market_prices"][symbol]
        lines.append(f"| {symbol} | {row['last_closed_price_usd']} | {row['price_change_24h_pct']}% | {row['observed_realized_volatility_24h_pct']}% |")
    nbp = report["nbp_usdpln"]
    lines.extend([
        "",
        f"USD/PLN NBP (kurs średni referencyjny): {nbp['usdpln_mid_reference']} — data NBP: {nbp['nbp_effective_date']}.",
        "Dostępność kursu NBP to konserwatywne założenie od następnego dnia UTC; nie jest to kurs wymiany możliwy do wykonania.",
    ])
    p = report["portfolio"]
    if p is None:
        lines.extend(["", "## Portfel", "**Brak prywatnego snapshotu — brak podstaw do wyceny indywidualnego portfela.**"])
    else:
        lines.extend(["", "## Portfel — prywatny snapshot odczytowy",
            f"Wartość zgłoszona: {p['reported_total_usd']} USD; snapshot: {p['captured_at_utc']}.",
            f"Największa pozycja: {p['largest_asset']} ({p['largest_asset_share_pct']}%).",
            f"Wartość oznaczona jako staking: {p['staked_value_usd']} USD ({p['staked_share_pct']}%).",
            "Nie ustalono dostępności do handlu na podstawie łącznych sald.",
            "Kontrole: " + (", ".join(p["risk_flags"]) or "brak sygnałów przekroczenia przyjętych progów") + "."])
    lines.extend(["", "## Granice interpretacji",
        "Dane rynkowe i salda służą wyłącznie monitoringowi. Brak wskazań kupna/sprzedaży i zleceń.",
        "Ostatnie zamknięcie świecy nie jest notowaniem bid/ask ani gwarantowaną ceną transakcji.",
        "Dane portfela, jeśli dostarczone, są odczytowe i mogą być nieaktualne.",
        "Brak potwierdzonej przewagi inwestycyjnej i brak operacji na rachunku."])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Public read-only market and optional local account risk report")
    parser.add_argument("--portfolio-file", type=Path, help="PRIVATE local snapshot; NEVER use in public GitHub Actions")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    if args.portfolio_file:
        if args.portfolio_file.stat().st_size > MAX_ACCOUNT_FILE_BYTES:
            raise MonitoringError("Private snapshot file oversized")
        private = json.loads(args.portfolio_file.read_text(encoding="utf-8"))
    else:
        private = None
    markets = fetch_markets(now)
    fx = fetch_usdpln(now)
    report = build_report(now, markets, fx, private)
    print(json.dumps(report, sort_keys=True, ensure_ascii=False) if args.format == "json"
          else render_markdown(report))


if __name__ == "__main__":
    main()
