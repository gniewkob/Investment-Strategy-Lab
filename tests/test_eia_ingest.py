"""In-memory transactional-cursor tests of the EIA research-only importer.

No real PostgreSQL, credentials, network or brokerage access.
"""
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from src.isl_v2.eia_ingest import fetch_official, store, summary
from src.isl_v2.eia_sources import SourceFormatError, parse_snapshot
from test_eia_sources import fixture, NOW


class CursorStub:
    """Narrow SQL-effect simulator: tests revisions and idempotency semantics."""
    def __init__(self):
        self.versions = {}
        self.runs = {}
        self.docs = set()
        self.calls = []
        self.result = None
        self.catalogue_ok = True

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "pg_advisory_xact_lock" in sql:
            self.result = (1,)
        elif "FROM investment_lab.data_sources" in sql or "FROM investment_lab.instruments" in sql:
            self.result = ("exists",) if self.catalogue_ok else None
        elif "SELECT status FROM investment_lab.pipeline_runs" in sql:
            self.result = (self.runs[params[0]],) if params[0] in self.runs else None
        elif "INSERT INTO investment_lab.source_documents" in sql:
            self.docs.add(params[2])
            self.result = None
        elif "SELECT document_id FROM investment_lab.source_documents" in sql:
            self.result = ("fixture-document-" + params[2][:8],)
        elif "SELECT revision_no,price_value FROM investment_lab.price_observation_versions" in sql:
            key = (params[0], params[1], params[2])
            self.result = self.versions.get(key)
        elif "INSERT INTO investment_lab.price_observation_versions" in sql:
            inst, source, obs, rev, doc, price, available, note = params
            self.versions[(inst, source, obs)] = (rev, price)
            self.result = None
        elif "INSERT INTO investment_lab.pipeline_runs" in sql:
            self.runs[params[0]] = "SUCCEEDED"
            self.result = None
        else:
            raise AssertionError("Unexpected SQL operation: " + sql[:100])

    def fetchone(self):
        return self.result


class Response:
    def __init__(self, url, data, mimetype="text/html"):
        self.url, self.data = url, data
        self.headers = {"Content-Type": mimetype}

    def geturl(self):
        return self.url

    def read(self, maxbytes):
        return self.data[:maxbytes]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class IngestionTests(unittest.TestCase):
    def snapshot(self, replaced=None):
        return parse_snapshot("brent", fixture(replace_cell=replaced), NOW)

    def test_first_snapshot_saved_once(self):
        cur = CursorStub()
        s = self.snapshot()
        first = store(cur, s)
        self.assertEqual(first["new"], 18)
        self.assertEqual(first["revised"], 0)
        self.assertEqual(len(cur.versions), 18)
        again = store(cur, s)
        self.assertTrue(again["duplicate_run"])
        self.assertEqual(again["new"], 0)
        self.assertEqual(len(cur.versions), 18)

    def test_source_correction_creates_new_revision_only(self):
        cur = CursorStub()
        store(cur, self.snapshot())
        r = store(cur, self.snapshot((0, 0, "100.95")))
        self.assertEqual(r["new"], 1)
        self.assertEqual(r["revised"], 1)
        self.assertEqual(len(cur.docs), 2)
        self.assertEqual(len(cur.versions), 18)
        self.assertEqual(next(iter(cur.versions.values()))[0], 2)

    def test_unverified_source_is_rejected(self):
        cur = CursorStub()
        cur.catalogue_ok = False
        with self.assertRaises(SourceFormatError):
            store(cur, self.snapshot())
        self.assertEqual(len(cur.versions), 0)

    def test_read_only_source_summary_flags_staleness(self):
        s = self.snapshot()
        info = summary(s, today=NOW.date())
        self.assertEqual(info["validated_observations"], 18)
        self.assertFalse(info["is_stale"])
        from datetime import timedelta
        self.assertTrue(summary(s, today=NOW.date() + timedelta(days=25))["is_stale"])

    def test_fetch_from_eia_allowlist_without_redirect(self):
        s = self.snapshot()
        def opener(request, timeout):
            self.assertEqual(timeout, 30)
            return Response(s.url, fixture())
        got = fetch_official("brent", NOW, opener=opener)
        self.assertEqual(got.sha256_hex, s.sha256_hex)

    def test_reject_fetch_redirect(self):
        def opener(request, timeout):
            return Response("https://example.invalid/page", fixture())
        with self.assertRaises(SourceFormatError):
            fetch_official("brent", NOW, opener=opener)

    def test_reject_non_html_content_type(self):
        url = self.snapshot().url
        def opener(request, timeout):
            return Response(url, b"NOT HTML", "application/pdf")
        with self.assertRaises(SourceFormatError):
            fetch_official("brent", NOW, opener=opener)


if __name__ == "__main__":
    unittest.main()
