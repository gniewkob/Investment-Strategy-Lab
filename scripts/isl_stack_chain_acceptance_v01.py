"""Read-only, synthetic A2->B1->C1->C2 stacked-tree acceptance.

Verifies exactly pinned Git source blobs and archived v0.9 bytes, then executes
the offline unit suites with Python socket connects disabled. This gate
provides no rights, historical-PIT, investability or performance attestation.
No external DB, wallet, exchange, order, broker or market feed is used.
"""
from __future__ import annotations

import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path
import socket
import sys
import unittest

A2_HEAD = "3f6c727ccb2598fd4a11a3fee49b98270d2132a0"
B1_HEAD = "ca5ba310451d3fbcfda86d1e2bd38e697c29f6a1"
C1_HEAD = "b44d23ebb4c1f3ec9974dbeec2b3b85e110e2ba1"
V09_SHA256 = "4a4fece5c84996cf7e663abae81d5c583e5397904bbe17ab57b8f0a150b797d3"
V09_PATH = "evidence/shadow/v09/checkpoint-bundle-run-42305280062.json"
# Git blob SHA-1 is an exact byte-identity check, not a licence or authenticity certificate.
EXPECTED_BLOBS = {
    ".github/workflows/isl-a2-offline-source-evidence-ci.yml": "aa92f5347c369a2f91c8ebb10374abce4e2ea5f0",
    "docs/A2_OFFLINE_SOURCE_EVIDENCE_ACCEPTANCE_PL.md": "9f7e2ca40777edea2a4f15cf99a80208a711a3ec",
    "docs/A2_POST_SPLIT_OFFLINE_GATE_REVIEW_20261109_PL.md": "3738e2f83ef77548c799a25ac29091fa1a37d13c",
    "scripts/nbp_bondspot_exact_date_v04.py": "67bf0ee370ab277aee282622bb4f7250355e8cf5",
    "scripts/nbp_reference_capture.py": "07f97726687540960bdae2ef93070a86844473bd",
    "scripts/reference_archive_calendar_v04.py": "48c8cdb25acc2e846628443d2fa5cd1897ef47dd",
    "scripts/vanguard_nav_to_pln_reference_v04.py": "d04ba8927cf69782cdccd94b3636fc4eddb38270",
    "scripts/vanguard_xlsx_offline_intake_v04.py": "8091e2a75978b2e4049bfd9d78c5ed5c1b29ed3b",
    "tests/test_a2_explicit_source_access_v01.py": "06522a0e25b104db3f07ab5b686551fe0852727c",
    "tests/test_reference_archive_calendar_v04.py": "df2d713aabacb9b29c100ccea54e13a2051b3aed",
    "tests/test_vanguard_nav_to_pln_reference_v04.py": "169241b4b7d51d8dfb0585b1d4cf70848567d017",
    "tests/test_vanguard_xlsx_offline_intake_v04.py": "07a6ef9678b96741640ef9a68390ccb10f74b787",
    # Spot-check immutable inherited B1 and C1 code against their reviewed heads.
    "scripts/shadow_decision_engine_v05.py": "0078a3b04de4fa9e86764facab1741e91e9055ad",
    "scripts/research_decision_controller_v15.py": "ff57fe4031ddb9ab127a280b184363398d08be26",
}

SUITES = {
    "A2": (37, (
        "tests.test_vanguard_xlsx_offline_intake_v04",
        "tests.test_reference_archive_calendar_v04",
        "tests.test_a2_explicit_source_access_v01",
        "tests.test_vanguard_nav_to_pln_reference_v04",
    )),
    "B1": (47, (
        "tests.test_shadow_decision_engine_v05",
        "tests.test_shadow_capture_v07",
        "tests.test_github_checkpoint_verify_v08",
        "tests.test_shadow_evidence_ledger_v09",
        "tests.test_shadow_external_anchor_v10",
        "tests.test_shadow_backup_restore_v11",
    )),
    "C1": (53, (
        "tests.test_shadow_forward_evaluation_v05",
        "tests.test_shadow_journal_v06",
        "tests.test_research_decision_controller_v15",
        "tests.test_research_decision_pipeline_v16",
        "tests.test_research_forward_journal_v17",
    )),
    "C2": (21, (
        "tests.test_real_reference_gateway_v18",
        "tests.test_acwi_netr_offline_intake_v19",
    )),
}


class ChainBlocked(ValueError):
    """A discrepancy prevents integration acceptance."""


def git_blob_sha(raw: bytes) -> str:
    return sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _bounded_file(root: Path, relative: str) -> bytes:
    file = root / relative
    if not file.is_file() or file.is_symlink():
        raise ChainBlocked("missing or symlinked source: " + relative)
    current = file.parent
    while current != root:
        if current.is_symlink():
            raise ChainBlocked("symlinked source directory: " + relative)
        if root not in current.parents:
            raise ChainBlocked("path outside repository")
        current = current.parent
    if file.stat().st_size > 1_000_000:
        raise ChainBlocked("unexpected source file size: " + relative)
    return file.read_bytes()


def verify_snapshot(root: Path) -> dict:
    if not root.is_dir() or root.is_symlink():
        raise ChainBlocked("repository root must be a regular directory")
    checked = 0
    for path, expected in EXPECTED_BLOBS.items():
        actual = git_blob_sha(_bounded_file(root, path))
        if actual != expected:
            raise ChainBlocked("A2/B1/C1 source blob changed: " + path)
        checked += 1
    if sha256(_bounded_file(root, V09_PATH)).hexdigest() != V09_SHA256:
        raise ChainBlocked("pinned original v0.9 checkpoint bytes changed")
    return {
        "status": "PINNED_OFFLINE_SOURCE_IDENTITY_OK",
        "a2_upstream_head": A2_HEAD,
        "b1_upstream_head": B1_HEAD,
        "c1_upstream_head": C1_HEAD,
        "a2_pinned_files": 12,
        "inherited_b1_c1_spot_checks": 2,
        "checked_blobs": checked,
        "v09_sha256_verified": True,
        "qualified_market_series": 0,
        "historical_pit_certified": False,
        "trading_authorized": False,
    }


def _deny_network(*_args, **_kwargs):
    raise ChainBlocked("stacked offline test attempted a network connection")


def run_offline_suites() -> dict:
    # Explicitly forbid Python socket transports during all suites, even
    # though the test fixtures do not require real providers.
    socket.socket.connect = _deny_network
    socket.socket.connect_ex = _deny_network
    socket.create_connection = _deny_network
    counts = {}
    for layer, (expected, modules) in SUITES.items():
        suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
        outcome = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
        if not outcome.wasSuccessful() or outcome.skipped or outcome.testsRun != expected:
            raise ChainBlocked(
                f"{layer} failed or test count changed: {outcome.testsRun} vs {expected}"
            )
        counts[layer] = outcome.testsRun
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    receipt = verify_snapshot(args.repository_root.absolute())
    counts = run_offline_suites()
    output = {
        "status": "STACK_OFFLINE_CONTRACTS_PASS",
        "source_identity": receipt,
        "test_counts": counts,
        "total_tests": sum(counts.values()),
        "real_orders": 0,
        "paper_fills": 0,
        "database_writes": 0,
        "provider_fetches": 0,
        "model_qualification": "BLOCKED_MISSING_LICENSED_PIT_TOTAL_RETURN_SERIES",
        "integration_to_main_authorized": False,
    }
    print("ISL_STACK_CHAIN_ACCEPTANCE=" + json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
