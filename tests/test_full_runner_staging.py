"""Offline guard tests for the actual full educational research runner."""
from datetime import datetime, timezone
from io import StringIO
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import sys
import unittest

from src.isl_v2 import agent_runner
from src.isl_v2.autonomous_agent import run_cycle


class FullRunnerStagingTests(unittest.TestCase):
    def test_real_agent_with_one_observation_produces_only_hold_cash(self):
        obs={
            "instrument_code":"BRENT_EIA_USD_BBL",
            "source_code":"eia_brent_daily",
            "observed_for":"2026-10-15T00:00:00+00:00",
            "interval_code":"1d","price_value":"99.1",
            "value_concept":"DAILY_SPOT","revision_no":1,
            "available_at":"2026-10-17T00:00:00+00:00",
            "document":{"canonical_url":"https://www.eia.gov/",
                        "sha256_hex":"a"*64,
                        "published_at":"2026-10-16T00:00:00+00:00",
                        "publication_precision":"DAY"}
        }
        job={"run_key":"daily-research-2026-10-18",
             "as_of":"2026-10-18T07:00:00+00:00",
             "code_version":"2.0.0-rc1",
             "observations":[obs],
             "requirements":{}}
        a=run_cycle(job)
        self.assertEqual(a,run_cycle(job))
        self.assertEqual(a["observations_available"],1)
        self.assertFalse(a["hypotheses"])
        self.assertEqual([x["decision_type"] for x in a["paper_decisions"]],["HOLD_CASH"]*3)
        self.assertEqual(a["paper_fills_created"],0)
        self.assertEqual(a["real_orders_created"],0)

    def test_fixed_main_uses_real_execute_twice_and_emits_manifest(self):
        synthetic={
            "newly_written":True, "run_key":"daily-research-2026-10-18",
            "as_of":"2026-10-18T07:00:00+00:00",
            "input_sha256":"b"*64,"observations_available":1,
            "paper_decisions":[{"model_code":x,"decision_type":"HOLD_CASH"} for x in
                               ("M1_GLOBAL_EQ","M2_DIVERSIFIED","M3_TACTICAL")],
            "evaluated_hypotheses":0
        }
        repeat={**synthetic,"newly_written":False}
        with TemporaryDirectory() as tmp:
            with patch.dict("os.environ",{"NEON_DATABASE_URL":"opaque-synthetic"}):
                with patch("scripts.staging_preflight.check_connection") as pre:
                    with patch.object(agent_runner,"execute",side_effect=[synthetic,repeat]) as exe:
                        with patch.object(sys,"argv",["agent_runner","--fixed-staging-canary","--out-dir",tmp]):
                            agent_runner.main()
            pre.assert_called_once_with("opaque-synthetic")
            self.assertEqual(exe.call_count,2)
            self.assertEqual(exe.call_args.args[2],agent_runner.CANARY_NOW)
            summary=json.loads((Path(tmp)/"manifest.json").read_text())
            self.assertEqual(summary["status"],"FULL_RESEARCH_RUNNER_STAGING_VERIFIED")
            self.assertTrue(summary["first_write"])
            self.assertFalse(summary["replay_write"])
            self.assertEqual(summary["real_orders"],0)

    def test_fixed_main_allows_idempotent_re_run_later(self):
        prev={"newly_written":False,"run_key":"daily-research-2026-10-18",
              "as_of":"2026-10-18T07:00:00+00:00","input_sha256":"b"*64,
              "observations_available":1,
              "paper_decisions":[{"decision_type":"HOLD_CASH"}]*3,
              "evaluated_hypotheses":0}
        with TemporaryDirectory() as tmp:
            with patch.dict("os.environ",{"NEON_DATABASE_URL":"test-opaque"}):
                with patch("scripts.staging_preflight.check_connection"):
                    with patch.object(agent_runner,"execute",side_effect=[prev,prev]):
                        with patch.object(sys,"argv",["runner","--fixed-staging-canary","--out-dir",tmp]):
                            agent_runner.main()
            summary=json.loads((Path(tmp)/"manifest.json").read_text())
            self.assertFalse(summary["first_write"])

    def test_runner_refuses_invalid_replay(self):
        first={"newly_written":True,"run_key":"daily-research-2026-10-18",
               "as_of":"2026-10-18T07:00:00+00:00",
               "input_sha256":"a"*64, "observations_available":1,
               "paper_decisions":[{"decision_type":"HOLD_CASH"}]*3,
               "evaluated_hypotheses":0}
        second={**first,"newly_written":False,"input_sha256":"c"*64}
        out=StringIO()
        with TemporaryDirectory() as tmp, patch.dict("os.environ",{"NEON_DATABASE_URL":"opaque-test"}):
            with patch("scripts.staging_preflight.check_connection"):
                with patch.object(agent_runner,"execute",side_effect=[first,second]):
                    with patch.object(sys,"argv",["runner","--fixed-staging-canary","--out-dir",tmp]):
                        with redirect_stderr(out):
                            with self.assertRaises(SystemExit):
                                agent_runner.main()
            self.assertFalse((Path(tmp)/"manifest.json").exists())
        self.assertIn("FULL_STAGING_RUNNER_FAILED: RuntimeError",out.getvalue())

    def test_main_refuses_missing_fixed_flag(self):
        with patch.object(sys,"argv",["runner"]):
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    agent_runner.main()


if __name__=="__main__":
    unittest.main()
