"""Synthetic integrity tests only. No network or account access."""
import json
from unittest import TestCase
from scripts.coinbase_public_hourly_research import SourceError,parse_ohlcv

BEGIN=1791936000

def fixture(change=None):
    rows=[{"start":str(BEGIN+i*3600),"open":"100","high":"102",
           "low":"99","close":"101","volume":"1.5"} for i in range(48)]
    if change=="missing":rows.pop(10)
    if change=="duplicate":rows[22]["start"]=rows[21]["start"]
    if change=="bad_ohlc":rows[5]["low"]="103"
    rows.append({"start":str(BEGIN+48*3600),"open":"100","high":"102",
                 "low":"99","close":"101","volume":"1.5"})
    return json.dumps({"candles":rows}).encode()

class CoinbasePublicHourlySourceTests(TestCase):
    def test_full_48_hours_plus_exclusive_end_boundary(self):
        x=parse_ohlcv(fixture(),"BTC-USD",BEGIN,BEGIN+48*3600)
        self.assertEqual(x["expected_hours"],48)
        self.assertEqual(x["validated_candles"],48)
        self.assertFalse(x["historical_as_published_pit_certified"])
        self.assertFalse(x["tradeable_fill_verified"])

    def test_bad_records_fail_closed(self):
        for bad in ("missing","duplicate","bad_ohlc"):
            with self.subTest(bad=bad):
                with self.assertRaises(SourceError):
                    parse_ohlcv(fixture(bad),"ETH-USD",BEGIN,BEGIN+48*3600)

    def test_single_price_change_modifies_source_identity(self):
        original=fixture()
        newer=json.loads(original)
        newer["candles"][10]["close"]="100.5"
        a=parse_ohlcv(original,"BTC-USD",BEGIN,BEGIN+48*3600)
        b=parse_ohlcv(json.dumps(newer).encode(),"BTC-USD",BEGIN,BEGIN+48*3600)
        self.assertNotEqual(a["canonical_ohlcv_sha256"],b["canonical_ohlcv_sha256"])

    def test_unknown_product_and_untrusted_format(self):
        with self.assertRaises(SourceError):
            parse_ohlcv(fixture(),"SOL-USD",BEGIN,BEGIN+48*3600)
        with self.assertRaises(SourceError):
            parse_ohlcv(b"<html>missing</html>","ETH-USD",BEGIN,BEGIN+48*3600)
