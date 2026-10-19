"""Synthetic regressions for post-backfill 695-day EIA and Neon receipt.

No real Neon, EIA HTTP, credentials or private market prices are accessed.
"""
from __future__ import annotations

from contextlib import redirect_stderr
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
from io import StringIO
import json
from unittest import TestCase
from unittest.mock import patch

from scripts import eia_wti_postimport_receipt as post
from src.isl_v2.eia_sources import SOURCES, Spot, Snapshot

FIRST = date(2026, 10, 9)
OLD_LAST = date(2026, 10, 12)
NEW_FIRST = date(2026, 10, 13)
LAST = date(2026, 10, 14)
RELEASE = date(2026, 10, 15)
ORIGINAL = {FIRST: Decimal("71.000"), OLD_LAST: Decimal("72.000")}
ADDED = {NEW_FIRST: Decimal("73.000"), LAST: Decimal("74.000")}
HASH = hashlib.sha256(
    "\n".join(f"{d.isoformat()},{p}" for d,p in sorted(ORIGINAL.items())).encode()
).hexdigest()


def fixture_records():
    old = datetime(2026, 10, 17, 12, tzinfo=timezone.utc).isoformat()
    newer = datetime(2026, 10, 19, 18, 56, tzinfo=timezone.utc).isoformat()
    rows = [
        {"instrument_code": post.INSTRUMENT,
         "interval_code": "1d", "return_basis": "PRICE_ONLY",
         "observed_for": f"{d.isoformat()}T00:00:00+00:00",
         "ingested_at": old if d in ORIGINAL else newer,
         "close_price": str(v)}
        for d,v in sorted({**ORIGINAL,**ADDED}.items())
    ]
    rows.append({
        "instrument_code": "BRENT_EIA_USD_BBL",
        "interval_code": "1d", "return_basis": "PRICE_ONLY",
        "observed_for": "2026-10-12T00:00:00+00:00",
        "ingested_at": old, "close_price": "88.00",
    })
    return rows


def fixture_snapshot(rows=None, vintage="UNVERIFIED_HISTORICAL_PUBLICATION"):
    return {
        "mode": "RETROSPECTIVE_RESEARCH_ONLY",
        "source_vintage": vintage,
        "records": fixture_records() if rows is None else rows,
    }


def fixture_manifest():
    return {
        "series_counts": {post.INSTRUMENT: 4},
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "database_writes": 0,
        "as_of": "2026-10-19T19:00:00+00:00",
    }


def official():
    return Snapshot(
        *SOURCES["wti"], "a"*64, RELEASE,
        datetime(2026, 10, 19, 19, tzinfo=timezone.utc),
        tuple(Spot(d,p) for d,p in sorted({**ORIGINAL,**ADDED}.items())), 4,
    )


class PostImportStagingReceiptTests(TestCase):
    def setUp(self):
        self.patchers = [
            patch.object(post, "FIRST", FIRST),
            patch.object(post, "ORIGINAL_LAST", OLD_LAST),
            patch.object(post, "IMPORT_FIRST", NEW_FIRST),
            patch.object(post, "LAST", LAST),
            patch.object(post, "EXPECTED_ORIGINAL_ROWS", 2),
            patch.object(post, "EXPECTED_NEW_ROWS", 2),
            patch.object(post, "EXPECTED_COMPLETE_ROWS", 4),
            patch.object(post, "ORIGINAL_660_SHA256", HASH),
        ]
        for p in self.patchers: p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patchers)])

    def test_original_slice_and_actual_import_chronology(self):
        evidence = post.verify_staging_chronology(
            fixture_snapshot(), fixture_manifest()["as_of"])
        self.assertEqual(evidence["unchanged_prior_660_sha256"], HASH)
        self.assertEqual(evidence["previously_stored_rows"], 2)
        self.assertEqual(evidence["backfilled_rows"], 2)
        self.assertFalse(evidence["source_publication_vintages_verified"])

    def test_full_single_run_passes_and_emits_only_aggregates(self):
        with (patch.object(post, "fetch_staging_history",
                           return_value=(fixture_snapshot(), fixture_manifest())) as staging,
              patch.object(post, "fetch_official", return_value=official()) as source):
            report = post.audit("temporary-test-dsn-not-to-print")
        staging.assert_called_once_with("temporary-test-dsn-not-to-print")
        source.assert_called_once()
        self.assertEqual(source.call_args.args[0], "wti")
        self.assertEqual(source.call_args.kwargs["max_age_days"], 1100)
        self.assertEqual(report["status"], "WTI_POSTIMPORT_EIA_STAGING_695_MATCH_READ_ONLY")
        self.assertEqual(report["matching_dates_and_prices"], 4)
        self.assertEqual(report["source_original_html_sha256"], "a"*64)
        self.assertEqual(report["database_reads"], 1)
        self.assertEqual(report["database_writes"], 0)
        self.assertFalse(report["independent_point_in_time_market_data_certified"])
        self.assertEqual(report["versioned_market_documents_created"], 0)
        self.assertEqual(report["versioned_market_observations_created"], 0)
        self.assertEqual(
            report["current_source_available_not_before_utc"],
            "2026-10-19T19:00:00+00:00")
        raw = json.dumps(report)
        for secret in ("71.000", "72.000", "73.000", "74.000",
                       "88.00", "temporary-test-dsn-not-to-print",
                       "postgresql://"):
            self.assertNotIn(secret, raw)

    def test_source_mismatch_fails_not_a_forgiving_count(self):
        ref = {**ORIGINAL,**ADDED}
        chronology = post.verify_staging_chronology(
            fixture_snapshot(),fixture_manifest()["as_of"])
        corrupted = replace(official(),
                            observations=tuple(
                                Spot(s.observed_on, Decimal("88.888")
                                     if s.observed_on==LAST else s.price)
                                for s in official().observations))
        with self.assertRaisesRegex(ValueError, "integrity"):
            post.review_complete(corrupted, ref, reference_sha256="b"*64,
                                 chronology=chronology)
        with self.assertRaisesRegex(ValueError, "coverage"):
            post.review_complete(official(), {k:v for k,v in ref.items() if k!=LAST},
                                 reference_sha256="b"*64, chronology=chronology)
        with self.assertRaisesRegex(ValueError, "publication"):
            post.review_complete(replace(official(),release_day=date(2026,10,16)),
                                 ref,reference_sha256="b"*64, chronology=chronology)
        with self.assertRaisesRegex(ValueError, "source"):
            post.review_complete(replace(official(),
                                         instrument_code="BRENT_EIA_USD_BBL"),
                                 ref,reference_sha256="b"*64, chronology=chronology)

    def test_old_values_cannot_change_even_if_current_official_matches(self):
        rows = fixture_records()
        rows[0]["close_price"] = "99.000"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            post.verify_staging_chronology(
                fixture_snapshot(rows), fixture_manifest()["as_of"])

    def test_new_prices_must_not_be_backdated(self):
        rows = fixture_records()
        rows[3]["ingested_at"] = "2026-08-26T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "chronology|backdated"):
            post.verify_staging_chronology(
                fixture_snapshot(rows), fixture_manifest()["as_of"])

    def test_reject_missing_duplicate_or_new_outside_frozen_window(self):
        rows = fixture_records()
        rows[3] = dict(rows[2])
        with self.assertRaises(ValueError):
            post.verify_staging_chronology(fixture_snapshot(rows),
                                            fixture_manifest()["as_of"])
        rows = fixture_records()
        rows[3]["observed_for"] = "2026-10-16T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "outside"):
            post.verify_staging_chronology(fixture_snapshot(rows),
                                            fixture_manifest()["as_of"])

    def test_bad_staging_fails_before_http_fetch(self):
        with (patch.object(post,"fetch_staging_history",
                           return_value=(fixture_snapshot(), fixture_manifest())),
              patch.object(post, "fetch_official") as src,
              patch.object(post, "ORIGINAL_660_SHA256", "f"*64)):
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                post.audit("fake-dsn")
            src.assert_not_called()

    def test_invalid_report_logs_no_secret(self):
        stderr = StringIO()
        with (patch.object(post, "audit",
                           side_effect=ValueError("postgresql://user:secret@host")),
              redirect_stderr(stderr)):
            result = post.main()
        self.assertEqual(result, 2)
        self.assertEqual(stderr.getvalue(),
                         "WTI_POSTIMPORT_RECEIPT_FAILED: ValueError\n")


if __name__ == "__main__":
    import unittest
    unittest.main()
