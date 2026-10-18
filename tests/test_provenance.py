import copy
import unittest
from src.isl_v2.provenance import utc, fingerprint, parse_observation, select_asof
from src.isl_v2.pipeline import run

BASE = {
  "instrument_code": "COPPER_WB_USD_T", "source_code": "wb_pink_monthly",
  "observed_for": "2026-09-30T00:00:00+00:00", "interval_code": "1mo",
  "revision_no": 1, "price_value": "14474", "value_concept": "MONTHLY_AVERAGE",
  "available_at": "2026-10-03T00:00:00+00:00",
  "document": {"canonical_url": "https://thedocs.worldbank.org/sample.pdf",
   "published_at": "2026-10-02T00:00:00+00:00", "publication_precision": "DAY",
   "sha256_hex": "a" * 64}
}

class ProvenanceTests(unittest.TestCase):
    def test_start_of_release_day_excluded(self):
        self.assertEqual(select_asof([BASE], "2026-10-02T00:00:00Z"), [])
    def test_end_of_release_day_excluded(self):
        self.assertEqual(select_asof([BASE], "2026-10-02T23:59:59Z"), [])
    def test_day_after_release_included(self):
        self.assertEqual(select_asof([BASE], "2026-10-03T00:00:00Z")[0]["price_value"], "14474")
    def test_revision_not_visible_before_later_release(self):
        rev = copy.deepcopy(BASE)
        rev["revision_no"] = 2
        rev["price_value"] = "14500"
        rev["available_at"] = "2026-11-04T00:00:00Z"
        rev["document"]["published_at"] = "2026-11-03T00:00:00Z"
        rev["document"]["sha256_hex"] = "b" * 64
        self.assertEqual(select_asof([BASE,rev], "2026-11-03T23:59:59Z")[0]["price_value"], "14474")
        self.assertEqual(select_asof([BASE,rev], "2026-11-04T00:00:00Z")[0]["price_value"], "14500")
    def test_missing_timezone(self):
        with self.assertRaises(ValueError): utc("2026-10-01T00:00:00")
    def test_negative_price(self):
        x = {**BASE, "price_value": "-2"}
        with self.assertRaises(ValueError): parse_observation(x)
    def test_nan(self):
        x = {**BASE, "price_value": "NaN"}
        with self.assertRaises(ValueError): parse_observation(x)
    def test_cannot_use_monthly_mean_as_daily_close(self):
        x = {**BASE, "value_concept": "DAILY_SPOT"}
        with self.assertRaises(ValueError): parse_observation(x)
    def test_invalid_document_hash(self):
        x = copy.deepcopy(BASE); x["document"]["sha256_hex"] = "junk"
        with self.assertRaises(ValueError): parse_observation(x)
    def test_reject_premature_availability(self):
        x = {**BASE, "available_at": "2026-10-02T10:00:00Z"}
        with self.assertRaises(ValueError): parse_observation(x)
    def test_reject_duplicate_revision(self):
        with self.assertRaises(ValueError): select_asof([BASE,BASE], "2026-10-09T00:00:00Z")
    def test_exact_timestamp_can_be_used_immediately(self):
        x=copy.deepcopy(BASE); x["document"]["publication_precision"]="EXACT"
        x["available_at"]="2026-10-02T00:00:00Z"
        self.assertEqual(len(select_asof([x],"2026-10-02T00:00:00Z")),1)
    def test_deterministic_fingerprint(self):
        self.assertEqual(fingerprint({"a": 1,"b": 2}),fingerprint({"b": 2,"a": 1}))
    def test_run_fingerprint_stable(self):
        job={"run_key":"fixture-2026-10-17", "pipeline_name":"offline_pit",
             "code_version":"s1", "as_of":"2026-10-03T00:00:00Z","observations":[BASE]}
        self.assertEqual(run(job),run(job))
        self.assertTrue(run(job)["no_live_execution"])
    def test_future_publication_absent(self):
        self.assertEqual(select_asof([BASE],"2026-09-30T23:59:59Z"),[])

if __name__ == "__main__": unittest.main()
