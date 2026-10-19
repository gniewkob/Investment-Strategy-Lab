"""Pure offline checks for semantic EIA date/Decimal price fingerprints."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from unittest import TestCase

from src.isl_v2.eia_sources import parse_snapshot, Spot, SourceFormatError
from src.isl_v2.eia_semantic_evidence import semantic_evidence
from test_eia_sources import fixture, NOW


class EIADateValueFingerprintTests(TestCase):
    def test_html_template_change_changes_raw_sha_but_not_prices_digest(self):
        a = parse_snapshot("wti", fixture(), NOW)
        cosmetic = fixture().replace(b"<html>", b"<html><!-- harmless HTML edit -->")
        b = parse_snapshot("wti", cosmetic, NOW)
        self.assertNotEqual(a.sha256_hex, b.sha256_hex)
        self.assertEqual(semantic_evidence(a)["semantic_observations_sha256"],
                         semantic_evidence(b)["semantic_observations_sha256"])
        self.assertEqual(semantic_evidence(a)["semantic_observation_count"], 18)
        self.assertFalse(semantic_evidence(b)["historical_publication_vintages_verified"])

    def test_decimal_display_format_does_not_fake_price_revision(self):
        a = parse_snapshot("wti", fixture(), NOW)
        formatted = fixture().replace(b"101.10", b"101.1000")
        b = parse_snapshot("wti", formatted, NOW)
        self.assertNotEqual(a.sha256_hex, b.sha256_hex)
        self.assertEqual(semantic_evidence(a)["semantic_observations_sha256"],
                         semantic_evidence(b)["semantic_observations_sha256"])

    def test_real_value_change_changes_semantic_digest(self):
        a = parse_snapshot("wti", fixture(), NOW)
        b = parse_snapshot("wti", fixture(replace_cell=(0, 0, "101.11")), NOW)
        self.assertNotEqual(semantic_evidence(a)["semantic_observations_sha256"],
                            semantic_evidence(b)["semantic_observations_sha256"])

    def test_wrong_instrument_and_duplicate_unsorted_prices_fail_closed(self):
        a = parse_snapshot("wti", fixture(), NOW)
        with self.assertRaisesRegex(SourceFormatError, "Unknown"):
            semantic_evidence(replace(a, instrument_code="ANYTHING"))
        with self.assertRaisesRegex(SourceFormatError, "strictly"):
            semantic_evidence(replace(a, observations=a.observations + (a.observations[-1],)))
        with self.assertRaisesRegex(SourceFormatError, "strictly"):
            semantic_evidence(replace(a, observations=tuple(reversed(a.observations))))
        with self.assertRaisesRegex(SourceFormatError, "strictly"):
            semantic_evidence(replace(a, observations=(
                replace(a.observations[0],price=Decimal("-1")), *a.observations[1:],
            )))

    def test_source_and_unit_contribute_to_fingerprint(self):
        a = parse_snapshot("wti", fixture(), NOW)
        b = parse_snapshot("brent", fixture(), NOW)
        self.assertNotEqual(semantic_evidence(a)["semantic_observations_sha256"],
                            semantic_evidence(b)["semantic_observations_sha256"])
