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

    def test_renders_without_mutating_observation(self):
        report = self.make_report()
        import copy
        before = copy.deepcopy(report)
        self.assertEqual(portfolio.render(report), portfolio.render(report))
        self.assertEqual(report, before)


if __name__ == "__main__":
    unittest.main()
