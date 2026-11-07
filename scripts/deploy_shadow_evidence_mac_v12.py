"""Install an isolated research-only shadow evidence store on macOS.

This installer never touches existing portfolio collectors, launchd jobs,
broker/wallet credentials, or Neon. Requires an exact Git commit and a known
SHA-256 of versioned archived evidence. No scheduler/offsite WORM claims.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile

from scripts.shadow_decision_engine_v05 import ShadowInputError
from scripts.shadow_evidence_ledger_v09 import append, audit
from scripts.shadow_external_anchor_v10 import (
    prepare_anchor, verify_anchor, write_new_anchor,
)
from scripts.shadow_backup_restore_v11 import (
    create_snapshot, restore_drill, verify_snapshot,
)

EVIDENCE_PATH = Path("evidence/shadow/v09/checkpoint-bundle-run-42305280062.json")
EVIDENCE_SHA256 = "4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3"
REPOSITORY = "gniewkob/Investment-Strategy-Lab"
SHA40 = re.compile(r"^[a-f0-9]{40}$")
DEFAULT_BASE = (
    Path.home() / "Library" / "Application Support" /
    "InvestmentStrategyLabShadowEvidence"
)


def _digest_file(path):
    h = sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _private_dir(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ShadowInputError("expected existing non-symlink directory")
    info = path.stat()
    if os.name == "posix":
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ShadowInputError("private directory must be owned by caller and mode 0700")
    return path


def preflight(repo_root, base, expected_sha, *, require_macos=True):
    repo_root = Path(repo_root).resolve()
    base = Path(base).expanduser()
    if require_macos and platform.system() != "Darwin":
        raise ShadowInputError("deployment requires macOS")
    if os.geteuid() == 0:
        raise ShadowInputError("never deploy as root")
    if not SHA40.fullmatch(expected_sha):
        raise ShadowInputError("explicit full 40-char expected commit required")
    if not base.is_absolute() or base.is_symlink() or os.path.lexists(base):
        raise ShadowInputError("target must be a new absolute nonexisting directory")
    if not base.parent.is_dir() or base.parent.is_symlink():
        raise ShadowInputError("target parent must already exist and not be a symlink")
    if base.name.startswith(".") or base.name in ("ledger", "backups"):
        raise ShadowInputError("invalid deployment directory name")
    try:
        head = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        origin = subprocess.check_output(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip().removesuffix(".git")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ShadowInputError("required source Git repo metadata unavailable") from exc
    if head != expected_sha:
        raise ShadowInputError("checked-out HEAD differs from authorized commit")
    if origin not in (
        "https://github.com/" + REPOSITORY,
        "git@github.com:" + REPOSITORY,
        "ssh://git@github.com/" + REPOSITORY,
    ):
        raise ShadowInputError("unexpected repository origin")
    if (repo_root / "scripts" / "deploy_shadow_evidence_mac_v12.py").resolve() != Path(__file__).resolve():
        raise ShadowInputError("installer must run from checked-out pinned repository")
    evidence = repo_root / EVIDENCE_PATH
    if evidence.is_symlink() or not evidence.is_file() or _digest_file(evidence) != EVIDENCE_SHA256:
        raise ShadowInputError("archived source evidence checksum mismatch")
    try:
        source_bundle = json.loads(evidence.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise ShadowInputError("archived evidence is not valid JSON") from exc
    return source_bundle


def _write_receipt(path, data):
    raw = (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()
    with Path(path).open("xb") as f:
        os.chmod(path, 0o600)
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def deploy_isolated(base, bundle, *, source_sha):
    """Atomic new-directory install; never merge with an existing home tree."""
    base = Path(base)
    if os.path.lexists(base):
        raise ShadowInputError("target already exists; refusing to overwrite or redeploy")
    parent = base.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ShadowInputError("deployment parent unavailable")
    old_umask = os.umask(0o077)
    stage = Path(tempfile.mkdtemp(prefix=".isl-shadow-v12-stage-", dir=parent))
    os.chmod(stage, 0o700)
    promoted = False
    try:
        for dirname in ("ledger", "anchors", "backups", "restore-drills", "state"):
            (stage / dirname).mkdir(mode=0o700)
            _private_dir(stage / dirname)
        ledger = stage / "ledger" / "research-evidence.sqlite3"
        appended = append(ledger, bundle)
        os.chmod(ledger, 0o600)
        if appended.get("entries") != 1 or appended.get("append_status") != "NEW_EVIDENCE":
            raise ShadowInputError("bootstrap must create exactly one new research receipt")
        anchor_doc = prepare_anchor(ledger, created_at_utc=datetime.now(timezone.utc).isoformat())
        anchor_written = write_new_anchor(stage / "anchors", anchor_doc)
        anchor_path = Path(anchor_written["path"])
        pinned = anchor_written["anchor_sha256"]
        verified = verify_anchor(ledger, anchor_path, expected_sha256=pinned)
        if verified["anchored_entries"] != 1:
            raise ShadowInputError("unexpected anchoring state")
        saved = create_snapshot(ledger, anchor_path, pinned, stage / "backups")
        restored = restore_drill(saved["path"], saved["manifest_sha256"],
                                 stage / "restore-drills")
        verify_snapshot(restored["path"], saved["manifest_sha256"])
        if audit(ledger)["head_sha256"] != anchor_written["head_sha256"]:
            raise ShadowInputError("final SQLite head does not match initial anchor")
        result = {
            "status": "ISOLATED_RESEARCH_LEDGER_DEPLOYED_NO_SCHEDULE",
            "source_commit_sha": source_sha,
            "archived_evidence_sha256": EVIDENCE_SHA256,
            "ledger_relpath": "ledger/research-evidence.sqlite3",
            "anchor_relpath": str(anchor_path.relative_to(stage)),
            "anchor_sha256": pinned,
            "head_sha256": anchor_written["head_sha256"],
            "backup_relpath": str(Path(saved["path"]).relative_to(stage)),
            "backup_manifest_sha256": saved["manifest_sha256"],
            "restore_relpath": str(Path(restored["path"]).relative_to(stage)),
            "entries": 1,
            "independent_worm_verified": False,
            "offsite_backup_verified": False,
            "trusted_timestamp_verified": False,
            "active_scheduler_changed": False,
            "neon_modified": False,
            "financial_operations": 0,
        }
        _write_receipt(stage / "state" / "deployment-receipt-v12.json", result)
        if os.path.lexists(base):
            raise ShadowInputError("target appeared during deployment; refusing replacement")
        os.rename(stage, base)
        promoted = True
        if audit(base / result["ledger_relpath"])["head_sha256"] != result["head_sha256"]:
            raise ShadowInputError("post-install read-back hash mismatch")
        verify_snapshot(base / result["backup_relpath"], result["backup_manifest_sha256"])
        return {"path": str(base), **result}
    finally:
        if not promoted and stage.exists():
            shutil.rmtree(stage)
        os.umask(old_umask)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--base-dir", type=Path, default=DEFAULT_BASE)
    p.add_argument("--expected-commit", required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = p.parse_args()
    try:
        data = preflight(args.repo_root, args.base_dir, args.expected_commit)
        if args.preflight:
            result = {
                "status": "MAC_PREFLIGHT_OK_NO_CHANGES", "target": str(args.base_dir),
                "source_commit_sha": args.expected_commit,
                "archived_evidence_sha256": EVIDENCE_SHA256,
                "financial_operations": 0,
            }
        else:
            result = deploy_isolated(args.base_dir, data, source_sha=args.expected_commit)
    except (ShadowInputError, OSError, sqlite3.DatabaseError) as exc:
        p.exit(2, "ISL_V12_BLOCKED: " + str(exc) + "\n")
    print("ISL_MAC_SHADOW_V12=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
