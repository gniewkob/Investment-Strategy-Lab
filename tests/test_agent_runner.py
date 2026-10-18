import unittest
from datetime import datetime,timezone
from src.isl_v2.agent_runner import scheduled_cutoff

class RunnerTests(unittest.TestCase):
    def test_cutoff_is_stable_across_retries(self):
        a=scheduled_cutoff(datetime(2026,10,17,8,4,tzinfo=timezone.utc))
        b=scheduled_cutoff(datetime(2026,10,17,16,30,tzinfo=timezone.utc))
        self.assertEqual(a,b)
        self.assertEqual(a.isoformat(),'2026-10-17T07:00:00+00:00')
    def test_before_cutoff_uses_previous_day(self):
        a=scheduled_cutoff(datetime(2026,10,17,6,30,tzinfo=timezone.utc))
        self.assertEqual(a.isoformat(),'2026-10-16T07:00:00+00:00')

    def test_late_ingestion_checked_before_latest_revision(self):
        import inspect
        from src.isl_v2.agent_runner import load_observations
        source = inspect.getsource(load_observations)
        self.assertIn('v.recorded_at<=%s', source)
        self.assertIn('d.retrieved_at<=%s', source)
        self.assertIn('DISTINCT ON', source)

if __name__=='__main__':unittest.main()
