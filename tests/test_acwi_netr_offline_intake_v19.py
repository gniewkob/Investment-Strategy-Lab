"""v0.19 licensed-data offline intake: tests are synthetic, never MSCI market data."""
import calendar
from copy import deepcopy
from datetime import date
from hashlib import sha256
import unittest

from scripts.acwi_netr_offline_intake_v19 import audit
from scripts.shadow_decision_engine_v05 import ShadowInputError, _digest


def fixture(months=36, *, variant="NETR", match=True, missing=False):
    lines = ["Date,Code,Index name,Index variant,Index level"]
    fx = []
    for i in range(months):
        year = 2022 + i // 12
        month = i % 12 + 1
        day = date(year, month, calendar.monthrange(year, month)[1])
        lines.append(f"{day:%d/%m/%Y},00001,MSCI ACWI,{variant},{1000 + i * 5}")
        if not missing or i != 5:
            fx_day = day if match else date(year, month, 20)
            fx.append({"month": f"{year:04d}-{month:02d}",
                       "observed_for": fx_day.isoformat(),
                       "value": "4.00"})
    doc = {
        "source": "NBP_OFFICIAL_API",
        "data_kind": "NON_EXECUTABLE_REFERENCE_ONLY",
        "series_contract": {"usdpln": {"return_basis": "FX_RATE"}},
        "monthly_observations": {"usdpln": fx},
    }
    doc["evidence_sha256"] = _digest(doc)
    return ("\n".join(lines) + "\n").encode(), doc


class AcwiNetrV19Tests(unittest.TestCase):
    def test_36_month_synthetic_layout_reports_coverage_never_m1_eligible(self):
        raw, nbp = fixture()
        r = audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")
        self.assertEqual(r["monthly_observations"], 36)
        self.assertTrue(r["minimum_months_met"])
        self.assertTrue(r["same_date_fx_complete"])
        self.assertEqual(r["same_date_nbp_fx_matches"], 36)
        self.assertEqual(r["claimed_return_basis"], "NET_TOTAL_RETURN")
        self.assertEqual(r["original_csv_sha256"], sha256(raw).hexdigest())
        self.assertFalse(r["eligible_M1"])
        self.assertEqual(r["pln_tr_model_qualification"], "BLOCKED_UNVERIFIED_RIGHTS_AND_PIT")
        self.assertIsNone(r["estimated_returns"])
        self.assertFalse(r["original_export_rights_independently_verified"])
        self.assertFalse(r["historical_first_publication_independently_verified"])
        self.assertEqual(r["orders_sent"], 0)
        self.assertEqual(r["database_writes"], 0)

    def test_repeat_and_no_source_mutation(self):
        raw, nbp = fixture()
        snapshot = deepcopy(nbp)
        a = audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")
        b = audit(raw, deepcopy(nbp), as_of_utc="2026-11-07T16:00:00Z")
        self.assertEqual(a, b)
        self.assertEqual(nbp, snapshot)

    def test_missing_exact_day_fx_does_not_forward_fill(self):
        raw, nbp = fixture(missing=True)
        r = audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")
        self.assertEqual(r["same_date_nbp_fx_matches"], 35)
        self.assertEqual(r["same_date_nbp_fx_missing"], ["2022-06"])
        self.assertFalse(r["same_date_fx_complete"])

    def test_mismatched_dates_block_fx_join(self):
        raw, nbp = fixture(match=False)
        r = audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")
        self.assertEqual(r["same_date_nbp_fx_matches"], 0)
        self.assertFalse(r["same_date_fx_complete"])

    def test_less_than_36_months_is_not_complete(self):
        raw, nbp = fixture(months=35)
        r = audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")
        self.assertFalse(r["minimum_months_met"])
        self.assertFalse(r["eligible_M1"])

    def test_price_only_or_wrong_name_not_promoted(self):
        for value in ("STDR", "GRTR"):
            raw, nbp = fixture(variant=value)
            with self.subTest(value=value), self.assertRaisesRegex(
                    ShadowInputError, "series absent"):
                audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")
        raw, nbp = fixture()
        raw = raw.replace(b"MSCI ACWI", b"MSCI World")
        with self.assertRaisesRegex(ShadowInputError, "series absent"):
            audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")

    def test_corrupt_nbp_receipt_rejected(self):
        raw, nbp = fixture()
        nbp["monthly_observations"]["usdpln"][3]["value"] = "99"
        with self.assertRaisesRegex(ShadowInputError, "fingerprint mismatch"):
            audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")

    def test_gapped_months_fail_closed(self):
        raw, nbp = fixture()
        raw = raw.replace(b"30/06/2022,00001,MSCI ACWI,NETR,1025\n", b"")
        with self.assertRaisesRegex(ShadowInputError, "month gaps"):
            audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")

    def test_duplicate_record_rejected(self):
        raw, nbp = fixture()
        rows = raw.splitlines()
        raw = b"\n".join(rows + [rows[1]]) + b"\n"
        with self.assertRaisesRegex(ShadowInputError, "duplicate"):
            audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")

    def test_wrong_csv_format_rejected(self):
        raw, nbp = fixture()
        raw = raw.replace(b"Index level", b"Market price")
        with self.assertRaisesRegex(ShadowInputError, "headers"):
            audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")

    def test_future_dated_observation_rejected(self):
        raw, nbp = fixture()
        with self.assertRaisesRegex(ShadowInputError, "future"):
            audit(raw, nbp, as_of_utc="2023-01-01T00:00:00Z")

    def test_nonpositive_levels_rejected(self):
        raw, nbp = fixture()
        raw = raw.replace(b"NETR,1000", b"NETR,0")
        with self.assertRaisesRegex(ShadowInputError, "positive"):
            audit(raw, nbp, as_of_utc="2026-11-07T16:00:00Z")


if __name__ == "__main__":
    unittest.main()
