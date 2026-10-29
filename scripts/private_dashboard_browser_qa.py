"""Automated browser QA for the private portfolio dashboard — synthetic data only.

This script never loads production state, reads credentials, or accesses accounts.
Playwright is an isolated CI-only dependency, not an app runtime requirement.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from scripts.private_portfolio_dashboard import render


def fixture():
    time = "DEMO 2026-10-29 18:30 UTC"
    sources = {
        name: {"status": "OK", "checked_at_utc": time}
        for name in (
            "exchange", "history", "cdp_primary_1", "cdp_primary_8453",
            "chain_primary_8453", "market", "usdpln",
        )
    }
    sources["chain_primary_1"] = {
        "status": "PARTIAL", "checked_at_utc": time,
        "history_failure_categories": ["UNCONFIRMED_OR_INVALID_LOG"],
    }
    keys = (
        "requests", "http_200", "http_429", "http_other", "network_errors",
        "rpc_capacity_errors", "rpc_other_errors", "rejected_responses",
        "retries",
    )
    counts = dict.fromkeys(keys, 0)
    counts["requests"] = 7
    counts["http_200"] = 7
    return {
        "status": "PARTIAL", "checked_at_utc": time, "expires_at_utc": time,
        "financial_operations": 0, "complete_net_worth_certified": False,
        "known_priced_subtotal_pln": "1234.56", "unpriced_position_count": 1,
        "holdings": [
            {"location": "EXCHANGE_DEMO", "asset": "BTC", "quantity": "0.001",
             "reference_value_pln": "400.00"},
            {"location": "WALLET_BASE_DEMO", "asset": "ETH", "quantity": "0.1",
             "reference_value_pln": "834.56"},
            {"location": "WALLET_ETHEREUM_DEMO", "asset": "TOKEN_DEMO",
             "quantity": "10", "reference_value_pln": None},
        ],
        "sources": sources,
        "reference_fx": {"usdpln_mid_reference": "4.00",
                         "nbp_effective_date": "DEMO"},
        "history_coverage": {"gap_range_count": 1,
                             "historical_gap_detected": True},
        "history_backfill": {"status": "NO_ELIGIBLE_GAP",
                             "recovered_block_count": 0},
        "reconciliation": {"full_autonomous_reconciliation_ready": False},
        "paper_simulation": {
            "status": "OK",
            "data": {"reference_value_pln": "40120.55",
                     "reference_return_pct": "0.12",
                     "observed_drawdown_pct": "-0.31"},
        },
        "rpc_diagnostics": {
            "mode": "SCOPED_RPC_TRANSPORT_METADATA_V1",
            "scope": "ETHEREUM_BASE_RPC_ONLY",
            "chains": {"1": dict(counts), "8453": dict(counts)},
        },
        "alerts": ["DEMO_ERC20_HISTORY_PARTIAL", "DEMO_COVERAGE_GAP"],
    }


def run(output):
    # Import only inside the browser QA entry point so the normal app remains
    # dependency-free and the Python full regression does not require Playwright.
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    page_path = output / "synthetic-private-dashboard.html"
    html = render(fixture()).replace(
        "<main id='main'>",
        "<div role='note' style='padding:12px;font-weight:750'>"
        "PODGLĄD AUTOMATYCZNY — DANE SYNTETYCZNE"
        "</div><main id='main'>",
        1,
    )
    page_path.write_text(html, encoding="utf-8")
    page_path.chmod(0o600)

    cases = [
        (375, 812, "dark", "no-preference"),
        (768, 1024, "dark", "no-preference"),
        (1280, 800, "dark", "no-preference"),
        (1440, 900, "dark", "no-preference"),
        (1280, 800, "light", "no-preference"),
        (375, 812, "light", "reduce"),
    ]
    results = []
    failures = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for width, height, scheme, motion in cases:
                name = f"dashboard-{width}x{height}-{scheme}-{motion}.png"
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1,
                    color_scheme=scheme,
                    reduced_motion=motion,
                )
                page = context.new_page()
                errors = []
                external = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda req: external.append(req.url)
                        if req.url.startswith(("http://", "https://")) else None)
                page.goto(page_path.resolve().as_uri(), wait_until="load")
                page.screenshot(path=str(output / name), full_page=True)
                metrics = page.evaluate("""() => {
                    const doc = document.documentElement;
                    const navLinks = [...document.querySelectorAll('.nav a')];
                    const targetChecks = navLinks.map(a => {
                        const r = a.getBoundingClientRect();
                        return {
                            href: a.getAttribute('href'),
                            targetFound: !!document.getElementById(
                                (a.getAttribute('href') || '').slice(1)),
                            width: Math.round(r.width * 10) / 10,
                            height: Math.round(r.height * 10) / 10
                        };
                    });
                    const tableContainers = [...document.querySelectorAll('.table-wrap')];
                    const navBounds = document.querySelector('.nav').getBoundingClientRect();
                    const navFullyVisible = navLinks.every(el => {
                        const r = el.getBoundingClientRect();
                        return r.left >= navBounds.left - 1 &&
                            r.right <= navBounds.right + 1 &&
                            r.top >= navBounds.top - 1 &&
                            r.bottom <= navBounds.bottom + 1;
                    });
                    const rpcLabels = [...document.querySelectorAll(
                        '.rpc-table tbody th[scope="row"]')].map(el => ({
                            name: el.textContent.trim(),
                            width: el.getBoundingClientRect().width,
                            height: el.getBoundingClientRect().height,
                            whiteSpace: getComputedStyle(el).whiteSpace,
                        }));
                    return {
                        documentWidth: doc.scrollWidth,
                        viewportWidth: window.innerWidth,
                        nav: targetChecks,
                        navFullyVisible,
                        rpcLabels,
                        tableOverflowCount: tableContainers.filter(
                            el => el.scrollWidth > el.clientWidth + 1).length,
                        scrollHintVisible: [...document.querySelectorAll('.scroll-hint')]
                            .some(el => getComputedStyle(el).display !== 'none'),
                        reducedScrollBehavior: getComputedStyle(doc).scrollBehavior,
                        heroVisible: !!document.querySelector('.hero-value'),
                        sourceRows: document.querySelectorAll('#sources tbody tr').length,
                        financialOperations: document.querySelector(
                            '.decision p')?.textContent || '',
                    };
                }""")
                checks = {
                    "no_page_overflow": metrics["documentWidth"] <= width + 1,
                    "nav_targets": bool(metrics["nav"]) and all(
                        x["targetFound"] for x in metrics["nav"]),
                    "nav_touch_height_44": all(
                        x["height"] >= 43.5 for x in metrics["nav"]),
                    "all_nav_links_visible": metrics["navFullyVisible"],
                    "rpc_network_names_unwrapped": (
                        [x["name"] for x in metrics["rpcLabels"]] == ["Ethereum", "Base"]
                        and all(x["height"] < 70 and x["whiteSpace"] == "nowrap"
                                for x in metrics["rpcLabels"])),
                    "hero_visible": metrics["heroVisible"],
                    "source_rows": metrics["sourceRows"] == 8,
                    "financial_operations_zero": "0." in metrics["financialOperations"],
                    "no_script_errors": not errors,
                    "no_external_requests": not external,
                    "mobile_table_scroll_hint": (
                        metrics["scrollHintVisible"] if width <= 740
                        else not metrics["scrollHintVisible"]),
                    "reduced_motion": (
                        metrics["reducedScrollBehavior"] == "auto"
                        if motion == "reduce" else True),
                }
                result = {
                    "viewport": f"{width}x{height}",
                    "colorScheme": scheme, "motion": motion,
                    "screenshot": name,
                    "checks": checks,
                    "metrics": metrics,
                    "pageErrors": errors,
                    "externalRequestCount": len(external),
                }
                results.append(result)
                failures.extend(f"{name}: {key}" for key, ok in checks.items()
                                if not ok)
                print(f"{name}: " + ("PASS" if all(checks.values()) else "FAIL"))
                context.close()
        finally:
            browser.close()

    outcome = {
        "mode": "SYNTHETIC_BROWSER_QA_ONLY",
        "privacy": "NO_WALLET_OR_EXCHANGE_DATA",
        "cases": results,
        "failureCount": len(failures),
        "failedChecks": failures,
    }
    (output / "browser-qa.json").write_text(
        json.dumps(outcome, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("BROWSER_QA_STATUS=" + ("PASS" if not failures else "FAIL"))
    print("BROWSER_QA_CASES=" + str(len(results)))
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    return run(args.output_dir)


if __name__ == "__main__":
    sys.exit(main())
