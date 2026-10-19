"""No-network tests for explicit private EIA archive operator CLI."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json

from scripts import eia_archive_local as cli
from src.isl_v2.eia_versioned_ingest import prepare
from test_eia_sources import fixture, NOW


class PrivateArchiveCLITests(TestCase):
    def test_explicit_capture_and_offline_verify_no_neon(self):
        with TemporaryDirectory(prefix="isl-eia-local-private-") as private:
            root = Path(private)
            root.chmod(0o700)
            p=prepare("wti",fixture(),NOW)
            captured=StringIO()
            with (patch.object(cli,"fetch_plan",return_value=p) as fetched,
                  redirect_stdout(captured)):
                self.assertEqual(cli.main(["capture","--source","wti",
                                           "--archive-root",str(root)]),0)
            fetched.assert_called_once()
            report=json.loads(captured.getvalue())
            self.assertEqual(report["source_code"],"eia_wti_daily")
            self.assertTrue(report["immediate_independent_replay"])
            self.assertFalse(report["immutable_object_storage_certified"])
            self.assertEqual(report["database_writes"],0)
            self.assertNotIn(str(root),captured.getvalue())
            self.assertNotIn("101.10",captured.getvalue())
            result=StringIO()
            with (patch.object(cli,"fetch_plan") as fetch,
                  redirect_stdout(result)):
                self.assertEqual(cli.main([
                    "verify","--source","wti","--archive-root",str(root),
                    "--sha256",p.source_bytes_sha256,
                    "--retrieved-at",NOW.isoformat()]),0)
                fetch.assert_not_called()
            proof=json.loads(result.getvalue())
            self.assertEqual(proof["status"],
                             "EIA_RAW_HTML_ARCHIVE_INDEPENDENT_OFFLINE_VERIFIED")
            self.assertFalse(proof["immutable_object_storage_certified"])
            self.assertEqual(proof["database_connections"],0)

    def test_failure_is_closed_and_does_not_log_private_paths_or_secrets(self):
        with TemporaryDirectory(prefix="isl-very-sensitive-path-") as private:
            plan=prepare("wti",fixture(),NOW)
            root=Path(private)
            root.chmod(0o755)
            err=StringIO()
            with (patch.object(cli,"fetch_plan",return_value=plan),
                  redirect_stderr(err)):
                code=cli.main(["capture","--source","wti",
                               "--archive-root",str(root)])
            self.assertEqual(code,2)
            self.assertEqual(err.getvalue(),
                             "EIA_PRIVATE_ARCHIVE_FAILED: SourceFormatError\n")
            self.assertNotIn(private,err.getvalue())
            self.assertNotIn("101.10",err.getvalue())

    def test_capture_explicitly_requires_operator_selected_path(self):
        with (redirect_stderr(StringIO()),
              self.assertRaises(SystemExit)):
            cli.main(["capture","--source","wti"])
