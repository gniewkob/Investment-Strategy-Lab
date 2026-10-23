"""Private local setup. Native dialogs keep key/account choices out of chat."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from scripts import autonomous_coinbase_history as a
from scripts.operational_read_only import read_private, write_private
from scripts.coinbase_deposit_history import _cursor


def native_file():
    script = 'POSIX path of (choose file with prompt "Wybierz prywatny eksport klucza Coinbase ECDSA z uprawnieniem tylko View. Nie wklejaj klucza do czatu.")'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    a.require(result.returncode == 0 and result.stdout.strip())
    return Path(result.stdout.strip())


def native_account(options):
    labels = [f"{row['currency']} — konto {index + 1}" for index, row in enumerate(options)]
    choices = "{" + ",".join(json.dumps(label, ensure_ascii=False) for label in labels) + "}"
    script = 'set selected to choose from list ' + choices + ' with prompt "Wybierz konto do autonomicznego odczytu historii"\nif selected is false then return ""\nreturn item 1 of selected'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    a.require(result.returncode == 0 and result.stdout.strip() in labels)
    return options[labels.index(result.stdout.strip())]["id"]


def secure_source(path):
    """Restrict an operator-selected, owner-controlled download before parsing it."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        a.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and 0 < info.st_size <= 16384)
        parsed = json.loads(os.read(fd, 16385))
        a.require(isinstance(parsed, dict) and set(parsed) == {"name", "privateKey"})
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    return read_private(path)


def discover_accounts(client):
    """Discover only IDs/currency locally. Never return balances or account names."""
    a.require(client.account is None)
    client.check_permissions()
    cursor = None
    seen = set()
    rows = []
    for _ in range(20):
        response = client.get(client.path, cursor)
        data, pagination = response.get("data"), response.get("pagination")
        a.require(isinstance(data, list) and len(data) <= 100 and isinstance(pagination, dict)
                  and "next_uri" in pagination and response.get("proof_token_required") is not True)
        for row in data:
            a.require(isinstance(row, dict))
            ident = a._uuid(row.get("id"))
            a.require(ident not in seen)
            seen.add(ident)
            currency = row.get("currency")
            if isinstance(currency, dict): currency = currency.get("code")
            a.require(isinstance(currency, str) and re.fullmatch(r"[A-Za-z0-9]{2,12}", currency))
            rows.append({"id": ident, "currency": currency})
            a.require(len(rows) <= 1000)
        next_cursor = _cursor(pagination["next_uri"], client.path)
        if next_cursor is None:
            break
        a.require(data and data[-1]["id"] == next_cursor and next_cursor != cursor)
        cursor = next_cursor
    else:
        raise a.AutonomousHistoryError("SETUP_ACCOUNT_PAGE_LIMIT")
    a.require(rows)
    return rows


def configure(root, key_path, select_account, *, signer_factory=a.make_sdk_signer,
              client_factory=a.ReadOnlyClient):
    root = a.private_directory(root)
    with a.process_lock(root):
        return _configure(root, key_path, select_account, signer_factory, client_factory)


def _configure(root, key_path, select_account, signer_factory, client_factory):
    a.require(not os.path.lexists(root / "reader-config.json"))
    credentials_dir = a.private_directory(root / "credentials")
    state_dir = a.private_directory(root / "state")
    secret = secure_source(key_path)
    # Validate algorithm locally before any request. Never output secret or JWT.
    signer = signer_factory(key_path)
    probe = client_factory(None, "00000000-0000-4000-8000-000000000000", signer)
    permissions = probe.get(a.PERMISSIONS)
    a.require(permissions.get("can_view") is True and permissions.get("can_trade") is False
              and permissions.get("can_transfer") is False)
    portfolio = a._uuid(permissions.get("portfolio_uuid"))
    discovery = client_factory(None, portfolio, signer)
    accounts = discover_accounts(discovery)
    account = select_account(accounts)
    a.require(account in {row["id"] for row in accounts})
    managed_key = credentials_dir / "coinbase.secret.json"
    a.require(not os.path.lexists(managed_key))
    write_private(managed_key, secret)
    config = {"account_id": account, "portfolio_id": portfolio,
        "credentials_file": str(managed_key), "state_directory": str(state_dir), "interval_seconds": 300}
    try:
        write_private(root / "reader-config.json", config)
    except Exception:
        managed_key.unlink()
        raise
    return root / "reader-config.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private native setup for Coinbase view-only history")
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--enable-local-setup", action="store_true")
    args = parser.parse_args(argv)
    if not args.enable_local_setup:
        print("AUTONOMOUS_HISTORY_SETUP_NOT_ENABLED")
        return 2
    try:
        configure(args.runtime_root, native_file(), native_account)
        print("AUTONOMOUS_HISTORY_PRIVATE_SETUP_READY", flush=True)
        return 0
    except Exception:
        print("AUTONOMOUS_HISTORY_SETUP_CANCELLED_OR_REJECTED", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
