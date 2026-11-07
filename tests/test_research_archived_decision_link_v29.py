"""v0.29 real archived metadata fixture, no proprietary price series."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.research_archived_decision_link_v29 import link
from scripts.shadow_evidence_ledger_v09 import append
from scripts.shadow_decision_engine_v05 import ShadowInputError

ARCHIVE=(Path(__file__).resolve().parents[1] /
         "evidence/shadow/v09/checkpoint-bundle-run-42305280062.json")


def bundle():
    return json.loads(ARCHIVE.read_text(encoding="utf-8"))


class ArchivedDecisionLinkTests(unittest.TestCase):
    def test_real_archived_checkpoint_metadata_replays_hold_without_sources(self):
        value=link(bundle())
        self.assertEqual(value["status"],
                         "ARCHIVED_HOLD_CASH_REPLAYED_NOT_CHRONOLOGICAL_SOURCE_OBSERVATION")
        self.assertTrue(all(x=="HOLD_CASH" for x in value["model_states"].values()))
        self.assertFalse(value["source_series_available"])
        self.assertFalse(value["suitable_for_v28_chronological_market_journal"])
        self.assertFalse(value["qualified_m1_m2_m3"])
        self.assertEqual(value["financial_operations"],0)

    def test_replayed_evidence_is_deterministic_and_does_not_modify_bundle(self):
        doc=bundle()
        original=deepcopy(doc)
        self.assertEqual(link(doc),link(deepcopy(doc)))
        self.assertEqual(doc,original)
        self.assertEqual(len(link(doc)["evidence_link_sha256"]),64)

    def test_real_archived_bundle_reconciles_existing_read_only_sqlite_ledger(self):
        doc=bundle()
        with TemporaryDirectory() as d:
            path=Path(d)/"private.sqlite"
            added=append(path, doc)
            self.assertEqual(added["append_status"],"NEW_EVIDENCE")
            result=link(doc,ledger_path=path)
            self.assertEqual(result["v09_ledger_reconciliation"]["ledger_sequence"],1)
            self.assertEqual(result["v09_ledger_reconciliation"]["ledger_entries"],1)
            self.assertEqual(result["v09_ledger_reconciliation"]["ledger_head_sha256"],
                             added["head_sha256"])
            self.assertFalse(result["v09_ledger_reconciliation"]["ledger_externally_anchored"])

    def test_missing_original_ledger_does_not_create_new_database(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"missing.sqlite"
            with self.assertRaisesRegex(ShadowInputError,"existing ordinary"):
                link(bundle(),ledger_path=path)
            self.assertFalse(path.exists())

    def test_tampered_capture_rejected_even_if_no_ledger(self):
        doc=bundle()
        doc["capture"]["orders_sent"]=1
        with self.assertRaises(ShadowInputError):
            link(doc)

    def test_tampered_checkpoint_rejected(self):
        doc=bundle()
        doc["checkpoint"]["status"]="APPROVED_LIVE_TRADING"
        with self.assertRaises(ShadowInputError):
            link(doc)

    def test_disconnected_ledger_identity_fail_closed(self):
        doc=bundle()
        with TemporaryDirectory() as d:
            path=Path(d)/"private.sqlite"
            append(path,doc)
            # Disturb the ledger's canonical data without rewriting the
            # externally known checkpoint: mandatory full audit rejects.
            import sqlite3
            with sqlite3.connect(path) as conn:
                conn.execute("DROP TRIGGER evidence_no_update")
                conn.execute("UPDATE evidence SET bundle_sha256=? WHERE seq=1",("a"*64,))
            with self.assertRaises(ShadowInputError):
                link(doc,ledger_path=path)

    def test_no_live_mode_or_missing_archived_metadata(self):
        doc=bundle()
        doc["capture"]["decision"]["mode"]="LIVE_TRADING"
        with self.assertRaises(ShadowInputError):
            link(doc)
        doc=bundle()
        doc["run"]["conclusion"]="failure"
        with self.assertRaises(ShadowInputError):
            link(doc)


if __name__=="__main__":
    unittest.main()
