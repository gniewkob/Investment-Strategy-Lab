"""Synthetic-only reviewed source pin tests, no real source or market data."""
from dataclasses import asdict, replace
from hashlib import sha256
import unittest

from src.isl_v2.reviewed_source_registry import (
    SourceRegistryBlocked, ReviewedSourcePin, REVIEWED_SOURCE_PINS,
    _verify_with_reviewed_pin, registry_inventory, verify_registry_candidate,
    MAX_ARTIFACT_BYTES,
)

ARTIFACT = b"synthetic TOTAL RETURN index fixture: no market observations"
CAPTURE = "2026-10-10T14:00:00Z"
CUTOFF = "2026-10-17T07:00:00Z"


def pin_fixture():
    return ReviewedSourcePin(
        instrument_code="EQUITY_TR_PLN",
        source_code="test_publisher",
        official_series_id="test_TR_PLN",
        canonical_url="https://example.org/research/data.csv",
        license_url="https://example.org/research/license",
        source_version="v1",
        source_sha256=sha256(ARTIFACT).hexdigest(),
        first_public_at="2026-10-09T12:00:00Z",
    )


class ReviewedSourceRegistryTests(unittest.TestCase):
    def example(self, pin=None):
        pin = pin or pin_fixture()
        return asdict(pin)

    def check(self, pin=None, claimed=None, artifact=ARTIFACT, captured_at=CAPTURE,
              decision_asof=CUTOFF):
        pin = pin or pin_fixture()
        return _verify_with_reviewed_pin(
            pin, claimed if claimed is not None else self.example(pin), artifact,
            captured_at=captured_at, decision_asof=decision_asof
        )

    def blocked(self, reason, **kwargs):
        with self.assertRaisesRegex(SourceRegistryBlocked, reason):
            self.check(**kwargs)

    def test_production_registry_is_empty_and_no_paper_source_is_authorized(self):
        inventory = registry_inventory()
        self.assertEqual(len(REVIEWED_SOURCE_PINS), 0)
        self.assertEqual(inventory["reviewed_source_pin_count"], 0)
        self.assertEqual(len(inventory["assets"]), 3)
        self.assertEqual({x["source_state"] for x in inventory["assets"]}, {"PIN_REVIEW_REQUIRED"})
        self.assertFalse(inventory["model_admission_granted"])
        self.assertEqual(inventory["qualified_model_series"], [])
        self.assertEqual(inventory["financial_operations"], 0)

    def test_public_candidate_is_blocked_without_reviewed_source(self):
        with self.assertRaisesRegex(SourceRegistryBlocked, "NO_REVIEWED_SOURCE_PIN"):
            verify_registry_candidate(self.example(), ARTIFACT,
                                      captured_at=CAPTURE, decision_asof=CUTOFF)

    def test_unknown_asset_blocked_even_if_claimed_trusted(self):
        claim = self.example()
        claim.update(instrument_code="UNKNOWN", trusted=True)
        with self.assertRaisesRegex(SourceRegistryBlocked, "UNKNOWN_INSTRUMENT"):
            verify_registry_candidate(claim, ARTIFACT,
                                      captured_at=CAPTURE, decision_asof=CUTOFF)

    def test_internal_synthetic_pin_only_verifies_local_hash_not_origin(self):
        result = self.check()
        self.assertTrue(result["artifact_sha256_matches_reviewed_pin"])
        self.assertTrue(result["source_metadata_matches_reviewed_pin"])
        self.assertFalse(result["source_network_origin_attested"])
        self.assertFalse(result["capture_clock_independently_attested"])
        self.assertFalse(result["historical_pit_certified"])
        self.assertFalse(result["model_admission_granted"])
        self.assertEqual(result["qualified_model_series"], [])
        self.assertEqual(result["model_state"], "HOLD_CASH")

    def test_client_approval_flag_does_not_authorize_model(self):
        c = self.example()
        c.update(approved=True, PIT_VERIFIED=True, legal_to_trade=True)
        self.assertFalse(self.check(claimed=c)["model_admission_granted"])

    def test_tampered_file_bytes_rejected(self):
        self.blocked("ARTIFACT_DIGEST_MISMATCH", artifact=ARTIFACT + b"tamper")

    def test_hash_mismatch_in_client_claim_rejected(self):
        c = self.example()
        c["source_sha256"] = "a" * 64
        self.blocked("SOURCE_BINDING_MISMATCH", claimed=c)

    def test_subdomain_spoof_rejected(self):
        c = self.example()
        c["canonical_url"] = "https://example.org.attacker.invalid/research/data.csv"
        self.blocked("SOURCE_BINDING_MISMATCH", claimed=c)

    def test_username_host_spoof_rejected(self):
        p = replace(pin_fixture(), canonical_url="https://example.org@evil.invalid/research")
        self.blocked("PIN_URL_INVALID", pin=p)

    def test_url_query_secret_rejected(self):
        p = replace(pin_fixture(), canonical_url="https://example.org/research/data.csv?key=test")
        self.blocked("PIN_URL_INVALID", pin=p)

    def test_redirect_target_cannot_claim_different_url(self):
        c = self.example()
        c["canonical_url"] = "https://redirector.invalid/research/data.csv"
        self.blocked("SOURCE_BINDING_MISMATCH", claimed=c)

    def test_invalid_hash_in_curated_pin_rejected(self):
        self.blocked("PIN_DIGEST_INVALID", pin=replace(pin_fixture(), source_sha256="fake"))

    def test_pin_basis_price_only_rejected(self):
        self.blocked("PIN_PRICE_BASIS_INVALID", pin=replace(pin_fixture(), value_concept="OTHER_REFERENCE"))

    def test_non_pln_pin_rejected(self):
        self.blocked("PIN_PRICE_BASIS_INVALID", pin=replace(pin_fixture(), currency="USD"))

    def test_unknown_pin_asset_rejected(self):
        self.blocked("PIN_UNKNOWN_INSTRUMENT", pin=replace(pin_fixture(), instrument_code="CRYPTO_TR_PLN"))

    def test_empty_artifact_rejected(self):
        self.blocked("ARTIFACT_BYTES_INVALID", artifact=b"")

    def test_oversize_artifact_rejected(self):
        self.blocked("ARTIFACT_BYTES_INVALID", artifact=b"x"*(MAX_ARTIFACT_BYTES+1))

    def test_future_publication_blocks(self):
        p=replace(pin_fixture(),first_public_at="2026-11-10T00:00:00Z")
        self.blocked("PUBLICATION_AFTER_DECISION", pin=p)

    def test_retrospective_capture_cannot_be_historic_pit(self):
        self.blocked("RETROSPECTIVE_CAPTURE_AFTER_DECISION", captured_at="2026-11-11T00:00:00Z")

    def test_capture_before_publication_blocks(self):
        self.blocked("CAPTURE_BEFORE_PUBLICATION", captured_at="2026-10-01T00:00:00Z")

    def test_naive_capture_timestamp_blocks(self):
        self.blocked("TIMESTAMP_INVALID", captured_at="2026-10-10T12:00:00")

    def test_naive_pub_time_blocks(self):
        p = replace(pin_fixture(), first_public_at="2026-10-09T12:00:00")
        self.blocked("TIMESTAMP_INVALID", pin=p)

    def test_immutable_pin_cannot_be_mutated(self):
        p=pin_fixture()
        with self.assertRaises((AttributeError, TypeError)):
            p.currency = "USD"


if __name__ == "__main__":
    unittest.main()
