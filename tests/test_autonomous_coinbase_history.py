"""Synthetic transport only: no real key, Coinbase account, HTTP or financial operation."""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import timedelta
from io import StringIO
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import autonomous_coinbase_history as a
from scripts.operational_read_only import read_private, write_private
from tests.test_coinbase_deposit_history import ACCOUNT, SECOND, IDENT, PATH, NOW, transaction, page

PORTFOLIO = "00000000-0000-4000-8000-000000000004"


class Response:
    def __init__(self, url, data, status=200):
        self.url, self.data, self.status = url, data, status
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def geturl(self): return self.url
    def read(self, count): return json.dumps(self.data).encode()[:count]


class Provider:
    def __init__(self):
        self.calls = []
        self.can_trade = False
        self.can_transfer = False
        self.fail = False
        self.status = "pending"
    def open(self, request, timeout):
        self.calls.append(request)
        if self.fail: raise RuntimeError("[PRIVATE_UPSTREAM_DETAILS]")
        if request.full_url == a.HOST + a.PERMISSIONS:
            return Response(request.full_url, {"can_view": True, "can_trade": self.can_trade,
                "can_transfer": self.can_transfer, "portfolio_uuid": PORTFOLIO})
        return Response(request.full_url, page([transaction(status=self.status)])["response"])
    def client(self):
        return a.ReadOnlyClient(ACCOUNT, PORTFOLIO, lambda method, path: "synthetic-token", opener=self.open)


class AutonomousHistoryTests(unittest.TestCase):
    def test_permissions_fail_closed_before_any_history_read(self):
        for field, value in (("can_trade", True), ("can_transfer", True),
                             ("can_trade", 0), ("can_transfer", None)):
            p = Provider(); setattr(p, field, value)
            with self.assertRaises(a.AutonomousHistoryError): a.collect_capture(p.client(), lambda: NOW)
            self.assertEqual(len(p.calls), 1)
            self.assertTrue(p.calls[0].full_url.endswith(a.PERMISSIONS))

    def test_wrong_portfolio_denied(self):
        p = Provider()
        c = a.ReadOnlyClient(ACCOUNT, SECOND, lambda method, path: "synthetic-token", opener=p.open)
        with self.assertRaises(a.AutonomousHistoryError): a.collect_capture(c, lambda: NOW)
        self.assertEqual(len(p.calls), 1)

    def test_client_exposes_only_get_allowlisted_paths_and_sanitizes_errors(self):
        p = Provider(); c = p.client()
        for path in ("/v2/accounts/" + SECOND + "/transactions", "/api/v3/brokerage/orders",
                     "https://example.invalid", PATH + "?type=send"):
            with self.assertRaises(a.AutonomousHistoryError): c.get(path)
        self.assertEqual(p.calls, [])
        a.collect_capture(c, lambda: NOW)
        self.assertTrue(all(r.get_method() == "GET" and r.data is None for r in p.calls))
        p.fail = True
        with self.assertRaisesRegex(a.AutonomousHistoryError, "^AUTONOMOUS_HISTORY_READ_FAILED$"):
            c.get(a.PERMISSIONS)

    def test_http_redirect_wrong_status_json_shape_and_token_rejected(self):
        for status, url, payload in ((302, a.HOST + a.PERMISSIONS, {}),
                (200, "https://example.invalid", {}), (200, a.HOST + a.PERMISSIONS, []),
                (200, a.HOST + a.PERMISSIONS, {"error": "[PRIVATE_DETAILS]"})):
            c = a.ReadOnlyClient(ACCOUNT, PORTFOLIO, lambda method, path: "synthetic-token",
                opener=lambda request, timeout: Response(url, payload, status))
            with self.assertRaises(a.AutonomousHistoryError): c.check_permissions()
        with self.assertRaises(a.AutonomousHistoryError):
            a.NoRedirect().redirect_request(None, None, None, None)
        c = a.ReadOnlyClient(ACCOUNT, PORTFOLIO, lambda method, path: "bad\nheader")
        with self.assertRaises(a.AutonomousHistoryError): c.get(a.PERMISSIONS)

    def test_bounded_cursor_collection_minimizes_raw_provider_data(self):
        calls = []
        def get(request, timeout):
            calls.append(request.full_url)
            if request.full_url.endswith(a.PERMISSIONS):
                return Provider().open(request, timeout)
            if "starting_after" not in request.full_url:
                row = transaction(); row["amount"]["extra"] = "[PRIVATE_NOTE]"
                return Response(request.full_url, page([row], next_cursor=IDENT)["response"])
            return Response(request.full_url, page([], cursor=IDENT)["response"])
        c = a.ReadOnlyClient(ACCOUNT, PORTFOLIO, lambda method, path: "synthetic-token", opener=get)
        capture = a.collect_capture(c, lambda: NOW)
        self.assertEqual(len(capture["pages"]), 2)
        self.assertEqual(len(calls), 3)
        self.assertIn("starting_after=" + IDENT, calls[-1])
        for private in ("[PRIVATE_NOTE]", "[PRIVATE_EMAIL]", "description", "from"):
            self.assertNotIn(private, json.dumps(capture))

    def test_missing_page_cursor_loop_and_proof_challenge_rejected(self):
        for mutation in ("missing", "loop", "proof"):
            class Source:
                account = ACCOUNT
                path = PATH
                def check_permissions(self): pass
                def get(self, path, cursor):
                    r = page([transaction()], cursor=cursor, next_cursor=IDENT)["response"]
                    if mutation == "missing": r["pagination"].pop("next_uri")
                    if mutation == "proof": r["proof_token_required"] = True
                    return r
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                a.collect_capture(Source(), lambda: NOW)

    def test_two_cycles_and_restart_compare_automatically(self):
        p = Provider(); clock = [NOW]; sleeps = []
        def sleep(seconds):
            sleeps.append(seconds); clock[0] += timedelta(seconds=seconds); p.status = "completed"
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()) as output:
            self.assertEqual(a.run_service(p.client(), directory, interval=60, cycles=2,
                                         clock=lambda: clock[0], sleep=sleep), 0)
            saved = read_private(Path(directory) / "checkpoint.json")
            diff = saved["report"]["receive_history_comparison"]
            self.assertEqual(diff["changes"][0]["classification"], "STATUS_CHANGED_NOT_NEW_FUNDING")
            self.assertEqual(sleeps, [60])
            self.assertEqual(saved["report"]["blockchain_evidence_status"], "NOT_CONFIGURED")
            clock[0] += timedelta(seconds=60)
            self.assertEqual(a.run_service(p.client(), directory, cycles=1, clock=lambda: clock[0]), 0)
            saved = read_private(Path(directory) / "checkpoint.json")
            self.assertEqual(saved["report"]["receive_history_comparison"]["unchanged_receive_count"], 1)
            for value in (ACCOUNT, IDENT, "synthetic-token", "[PRIVATE_EMAIL]"):
                self.assertNotIn(value, output.getvalue())
            self.assertFalse(read_private(Path(directory) / "health.json")["full_autonomous_reconciliation_ready"])
            self.assertEqual((Path(directory) / "checkpoint.json").stat().st_mode & 0o777, 0o600)

    def test_failure_preserves_baseline_and_recovers_without_duplicate_funding(self):
        p = Provider(); clock = [NOW]
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()) as output:
            a.run_service(p.client(), directory, cycles=1, clock=lambda: clock[0])
            checkpoint = Path(directory) / "checkpoint.json"
            original = checkpoint.read_bytes()
            p.fail = True; clock[0] += timedelta(seconds=60)
            self.assertEqual(a.run_service(p.client(), directory, cycles=1, clock=lambda: clock[0]), 2)
            self.assertEqual(checkpoint.read_bytes(), original)
            self.assertEqual(read_private(Path(directory) / "health.json")["status"], "UNAVAILABLE")
            p.fail = False; clock[0] += timedelta(seconds=60)
            self.assertEqual(a.run_service(p.client(), directory, cycles=1, clock=lambda: clock[0]), 0)
            self.assertEqual(read_private(checkpoint)["report"]["receive_history_comparison"]["changes"], [])
            self.assertNotIn("[PRIVATE_UPSTREAM_DETAILS]", output.getvalue())

    def test_private_state_symlinks_permissions_corruption_and_lock_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o755)
            with self.assertRaises(ValueError): a.private_directory(root)
            root.chmod(0o700)
            with a.process_lock(root):
                with self.assertRaises(BlockingIOError):
                    with a.process_lock(root): pass
            (root / "source").write_text('{}'); (root / "source").chmod(0o600)
            (root / "target").symlink_to(root / "source")
            with self.assertRaises(ValueError): a.atomic_private(root / "target", {"new": True})
            self.assertEqual((root / "source").read_text(), '{}')
            write_private(root / "checkpoint.json", {"mode": "WRONG"})
            with redirect_stdout(StringIO()):
                self.assertEqual(a.run_service(Provider().client(), root, cycles=1, clock=lambda: NOW), 2)

    def test_live_mode_requires_explicit_flag_before_config_or_credentials(self):
        run = subprocess.run([sys.executable, "-m", "scripts.autonomous_coinbase_history",
            "--config", "/does-not-exist"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout.strip(), "AUTONOMOUS_HISTORY_LIVE_ACCESS_NOT_ENABLED")
        self.assertEqual(run.stderr, "")

    def test_generic_tx_amount_survives_collection_and_legacy_checkpoint_upgrade(self):
        from tests.test_coinbase_deposit_history import capture
        class GenericProvider(Provider):
            def open(self, request, timeout):
                response = super().open(request, timeout)
                if not request.full_url.endswith(a.PERMISSIONS):
                    response.data["data"][0]["type"] = "tx"
                    response.data["data"][0]["amount"]["private_extra"] = "[PRIVATE_NOTE]"
                return response
        p = GenericProvider()
        legacy = capture(); legacy["captured_at"] = (NOW - timedelta(minutes=5)).isoformat()
        legacy["pages"][0]["response"]["data"][0]["type"] = "tx"
        legacy["pages"][0]["response"]["data"][0].pop("amount")
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            a.atomic_private(Path(directory) / "checkpoint.json", {"mode": a.STATE_MODE, "capture": legacy, "report": {}})
            self.assertEqual(a.run_service(p.client(), directory, cycles=1, clock=lambda: NOW), 0)
            saved = read_private(Path(directory) / "checkpoint.json")
            self.assertIn("amount", saved["capture"]["pages"][0]["response"]["data"][0])
            self.assertNotIn("[PRIVATE_NOTE]", json.dumps(saved))
            history = saved["report"]["history"]
            self.assertEqual(history["unclassified_account_events"][0]["quantity_reported"], "0.00005000")
            self.assertEqual(saved["report"]["source_schema_status"], "UNCLASSIFIED_ACCOUNT_EVENTS_PRESENT")
            self.assertFalse(history["unclassified_account_events"][0]["external_funding_certified"])

    @unittest.skipUnless(importlib.util.find_spec("coinbase"), "optional signing SDK not installed")
    def test_real_sdk_signs_get_uri_with_ephemeral_test_key_and_rejects_eddsa(self):
        import jwt
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec, ed25519
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = ec.generate_private_key(ec.SECP256R1())
            pem = key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()).decode()
            write_private(root / "synthetic-key", {"name": "organizations/synthetic/apiKeys/test", "privateKey": pem})
            with redirect_stdout(StringIO()) as output:
                token = a.make_sdk_signer(root / "synthetic-key")("GET", a.PERMISSIONS)
            decoded = jwt.decode(token, key.public_key(), algorithms=["ES256"])
            self.assertEqual(decoded["uri"], "GET api.coinbase.com" + a.PERMISSIONS)
            self.assertEqual(decoded["exp"] - decoded["nbf"], 120)
            self.assertEqual(output.getvalue(), "")
            wrong = ed25519.Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
            write_private(root / "wrong-algorithm", {"name": "organizations/synthetic/apiKeys/test", "privateKey": wrong})
            with self.assertRaises(ValueError): a.make_sdk_signer(root / "wrong-algorithm")


if __name__ == "__main__":
    unittest.main()
