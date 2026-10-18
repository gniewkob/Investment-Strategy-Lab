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

    def test_staging_dsn_requires_exact_identity_and_verified_tls(self):
        from src.isl_v2.agent_runner import validate_staging_dsn, STAGING_HOST
        valid=(f"postgresql://isl_agent_staging_limited:fixture-not-a-secret@{STAGING_HOST}/"
               "investment_lab?sslmode=verify-full")
        validate_staging_dsn(valid)
        invalid=[
            valid.replace("isl_agent_staging_limited", "investment_lab_owner"),
            valid.replace("/investment_lab?", "/postgres?"),
            valid.replace(STAGING_HOST, "ep-production.c-8.eu-central-1.aws.neon.tech"),
            valid.replace(STAGING_HOST, STAGING_HOST.replace(".c-8.", "-pooler.c-8.")),
            valid.replace("sslmode=verify-full", "sslmode=require"),
            valid.replace(":fixture-not-a-secret@", "@"),
            valid + "&hostaddr=127.0.0.1",
            valid + "&service=fake",
        ]
        for dsn in invalid:
            with self.subTest(dsn_type=invalid.index(dsn)):
                with self.assertRaises(ValueError):
                    validate_staging_dsn(dsn)

    def test_runner_rejects_wrong_target_before_opening_connection(self):
        from unittest.mock import patch
        from pathlib import Path
        from src.isl_v2.agent_runner import execute, STAGING_HOST
        now=datetime(2026,10,18,10,0,tzinfo=timezone.utc)
        bad=(f"postgresql://investment_lab_owner:synthetic@{STAGING_HOST}/"
             "investment_lab?sslmode=verify-full")
        with patch("psycopg.connect") as connect:
            with self.assertRaises(ValueError):
                execute(bad,Path("/tmp/agent-never-written"),now)
            connect.assert_not_called()

    def test_runner_connects_using_canonical_ca_bundle_only(self):
        from unittest.mock import patch
        from pathlib import Path
        from src.isl_v2.agent_runner import execute, STAGING_HOST
        now=datetime(2026,10,18,10,0,tzinfo=timezone.utc)
        good=(f"postgresql://isl_agent_staging_limited:synthetic@{STAGING_HOST}/"
              "investment_lab?sslmode=verify-full")
        with patch("psycopg.connect", side_effect=RuntimeError("offline")) as connect:
            with self.assertRaises(RuntimeError):
                execute(good,Path("/tmp/agent-never-written"),now)
            self.assertEqual(connect.call_args.kwargs["sslmode"],"verify-full")
            self.assertEqual(connect.call_args.kwargs["sslrootcert"],
                             "/etc/ssl/certs/ca-certificates.crt")
            self.assertFalse(connect.call_args.kwargs["autocommit"])

    def test_late_ingestion_checked_before_latest_revision(self):
        import inspect
        from src.isl_v2.agent_runner import load_observations
        source = inspect.getsource(load_observations)
        self.assertIn('v.recorded_at<=%s', source)
        self.assertIn('d.retrieved_at<=%s', source)
        self.assertIn('DISTINCT ON', source)

if __name__=='__main__':unittest.main()
