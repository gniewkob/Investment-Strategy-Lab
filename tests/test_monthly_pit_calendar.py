import unittest

from scripts.monthly_pit_calendar import assess_calendar

HASH = "a" * 64


def observation(observed="2026-10-30", published="2026-10-30", **overrides):
    row = {
        "observed_for": observed,
        "publication_date": published,
        "retrieved_at": "2026-11-04T12:00:00Z",
        "value": "100.50",
        "source_url": "https://example.org/original.csv",
        "source_sha256": HASH,
        "currency": "PLN",
        "basis": "total_return",
        "license_status": "unverified",
        "historical_vintage_verified": False,
    }
    row.update(overrides)
    return row


def manifest(rows=None):
    return {
        "sessions": ["2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04"],
        "decision_dates": ["2026-10-30", "2026-11-02", "2026-11-03"],
        "series": {"equity": rows if rows is not None else [observation()]},
    }


class CalendarTests(unittest.TestCase):
    def test_next_session_not_same_publication_session(self):
        result = assess_calendar(manifest())
        before, next_day = result["coverage_by_decision"][:2]
        self.assertIn("equity", before["missing_series"])
        self.assertEqual(next_day["available_series"]["equity"]["first_usable_session"],
                         "2026-11-02")
        self.assertFalse(next_day["available_series"]["equity"]["historical_vintage_verified"])
        self.assertEqual(result["backtest"], "NOT_RUN")
        self.assertEqual(result["paper_events_created"], 0)

    def test_newly_retrieved_history_is_not_certified(self):
        row = observation(license_status="verified_permitted",
                          historical_vintage_verified=True)
        result = assess_calendar(manifest([row]))
        self.assertFalse(result["coverage_by_decision"][1]["historical_pit_certified"])
        self.assertEqual(set(result["models"].values()), {"INSUFFICIENT_DATA"})

    def test_later_publication_does_not_leak_into_decision(self):
        result = assess_calendar(manifest([observation(published="2026-11-03")]))
        self.assertIn("equity", result["coverage_by_decision"][2]["missing_series"])

    def test_duplicates_and_unknown_timestamp_are_rejected(self):
        rows = [observation(), observation(),
                observation(retrieved_at="2026-11-04T12:00:00")]
        result = assess_calendar(manifest(rows))
        self.assertEqual(result["series"]["equity"]["accepted_rows"], 1)
        self.assertEqual(len(result["series"]["equity"]["issues"]), 2)

    def test_invalid_publication_and_price_rejected(self):
        rows = [observation(published="2026-10-29"),
                observation(value="-1"),
                observation(source_sha256="incomplete")]
        result = assess_calendar(manifest(rows))
        self.assertEqual(result["series"]["equity"]["accepted_rows"], 0)

    def test_zero_cost_allowed_but_not_zero_asset_value(self):
        m = manifest([observation(value="0")])
        m["series"]["costs"] = [observation(value="0", basis="fee")]
        result = assess_calendar(m)
        self.assertEqual(result["series"]["equity"]["accepted_rows"], 0)
        self.assertEqual(result["series"]["costs"]["accepted_rows"], 1)

    def test_invalid_session_or_decision_calendar_fails(self):
        m = manifest()
        m["sessions"].append("2026-11-02")
        with self.assertRaises(ValueError):
            assess_calendar(m)
        m = manifest()
        m["decision_dates"] = ["2026-11-01"]
        with self.assertRaises(ValueError):
            assess_calendar(m)

    def test_all_models_share_exact_same_schedule(self):
        m = manifest()
        m["series"] = {name: [observation()] for name in
                       ("equity", "bonds", "gold", "usdpln", "eurpln", "inflation", "costs")}
        result = assess_calendar(m)
        self.assertTrue(result["coverage_by_decision"][1]["all_series_present"])
        self.assertEqual(len(result["coverage_by_decision"][1]["available_series"]), 7)
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")


if __name__ == "__main__":
    unittest.main()
