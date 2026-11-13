"""Cross-provider evidence never upgrades source qualification."""
import unittest
from datetime import datetime,timezone
from copy import deepcopy
from scripts.research_readiness_quality_v07 import compose_source_readiness,ResearchEvidenceBlocked

NOW=datetime(2026,11,13,12,tzinfo=timezone.utc)
SHA="a"*64

def evidence():
    return (
        {"schema":"ISL_UKNF_ONE_CLASS_DESCRIPTIVE_NAV_QUALITY_V07",
         "same_unit_primary_pln":True,"nav_distribution_adjusted_return":False,
         "historical_first_publication_proven":False,"asset_return_series_admitted":[],
         "financial_operations":0,"source_history_sha256":SHA,"distinct_valuation_days":22},
        {"schema":"ISL_MF_OFFICIAL_SECONDARY_TREASURY_SCHEMA_AUDIT_V07",
         "state":"ORIGINAL_WORKBOOK_SCHEMA_ONLY_NO_TURNOVER_ADMISSION",
         "turnover_units_validated":False,"historical_first_publication_proven":False,
         "bond_total_return_observed":False,"source_data_rows_in_report":0,
         "financial_operations":0,"sha256":SHA},
    )

class ReadinessTests(unittest.TestCase):
    def test_unqualified_two_source_readiness(self):
        n,m=evidence()
        d=compose_source_readiness(nav_quality=n,mf_schema=m,observed_at=NOW)
        self.assertEqual(d["source_families"],2)
        self.assertFalse(d["historical_pit_admitted"])
        self.assertFalse(d["live_execution_authorized"])
        self.assertEqual(d["asset_total_return_qualified"],[])
        self.assertEqual(d["m1_m2_m3"],"INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual(d["financial_operations"],0)
        self.assertEqual(d["outbound_source_reads"],0)
    def test_invalid_nav_provenance_blocks(self):
        n,m=evidence()
        n["source_history_sha256"]="not-a-hash"
        with self.assertRaises(ResearchEvidenceBlocked):
            compose_source_readiness(nav_quality=n,mf_schema=m,observed_at=NOW)
    def test_nav_cannot_claim_pit(self):
        n,m=evidence()
        n["historical_first_publication_proven"]=True
        with self.assertRaisesRegex(ResearchEvidenceBlocked,"NAV_QUALITY"):
            compose_source_readiness(nav_quality=n,mf_schema=m,observed_at=NOW)
    def test_nav_cannot_promote_asset_total_return(self):
        n,m=evidence()
        n["asset_return_series_admitted"]=["PL_BONDS_TR_PLN"]
        with self.assertRaisesRegex(ResearchEvidenceBlocked,"NAV_QUALITY"):
            compose_source_readiness(nav_quality=n,mf_schema=m,observed_at=NOW)
    def test_mf_cannot_claim_unverified_units(self):
        n,m=evidence()
        m["turnover_units_validated"]=True
        with self.assertRaisesRegex(ResearchEvidenceBlocked,"MF_ORIGINAL"):
            compose_source_readiness(nav_quality=n,mf_schema=m,observed_at=NOW)
    def test_mf_cannot_reclassify_bonds_total_return(self):
        n,m=evidence()
        m["bond_total_return_observed"]=True
        with self.assertRaisesRegex(ResearchEvidenceBlocked,"MF_ORIGINAL"):
            compose_source_readiness(nav_quality=n,mf_schema=m,observed_at=NOW)
    def test_naive_clock_blocks(self):
        n,m=evidence()
        with self.assertRaisesRegex(ResearchEvidenceBlocked,"UTC_AWARE"):
            compose_source_readiness(nav_quality=n,mf_schema=m,observed_at=datetime(2026,11,13))
    def test_absent_macro_source_is_explicit_not_fabricated(self):
        n,m=evidence()
        d=compose_source_readiness(nav_quality=n,mf_schema=m,macro_reference=None,observed_at=NOW)
        self.assertEqual(len(d["source_readiness"]),2)
    def test_wrong_macro_series_denied(self):
        n,m=evidence()
        fake={"schema":"ISL_PUBLIC_MULTISOURCE_MACRO_EVIDENCE_V05",
              "historical_point_in_time_certified":False,
              "source_rights_fully_approved":False,
              "asset_total_return_series_qualified":[],
              "financial_operations":0,
              "hicp_months":13,"government_yield_months":59,
              "source_fingerprints_sha256":{"nbp_gold":SHA},
              "receipt_sha256":SHA}
        with self.assertRaisesRegex(ResearchEvidenceBlocked,"MACRO_SOURCE"):
            compose_source_readiness(nav_quality=n,mf_schema=m,macro_reference=fake,observed_at=NOW)
    def test_no_data_values_or_fund_ids_exposed(self):
        n,m=evidence()
        s=str(compose_source_readiness(nav_quality=n,mf_schema=m,observed_at=NOW))
        self.assertNotIn("fundId",s)
        self.assertNotIn("value_at_risk",s)
