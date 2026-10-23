"""Synthetic Coinbase App captures only; no account, wallet or credential access."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import coinbase_deposit_history as h
from scripts.coinbase_read_only_history import HistoryError
from scripts.operational_read_only import read_private, write_private
from tests.test_deposit_evidence_reconciliation import chain, deposit

ACCOUNT = "00000000-0000-4000-8000-000000000001"
IDENT = "00000000-0000-4000-8000-000000000002"
SECOND = "00000000-0000-4000-8000-000000000003"
PATH = f"/v2/accounts/{ACCOUNT}/transactions"
NOW = datetime(2026, 10, 23, 10, tzinfo=timezone.utc)


def transaction(ident=IDENT, **changes):
    return {"id": ident, "type": "receive", "status": "completed",
        "amount": {"amount": "0.00005000", "currency": "BTC"},
        "created_at": "2026-10-22T12:00:00Z", "resource": "transaction",
        "resource_path": PATH + "/" + ident, "description": "[PRIVATE_NOTE]",
        "from": {"email": "[PRIVATE_EMAIL]"}, **changes}


def page(rows, cursor=None, next_cursor=None):
    return {"request_cursor": cursor, "response": {"data": rows, "pagination": {
        "starting_after": cursor, "ending_before": None, "order": "desc", "limit": 100,
        "next_uri": PATH + "?starting_after=" + next_cursor if next_cursor else None}}}


def capture():
    return {"mode": h.CAPTURE_MODE, "account_id": ACCOUNT,
        "captured_at": NOW.isoformat(), "pages": [page([transaction()])]}


def bundle():
    return {"mode": h.BUNDLE_MODE, "history": capture(),
        "network_transfers": [chain()], "deposit_records": [deposit()]}


class DepositHistoryTests(unittest.TestCase):
    def test_receive_is_minimized_and_never_promoted_by_optional_hash(self):
        c = capture()
        c["pages"][0]["response"]["data"][0]["network"] = {
            "hash": "0x" + "a" * 64, "network_name": "base", "status": "confirmed"}
        before = deepcopy(c)
        result = h.normalize_receives(c, NOW)
        self.assertEqual(c, before)
        self.assertEqual(result["event_count"], 1)
        self.assertFalse(result["events"][0]["onchain_reconciliation_eligible"])
        self.assertFalse(result["coinbase_provenance_verified"])
        self.assertFalse(result["snapshot_completeness_certified"])
        for value in (ACCOUNT, IDENT, "[PRIVATE_NOTE]", "[PRIVATE_EMAIL]", "0x" + "a" * 64):
            self.assertNotIn(value, json.dumps(result))

    def test_page_chain_and_excluded_trades_do_not_become_deposits(self):
        c = capture()
        c["pages"] = [page([transaction()], next_cursor=IDENT),
            page([transaction(SECOND, type="advanced_trade_fill")], cursor=IDENT)]
        result = h.normalize_receives(c, NOW)
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(result["observed_record_count"], 2)
        self.assertEqual(result["excluded_non_receive_count"], 1)
        self.assertEqual(result["event_count"], 1)

    def test_truncated_duplicate_missing_and_badly_scoped_pages_rejected(self):
        cases = []
        c = capture(); c["pages"][0] = page([transaction()], next_cursor=IDENT); cases.append(c)
        c = capture(); c["pages"] *= 2; cases.append(c)
        c = capture(); c["pages"][0]["response"]["data"] *= 2; cases.append(c)
        c = capture(); c["pages"][0]["response"]["data"][0]["resource_path"] = "/wrong"; cases.append(c)
        c = capture(); del c["pages"][0]["response"]["pagination"]["next_uri"]; cases.append(c)
        c = capture(); c["pages"][0]["response"] = {}; cases.append(c)
        c = capture(); c["pages"] = []; cases.append(c)
        c = capture(); c["pages"][0]["response"]["errors"] = []; cases.append(c)
        for c in cases:
            with self.subTest(capture=c), self.assertRaises(HistoryError):
                h.normalize_receives(c, NOW)

    def test_empty_success_is_distinguished_from_unknown(self):
        c = capture(); c["pages"] = [page([])]
        result = h.normalize_receives(c, NOW)
        self.assertEqual(result["event_count"], 0)
        self.assertFalse(result["complete_funding_history_certified"])

    def test_cursor_cannot_change_account_host_or_request_shape(self):
        for uri in ("https://example.invalid" + PATH + "?starting_after=" + IDENT,
                    PATH.replace(ACCOUNT, SECOND) + "?starting_after=" + IDENT,
                    PATH + "?starting_after=" + IDENT + "&type=send",
                    PATH + "?starting_after=" + IDENT + "&starting_after=" + IDENT,
                    PATH + "?starting_after=" + IDENT + "&order=asc",
                    PATH + "?starting_after=" + IDENT + "#fragment"):
            c = capture()
            c["pages"] = [page([transaction()], next_cursor=IDENT), page([], cursor=IDENT)]
            c["pages"][0]["response"]["pagination"]["next_uri"] = uri
            with self.subTest(uri=uri), self.assertRaises(HistoryError):
                h.normalize_receives(c, NOW)

    def test_cursor_cannot_skip_the_last_observed_row(self):
        c = capture(); c["pages"] = [page([transaction()], next_cursor=SECOND), page([], cursor=SECOND)]
        with self.assertRaises(HistoryError): h.normalize_receives(c, NOW)

    def test_invalid_values_and_future_records_rejected(self):
        for changes in ({"status": []}, {"created_at": "2027-01-01T00:00:00Z"},
                        {"created_at": "2026-10-22T12:00:00"}, {"id": "[PRIVATE_ID]"}):
            c = capture(); c["pages"][0]["response"]["data"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(HistoryError): h.normalize_receives(c, NOW)
        for value in ("0", "-1", "NaN", "1e99999", "1" * 81, [], True):
            c = capture(); c["pages"][0]["response"]["data"][0]["amount"]["amount"] = value
            with self.subTest(value=value), self.assertRaises(HistoryError): h.normalize_receives(c, NOW)

    def test_unknown_status_is_preserved_as_unknown_not_completed(self):
        c = capture(); c["pages"][0]["response"]["data"][0]["status"] = "new_status"
        self.assertEqual(h.normalize_receives(c, NOW)["events"][0]["status"], "UNKNOWN")

    def test_budgets_are_enforced(self):
        c = capture(); c["pages"] *= 51
        with self.assertRaises(HistoryError): h.normalize_receives(c, NOW)
        c = capture(); c["pages"][0]["response"]["data"] *= 101
        with self.assertRaises(HistoryError): h.normalize_receives(c, NOW)

    def test_manual_matches_remain_unverified_and_separate_from_receives(self):
        result = h.review_bundle(bundle(), NOW)
        self.assertEqual(result["operator_evidence_reconciliation"][0]["classification"],
                         "REPORTED_MATCH_SOURCE_UNVERIFIED")
        self.assertFalse(result["receive_events_linked_to_chain"])
        self.assertFalse(result["sources_summed"])
        self.assertEqual(result["financial_operations"], 0)
        b = bundle(); b["deposit_records"] = []
        self.assertEqual(h.review_bundle(b, NOW)["operator_evidence_reconciliation"][0]["classification"],
                         "NO_MATCHING_DEPOSIT_RECORD")

    def test_cli_private_files_and_fixed_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_private(root / "input", bundle())
            cmd = [sys.executable, "-m", "scripts.coinbase_deposit_history", "--input", str(root / "input"),
                   "--output", str(root / "output"), "--at", NOW.isoformat()]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "output").stat().st_mode & 0o777, 0o600)
            self.assertEqual(read_private(root / "output")["history"]["event_count"], 1)
            self.assertNotIn(ACCOUNT, result.stdout + result.stderr)
            original = (root / "output").read_bytes()
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)
            self.assertEqual((root / "output").read_bytes(), original)
            (root / "input").chmod(0o644)
            cmd[cmd.index("--output") + 1] = str(root / "rejected")
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((root / "rejected").exists())
            self.assertEqual(result.stdout.strip(), "DEPOSIT_HISTORY_PRIVATE_REVIEW_REJECTED")


if __name__ == "__main__":
    unittest.main()
