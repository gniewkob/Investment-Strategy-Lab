"""Local durable SQLite ledger for independently corroborated shadow receipts.

Append-only is enforced for ordinary SQL writes by triggers plus an ordered
SHA-256 chain. It is NOT cryptographically immutable against DB-file editors,
administrators, or lost final rows. Export/anchor the head to independent WORM
storage if external nonrepudiation is needed. No brokerage or Neon I/O.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import sqlite3
from pathlib import Path

from scripts.github_checkpoint_verify_v08 import verify
from scripts.shadow_decision_engine_v05 import ShadowInputError, _digest

SCHEMA = "ISL_SHADOW_EVIDENCE_LEDGER_V09_001"
GENESIS = "0" * 64
MAX_BYTES = 2_000_000


def _validated_bundle(bundle):
    if not isinstance(bundle, dict) or set(bundle) != {"capture", "run", "artifacts", "checkpoint"}:
        raise ShadowInputError("ledger requires exact capture/run/artifacts/checkpoint bundle")
    checkpoint = bundle["checkpoint"]
    if not isinstance(checkpoint, dict):
        raise ShadowInputError("checkpoint must be an object")
    saved_sha = checkpoint.get("receipt_sha256")
    if not isinstance(saved_sha, str) or saved_sha != _digest({
        k: v for k, v in checkpoint.items() if k != "receipt_sha256"
    }):
        raise ShadowInputError("checkpoint receipt SHA mismatch")
    if checkpoint.get("schema") != "ISL_GITHUB_CHECKPOINT_V08_001":
        raise ShadowInputError("unsupported checkpoint format")
    proof = verify(bundle["capture"], bundle["run"], bundle["artifacts"],
                   cutoff_utc=checkpoint.get("independently_supplied_cutoff_utc"))
    proof["receipt_sha256"] = _digest(proof)
    if checkpoint != proof:
        raise ShadowInputError("checkpoint differs from recomputed GitHub metadata check")
    serialized = json.dumps(bundle, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True, allow_nan=False)
    if len(serialized.encode("utf-8")) > MAX_BYTES:
        raise ShadowInputError("evidence bundle exceeds 2MB limit")
    return serialized, _digest(bundle)


def _install(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS evidence (
      seq INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id INTEGER NOT NULL,
      run_attempt INTEGER NOT NULL,
      artifact_id INTEGER NOT NULL,
      bundle_json TEXT NOT NULL,
      bundle_sha256 TEXT NOT NULL,
      previous_sha256 TEXT NOT NULL,
      entry_sha256 TEXT NOT NULL,
      UNIQUE(run_id, run_attempt, artifact_id)
    )""")
    conn.execute("""CREATE TRIGGER IF NOT EXISTS evidence_no_update
      BEFORE UPDATE ON evidence BEGIN SELECT RAISE(ABORT, 'append-only evidence'); END""")
    conn.execute("""CREATE TRIGGER IF NOT EXISTS evidence_no_delete
      BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT, 'append-only evidence'); END""")


def _check_rows(conn):
    previous = GENESIS
    count = 0
    for seq, run_id, attempt, artifact_id, serialized, bundle_sha, prior, entry_sha in conn.execute(
            """SELECT seq, run_id, run_attempt, artifact_id, bundle_json,
                      bundle_sha256, previous_sha256, entry_sha256 FROM evidence ORDER BY seq"""):
        count += 1
        if seq != count or prior != previous:
            raise ShadowInputError("ledger sequence or previous hash corrupted")
        try:
            bundle = json.loads(serialized)
        except (TypeError, ValueError) as exc:
            raise ShadowInputError("ledger JSON corrupted") from exc
        canonical, digest = _validated_bundle(bundle)
        if canonical != serialized or digest != bundle_sha:
            raise ShadowInputError("ledger evidence bytes modified")
        cp = bundle["checkpoint"]
        if (cp["run_id"], cp["run_attempt"], cp["artifact_id"]) != (
                run_id, attempt, artifact_id):
            raise ShadowInputError("ledger run identity modified")
        expected = _digest({"seq": seq, "run_id": run_id,
                            "run_attempt": attempt, "artifact_id": artifact_id,
                            "bundle_sha256": bundle_sha, "previous_sha256": prior})
        if expected != entry_sha:
            raise ShadowInputError("ledger chain hash mismatch")
        previous = entry_sha
    return {"schema": SCHEMA, "entries": count,
            "head_sha256": previous, "external_head_anchor_verified": False,
            "trusted_timestamp_certified": False, "financial_operations": 0}


def audit(path):
    if not Path(path).is_file():
        raise ShadowInputError("ledger does not exist")
    uri = Path(path).resolve().as_uri().replace("file://", "file:") + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        return _check_rows(conn)


def append(path, bundle):
    canonical, digest = _validated_bundle(bundle)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=15)) as conn, conn:
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("BEGIN IMMEDIATE")
        _install(conn)
        current = _check_rows(conn)
        cp = bundle["checkpoint"]
        identity = (cp["run_id"], cp["run_attempt"], cp["artifact_id"])
        old = conn.execute("""SELECT seq, bundle_sha256 FROM evidence
              WHERE run_id=? AND run_attempt=? AND artifact_id=?""", identity).fetchone()
        if old is not None:
            if old[1] != digest:
                raise ShadowInputError("conflicting evidence for existing run/attempt/artifact")
            conn.commit()
            return {**current, "append_status": "IDEMPOTENT_REPLAY", "sequence": old[0]}
        seq = current["entries"] + 1
        previous = current["head_sha256"]
        entry_sha = _digest({"seq": seq, "run_id": identity[0],
                             "run_attempt": identity[1], "artifact_id": identity[2],
                             "bundle_sha256": digest, "previous_sha256": previous})
        conn.execute("""INSERT INTO evidence (seq,run_id,run_attempt,artifact_id,
                    bundle_json,bundle_sha256,previous_sha256,entry_sha256)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (seq, *identity, canonical, digest, previous, entry_sha))
        verified = _check_rows(conn)
        conn.commit()
    return {**verified, "append_status": "NEW_EVIDENCE", "sequence": seq}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--append-bundle", type=Path)
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        result = audit(args.ledger)
    else:
        bundle = json.loads(args.append_bundle.read_text(encoding="utf-8"))
        result = append(args.ledger, bundle)
    print("ISL_SHADOW_LEDGER_V09=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
