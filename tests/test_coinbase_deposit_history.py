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

    def test_provider_offsets_normalize_to_utc_for_receives_and_other_types(self):
        expected = h.normalize_receives(capture(), NOW)
        for stamp in ("2026-10-22T05:00:00-07:00", "2026-10-22T14:00:00+02:00"):
            c = capture(); c["pages"][0]["response"]["data"][0]["created_at"] = stamp
            self.assertEqual(h.normalize_receives(c, NOW), expected)
        c = capture()
        c["pages"][0]["response"]["data"][0].update(
            type="buy", created_at="2015-03-26T23:44:08-07:00")
        self.assertEqual(h.normalize_receives(c, NOW)["excluded_non_receive_count"], 1)

    def test_provider_offsets_do_not_bypass_future_or_timezone_checks(self):
        for stamp in ("2026-10-23T05:00:00-07:00", "2026-10-22T12:00:00",
                      "9999-12-31T23:59:59-07:00"):
            c = capture(); c["pages"][0]["response"]["data"][0]["created_at"] = stamp
            with self.subTest(stamp=stamp), self.assertRaises(HistoryError):
                h.normalize_receives(c, NOW)

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

    def test_review_exposes_unpaired_deposit_without_linking_or_adding_receives(self):
        b = bundle(); b["network_transfers"] = []
        result = h.review_bundle(b, NOW)
        coverage = result["operator_evidence_coverage"]
        self.assertEqual(result["operator_evidence_reconciliation"], [])
        self.assertEqual(coverage["counts"]["classification_counts"], {"NO_MATCHING_NETWORK_TRANSFER": 1})
        self.assertEqual(coverage["unmatched_deposit_records"][0]["deposit_id"], "synthetic123")
        self.assertFalse(coverage["unmatched_is_external_funding"])
        self.assertFalse(result["receive_events_linked_to_chain"])
        self.assertFalse(result["balances_adjusted"])
        b["history"]["pages"] = [page([])]
        self.assertEqual(h.review_bundle(b, NOW)["operator_evidence_coverage"], coverage)


class UnclassifiedAccountEventTests(unittest.TestCase):
    def test_generic_credit_debit_and_zero_remain_unknown_source(self):
        for amount, direction in (("0.5", "ACCOUNT_CREDIT"), ("-0.5", "ACCOUNT_DEBIT"), ("0", "ZERO_REPORTED")):
            c = capture(); row = c["pages"][0]["response"]["data"][0]
            row.update(type="tx", amount={"amount": amount, "currency": "BTC"})
            result = h.normalize_receives(c, NOW)
            self.assertEqual(result["event_count"], 0)
            self.assertEqual(result["unclassified_account_event_count"], 1)
            self.assertEqual(result["excluded_other_event_count"], 0)
            self.assertEqual(result["excluded_non_receive_count"], 1)
            event = result["unclassified_account_events"][0]
            self.assertEqual(event["quantity_reported"], amount)
            self.assertEqual(event["direction"], direction)
            self.assertEqual(event["classification"], "UNCLASSIFIED_ACCOUNT_EVENT")
            self.assertFalse(event["external_funding_certified"])
            self.assertFalse(event["onchain_reconciliation_eligible"])
            self.assertFalse(result["absence_of_receive_proves_no_funding"])

    def test_legacy_generic_record_without_amount_stays_unknown_not_zero(self):
        c = capture(); row = c["pages"][0]["response"]["data"][0]
        row["type"] = "tx"; row.pop("amount")
        event = h.normalize_receives(c, NOW)["unclassified_account_events"][0]
        self.assertIsNone(event["quantity_reported"])
        self.assertIsNone(event["asset"])
        self.assertEqual(event["direction"], "UNKNOWN")
        self.assertEqual(event["amount_status"], "NOT_CAPTURED_UNKNOWN")

    def test_malformed_generic_money_rejected_when_field_is_present(self):
        for money in (None, {}, {"amount": "NaN", "currency": "BTC"},
                      {"amount": "1e3", "currency": "BTC"}, {"amount": True, "currency": "BTC"},
                      {"amount": "1" * 81, "currency": "BTC"}):
            c = capture(); c["pages"][0]["response"]["data"][0].update(type="tx", amount=money)
            with self.subTest(money=money), self.assertRaises(HistoryError): h.normalize_receives(c, NOW)

    def test_generic_event_privacy_and_no_optional_hash_promotion(self):
        c = capture(); c["pages"][0]["response"]["data"][0].update(type="tx",
            network={"hash": "0x" + "a" * 64, "status": "confirmed"})
        before = deepcopy(c)
        result = h.normalize_receives(c, NOW)
        self.assertEqual(c, before)
        for sensitive in (ACCOUNT, IDENT, "[PRIVATE_NOTE]", "[PRIVATE_EMAIL]", "0x" + "a" * 64):
            self.assertNotIn(sensitive, json.dumps(result))
        self.assertFalse(result["unclassified_account_events"][0]["onchain_reconciliation_eligible"])

    def test_generic_record_does_not_fill_deposit_evidence_gap(self):
        b = bundle(); b["history"]["pages"][0]["response"]["data"][0]["type"] = "tx"
        b["deposit_records"] = []
        result = h.review_bundle(b, NOW)
        self.assertEqual(result["operator_evidence_reconciliation"][0]["classification"], "NO_MATCHING_DEPOSIT_RECORD")
        self.assertEqual(result["history"]["unclassified_account_event_count"], 1)
        self.assertFalse(result["sources_summed"])

    def test_comparison_is_explicitly_receive_only_and_accepts_legacy_baseline(self):
        old, new = capture(), capture()
        old["captured_at"] = "2026-10-23T09:00:00Z"
        old["pages"][0]["response"]["data"][0]["type"] = "tx"
        old["pages"][0]["response"]["data"][0].pop("amount")
        new["pages"][0]["response"]["data"][0]["type"] = "tx"
        diff = h.compare_receive_captures(old, new, NOW)
        self.assertEqual(diff["records_compared"], "RECEIVE_ONLY")
        self.assertFalse(diff["unclassified_account_events_compared"])
        self.assertFalse(diff["new_external_funding_certified"])


class ReceiveComparisonTests(unittest.TestCase):
    def captures(self):
        previous, current = capture(), capture()
        previous["captured_at"] = "2026-10-23T09:00:00Z"
        return previous, current

    def test_repeat_observation_and_decimal_formatting_are_unchanged(self):
        previous, current = self.captures()
        current["pages"][0]["response"]["data"][0]["amount"]["amount"] = "0.00005"
        current["pages"][0]["response"]["data"][0]["created_at"] = "2026-10-22T05:00:00-07:00"
        before = deepcopy((previous, current))
        result = h.compare_receive_captures(previous, current, NOW)
        self.assertEqual(result["changes"], [])
        self.assertEqual(result["unchanged_receive_count"], 1)
        self.assertEqual((previous, current), before)
        self.assertFalse(result["new_external_funding_certified"])
        for value in (ACCOUNT, IDENT, "[PRIVATE_NOTE]", "[PRIVATE_EMAIL]"):
            self.assertNotIn(value, json.dumps(result))

    def test_added_and_missing_events_do_not_mean_new_funding_or_deletion(self):
        previous, current = self.captures()
        current["pages"] = [page([transaction(SECOND)])]
        result = h.compare_receive_captures(previous, current, NOW)
        self.assertCountEqual([c["classification"] for c in result["changes"]],
            ["NEWLY_OBSERVED_NOT_NEW_FUNDING", "NOT_OBSERVED_IN_CURRENT_CAPTURE"])
        self.assertFalse(result["missing_means_deleted"])
        self.assertFalse(result["balances_adjusted"])

    def test_status_changes_never_count_as_another_deposit(self):
        for old, new in (("pending", "completed"), ("completed", "pending"),
                         ("pending", "failed"), ("completed", "new_status")):
            previous, current = self.captures()
            previous["pages"][0]["response"]["data"][0]["status"] = old
            current["pages"][0]["response"]["data"][0]["status"] = new
            result = h.compare_receive_captures(previous, current, NOW)
            self.assertEqual(result["previous_receive_count"], 1)
            self.assertEqual(result["current_receive_count"], 1)
            self.assertEqual(result["changes"][0]["classification"], "STATUS_CHANGED_NOT_NEW_FUNDING")

    def test_material_record_changes_take_precedence_over_status_change(self):
        for field, changes in (("asset", {"amount": {"amount": "0.00005", "currency": "ETH"}}),
                               ("quantity_reported", {"amount": {"amount": "0.00006", "currency": "BTC"}}),
                               ("source_event_timestamp_utc", {"created_at": "2026-10-22T13:00:00Z"})):
            previous, current = self.captures()
            current["pages"][0]["response"]["data"][0].update(**changes, status="pending")
            row = h.compare_receive_captures(previous, current, NOW)["changes"][0]
            self.assertEqual(row["classification"], "CONFLICTING_RECEIVE_RECORD")
            self.assertEqual(row["changed_fields"], [field])

    def test_different_accounts_equal_or_reversed_capture_times_rejected(self):
        previous, current = self.captures()
        for stamp in (previous["captured_at"], "2026-10-23T08:00:00Z"):
            c = deepcopy(current); c["captured_at"] = stamp
            with self.assertRaises(HistoryError): h.compare_receive_captures(previous, c, NOW)
        current["account_id"] = SECOND
        current["pages"][0]["response"]["data"][0]["resource_path"] = PATH.replace(ACCOUNT, SECOND) + "/" + IDENT
        with self.assertRaises(HistoryError): h.compare_receive_captures(previous, current, NOW)

    def test_incomplete_prior_capture_cannot_be_used_as_a_baseline(self):
        previous, current = self.captures()
        previous["pages"][0] = page([transaction()], next_cursor=IDENT)
        with self.assertRaises(HistoryError): h.compare_receive_captures(previous, current, NOW)
        previous["pages"] = [page([])]
        current["pages"] = [page([])]
        result = h.compare_receive_captures(previous, current, NOW)
        self.assertEqual(result["changes"], [])
        self.assertEqual(result["unchanged_receive_count"], 0)

    def test_cli_comparison_uses_private_baseline_and_preserves_old_mode(self):
        previous, current = self.captures()
        b = bundle(); b["history"] = current
        self.assertNotIn("receive_history_comparison", h.review_bundle(b, NOW))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_private(root / "previous", previous)
            write_private(root / "bundle", b)
            cmd = [sys.executable, "-m", "scripts.coinbase_deposit_history", "--input", str(root / "bundle"),
                   "--previous-history", str(root / "previous"), "--output", str(root / "result"),
                   "--at", NOW.isoformat()]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(read_private(root / "result")["receive_history_comparison"]["unchanged_receive_count"], 1)
            (root / "previous").chmod(0o644)
            cmd[cmd.index("--output") + 1] = str(root / "rejected")
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertFalse((root / "rejected").exists())
            self.assertEqual(run.stdout.strip(), "DEPOSIT_HISTORY_PRIVATE_REVIEW_REJECTED")


if __name__ == "__main__":
    unittest.main()
