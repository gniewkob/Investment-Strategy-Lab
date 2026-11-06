"""Capture a research-only shadow decision with GitHub-run context.

This is a receipt *candidate*. Independent timing is NOT certified by environment
variables or by a local SHA-256 digest; downstream verification must fetch the
run and artifact metadata from GitHub independently, before using forward data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import re

from scripts.shadow_decision_engine_v05 import ShadowInputError, _digest, _utc, evaluate

SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = "gniewkob/Investment-Strategy-Lab"
EVENTS = {"pull_request", "workflow_dispatch", "schedule"}


def capture(metadata, captured_at):
    if not isinstance(metadata, dict) or set(metadata) != {
        "repository", "run_id", "run_attempt", "head_sha", "event"
    }:
        raise ShadowInputError("invalid GitHub run metadata envelope")
    if metadata["repository"] != REPO:
        raise ShadowInputError("unexpected repository")
    if type(metadata["run_id"]) is not int or metadata["run_id"] <= 0:
        raise ShadowInputError("invalid run id")
    if type(metadata["run_attempt"]) is not int or metadata["run_attempt"] <= 0:
        raise ShadowInputError("invalid run attempt")
    if not isinstance(metadata["head_sha"], str) or not SHA.fullmatch(metadata["head_sha"]):
        raise ShadowInputError("invalid commit SHA")
    if metadata["event"] not in EVENTS:
        raise ShadowInputError("unsupported event")
    instant = _utc(captured_at)
    if instant > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ShadowInputError("future capture time")
    decision = evaluate({
        "mode": "EDUCATIONAL_SHADOW_ONLY",
        "as_of_utc": instant.isoformat(),
        "series": {},  # Never promote unqualified NBP/TBSP references into total return.
        "policy_version": "V05_FROZEN_001",
    })
    if decision["eligible_models"] or any(
        item["status"] != "HOLD_CASH" for item in decision["model_decisions"].values()
    ):
        raise ShadowInputError("unexpected eligible shadow model")
    report = {
        "schema": "ISL_SHADOW_CAPTURE_V07_001",
        "run_context_declared": metadata,
        "captured_at_utc": instant.isoformat(),
        "decision": decision,
        "github_metadata_independently_verified": False,
        "artifact_timestamp_independently_verified": False,
        "prospective_timing_certified": False,
        "source_rights_independently_certified": False,
        "future_performance_observed": False,
        "orders_sent": 0,
        "paper_fills": 0,
        "database_writes": 0,
    }
    report["capture_sha256"] = _digest(report)
    return report


def main():
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        meta = {
            "repository": os.environ["GITHUB_REPOSITORY"],
            "run_id": int(os.environ["GITHUB_RUN_ID"]),
            "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
            # pull_request GITHUB_SHA denotes the temporary merge commit,
            # whereas Actions run metadata uses the PR HEAD commit SHA.
            "head_sha": os.environ.get("GITHUB_CAPTURE_HEAD_SHA") or os.environ["GITHUB_SHA"],
            "event": os.environ["GITHUB_EVENT_NAME"],
        }
    except (KeyError, ValueError) as exc:
        raise ShadowInputError("required GitHub environment not available") from exc
    result = capture(meta, datetime.now(timezone.utc).isoformat())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("ISL_SHADOW_CAPTURE_V07=" + json.dumps({
        "status": "DECLARED_RUN_CONTEXT_NOT_INDEPENDENT_ATTESTATION",
        "capture_sha256": result["capture_sha256"],
        "decision_sha256": result["decision"]["decision_fingerprint_sha256"],
        "eligible_models": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
