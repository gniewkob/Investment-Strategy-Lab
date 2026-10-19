"""Offline fail-closed contract for the EIA STAGING SQL data-readiness probe.

No network, Neon credentials, DB writes, or historical price fixtures.
"""
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "db/verify_eia_first_snapshot_READONLY.sql"


class EIAStagingReadOnlyContractTests(unittest.TestCase):
    @staticmethod
    def sql():
        raw = PREFLIGHT.read_text(encoding="utf-8")
        return "\n".join(line.split("--", 1)[0] for line in raw.splitlines())

    def test_sql_only_one_read_only_statement_without_mutating_operations(self):
        src = self.sql().strip()
        statements = [s.strip() for s in src.split(";") if s.strip()]
        self.assertEqual(len(statements), 1)
        self.assertTrue(statements[0].upper().startswith("WITH\n"))
        forbidden = (
            "INSERT", "UPDATE", "DELETE", "TRUNCATE", "MERGE", "CREATE",
            "ALTER", "DROP", "GRANT", "REVOKE", "CALL", "EXECUTE", "DO",
            "COPY", "LOCK", "VACUUM", "ANALYZE", "REFRESH",
        )
        # Ignore case and separate word tokens. The contract is one top-level
        # SELECT with read-only CTEs; no SQL mutation or administrative verbs.
        for verb in forbidden:
            with self.subTest(verb=verb):
                self.assertIsNone(re.search(r"\b" + verb + r"\b", src, re.I))

    def test_never_claims_live_source_or_writer_go(self):
        sql = self.sql()
        self.assertIn("NO_GO_PENDING_LIVE_SOURCE_AND_EXPLICIT_WRITER_APPROVAL", sql)
        self.assertIn("REFERENCE_DATA_PREFLIGHT_PASS", sql)
        self.assertIn("REFERENCE_DATA_PREFLIGHT_FAIL", sql)
        for safety in (
            "latest_eia_html_provenance_verified_by_this_sql",
            "github_workflow_manual_receipts_verified_by_this_sql",
            "independent_historical_publication_vintages_verified",
        ):
            self.assertIn(safety, sql)
        self.assertIn("FALSE AS latest_eia_html_provenance_verified_by_this_sql", sql)
        self.assertIn("0 AS database_writes", sql)

    def test_pinned_staging_marker_frozen_wti_price_checksum_and_catalog(self):
        src = self.sql()
        for required in (
            "staging-security-canary-2026-10-18",
            "2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8",
            "WTI_EIA_USD_BBL",
            "BRENT_EIA_USD_BBL",
            "HENRY_HUB_USD_MMBTU",
            "eia_wti_daily",
            "eia_brent_daily",
            "eia_henryhub_daily",
            "wti_rows=695",
            "wti_unique_days=695",
            "wti_backfilled=35",
            "brent_rows=706",
            "staging_marker_cycles=1",
            "staging_marker_decisions=3",
            "rolname='isl_eia_pit_staging_writer'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, src)


if __name__ == "__main__":
    unittest.main()
