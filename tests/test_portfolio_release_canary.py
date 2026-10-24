"""Synthetic local release preflight/canary; never uses real account data or RPC."""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import history_coverage as c
from scripts import portfolio_release_canary as m
from scripts.operational_read_only import read_private, write_private
from scripts.private_wallet_chain_monitor import _private_config

NOW = datetime(2026, 10, 24, 13, 0, tzinfo=timezone.utc)
SHA = "a" * 40
ADDRESS = "0x" + "b" * 40
TOKEN = "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf"
PORTFOLIO = "00000000-0000-4000-8000-000000000000"
KEY = "chain_research_8453"


def no_git(expected, root):
    return expected == SHA


def history_source():
    return {KEY: {"status": "OK", "data": {
        "wallets": [{
            "wallet_label": "research", "chain_id": 8453,
            "source_block_number": 1000,
            "history": {"status": "COMPLETE_REQUESTED_TOKEN_RANGE",
                        "from_block": 1, "to_block": 1000}
        }]
    }}}


class LocalReleaseTests(unittest.TestCase):
    def setup(self, directory):
        root = Path(directory) / "private"
        root.mkdir(mode=0o700)
        credentials = root / "credentials"
        credentials.mkdir(mode=0o700)
        state = root / "portfolio-state"
        state.mkdir(mode=0o700)
        watch = root / "watch.json"
        config = root / "config.json"
        key = credentials / "key.json"
        write_private(key, {"synthetic": "PRIVATE_TEST_SECRET_MUST_NOT_LEAK"})
        write_private(watch, {
            "mode": "PRIVATE_WALLET_READ_ONLY",
            "watch": [{
                "label": "research", "chain_id": 8453,
                "address": ADDRESS,
                "verified_token_contracts": [TOKEN]
            }]
        })
        write_private(config, {
            "credentials_file": str(key), "portfolio_id": PORTFOLIO,
            "watchlist_file": str(watch), "state_directory": str(state),
            "interval_seconds": 900
        })
        return config, key, watch, state

    def make_reports(self, watch, state, *, status="OBSERVATION_OK",
                     checked=NOW, gaps=False):
        entries = _private_config(read_private(watch))
        cov = c.advance(None, entries, history_source())
        if gaps:
            cov = c.advance(cov, entries, {KEY: {"status": "OK", "data": {
                "wallets": [{"wallet_label": "research", "chain_id": 8453,
                             "source_block_number": 3000,
                             "history": {"status": "COMPLETE_REQUESTED_TOKEN_RANGE",
                                         "from_block": 2001, "to_block": 3000}}]
            }}})
        report = {
            "mode": "PRIVATE_AUTONOMOUS_PORTFOLIO_V1",
            "checked_at_utc": checked.isoformat(),
            "expires_at_utc": (checked + timedelta(minutes=30)).isoformat(),
            "status": status,
            "alerts": ["HISTORY_COVERAGE_GAP"] if gaps else [],
            "financial_operations": 0,
            "sources": {"exchange": {"status": "OK"},
                        "market": {"status": "OK"},
                        "usdpln": {"status": "OK"},
                        KEY: {"status": "OK"}},
            "history_coverage": cov,
            "history_backfill": {"status": "NO_ELIGIBLE_GAP",
                                 "recovered_block_count": 0, "events_saved": 0,
                                 "financial_operations": 0},
            "holdings": [{"private_balance": "4096.12345"}],
        }
        write_private(state / "portfolio.json", report)
        write_private(state / "health.json", {k: report[k] for k in (
            "status", "checked_at_utc", "expires_at_utc",
            "alerts", "financial_operations")})
        return report

    def audit(self, config, phase, now=NOW):
        return m.inspect(config, SHA, phase, now, git_probe=no_git)

    def test_preflight_is_local_redacted_and_no_private_file_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            config, key, watch, state = self.setup(d)
            files_before = sorted(str(p) for p in Path(d).rglob("*"))
            result = self.audit(config, "before")
            self.assertEqual(result["result"], "READY_FOR_CONTROLLED_READ_ONLY_CANARY")
            self.assertTrue(result["source_commit_matches_clean_checkout"])
            self.assertFalse(result["credentials_opened"])
            self.assertFalse(result["local_daemon_running_verified"])
            self.assertEqual(result["network_requests"], 0)
            self.assertEqual(result["financial_operations"], 0)
            self.assertNotIn(ADDRESS, json.dumps(result))
            self.assertNotIn("PRIVATE_TEST_SECRET_MUST_NOT_LEAK", json.dumps(result))
            self.assertNotIn(str(config), json.dumps(result))
            self.assertEqual(files_before, sorted(str(p) for p in Path(d).rglob("*")))

    def test_after_validated_but_not_remote_provider_attested(self):
        with tempfile.TemporaryDirectory() as d:
            config, key, watch, state = self.setup(d)
            self.make_reports(watch, state)
            result = self.audit(config, "after")
            self.assertEqual(result["result"], "LOCAL_METADATA_CANARY_OK_NOT_PROVIDER_ATTESTED")
            self.assertFalse(result["provider_response_authenticated_by_canary"])
            self.assertEqual(result["observed_source_count"], 4)
            self.assertEqual(result["gap_range_count"], 0)
            self.assertEqual(result["last_cycle_status"], "OBSERVATION_OK")
            self.assertEqual(result["last_backfill_status"], "NO_ELIGIBLE_GAP")
            self.assertNotIn(ADDRESS, json.dumps(result))
            self.assertNotIn("4096.12345", json.dumps(result))

    def test_gap_or_partial_yields_partial_without_falsifying_success(self):
        with tempfile.TemporaryDirectory() as d:
            config, key, watch, state = self.setup(d)
            self.make_reports(watch, state, status="PARTIAL", gaps=True)
            result = self.audit(config, "after")
            self.assertEqual(result["result"], "LOCAL_METADATA_CANARY_PARTIAL")
            self.assertTrue(result["gap_or_overflow_detected"])
            self.assertEqual(result["gap_range_count"], 1)

    def test_missing_outputs_mismatched_health_and_stale_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            config, key, watch, state = self.setup(d)
            with self.assertRaises(m.ReleaseRejected):
                self.audit(config, "after")
            self.make_reports(watch, state, checked=NOW-timedelta(hours=2))
            with self.assertRaises(m.ReleaseRejected):
                self.audit(config, "after")
        with tempfile.TemporaryDirectory() as d:
            config, key, watch, state = self.setup(d)
            self.make_reports(watch, state)
            state.joinpath("health.json").unlink()
            write_private(state/"health.json", {"status": "UNAVAILABLE",
                 "checked_at_utc": NOW.isoformat(), "expires_at_utc": (NOW+timedelta(minutes=30)).isoformat(),
                 "alerts": [], "financial_operations": 0})
            with self.assertRaises(m.ReleaseRejected):
                self.audit(config, "after")

    def test_fake_complete_net_worth_or_bad_scope_cannot_certify(self):
        with tempfile.TemporaryDirectory() as d:
            config, key, watch, state = self.setup(d)
            p = self.make_reports(watch, state)
            p["history_coverage"]["complete_chain_history_certified"] = True
            (state/"portfolio.json").unlink()
            write_private(state/"portfolio.json", p)
            with self.assertRaises(m.ReleaseRejected):
                self.audit(config, "after")

    def test_untrusted_private_symlinks_and_permissions_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            config, key, watch, state = self.setup(d)
            key.chmod(0o644)
            with self.assertRaises(m.ReleaseRejected):
                self.audit(config, "before")
            key.chmod(0o600)
            watch_link = Path(d)/"watch-symlink"
            watch_link.symlink_to(watch)
            conf = read_private(config)
            conf["watchlist_file"] = str(watch_link)
            config.unlink()
            write_private(config, conf)
            with self.assertRaises(m.ReleaseRejected):
                self.audit(config, "before")

    def test_false_healthy_reports_are_never_accepted(self):
        cases = (
            lambda report: report["sources"]["usdpln"].update(status="UNAVAILABLE"),
            lambda report: report["history_backfill"].update(status="UNAVAILABLE"),
            lambda report: report["history_backfill"].update(
                status="RECOVERED_WINDOW", recovered_block_count=0),
            lambda report: report["sources"].pop(KEY),
            lambda report: report["history_coverage"].update(
                latest_source_incomplete=True),
        )
        for mutate in cases:
            with self.subTest(case=repr(mutate)), tempfile.TemporaryDirectory() as d:
                config, key, watch, state = self.setup(d)
                report = self.make_reports(watch, state)
                mutate(report)
                (state/"portfolio.json").unlink()
                write_private(state/"portfolio.json", report)
                with self.assertRaises(m.ReleaseRejected):
                    self.audit(config, "after")

    def test_healthy_claim_cannot_hide_existing_gap(self):
        with tempfile.TemporaryDirectory() as d:
            config, key, watch, state = self.setup(d)
            self.make_reports(watch, state, status="OBSERVATION_OK", gaps=True)
            with self.assertRaises(m.ReleaseRejected):
                self.audit(config, "after")

    def test_wrong_commit_rejected_before_reading_private_data(self):
        with tempfile.TemporaryDirectory() as d:
            config, key, watch, state = self.setup(d)
            probe_calls = []
            def no(expected, repo):
                probe_calls.append(expected)
                return False
            with self.assertRaises(m.ReleaseRejected):
                m.inspect(config, SHA, "before", NOW, git_probe=no)
            self.assertEqual(probe_calls, [SHA])

    def test_cli_fixed_error_redacts_secret_and_path(self):
        output = StringIO()
        with redirect_stdout(output):
            with patch.object(m, "inspect", side_effect=RuntimeError("secret /very/private/path")):
                code = m.main(["--config", "/very/private/path",
                               "--expected-commit", SHA, "--phase", "after"])
        self.assertEqual(code, 2)
        self.assertEqual(output.getvalue().strip(), "PRIVATE_RELEASE_CANARY_REJECTED")

    def test_local_git_expected_sha_and_worktree_clean_contract(self):
        repo = Path(__file__).resolve().parents[1]
        actual = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        self.assertTrue(m.local_code_attestation(actual, repo))
        with self.assertRaises(m.ReleaseRejected):
            m.local_code_attestation("f"*40, repo)
        with self.assertRaises(m.ReleaseRejected):
            m.local_code_attestation("notsha", repo)


if __name__ == "__main__":
    unittest.main()
