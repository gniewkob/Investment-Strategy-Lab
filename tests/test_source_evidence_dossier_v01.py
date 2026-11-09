"""I5 independent synthetic-source gap audit; never use actual vendor data."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
import json
import tempfile
import unittest

from scripts.acwi_netr_offline_intake_v19 import audit as audit_msci
from scripts.real_reference_gateway_v18 import evaluate_reference
from scripts.source_evidence_dossier_v01 import (
    EvidenceDossierError, assess_dossier, _read_bounded, _digest, EVIDENCE_GAPS,
)
from scripts.vanguard_xlsx_offline_intake_v04 import inspect_export
from tests.test_acwi_netr_offline_intake_v19 import fixture as msci_fixture
from tests.test_real_reference_gateway_v18 import fixture as reference_fixture
from tests.test_vanguard_xlsx_offline_intake_v04 import fake_xlsx


def synthetic_reports():
    raw, fx = msci_fixture()
    return {
        "msci": audit_msci(raw, fx, as_of_utc="2026-11-07T16:00:00Z"),
        "vanguard": inspect_export(
            fake_xlsx(months=60), "2021-11", "2026-10",
            as_of=date(2026, 11, 7)),
        "reference": evaluate_reference(
            reference_fixture(), as_of_utc="2026-11-07T15:00:00Z"),
    }


def repin(record, key):
    record[key] = _digest({k: v for k, v in record.items() if k != key})
    return record


class SourceEvidenceDossierTests(unittest.TestCase):
    def assert_all_blocked(self, result):
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_REVIEW_REQUIRED")
        self.assertEqual(result["qualified_model_series"], [])
        self.assertEqual(result["paper_candidates"], [])
        self.assertFalse(result["source_manifest_created"])
        self.assertFalse(result["historical_point_in_time_certified"])
        self.assertFalse(result["source_rights_independently_certified"])
        self.assertFalse(result["market_execution_authorized"])
        self.assertFalse(result["integration_to_main_authorized"])
        self.assertTrue(all(
            m["status"] == "HOLD_CASH"
            and m["virtual_target"] == {"CASH_PLN": "1"}
            for m in result["model_decisions"].values()))
        for field in ("orders_sent", "paper_fills",
                      "financial_operations", "database_writes"):
            self.assertEqual(result[field], 0)
        self.assertEqual(len(result["asset_qualification"]), 3)
        for asset, gap in EVIDENCE_GAPS.items():
            self.assertEqual(result["asset_qualification"][asset][
                "required_independent_evidence"], gap)
            self.assertFalse(result["asset_qualification"][asset][
                "qualified_source_available"])

    def test_no_reports_means_all_candidates_and_models_blocked(self):
        result = assess_dossier({})
        self.assert_all_blocked(result)
        self.assertEqual(set(result["reports"]), {"msci", "vanguard", "reference"})
        self.assertTrue(all(r["status"] == "NO_REPORT_AVAILABLE"
                            for r in result["reports"].values()))

    def test_three_full_synthetic_audit_reports_are_internal_only(self):
        result = assess_dossier(synthetic_reports())
        self.assert_all_blocked(result)
        self.assertTrue(all(r["status"] == "INTERNAL_CONSISTENCY_ONLY"
                            for r in result["reports"].values()))
        self.assertEqual(result["reports"]["msci"]["reported_months"], 36)
        self.assertEqual(result["reports"]["vanguard"]["reported_months"], 60)
        self.assertEqual(result["reports"]["reference"]["reported_months"], 60)
        self.assertEqual(result["asset_qualification"][
            "GLOBAL_EQUITY_TR_PLN"]["candidate_audits_available"], ["msci", "vanguard"])

    def test_vanguard_nav_values_never_appear_in_dossier_output(self):
        reports = synthetic_reports()
        result = assess_dossier(reports)
        rendered = json.dumps(result)
        self.assertNotIn('"monthly":', rendered)
        self.assertNotIn('"nav_usd":', rendered)
        self.assertNotIn('"estimated_returns":', rendered)
        self.assertNotIn('"level_pln":', rendered)

    def test_no_input_mutation_and_deterministic_receipt(self):
        reports = synthetic_reports()
        original = deepcopy(reports)
        a = assess_dossier(reports)
        b = assess_dossier(deepcopy(reports))
        self.assertEqual(a, b)
        self.assertEqual(reports, original)
        self.assertEqual(a["dossier_sha256"], _digest({
            k: v for k, v in a.items() if k != "dossier_sha256"
        }))

    def test_single_source_families_never_promote_missing_assets(self):
        reports = synthetic_reports()
        for name in ("msci", "vanguard", "reference"):
            with self.subTest(name=name):
                out = assess_dossier({name: reports[name]})
                self.assert_all_blocked(out)

    def test_corrupt_upstream_receipts_rejected(self):
        reports = synthetic_reports()
        for name, key in (
            ("msci", "audit_receipt_sha256"),
            ("vanguard", "candidate_sha256"),
            ("reference", "gateway_receipt_sha256"),
        ):
            modified = deepcopy(reports[name])
            modified[key] = "0" * 64
            with self.subTest(name=name), self.assertRaisesRegex(
                    EvidenceDossierError, "receipt mismatch"):
                assess_dossier({name: modified})

    def test_self_certification_remains_blocked_even_with_rehashed_receipt(self):
        reports = synthetic_reports()
        for name, field, receipt in (
            ("msci", "original_export_rights_independently_verified",
             "audit_receipt_sha256"),
            ("msci", "source_currency_independently_verified",
             "audit_receipt_sha256"),
            ("msci", "eligible_M1", "audit_receipt_sha256"),
            ("vanguard", "usable_as_GLOBAL_EQUITY_TR_PLN", "candidate_sha256"),
            ("vanguard", "historical_pit_certified", "candidate_sha256"),
            ("reference", "source_licence_independently_certified",
             "gateway_receipt_sha256"),
            ("reference", "historical_pit_certified", "gateway_receipt_sha256"),
        ):
            modified = deepcopy(reports[name])
            modified[field] = True
            repin(modified, receipt)
            with self.subTest(name=name, field=field), self.assertRaises(
                    EvidenceDossierError):
                assess_dossier({name: modified})

    def test_incorrect_msci_currency_or_fx_conversion_rejected(self):
        record = synthetic_reports()["msci"]
        for field, value in (("claimed_currency", "USD"),
                             ("usd_pln_conversion_performed", True),
                             ("estimated_returns", [10])):
            changed = deepcopy(record)
            changed[field] = value
            repin(changed, "audit_receipt_sha256")
            with self.subTest(field=field), self.assertRaises(
                    EvidenceDossierError):
                assess_dossier({"msci": changed})

    def test_msci_fx_calendar_match_does_not_establish_currency_or_pit(self):
        raw, fx = msci_fixture()
        out = assess_dossier({
            "msci": audit_msci(raw, fx, as_of_utc="2026-11-07T16:00:00Z")
        })
        self.assertEqual(out["reports"]["msci"]["reported_months"], 36)
        self.assertFalse(out["reports"]["msci"]["source_currency_verified"])
        self.assertFalse(out["reports"]["msci"]["historical_pit_verified"])
        self.assert_all_blocked(out)

    def test_reference_index_cannot_be_relabelled_total_return(self):
        record = synthetic_reports()["reference"]
        for field, value in (
            ("qualified_total_return_model_series", ["PL_BONDS_TR_PLN"]),
            ("model_states", {"M1_GLOBAL_EQ": "PAPER_CANDIDATE_ONLY"}),
            ("candidate_models", ["M1_GLOBAL_EQ"]),
        ):
            modified = deepcopy(record)
            modified[field] = value
            repin(modified, "gateway_receipt_sha256")
            with self.subTest(field=field), self.assertRaisesRegex(
                    EvidenceDossierError, "promoted"):
                assess_dossier({"reference": modified})

    def test_extra_rights_or_pit_fields_are_rejected(self):
        for name, receipt in (("msci", "audit_receipt_sha256"),
                              ("vanguard", "candidate_sha256"),
                              ("reference", "gateway_receipt_sha256")):
            record = deepcopy(synthetic_reports()[name])
            record["independent_authorization_granted"] = True
            repin(record, receipt)
            with self.subTest(name=name), self.assertRaisesRegex(
                    EvidenceDossierError, "promotion fields"):
                assess_dossier({name: record})

    def test_rehashed_source_levels_are_not_tradable_and_not_disclosed(self):
        record = synthetic_reports()["vanguard"]
        record["monthly"][-1]["nav_usd"] = "99999999"
        repin(record, "candidate_sha256")
        out = assess_dossier({"vanguard": record})
        self.assert_all_blocked(out)
        self.assertNotIn("99999999", json.dumps(out))
        self.assertFalse(out["reports"]["vanguard"]["is_executable_quote"])

    def test_nonsequential_vanguard_months_rejected_even_if_rehashed(self):
        record = synthetic_reports()["vanguard"]
        record["monthly"][4]["month"] = record["monthly"][3]["month"]
        repin(record, "candidate_sha256")
        with self.assertRaisesRegex(EvidenceDossierError, "nonsequential"):
            assess_dossier({"vanguard": record})

    def test_mismatched_coverage_or_fake_zero_rejected(self):
        msci = synthetic_reports()["msci"]
        msci["same_date_nbp_fx_matches"] = True
        repin(msci, "audit_receipt_sha256")
        with self.assertRaisesRegex(EvidenceDossierError, "coverage"):
            assess_dossier({"msci": msci})
        reference = synthetic_reports()["reference"]
        reference["orders_sent"] = False
        repin(reference, "gateway_receipt_sha256")
        with self.assertRaisesRegex(EvidenceDossierError, "activity claimed"):
            assess_dossier({"reference": reference})

    def test_unknown_candidate_family_and_nonjson_data_rejected(self):
        with self.assertRaises(EvidenceDossierError):
            assess_dossier({"trade": {"authorized": True}})
        with self.assertRaises(EvidenceDossierError):
            assess_dossier({"msci": {"status": "ACCEPTED"}})
        with self.assertRaises(EvidenceDossierError):
            assess_dossier({"reference": float("nan")})

    def test_symlinked_or_oversized_metadata_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            input_file = base / "source.json"
            input_file.write_text("{}", encoding="utf-8")
            link = base / "linked.json"
            link.symlink_to(input_file)
            with self.assertRaisesRegex(EvidenceDossierError, "regular metadata"):
                _read_bounded(link)
            oversized = base / "oversized.json"
            oversized.write_bytes(b" " * 1_000_001)
            with self.assertRaisesRegex(EvidenceDossierError, "bounded regular"):
                _read_bounded(oversized)


if __name__ == "__main__":
    unittest.main()
