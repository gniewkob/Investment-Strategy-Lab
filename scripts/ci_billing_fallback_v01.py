"""Manual, offline Mac fallback for the ISL stack workflow's pre-run billing block.

This is a *local* evidence runner, not a GitHub status check or a merge gate.
Only the two fixed offline commands from isl-stack-chain-offline-ci.yml run.
No GitHub credentials, source network fetches, database or account access.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time


REPOSITORY = "gniewkob/Investment-Strategy-Lab"
WORKFLOW = ".github/workflows/isl-stack-chain-offline-ci.yml"
JOB_NAMES = frozenset({"stack-ubuntu", "stack-macos"})
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
MAX_SNAPSHOT_BYTES = 2_000_000
MAX_TEST_SECONDS = 900


class FallbackBlocked(ValueError):
    """The local fallback is not admissible; do not execute test commands."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshot(path: Path) -> tuple[dict, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FallbackBlocked("Cannot read operator-supplied GitHub snapshot") from exc
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise FallbackBlocked("GitHub snapshot exceeds size limit")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise FallbackBlocked("GitHub snapshot is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise FallbackBlocked("GitHub snapshot must be a JSON object")
    return payload, _digest(raw)


def assess_billing_preexecution(
    run: dict, jobs_payload: dict, expected_sha: str, billing_note: str
) -> dict:
    """Inspect exact-SHA metadata and require a separately copied billing notice.

    The note is operator-supplied, not authenticated by this offline script.
    GitHub's check-run annotations cannot be reliably retrieved by this tool.
    """
    if not SHA_RE.fullmatch(expected_sha):
        raise FallbackBlocked("--sha must be an exact, lowercase commit SHA")
    if (
        not isinstance(billing_note, str)
        or not (20 <= len(billing_note) <= 1000)
        or "billing" not in billing_note.casefold()
        or "not started" not in billing_note.casefold()
    ):
        raise FallbackBlocked("An explicit GitHub pre-start billing annotation is required")
    run_id = run.get("id")
    if type(run_id) is not int or run_id <= 0:
        raise FallbackBlocked("Invalid workflow run ID")
    url = f"https://github.com/{REPOSITORY}/actions/runs/{run_id}"
    if (
        run.get("head_sha") != expected_sha
        or run.get("html_url") != url
        or run.get("path") != WORKFLOW
        or run.get("event") != "pull_request"
        or run.get("status") != "completed"
        or run.get("conclusion") != "failure"
    ):
        raise FallbackBlocked("GitHub workflow run is not the exact failed PR stack run")
    jobs = jobs_payload.get("jobs")
    if (
        not isinstance(jobs, list)
        or type(jobs_payload.get("total_count")) is not int
        or jobs_payload["total_count"] != 2
        or len(jobs) != 2
    ):
        raise FallbackBlocked("Expected exactly the two stack workflow jobs")
    observed = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise FallbackBlocked("Invalid job in GitHub snapshot")
        name = job.get("name")
        if (
            name not in JOB_NAMES
            or name in observed
            or type(job.get("run_id")) is not int
            or job["run_id"] != run_id
            or job.get("head_sha") != expected_sha
            or job.get("status") != "completed"
            or job.get("conclusion") != "failure"
            or job.get("steps") != []
        ):
            raise FallbackBlocked("Job failed after starting, has steps or mismatches SHA")
        observed.add(name)
    if observed != JOB_NAMES:
        raise FallbackBlocked("Expected both stack jobs")
    return {
        "workflow_run_url": url,
        "github_run_id": run_id,
        "hosted_ci": "FAILURE_WITH_ZERO_STEPS",
        "billing_attribution": "OPERATOR_COPIED_GITHUB_UI_UNVERIFIED",
        "billing_note_sha256": _digest(billing_note.encode("utf-8")),
        "job_names": sorted(observed),
    }


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FallbackBlocked("Cannot verify local Git checkout") from exc
    if result.returncode != 0:
        raise FallbackBlocked("Cannot verify local Git checkout")
    return result.stdout.strip()


def verify_checkout(root: Path, expected_sha: str, *, require_macos: bool = True) -> None:
    if require_macos and platform.system() != "Darwin":
        raise FallbackBlocked("Operational fallback must run on macOS")
    if sys.version_info[:2] != (3, 12):
        raise FallbackBlocked("Operational fallback requires Python 3.12")
    if not SHA_RE.fullmatch(expected_sha):
        raise FallbackBlocked("Invalid exact commit SHA")
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise FallbackBlocked("--repository-root is not the checkout root")
    if _git(root, "rev-parse", "HEAD") != expected_sha:
        raise FallbackBlocked("Checkout HEAD does not match the required commit SHA")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise FallbackBlocked("Checkout must be clean, including untracked files")


def run_offline_stack(root: Path) -> list[dict]:
    steps = [
        [sys.executable, "-m", "unittest", "-v", "tests.test_isl_stack_chain_acceptance_v01"],
        [sys.executable, "-m", "scripts.isl_stack_chain_acceptance_v01", "--repository-root", "."],
    ]
    results = []
    for command in steps:
        start = time.monotonic()
        try:
            completed = subprocess.run(
                command, cwd=root, capture_output=True, timeout=MAX_TEST_SECONDS,
                check=False,
            )
            exit_code = completed.returncode
            stdout, stderr = completed.stdout, completed.stderr
            timeout = False
        except subprocess.TimeoutExpired as exc:
            exit_code = None
            stdout, stderr = exc.stdout or b"", exc.stderr or b""
            timeout = True
        except OSError:
            exit_code, stdout, stderr, timeout = None, b"", b"", False
        results.append({
            "command": command[1:],  # do not expose machine-local Python binary path
            "exit_code": exit_code,
            "timed_out": timeout,
            "elapsed_ms": round((time.monotonic() - start) * 1000),
            "stdout_sha256": _digest(stdout),
            "stderr_sha256": _digest(stderr),
            "stdout_bytes": len(stdout),
            "stderr_bytes": len(stderr),
        })
        if exit_code != 0 or timeout:
            break
    return results


def execute(args: argparse.Namespace) -> int:
    root = Path(args.repository_root).resolve()
    out = Path(args.out).resolve()
    if out == root or root in out.parents:
        raise FallbackBlocked("Receipt must be outside the tracked checkout")
    if not out.parent.is_dir() or out.exists():
        raise FallbackBlocked("Receipt parent must exist; do not overwrite evidence")
    run, run_digest = _snapshot(Path(args.run_json))
    jobs, jobs_digest = _snapshot(Path(args.jobs_json))
    try:
        billing_note = Path(args.billing_note_file).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise FallbackBlocked("Cannot read the operator-copied GitHub billing annotation") from exc
    triage = assess_billing_preexecution(run, jobs, args.sha, billing_note)
    verify_checkout(root, args.sha)
    steps = run_offline_stack(root)
    try:
        verify_checkout(root, args.sha)
        checkout_unchanged = True
    except FallbackBlocked:
        checkout_unchanged = False
    passed = (
        checkout_unchanged
        and len(steps) == 2
        and all(step["exit_code"] == 0 and not step["timed_out"] for step in steps)
    )
    receipt = {
        "schema_version": 1,
        "kind": "MANUAL_OFFLINE_LOCAL_FALLBACK_NOT_GITHUB_CI",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": REPOSITORY,
        "commit_sha": args.sha,
        "workflow": WORKFLOW,
        "run_snapshot_sha256": run_digest,
        "jobs_snapshot_sha256": jobs_digest,
        **triage,
        "hosted_checks_passed": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "checkout_unchanged_after_tests": checkout_unchanged,
        "test_host": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
        "local_test_status": "PASS" if passed else "FAIL",
        "steps": steps,
    }
    # Exclusive create keeps existing receipts intact and produces no repo changes.
    try:
        with out.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2)
            stream.write("\n")
    except OSError as exc:
        raise FallbackBlocked("Could not create the local evidence receipt") from exc
    print(json.dumps({"local_test_status": receipt["local_test_status"], "commit_sha": args.sha, "receipt": str(out)}))
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run-json", required=True)
    parser.add_argument("--jobs-json", required=True)
    parser.add_argument("--billing-note-file", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except FallbackBlocked as exc:
        print(f"FALLBACK_BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
