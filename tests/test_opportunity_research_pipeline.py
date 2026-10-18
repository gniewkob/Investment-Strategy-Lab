"""Offline regression tests: market anomalies + macro/geopolitical context.

Synthetic data only, no market requests or real-money actions.
"""
from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import economic_geopolitical_context as context
from scripts import opportunity_demo_fixture
from scripts import opportunity_research_pipeline as pipeline


def example():
    return {
        "event_key": "synthetic-policy-case-01",
        "category": "CENTRAL_BANK_POLICY",
        "transmission_channel": "COST_OF_CAPITAL",
        "source_name": "SYNTHETIC Federal Reserve example",
        "canonical_source_url": "https://www.federalreserve.gov/",
        "evidence_grade": "PRIMARY_OFFICIAL",
        "confirmation_status": "CONFIRMED_OFFICIAL",
        "published_at": "2026-10-14T10:00:00Z",
        "retrieved_at": "2026-10-17T15:00:00Z",
        "reference_series": ["BTC-USD", "ETH-USD"],
        "mechanism": "HYPOTHESIZED_TRANSMISSION_ONLY",
        "counterargument": "Market reaction can be driven by unrelated risk appetite and prior expectations.",
    }


class MacroGeopoliticalPipelineTests(unittest.TestCase):
    def payload(self):
        return opportunity_demo_fixture.generate()

    def test_end_to_end_evidence_pipeline_is_repeatable_and_research_only(self):
        obj = self.payload()
        first, second = pipeline.run_pipeline(obj), pipeline.run_pipeline(obj)
        self.assertEqual(first, second)
        self.assertEqual(first["manifest"]["input_dataset_kind"],
                         "SYNTHETIC_OFFLINE_FIXTURE")
        self.assertEqual(first["manifest"]["source_vintage"],
                         "UNVERIFIED_HISTORICAL_PUBLICATION")
        self.assertEqual(first["manifest"]["hypothetical_allocation_changes"],0)
        self.assertEqual(first["manifest"]["paper_fills"],0)
        self.assertEqual(first["manifest"]["real_orders"],0)
        self.assertEqual(first["manifest"]["database_writes"],0)
        self.assertFalse(first["manifest"]["schedule_enabled"])
        self.assertEqual(first["context"]["status"],"NO_CONTEXT_EVIDENCE")
        self.assertEqual(first["ledger"]["portfolio_reallocations"],0)

    def test_official_event_with_retrieval_timestamp_is_context_only(self):
        obj = self.payload()
        obj["context_source"] = "UNVERIFIED_HISTORICAL_EVENT_VINTAGE"
        obj["context_events"] = [example()]
        report = pipeline.run_pipeline(obj)
        self.assertEqual(report["context"]["status"],"CONTEXT_HYPOTHESES_ONLY")
        self.assertEqual(report["context"]["context_events"],1)
        event = report["context"]["events"][0]
        self.assertFalse(event["causality_verified"])
        self.assertFalse(event["possible_direction_established"])
        self.assertFalse(report["context"]["market_prediction_allowed"])
        self.assertFalse(report["context"]["trade_or_allocation_allowed"])
        self.assertEqual(report["manifest"]["hypothetical_allocation_changes"],0)
        self.assertIn("Market reaction can be driven",event["counterargument"])
        self.assertEqual(len(report["manifest"]["context_sha256"]),64)

    def test_geopolitical_energy_event_can_be_catalogued_without_price_target(self):
        obj = self.payload()
        event = example()
        event.update({"event_key":"synthetic-supply-shock",
                      "category":"SANCTIONS",
                      "transmission_channel":"TRADE_FRICTION",
                      "reference_series":["BTC-USD"],
                      "counterargument":"Economic effects can be offset by changes in other supply and demand channels."})
        obj.update({"context_source":"UNVERIFIED_HISTORICAL_EVENT_VINTAGE",
                    "context_events":[event]})
        report = pipeline.run_pipeline(obj)
        self.assertEqual(report["context"]["events"][0]["category"],"SANCTIONS")
        self.assertFalse(report["context"]["causal_effect_established"])
        self.assertEqual(report["ledger"]["portfolio_reallocations"],0)

    def test_unsupported_source_url_rejected(self):
        obj=self.payload()
        e=example()
        e["canonical_source_url"]="https://bad.example.org/fake"
        obj.update({"context_source":"UNVERIFIED_HISTORICAL_EVENT_VINTAGE",
                    "context_events":[e]})
        with self.assertRaises(ValueError):
            pipeline.run_pipeline(obj)

    def test_event_cannot_be_known_before_retrieval(self):
        obj=self.payload()
        e=example()
        e["retrieved_at"]="2026-10-19T12:00:00Z"
        obj.update({"context_source":"UNVERIFIED_HISTORICAL_EVENT_VINTAGE",
                    "context_events":[e]})
        with self.assertRaisesRegex(ValueError,"Future"):
            pipeline.run_pipeline(obj)

    def test_event_publication_after_retrieval_rejected(self):
        obj=self.payload()
        e=example()
        e["published_at"]="2026-10-18T10:00:00Z"
        obj.update({"context_source":"UNVERIFIED_HISTORICAL_EVENT_VINTAGE",
                    "context_events":[e]})
        with self.assertRaises(ValueError):
            pipeline.run_pipeline(obj)

    def test_missing_counterargument_rejected(self):
        obj=self.payload()
        e=example()
        e.pop("counterargument")
        obj.update({"context_source":"UNVERIFIED_HISTORICAL_EVENT_VINTAGE",
                    "context_events":[e]})
        with self.assertRaises(ValueError):
            pipeline.run_pipeline(obj)

    def test_false_verified_vintage_rejected(self):
        obj=self.payload()
        obj.update({"context_source":"VERIFIED_HISTORICAL_SOURCE",
                    "context_events":[example()]})
        with self.assertRaises(ValueError):
            pipeline.run_pipeline(obj)

    def test_invalid_reference_series_and_duplicates_rejected(self):
        for codes in (["EQUITY_TR_PLN"],["BTC-USD","BTC-USD"]):
            obj=self.payload()
            e=example()
            e["reference_series"]=codes
            obj.update({"context_source":"UNVERIFIED_HISTORICAL_EVENT_VINTAGE",
                        "context_events":[e]})
            with self.assertRaises(ValueError):
                pipeline.run_pipeline(obj)

    def test_missing_dataset_kind_rejected(self):
        obj=self.payload()
        obj.pop("dataset_kind")
        with self.assertRaises(ValueError):
            pipeline.run_pipeline(obj)

    def test_exact_report_artifacts_contain_no_trade_authorization(self):
        with tempfile.TemporaryDirectory() as td:
            inp=Path(td)/"input.json"
            out=Path(td)/"result"
            obj=self.payload()
            obj.update({"context_source":"UNVERIFIED_HISTORICAL_EVENT_VINTAGE",
                        "context_events":[example()]})
            inp.write_text(json.dumps(obj),encoding="utf-8")
            with patch("sys.argv",["pipeline","--input",str(inp),"--out-dir",str(out)]):
                self.assertEqual(pipeline.main(),0)
            self.assertTrue((out/"radar.json").exists())
            self.assertTrue((out/"decision_ledger.json").exists())
            self.assertTrue((out/"economic_geopolitical_context.json").exists())
            self.assertTrue((out/"manifest.json").exists())
            doc=(out/"research_report.md").read_text(encoding="utf-8")
            self.assertIn("Economic and geopolitical evidence",doc)
            self.assertIn("HOLD_NO_CHANGE",doc)
            self.assertIn("not investment advice",doc.lower())
            manifest=json.loads((out/"manifest.json").read_text())
            self.assertEqual(manifest["real_orders"],0)
            self.assertEqual(manifest["database_writes"],0)

    def test_bad_json_does_not_leak_source_text_in_logs(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"test.json"
            f.write_text("private-fake-connection-string",encoding="utf-8")
            log=StringIO()
            with patch("sys.argv",["pipeline","--input",str(f)]):
                with redirect_stderr(log):
                    self.assertEqual(pipeline.main(),2)
            self.assertNotIn("private-fake-connection-string",log.getvalue())
            self.assertIn("EDUCATIONAL_EVIDENCE_PIPELINE_FAILED",log.getvalue())


if __name__=="__main__":
    unittest.main()
