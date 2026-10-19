"""Offline synthetic EIA byte-provenance and gated versioned-ingestion tests."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import StringIO
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import json
from unittest import TestCase
from unittest.mock import patch

from src.isl_v2 import eia_versioned_ingest as ingest
from src.isl_v2.eia_sources import SOURCES, SourceFormatError
from test_eia_sources import NOW, fixture


class Response:
    def __init__(self, raw: bytes, *, source: str = "wti",
                 media: str = "text/html", url: str | None = None):
        self.raw = raw
        self._url = url if url is not None else SOURCES[source][2]
        self.headers = {"Content-Type": media}

    def geturl(self): return self._url
    def read(self, cap): return self.raw[:cap]
    def __enter__(self): return self
    def __exit__(self, *unused): return False


class TransactionalCursorStub:
    """SQL-effect simulator, not a real database. Caller owns rollback/commit."""
    def __init__(self):
        self.roles = list((
            ingest.EXPECTED_WRITER, ingest.EXPECTED_DATABASE, "off",
            False,False,False,False,False,False,False,
            True,True,True,True,
            False,False,False,False,False,False,
        ))
        assert len(self.roles) == 20
        self.source = "eia_wti_daily"
        self.instrument = "WTI_EIA_USD_BBL"
        self.docs = {}
        self.versions = {}
        self.calls = []
        self.result = None

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM pg_roles r" in sql:
            self.result = tuple(self.roles)
        elif "SELECT now()" in sql:
            self.result = (NOW + timedelta(days=10),)
        elif "pg_advisory_xact_lock" in sql:
            self.result = None
        elif "FROM investment_lab.data_sources" in sql:
            self.result = (self.source,) if params[0] == self.source else None
        elif "FROM investment_lab.instruments" in sql:
            self.result = (self.instrument,) if params[0] == self.instrument else None
        elif "INSERT INTO investment_lab.source_documents" in sql:
            code,url,sha,published,retrieved,meta = params
            key = (code,url,sha)
            if key not in self.docs:
                doc_id = f"synthetic-id-{len(self.docs)+1}"
                self.docs[key] = (doc_id,published,"DAY",retrieved,json.loads(meta))
                self.result = (doc_id,)
            else:
                self.result = None
        elif "FROM investment_lab.source_documents" in sql:
            self.result = self.docs.get(tuple(params))
        elif "FROM investment_lab.price_observation_versions v" in sql:
            self.result = self.versions.get(tuple(params))
        elif "INSERT INTO investment_lab.price_observation_versions" in sql:
            code,source,observed,revision,doc,price,available,note = params
            meta = next(v[4] for v in self.docs.values() if v[0] == doc)
            self.versions[(code,source,observed)] = (
                revision,price,available,meta,
            )
            self.result = None
        else:
            raise AssertionError("Unexpected SQL operation")

    def fetchone(self):
        return self.result


class IngestionPlanTests(TestCase):
    def plan(self, *, when=NOW, changed=None):
        return ingest.prepare("wti", fixture(replace_cell=changed), when)

    def test_exact_original_bytes_and_current_retrieval_evidence(self):
        p = self.plan()
        self.assertEqual(p.source_bytes_sha256, hashlib.sha256(fixture()).hexdigest())
        self.assertEqual(p.snapshot.sha256_hex, p.source_bytes_sha256)
        self.assertEqual(p.available_at, NOW)
        s = ingest.dry_run_summary(p)
        self.assertFalse(s["historical_individual_publication_vintages_verified"])
        self.assertEqual(s["database_writes"], 0)
        self.assertEqual(s["database_connections"], 0)
        self.assertEqual(s["daily_spot_observations"], 18)
        summary = json.dumps(s)
        for secret in ("101.10", "104.30", "postgresql://"):
            self.assertNotIn(secret,summary)

    def test_fetch_validates_only_allowlisted_original_html(self):
        def opener(req,timeout):
            self.assertEqual(timeout,30)
            self.assertEqual(req.full_url,SOURCES["wti"][2])
            return Response(fixture())
        p = ingest.fetch_plan("wti", NOW, opener=opener)
        self.assertEqual(p.source_bytes_sha256,hashlib.sha256(fixture()).hexdigest())
        for bad in (
            Response(fixture(),url="https://redirect.invalid/"),
            Response(fixture(),media="application/json"),
            Response(b"",media="text/html"),
        ):
            with self.assertRaises(SourceFormatError):
                ingest.fetch_plan("wti",NOW,opener=lambda *_, r=bad,**__:r)

    def test_prevent_fabricated_or_future_release(self):
        with self.assertRaises(SourceFormatError):
            ingest.prepare("wti",fixture(release="10/19/2026"),NOW)
        with self.assertRaises(SourceFormatError):
            ingest.prepare("wti",fixture(),NOW,max_age_days=1)
        with self.assertRaises(SourceFormatError):
            ingest.prepare("wti",b"not-html",NOW)
        with self.assertRaises(SourceFormatError):
            ingest.prepare("wti",fixture(),NOW.replace(tzinfo=None))

    def test_first_insert_replay_and_one_correction(self):
        cur = TransactionalCursorStub()
        base = self.plan()
        first = ingest.apply_plan(cur,base)
        self.assertTrue(first["document_added"])
        self.assertEqual(first["new_observation_versions"],18)
        self.assertEqual(first["revised_observation_versions"],0)
        self.assertEqual(len(cur.versions),18)
        self.assertEqual(len(cur.docs),1)

        again = ingest.apply_plan(cur,base)
        self.assertFalse(again["document_added"])
        self.assertEqual(again["new_observation_versions"],0)
        self.assertEqual(again["unchanged_prices"],18)

        # A later actual source retrieval with ONE revised observation creates
        # one new document + exactly one revised price version, never 18.
        updated = self.plan(when=NOW + timedelta(days=1),
                            changed=(0,0,"100.95"))
        r = ingest.apply_plan(cur,updated)
        self.assertTrue(r["document_added"])
        self.assertEqual(r["new_observation_versions"],1)
        self.assertEqual(r["revised_observation_versions"],1)
        self.assertEqual(r["unchanged_prices"],17)
        self.assertEqual(len(cur.docs),2)
        self.assertEqual(len(cur.versions),18)
        first_day = sorted(cur.versions)[0]
        self.assertEqual(cur.versions[first_day][0],2)

        for sql,params in cur.calls:
            if "INSERT INTO" in sql:
                self.assertIn("%s",sql)
                self.assertNotIn("100.95",sql)
                self.assertNotIn("101.10",sql)
                self.assertTrue(params)

    def test_changed_html_without_changed_prices_creates_document_only(self):
        cur = TransactionalCursorStub()
        first = self.plan()
        ingest.apply_plan(cur,first)
        altered_html = fixture().replace(b"<html>",b"<html><!--format-update-->")
        later = ingest.prepare("wti",altered_html,NOW+timedelta(days=1))
        res = ingest.apply_plan(cur,later)
        self.assertTrue(res["document_added"])
        self.assertEqual(res["new_observation_versions"],0)
        self.assertEqual(res["unchanged_prices"],18)
        self.assertEqual(len(cur.docs),2)

    def test_denies_owner_legacy_reader_and_excess_privileges(self):
        for index,wrong in ((0,"investment_lab_owner"),
                            (0,"isl_legacy_history_reader"),
                            (2,"on"),(3,True),(7,True),
                            (14,True),(15,True),(16,True),
                            (19,True),(11,False)):
            cur = TransactionalCursorStub()
            cur.roles[index] = wrong
            with self.assertRaisesRegex(SourceFormatError,"writer"):
                ingest.apply_plan(cur,self.plan())
            self.assertEqual(cur.docs,{})
            self.assertEqual(cur.versions,{})

    def test_reject_synthetic_existing_version_without_blending(self):
        cur = TransactionalCursorStub()
        plan = self.plan()
        ingest.apply_plan(cur,plan)
        key = sorted(cur.versions)[0]
        prev=cur.versions[key]
        cur.versions[key]=(prev[0],prev[1],prev[2],
                           {"synthetic":True,"source_type":"EIA_DAILY_SPOT"})
        with self.assertRaisesRegex(SourceFormatError,"provenance"):
            ingest.apply_plan(cur,plan)

    def test_no_cli_writer_or_connection_even_with_flags(self):
        out,err = StringIO(), StringIO()
        with (patch.object(ingest,"fetch_plan",return_value=self.plan()) as public,
              patch.object(ingest,"apply_plan") as writer,
              redirect_stdout(out),redirect_stderr(err)):
            status = ingest.main(["--source","wti"])
            self.assertEqual(status,0)
            status_invalid = None
        self.assertEqual(json.loads(out.getvalue())["database_writes"],0)
        writer.assert_not_called()
        self.assertEqual(err.getvalue(),"")
        with (patch.object(ingest,"fetch_plan",return_value=self.plan()),
              redirect_stderr(StringIO())):
            with self.assertRaises(SystemExit):
                ingest.main(["--source","wti","--write"])


if __name__ == "__main__":
    import unittest
    unittest.main()
