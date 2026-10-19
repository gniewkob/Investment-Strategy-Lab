"""Operator-only EIA original HTML local archive and offline verification.

This script has NO Neon URL, credentials, broker, trade or scheduled job.
Use ONLY an existing private directory outside a Git checkout on a persistent
machine. Never use a public artifact, CI ephemeral drive or public repository
as the only archive. It does not claim tamper-proof WORM storage.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys

from src.isl_v2.eia_sources import SOURCES
from src.isl_v2.eia_versioned_ingest import fetch_plan
from src.isl_v2.eia_raw_archive import archive_snapshot, verify_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="EIA original HTML local PRIVATE source archive, NO DATABASE")
    cmd = parser.add_subparsers(dest="command", required=True)
    capture = cmd.add_parser("capture", help="Fetch official EIA and stage source bytes locally")
    capture.add_argument("--source", choices=sorted(SOURCES), required=True)
    capture.add_argument("--archive-root", required=True)
    capture.add_argument("--max-age-days", type=int, default=420)
    verify = cmd.add_parser("verify", help="Independently verify saved source WITHOUT web")
    verify.add_argument("--source", choices=sorted(SOURCES), required=True)
    verify.add_argument("--archive-root", required=True)
    verify.add_argument("--sha256", required=True)
    verify.add_argument("--retrieved-at", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            plan = fetch_plan(args.source, datetime.now(timezone.utc),
                              max_age_days=args.max_age_days)
            result = archive_snapshot(args.archive_root, plan)
            replay = verify_receipt(args.archive_root,
                                    plan.snapshot.source_code,
                                    plan.source_bytes_sha256,
                                    plan.snapshot.downloaded_at)
            if replay["original_html_sha256"] != result["original_html_sha256"]:
                raise ValueError("Archived EIA document and read-back hashes differ")
            result["immediate_independent_replay"] = True
        else:
            at = datetime.fromisoformat(args.retrieved_at)
            result = verify_receipt(args.archive_root, SOURCES[args.source][1],
                                    args.sha256, at)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        # No secret/path/raw quote/HTML exposure from caught I/O exceptions.
        print("EIA_PRIVATE_ARCHIVE_FAILED: "+type(exc).__name__,file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
