"""Offline deterministic tests. No DB, account secrets, or financial execution."""
from datetime import datetime, timedelta, timezone
from io import StringIO
from contextlib import redirect_stderr
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import opportunity_radar as radar

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
INGESTED = "2026-10-17T20:00:00Z"
AS_OF = "2026-10-18T20:00:00Z"


def rows(code="BTC-USD", count=100, shock_index=80, *, interval="1d"):
    data = []
    px = 100.0
    for i in range(count):
        if i:
            change = (0.004 if i % 2 else -0.003)
            if i == shock_index:
                change = 0.18
            px *= 1+change
        date = START + timedelta(days=i if interval=="1d" else 30*i)
        data.append({"instrument_code":code,"interval_code":interval,
                     "return_basis":"PRICE_ONLY",
                     "observed_for":date.isoformat(),
                     "ingested_at":INGESTED,
                     "close_price":str(round(px,8))})
    return data


def payload(records):
    return {"mode":"RETROSPECTIVE_RESEARCH_ONLY",
            "source_vintage":"UNVERIFIED_HISTORICAL_PUBLICATION",
            "as_of":AS_OF,"records":records}


class RetrospectiveRadarTests(unittest.TestCase):
    def test_shock_detected_from_past_only(self):
        result=radar.analyze(payload(rows()))
        series=result["series"][0]
        self.assertEqual(result["series_analyzed"],1)
        self.assertGreaterEqual(series["shock_samples"],1)
        self.assertIn("2026-03-22", [s["observed_for"][:10] for s in series["signals"]])
        self.assertEqual(result["decision_classification"],"INVESTIGATE_OR_OBSERVE_ONLY")
        self.assertFalse(result["pit_backtest_certified"])
        self.assertEqual(result["virtual_portfolio_changes"],0)
        self.assertEqual(result["real_orders"],0)

    def test_changing_future_bars_cannot_change_earlier_signal(self):
        first = rows()
        second = [dict(v) for v in first]
        # 80th bar is a signal, later bars must not modify its zscore.
        for i in range(86, len(second)):
            second[i]["close_price"] = str(float(second[i]["close_price"])*1.22)
        a=radar.analyze(payload(first))["series"][0]["signals"]
        b=radar.analyze(payload(second))["series"][0]["signals"]
        left={x["observed_for"]:x for x in a}
        right={x["observed_for"]:x for x in b}
        event="2026-03-22T00:00:00+00:00"
        self.assertIn(event,left)
        self.assertIn(event,right)
        self.assertEqual(left[event]["absolute_zscore"],right[event]["absolute_zscore"])
        self.assertEqual(left[event]["direction"],right[event]["direction"])
        self.assertEqual(left[event]["forward_reference_change_pct"],
                         right[event]["forward_reference_change_pct"])

    def test_repeatable_fingerprint_and_research_report(self):
        example=payload(rows())
        a,b=radar.analyze(example),radar.analyze(example)
        self.assertEqual(a,b)
        self.assertEqual(len(a["data_sha256"]),64)
        report=radar.markdown_report(a)
        self.assertIn("INVESTIGATE",report.lower().upper())
        self.assertIn("unverified", report)
        self.assertNotIn("buy now", report.lower())

    def test_rejects_missing_unverified_vintage_marker(self):
        q=payload(rows())
        q["source_vintage"]="VERIFIED_PIT"
        with self.assertRaises(ValueError):
            radar.analyze(q)
        q["source_vintage"]="UNVERIFIED_HISTORICAL_PUBLICATION"
        q.pop("mode")
        with self.assertRaises(ValueError):
            radar.analyze(q)

    def test_future_dated_observations_and_ingestion_fail_closed(self):
        q=payload(rows())
        q["records"][0]["ingested_at"]="2026-10-20T10:00:00Z"
        with self.assertRaises(ValueError):
            radar.analyze(q)
        q=payload(rows())
        q["records"][-1]["observed_for"]="2026-10-19T00:00:00Z"
        with self.assertRaises(ValueError):
            radar.analyze(q)

    def test_timestamp_unaware_and_unordered_ingestion_rejected(self):
        q=payload(rows())
        q["records"][0]["ingested_at"]="2026-10-17T20:00:00"
        with self.assertRaises(ValueError):
            radar.analyze(q)
        q=payload(rows())
        q["records"][0]["ingested_at"]="2025-01-01T00:00:00Z"
        with self.assertRaises(ValueError):
            radar.analyze(q)

    def test_duplicate_observation_rejected(self):
        record=rows()
        with self.assertRaises(ValueError):
            radar.analyze(payload(record+[dict(record[0])]))

    def test_wrong_basis_unknown_series_and_nonpositive_price_rejected(self):
        q=payload(rows())
        q["records"][0]["return_basis"]="TOTAL_RETURN_INDEX"
        with self.assertRaises(ValueError):
            radar.analyze(q)
        q=payload(rows())
        q["records"][0]["instrument_code"]="FAKE_ETF"
        with self.assertRaises(ValueError):
            radar.analyze(q)
        q=payload(rows())
        q["records"][0]["close_price"]="0"
        with self.assertRaises(ValueError):
            radar.analyze(q)

    def test_short_series_stays_excluded(self):
        r=radar.analyze(payload(rows(count=20)))
        self.assertEqual(r["series_analyzed"],0)
        self.assertEqual(r["insufficient_series"],["BTC-USD/1d"])
        self.assertEqual(r["real_orders"],0)

    def test_usd_crypto_divergence_requires_matched_dates(self):
        both=rows("BTC-USD")+rows("ETH-USD",shock_index=75)
        result=radar.analyze(payload(both))["cross_market_btc_eth"]
        self.assertEqual(result["matched_observations"],100)
        self.assertEqual(result["status"],"RETROSPECTIVE_UNVERIFIED_VINTAGE")
        self.assertGreaterEqual(len(result["recent_divergence_events"]),1)
        self.assertTrue(result["no_arbitrage_or_trade_inference"])

    def test_only_one_crypto_cannot_create_divergence(self):
        r=radar.analyze(payload(rows()))["cross_market_btc_eth"]
        self.assertEqual(r["status"],"INSUFFICIENT_MATCHED_HISTORY")
        self.assertFalse(r["recent_divergence_events"])

    def test_mixed_frequency_never_blended(self):
        r=radar.analyze(payload(rows("BTC-USD",count=60,shock_index=45)+
                                rows("COPPER_WB_USD_T",count=9,interval="1mo")))
        self.assertEqual(r["series_analyzed"],1)
        self.assertIn("COPPER_WB_USD_T/1mo",r["insufficient_series"])

    def test_json_artifact_contains_no_private_connection_or_orders(self):
        with TemporaryDirectory() as folder:
            src=Path(folder)/"source.json"
            out=Path(folder)/"output"
            src.write_text(json.dumps(payload(rows())))
            with patch("sys.argv",["radar","--input",str(src),"--out-dir",str(out)]):
                self.assertEqual(radar.main(),0)
            result=json.loads((out/"radar.json").read_text())
            markdown=(out/"report.md").read_text()
            self.assertEqual(result["database_writes"],0)
            self.assertEqual(result["real_orders"],0)
            self.assertIn("retrospective",markdown.lower())
            self.assertFalse(result["pit_backtest_certified"])

    def test_exceptions_do_not_leak_input_content(self):
        with TemporaryDirectory() as folder:
            src=Path(folder)/"bad.json"
            src.write_text("secret-never-log")
            log=StringIO()
            with patch("sys.argv",["radar","--input",str(src)]):
                with redirect_stderr(log):
                    self.assertEqual(radar.main(),2)
            self.assertNotIn("secret-never-log",log.getvalue())
            self.assertIn("OPPORTUNITY_RADAR_FAILED",log.getvalue())


if __name__=="__main__":
    unittest.main()
