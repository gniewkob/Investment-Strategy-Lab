"""v0.29 link independently checkpointed v0.9 research evidence to M1–M3.

Read-only bridge: verify the complete v0.9 bundle, independently replay its
archived empty-source decision, and optionally reconcile with an existing
local v0.9 SQLite evidence ledger. Do not invent sources, backdate an
observation, treat GitHub metadata as trusted clock, or mark trading ready.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3

from scripts.research_decision_pipeline_v16 import (
    _load, _manifest_from_archived_bundle, run_cycle,
)
from scripts.shadow_evidence_ledger_v09 import audit as audit_ledger, _validated_bundle
from scripts.shadow_decision_engine_v05 import MODEL_ASSETS, ShadowInputError, _digest

SCHEMA = "ISL_ARCHIVED_DECISION_EVIDENCE_LINK_V29_001"
SHA64 = re.compile(r"^[0-9a-f]{64}$")


def _ledger_match(ledger_path, bundle, digest):
    path = Path(ledger_path)
    if path.is_symlink() or not path.is_file():
        raise ShadowInputError("existing ordinary SQLite ledger file required")
    state = audit_ledger(path)  # revalidate every row before trusting identity
    cp = bundle["checkpoint"]
    identity = (cp["run_id"], cp["run_attempt"], cp["artifact_id"])
    uri = path.resolve().as_uri().replace("file://", "file:") + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        matches = conn.execute(
            """SELECT seq, bundle_sha256, entry_sha256 FROM evidence
               WHERE run_id=? AND run_attempt=? AND artifact_id=?""",
            identity).fetchall()
    if len(matches) != 1 or matches[0][1] != digest:
        raise ShadowInputError("archived capture not uniquely found in verified ledger")
    return {
        "ledger_entries": state["entries"],
        "ledger_head_sha256": state["head_sha256"],
        "ledger_sequence": matches[0][0],
        "ledger_entry_sha256": matches[0][2],
        "ledger_externally_anchored": False,
    }


def link(bundle, *, ledger_path=None):
    canonical, bundle_sha = _validated_bundle(bundle)
    manifest, provenance = _manifest_from_archived_bundle(bundle)
    cycle = run_cycle(archived_bundle=bundle)
    if (cycle["paper_candidates"] or
            cycle["input_kind"] != "ARCHIVED_READ_ONLY_CAPTURE_V09" or
            any(cycle["model_decisions"][m]["status"] != "HOLD_CASH"
                for m in MODEL_ASSETS) or
            cycle["current_manifest_sha256"] != _digest(manifest)):
        raise ShadowInputError("archived decision cannot be promoted")
    cp = bundle["checkpoint"]
    if not isinstance(cp.get("receipt_sha256"), str) or not SHA64.fullmatch(
            cp["receipt_sha256"]):
        raise ShadowInputError("checkpoint SHA required")
    evidence = (_ledger_match(ledger_path, bundle, bundle_sha)
                if ledger_path is not None else None)
    report = {
        "schema": SCHEMA,
        "status": "ARCHIVED_HOLD_CASH_REPLAYED_NOT_CHRONOLOGICAL_SOURCE_OBSERVATION",
        "archived_run_id": cp["run_id"],
        "archived_run_attempt": cp["run_attempt"],
        "archived_artifact_id": cp["artifact_id"],
        "archived_bundle_sha256": bundle_sha,
        "archived_checkpoint_sha256": cp["receipt_sha256"],
        "archived_decision_at_utc": manifest["as_of_utc"],
        "frozen_policy_version": manifest["policy_version"],
        "manifest_sha256": _digest(manifest),
        "cycle_receipt_sha256": cycle["cycle_receipt_sha256"],
        "model_states": {m: cycle["model_decisions"][m]["status"]
                         for m in MODEL_ASSETS},
        "source_series_available": False,
        "suitable_for_v28_chronological_market_journal": False,
        "v09_ledger_reconciliation": evidence,
        "independent_time_attestation_verified": False,
        "independent_provider_source_verified": False,
        "historical_pit_verified": False,
        "oos_returns_evaluated": False,
        "qualified_m1_m2_m3": False,
        "orders_sent": 0, "paper_fills": 0, "financial_operations": 0,
        "database_writes": 0,
    }
    report["evidence_link_sha256"] = _digest(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archived-v09", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args()
    report = link(_load(args.archived_v09), ledger_path=args.ledger)
    print("ISL_EVIDENCE_DECISION_LINK_V29=" +
          json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
