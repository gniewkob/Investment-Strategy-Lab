"""Offline educational EIA archive vintage comparisons; no network/Neon."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import json

from scripts.eia_prospective_archive_research import inspect_archive, main
from src.isl_v2.eia_raw_archive import archive_snapshot, _paths
from src.isl_v2.eia_versioned_ingest import prepare
from src.isl_v2.eia_sources import SourceFormatError
from test_eia_sources import NOW, fixture


class ProspectiveEIAArchiveResearchTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(prefix="isl-eia-prospective-private-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.root.chmod(0o700)

    def capture(self, source, *, time=NOW, content=None):
        plan=prepare(source,fixture() if content is None else content,time)
        archive_snapshot(self.root,plan)
        return plan

    def three_sources(self):
        return [self.capture(code) for code in ("wti","brent","henry_hub")]

    def test_first_real_vintage_three_sources_is_baseline_not_backtest(self):
        originals=self.three_sources()
        before=sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        report=inspect_archive(str(self.root))
        after=sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(before,after)
        self.assertEqual(report["status"],"EIA_PROSPECTIVE_ARCHIVE_DESCRIPTIVE_AUDIT")
        self.assertEqual(report["archive_sources_verified"],3)
        self.assertEqual(report["total_overlapping_price_revisions_since_captured_baseline"],0)
        self.assertFalse(report["original_historical_publication_vintages_verified"])
        self.assertFalse(report["historical_point_in_time_backtest_certified"])
        self.assertFalse(report["predictive_advantage_established"])
        self.assertFalse(report["investable_total_return_data_verified"])
        self.assertEqual(report["decision"],"RESEARCH_ONLY_HOLD_NO_CHANGE")
        for key in ("database_connections","database_writes",
                    "external_http_requests","file_creations",
                    "virtual_model_allocations_changed","paper_fills","real_orders"):
            self.assertEqual(report[key],0)
        self.assertFalse(report["schedule_enabled"])
        for row,plan in zip(report["source_series"],originals):
            self.assertEqual(row["source_code"],plan.snapshot.source_code)
            self.assertEqual(row["latest_raw_html_sha256"],plan.source_bytes_sha256)
            self.assertEqual(row["latest_semantic_sha256"],
                             archive_snapshot(self.root,plan)["semantic_observations_sha256"])
            self.assertEqual(row["latest_observation_count"],18)
            self.assertEqual(row["research_readiness"],"FIRST_SOURCE_CAPTURE_BASELINE_ONLY")
            self.assertEqual(row["comparisons"],[])
        self.assertEqual(before,sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*")))

    def test_cosmetic_html_change_does_not_fabricate_quote_revision(self):
        self.three_sources()
        cosmetic=fixture().replace(b"<html>",b"<html><!--new EIA template-->")
        self.capture("wti",time=NOW+timedelta(seconds=10),content=cosmetic)
        report=inspect_archive(str(self.root))
        wti=report["source_series"][0]
        self.assertEqual(wti["captured_vintages"],2)
        comparison=wti["comparisons"][0]
        self.assertEqual(comparison["overlapping_observed_dates"],18)
        self.assertEqual(comparison["unchanged_overlapping_prices"],18)
        self.assertEqual(comparison["revised_overlapping_prices"],0)
        self.assertEqual(comparison["newly_seen_observed_dates"],0)
        self.assertEqual(comparison["no_longer_in_current_window"],0)
        self.assertTrue(comparison["raw_html_hash_changed"])
        self.assertFalse(comparison["semantic_hash_changed"])
        self.assertFalse(comparison["historical_original_release_dates_verified"])
        self.assertEqual(wti["research_readiness"],
                         "PROSPECTIVE_VINTAGE_COMPARISON_DESCRIPTIVE_ONLY")

    def test_actual_changed_overlapping_quote_detected_without_price_disclosure(self):
        self.three_sources()
        later=fixture(replace_cell=(0,0,"101.99"))
        self.capture("brent",time=NOW+timedelta(hours=2),content=later)
        captured=StringIO()
        with redirect_stdout(captured):
            self.assertEqual(main(["--archive-root",str(self.root)]),0)
        report=json.loads(captured.getvalue())
        brent=report["source_series"][1]
        change=brent["comparisons"][0]
        self.assertEqual(change["revised_overlapping_prices"],1)
        self.assertEqual(change["unchanged_overlapping_prices"],17)
        self.assertEqual(change["newly_seen_observed_dates"],0)
        self.assertTrue(change["semantic_hash_changed"])
        self.assertEqual(brent["research_readiness"],"PROSPECTIVE_REVISION_REVIEW_ONLY")
        self.assertEqual(report["total_overlapping_price_revisions_since_captured_baseline"],1)
        for forbidden in ("101.99","101.10",str(self.root),"postgresql://"):
            self.assertNotIn(forbidden,captured.getvalue())
        self.assertEqual(report["virtual_model_allocations_changed"],0)
        self.assertEqual(report["real_orders"],0)

    def test_idempotent_duplicate_bytes_different_acquisition_time(self):
        self.three_sources()
        self.capture("henry_hub",time=NOW+timedelta(seconds=1))
        row=inspect_archive(str(self.root))["source_series"][2]
        self.assertEqual(row["captured_vintages"],2)
        delta=row["comparisons"][0]
        self.assertFalse(delta["raw_html_hash_changed"])
        self.assertFalse(delta["semantic_hash_changed"])
        self.assertEqual(delta["revised_overlapping_prices"],0)

    def test_tampered_archive_object_and_manifest_fail_closed(self):
        original=self.three_sources()[0]
        _, obj, name=_paths(original)
        object_file=self.root/"objects"/obj
        object_file.write_bytes(b"tampered")
        with self.assertRaises(SourceFormatError):
            inspect_archive(str(self.root))
        object_file.write_bytes(original.original_html)
        target=self.root/"receipts"/original.snapshot.source_code/name
        manifest=json.loads(target.read_text())
        manifest["semantic_observations_sha256"]="0"*64
        target.write_text(json.dumps(manifest)+"\n")
        with self.assertRaises(SourceFormatError):
            inspect_archive(str(self.root))

    def test_conflicting_same_instant_receipts_are_rejected(self):
        self.three_sources()
        self.capture("wti",time=NOW,content=fixture(replace_cell=(0,0,"101.55")))
        with self.assertRaisesRegex(SourceFormatError,"Conflicting EIA"):
            inspect_archive(str(self.root))

    def test_missing_source_and_public_permissions_fail_without_leakage(self):
        self.capture("wti")
        errors=StringIO()
        with redirect_stderr(errors):
            self.assertEqual(main(["--archive-root",str(self.root)]),2)
        self.assertEqual(errors.getvalue().strip(),
                         "EIA_PROSPECTIVE_ARCHIVE_AUDIT_FAILED: FileNotFoundError")
        self.assertNotIn(str(self.root),errors.getvalue())
        self.root.chmod(0o755)
        with self.assertRaisesRegex(SourceFormatError,"private"):
            inspect_archive(str(self.root))
