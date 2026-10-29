"""Offline, synthetic privacy and status tests for the private dashboard."""
import unittest

from scripts import autonomous_portfolio as portfolio


class PrivateDashboardTests(unittest.TestCase):
    def make_report(self):
        return {
            "status": "PARTIAL",
            "checked_at_utc": "2026-10-29T10:00:00+00:00",
            "expires_at_utc": "2026-10-29T10:30:00+00:00",
            "financial_operations": 0,
            "known_priced_subtotal_pln": "123.45",
            "unpriced_position_count": 1,
            "complete_net_worth_certified": False,
            "holdings": [
                {"location": "COINBASE", "asset": "BTC", "quantity": "0.001",
                 "reference_value_pln": "123.45"},
                {"location": "chain_primary_8453", "asset": "UNREVIEWED_TOKEN",
                 "quantity": "3", "reference_value_pln": None},
            ],
            "sources": {
                "exchange": {"status": "OK", "checked_at_utc": "2026-10-29T09:59:59+00:00"},
                "chain_primary_8453": {"status": "PARTIAL",
                                       "checked_at_utc": "2026-10-29T09:59:58+00:00"},
            },
            "reference_fx": {"usdpln_mid_reference": "4.1", "nbp_effective_date": "2026-10-28"},
            "history_coverage": {"gap_range_count": 1, "historical_gap_detected": True},
            "history_backfill": {"status": "NO_ELIGIBLE_GAP", "recovered_block_count": 0},
            "reconciliation": {"full_autonomous_reconciliation_ready": False},
            "paper_simulation": {"status": "UNAVAILABLE", "data": None},
            "alerts": ["chain_primary_8453", "HISTORY_COVERAGE_GAP"],
        }

    def test_status_quality_and_uncertainty_are_visible(self):
        page = portfolio.render(self.make_report())
        for label in ("HOLD_NO_CHANGE", "PARTIAL", "123.45", "1 / 2",
                      "Brak wyceny", "ważne do", "Pokrycie historii ERC20",
                      "HISTORY_COVERAGE_GAP", "Coinbase Exchange",
                      "pełnego majątku", "Brak potwierdzonej przewagi"):
            self.assertIn(label, page)
        self.assertNotIn("100% kompletności", page)
        self.assertNotIn("trade-ready", page)
        self.assertIn("default-src 'none'", page)
        self.assertNotIn("<script", page)
        self.assertNotIn("<iframe", page)

    def test_history_failure_reason_is_visible_without_untrusted_source_text(self):
        report = self.make_report()
        report["sources"]["chain_primary_1"] = {
            "status": "PARTIAL",
            "checked_at_utc": "2026-10-29T12:00:00+00:00",
            "history_failure_categories": ["UNCONFIRMED_OR_INVALID_LOG"],
        }
        page = portfolio.render(report)
        self.assertIn("Powód niepełnej historii ERC-20", page)
        self.assertIn("UNCONFIRMED_OR_INVALID_LOG", page)
        report["sources"]["chain_primary_1"]["history_failure_categories"] = [
            "<img src=invalid onerror=alert(1)>"]
        page = portfolio.render(report)
        self.assertNotIn("<img", page)
        self.assertIn("<td>UNKNOWN</td>", page)
        self.assertNotIn("&lt;img", page)

    def test_apple_inspired_dashboard_is_accessible_and_responsive_without_js(self):
        page = portfolio.render(self.make_report())
        self.assertIn("href='#main'>Przejdź do treści", page)
        self.assertIn("id='overview'", page)
        self.assertIn("id='holdings'", page)
        self.assertIn("id='sources'", page)
        self.assertIn("id='quality'", page)
        self.assertIn("id='research'", page)
        self.assertIn("aria-label='Sekcje panelu'", page)
        self.assertIn("prefers-color-scheme:light", page)
        self.assertIn("prefers-reduced-motion:reduce", page)
        self.assertIn("@media (max-width:620px)", page)
        self.assertIn("tabindex='0'", page)
        self.assertIn("system-ui", page)
        self.assertIn("ostatni zapisany cykl", page.lower())
        self.assertNotIn("<script", page)
        self.assertNotIn("<iframe", page)
        self.assertNotIn("https://", page)
        self.assertIn("default-src 'none'", page)

    def test_design_does_not_make_unknown_holding_or_status_falsely_current(self):
        report = self.make_report()
        report["known_priced_subtotal_pln"] = None
        report["paper_simulation"] = {
            "status": "UNAVAILABLE",
            "data": {"reference_value_pln": "SENSITIVE_STALE_FIGURE"},
        }
        page = portfolio.render(report)
        self.assertIn("Brak wyceny", page)
        self.assertIn("Po terminie ważności status", page)
        self.assertIn("Nie jest to wartość całego portfela", page)
        self.assertIn("Bieżąca symulacja niedostępna", page)
        self.assertNotIn("SENSITIVE_STALE_FIGURE", page)

    def test_unavailable_paper_does_not_replay_old_success(self):
        report = self.make_report()
        report["paper_simulation"] = {"status": "PARTIAL", "data": {
            "reference_value_pln": "999999.99", "reference_return_pct": "500"}}
        page = portfolio.render(report)
        self.assertIn("Bieżąca symulacja niedostępna", page)
        self.assertNotIn("999999.99", page)
        self.assertNotIn("500%", page)

    def test_external_labels_and_values_are_escaped(self):
        report = self.make_report()
        report["sources"]["<script>alert(1)</script>"] = {"status": "<img src=x>"}
        report["holdings"][0]["asset"] = "<svg onload=alert(1)>"
        report["alerts"].append("<a href='https://evil.invalid'>bad</a>")
        report["paper_simulation"] = {
            "status": "OK", "data": {"reference_value_pln": "<script>boom</script>",
                                    "reference_return_pct": "2", "observed_drawdown_pct": "-1"}}
        page = portfolio.render(report)
        self.assertNotIn("<script>", page)
        self.assertNotIn("<img", page)
        self.assertNotIn("<svg", page)
        self.assertNotIn("<a href=", page)
        self.assertIn("&lt;script&gt;", page)

    def test_missing_data_are_unknown_not_zero(self):
        report = {"status": "UNAVAILABLE", "checked_at_utc": "2026-10-29T10:00:00+00:00",
                  "expires_at_utc": "2026-10-29T10:30:00+00:00",
                  "sources": {}, "holdings": []}
        page = portfolio.render(report)
        self.assertIn("Dane niedostępne", page)
        self.assertIn("Brak dostępnych pozycji; nie oznacza to salda zero.", page)
        self.assertIn("Brak danych o alertach", page)
        self.assertIn("Operacje finansowe w ostatnim cyklu: Dane niedostępne", page)
        self.assertNotIn("Operacje finansowe w ostatnim cyklu: 0", page)

    def test_rpc_diagnostics_from_companion_pr85_is_explicit_and_scoped(self):
        report = self.make_report()
        counts = {"requests": 8, "http_200": 7, "http_429": 1,
                  "http_other": 0, "network_errors": 0,
                  "rpc_capacity_errors": 0, "rpc_other_errors": 0,
                  "rejected_responses": 0, "retries": 1}
        other = {**counts, "requests": 2, "http_200": 2, "http_429": 0,
                 "retries": 0}
        report["rpc_diagnostics"] = {
            "mode": "SCOPED_RPC_TRANSPORT_METADATA_V1",
            "scope": "ETHEREUM_BASE_RPC_ONLY",
            "chains": {"1": counts, "8453": other},
        }
        page = portfolio.render(report)
        self.assertIn("Diagnostyka Ethereum/Base RPC", page)
        self.assertIn("<th scope='row'>Ethereum</th>", page)
        self.assertIn("<th scope='row'>Base</th>", page)
        self.assertIn("<th scope='col'>HTTP 429</th>", page)
        self.assertIn("HTTP 429 po udanym retry nadal jest liczone", page)
        self.assertNotIn("Liczba HTTP 429: nieznana", page)

    def test_missing_invalid_and_extra_rpc_telemetry_never_mean_zero(self):
        import copy
        report = self.make_report()
        sample = {
            "mode": "SCOPED_RPC_TRANSPORT_METADATA_V1",
            "scope": "ETHEREUM_BASE_RPC_ONLY",
            "chains": {chain: {key: 0 for key in (
                "requests", "http_200", "http_429", "http_other", "network_errors",
                "rpc_capacity_errors", "rpc_other_errors",
                "rejected_responses", "retries",
            )} for chain in ("1", "8453")},
        }
        malformed = []
        a = copy.deepcopy(sample)
        a["chains"]["1"]["http_429"] = True
        malformed.append(a)
        a = copy.deepcopy(sample)
        a["chains"]["1"]["http_429"] = -1
        malformed.append(a)
        a = copy.deepcopy(sample)
        a["chains"]["1"]["PRIVATE_URL"] = "https://secret.invalid"
        malformed.append(a)
        a = copy.deepcopy(sample)
        a["chains"]["137"] = a["chains"]["1"]
        malformed.append(a)
        a = copy.deepcopy(sample)
        a["mode"] = "<script>PRIVATE</script>"
        malformed.append(a)
        for metadata in [None, {}, "error"] + malformed:
            with self.subTest(metadata=type(metadata).__name__):
                report["rpc_diagnostics"] = metadata
                page = portfolio.render(report)
                self.assertIn("Liczba HTTP 429: nieznana", page)
                self.assertNotIn("https://secret.invalid", page)
                self.assertNotIn("<script>PRIVATE</script>", page)

    def test_valid_zero_rpc_counter_requires_explicit_producer(self):
        report = self.make_report()
        report["rpc_diagnostics"] = {
            "mode": "SCOPED_RPC_TRANSPORT_METADATA_V1",
            "scope": "ETHEREUM_BASE_RPC_ONLY",
            "chains": {chain: {key: 0 for key in (
                "requests", "http_200", "http_429", "http_other", "network_errors",
                "rpc_capacity_errors", "rpc_other_errors", "rejected_responses",
                "retries")} for chain in ("1", "8453")},
        }
        page = portfolio.render(report)
        self.assertIn("HTTP 429 po udanym retry", page)
        self.assertNotIn("Liczba HTTP 429: nieznana", page)
        self.assertIn("Zero w tym zestawieniu nie oznacza braku błędów", page)

    def test_renders_without_mutating_observation(self):
        report = self.make_report()
        import copy
        before = copy.deepcopy(report)
        self.assertEqual(portfolio.render(report), portfolio.render(report))
        self.assertEqual(report, before)


if __name__ == "__main__":
    unittest.main()
