"""Read-only-in-refs integration dry-run for diverged ISL research branches.

Uses Git merge-tree in a local repository without checkout, commit, merge,
rebase, network fetch, credential use, or modifying branch refs. Git itself
may create unreachable tree objects in its object store, never a new ref.
Capture only metadata, not potentially private source diffs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

SCHEMA = "ISL_GIT_INTEGRATION_PREFLIGHT_001"
HEX = re.compile(r"^[0-9a-f]{40,64}$")


def _run(repo, *args, ok=(0,)):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True,
        check=False, timeout=60,
    )
    if result.returncode not in ok:
        raise RuntimeError(
            "git command did not complete successfully: " + args[0] +
            " (exit " + str(result.returncode) + ")"
        )
    return result


def preflight(repo, *, left="origin/main", right="origin/codex/v04-monthly-backtest-engine-20261106"):
    repo = Path(repo).resolve()
    if not repo.is_dir():
        raise ValueError("existing local git repository directory required")
    _run(repo, "rev-parse", "--is-inside-work-tree")
    left_sha = _run(repo, "rev-parse", "--verify", left + "^{commit}").stdout.decode().strip()
    right_sha = _run(repo, "rev-parse", "--verify", right + "^{commit}").stdout.decode().strip()
    merge_base = _run(repo, "merge-base", left_sha, right_sha).stdout.decode().strip()
    if not all(HEX.fullmatch(v) for v in (left_sha, right_sha, merge_base)):
        raise RuntimeError("invalid git revision resolved")
    left_paths = set(filter(None, _run(
        repo, "diff", "--name-only", "-z", merge_base, left_sha).stdout.decode().split("\0")))
    right_paths = set(filter(None, _run(
        repo, "diff", "--name-only", "-z", merge_base, right_sha).stdout.decode().split("\0")))
    # git merge-tree --write-tree returns 0 clean, 1 conflicts, >1 error.
    # Unlike git merge, it does not modify index, working files or refs.
    merged = _run(repo, "merge-tree", "--write-tree", left_sha, right_sha, ok=(0, 1))
    status = "CLEAN_TREE_MERGE_ONLY_NOT_TESTED" if merged.returncode == 0 else "CONFLICTS_DETECTED_DO_NOT_MERGE"
    result = {
        "schema": SCHEMA,
        "status": status,
        "base_commit_sha": merge_base,
        "main_commit_sha": left_sha,
        "research_commit_sha": right_sha,
        "left_changed_paths_count": len(left_paths),
        "right_changed_paths_count": len(right_paths),
        "overlapping_changed_paths": sorted(left_paths & right_paths),
        "merge_tree_exit_code": merged.returncode,
        "merge_tree_output_sha256": sha256(merged.stdout).hexdigest(),
        "working_tree_modified_by_tool": False,
        "refs_modified_by_tool": False,
        "financial_operations": 0,
        "database_writes": 0,
        "integration_approved": False,
    }
    if merged.returncode == 0:
        tree_sha = merged.stdout.decode().strip()
        if not HEX.fullmatch(tree_sha):
            raise RuntimeError("git merge-tree output did not return a tree SHA")
        result["result_tree_sha"] = tree_sha
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--main-ref", default="origin/main")
    p.add_argument("--research-ref", default="origin/codex/v04-monthly-backtest-engine-20261106")
    args=p.parse_args()
    result=preflight(args.repo, left=args.main_ref, right=args.research_ref)
    print("ISL_PR96_MERGE_PREFLIGHT=" + json.dumps(result, sort_keys=True, separators=(",", ":")))
    if result["merge_tree_exit_code"] != 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
