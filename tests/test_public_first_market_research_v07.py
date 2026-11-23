"""Offline integration of source-qualified market research, synthetic fixtures only."""
from __future__ import annotations

import copy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from scripts.public_first_market_research_v07 import (
    ResearchPipelineBlocked, compose_market_research, main,
)
from tests.test_public_first_market_quality_v07 import synthetic_three_sources
from tests.test_research_readiness_quality_v07 import evidence

NOW=datetime(2026,11,14,0,tzinfo=timezone.utc)


def _stamp(receipt):
    payload={k:v for k,v in receipt.items() if k!="receipt_sha256"}
    receipt["receipt_sha256"]=sha256(
        json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def three_source_receipts():
    mf,nav,macro=synthetic_three_sources()
    nav_quality,mf_schema=evidence()
    nav_quality["source_history_sha256"]=nav["source_documents"]["history_sha256"]
    nav_quality["observed_by_runner_at_utc"]=nav["observed_at_utc"]
    mf_schema["sha256"]=mf["source_sha256"]
    mf_schema["observed_at_utc"]=mf["source_observed_at_utc"]
    return dict(nav_quality=nav_quality,mf_schema=mf_schema,
                macro_reference=macro,mf_turnover=mf,nav_original=nav)


class MarketResearchPipelineTests(unittest.TestCase):
    def test_schema_only_holds_cash_without_market_values(self):
        receipts=three_source_receipts()
        receipts.pop("mf_turnover")
        receipts.pop("nav_original")
        result=compose_market_research(**receipts,observed_at=NOW)
        self.assertEqual(result["mode"],"SCHEMA_ONLY")
        self.assertIsNone(result["market_context"])
        self.assertEqual(result["source_readiness"]["source_families"],3)
        self.assertFalse(result["historical_pit_admitted"])
        self.assertEqual(result["asset_total_return_qualified"],[])
        self.assertEqual(result["m1_m2_m3"],"INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual(result["financial_operations"],0)
        self.assertEqual(result["outbound_reads_by_reporter"],0)

    def test_matched_original_receipts_add_descriptive_market_context(self):
        result=compose_market_research(**three_source_receipts(),observed_at=NOW)
        self.assertEqual(result["mode"],"DESCRIPTIVE_MARKET_CONTEXT")
        self.assertEqual(result["market_context"]["source_quality_gate"]["mf_complete_history_months"],202)
        self.assertEqual(result["market_context"]["source_quality_gate"]["macro_nbp_publication_days"],1)
        self.assertFalse(result["market_context"]["source_quality_gate"]["macro_nbp_full_22_day_coverage"])
        self.assertFalse(result["market_context"]["cross_source_causal_inference_permitted"])
        self.assertEqual(result["asset_total_return_qualified"],[])
        self.assertEqual(result["m1_m2_m3"],"INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual(result["source_consistency"]["mf_workbook_sha256"],
                         result["market_context"]["original_source_payload_fingerprints"]["mf_original_workbook"])
        self.assertRegex(result["receipt_sha256"],r"^[a-f0-9]{64}$")

    def test_mf_fingerprint_mismatch_denied_even_if_separately_validated(self):
        receipts=three_source_receipts()
        receipts["mf_schema"]["sha256"]="b"*64
        with self.assertRaisesRegex(ResearchPipelineBlocked,"MF_SOURCE_MISMATCH"):
            compose_market_research(**receipts,observed_at=NOW)

    def test_nav_fingerprint_mismatch_denied_even_with_recomputed_receipt_hash(self):
        receipts=three_source_receipts()
        receipts["nav_quality"]["source_history_sha256"]="c"*64
        _stamp(receipts["nav_quality"])
        with self.assertRaisesRegex(ResearchPipelineBlocked,"NAV_SOURCE_MISMATCH"):
            compose_market_research(**receipts,observed_at=NOW)

    def test_half_admitted_original_context_denied(self):
        receipts=three_source_receipts()
        receipts.pop("nav_original")
        with self.assertRaisesRegex(ResearchPipelineBlocked,"ORIGINAL_CONTEXT_ALL_OR_NOTHING"):
            compose_market_research(**receipts,observed_at=NOW)

    def test_original_market_context_requires_macro(self):
        receipts=three_source_receipts()
        receipts.pop("macro_reference")
        with self.assertRaisesRegex(ResearchPipelineBlocked,"ORIGINAL_CONTEXT_ALL_OR_NOTHING"):
            compose_market_research(**receipts,observed_at=NOW)

    def test_future_source_observation_denied(self):
        receipts=three_source_receipts()
        receipts["mf_schema"]["observed_at_utc"]=(NOW+timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ResearchPipelineBlocked,"SOURCE_OBSERVED_AFTER_REPORT"):
            compose_market_research(**receipts,observed_at=NOW)

    def test_invalid_receipt_hash_denied_when_present(self):
        receipts=three_source_receipts()
        receipts["macro_reference"]["receipt_sha256"]="d"*64
        with self.assertRaisesRegex(ResearchPipelineBlocked,"RECEIPT_HASH_MISMATCH"):
            compose_market_research(**receipts,observed_at=NOW)

    def test_repeatable_json_and_markdown_cli_with_no_market_context(self):
        payload=three_source_receipts()
        payload.pop("mf_turnover")
        payload.pop("nav_original")
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            inpath=root/"input.json"
            inpath.write_text(json.dumps(payload),encoding="utf-8")
            out=root/"reports"
            argv=["--input",str(inpath),"--out-dir",str(out),
                  "--observed-at-utc",NOW.isoformat()]
            self.assertEqual(main(argv),0)
            first_json=(out/"market_research_v07.json").read_bytes()
            first_md=(out/"market_research_v07.md").read_bytes()
            self.assertEqual(main(argv),0)
            self.assertEqual(first_json,(out/"market_research_v07.json").read_bytes())
            self.assertEqual(first_md,(out/"market_research_v07.md").read_bytes())
            self.assertIn(b"HOLD_CASH",first_md)
            self.assertNotIn(b"buy",first_md)
            self.assertEqual(json.loads(first_json)["mode"],"SCHEMA_ONLY")


if __name__=="__main__":
    unittest.main()
