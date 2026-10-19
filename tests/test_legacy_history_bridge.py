"""Offline security tests for private, read-only market-reference history bridge."""
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import legacy_history_bridge as bridge
from scripts.opportunity_demo_fixture import generate


HOST=bridge.EXPECTED_HOST
GOOD=(f"postgresql://{bridge.EXPECTED_READER}:synthetic-test-password@{HOST}/"
      "investment_lab?sslmode=verify-full")
ASOF=datetime(2026,10,19,8,tzinfo=timezone.utc)


def sample_row(day=0,code="BTC-USD",price="101"):
    when=datetime(2026,4,1,tzinfo=timezone.utc)+timedelta(days=day)
    source,interval,basis=bridge.SOURCES[code]
    return (code,source,interval,basis,when,
            datetime(2026,10,17,tzinfo=timezone.utc),Decimal(price))


class FakeDB:
    """Only SELECT and read-only transaction are supported."""
    def __init__(self,rows,admin=False):
        self.rows=rows
        self.admin=admin
        self.query=[]
        self.fetch_result=None
        self.fetch_all=None

    def __enter__(self): return self
    def __exit__(self,*args): return False
    def cursor(self): return self

    def execute(self,sql,params=None):
        text=" ".join(sql.split())
        self.query.append((text,params))
        self.fetch_result=None
        self.fetch_all=None
        if text=="SET TRANSACTION READ ONLY":
            return
        if "FROM pg_roles r WHERE r.rolname=current_user" in text:
            self.fetch_result=(bridge.EXPECTED_READER,"investment_lab","on",
                               False,False,False,False,
                               False,False,False,True,False,
                               self.admin,False,False,False)
        elif text=="SELECT now()":
            self.fetch_result=(ASOF,)
        elif "FROM investment_lab.price_observations" in text:
            self.fetch_all=self.rows
            if params[3]!=bridge.MAX_ROWS+1:
                raise AssertionError("Unbounded historical query")
        else:
            raise AssertionError("Unexpected database query: "+text[:100])

    def fetchone(self): return self.fetch_result
    def fetchall(self): return self.fetch_all


class HistoricalBridgeTests(unittest.TestCase):
    def test_known_staging_reader_with_full_tls(self):
        bridge.validate_research_dsn(GOOD)

    def test_wrong_credentials_and_destinations_rejected(self):
        invalid=[
            GOOD.replace(bridge.EXPECTED_READER,"investment_lab_owner"),
            GOOD.replace(bridge.EXPECTED_READER,"isl_agent_staging_limited"),
            GOOD.replace(HOST,"ep-other-neon.c-8.eu-central-1.aws.neon.tech"),
            GOOD.replace(HOST,HOST.replace(".c-8.","-pooler.c-8.")),
            GOOD.replace("sslmode=verify-full","sslmode=require"),
            GOOD.replace(":synthetic-test-password@","@"),
            GOOD+"&hostaddr=127.0.0.1",
            GOOD+"&service=fixture",
            GOOD.replace("/investment_lab?","/neondb?"),
        ]
        for case in invalid:
            with self.subTest(index=invalid.index(case)):
                with self.assertRaises(ValueError):
                    bridge.validate_research_dsn(case)

    def test_snapshot_is_retrospective_and_source_fingerprinted(self):
        rows=[sample_row(0),sample_row(1),sample_row(2)]
        s,m=bridge.snapshot_from_rows(rows,ASOF)
        self.assertEqual(m["total_rows"],3)
        self.assertFalse(m["raw_price_exported_as_artifact"])
        self.assertEqual(len(m["source_mapping_sha256"]),64)
        self.assertEqual(m["series_counts"],{"BTC-USD":3})
        self.assertEqual(s["source_vintage"],"UNVERIFIED_HISTORICAL_PUBLICATION")
        self.assertEqual(s["dataset_kind"],"LEGACY_REFERENCE_SNAPSHOT_UNVERIFIED")
        self.assertNotIn("source_code",s["records"][0])

    def test_mismatched_source_rejected(self):
        row=list(sample_row())
        row[1]="coinbase_fake"
        with self.assertRaisesRegex(ValueError,"mismatched"):
            bridge.snapshot_from_rows([tuple(row)],ASOF)

    def test_future_ingestion_and_observation_rejected(self):
        row=list(sample_row())
        row[5]=ASOF+timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError,"chronology"):
            bridge.snapshot_from_rows([tuple(row)],ASOF)
        row=list(sample_row())
        row[4]=ASOF+timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError,"chronology"):
            bridge.snapshot_from_rows([tuple(row)],ASOF)

    def test_price_and_duplicate_periods_rejected(self):
        for price in ("0","NaN","-1"):
            with self.subTest(price=price):
                with self.assertRaises(ValueError):
                    bridge.snapshot_from_rows([sample_row(price=price)],ASOF)
        with self.assertRaises(ValueError):
            bridge.snapshot_from_rows([sample_row(),sample_row()],ASOF)

    def test_max_records_fail_closed(self):
        with self.assertRaises(ValueError):
            bridge.snapshot_from_rows([],ASOF)
        with self.assertRaises(ValueError):
            bridge.snapshot_from_rows([sample_row()]*(bridge.MAX_ROWS+1),ASOF)

    def test_reader_uses_strict_tls_readonly_sql_and_no_private_tables(self):
        db=FakeDB([sample_row()])
        with patch("psycopg.connect",return_value=db) as connect:
            snap,manifest=bridge.fetch_staging_history(GOOD)
        self.assertEqual(manifest["total_rows"],1)
        self.assertEqual(connect.call_args.kwargs["sslmode"],"verify-full")
        self.assertEqual(connect.call_args.kwargs["sslrootcert"],
                         "/etc/ssl/certs/ca-certificates.crt")
        self.assertIn("default_transaction_read_only=on",
                      connect.call_args.kwargs["options"])
        self.assertEqual(db.query[0][0],"SET TRANSACTION READ ONLY")
        for sql,_ in db.query:
            self.assertTrue(sql.startswith(("SELECT","SET TRANSACTION")))
            self.assertNotIn("FROM investment_lab.holding_snapshots",sql)
            self.assertNotIn("FROM investment_lab.paper_events",sql)
        self.assertEqual(snap["records"][0]["instrument_code"],"BTC-USD")

    def test_reader_rejects_access_to_private_holdings(self):
        db=FakeDB([sample_row()],admin=True)
        with patch("psycopg.connect",return_value=db):
            with self.assertRaisesRegex(RuntimeError,"least-privilege"):
                bridge.fetch_staging_history(GOOD)
        self.assertFalse(any("FROM investment_lab.price_observations" in q
                             for q,_ in db.query))

    def test_real_offline_pipeline_generates_aggregate_only_outputs(self):
        fake=generate()  # explicitly artificial historical observations
        rows=[]
        for r in fake["records"]:
            code=r["instrument_code"]
            source,interval,basis=bridge.SOURCES[code]
            rows.append((code,source,interval,basis,
                         datetime.fromisoformat(r["observed_for"]),
                         datetime.fromisoformat(r["ingested_at"]),
                         Decimal(r["close_price"])))
        snapshot,manifest=bridge.snapshot_from_rows(rows,ASOF)
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)
            result=bridge.run_and_report(snapshot,manifest,output)
            self.assertEqual(result["real_orders"],0)
            self.assertEqual(result["database_writes"],0)
            self.assertEqual(result["hypothetical_allocation_changes"],0)
            self.assertTrue((output/"research_report.md").exists())
            quality=json.loads((output/"reference_data_quality.json").read_text())
            self.assertEqual(quality["status"], "REFERENCE_DATA_QUALITY_RESEARCH_ONLY")
            self.assertFalse(quality["historical_release_dates_verified"])
            self.assertEqual(quality["source_radar_sha256"], result["radar_data_sha256"])
            self.assertEqual(quality["database_writes"], 0)
            self.assertEqual(quality["real_orders"], 0)
            saved=json.loads((output/"manifest.json").read_text())
            self.assertEqual(saved["source_vintage"],"UNVERIFIED_HISTORICAL_PUBLICATION")
            self.assertEqual(saved["total_rows"],len(rows))
            self.assertFalse((output/"snapshot.json").exists())
            self.assertNotIn("records",saved)

    def test_dsn_not_leaked_in_error(self):
        bad="password-in-exception"
        with patch.dict("os.environ",{
            "NEON_HISTORICAL_READ_DATABASE_URL": GOOD},clear=True):
            with patch.object(bridge,"fetch_staging_history",
                              side_effect=RuntimeError(bad)):
                logs=StringIO()
                with redirect_stderr(logs):
                    self.assertEqual(bridge.main(),2)
        self.assertEqual(logs.getvalue().strip(),
                         "LEGACY_HISTORY_RESEARCH_FAILED: RuntimeError")
        self.assertNotIn(bad,logs.getvalue())
        self.assertNotIn("synthetic-test-password",logs.getvalue())


if __name__=="__main__":
    unittest.main()
