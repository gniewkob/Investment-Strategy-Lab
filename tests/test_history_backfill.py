"""Synthetic-only validation of rate-limited ERC20 history repair and persistence."""
from copy import deepcopy
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from scripts import history_backfill as b, history_coverage as c
from scripts.operational_read_only import TRANSFER_TOPIC, TOKENS

CHAIN = 8453
ADDRESS = "0x" + "a"*40
TOKEN = next(iter(TOKENS[CHAIN]))
LABEL = "research"
KEY = "chain_research_8453"
HASH = "0x" + "b"*64
TOPIC_FROM = "0x" + "0"*24 + ADDRESS[2:]
TOPIC_OTHER = "0x" + "0"*24 + "c"*40
ENTRIES = [(CHAIN, ADDRESS, LABEL, frozenset({TOKEN}))]


def source(start, end):
    return {KEY: {"status": "OK", "data": {
        "wallets": [{"wallet_label": LABEL, "chain_id": CHAIN,
                     "source_block_number": end,
                     "history": {"status": "COMPLETE_REQUESTED_TOKEN_RANGE",
                                 "from_block": start, "to_block": end}}]}}}


def gap(lo=2000, hi=2199):
    first = c.advance(None, ENTRIES, source(1000, 1999))
    return c.advance(first, ENTRIES, source(lo+0, hi+1000))


def rpc_fixture(event=False, *, limit=False, changed=False, logs_fail=False):
    calls = []
    def rpc(chain, method, params):
        calls.append((chain, method, params))
        if logs_fail and method == "eth_getLogs":
            raise RuntimeError("SYNTHETIC_RPC_ERROR_WITH_PRIVATE_PATH")
        if method == "eth_chainId":
            return hex(CHAIN)
        if method == "eth_getBlockByNumber":
            ident = params[0]
            number = 5000 if ident == "finalized" else int(ident, 16)
            return {"number": hex(number), "hash": ("0x" + "f"*64 if changed and ident != "finalized" and calls.count((chain,method,params))>1 else HASH),
                    "timestamp": "0x70"}
        if method == "eth_getLogs":
            if not event:
                return []
            query = params[0]
            if len(query["topics"]) == 3:
                return []
            start = int(query["fromBlock"],16)
            return [{"address":TOKEN, "topics":[TRANSFER_TOPIC, TOPIC_FROM, TOPIC_OTHER],
                "transactionHash":HASH, "blockHash":HASH, "blockNumber":hex(start),
                "logIndex":"0x0", "data":hex(500), "removed":False}]
        raise AssertionError(method)
    return rpc,calls


class RestoreTests(unittest.TestCase):
    def test_partial_and_complete_restore_adjusts_oldest_gap_only(self):
        original=gap()
        before=deepcopy(original)
        id_=original["streams"][KEY]["identity_sha256"]
        half=b.restore(original,KEY,id_,2000,2079,"1"*64)
        self.assertEqual(half["streams"][KEY]["gap_ranges"],[[2080,2199]])
        self.assertTrue(half["historical_gap_detected"])
        done=b.restore(half,KEY,id_,2080,2159,"1"*64)
        done=b.restore(done,KEY,id_,2160,2199,"1"*64)
        self.assertEqual(done["streams"][KEY]["gap_ranges"],[])
        self.assertFalse(done["historical_gap_detected"])
        self.assertEqual(done["streams"][KEY]["last_complete_to_block"],3199)
        self.assertEqual(original,before)

    def test_reject_unverified_order_scope_or_chunk(self):
        cvr=gap(); scope=cvr["streams"][KEY]["identity_sha256"]
        for stream,identity,start,end in (
            (KEY,scope,2001,2080),(KEY,scope,2000,2080),
            (KEY,"9"*64,2000,2079),(KEY,scope,1900,1979),
            ("missing",scope,2000,2079)):
            with self.subTest(start=start,end=end):
                with self.assertRaises(b.RecoveryError):
                    b.restore(cvr,stream,identity,start,end,"1"*64)
        cvr["streams"][KEY]["gap_range_overflow"]=True
        done=b.restore(cvr,KEY,scope,2000,2079,"1"*64)
        self.assertTrue(done["historical_gap_detected"])


class RecoveryTests(unittest.TestCase):
    def test_no_gap_causes_no_rpc_or_filesystem(self):
        latest=c.advance(None,ENTRIES,source(1000,1999))
        def should_not_read(*args): self.fail("read-only RPC unexpectedly invoked")
        with tempfile.TemporaryDirectory() as d:
            r=b.recover_one(latest,ENTRIES,source(1000,1999),d,rpc=should_not_read)
            self.assertEqual(r["status"],"NO_ELIGIBLE_GAP")
            self.assertFalse((Path(d)/"history-backfill").exists())

    def test_stepwise_backfill_evidence_before_gap_closure(self):
        rpc,calls=rpc_fixture()
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            current=gap()
            for expected_lo,expected_hi,blocks in ((2080,2199,80),(2160,2199,80),(None,None,40)):
                report=b.recover_one(current,ENTRIES,source(2200,3199),root,rpc=rpc)
                self.assertEqual(report["status"],"RECOVERED_WINDOW")
                self.assertEqual(report["recovered_block_count"],blocks)
                self.assertEqual(report["events_saved"],0)
                current=report["coverage"]
                if expected_lo is None:
                    self.assertEqual(current["gap_range_count"],0)
                else:
                    self.assertEqual(current["streams"][KEY]["gap_ranges"],[[expected_lo,expected_hi]])
            files=list((root/"history-backfill").glob("*.json"))
            self.assertEqual(len(files),3)
            self.assertEqual((root/"history-backfill").stat().st_mode & 0o777,0o700)
            self.assertTrue(all(p.stat().st_mode & 0o777==0o600 for p in files))
            self.assertNotIn(ADDRESS,json.dumps(current))
            self.assertNotIn(ADDRESS," ".join(p.name for p in files))
            self.assertFalse(current["complete_chain_history_certified"])
            self.assertEqual(report["financial_operations"],0)
            self.assertEqual(len([x for x in calls if x[1]=="eth_getLogs"]),6)

    def test_failure_does_not_save_or_clear_gap(self):
        rpc,calls=rpc_fixture(logs_fail=True)
        with tempfile.TemporaryDirectory() as root:
            state=gap()
            original=deepcopy(state)
            with self.assertRaisesRegex(RuntimeError,"SYNTHETIC_RPC_ERROR"):
                b.recover_one(state,ENTRIES,source(2200,3199),root,rpc=rpc)
            self.assertEqual(state,original)
            self.assertFalse((Path(root)/"history-backfill").exists())

    def test_wrong_chain_unsupported_scope_and_unfinalized_target_reject(self):
        with tempfile.TemporaryDirectory() as root:
            wrong=lambda chain, method, params: "0x1" if method=="eth_chainId" else {}
            with self.assertRaises(b.RecoveryError):
                b.recover_one(gap(),ENTRIES,source(2200,3199),root,rpc=wrong)
            entries=[(CHAIN,ADDRESS,LABEL,frozenset({"0x"+"9"*40}))]
            with self.assertRaises(b.RecoveryError):
                b.recover_one(gap(),entries,source(2200,3199),root,rpc=wrong)
            def old_head(chain,method,params):
                if method=="eth_chainId":return hex(CHAIN)
                return {"number":hex(2078),"hash":HASH,"timestamp":"0x70"}
            with self.assertRaises(b.RecoveryError):
                b.recover_one(gap(),ENTRIES,source(2200,3199),root,rpc=old_head)

    def test_verified_one_log_persisted_only_privately_and_idempotent(self):
        rpc,calls=rpc_fixture(event=True)
        with tempfile.TemporaryDirectory() as root:
            original=gap(2000,2080)
            first=b.recover_one(original,ENTRIES,source(2081,3080),root,rpc=rpc)
            self.assertEqual(first["events_saved"],1)
            files=list((Path(root)/"history-backfill").glob("*.json"))
            self.assertEqual(len(files),1)
            captured=json.loads(files[0].read_text())
            self.assertEqual(captured["event_count"],1)
            self.assertEqual(captured["events"][0]["block_number"],2000)
            self.assertFalse(captured["coinbase_linkage_verified"])
            self.assertNotIn(ADDRESS,files[0].read_text())
            # Simulate crash after durable evidence, before coverage commit.
            again=b.recover_one(original,ENTRIES,source(2081,3080),root,rpc=rpc)
            self.assertEqual(again["coverage"],first["coverage"])
            self.assertEqual(len(list((Path(root)/"history-backfill").glob("*.json"))),1)
            self.assertEqual(first["coverage"]["streams"][KEY]["gap_ranges"],[[2080,2080]])

    def test_tampered_evidence_cannot_acknowledge_gap(self):
        rpc,calls=rpc_fixture()
        with tempfile.TemporaryDirectory() as root:
            initial=gap()
            result=b.recover_one(initial,ENTRIES,source(2200,3199),root,rpc=rpc)
            p=next((Path(root)/"history-backfill").glob("*.json"))
            data=json.loads(p.read_text());data["event_count"]=999
            p.write_text(json.dumps(data))
            with self.assertRaises(b.RecoveryError):
                b.recover_one(initial,ENTRIES,source(2200,3199),root,rpc=rpc)
            self.assertEqual(initial["streams"][KEY]["gap_ranges"],[[2000,2199]])
            self.assertTrue(result["coverage"]["historical_gap_detected"])

    def test_partial_latest_source_skips_expensive_recovery(self):
        r=gap()
        no_source={KEY:{"status":"PARTIAL","data":None}}
        def not_allowed(*args): self.fail("must not fetch")
        with tempfile.TemporaryDirectory() as root:
            result=b.recover_one(r,ENTRIES,no_source,root,rpc=not_allowed)
            self.assertEqual(result["status"],"NO_ELIGIBLE_GAP")
            self.assertEqual(result["coverage"],r)


if __name__ == "__main__":
    unittest.main()
