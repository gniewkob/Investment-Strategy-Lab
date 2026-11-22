# Manual exact-SHA GitHub Actions billing fallback (v0.1)

## When to use

**Primary CI remains GitHub Actions.** Use this manual **macOS + Python 3.12**
fallback only for a failed PR run of
`.github/workflows/isl-stack-chain-offline-ci.yml` when GitHub reports that
**both** `stack-ubuntu` and `stack-macos` jobs did not start owing to an
account-level **billing** block. It does not apply to a failed test, cancelled
run, queued job or a different workflow.

This is a **local test receipt, not a GitHub CI pass**. It must not set GitHub
commit statuses, edit branch rules, auto-merge, deploy, use credentials, contact
market providers or run any financial operation. Other GitHub CI checks must be
handled separately. A green local result never certifies the missing Ubuntu or
hosted macOS execution.

## Operator procedure — read-only GitHub metadata, offline local checks

1. In GitHub, open the failed PR Actions run, confirm its exact `head_sha`, and
   copy the **actual GitHub billing pre-start annotation** (not a guessed reason)
   to a temporary UTF-8 text file outside Git. If the annotation cannot be
   confirmed, **stop**: zero executed steps is not proof of a billing problem.
2. Download the run and all job metadata without modifying GitHub. For example:

   ```bash
   gh api repos/gniewkob/Investment-Strategy-Lab/actions/runs/REPLACE_RUN_ID > /tmp/isl-run.json
   gh api repos/gniewkob/Investment-Strategy-Lab/actions/runs/REPLACE_RUN_ID/jobs > /tmp/isl-jobs.json
   ```

3. On the **Mac mini**, prepare a separate **clean, detached checkout** at the
   exact PR SHA (use a new disposable clone/worktree; do not change an existing
   operational checkout). Run `git rev-parse HEAD` and confirm it equals the
   SHA shown by the GitHub run. Ensure Python **3.12** is selected. Keep the
   fallback runner script available separately: the SHA under review may not
   yet contain this tool.
4. Execute the runner as an **absolute script path** from its own checkout:

   ```bash
   python3.12 /PATH_TO_FALLBACK_TOOL/scripts/ci_billing_fallback_v01.py \
     --repository-root /PATH_TO_CLEAN_REVIEW_CHECKOUT \
     --sha REPLACE_EXACT_40_CHAR_SHA \
     --run-json /tmp/isl-run.json \
     --jobs-json /tmp/isl-jobs.json \
     --billing-note-file /tmp/isl-github-billing-note.txt \
     --out /tmp/isl-fallback-REPLACE_EXACT_40_CHAR_SHA.json
   ```

The tool fails closed **before running tests** unless all of these match:

- run: exact SHA, PR event, completed/failure, expected workflow path and URL;
- jobs: exactly `stack-ubuntu` and `stack-macos`, same run ID and SHA,
  completed/failure and **no executed steps**;
- separate operator-copied billing pre-start annotation;
- native macOS, Python 3.12, exact clean Git `HEAD`, and a new receipt path
  outside the checkout.

The exact Git SHA and clean worktree are rechecked after both commands.
Changes to tracked or untracked files invalidate a local PASS.

It then runs the two **exact offline commands** configured in the existing
stack workflow, without a shell, on the pinned checkout:

```bash
python3.12 -m unittest -v tests.test_isl_stack_chain_acceptance_v01
python3.12 -m scripts.isl_stack_chain_acceptance_v01 --repository-root .
```

Return code: `0` = both local commands passed, `1` = local check failed,
`2` = fallback blocked (invalid evidence or checkout). A failed local test
short-circuits the second check. No test stdout/stderr contents are sent to
the receipt; only byte counts and SHA-256 digests. The JSON includes source
snapshot hashes, source run URL, commit SHA, host and Python version, outcomes,
and these invariant fields:

```json
{
  "kind": "MANUAL_OFFLINE_LOCAL_FALLBACK_NOT_GITHUB_CI",
  "hosted_checks_passed": false,
  "merge_authorized": false,
  "deploy_authorized": false,
  "billing_attribution": "OPERATOR_COPIED_GITHUB_UI_UNVERIFIED"
}
```

The script validates the operator-supplied GitHub JSON snapshots and note
**structurally**, but does not independently authenticate their origin; its
receipt is **not an external attestation or signature**. Retain original
GitHub URLs and data when reviewing evidence. GitHub Actions remains BLOCKED,
even when the local check passes. Only rerun hosted checks after billing is
fixed; do not merge a PR that requires those checks until they actually pass.

No Mac execution, remote runner activation, credential setup, CI bypass,
deployment, or new scheduling is performed by this repository change.
