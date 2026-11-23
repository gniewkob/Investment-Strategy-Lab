"""Offline, non-executable OECD-shaped Poland share-index research benchmark.

The caller is responsible for permissions. This module neither downloads data
nor certifies origin, rights, historical availability or an executable price.
"""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import io
import json
from pathlib import Path

URL = ('https://sdmx.oecd.org/public/rest/v1/data/'
       'OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/POL.M.SHARE.IX.......'
       '?startPeriod=2022-01&endPeriod=2025-12&format=csvfilewithlabels')
IDENTITY = {'STRUCTURE': 'DATAFLOW', 'STRUCTURE_ID': 'OECD.SDD.STES:DSD_STES@DF_FINMARK(4.0)',
            'ACTION': 'I', 'REF_AREA': 'POL', 'FREQ': 'M', 'MEASURE': 'SHARE',
            'UNIT_MEASURE': 'IX', 'ACTIVITY': '_Z', 'ADJUSTMENT': '_Z',
            'TRANSFORMATION': '_Z', 'TIME_HORIZ': '_Z', 'METHODOLOGY': 'N',
            'OBS_STATUS': 'A', 'UNIT_MULT': '0', 'BASE_PER': '2015'}
MONTHS = [f'{year}-{month:02}' for year in range(2022, 2026) for month in range(1, 13)]

class BenchmarkError(ValueError):
    """The source or receipt is insufficient for this bounded experiment."""

def parse_csv(data: bytes, retrieved_at: str) -> dict:
    if type(data) is not bytes or not 1 <= len(data) <= 1_000_000:
        raise BenchmarkError('INVALID_SOURCE_SIZE')
    try:
        if not isinstance(retrieved_at, str) or not retrieved_at.endswith('Z'):
            raise ValueError
        stamp = datetime.strptime(retrieved_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        if stamp < datetime(2026, 1, 1, tzinfo=timezone.utc) or stamp > datetime.now(timezone.utc):
            raise ValueError
    except ValueError as exc:
        raise BenchmarkError('INVALID_RETRIEVAL_TIME') from exc
    try:
        content = data.decode('utf-8-sig')
        if any(not line.strip() for line in content.splitlines()):
            raise BenchmarkError('BLANK_CSV_LINE')
        reader = csv.DictReader(io.StringIO(content, newline=''), strict=True)
        fields = reader.fieldnames or []
        required = set(IDENTITY) | {'TIME_PERIOD', 'OBS_VALUE'}
        if len(fields) != len(set(fields)) or not required.issubset(fields):
            raise BenchmarkError('CSV_HEADER_INVALID')
        levels = {}
        for row in reader:
            if None in row or any(value is None for value in row.values()) or any(row.get(k) != v for k, v in IDENTITY.items()):
                raise BenchmarkError('SERIES_METADATA_INVALID')
            month = row['TIME_PERIOD']
            if month not in MONTHS or month in levels:
                raise BenchmarkError('MONTH_INVALID_OR_DUPLICATE')
            raw = row['OBS_VALUE']
            if not isinstance(raw, str) or len(raw) > 40 or raw.strip() != raw:
                raise BenchmarkError('INDEX_INVALID')
            level = Decimal(raw)
            if not level.is_finite() or level <= 0 or not -18 <= level.adjusted() <= 18 or len(level.as_tuple().digits) > 32:
                raise BenchmarkError('INDEX_INVALID')
            levels[month] = level
        if set(levels) != set(MONTHS):
            raise BenchmarkError('MONTHLY_COVERAGE_INVALID')
    except (UnicodeError, csv.Error, InvalidOperation, TypeError) as exc:
        raise BenchmarkError('CSV_INVALID') from exc
    return {'levels': levels, 'receipt': {'source_url': URL, 'retrieved_at_utc': retrieved_at,
        'sha256': sha256(data).hexdigest(), 'bytes': len(data),
        'source_authenticity_verified': False, 'rights_verified': False}}

def benchmark(parsed: dict) -> dict:
    """Allocate 100 hypothetical PLN to dimensionless index units each month."""
    levels = parsed['levels']
    with localcontext() as ctx:
        ctx.prec = 40
        units = sum((Decimal(100) / levels[month] for month in MONTHS), Decimal(0))
        ending = units * levels[MONTHS[-1]]
    return {'schema': 'ISL_OECD_POL_INDEX_BENCHMARK_V01',
        'status': 'NON_EXECUTABLE_RESEARCH_BENCHMARK', 'months': 48,
        'period': '2022-01 to 2025-12', 'monthly_contribution_pln': '100',
        'contributions_pln': '4800', 'cash_baseline_pln': '4800',
        'terminal_index_equivalent_pln': format(ending.normalize(), 'f'),
        'source_receipt': parsed['receipt'], 'historical_pit_certified': False,
        'executable_price_certified': False, 'total_return_certified': False,
        'model_admitted': False, 'model_decisions': 'HOLD_NO_CHANGE',
        'orders_sent': 0, 'database_writes': 0}

def render_report(result: dict) -> str:
    receipt = result['source_receipt']
    return (f"# Poland share-index research benchmark\n\n"
        f"**{result['status']}**; M1/M2/M3 HOLD_NO_CHANGE.\n\n"
        f"48 months, 2022-01–2025-12: hypothetical 100 PLN monthly, "
        f"cash baseline {result['cash_baseline_pln']} PLN, terminal index-equivalent "
        f"{result['terminal_index_equivalent_pln']} PLN.\n\n"
        "The Poland share-price index is dimensionless (2015=100), not an executable "
        "price, ETF NAV, global series, or verified total return. The calculation "
        "divides each contribution by the monthly index level and marks these "
        "hypothetical units at the final level; no fees, dividends, tax, FX or "
        "historical point-in-time availability are established.\n\n"
        f"Source: OECD, Financial market, {receipt['source_url']} "
        f"(accessed {receipt['retrieved_at_utc']}); SHA-256 `{receipt['sha256']}`. "
        "The receipt is caller-declared and proves neither origin nor permission. "
        "Use only data for which the intended processing rights have been verified.\n")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--retrieved-at-utc', required=True, help='actual retrieval timestamp, YYYY-MM-DDTHH:MM:SSZ')
    args = parser.parse_args()
    try:
        with args.input.open('rb') as file:
            data = file.read(1_000_001)
        print(render_report(benchmark(parse_csv(data, args.retrieved_at_utc))))
    except (OSError, BenchmarkError) as exc:
        parser.error(str(exc))

if __name__ == '__main__':
    main()
