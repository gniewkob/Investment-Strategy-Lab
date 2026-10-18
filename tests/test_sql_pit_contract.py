"""Guard the reviewed SQL and Python point-in-time contract in offline CI.

These static regression checks supplement (not replace) PostgreSQL integration tests.
"""
import unittest
from pathlib import Path

from src.isl_v2.agent_runner import load_observations

ROOT = Path(__file__).resolve().parents[1]


class PointInTimeContractTests(unittest.TestCase):
    def test_sql_rejects_late_received_and_ingested_data(self):
        sql = (ROOT / "db/migrations/007_data_provenance.sql").read_text()
        function = sql.split("CREATE OR REPLACE FUNCTION investment_lab.prices_asof", 1)[1]
        # Published timestamp by itself is not when the agent knew about the price.
        self.assertGreaterEqual(function.count("v.recorded_at"), 3)
        self.assertGreaterEqual(function.count("s.retrieved_at"), 3)
        self.assertIn("<= cutoff", function)
        self.assertIn("SECURITY INVOKER", function)
        self.assertIn("DISTINCT ON", function)

    def test_online_runner_uses_same_ingest_gate(self):
        import inspect
        query = inspect.getsource(load_observations)
        self.assertGreaterEqual(query.count("v.recorded_at"), 4)
        self.assertGreaterEqual(query.count("d.retrieved_at"), 4)
        self.assertIn("v.recorded_at<=%s", query)
        self.assertIn("d.retrieved_at<=%s", query)
        self.assertIn("DISTINCT ON", query)


if __name__ == "__main__":
    unittest.main()
