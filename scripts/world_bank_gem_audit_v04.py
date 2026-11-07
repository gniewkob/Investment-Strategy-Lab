#!/usr/bin/env python3
"""Read-only World Bank GEM availability audit, not a market-data adapter."""
import argparse
import datetime as dt
import hashlib
import json
import math
import urllib.request

BASE = 'https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?source=15&format=json&per_page=1000&date=2021M11:2026M10'
MONTHS = [f'{y}M{m:02d}' for y in range(2021, 2027) for m in range(1, 13) if '2021M11' <= f'{y}M{m:02d}' <= '2026M10']


def analyze(raw, country, indicator):
    data = json.loads(raw)
    if not isinstance(data, list) or len(data) != 2 or not isinstance(data[0], dict):
        raise ValueError('Invalid API envelope')
    meta, rows = data
    if meta.get('total') == 0 and rows is None:
        rows = []
    if not isinstance(rows, list) or meta.get('total') != len(rows) or meta.get('pages', 0) not in (0, 1):
        raise ValueError('Incomplete or invalid API pagination')
    seen = set()
    for row in rows:
        month = row.get('date')
        value = row.get('value')
        if row.get('country', {}).get('id') != country or row.get('indicator', {}).get('id') != indicator:
            raise ValueError('Unexpected series identity')
        if month not in MONTHS or month in seen:
            raise ValueError('Unexpected or duplicate month')
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
            raise ValueError('Missing or invalid value')
        seen.add(month)
    return {'country': country, 'indicator': indicator, 'count': len(seen),
            'missing_months': [m for m in MONTHS if m not in seen],
            'source_sha256': hashlib.sha256(raw).hexdigest(), 'last_updated': meta.get('lastupdated')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    results = []
    for country, indicator in [('WLD', 'DSTKMKTXD'), ('WLD', 'DSTKMKTXN'), ('USA', 'DSTKMKTXD')]:
        url = BASE.format(country=country, indicator=indicator)
        req = urllib.request.Request(url, headers={'User-Agent': 'ISL research availability audit/1.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.geturl() != url or response.status != 200:
                raise ValueError('Unexpected HTTP response or redirect')
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Response too large')
        result = analyze(raw, country, indicator)
        result['url'] = url
        result['retrieved_at_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        results.append(result)
    report = {'status': 'BLOCKED_GLOBAL_SERIES_AND_RIGHTS_NOT_VERIFIED',
              'purpose': 'availability audit only; no proxy, no backtest, no database writes',
              'period': ['2021M11', '2026M10'], 'results': results}
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
