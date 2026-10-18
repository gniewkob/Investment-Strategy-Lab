"""Research-only decision ledger validation. Pure fixture tests, no secrets."""
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.evidence_decision_ledger import make_ledger, markdown_report, main


def source(shock_count=5, windows=100):
    return {
        "status":"RETROSPECTIVE_RESEARCH_COMPLETE",
        "source_vintage":"UNVERIFIED_HISTORICAL_PUBLICATION",
        "pit_backtest_certified":False,
        "real_orders":0,"database_writes":0,"virtual_portfolio_changes":0,
        "decision_classification":"INVESTIGATE_OR_OBSERVE_ONLY",
        "data_sha256":"a"*64,
        "series":[{
            "instrument_code":"BTC-USD","interval_code":"1d",
            "shock_samples":shock_count,
            "five_bar_baseline_samples":windows,
            "baseline_average_five_bar_change_pct":1.2,
            "shock_average_five_bar_change_pct":4.4,
        }]
    }


class EvidenceLedgerTests(unittest.TestCase):
    def test_a_historical_anomaly_qualifies_only_for_further_investigation(self):
        r=make_ledger(source())
        self.assertEqual(r["questions_for_independent_review"],1)
        self.assertEqual(r["questions"][0]["educational_decision"],
                         "INVESTIGATE_RESEARCH_ONLY")
        self.assertIs(r["questions"][0]["trade_or_purchase_allowed"],False)
        self.assertEqual(r["portfolio_reallocations"],0)
        self.assertEqual(r["real_orders"],0)

    def test_few_signals_do_not_claim_predictive_evidence(self):
        r=make_ledger(source(shock_count=3))
        self.assertEqual(r["questions"][0]["educational_decision"],"INSUFFICIENT_EVIDENCE")
        self.assertEqual(r["questions_for_independent_review"],0)
        self.assertTrue(r["questions"][0]["evidence_against"])

    def test_short_holdout_does_not_qualify(self):
        r=make_ledger(source(shock_count=7, windows=30))
        self.assertEqual(r["questions"][0]["educational_decision"],"INSUFFICIENT_EVIDENCE")
        self.assertFalse(r["questions"][0]["change_virtual_allocation"])

    def test_original_three_models_remain_unchanged(self):
        r=make_ledger(source())
        self.assertEqual(len(r["paper_portfolio_decisions"]),3)
        self.assertTrue(all(x["decision"]=="HOLD_NO_CHANGE" for x in r["paper_portfolio_decisions"]))
        self.assertTrue(all(x["orders"]==0 for x in r["paper_portfolio_decisions"]))
        self.assertFalse(r["automated_execution"])

    def test_missing_vintage_or_false_pit_claim_is_rejected(self):
        d=source()
        d["source_vintage"]="VERIFIED_PIT"
        with self.assertRaises(ValueError):
            make_ledger(d)
        d=source()
        d["pit_backtest_certified"]=True
        with self.assertRaises(ValueError):
            make_ledger(d)

    def test_input_purporting_to_trade_or_reallocate_is_rejected(self):
        for field in ("real_orders","database_writes","virtual_portfolio_changes"):
            d=source()
            d[field]=1
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    make_ledger(d)

    def test_invalid_signal_counts_rejected(self):
        for kwargs in (dict(shock_count=-1),dict(shock_count=20,windows=10),
                       dict(shock_count=2.5),dict(windows=-1)):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    make_ledger(source(**kwargs))

    def test_report_mentions_prohibitions_and_limits(self):
        r=make_ledger(source())
        doc=markdown_report(r)
        self.assertIn("HOLD_NO_CHANGE",doc)
        self.assertIn("not trade recommendations",doc)
        self.assertIn("Historical",doc)

    def test_cli_generates_reports_without_database_access(self):
        with TemporaryDirectory() as td:
            base=Path(td)
            input_file=base/"radar.json"
            input_file.write_text(json.dumps(source()),encoding="utf-8")
            output=base/"out"
            with patch("sys.argv",["ledger","--radar-input",str(input_file),"--out-dir",str(output)]):
                self.assertEqual(main(),0)
            r=json.loads((output/"decision_ledger.json").read_text())
            self.assertEqual(r["portfolio_reallocations"],0)
            self.assertEqual(r["questions"][0]["educational_decision"],"INVESTIGATE_RESEARCH_ONLY")
            self.assertTrue((output/"decision_ledger.md").exists())

    def test_cli_suppresses_sensitive_error_details(self):
        with TemporaryDirectory() as td:
            f=Path(td)/"bad.json"
            f.write_text("do-not-print-sensitive-input")
            stderr=StringIO()
            with patch("sys.argv",["ledger","--radar-input",str(f)]):
                with redirect_stderr(stderr):
                    self.assertEqual(main(),2)
            self.assertIn("RESEARCH_EVIDENCE_LEDGER_FAILED",stderr.getvalue())
            self.assertNotIn("do-not-print-sensitive-input",stderr.getvalue())


if __name__=="__main__":
    unittest.main()
