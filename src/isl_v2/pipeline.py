"""Read a verified local manifest and generate deterministic DRY-RUN research artifacts.

No database connection, networking, actual orders, or account access.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .provenance import canonical_json, fingerprint, select_asof, utc


def run(job: dict) -> dict:
    required = ("run_key", "pipeline_name", "code_version", "as_of", "observations")
    for field in required:
        if not job.get(field):
            raise ValueError(f"Missing field: {field}")
    if not isinstance(job["observations"], list):
        raise ValueError("observations must be list")
    utc(job["as_of"])
    fingerprint_input = fingerprint(job)
    prices = select_asof(job["observations"], job["as_of"])
    return {"run_key": job["run_key"], "pipeline_name": job["pipeline_name"],
            "code_version": job["code_version"], "status": "DRY_RUN",
            "as_of": job["as_of"], "input_sha256": fingerprint_input,
            "input_count": len(job["observations"]), "available_count": len(prices),
            "prices_asof": prices, "no_live_execution": True}


def main() -> None:
    ap = argparse.ArgumentParser(description="Investment Lab offline PIT smoke test")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    job = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = run(job)
    Path(args.output).write_text(canonical_json(result) + "\n", encoding="utf-8")
    print("DRY_RUN", result["run_key"], "available:", result["available_count"],
          "input hash:", result["input_sha256"])


if __name__ == "__main__":
    main()
