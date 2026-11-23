"""Offline OECD Poland share-price index appendix for an ISL research report.

Not a trading fill, fund NAV or total-return series. This module never fetches,
redistributes original observations, certifies rights or admits an investment model.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from scripts.oecd_pol_benchmark import BenchmarkError, benchmark, parse_csv, render_report

SCHEMA = 'ISL_OECD_POL_REPORT_APPENDIX_V02'
_HASH = re.compile(r'[0-9a-f]{64}\Z')

class OECDReportBlocked(ValueError):
    """Preflight or validation refused an incomplete research appendix."""


def _read_bounded(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise OECDReportBlocked('REGULAR_BOUNDED_SOURCE_REQUIRED')
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    if not 0 < len(data) <= maximum:
        raise OECDReportBlocked('REGULAR_BOUNDED_SOURCE_REQUIRED')
    return data


def assemble(*, raw: bytes, retrieved_at_utc: str, expected_sha256: str,
             base_report: str | None = None) -> tuple[dict, str]:
    """Create a descriptive appendix, never a model input or performance claim."""
    if type(expected_sha256) is not str or not _HASH.fullmatch(expected_sha256):
        raise OECDReportBlocked('EXPECTED_RAW_SHA256_REQUIRED')
    if sha256(raw).hexdigest() != expected_sha256:
        raise OECDReportBlocked('ORIGINAL_RAW_SHA256_MISMATCH')
    parsed = parse_csv(raw, retrieved_at_utc)
    result = benchmark(parsed)
    if (result.get('status') != 'NON_EXECUTABLE_RESEARCH_BENCHMARK'
            or result.get('months') != 48
            or result.get('historical_pit_certified') is not False
            or result.get('total_return_certified') is not False
            or result.get('executable_price_certified') is not False
            or result.get('model_admitted') is not False
            or result.get('orders_sent') != 0
            or result.get('database_writes') != 0):
        raise OECDReportBlocked('RESEARCH_ONLY_INVARIANTS_REQUIRED')
    package = {
        'schema': SCHEMA,
        'status': 'NON_EXECUTABLE_RESEARCH_BENCHMARK',
        'source_series': 'OECD.SDD.STES:DSD_STES@DF_FINMARK(4.0)/POL.M.SHARE.IX',
        'source_semantics': 'POLAND_MONTHLY_SHARE_PRICE_INDEX_2015_100',
        'observation_count': 48,
        'benchmark': result,
        'raw_source_sha256': expected_sha256,
        'rights_specific_to_series_verified': False,
        'upstream_owner_verified': False,
        'actual_aggregation_method_verified': False,
        'historical_point_in_time_certified': False,
        'qualified_asset_series': [],
        'm1_m2_m3': 'INSUFFICIENT_DATA_HOLD_CASH',
        'report_appendix_only': True,
        'real_financial_operations': 0,
        'database_writes': 0,
        'orders_sent': 0,
    }
    appendix = render_report(result)
    notice = ('\n**Laboratory integration:** research-only appendix, not a live pricing '
              'feed, an executable instrument or an M1–M3 model input. '
              'Exact upstream data ownership and permissible reuse remain UNKNOWN; '
              'no original monthly observations are included in this output.\n')
    if base_report is not None:
        if type(base_report) is not str or not base_report.strip():
            raise OECDReportBlocked('EXISTING_REPORT_REQUIRED')
        md = base_report.rstrip() + '\n\n---\n\n' + appendix + notice
    else:
        md = appendix + notice
    return package, md


def write_report(*, original_file: Path, expected_sha256: str,
                 retrieved_at_utc: str, out_dir: Path,
                 base_report_file: Path | None = None) -> dict:
    if out_dir.exists() or out_dir.is_symlink():
        raise OECDReportBlocked('OUTPUT_DIRECTORY_MUST_NOT_EXIST')
    if original_file.resolve(strict=False) == out_dir.resolve(strict=False):
        raise OECDReportBlocked('SOURCE_AND_OUTPUT_MUST_DIFFER')
    raw = _read_bounded(original_file, 1_000_000)
    base = None
    if base_report_file is not None:
        try:
            base = _read_bounded(base_report_file, 250_000).decode('utf-8')
        except UnicodeError as exc:
            raise OECDReportBlocked('BASE_REPORT_UTF8_REQUIRED') from exc
    result, markdown = assemble(raw=raw, retrieved_at_utc=retrieved_at_utc,
                                expected_sha256=expected_sha256, base_report=base)
    out_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (out_dir / 'oecd_research_appendix.json').open('x', encoding='utf-8') as out:
        json.dump(result, out, sort_keys=True, indent=2, ensure_ascii=False)
        out.write('\n')
    with (out_dir / 'research_report.md').open('x', encoding='utf-8') as out:
        out.write(markdown)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Existing local OECD CSV; no download')
    parser.add_argument('--raw-sha256', required=True, help='SHA-256 from original independent source receipt')
    parser.add_argument('--retrieved-at-utc', required=True, help='Actual source retrieval timestamp')
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--base-report', type=Path, help='Existing laboratory Markdown; read-only')
    args = parser.parse_args(argv)
    try:
        report = write_report(original_file=args.input, expected_sha256=args.raw_sha256,
                              retrieved_at_utc=args.retrieved_at_utc, out_dir=args.out_dir,
                              base_report_file=args.base_report)
    except (BenchmarkError, OECDReportBlocked, OSError, ValueError) as exc:
        parser.error(str(exc))
    print('OECD_REPORT_APPENDIX=' + json.dumps({'status': report['status'],
        'months': report['observation_count'], 'm1_m2_m3': report['m1_m2_m3'],
        'orders_sent': 0, 'database_writes': 0}, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
