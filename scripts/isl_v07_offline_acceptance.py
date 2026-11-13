"""Independent no-network offline acceptance for ISL v0.7 and UKNF v0.6.

Run from repository root: python3 -m scripts.isl_v07_offline_acceptance.
No secrets, HTTP, DB, accounts, trades or source downloads.
"""
from __future__ import annotations

import json
from pathlib import Path
import socket
import sys
import unittest

MODULES = (
    "scripts.mf_bond_market_history_v07",
    "scripts.mf_bond_turnover_metrics_v07",
    "scripts.public_first_market_quality_v07",
    "scripts.knf_mf_official_source_probe_v06",
    "scripts.knf_original_unit_history_research_v06",
)
TESTS = (
    "tests.test_mf_bond_market_history_v07",
    "tests.test_mf_bond_turnover_metrics_v07",
    "tests.test_public_first_market_quality_v07",
    "tests.test_knf_mf_official_source_probe_v06",
    "tests.test_knf_original_unit_history_research_v06",
)
EXPECTED_TESTS = 57


def _deny_network(*_args, **_kwargs):
    raise AssertionError("ISL_OFFLINE_ACCEPTANCE_FORBIDS_ALL_NETWORK")


def main() -> int:
    root=Path(__file__).resolve().parent.parent
    for module in MODULES:
        file=root.joinpath(*module.split(".")).with_suffix(".py")
        if not file.is_file():
            raise SystemExit("ISL_OFFLINE_MODULE_FILE_NOT_PRESENT:"+module)
        compile(file.read_text(encoding="utf-8"),str(file),"exec")
    socket.socket.connect=_deny_network
    socket.socket.connect_ex=_deny_network
    socket.create_connection=_deny_network
    tests=unittest.TestSuite()
    for module in TESTS:
        tests.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
    result=unittest.TextTestRunner(verbosity=1).run(tests)
    passed=(result.wasSuccessful() and result.testsRun==EXPECTED_TESTS
            and not result.skipped)
    print("ISL_V07_OFFLINE_ACCEPTANCE="+json.dumps({
        "status":"PASS" if passed else "FAIL",
        "ran":result.testsRun,
        "expected":EXPECTED_TESTS,
        "failures":len(result.failures),
        "errors":len(result.errors),
        "skipped":len(result.skipped),
        "network":"DENIED",
        "source_provenance":"SYNTHETIC_FIXTURES_ONLY_NOT_ORIGINAL_MF_HISTORY",
        "trading_operations":0,
        "db_writes":0,
    },sort_keys=True))
    return 0 if passed else 2


if __name__=="__main__":
    sys.exit(main())
