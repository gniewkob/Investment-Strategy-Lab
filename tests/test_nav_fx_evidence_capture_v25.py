"""v0.25 synthetic-only original XLSX + official NBP raw evidence tests."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import stat
from unittest.mock import patch
import json
import unittest

from scripts.nav_forward_freeze_v22 import freeze
from scripts import nav_forward_admission_v23 as v23
from scripts.nav_fx_evidence_capture_v25 import collect, _write_private_raw
from tests.test_conditional_m1_nav_diagnostic_v20 import sample_receipt
from tests.test_vanguard_xlsx_offline_intake_v04 import fake_xlsx

NOV=datetime(2026,11,7,22,tzinfo=timezone.utc)
DEC=datetime(2026,12,4,22,tzinfo=timezone.utc)
NBP=json.dumps([{"table":"A","effectiveDate":"2026-11-30",
                 "rates":[{"code":"USD","mid":4.0}]}]).encode()


def sources():
    baseline=sample_receipt()
    frozen=freeze(baseline,clock=lambda:NOV)
    return frozen,baseline


def run(frozen, baseline, **kw):
    with patch.object(v23,"ANCHORED_FREEZE_SHA",frozen["freeze_receipt_sha256"]):
        return collect(frozen,baseline,**kw)


class NAVFXCaptureV25Tests(unittest.TestCase):
    def test_original_nbp_raw_file_private_from_creation_and_exact_bytes(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"archive"/"nbp.json"
            # The output must stay 0600 even if parent process permits 0666.
            previous_umask=os.umask(0)
            try:
                _write_private_raw(path, NBP)
            finally:
                os.umask(previous_umask)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(path.read_bytes(), NBP)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_original_nbp_raw_file_never_overwritten(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"nbp.json"
            _write_private_raw(path, NBP)
            with self.assertRaises(FileExistsError):
                _write_private_raw(path, b"forged")
            self.assertEqual(path.read_bytes(), NBP)

    def test_original_nbp_raw_file_preexisting_symlink_rejected(self):
        with TemporaryDirectory() as d:
            target=Path(d)/"protected.json"
            target.write_bytes(b"keep")
            link=Path(d)/"nbp.json"
            link.symlink_to(target)
            with self.assertRaises(FileExistsError):
                _write_private_raw(link, NBP)
            self.assertEqual(target.read_bytes(), b"keep")

    def test_current_month_offline_pending_no_fetch(self):
        frozen,baseline=sources()
        def blocked(_):
            raise AssertionError("unexpected network")
        r,raw=run(frozen,baseline,clock=lambda:NOV,fetch=blocked)
        self.assertEqual(r["status"],"PENDING_NEW_PROVIDER_EXPORT")
        self.assertIsNone(raw)
        self.assertEqual(r["financial_operations"],0)

    def test_network_requires_explicit_source_and_consent(self):
        frozen,baseline=sources()
        with self.assertRaisesRegex(ValueError,"requires a new provider"):
            run(frozen,baseline,clock=lambda:NOV,allow_nbp_fetch=True)

    def test_pre_december_rejects_new_xlsx(self):
        frozen,baseline=sources()
        with self.assertRaisesRegex(ValueError,"month incomplete"):
            run(frozen,baseline,raw_xlsx=fake_xlsx(61),clock=lambda:NOV)

    def test_valid_new_export_without_network_is_ready_only(self):
        frozen,baseline=sources()
        r,raw=run(frozen,baseline,raw_xlsx=fake_xlsx(61),clock=lambda:DEC,
                  xlsx_retrieved_at_utc="2026-12-02T12:00:00+00:00")
        self.assertEqual(r["status"],"READY_FOR_EXPLICIT_NBP_SOURCE_READ")
        self.assertIsNone(raw)
        self.assertEqual(r["historical_revision_count"],0)
        self.assertEqual(r["prospective_qualified_months"],0)

    def test_fetch_is_exact_day_once_and_raw_bytes_preserved(self):
        frozen,baseline=sources()
        calls=[]
        def fake_fetch(url):
            calls.append(url)
            return NBP
        r,raw=run(frozen,baseline,raw_xlsx=fake_xlsx(61),clock=lambda:DEC,
                  xlsx_retrieved_at_utc="2026-12-02T12:00:00+00:00",
                  allow_nbp_fetch=True,fetch=fake_fetch)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0],
                         "https://api.nbp.pl/api/exchangerates/tables/a/"
                         "2026-11-30/2026-11-30/?format=json")
        self.assertEqual(raw,NBP)
        self.assertEqual(r["status"],"PRIVATE_OFFICIAL_NBP_CAPTURED_CANDIDATE_ONLY")
        self.assertEqual(r["prospective_qualified_months"],0)
        self.assertFalse(r["strict_m1_qualified"])
        self.assertEqual(r["financial_operations"],0)

    def test_revisions_do_not_fetch_nbp(self):
        frozen,baseline=sources()
        def blocked(_):
            raise AssertionError("source revisions must stop network")
        r,raw=run(frozen,baseline,raw_xlsx=fake_xlsx(61,localized=True),
                  clock=lambda:DEC,
                  xlsx_retrieved_at_utc="2026-12-02T12:00:00+00:00",
                  allow_nbp_fetch=True,fetch=blocked)
        self.assertEqual(r["status"],"BLOCKED_PROVIDER_REVISIONS_NEED_REVIEW")
        self.assertGreater(r["historical_revision_count"],0)
        self.assertIsNone(raw)

    def test_bad_official_nbp_response_is_not_archived(self):
        frozen,baseline=sources()
        def bad(_):
            return b'{"wrong":"payload"}'
        with self.assertRaises(ValueError):
            run(frozen,baseline,raw_xlsx=fake_xlsx(61),clock=lambda:DEC,
                xlsx_retrieved_at_utc="2026-12-02T12:00:00+00:00",
                allow_nbp_fetch=True,fetch=bad)

    def test_pre_freeze_export_timestamp_rejected(self):
        frozen,baseline=sources()
        with self.assertRaisesRegex(ValueError,"must postdate freeze"):
            run(frozen,baseline,raw_xlsx=fake_xlsx(61),clock=lambda:DEC,
                xlsx_retrieved_at_utc="2026-11-06T12:00:00+00:00")

    def test_unanchored_freeze_rejected(self):
        frozen,baseline=sources()
        with self.assertRaisesRegex(ValueError,"prepublished GitHub"):
            collect(frozen,baseline,clock=lambda:NOV)


if __name__=="__main__":
    unittest.main()
