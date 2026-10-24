"""Opt-in health-only ntfy delivery. Private topic never enters logs or Git."""
import argparse
import json
from pathlib import Path
import re
import secrets
import subprocess
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from scripts.operational_read_only import read_private, write_private

SERVER = "https://ntfy.sh"
SOURCES = {"history": "Historia Coinbase", "portfolio": "Monitoring portfela"}
STATUSES = {"HEALTHY", "OBSERVATION_OK", "PARTIAL", "UNAVAILABLE", "STALE", "INVALID_OR_MISSING"}


class NotificationError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NotificationError("NTFY_REDIRECT_REJECTED")


def load_config(path):
    try:
        config = read_private(path)
        topic = config.get("topic")
        if set(config) != {"topic"} or not isinstance(topic, str) or not re.fullmatch(
                r"isl-[A-Za-z0-9_-]{32,96}", topic):
            raise ValueError()
        return topic
    except Exception:
        raise NotificationError("NTFY_CONFIG_REJECTED") from None


def initialize(path):
    """Create only on operator request, in an existing private directory outside Git."""
    path = Path(path)
    if not path.is_absolute() or any((parent / ".git").exists() for parent in path.resolve().parents):
        raise NotificationError("NTFY_PRIVATE_PATH_REQUIRED")
    write_private(path, {"topic": "isl-" + secrets.token_urlsafe(24)})


def publish(config_path, source, status, *, test=False, opener=None):
    """Only fixed messages may leave the host; accept no account data or error text."""
    if source not in SOURCES or status not in STATUSES:
        raise NotificationError("NTFY_EVENT_REJECTED")
    topic = load_config(config_path)
    recovered = status in {"HEALTHY", "OBSERVATION_OK"}
    message = ("Test powiadomień Investment Strategy Lab." if test else
               SOURCES[source] + (": działanie wznowione." if recovered else
               ": wymaga uwagi (" + status + "). Sprawdź lokalny panel."))
    url = SERVER + "/" + topic
    request = Request(url, data=message.encode("utf-8"), method="POST", headers={
        "Content-Type": "text/plain; charset=utf-8", "Title": "Investment Strategy Lab",
        "Priority": "default" if recovered or test else "high",
        "Tags": "test_tube" if test else ("white_check_mark" if recovered else "warning"),
    })
    try:
        client = opener if opener is not None else build_opener(ProxyHandler({}), NoRedirect())
        with client.open(request, timeout=8) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError()
            raw = response.read(4097)
            if len(raw) > 4096:
                raise ValueError()
            result = json.loads(raw)
            if (result.get("event") != "message" or result.get("topic") != topic
                    or not isinstance(result.get("id"), str) or not result["id"]):
                raise ValueError()
    except Exception:
        # HTTP errors can contain the private topic URL. Never propagate them.
        raise NotificationError("NTFY_DELIVERY_FAILED") from None


def notifier(config_path, source, native):
    def notify(status):
        try:
            publish(config_path, source, status)
        finally:
            # Preserve local alerts during an ntfy outage; a failed POST still
            # propagates so the watchdog retries instead of marking delivery.
            try:
                native(status)
            except (OSError, subprocess.SubprocessError):
                pass
    return notify


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private health-only ntfy setup/test")
    parser.add_argument("--config", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--init", action="store_true")
    action.add_argument("--test", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.init:
            initialize(args.config)
            print("NTFY_CONFIG_CREATED")
        else:
            publish(args.config, "portfolio", "OBSERVATION_OK", test=True)
            print("NTFY_SERVER_ACCEPTED_TEST")
        return 0
    except Exception:
        print("NTFY_OPERATION_FAILED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
