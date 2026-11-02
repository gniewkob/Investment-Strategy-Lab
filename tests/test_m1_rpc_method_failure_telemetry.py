"""Synthetic offline tests: additive RPC failure telemetry, no real network."""
import json
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

from scripts import operational_read_only as rpc
from scripts import autonomous_portfolio as supervisor
from scripts import unattended_acceptance as collector
from scripts.operational_read_only import read_private

PRIVATE = "0x" + "7" * 40
NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)


class Response(BytesIO):
    status = 200

    def geturl(self):
        return rpc.RPC_URLS[1]


class MethodFailureTelemetryTests(unittest.TestCase):
    def test_only_within_explicit_capture_scope(self):
        self.assertIsNone(rpc.rpc_failure_metadata_snapshot())
        with rpc.capture_rpc_metadata():
            data = rpc.rpc_failure_metadata_snapshot()
            self.assertEqual(data["events"], [])
            self.assertFalse(data["truncated"])
            self.assertEqual(data["mode"], "SCOPED_RPC_METHOD_FAILURE_METADATA_V1")
        self.assertIsNone(rpc.rpc_failure_metadata_snapshot())

    def test_http403_captures_exact_method_and_code_without_secrets(self):
        def forbidden(req, timeout):
            raise HTTPError(PRIVATE, 403, "secret " + PRIVATE,
                            {"X-Token": PRIVATE}, None)
        with rpc.capture_rpc_metadata():
            with self.assertRaises(rpc.ReadOnlyError):
                rpc.rpc_read(1, "eth_getLogs",
                             [{"address": PRIVATE, "topics": [PRIVATE]}],
                             opener=forbidden, sleep=lambda _: self.fail("unexpected retry"))
            result = rpc.rpc_failure_metadata_snapshot()
            counters = rpc.rpc_metadata_snapshot()["chains"]["1"]
        self.assertEqual(result["events"], [{
            "chain_id": 1, "method": "eth_getLogs",
            "failure_category": "RPC_HTTP_FAILURE", "http_status": 403,
            "retry_policy": "NOT_ELIGIBLE", "attempt": 1
        }])
        self.assertEqual(counters["requests"], 1)
        self.assertEqual(counters["http_other"], 1)
        self.assertEqual(counters["retries"], 0)
        self.assertNotIn(PRIVATE, json.dumps(result))
        self.assertNotIn("secret", json.dumps(result))

    def test_http413_same_no_retry_policy(self):
        def fail(req, timeout):
            raise HTTPError(req.full_url, 413, PRIVATE, {}, None)
        with rpc.capture_rpc_metadata():
            with self.assertRaises(rpc.ReadOnlyError):
                rpc.rpc_read(1, "eth_getLogs", [],
                             opener=fail, sleep=lambda _: self.fail("no retry"))
            events = rpc.rpc_failure_metadata_snapshot()["events"]
        self.assertEqual(events[0]["http_status"], 413)
        self.assertEqual(events[0]["retry_policy"], "NOT_ELIGIBLE")

    def test_429_retry_keeps_existing_budget_and_v1_counter(self):
        attempts = []
        def limited(req, timeout):
            attempts.append(1)
            if len(attempts) == 1:
                raise HTTPError(req.full_url, 429, PRIVATE, {}, None)
            return Response(b'{"jsonrpc":"2.0","id":1,"result":"0x1"}')
        with rpc.capture_rpc_metadata():
            result = rpc.rpc_read(1, "eth_chainId", [], opener=limited,
                                  sleep=lambda _: None)
            events = rpc.rpc_failure_metadata_snapshot()["events"]
            old = rpc.rpc_metadata_snapshot()["chains"]["1"]
        self.assertEqual(result, "0x1")
        self.assertEqual(len(attempts), 2)
        self.assertEqual(events[0]["retry_policy"], "RETRY_ELIGIBLE")
        self.assertEqual(events[0]["http_status"], 429)
        self.assertEqual(old["http_429"], 1)
        self.assertEqual(old["http_200"], 1)
        self.assertEqual(old["retries"], 1)

    def test_http_other_response_records_non_200_code(self):
        class NotOkay(Response):
            status = 422
        def response(req, timeout):
            return NotOkay(b"private response " + PRIVATE.encode())
        with rpc.capture_rpc_metadata():
            with self.assertRaises(rpc.ReadOnlyError):
                rpc.rpc_read(1, "eth_chainId", [], opener=response)
            events = rpc.rpc_failure_metadata_snapshot()["events"]
        self.assertEqual(events[0]["http_status"], 422)
        self.assertEqual(events[0]["failure_category"], "RPC_UNEXPECTED_RESPONSE")
        self.assertNotIn(PRIVATE, json.dumps(events))

    def test_network_errors_are_bounded_to_three_attempts(self):
        def network(req, timeout):
            raise URLError(PRIVATE)
        with rpc.capture_rpc_metadata():
            with self.assertRaises(rpc.ReadOnlyError):
                rpc.rpc_read(1, "eth_chainId", [], opener=network, sleep=lambda _: None)
            events = rpc.rpc_failure_metadata_snapshot()["events"]
            old = rpc.rpc_metadata_snapshot()["chains"]["1"]
        self.assertEqual([e["retry_policy"] for e in events],
                         ["RETRY_ELIGIBLE", "RETRY_ELIGIBLE", "NOT_ELIGIBLE"])
        self.assertEqual([e["attempt"] for e in events], [1, 2, 3])
        self.assertEqual(old["network_errors"], 3)
        self.assertEqual(old["retries"], 2)

    def test_rpc_upstream_error_code_and_body_not_copied(self):
        def upstream(req, timeout):
            return Response(json.dumps({"id": 1, "error": {
                "code": -32603, "message": PRIVATE
            }}).encode())
        with rpc.capture_rpc_metadata():
            with self.assertRaises(rpc.ReadOnlyError):
                rpc.rpc_read(1, "eth_getLogs", [], opener=upstream)
            events = rpc.rpc_failure_metadata_snapshot()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["failure_category"], "RPC_UPSTREAM_ERROR")
        self.assertEqual(events[0]["http_status"], 200)
        self.assertNotIn(PRIVATE, json.dumps(events))

    def test_invalid_json_does_not_include_untrusted_response(self):
        def corrupted(req, timeout):
            return Response(PRIVATE.encode())
        with rpc.capture_rpc_metadata():
            with self.assertRaises(rpc.ReadOnlyError):
                rpc.rpc_read(1, "eth_chainId", [], opener=corrupted)
            events = rpc.rpc_failure_metadata_snapshot()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["failure_category"], "RPC_INVALID_RESPONSE")
        self.assertIsNone(events[0]["http_status"])
        self.assertNotIn(PRIVATE, json.dumps(events))

    def test_success_does_not_produce_failure_event(self):
        def successful(req, timeout):
            return Response(b'{"jsonrpc":"2.0","id":1,"result":"0x1"}')
        with rpc.capture_rpc_metadata():
            rpc.rpc_read(1, "eth_chainId", [], opener=successful)
            self.assertEqual(rpc.rpc_failure_metadata_snapshot()["events"], [])
            self.assertEqual(rpc.rpc_metadata_snapshot()["chains"]["1"]["http_200"], 1)

    def test_refuses_disallowed_methods_without_logging(self):
        with rpc.capture_rpc_metadata():
            with self.assertRaises(rpc.ReadOnlyError):
                rpc.rpc_read(1, "eth_sendRawTransaction", [PRIVATE],
                             opener=lambda *a, **kw: self.fail("no outbound request"))
            self.assertEqual(rpc.rpc_failure_metadata_snapshot()["events"], [])
            self.assertEqual(rpc.rpc_metadata_snapshot()["chains"]["1"]["requests"], 0)

    def test_allowlist_prevents_persisting_untrusted_category_or_method(self):
        with rpc.capture_rpc_metadata():
            rpc._rpc_failure_note(1, "eth_logs_" + PRIVATE, PRIVATE, 400)
            rpc._rpc_failure_note(1, "eth_getLogs", PRIVATE, 400)
            rpc._rpc_failure_note(1, "eth_getLogs", "RPC_HTTP_FAILURE",
                                  status=5999, attempt=1)
            events = rpc.rpc_failure_metadata_snapshot()["events"]
        self.assertEqual(len(events), 1)
        self.assertIsNone(events[0]["http_status"])
        self.assertNotIn(PRIVATE, json.dumps(events))

    def test_event_limit_with_overflow_flag_and_immutable_snapshot(self):
        with rpc.capture_rpc_metadata():
            for _ in range(40):
                rpc._rpc_failure_note(1, "eth_getLogs", "RPC_HTTP_FAILURE", 403)
            data = rpc.rpc_failure_metadata_snapshot()
            self.assertEqual(len(data["events"]), 32)
            self.assertTrue(data["truncated"])
            data["events"][0]["http_status"] = 999
            self.assertEqual(rpc.rpc_failure_metadata_snapshot()["events"][0]["http_status"], 403)

    def test_nested_capture_has_isolated_context(self):
        with rpc.capture_rpc_metadata():
            rpc._rpc_failure_note(1, "eth_getLogs", "RPC_HTTP_FAILURE", 403)
            with rpc.capture_rpc_metadata():
                self.assertEqual(rpc.rpc_failure_metadata_snapshot()["events"], [])
            self.assertEqual(len(rpc.rpc_failure_metadata_snapshot()["events"]), 1)

    def test_private_supervisor_report_additive_and_old_schema_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = {"credentials_file": "synthetic", "portfolio_id": "synthetic",
                      "watchlist_file": None}
            def synthetic_exchange(_):
                # No network: exercise persistence while the capture context is active.
                rpc._rpc_failure_note(1, "eth_getLogs", "RPC_HTTP_FAILURE", 403)
                return []
            with patch.object(supervisor, "exchange_accounts",
                              side_effect=synthetic_exchange):
                result = supervisor.cycle(config, root, lambda: NOW,
                    signer_factory=lambda _: None, client_factory=lambda *a: None,
                    market_reader=lambda now: {}, fx_reader=lambda now: {})
            events = result["rpc_failure_diagnostics"]["events"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["method"], "eth_getLogs")
            self.assertEqual(events[0]["http_status"], 403)
            self.assertEqual(result["rpc_diagnostics"]["mode"],
                             "SCOPED_RPC_TRANSPORT_METADATA_V1")
            self.assertEqual(result["financial_operations"], 0)
            saved = read_private(root / "portfolio.json")
            self.assertEqual(saved["rpc_failure_diagnostics"],
                             result["rpc_failure_diagnostics"])
            self.assertEqual(set(saved["rpc_diagnostics"]["chains"]["1"]),
                             set(rpc.RPC_COUNTERS))
            existing = collector.transport_metadata(saved)
            self.assertIsNotNone(existing)
            self.assertEqual(existing["1"]["http_other"], 0)


if __name__ == "__main__":
    unittest.main()
