"""Synthetic health metadata only; notification calls are mocked."""
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from scripts import autonomous_history_watchdog as w
from scripts.autonomous_coinbase_history import atomic_private
from scripts.operational_read_only import read_private
from tests.test_coinbase_deposit_history import NOW


def health(**changes):
    return {"status": "HISTORY_READ_OK", "checked_at_utc": NOW.isoformat(),
        "expires_at_utc": (NOW + timedelta(minutes=15)).isoformat(), "financial_operations": 0, **changes}


class WatchdogTests(unittest.TestCase):
    def test_fresh_expiry_boundary_and_invalid_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.json"
            atomic_private(path, health())
            self.assertEqual(w.check_health(directory, NOW), "HEALTHY")
            self.assertEqual(w.check_health(directory, NOW + timedelta(minutes=15)), "STALE")
            for changes in ({"financial_operations": True}, {"financial_operations": 1},
                    {"checked_at_utc": (NOW + timedelta(seconds=6)).isoformat()},
                    {"expires_at_utc": (NOW + timedelta(days=1)).isoformat()},
                    {"status": "UNKNOWN"}, {"checked_at_utc": "2026-10-23T12:00:00"}):
                atomic_private(path, health(**changes))
                self.assertEqual(w.check_health(directory, NOW), "INVALID_OR_MISSING")

    def test_quiet_while_healthy_or_unchanged_and_notify_on_failure_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.json"; calls = []
            atomic_private(path, health())
            self.assertFalse(w.run_check(directory, NOW, notify=calls.append)["notification_invoked"])
            self.assertFalse(w.run_check(directory, NOW, notify=calls.append)["notification_invoked"])
            atomic_private(path, health(status="UNAVAILABLE"))
            self.assertTrue(w.run_check(directory, NOW, notify=calls.append)["notification_invoked"])
            self.assertFalse(w.run_check(directory, NOW, notify=calls.append)["notification_invoked"])
            atomic_private(path, health())
            self.assertTrue(w.run_check(directory, NOW, notify=calls.append)["notification_invoked"])
            self.assertEqual(calls, ["UNAVAILABLE", "HEALTHY"])

    def test_stale_process_detected_after_restart_without_reading_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            atomic_private(Path(directory) / "health.json", health())
            (Path(directory) / "checkpoint.json").write_text("[PRIVATE_DATA_MUST_NOT_BE_READ]")
            calls = []
            w.run_check(directory, NOW, notify=calls.append)
            result = w.run_check(directory, NOW + timedelta(minutes=16), notify=calls.append)
            self.assertEqual(result["status"], "STALE")
            self.assertEqual(calls, ["STALE"])
            self.assertEqual(read_private(Path(directory) / "watchdog.json")["status"], "STALE")

    def test_failed_notification_does_not_mark_delivery_and_can_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            def fail(status): raise RuntimeError("synthetic notifier failure")
            with self.assertRaises(RuntimeError): w.run_check(directory, NOW, notify=fail)
            self.assertFalse((Path(directory) / "watchdog.json").exists())
            calls = []
            w.run_check(directory, NOW, notify=calls.append)
            self.assertEqual(calls, ["INVALID_OR_MISSING"])

    def test_insecure_health_is_never_healthy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.json"
            atomic_private(path, health()); path.chmod(0o644)
            self.assertEqual(w.check_health(directory, NOW), "INVALID_OR_MISSING")


if __name__ == "__main__": unittest.main()
