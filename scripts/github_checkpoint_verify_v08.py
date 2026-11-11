"""Read-only GitHub API evidence check for a v0.7 shadow capture artifact.

Inputs MUST be separately fetched from GitHub's API and artifact download.
Checking JSON alone cannot prove those inputs are from GitHub, nor cryptographically
certify a creation timestamp. No market prices, trades or database writes.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

from scripts.shadow_capture_v07 import REPO
from scripts.shadow_decision_engine_v05 import ShadowInputError, _digest, _utc

SCHEMA = "ISL_GITHUB_CHECKPOINT_V08_001"
WORKFLOW = ".github/workflows/shadow-capture-v07.yml"
ARTIFACT_PREFIX = "isl-v07-shadow-capture-run-"


def verify(capture, run, artifacts, *, cutoff_utc):
    if not all(isinstance(x, dict) for x in (capture, run, artifacts)):
        raise ShadowInputError("independent GitHub JSON objects required")
    if capture.get("schema") != "ISL_SHADOW_CAPTURE_V07_001":
        raise ShadowInputError("invalid capture schema")
    raw_hash = capture.get("capture_sha256")
    if not isinstance(raw_hash, str) or raw_hash != _digest({
        k: v for k, v in capture.items() if k != "capture_sha256"
    }):
        raise ShadowInputError("capture content fingerprint mismatch")
    decision = capture.get("decision")
    if not isinstance(decision, dict) or decision.get("decision_fingerprint_sha256") != _digest({
        k: v for k, v in decision.items() if k != "decision_fingerprint_sha256"
    }):
        raise ShadowInputError("frozen decision fingerprint mismatch")
    if decision.get("mode") != "EDUCATIONAL_SHADOW_ONLY" or decision.get("policy_version") != "V05_FROZEN_001":
        raise ShadowInputError("unexpected model policy")
    if decision.get("eligible_models") != [] or len(decision.get("model_decisions", {})) != 3 or any(
        x.get("status") != "HOLD_CASH" for x in decision["model_decisions"].values()
    ):
        raise ShadowInputError("non-HOLD_CASH decision cannot be accepted")
    if any(capture.get(k) is not False for k in (
        "github_metadata_independently_verified", "artifact_timestamp_independently_verified",
        "prospective_timing_certified", "source_rights_independently_certified",
        "future_performance_observed"
    )):
        raise ShadowInputError("capture improperly claims independent certification")
    if any(capture.get(k) != 0 for k in ("orders_sent", "paper_fills", "database_writes")):
        raise ShadowInputError("financial side-effect present")
    context = capture.get("run_context_declared")
    if not isinstance(context, dict) or context.get("repository") != REPO:
        raise ShadowInputError("unexpected repository identity")
    run_id = context.get("run_id")
    attempt = context.get("run_attempt")
    sha = context.get("head_sha")
    event = context.get("event")
    if (type(run_id) is not int or run_id <= 0 or type(attempt) is not int
            or attempt <= 0):
        raise ShadowInputError("invalid run context IDs")
    if (run.get("id") != run_id or run.get("run_attempt") != attempt
        or run.get("head_sha") != sha or run.get("event") != event
        or run.get("status") != "completed" or run.get("conclusion") != "success"):
        raise ShadowInputError("GitHub run identity or success mismatch")
    if run.get("repository", {}).get("full_name") != REPO:
        raise ShadowInputError("GitHub run repository mismatch")
    if run.get("path", "").split("@", 1)[0] != WORKFLOW:
        raise ShadowInputError("unexpected capture workflow path")
    if run.get("head_repository", {}).get("full_name") != REPO:
        raise ShadowInputError("external workflow head repository prohibited")
    captured = _utc(capture.get("captured_at_utc"))
    if captured != _utc(decision.get("as_of_utc")):
        raise ShadowInputError("capture date differs from frozen decision date")
    started = _utc(run.get("run_started_at"))
    created = _utc(run.get("created_at"))
    updated = _utc(run.get("updated_at"))
    cutoff = _utc(cutoff_utc)
    if not created <= started <= captured <= updated:
        raise ShadowInputError("GitHub chronology mismatch")
    if updated >= cutoff:
        raise ShadowInputError("GitHub run must be complete before independently supplied cutoff")
    items = artifacts.get("artifacts")
    if not isinstance(items, list):
        raise ShadowInputError("GitHub artifacts list missing")
    name = f"{ARTIFACT_PREFIX}{run_id}-attempt-{attempt}"
    matching = [x for x in items if isinstance(x, dict) and x.get("name") == name]
    if len(matching) != 1:
        raise ShadowInputError("exactly one matching artifact required")
    artifact = matching[0]
    if (type(artifact.get("id")) is not int or artifact["id"] <= 0
            or artifact.get("expired") is not False
            or artifact.get("workflow_run", {}).get("id") != run_id
            or artifact.get("workflow_run", {}).get("head_sha") != sha):
        raise ShadowInputError("artifact identity or retention invalid")
    artifact_created = _utc(artifact.get("created_at"))
    # GitHub Actions artifact timestamps have second resolution, while the
    # capture receipt records fractional seconds. Treat a within-second
    # overlap as ambiguous ordering, not a proven early artifact. An artifact
    # one or more complete seconds earlier is still rejected. The result does
    # NOT certify independent timing.
    if artifact_created >= cutoff or artifact_created + timedelta(seconds=1) <= captured:
        raise ShadowInputError("artifact was not preserved before cutoff")
    return {
        "schema": SCHEMA,
        "status": "GITHUB_API_AND_CAPTURE_MATCHED_NOT_TRUSTED_TIMESTAMP_CERTIFICATE",
        "run_id": run_id,
        "run_attempt": attempt,
        "artifact_id": artifact["id"],
        "capture_sha256": raw_hash,
        "decision_sha256": decision["decision_fingerprint_sha256"],
        "api_run_created_at": created.isoformat(),
        "api_artifact_created_at": artifact_created.isoformat(),
        "independently_supplied_cutoff_utc": cutoff.isoformat(),
        "github_api_metadata_matches": True,
        "artifact_bytes_externally_authenticated": False,
        "trusted_timestamp_certified": False,
        "prospective_performance_verified": False,
        "model_returns_calculated": False,
        "orders_sent": 0, "paper_fills": 0, "database_writes": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--cutoff-utc", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    result = verify(read(args.capture), read(args.run), read(args.artifacts),
                    cutoff_utc=args.cutoff_utc)
    result["receipt_sha256"] = _digest(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("ISL_GITHUB_CHECKPOINT_V08=" + json.dumps({
        "status": result["status"], "run_id": result["run_id"],
        "artifact_id": result["artifact_id"]}, sort_keys=True))


if __name__ == "__main__":
    main()
