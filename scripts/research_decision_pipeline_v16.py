"""v0.16 executable research decision *cycle*, never financial execution.

Accept either qualified source manifests or a previously archived v0.9
GitHub shadow-capture bundle. It runs the v0.15 controller, freezes a
reproducible summary and reports HOLD_CASH when histories are missing.
No network, broker access, account credentials, or DB writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.research_decision_controller_v15 import decide
from scripts.research_backtest_decision_boundary_v01 import review_backtest
from scripts.shadow_decision_engine_v05 import (
    ShadowInputError, _digest, evaluate, MODEL_ASSETS,
)

SCHEMA = "ISL_RESEARCH_DECISION_PIPELINE_V16_001"
ARCHIVE_SCHEMA = "ISL_SHADOW_CAPTURE_V07_001"
MAX_INPUT_BYTES = 8 * 1024 * 1024


def _load(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise ShadowInputError("expected bounded regular JSON input")
    with path.open("rb") as source:
        data = source.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ShadowInputError("research input is too large")
    return json.loads(data)


def _manifest_from_archived_bundle(bundle):
    if not isinstance(bundle, dict) or set(bundle) != {
            "artifacts", "capture", "checkpoint", "run"}:
        raise ShadowInputError("invalid v0.9 archived bundle schema")
    cap = bundle["capture"]
    if not isinstance(cap, dict) or cap.get("schema") != ARCHIVE_SCHEMA:
        raise ShadowInputError("expected real v0.7 archival capture")
    captured_digest = cap.get("capture_sha256")
    if not isinstance(captured_digest, str) or _digest({
            k: v for k, v in cap.items() if k != "capture_sha256"
    }) != captured_digest:
        raise ShadowInputError("archived capture fingerprint mismatch")
    frozen = cap.get("decision")
    if not isinstance(frozen, dict):
        raise ShadowInputError("frozen source decision required")
    frozen_hash = frozen.get("decision_fingerprint_sha256")
    if not isinstance(frozen_hash, str) or _digest({
            k: v for k, v in frozen.items()
            if k != "decision_fingerprint_sha256"
    }) != frozen_hash:
        raise ShadowInputError("archived decision fingerprint mismatch")
    checkpoint = bundle["checkpoint"]
    if not isinstance(checkpoint, dict) or (
            checkpoint.get("capture_sha256") != captured_digest or
            checkpoint.get("decision_sha256") != frozen_hash or
            checkpoint.get("github_api_metadata_matches") is not True or
            checkpoint.get("status") !=
            "GITHUB_API_AND_CAPTURE_MATCHED_NOT_TRUSTED_TIMESTAMP_CERTIFICATE"):
        raise ShadowInputError("archive checkpoint does not match capture")
    for doc in (cap, checkpoint):
        for key in ("orders_sent", "paper_fills", "database_writes"):
            if doc.get(key) != 0:
                raise ShadowInputError("financial operation in archived source")
    meta = cap.get("run_context_declared")
    run = bundle["run"]
    if not isinstance(meta, dict) or not isinstance(run, dict) or (
            meta.get("repository") != "gniewkob/Investment-Strategy-Lab" or
            meta.get("run_id") != run.get("id") or
            meta.get("head_sha") != run.get("head_sha") or
            run.get("conclusion") != "success"):
        raise ShadowInputError("run context inconsistent with capture")
    if frozen.get("eligible_models") != [] or not all(
            frozen.get("model_decisions", {}).get(m, {}).get("status") == "HOLD_CASH"
            for m in MODEL_ASSETS):
        raise ShadowInputError("archived capture unexpectedly promotes a model")
    # This archived source is verified only at the metadata and receipt
    # level. Its actual source series are absent; never fabricate them.
    manifest = {
        "mode": "EDUCATIONAL_SHADOW_ONLY",
        "as_of_utc": cap["captured_at_utc"],
        "policy_version": "V05_FROZEN_001",
        "series": {},
    }
    check = evaluate(manifest)
    if check["decision_fingerprint_sha256"] != frozen_hash:
        raise ShadowInputError("archived decision differs from re-executed v0.5")
    return manifest, {
        "archive_status": "CHECKPOINT_METADATA_MATCHED_NOT_ORIGINAL_BYTES_OR_PIT_PROOF",
        "archived_capture_sha256": captured_digest,
        "archived_checkpoint_sha256": checkpoint.get("receipt_sha256"),
        "archived_run_id": meta["run_id"],
        "archived_data_is_qualified_model_series": False,
    }


def run_cycle(*, current=None, previous=None, archived_bundle=None,
              backtest_report=None):
    if backtest_report is not None:
        if current is not None or previous is not None or archived_bundle is not None:
            raise ShadowInputError("A1 backtest cannot be combined with decision sources")
        # Intentional one-way firewall. Never call decide() on A1 data.
        return review_backtest(backtest_report)
    if (current is None) == (archived_bundle is None):
        raise ShadowInputError("exactly one current manifest or archived bundle required")
    if archived_bundle is not None:
        if previous is not None:
            raise ShadowInputError("archived empty-source cycle cannot take a prior manifest")
        current, provenance = _manifest_from_archived_bundle(archived_bundle)
        input_kind = "ARCHIVED_READ_ONLY_CAPTURE_V09"
    else:
        provenance = {
            "archive_status": None,
            "archived_capture_sha256": None,
            "archived_checkpoint_sha256": None,
            "archived_run_id": None,
            "archived_data_is_qualified_model_series": False,
        }
        input_kind = "EXPLICIT_SOURCE_MANIFEST"
    decision = decide(current, previous)
    states = decision["model_states"]
    summary = {
        code: {
            "status": state["status"],
            "reason": state["reason"],
            "blockers": state["blockers"],
            "virtual_target": state["virtual_target"],
        }
        for code, state in states.items()
    }
    result = {
        "schema": SCHEMA,
        "status": ("PAPER_RESEARCH_CANDIDATES_ONLY" if decision["paper_candidates"]
                   else "HOLD_CASH_SOURCE_OR_CONFIRMATION_BLOCKED"),
        "input_kind": input_kind,
        "as_of_utc": decision["current_as_of_utc"],
        "decision_controller_sha256": decision["controller_receipt_sha256"],
        "current_manifest_sha256": decision["current_source_manifest_sha256"],
        "previous_manifest_sha256": decision["previous_source_manifest_sha256"],
        "model_decisions": summary,
        "paper_candidates": decision["paper_candidates"],
        "missing_or_blocked_sources": decision["source_blockers"],
        "historical_point_in_time_certified": False,
        "source_license_independently_certified": False,
        "performance_or_alpha_proven": False,
        "real_order_authorized": False,
        "orders_sent": 0, "paper_fills": 0,
        "financial_operations": 0, "database_writes": 0,
        "provenance": provenance,
    }
    result["cycle_receipt_sha256"] = _digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--current", type=Path)
    inputs.add_argument("--archived-v09", type=Path)
    inputs.add_argument("--backtest-report", type=Path)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    result = run_cycle(
        current=_load(args.current) if args.current else None,
        archived_bundle=_load(args.archived_v09) if args.archived_v09 else None,
        previous=_load(args.previous) if args.previous else None,
        backtest_report=_load(args.backtest_report) if args.backtest_report else None,
    )
    label = ("ISL_A1_TO_C1_FIREWALL=" if args.backtest_report
             else "ISL_RESEARCH_CYCLE_V16=")
    print(label + json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
