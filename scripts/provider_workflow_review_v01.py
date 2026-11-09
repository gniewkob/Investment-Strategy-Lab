"""Read-only inventory auditor for quarantined, unmerged ISL workflow files.

Neither presence, a matching Git blob nor successful tests authorise activation,
external data reuse, trading, a trusted publication timestamp, or merging.
No network, git mutations, database, source-file writes or credentials.
"""
from __future__ import annotations

import argparse
from hashlib import sha1
import json
from pathlib import Path
import re

SCHEMA = "ISL_PROVIDER_WORKFLOW_GOVERNANCE_V01"
EXPECTED_COUNT = 16
GROUPS = {"CI_ONLY", "EVIDENCE_PIPELINE", "PUBLIC_PROVIDER", "RAW_PROVIDER"}
SHA1 = re.compile(r"^[0-9a-f]{40}$")
NAME = re.compile(r"^\.github/workflows/[a-z0-9][a-z0-9_-]*\.yml$")


class InventoryError(ValueError):
    pass


def read_inventory(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise InventoryError("unknown inventory schema")
    if doc.get("authorization") != "NOT_GRANTED":
        raise InventoryError("no provider activation can be authorised by this manifest")
    rows = doc.get("workflows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_COUNT or doc.get("count") != EXPECTED_COUNT:
        raise InventoryError("exact 16 source workflows must be inventoried")
    names = set()
    for item in rows:
        if not isinstance(item, dict) or set(item) != {
            "path", "git_blob_sha1", "group", "provider", "observed_flags", "approval"
        }:
            raise InventoryError("invalid workflow entry fields")
        name = item["path"]
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
            raise InventoryError("noncanonical or duplicate workflow path")
        names.add(name)
        if not isinstance(item["git_blob_sha1"], str) or not SHA1.fullmatch(item["git_blob_sha1"]):
            raise InventoryError("invalid original Git blob SHA")
        if item["group"] not in GROUPS or item["approval"] != "HOLD_FOR_SEPARATE_REVIEW":
            raise InventoryError("provider integration review must remain on hold")
        if not isinstance(item["provider"], str) or not item["provider"]:
            raise InventoryError("missing source/provider classification")
        flags = item["observed_flags"]
        if not isinstance(flags, list) or not flags or not all(
            isinstance(x, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", x) for x in flags
        ) or len(flags) != len(set(flags)):
            raise InventoryError("invalid risk flags")
    return doc


def git_blob_sha1(raw):
    return sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def observed_signals(text):
    """String indicators for review; NOT a full YAML or security-policy parser."""
    return {
        "schedule_literal": bool(re.search(r"(?m)^  schedule:\s*$", text)),
        "artifact_upload_literal": "actions/upload-artifact@" in text,
        "manual_dispatch_literal": bool(re.search(r"(?m)^  workflow_dispatch:\s*$", text)),
        "persist_credentials_false_literal": "persist-credentials: false" in text,
        "checkout_literal": "actions/checkout@" in text,
    }


def audit(root, inventory, *, require_all=False, forbid_present=False):
    if require_all and forbid_present:
        raise InventoryError("require_all and forbid_present are mutually exclusive")
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise InventoryError("source root must be an existing directory")
    items = []
    mismatch = 0
    missing = 0
    for row in inventory["workflows"]:
        candidate = root / row["path"]
        # Reject a path component that escapes through a symlink.
        if not candidate.resolve().is_relative_to(root):
            raise InventoryError("source path escapes the checkout")
        if not candidate.exists():
            missing += 1
            items.append({"path": row["path"], "status": "NOT_PRESENT_IN_CHECKOUT"})
            continue
        if not candidate.is_file() or candidate.is_symlink():
            raise InventoryError("workflow must be a regular non-symlink file")
        raw = candidate.read_bytes()
        actual = git_blob_sha1(raw)
        status = "EXACT_SOURCE_BLOB_FOR_REVIEW_ONLY" if actual == row["git_blob_sha1"] else "SOURCE_BLOB_CHANGED_REVIEW_REQUIRED"
        if actual != row["git_blob_sha1"]:
            mismatch += 1
        items.append({
            "path": row["path"],
            "status": status,
            "source_blob_matches": actual == row["git_blob_sha1"],
            "observed_signals": observed_signals(raw.decode("utf-8")),
        })
    report = {
        "schema": "ISL_PROVIDER_WORKFLOW_AUDIT_V01",
        "inventory_count": len(items),
        "present_count": len(items)-missing,
        "missing_count": missing,
        "changed_count": mismatch,
        "authorization": "NOT_GRANTED",
        "activation_approved": False,
        "deployment_approved": False,
        "provider_rights_verified": False,
        "financial_operations": 0,
        "status": "SOURCE_REVIEW_REQUIRED",
        "items": items,
    }
    if mismatch or (require_all and missing):
        report["status"] = "SNAPSHOT_INCOMPLETE_OR_CHANGED"
    if forbid_present and missing != len(items):
        # A matching Git blob is evidence of identity, never permission to
        # carry a provider workflow into this governance-only branch.
        report["status"] = "QUARANTINED_WORKFLOW_PRESENT"
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", type=Path, default=Path("governance/isl_provider_workflow_inventory_v01.json"))
    p.add_argument("--source-root", type=Path, default=Path("."))
    p.add_argument("--require-all", action="store_true")
    p.add_argument("--forbid-present", action="store_true", help="fail if any inventoried workflow exists in the checkout")
    args = p.parse_args()
    result = audit(args.source_root, read_inventory(args.inventory), require_all=args.require_all, forbid_present=args.forbid_present)
    print("ISL_PROVIDER_WORKFLOW_REVIEW=" + json.dumps(result, sort_keys=True, separators=(",", ":")))
    if result["status"] in {"SNAPSHOT_INCOMPLETE_OR_CHANGED", "QUARANTINED_WORKFLOW_PRESENT"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
