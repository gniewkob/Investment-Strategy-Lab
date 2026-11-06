"""Synthetic-only NAV USD * exact-date NBP FX provenance regression."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import unittest

from scripts.vanguard_nav_to_pln_reference_v04 import match_official_nav_to_fx
from tests.test_reference_archive_calendar_v04 import sample


def fixture(months=36):
    nbp, _ = sample(months,mismatches=0)
    nbp["series_contract"]={
        "usdpln":{"instrument_code":"USDPLN_NBP","return_basis":"FX_RATE"},
        "eurpln":{"instrument_code":"EURPLN_NBP","return_basis":"FX_RATE"},
        "gold":{"instrument_code":"GOLD_NBP_PLN_G","return_basis":"PRICE_ONLY"},
    }
    from scripts.reference_archive_calendar_v04 import _digest
    nbp["evidence_sha256"] = _digest({k:v for k,v in nbp.items()
                                       if k!="evidence_sha256"})
    monthly=[]
    csv_rows=["date,nav_usd"]
    for i, nbp_row in enumerate(nbp["monthly_observations"]["usdpln"]):
        nav=str(100+i)
        monthly.append({"month":nbp_row["month"],
                        "observed_for":nbp_row["observed_for"],"nav_usd":nav})
        csv_rows.append(f'{nbp_row["observed_for"]},{nav}')
    original=("\n".join(csv_rows)+"\n").encode("utf-8")
    nav={
        "source":"VANGUARD_OFFICIAL_NAV_USD_ACC",
        "isin":"IE00BK5BQT80",
        "quote_currency":"USD",
        "basis":"ACCUMULATING_FUND_NAV_USD",
        "instrument_kind":"NON_EXECUTABLE_NAV_REFERENCE",
        "historical_vintage_verified":False,
        "historical_first_publication_verified":False,
        "source_url":"https://www.ch.vanguard/en/private-investor/product/fund/equity/9679/ftse-all-world-ucits-etf-usd-accumulating",
        "retrieved_at":"2026-11-06T15:00:00Z",
        "raw_export_sha256":sha256(original).hexdigest(),
        "raw_file_format":"CSV_DATE_NAV_USD_V1",
        "monthly":monthly,
    }
    return nav,original,nbp


class NAVUSDPLNSourceTests(unittest.TestCase):
    def test_thirty_six_months_strict_reference_not_execution_price(self):
        nav,raw,nbp=fixture()
        result=match_official_nav_to_fx(nav,raw,nbp)
        self.assertEqual(result["calendar_months"],36)
        self.assertEqual(result["series_name"],"VANGUARD_ACC_NAV_REFERENCE_PLN")
        self.assertEqual(result["observations"][0]["nav_reference_pln"],
                         "10000")
        self.assertEqual(result["observations"][-1]["nav_reference_pln"],
                         "18225")
        self.assertEqual(result["source_nav_sha256"],sha256(raw).hexdigest())
        self.assertTrue(all(r["observed_for"] ==
                         nbp["monthly_observations"]["usdpln"][i]["observed_for"]
                         for i,r in enumerate(result["observations"])))
        self.assertFalse(result["historical_pit_certified"])
        self.assertFalse(result["mapped_to_GLOBAL_EQUITY_TR_PLN"])
        self.assertFalse(result["trading_fill_prices_verified"])
        self.assertEqual(result["real_backtest"],"NOT_RUN_SOURCE_REFERENCE_ONLY")
        self.assertEqual(result["financial_operations"],0)
        self.assertEqual(result["paper_events_created"],0)
        self.assertEqual(result,match_official_nav_to_fx(
            deepcopy(nav),raw,deepcopy(nbp)))

    def test_manifest_value_cannot_disagree_with_original_export_bytes(self):
        nav,raw,nbp=fixture()
        nav["monthly"][2]["nav_usd"]="999"
        with self.assertRaisesRegex(ValueError,"cannot be reproduced"):
            match_official_nav_to_fx(nav,raw,nbp)

    def test_manifest_date_cannot_disagree_with_raw_daily_rows(self):
        nav,raw,nbp=fixture()
        nav["monthly"][1]["observed_for"]="2021-12-27"
        with self.assertRaisesRegex(ValueError,"cannot be reproduced"):
            match_official_nav_to_fx(nav,raw,nbp)

    def test_corrupted_bytes_or_forged_digest_blocked(self):
        nav,raw,nbp=fixture()
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            match_official_nav_to_fx(nav,raw.replace(b"2021-11",b"2020-11"),nbp)
        nav,raw,nbp=fixture()
        nav["raw_export_sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            match_official_nav_to_fx(nav,raw,nbp)

    def test_incomplete_actual_nav_format_is_not_fake_verified_csv(self):
        nav,raw,nbp=fixture()
        nav["raw_file_format"]="XLSX"
        with self.assertRaisesRegex(ValueError,"not independently parsed"):
            match_official_nav_to_fx(nav,raw,nbp)
        nav,raw,nbp=fixture()
        invalid=b"PK\x03\x04some made-up Excel bytes"
        nav["raw_export_sha256"]=sha256(invalid).hexdigest()
        with self.assertRaisesRegex(ValueError,"CSV header"):
            match_official_nav_to_fx(nav,invalid,nbp)

    def test_exact_fx_date_is_required_no_forward_fill(self):
        nav,raw,nbp=fixture()
        nbp["monthly_observations"]["usdpln"][2]["observed_for"]="2022-01-27"
        from scripts.reference_archive_calendar_v04 import _digest
        nbp["evidence_sha256"]=_digest({k:v for k,v in nbp.items()
                                         if k!="evidence_sha256"})
        with self.assertRaisesRegex(ValueError,"EXACT_DATE_FX_MISSING"):
            match_official_nav_to_fx(nav,raw,nbp)

    def test_wrong_fx_basis_or_fake_NBP_receipt_rejected(self):
        nav,raw,nbp=fixture()
        nbp["series_contract"]["usdpln"]["return_basis"]="PRICE_ONLY"
        with self.assertRaisesRegex(ValueError,"official FX_RATE"):
            match_official_nav_to_fx(nav,raw,nbp)
        nav,raw,nbp=fixture()
        nbp["monthly_observations"]["usdpln"][0]["source_url"]="https://fake.example/a"
        from scripts.reference_archive_calendar_v04 import _digest
        nbp["evidence_sha256"]=_digest({k:v for k,v in nbp.items()
                                         if k!="evidence_sha256"})
        with self.assertRaisesRegex(ValueError,"source receipt"):
            match_official_nav_to_fx(nav,raw,nbp)

    def test_short_history_and_source_identity_rejected(self):
        nav,raw,nbp=fixture()
        nav["monthly"]=nav["monthly"][:-1]
        with self.assertRaisesRegex(ValueError,"36-72"):
            match_official_nav_to_fx(nav,raw,nbp)
        nav,raw,nbp=fixture()
        nav["source_url"]="https://faux-vanguard.example/price"
        with self.assertRaisesRegex(ValueError,"official Vanguard"):
            match_official_nav_to_fx(nav,raw,nbp)
        nav,raw,nbp=fixture()
        nav["historical_vintage_verified"]=True
        with self.assertRaisesRegex(ValueError,"vintage"):
            match_official_nav_to_fx(nav,raw,nbp)

    def test_csv_duplicate_and_missing_dates_rejected(self):
        nav,raw,nbp=fixture()
        duplicate=raw+raw.splitlines()[1]+b"\n"
        nav["raw_export_sha256"]=sha256(duplicate).hexdigest()
        with self.assertRaisesRegex(ValueError,"duplicated"):
            match_official_nav_to_fx(nav,duplicate,nbp)
        nav,raw,nbp=fixture()
        absent=b"\n".join(raw.splitlines()[:-1])+b"\n"
        nav["raw_export_sha256"]=sha256(absent).hexdigest()
        with self.assertRaisesRegex(ValueError,"absent from original export"):
            match_official_nav_to_fx(nav,absent,nbp)


if __name__ == "__main__":
    unittest.main()
