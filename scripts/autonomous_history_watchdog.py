"""Private local freshness watchdog; never reads credentials or account captures."""
import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess

from scripts.autonomous_coinbase_history import atomic_private, require
from scripts.coinbase_read_only_history import _time
from scripts.operational_read_only import read_private
from scripts import ntfy_notifications

MODE = "PRIVATE_HISTORY_WATCHDOG_V1"


def check_health(directory, now):
    try:
        health = read_private(Path(directory) / "health.json")
        require(type(health.get("financial_operations")) is int and health["financial_operations"] == 0)
        checked = _time(health.get("checked_at_utc"))
        require(checked <= now + timedelta(seconds=5))
        if health.get("status") == "UNAVAILABLE":
            return "UNAVAILABLE"
        require(health.get("status") == "HISTORY_READ_OK")
        expires = _time(health.get("expires_at_utc"))
        require(checked < expires <= checked + timedelta(minutes=15))
        return "HEALTHY" if now < expires and now - checked <= timedelta(minutes=15) else "STALE"
    except (ValueError, TypeError, KeyError, OSError, OverflowError):
        return "INVALID_OR_MISSING"


def native_notify(status):
    message = ("Odczyt historii Coinbase wznowiony." if status == "HEALTHY" else
               "Odczyt historii Coinbase jest niedostępny lub nieaktualny. Sprawdź lokalny status.")
    script = 'display notification "' + message + '" with title "Investment Strategy Lab"'
    subprocess.run(["osascript", "-e", script], check=True, timeout=5,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_check(directory, now, *, notify=native_notify):
    directory = Path(directory)
    current = check_health(directory, now)
    marker = directory / "watchdog.json"
    previous = None
    if os.path.lexists(marker):
        saved = read_private(marker)
        require(saved.get("mode") == MODE and saved.get("status") in {
            "HEALTHY", "UNAVAILABLE", "STALE", "INVALID_OR_MISSING"})
        previous = saved["status"]
    sent = current != previous and (current != "HEALTHY" or previous is not None)
    if sent:
        notify(current)
    atomic_private(marker, {"mode": MODE, "status": current, "checked_at_utc": now.isoformat()})
    return {"status": current, "notification_invoked": sent, "financial_operations": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private local Coinbase history freshness watchdog")
    parser.add_argument("--state-directory", required=True)
    parser.add_argument("--ntfy-config", help="Private ntfy configuration; enables iOS delivery")
    args = parser.parse_args(argv)
    try:
        notify = (ntfy_notifications.notifier(args.ntfy_config, "history", native_notify)
                  if args.ntfy_config else native_notify)
        result = run_check(args.state_directory, datetime.now(timezone.utc), notify=notify)
        print("HISTORY_WATCHDOG_" + result["status"])
        return 0 if result["status"] == "HEALTHY" else 2
    except Exception:
        print("HISTORY_WATCHDOG_CHECK_FAILED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
