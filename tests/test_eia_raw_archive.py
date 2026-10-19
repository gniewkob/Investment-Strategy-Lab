"""Synthetic no-network regression for private EIA original-byte archive.

No actual EIA pages, Neon credentials, portfolio data, or GitHub artifacts.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from src.isl_v2.eia_versioned_ingest import prepare
from src.isl_v2.eia_raw_archive import (
    archive_snapshot, verify_snapshot, SCHEMA, _paths,
)
from src.isl_v2.eia_sources import SourceFormatError
from test_eia_sources import NOW, fixture


class SourceArchiveTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(prefix="isl-eia-private-archive-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)

    def plan(self, *, when=NOW, html=None):
        return prepare("wti", fixture() if html is None else html, when)

    def test_first_archive_retains_exact_original_source_bytes(self):
        p = self.plan()
        summary = archive_snapshot(self.root,p)
        verified = verify_snapshot(self.root,p)
        source, raw_name, manifest_name = _paths(p)
        raw = (self.root/"objects"/raw_name).read_bytes()
        metadata = json.loads((self.root/"receipts"/source/manifest_name).read_text())
        self.assertEqual(raw,fixture())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),p.source_bytes_sha256)
        self.assertEqual(metadata["original_html_sha256"],p.source_bytes_sha256)
        self.assertEqual(metadata["archive_schema"],SCHEMA)
        self.assertEqual(metadata["semantic_observation_count"],18)
        self.assertEqual(metadata["retrieved_at"],NOW.isoformat())
        self.assertFalse(metadata["immutable_object_storage_certified"])
        self.assertFalse(metadata["independent_historical_publication_vintages_verified"])
        self.assertEqual(summary["database_connections"],0)
        self.assertEqual(summary["database_writes"],0)
        self.assertEqual(verified["status"],"EIA_RAW_HTML_ARCHIVE_LOCAL_READBACK_VALID")
        self.assertTrue(summary["object_created"])
        self.assertTrue(summary["receipt_created"])
        # Files and directories must remain unavailable to other system users.
        self.assertEqual((self.root/"objects"/raw_name).stat().st_mode & 0o077,0)
        self.assertEqual((self.root/"receipts"/source/manifest_name).stat().st_mode & 0o077,0)
        for private in ("objects","receipts",f"receipts/{source}"):
            self.assertEqual((self.root/private).stat().st_mode & 0o077,0)
        text = json.dumps(summary)
        for forbidden in ("101.10","102.10",str(self.root),"postgresql://"):
            self.assertNotIn(forbidden,text)

    def test_byte_identity_dedupe_and_distinct_acquisition_proofs(self):
        a = self.plan()
        first = archive_snapshot(self.root,a)
        again = archive_snapshot(self.root,a)
        self.assertTrue(first["object_created"])
        self.assertFalse(again["object_created"])
        self.assertFalse(again["receipt_created"])
        later = self.plan(when=NOW+timedelta(seconds=1))
        result=archive_snapshot(self.root,later)
        self.assertFalse(result["object_created"])
        self.assertTrue(result["receipt_created"])
        source, raw_name, _ = _paths(a)
        self.assertEqual(len(list((self.root/"objects").glob("*.html"))),1)
        self.assertEqual(len(list((self.root/"receipts"/source).glob("*.json"))),2)
        self.assertEqual(verify_snapshot(self.root,a)["original_html_sha256"],a.source_bytes_sha256)
        self.assertEqual(verify_snapshot(self.root,later)["retrieved_at"],
                         later.snapshot.downloaded_at.isoformat())

    def test_cosmetic_html_and_real_price_change_are_distinct(self):
        a=self.plan()
        cosmetic = self.plan(when=NOW+timedelta(seconds=1),
                             html=fixture().replace(b"<html>",b"<html><!--layout only-->"))
        revised=self.plan(when=NOW+timedelta(seconds=2),
                          html=fixture(replace_cell=(0,0,"101.12")))
        report_a=archive_snapshot(self.root,a)
        report_b=archive_snapshot(self.root,cosmetic)
        report_c=archive_snapshot(self.root,revised)
        self.assertNotEqual(report_a["original_html_sha256"],report_b["original_html_sha256"])
        self.assertEqual(report_a["semantic_observations_sha256"],
                         report_b["semantic_observations_sha256"])
        self.assertNotEqual(report_a["semantic_observations_sha256"],
                            report_c["semantic_observations_sha256"])
        self.assertEqual(len(list((self.root/"objects").glob("*.html"))),3)
        self.assertTrue(verify_snapshot(self.root,revised))

    def test_corrupted_object_fails_replay_and_verify_without_overwrite(self):
        a=self.plan()
        archive_snapshot(self.root,a)
        _,raw,_ = _paths(a)
        target=self.root/"objects"/raw
        corrupt=b"overwrite-not-allowed"
        target.write_bytes(corrupt)
        with self.assertRaisesRegex(SourceFormatError,"differs"):
            archive_snapshot(self.root,a)
        with self.assertRaisesRegex(SourceFormatError,"differ"):
            verify_snapshot(self.root,a)
        self.assertEqual(target.read_bytes(),corrupt)

    def test_tampered_manifest_fails_without_overwrite(self):
        a=self.plan()
        archive_snapshot(self.root,a)
        source,_,manifest=_paths(a)
        target=self.root/"receipts"/source/manifest
        saved=json.loads(target.read_text())
        saved["retrieved_at"]="2024-01-01T00:00:00+00:00"
        target.write_text(json.dumps(saved))
        with self.assertRaisesRegex(SourceFormatError,"differs"):
            archive_snapshot(self.root,a)
        with self.assertRaisesRegex(SourceFormatError,"differ"):
            verify_snapshot(self.root,a)

    def test_no_symlink_in_root_or_archive_entries(self):
        a=self.plan()
        original=self.root/"objects"
        original.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):
            archive_snapshot(self.root,a)
        original.unlink()
        archive_snapshot(self.root,a)
        _,raw,_=_paths(a)
        (self.root/"objects"/raw).unlink()
        (self.root/"objects"/raw).symlink_to(self.root/"not-a-real-object")
        with self.assertRaises(OSError):
            archive_snapshot(self.root,a)

    def test_reject_untrusted_private_archive_root_and_forged_plan(self):
        a=self.plan()
        self.root.chmod(0o755)
        with self.assertRaisesRegex(SourceFormatError,"private"):
            archive_snapshot(self.root,a)
        self.root.chmod(0o700)
        with self.assertRaisesRegex(SourceFormatError,"absolute"):
            archive_snapshot("relative/path",a)
        with self.assertRaisesRegex(SourceFormatError,"source bytes"):
            archive_snapshot(self.root,replace(a,original_html=a.original_html+b"altered"))
        with self.assertRaisesRegex(SourceFormatError,"source bytes"):
            archive_snapshot(self.root,replace(a,source_bytes_sha256="f"*64))
        with self.assertRaises(SourceFormatError):
            archive_snapshot(self.root,replace(a,snapshot=replace(
                a.snapshot,observations=(replace(
                    a.snapshot.observations[0],price=Decimal("999.99")),
                    *a.snapshot.observations[1:]))))
        self.assertFalse((self.root/"objects").exists())

    def test_readback_has_no_side_effect_if_directory_missing(self):
        p=self.plan()
        with self.assertRaises(FileNotFoundError):
            verify_snapshot(self.root,p)
        self.assertEqual(list(self.root.iterdir()),[])


if __name__=="__main__":
    import unittest
    unittest.main()
