"""External head-anchor protocol for the research-only SQLite evidence ledger.

An anchor pins the count/head of an already verified ledger. A separately
preserved, independently trusted SHA-256 of its canonical JSON is REQUIRED to
verify it. Neither this utility nor a local anchor directory proves trusted
time, immutability, WORM storage or legal market-data entitlement.

No network, wallet, broker or Neon operations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from scripts.shadow_decision_engine_v05 import ShadowInputError, _utc, _digest
from scripts.shadow_evidence_ledger_v09 import audit, SCHEMA as LEDGER_SCHEMA, GENESIS

SCHEMA = "ISL_SHADOW_LEDGER_EXTERNAL_ANCHOR_V10_001"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ANCHOR_KEYS = {
    "schema", "ledger_schema", "entries", "head_sha256",
    "created_at_utc", "time_independently_attested",
    "external_storage_independently_verified", "financial_operations",
}


def _canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def prepare_anchor(ledger_path, *, created_at_utc):
    """Verify the complete SQLite ledger before preparing the minimal anchor."""
    report = audit(ledger_path)
    now = _utc(created_at_utc)
    if now > datetime.now(timezone.utc):
        raise ShadowInputError("anchor timestamp is in the future")
    if report.get("schema") != LEDGER_SCHEMA or report["entries"] < 1:
        raise ShadowInputError("cannot anchor an empty or unknown ledger")
    result = {
        "schema": SCHEMA,
        "ledger_schema": LEDGER_SCHEMA,
        "entries": report["entries"],
        "head_sha256": report["head_sha256"],
        "created_at_utc": now.isoformat(),
        "time_independently_attested": False,
        "external_storage_independently_verified": False,
        "financial_operations": 0,
    }
    return result


def _validate_anchor(anchor):
    if not isinstance(anchor, dict) or set(anchor) != ANCHOR_KEYS:
        raise ShadowInputError("invalid external anchor schema")
    if anchor["schema"] != SCHEMA or anchor["ledger_schema"] != LEDGER_SCHEMA:
        raise ShadowInputError("anchor schema mismatch")
    if type(anchor["entries"]) is not int or anchor["entries"] < 1:
        raise ShadowInputError("anchor entry count invalid")
    if not isinstance(anchor["head_sha256"], str) or not HEX64.fullmatch(anchor["head_sha256"]):
        raise ShadowInputError("anchor head hash invalid")
    _utc(anchor["created_at_utc"])
    if (anchor["time_independently_attested"] is not False
            or anchor["external_storage_independently_verified"] is not False
            or anchor["financial_operations"] != 0):
        raise ShadowInputError("anchor asserts unverified authority")


def write_new_anchor(anchor_dir, anchor):
    """Create an anchor with exclusive hard link, never replace an old anchor."""
    _validate_anchor(anchor)
    dest_dir = Path(anchor_dir)
    if not dest_dir.is_dir() or dest_dir.is_symlink():
        raise ShadowInputError("anchor directory must already exist and not be symlinked")
    payload = _canonical_bytes(anchor)
    digest = sha256(payload).hexdigest()
    path = dest_dir / ("isl-shadow-anchor-v10-%09d-%s.json" %
                       (anchor["entries"], anchor["head_sha256"][:16]))
    temp_path = None
    try:
        fd, name = tempfile.mkstemp(prefix=".isl-anchor-", dir=dest_dir)
        temp_path = Path(name)
        with os.fdopen(fd, "wb") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temp_path, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise ShadowInputError("existing anchor cannot be overwritten") from exc
        # Durable directory entry where supported; does not make it WORM.
        dir_fd = os.open(str(dest_dir), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return {"path": str(path), "anchor_sha256": digest,
            "entries": anchor["entries"], "head_sha256": anchor["head_sha256"],
            "external_storage_independently_verified": False}


def verify_anchor(ledger_path, anchor_path, *, expected_sha256):
    """Require out-of-band pinned anchor checksum, then check anchored prefix."""
    if not isinstance(expected_sha256, str) or not HEX64.fullmatch(expected_sha256):
        raise ShadowInputError("independently pinned SHA-256 required")
    raw = Path(anchor_path).read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ShadowInputError("anchor SHA-256 differs from independent pinned value")
    try:
        anchor = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ShadowInputError("invalid anchor JSON") from exc
    _validate_anchor(anchor)
    if raw != _canonical_bytes(anchor):
        raise ShadowInputError("anchor bytes not canonical")
    # audit() independently walks the complete ledger and recomputes the full
    # chain. Then verify the anchored prefix, even if later rows were appended.
    state = audit(ledger_path)
    if state["entries"] < anchor["entries"]:
        raise ShadowInputError("ledger truncated below externally anchored count")
    uri = Path(ledger_path).resolve().as_uri().replace("file://", "file:") + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        row = conn.execute("SELECT entry_sha256 FROM evidence WHERE seq=?",
                           (anchor["entries"],)).fetchone()
    if row is None or row[0] != anchor["head_sha256"]:
        raise ShadowInputError("ledger anchored prefix hash changed")
    return {
        "status": "SUPPLIED_HASH_AND_SQLITE_PREFIX_MATCH_NOT_EXTERNAL_PROOF",
        "anchored_entries": anchor["entries"],
        "current_entries": state["entries"],
        "anchored_head_sha256": anchor["head_sha256"],
        "current_head_sha256": state["head_sha256"],
        "anchor_sha256": expected_sha256,
        "trusted_time_verified": False,
        "external_hash_independently_witnessed": False,
        "external_WORM_storage_verified": False,
        "investment_performance_verified": False,
        "financial_operations": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, type=Path)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--create-in", type=Path)
    operation.add_argument("--verify", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if args.create_in:
        if args.expected_sha256:
            parser.error("--expected-sha256 applies only to --verify")
        a = prepare_anchor(args.ledger, created_at_utc=datetime.now(timezone.utc).isoformat())
        result = write_new_anchor(args.create_in, a)
    else:
        result = verify_anchor(args.ledger, args.verify, expected_sha256=args.expected_sha256)
    print("ISL_SHADOW_ANCHOR_V10=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
