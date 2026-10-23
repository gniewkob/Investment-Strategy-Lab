"""Local polling service for read-only Coinbase App history. Live access is opt-in.

No financial execution APIs. Credentials stay in a private operator-managed file;
neither credentials, provider errors nor private records are written to console.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from uuid import uuid4

from scripts.coinbase_deposit_history import (
    CAPTURE_MODE, BUNDLE_MODE, MAX_PAGES, MAX_RECORDS, _uuid, _cursor,
    normalize_receives, review_bundle)
from scripts.operational_read_only import read_private, write_private, MAX_BYTES

HOST = "https://api.coinbase.com"
PERMISSIONS = "/api/v3/brokerage/key_permissions"
STATE_MODE = "PRIVATE_AUTONOMOUS_COINBASE_HISTORY_V1"


class AutonomousHistoryError(ValueError):
    pass


def require(condition):
    if not condition:
        raise AutonomousHistoryError("AUTONOMOUS_HISTORY_REJECTED")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise AutonomousHistoryError("AUTONOMOUS_HISTORY_REDIRECT_REJECTED")


class ReadOnlyClient:
    """The signer receives GET and an allowlisted path; queries never set methods."""
    def __init__(self, account, portfolio, signer, *, opener=None):
        self.account = _uuid(account) if account is not None else None
        self.portfolio = _uuid(portfolio)
        self.path = f"/v2/accounts/{account}/transactions" if account is not None else "/v2/accounts"
        self.signer = signer
        self.opener = opener or build_opener(ProxyHandler({}), NoRedirect()).open

    def get(self, path, cursor=None):
        require(path in (PERMISSIONS, self.path))
        require(cursor is None or path == self.path)
        if cursor is not None:
            _uuid(cursor)
        query = {"limit": "100", "order": "desc"} if path == self.path else {}
        if cursor is not None:
            query["starting_after"] = cursor
        url = HOST + path + ("?" + urlencode(query) if query else "")
        try:
            token = self.signer("GET", path)
            require(isinstance(token, str) and 0 < len(token) <= 8192
                    and all(32 < ord(c) < 127 for c in token))
            request = Request(url, method="GET", headers={
                "Authorization": "Bearer " + token, "Accept": "application/json",
                "User-Agent": "ISL-Read-Only-History/1.0"})
            with self.opener(request, timeout=20) as response:
                require(response.status == 200 and response.geturl() == url)
                raw = response.read(MAX_BYTES + 1)
            require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES)
            obj = json.loads(raw)
            require(isinstance(obj, dict) and not ({"error", "errors"} & set(obj)))
            return obj
        except Exception:
            raise AutonomousHistoryError("AUTONOMOUS_HISTORY_READ_FAILED") from None

    def check_permissions(self):
        obj = self.get(PERMISSIONS)
        require(obj.get("can_view") is True and obj.get("can_trade") is False
                and obj.get("can_transfer") is False
                and obj.get("portfolio_uuid") == self.portfolio)


def collect_capture(client, clock):
    """Fetch bounded pages; rebuild queries rather than following next_uri URLs."""
    client.check_permissions()
    pages = []
    cursor = None
    seen = set()
    count = 0
    for _ in range(MAX_PAGES):
        response = client.get(client.path, cursor)
        rows, pagination = response.get("data"), response.get("pagination")
        require(response.get("proof_token_required") is not True
                and isinstance(rows, list) and len(rows) <= 100 and isinstance(pagination, dict)
                and "next_uri" in pagination)
        count += len(rows)
        require(count <= MAX_RECORDS)
        # Never persist descriptions, counterparties or optional network fields.
        minimized = []
        for row in rows:
            require(isinstance(row, dict))
            item = {k: row[k] for k in (
                "id", "type", "status", "created_at", "resource", "resource_path") if k in row}
            if row.get("type") in {"receive", "tx"}:
                money = row.get("amount")
                require(isinstance(money, dict))
                item["amount"] = {k: money[k] for k in ("amount", "currency") if k in money}
            minimized.append(item)
        clean = {"data": minimized, "pagination": {k: pagination[k] for k in (
            "next_uri", "starting_after", "ending_before", "order", "limit") if k in pagination}}
        pages.append({"request_cursor": cursor, "response": clean})
        require(len(json.dumps(pages).encode()) <= MAX_BYTES // 2)
        next_cursor = _cursor(pagination["next_uri"], client.path)
        if next_cursor is None:
            break
        require(next_cursor not in seen and rows and rows[-1].get("id") == next_cursor)
        seen.add(next_cursor)
        cursor = next_cursor
    else:
        raise AutonomousHistoryError("AUTONOMOUS_HISTORY_PAGE_LIMIT")
    now = clock()
    capture = {"mode": CAPTURE_MODE, "account_id": client.account,
               "captured_at": now.isoformat(), "pages": pages}
    normalize_receives(capture, now)
    return capture


def private_directory(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=False, exist_ok=True)
    s = path.lstat()
    require(stat.S_ISDIR(s.st_mode) and s.st_uid == os.getuid() and not s.st_mode & 0o077)
    return path


@contextmanager
def process_lock(directory):
    fd = os.open(Path(directory) / "service.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        s = os.fstat(fd)
        require(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid() and not s.st_mode & 0o077)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def atomic_private(path, value):
    path = Path(path)
    if os.path.lexists(path):
        read_private(path)  # Validate existing ownership/mode; never replace unsafe state.
    temporary = path.parent / ("pending-" + uuid4().hex + ".json")
    try:
        write_private(temporary, value)
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def run_cycle(client, directory, clock, evidence=None):
    """Commit capture+report together only after all reads/validation succeed.

    Caller holds process_lock across every cycle. Failed cycles preserve the
    prior checkpoint; separate health marks it unavailable instead of fresh.
    """
    directory = Path(directory)
    checkpoint = directory / "checkpoint.json"
    previous = None
    if os.path.lexists(checkpoint):
        saved = read_private(checkpoint)
        require(saved.get("mode") == STATE_MODE)
        previous = saved.get("capture")
        require(isinstance(previous, dict))
    capture = collect_capture(client, clock)
    now = clock()
    if evidence is None:
        evidence = {"network_transfers": [], "deposit_records": []}
        evidence_status = "NOT_CONFIGURED"
    else:
        require(isinstance(evidence, dict) and set(evidence) == {"network_transfers", "deposit_records"})
        evidence_status = "OPERATOR_SUPPLIED_NOT_AUTHENTICATED"
    report = review_bundle({"mode": BUNDLE_MODE, "history": capture, **evidence}, now,
                           previous_history=previous)
    report["source_connection"] = "LOCAL_AUTHENTICATED_GET_VIEW_ONLY_PREFLIGHT"
    report["blockchain_evidence_status"] = evidence_status
    report["source_schema_status"] = ("UNCLASSIFIED_ACCOUNT_EVENTS_PRESENT"
        if report["history"]["unclassified_account_event_count"] else "NO_UNCLASSIFIED_ACCOUNT_EVENTS_OBSERVED")
    atomic_private(checkpoint, {"mode": STATE_MODE, "capture": capture, "report": report})
    atomic_private(directory / "health.json", {"status": "HISTORY_READ_OK",
        "checked_at_utc": now.isoformat(), "blockchain_evidence_status": evidence_status,
        "source_schema_status": report["source_schema_status"],
        "expires_at_utc": (now + timedelta(minutes=15)).isoformat(),
        "full_autonomous_reconciliation_ready": False, "financial_operations": 0})
    return report


def run_service(client, directory, *, interval=300, cycles=None, evidence_path=None,
                clock=lambda: datetime.now(timezone.utc), sleep=time.sleep):
    require(type(interval) is int and 60 <= interval <= 86400)
    require(cycles is None or type(cycles) is int and 1 <= cycles <= 10000)
    directory = private_directory(directory)
    last_code = 0
    with process_lock(directory):
        iteration = 0
        while cycles is None or iteration < cycles:
            try:
                evidence = read_private(evidence_path) if evidence_path else None
                run_cycle(client, directory, clock, evidence)
                last_code = 0
                print("AUTONOMOUS_HISTORY_CYCLE_OK financial_operations=0", flush=True)
            except Exception:
                last_code = 2
                atomic_private(directory / "health.json", {"status": "UNAVAILABLE",
                    "checked_at_utc": clock().isoformat(),
                    "full_autonomous_reconciliation_ready": False, "financial_operations": 0})
                print("AUTONOMOUS_HISTORY_CYCLE_UNAVAILABLE", flush=True)
            iteration += 1
            if cycles is None or iteration < cycles:
                sleep(interval)
    return last_code


def make_sdk_signer(credentials_path):
    """Load a single approved local ECDSA P-256 key; rotation requires restart."""
    from coinbase import jwt_generator
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    credentials = read_private(credentials_path)
    require(set(credentials) == {"name", "privateKey"})
    name, secret = credentials["name"], credentials["privateKey"]
    require(isinstance(name, str) and bool(re.fullmatch(
        r"organizations/[A-Za-z0-9-]{1,100}/apiKeys/[A-Za-z0-9-]{1,100}", name))
        and isinstance(secret, str) and len(secret) <= 8192)
    key = serialization.load_pem_private_key(secret.encode(), password=None)
    require(isinstance(key, ec.EllipticCurvePrivateKey) and isinstance(key.curve, ec.SECP256R1))
    def signer(method, path):
        return jwt_generator.build_rest_jwt(
            jwt_generator.format_jwt_uri(method, path), name, secret)
    return signer


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Coinbase GET-only polling service")
    parser.add_argument("--config", required=True, help="Private config; never pass secrets as arguments")
    parser.add_argument("--enable-live-read", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if not args.enable_live_read:
        print("AUTONOMOUS_HISTORY_LIVE_ACCESS_NOT_ENABLED")
        return 2
    try:
        config = read_private(args.config)
        require(set(config) == {"account_id", "portfolio_id", "credentials_file", "state_directory", "interval_seconds"})
        _uuid(config["account_id"]); _uuid(config["portfolio_id"])
        require(type(config["interval_seconds"]) is int and 60 <= config["interval_seconds"] <= 86400)
        # Local SDK only signs JWTs. No REST client, order or transfer method is used.
        signer = make_sdk_signer(config["credentials_file"])
        client = ReadOnlyClient(config["account_id"], config["portfolio_id"], signer)
        return run_service(client, config["state_directory"], interval=config["interval_seconds"],
                           cycles=1 if args.once else None)
    except KeyboardInterrupt:
        print("AUTONOMOUS_HISTORY_STOPPED")
        return 0
    except Exception:
        print("AUTONOMOUS_HISTORY_START_REJECTED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
