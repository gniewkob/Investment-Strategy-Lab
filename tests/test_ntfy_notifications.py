"""Synthetic topic and health metadata only; no real network or account access."""
from contextlib import redirect_stdout
from datetime import timedelta
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

from scripts import ntfy_notifications as n
from scripts import autonomous_history_watchdog as h
from scripts import autonomous_portfolio as p
from scripts.autonomous_coinbase_history import atomic_private
from scripts.operational_read_only import read_private
from tests.test_coinbase_deposit_history import NOW

TOPIC = "isl-" + "synthetic" * 4


class NtfyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = self.root / "ntfy.json"
        atomic_private(self.config, {"topic": TOPIC})

    def opener(self, **changes):
        response = Mock()
        response.status = 200
        response.geturl.return_value = n.SERVER + "/" + TOPIC
        response.read.return_value = json.dumps({"id": "synthetic-id", "event": "message",
                                                "topic": TOPIC, **changes}).encode()
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        return opener

    def test_contract_and_fixed_health_only_payload(self):
        for status in sorted(n.STATUSES):
            with self.subTest(status=status):
                opener = self.opener()
                n.publish(self.config, "portfolio", status, opener=opener)
                args, kwargs = opener.open.call_args
                request = args[0]
                self.assertEqual(request.get_method(), "POST")
                self.assertEqual(request.full_url, n.SERVER + "/" + TOPIC)
                self.assertEqual(kwargs, {"timeout": 8})
                self.assertNotIn(TOPIC, request.data.decode())
                self.assertEqual(request.get_header("Priority"),
                                 "default" if status in {"HEALTHY", "OBSERVATION_OK"} else "high")

    def test_rejects_untrusted_events_before_network(self):
        opener = self.opener()
        for source, status in (("[ACCOUNT_ID]", "STALE"), ("portfolio", "[PRIVATE_ERROR]")):
            with self.assertRaises(n.NotificationError):
                n.publish(self.config, source, status, opener=opener)
        opener.open.assert_not_called()

    def test_private_config_validation_and_symlink(self):
        for topic in ("public-topic", "isl-" + "a" * 32 + "/json", "isl-" + "a" * 32 + "?x=y"):
            atomic_private(self.config, {"topic": topic})
            with self.assertRaisesRegex(n.NotificationError, "^NTFY_CONFIG_REJECTED$"):
                n.load_config(self.config)
        atomic_private(self.config, {"topic": TOPIC})
        self.config.chmod(0o644)
        with self.assertRaises(n.NotificationError): n.load_config(self.config)
        self.config.chmod(0o600)
        link = self.root / "link.json"
        link.symlink_to(self.config)
        with self.assertRaises(n.NotificationError): n.load_config(link)

    def test_init_exclusive_private_outside_git(self):
        target = self.root / "new.json"
        n.initialize(target)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertTrue(n.load_config(target).startswith("isl-"))
        with self.assertRaises(ValueError): n.initialize(target)
        (self.root / ".git").mkdir()
        with self.assertRaises(n.NotificationError): n.initialize(self.root / "forbidden.json")

    def test_failures_redacted_and_invalid_ack_rejected(self):
        opener = self.opener()
        opener.open.side_effect = RuntimeError(n.SERVER + "/" + TOPIC)
        with self.assertRaisesRegex(n.NotificationError, "^NTFY_DELIVERY_FAILED$"):
            n.publish(self.config, "history", "STALE", opener=opener)
        for changes in ({"event": "open"}, {"topic": "wrong"}, {"id": ""}):
            with self.assertRaises(n.NotificationError):
                n.publish(self.config, "history", "STALE", opener=self.opener(**changes))
        for field, value in (("status", 429), ("geturl", "https://example.invalid/"),
                             ("read", b"x" * 4097)):
            opener = self.opener()
            response = opener.open.return_value.__enter__.return_value
            if field == "status": response.status = value
            else: getattr(response, field).return_value = value
            with self.assertRaises(n.NotificationError):
                n.publish(self.config, "history", "STALE", opener=opener)

    def test_no_proxy_or_redirect_and_cli_redaction(self):
        with self.assertRaises(n.NotificationError):
            n.NoRedirect().redirect_request(None, None, 302, None, None, "https://example.invalid")
        opener = self.opener()
        with patch.object(n, "build_opener", return_value=opener) as build:
            n.publish(self.config, "history", "STALE")
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], n.NoRedirect)
        output = io.StringIO()
        with patch.object(n, "publish", side_effect=RuntimeError(TOPIC)), redirect_stdout(output):
            self.assertEqual(n.main(["--config", str(self.config), "--test"]), 2)
        self.assertEqual(output.getvalue(), "NTFY_OPERATION_FAILED\n")

    def test_remote_primary_and_native_failure_does_not_block_ios(self):
        native = Mock(side_effect=subprocess.CalledProcessError(1, "osascript"))
        with patch.object(n, "publish") as publish:
            n.notifier(self.config, "history", native)("STALE")
        publish.assert_called_once_with(self.config, "history", "STALE")
        native.assert_called_once_with("STALE")

    def test_remote_failure_keeps_local_notification_and_remains_retryable(self):
        native = Mock()
        with patch.object(n, "publish", side_effect=n.NotificationError("NTFY_DELIVERY_FAILED")):
            with self.assertRaises(n.NotificationError):
                n.notifier(self.config, "history", native)("STALE")
        native.assert_called_once_with("STALE")

    def test_cli_test_success_and_history_cli_wires_ntfy(self):
        output = io.StringIO()
        with patch.object(n, "publish") as publish, redirect_stdout(output):
            self.assertEqual(n.main(["--config", str(self.config), "--test"]), 0)
        publish.assert_called_once_with(str(self.config), "portfolio", "OBSERVATION_OK", test=True)
        self.assertEqual(output.getvalue(), "NTFY_SERVER_ACCEPTED_TEST\n")
        with patch.object(n, "publish") as publish, patch.object(h, "native_notify"), redirect_stdout(io.StringIO()):
            self.assertEqual(h.main(["--state-directory", str(self.root),
                                     "--ntfy-config", str(self.config)]), 2)
        publish.assert_called_once_with(str(self.config), "history", "INVALID_OR_MISSING")

    def test_both_watchdogs_retry_remote_failure_then_deduplicate_and_recover(self):
        for source in ("history", "portfolio"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                def check():
                    if source == "history":
                        return h.run_check(root, NOW, notify=n.notifier(self.config, source, Mock()))
                    return p.check_health(root, NOW, Mock(), ntfy_config=self.config)
                with patch.object(n, "publish", side_effect=n.NotificationError("NTFY_DELIVERY_FAILED")):
                    with self.assertRaises(n.NotificationError): check()
                self.assertFalse((root / "watchdog.json").exists())
                with patch.object(n, "publish") as publish:
                    check(); check()
                    self.assertEqual(publish.call_count, 1)
                    atomic_private(root / "health.json", {
                        "status": "HISTORY_READ_OK" if source == "history" else "OBSERVATION_OK",
                        "financial_operations": 0, "checked_at_utc": NOW.isoformat(),
                        "expires_at_utc": (NOW + timedelta(minutes=15)).isoformat()})
                    check(); check()
                    self.assertEqual(publish.call_count, 2)
                    self.assertEqual(read_private(root / "watchdog.json")[
                        "status" if source == "history" else "signature"],
                        "HEALTHY" if source == "history" else "OBSERVATION_OK:")


if __name__ == "__main__":
    unittest.main()
