"""Offline, research-only anchored SQLite backup and non-destructive restore drill.

Does not deploy, schedule, connect to Neon/wallet, create trading positions,
certify trusted time, or make a backup immutable/offsite.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
from uuid import uuid4

from scripts.shadow_decision_engine_v05 import ShadowInputError
from scripts.shadow_external_anchor_v10 import verify_anchor

SCHEMA = "ISL_SHADOW_BACKUP_V11_001"
FILES = {"ledger.sqlite3", "anchor.json", "manifest.json"}


def _digest(path):
    h = sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _canonical(doc):
    return (json.dumps(doc, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _private_dir(path):
    path = Path(path)
    if not path.is_dir() or path.is_symlink():
        raise ShadowInputError("explicit existing private directory required")
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ShadowInputError("directory must have permissions 0700")
    return path


def _file(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ShadowInputError("regular non-symlink file required")
    return path


def _sqlite_integrity(path):
    uri = _file(path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ShadowInputError("SQLite integrity_check failed")


def _write(path, data):
    with Path(path).open("xb") as dst:
        os.chmod(path, 0o600)
        dst.write(data)
        dst.flush()
        os.fsync(dst.fileno())


def verify_snapshot(snapshot, manifest_sha256):
    if not isinstance(manifest_sha256, str) or not (
            len(manifest_sha256) == 64 and
            all(c in "0123456789abcdef" for c in manifest_sha256)):
        raise ShadowInputError("externally supplied manifest sha256 required")
    folder = _private_dir(snapshot)
    if {p.name for p in folder.iterdir()} != FILES:
        raise ShadowInputError("snapshot contents differ from sealed manifest")
    manifest_path = _file(folder / "manifest.json")
    anchor = _file(folder / "anchor.json")
    ledger = _file(folder / "ledger.sqlite3")
    if _digest(manifest_path) != manifest_sha256:
        raise ShadowInputError("snapshot manifest pin mismatch")
    doc = json.loads(manifest_path.read_bytes())
    if not isinstance(doc, dict) or set(doc) != {
        "schema", "created_at_utc", "ledger_sha256", "anchor_sha256",
        "anchored_entries", "anchored_head_sha256", "offsite_verified",
        "trusted_time_verified", "financial_operations",
    }:
        raise ShadowInputError("unexpected backup manifest schema")
    if (doc["schema"] != SCHEMA or doc["offsite_verified"] is not False
            or doc["trusted_time_verified"] is not False
            or doc["financial_operations"] != 0
            or manifest_path.read_bytes() != _canonical(doc)):
        raise ShadowInputError("manifest claims unverified authority")
    if _digest(ledger) != doc["ledger_sha256"] or _digest(anchor) != doc["anchor_sha256"]:
        raise ShadowInputError("snapshot file digest mismatch")
    _sqlite_integrity(ledger)
    verified = verify_anchor(ledger, anchor, expected_sha256=doc["anchor_sha256"])
    if (verified["anchored_entries"] != doc["anchored_entries"]
            or verified["anchored_head_sha256"] != doc["anchored_head_sha256"]):
        raise ShadowInputError("anchored ledger prefix mismatch")
    return {"status": "LOCAL_SNAPSHOT_VERIFIED_NOT_OFFSITE",
            "manifest_sha256": manifest_sha256,
            "current_entries": verified["current_entries"],
            "anchored_head_sha256": verified["anchored_head_sha256"],
            "offsite_verified": False, "financial_operations": 0}


def create_snapshot(ledger, anchor, anchor_sha256, destination_root):
    ledger = _file(ledger)
    anchor = _file(anchor)
    root = _private_dir(destination_root)
    before = verify_anchor(ledger, anchor, expected_sha256=anchor_sha256)
    _sqlite_integrity(ledger)
    stage = Path(tempfile.mkdtemp(prefix=".isl-staging-", dir=root))
    os.chmod(stage, 0o700)
    target = root / ("isl-shadow-" + uuid4().hex)
    try:
        with sqlite3.connect(ledger.resolve().as_uri() + "?mode=ro", uri=True) as src:
            with sqlite3.connect(stage / "ledger.sqlite3") as dst:
                src.backup(dst)
        os.chmod(stage / "ledger.sqlite3", 0o600)
        _write(stage / "anchor.json", anchor.read_bytes())
        after = verify_anchor(stage / "ledger.sqlite3", stage / "anchor.json",
                              expected_sha256=anchor_sha256)
        if (before["current_entries"] != after["current_entries"]
                or before["current_head_sha256"] != after["current_head_sha256"]):
            raise ShadowInputError("source ledger changed during backup")
        doc = {
            "schema": SCHEMA, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "ledger_sha256": _digest(stage / "ledger.sqlite3"),
            "anchor_sha256": _digest(stage / "anchor.json"),
            "anchored_entries": after["anchored_entries"],
            "anchored_head_sha256": after["anchored_head_sha256"],
            "offsite_verified": False, "trusted_time_verified": False,
            "financial_operations": 0,
        }
        _write(stage / "manifest.json", _canonical(doc))
        pinned = _digest(stage / "manifest.json")
        verify_snapshot(stage, pinned)
        os.rename(stage, target)
        return {"path": str(target), **verify_snapshot(target, pinned)}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def restore_drill(snapshot, manifest_sha256, restore_root):
    verify_snapshot(snapshot, manifest_sha256)
    root = _private_dir(restore_root)
    staged = Path(tempfile.mkdtemp(prefix=".isl-drill-", dir=root))
    os.chmod(staged, 0o700)
    target = root / ("isl-restored-" + uuid4().hex)
    try:
        for name in sorted(FILES):
            shutil.copyfile(Path(snapshot) / name, staged / name)
            os.chmod(staged / name, 0o600)
        verify_snapshot(staged, manifest_sha256)
        os.rename(staged, target)
        return {"path": str(target), "status": "RESTORE_VERIFIED_NOT_ACTIVATED",
                "manifest_sha256": manifest_sha256, "financial_operations": 0}
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="operation", required=True)
    make = commands.add_parser("create")
    make.add_argument("--ledger", type=Path, required=True)
    make.add_argument("--anchor", type=Path, required=True)
    make.add_argument("--anchor-sha256", required=True)
    make.add_argument("--destination-root", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("--snapshot", type=Path, required=True)
    check.add_argument("--manifest-sha256", required=True)
    drill = commands.add_parser("restore-drill")
    drill.add_argument("--snapshot", type=Path, required=True)
    drill.add_argument("--manifest-sha256", required=True)
    drill.add_argument("--restore-root", type=Path, required=True)
    args = p.parse_args()
    if args.operation == "create":
        out = create_snapshot(args.ledger, args.anchor, args.anchor_sha256, args.destination_root)
    elif args.operation == "verify":
        out = verify_snapshot(args.snapshot, args.manifest_sha256)
    else:
        out = restore_drill(args.snapshot, args.manifest_sha256, args.restore_root)
    print("ISL_SHADOW_BACKUP_V11=" + json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
