"""Reconciliation of two official monthly reference families; no trading."""
import copy
from datetime import date
import unittest

from scripts.reference_archive_calendar_v04 import _digest, reconcile
from scripts.nbp_bondspot_exact_date_v04 import match
from datetime import datetime, timezone
from urllib.parse import urlsplit
import json


def sample(months=36, mismatches=2):
    nbp = {"source": "NBP_OFFICIAL_API",
           "data_kind": "NON_EXECUTABLE_REFERENCE_ONLY",
           "first_month": "2021-11",
           "calendar_months": months,
           "historical_vintage_verified": False,
           "source_windows": [],
           "monthly_observations": {"usdpln": [], "eurpln": [], "gold": []}}
    bond = {"source": "BONDSPOT_OFFICIAL_ARCHIVE",
            "identity": "TBSP.Index",
            "return_basis": "BOND_TOTAL_RETURN_BENCHMARK_INDEX",
            "instrument_kind": "NON_TRADABLE_INDEX",
            "historical_first_available_verified": False,
            "months": months, "first_month": "2021-11", "monthly": []}
    for i in range(months):
        year = 2021 + (10 + i) // 12
        m = (10 + i) % 12 + 1
        month = f"{year:04d}-{m:02d}"
        day = date(year, m, 28)
        nbp_url = f"https://api.nbp.pl/api/exchangerates/tables/a/{month}-01/{month}-28/?format=json"
        gold_url = f"https://api.nbp.pl/api/cenyzlota/{month}-01/{month}-28/?format=json"
        nbp["source_windows"].append({
            "from": day.replace(day=1).isoformat(),
            "to": day.isoformat(),
            "receipts": {
                "fx": {"url": nbp_url, "sha256": "a" * 64,
                       "retrieved_at": "2026-11-06T14:00:00Z"},
                "gold": {"url": gold_url, "sha256": "b" * 64,
                         "retrieved_at": "2026-11-06T14:00:01Z"},
            },
        })
        for key in ("usdpln", "eurpln", "gold"):
            kind = "gold" if key == "gold" else "fx"
            r = nbp["source_windows"][-1]["receipts"][kind]
            nbp["monthly_observations"][key].append({
                "month": month, "observed_for": day.isoformat(),
                "value": str(100+i), "source_url": r["url"],
                "raw_sha256": r["sha256"], "retrieved_at": r["retrieved_at"],
            })
        close_date = day.replace(day=27) if i < mismatches else day
        bond["monthly"].append({
            "month": month, "observed_for": close_date.isoformat(),
            "value": str(1800+i),
            "source_url": ("https://www.bondspot.pl/tbsp_index_archive_en"
                           f"?date={close_date:%Y%m%d}&month={close_date:%m}"
                           f"&year={close_date:%Y}"),
            "raw_sha256": "c" * 64,
            "quote_currency": "PLN",
            "return_basis": "BOND_TOTAL_RETURN_BENCHMARK_INDEX",
            "instrument_kind": "NON_TRADABLE_INDEX",
        })
    nbp["last_month"] = bond["last_month"] = month
    nbp["evidence_sha256"] = _digest(nbp)
    bond["evidence_sha256"] = _digest(bond)
    return nbp, bond


class ReferenceArchiveCalendarTests(unittest.TestCase):
    def test_all_months_retained_without_fabricating_simultaneous_dates(self):
        n, b = sample(60, mismatches=5)
        result = reconcile(n, b)
        self.assertEqual(result["months"], 60)
        self.assertEqual(result["same_calendar_date_months"], 55)
        self.assertEqual(result["different_calendar_date_months"], 5)
        self.assertEqual(len(result["different_date_months"]), 5)
        self.assertEqual(result["timeline"][0]["observed_for"]["tbsp"],
                         "2021-11-27")
        self.assertNotEqual(result["timeline"][0]["observed_for"]["tbsp"],
                            result["timeline"][0]["observed_for"]["usdpln"])
        self.assertEqual(result["timeline"][-1]["calendar_date_match_status"],
                         "MATCHING_CALENDAR_DATE_NOT_PIT_CERTIFIED")
        self.assertEqual(result["backtest_status"],
                         "NOT_RUN_MISSING_OFFICIAL_NAV_AND_EXECUTION_EVIDENCE")
        self.assertEqual(result["financial_operations"], 0)
        self.assertEqual(result["paper_events_created"], 0)
        self.assertEqual(result, reconcile(copy.deepcopy(n), copy.deepcopy(b)))

    def test_source_value_tamper_without_rehash_fails(self):
        n, b = sample()
        n["monthly_observations"]["gold"][0]["value"] = "999"
        with self.assertRaisesRegex(ValueError, "evidence SHA-256 mismatch"):
            reconcile(n, b)

    def test_source_origin_forgery_with_rehash_fails(self):
        n, b = sample()
        b["monthly"][0]["source_url"] = "https://forged.example/quote"
        b["evidence_sha256"] = _digest({k:v for k,v in b.items()
                                         if k != "evidence_sha256"})
        with self.assertRaisesRegex(ValueError, "source origin"):
            reconcile(n, b)

    def test_bondspot_wrong_day_even_when_hash_updated_is_blocked(self):
        n,b = sample()
        b["monthly"][0]["source_url"] = b["monthly"][0]["source_url"].replace(
            "date=20211127", "date=20211126")
        b["evidence_sha256"] = _digest({k:v for k,v in b.items()
                                         if k != "evidence_sha256"})
        with self.assertRaisesRegex(ValueError, "closing-price source evidence"):
            reconcile(n, b)

    def test_nbps_must_match_original_source_receipt(self):
        n,b = sample()
        n["monthly_observations"]["usdpln"][0]["raw_sha256"] = "d" * 64
        n["evidence_sha256"] = _digest({k:v for k,v in n.items()
                                         if k != "evidence_sha256"})
        with self.assertRaisesRegex(ValueError, "no unique authentic source receipt"):
            reconcile(n,b)

    def test_missing_month_and_short_history_block_early(self):
        n,b = sample()
        b["monthly"].pop()
        b["months"] -= 1
        b["last_month"] = b["monthly"][-1]["month"]
        b["evidence_sha256"] = _digest({k:v for k,v in b.items()
                                         if k != "evidence_sha256"})
        with self.assertRaises(ValueError):
            reconcile(n,b)
        n,b = sample(35)
        with self.assertRaisesRegex(ValueError, "36-72"):
            reconcile(n,b)

    def test_no_claim_of_executable_tradability_or_historical_pit(self):
        n,b = sample()
        n["historical_vintage_verified"] = True
        n["evidence_sha256"] = _digest({k:v for k,v in n.items()
                                         if k != "evidence_sha256"})
        with self.assertRaisesRegex(ValueError, "self-certify"):
            reconcile(n,b)
        n,b=sample()
        b["instrument_kind"]="TRADABLE_PRICE"
        b["evidence_sha256"] = _digest({k:v for k,v in b.items()
                                         if k != "evidence_sha256"})
        with self.assertRaisesRegex(ValueError, "source identity"):
            reconcile(n,b)


def official_day_stub(url):
    parts = urlsplit(url).path.strip("/").split("/")
    day = parts[-1]
    if parts[-2] != day:
        raise ValueError("test fixture only accepts single-day official source")
    if "cenyzlota" in url:
        return json.dumps([{"data": day, "cena": "250.01"}]).encode()
    return json.dumps([{
        "table": "A", "no": "001/A/NBP/2021", "effectiveDate": day,
        "rates": [{"code": "USD", "mid": "4.11"},
                  {"code": "EUR", "mid": "4.55"}],
    }]).encode()


class ExactDateNBPResearchTests(unittest.TestCase):
    def test_five_unaligned_months_can_be_repaired_with_exact_day_sources(self):
        n,b = sample(60, mismatches=5)
        stamp = datetime(2026, 11, 6, 14, tzinfo=timezone.utc)
        result = match(n,b,fetch=official_day_stub,clock=lambda:stamp)
        self.assertEqual(result["months"], 60)
        self.assertEqual(result["official_exact_day_retrieval_count"], 5)
        self.assertEqual(result["source_request_count"], 10)
        self.assertEqual(result["original_mismatches"],
                         [x["month"] for x in b["monthly"][:5]])
        self.assertTrue(all(x["same_calendar_date"] for x in result["timeline"]))
        self.assertEqual(result["timeline"][0]["reference_date"], "2021-11-27")
        self.assertEqual(result["timeline"][0]["nbp"]["usdpln"]["observed_for"],
                         "2021-11-27")
        self.assertEqual(result["timeline"][0]["nbp"]["gold"]["value"], "250.01")
        self.assertEqual(result["timeline"][-1]["nbp"]["gold"]["alignment"],
                         "MONTHLY_NBP_SAME_DATE_AS_TBSP")
        self.assertFalse(result["historical_publication_hour_verified"])
        self.assertFalse(result["historical_vintage_verified"])
        self.assertFalse(result["investable_security_price_verified"])
        self.assertEqual(result["paper_events_created"], 0)
        self.assertEqual(result["financial_operations"], 0)
        self.assertTrue(result["backtest"].startswith("NOT_RUN"))
        self.assertEqual(result,match(n,b,fetch=official_day_stub,clock=lambda:stamp))

    def test_no_source_imputation_if_exact_bondspot_date_missing(self):
        n,b = sample()
        def fail_gold(url):
            if "cenyzlota" in url:
                return b"[]"
            return official_day_stub(url)
        with self.assertRaisesRegex(ValueError, "empty or invalid response"):
            match(n,b,fetch=fail_gold,
                  clock=lambda:datetime(2026,11,6,tzinfo=timezone.utc))

    def test_matching_months_do_not_trigger_redundant_network_calls(self):
        n,b = sample(36,mismatches=0)
        def no_network(url):
            raise AssertionError("not needed")
        result=match(n,b,fetch=no_network)
        self.assertEqual(result["source_request_count"],0)
        self.assertEqual(result["official_exact_day_retrieval_count"],0)
        self.assertTrue(all(row["same_calendar_date"] for row in result["timeline"]))

    def test_existing_source_tampering_is_rejected_before_http(self):
        n,b = sample()
        b["monthly"][0]["value"]="9999"
        with self.assertRaisesRegex(ValueError,"evidence SHA-256 mismatch"):
            match(n,b,fetch=official_day_stub)


if __name__ == "__main__":
    unittest.main()
