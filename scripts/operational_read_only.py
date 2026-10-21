"""Private one-shot Coinbase capture + finalized EVM observation. No execution APIs.

The agent's existing authorized Coinbase connector supplies the capture; this
CLI does not acquire credentials or impersonate an authenticated connection.
Only public, allowlisted RPC reads are sent over the network. Outputs stay local.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import time
from urllib.error import HTTPError, URLError
from email.utils import parsedate_to_datetime
from urllib.request import Request, build_opener, HTTPRedirectHandler

from scripts.read_only_portfolio_monitor import analyze_portfolio, _when, _number
from scripts.private_wallet_chain_monitor import _private_config, WalletSourceError

RPC_URLS = {1: 'https://ethereum-rpc.publicnode.com', 8453: 'https://mainnet.base.org'}
READ_METHODS = frozenset({'eth_chainId', 'eth_getBlockByNumber', 'eth_getBalance', 'eth_call', 'eth_getLogs'})
# Identity from https://www.coinbase.com/cbbtc (Ethereum AND Base deployments).
# The same contract on another chain is NOT implicitly trusted.
TOKENS = {c: {'0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf': ('cbBTC', 8)} for c in (1, 8453)}
TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
MAX_BYTES = 2_000_000
HEX32 = re.compile(r'0x[0-9a-fA-F]{64}\Z')
ADDR = re.compile(r'0x[0-9a-fA-F]{40}\Z')


class ReadOnlyError(ValueError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReadOnlyError('RPC_REDIRECT_REJECTED')


def rpc_read(chain, method, params, *, opener=None, sleep=time.sleep):
    """Bounded retry for read RPC only; block redirects BEFORE following them."""
    if chain not in RPC_URLS or method not in READ_METHODS:
        raise ReadOnlyError('RPC_METHOD_OR_CHAIN_FORBIDDEN')
    if method == 'eth_call':
        if (len(params) != 2 or set(params[0]) != {'to', 'data'}
                or params[0]['to'] not in TOKENS[chain]
                or not re.fullmatch(r'0x70a08231[0-9a-f]{64}', params[0]['data'])):
            raise ReadOnlyError('ONLY_REGISTERED_TOKEN_BALANCE_CALL_ALLOWED')
    url = RPC_URLS[chain]
    op = opener or build_opener(_NoRedirect()).open
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode()
    for attempt in range(3):
        delay = min(2**attempt, 8)
        try:
            req = Request(url, data=body, headers={'Content-Type': 'application/json',
                          'User-Agent': 'ISL-readonly/1.0'})
            with op(req, timeout=15) as response:
                if response.status != 200 or response.geturl() != url:
                    raise ReadOnlyError('RPC_UNEXPECTED_RESPONSE')
                raw = response.read(MAX_BYTES+1)
            if len(raw) > MAX_BYTES:
                raise ReadOnlyError('RPC_RESPONSE_TOO_LARGE')
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get('id') != 1:
                raise ReadOnlyError('RPC_INVALID_ENVELOPE')
            if 'error' in data:
                # Retry rate/capacity errors, never print upstream message.
                if isinstance(data['error'], dict) and data['error'].get('code') in (-32005, -32016, -32002) and attempt < 2:
                    sleep(delay); continue
                raise ReadOnlyError('RPC_UPSTREAM_ERROR')
            if data.get('jsonrpc') != '2.0' or 'result' not in data or data['result'] is None:
                raise ReadOnlyError('RPC_RESULT_MISSING')
            result = data['result']
            expected_type = dict if method == 'eth_getBlockByNumber' else list if method == 'eth_getLogs' else str
            if not isinstance(result, expected_type):
                raise ReadOnlyError('RPC_RESULT_SHAPE_INVALID')
            return result
        except HTTPError as exc:
            retry = exc.code in (429, 500, 502, 503, 504)
            retry_after = exc.headers.get('Retry-After', '') if exc.headers else ''
            if retry_after:
                try:
                    delay = int(retry_after) if retry_after.isdigit() else max(0, int(
                        (parsedate_to_datetime(retry_after)-datetime.now(timezone.utc)).total_seconds())+1)
                except (ValueError, TypeError, OverflowError):
                    raise ReadOnlyError('RPC_INVALID_RETRY_AFTER') from None
                if delay > 30:
                    exc.close()
                    raise ReadOnlyError('RPC_RETRY_AFTER_EXCEEDS_BUDGET') from None
            exc.close()
            if not retry or attempt == 2:
                raise ReadOnlyError('RPC_HTTP_FAILURE') from None
        except (URLError, TimeoutError, OSError):
            if attempt == 2: raise ReadOnlyError('RPC_NETWORK_FAILURE') from None
        except (ValueError, TypeError, KeyError):
            raise ReadOnlyError('RPC_INVALID_RESPONSE') from None
        sleep(delay)
    raise ReadOnlyError('RPC_RETRY_EXHAUSTED')


def _hex(value, size=None):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]+', value):
        raise ReadOnlyError('INVALID_RPC_HEX')
    if len(value) > 66 or size and len(value) != size*2+2:
        raise ReadOnlyError('INVALID_RPC_HEX_LENGTH')
    return int(value, 16)


def _analyze(payload, now):
    try:
        return analyze_portfolio(payload, now)
    except ValueError:
        raise ReadOnlyError('EXCHANGE_POSITIONS_DO_NOT_RECONCILE') from None


def normalize_exchange(capture, now):
    """Validate multi-portfolio coverage; never add balances to position totals.

    Capture provenance is operator asserted, NOT cryptographically authenticated
    by this CLI. No retrieval time from the connector means source_as_of UNKNOWN.
    """
    if capture.get('mode') != 'COINBASE_CONNECTOR_READ_ONLY_CAPTURE':
        raise ReadOnlyError('EXCHANGE_CAPTURE_MODE_REQUIRED')
    at = _when(capture.get('captured_at'))
    if not timedelta(seconds=-5) <= now-at <= timedelta(minutes=15):
        raise ReadOnlyError('EXCHANGE_CAPTURE_STALE_OR_FUTURE')
    portfolios, reads = capture.get('portfolios'), capture.get('reads')
    if not isinstance(portfolios, list) or not isinstance(reads, list) or len(reads) > 100:
        raise ReadOnlyError('EXCHANGE_PORTFOLIO_LIST_REQUIRED')
    ids = [p.get('uuid') for p in portfolios if p.get('deleted') is not True]
    if (not ids or any(not isinstance(p, str) or not p for p in ids)
            or len(set(ids)) != len(ids) or len(reads) != len(ids)
            or {r.get('portfolio_id') for r in reads} != set(ids)):
        raise ReadOnlyError('EXCHANGE_PORTFOLIO_COVERAGE_INVALID')
    totals, positions, seen_positions, seen_accounts = Decimal(0), [], set(), set()
    trading = {}
    for r in reads:
        p = r['breakdown']
        if p.get('portfolio', {}).get('uuid') != r['portfolio_id']:
            raise ReadOnlyError('EXCHANGE_PORTFOLIO_ID_MISMATCH')
        if p.get('futures_positions') or p.get('equity_positions'):
            raise ReadOnlyError('NONSPOT_PORTFOLIO_NOT_SUPPORTED')
        total = p.get('portfolio_balances', {}).get('total_balance', {})
        if total.get('currency') != 'USD': raise ReadOnlyError('EXCHANGE_USD_REQUIRED')
        totals += _number(total.get('value'), 'total')
        # Reconcile each portfolio independently, not just the global total.
        _analyze({'source': 'USER_SUPPLIED_READ_ONLY_COINBASE_CAPTURE',
                           'captured_at': at.isoformat(),
                           'portfolio_balances': p['portfolio_balances'],
                           'spot_positions': p.get('spot_positions')}, now)
        for pos in p['spot_positions']:
            ident = pos.get('account_uuid')
            # Missing account ID is permitted ONLY for an empty fiat placeholder.
            if not ident and pos.get('total_balance_fiat') is None and pos.get('account_type') == 'ACCOUNT_TYPE_FIAT':
                continue
            if not isinstance(ident, str) or not ident or ident in seen_positions:
                raise ReadOnlyError('DUPLICATE_OR_MISSING_POSITION_ID')
            seen_positions.add(ident); positions.append(pos)
        pages = r.get('balance_pages')
        if not isinstance(pages, list) or not 1 <= len(pages) <= 100:
            raise ReadOnlyError('EXCHANGE_BALANCE_PAGES_REQUIRED')
        cursors = set()
        for i, page in enumerate(pages):
            if ('has_next' not in page and (page.get('size') != len(page.get('accounts', []))
                    or not 0 <= page['size'] < 250 or page.get('cursor'))):
                raise ReadOnlyError('EXCHANGE_PAGINATION_TERMINAL_EVIDENCE_MISSING')
            if 'has_next' in page and not isinstance(page['has_next'], bool):
                raise ReadOnlyError('EXCHANGE_PAGINATION_FLAG_INVALID')
            if (page.get('portfolio_id') != r['portfolio_id']
                    or bool(page.get('has_next', False)) != (i < len(pages)-1)):
                raise ReadOnlyError('EXCHANGE_PAGINATION_INCOMPLETE')
            if i < len(pages)-1:
                cursor = page.get('cursor')
                if not isinstance(cursor, str) or not cursor or cursor in cursors:
                    raise ReadOnlyError('EXCHANGE_CURSOR_REPEATED_OR_MISSING')
                cursors.add(cursor)
            accounts = page.get('accounts')
            if not isinstance(accounts, list) or len(accounts) > 250:
                raise ReadOnlyError('EXCHANGE_ACCOUNTS_INVALID')
            for a in accounts:
                ident, currency = a.get('uuid'), a.get('currency')
                if not ident or ident in seen_accounts or not isinstance(currency, str) or not re.fullmatch(r'[A-Z0-9]{2,12}', currency):
                    raise ReadOnlyError('DUPLICATE_OR_INVALID_TRADING_ACCOUNT')
                seen_accounts.add(ident)
                node = trading.setdefault(currency, {'available': Decimal(0), 'hold': Decimal(0)})
                for key, field in (('available', 'available_balance'), ('hold', 'hold')):
                    v = a.get(field, {})
                    if v.get('currency') != currency: raise ReadOnlyError('EXCHANGE_BALANCE_CURRENCY_MISMATCH')
                    node[key] += _number(v.get('value'), 'balance')
    normalized = _analyze({'source': 'USER_SUPPLIED_READ_ONLY_COINBASE_CAPTURE',
        'captured_at': at.isoformat(), 'portfolio_balances': {'total_balance': {'currency': 'USD', 'value': str(totals)}},
        'spot_positions': positions}, now)
    normalized.update({'portfolio_count': len(ids), 'cli_authenticated_coinbase_directly': False,
        'provenance': 'OPERATOR_ASSERTED_CAPTURE_OF_AUTHORIZED_CONNECTOR_READS',
        'source_as_of_utc': None, 'source_as_of_status': 'NOT_PROVIDED_BY_CONNECTOR',
        'trading_balances': {k: {f: str(v) for f, v in n.items()} for k, n in trading.items()},
        'trading_balances_added_to_holdings': False})
    return normalized


def _history(chain, addr, contracts, end, count, rpc):
    if not 1 <= count <= 1000: raise ReadOnlyError('HISTORY_RANGE_OUTSIDE_1_1000_BLOCKS')
    start = max(0, end-count+1)
    events = {}
    topic_addr = '0x' + '0'*24 + addr[2:]
    for contract in sorted(contracts):
        symbol, decimals = TOKENS[chain][contract]
        for topics in ([TRANSFER_TOPIC, topic_addr], [TRANSFER_TOPIC, None, topic_addr]):
            raw = rpc(chain, 'eth_getLogs', [{'address': contract, 'fromBlock': hex(start),
                       'toBlock': hex(end), 'topics': topics}])
            if not isinstance(raw, list) or len(raw) > 5000: raise ReadOnlyError('HISTORY_TOO_LARGE')
            for log in raw:
                t = log.get('topics', [])
                block = _hex(log.get('blockNumber'))
                if (log.get('removed') is not False or log.get('address', '').lower() != contract
                    or len(t) != 3 or t[0].lower() != TRANSFER_TOPIC
                    or any(not HEX32.fullmatch(v) for v in t)
                    or not start <= block <= end or topic_addr not in (t[1].lower(), t[2].lower())
                    or not HEX32.fullmatch(log.get('transactionHash', ''))
                    or not HEX32.fullmatch(log.get('blockHash', ''))):
                    raise ReadOnlyError('UNCONFIRMED_OR_INVALID_LOG')
                tx = log['transactionHash'].lower()
                index = _hex(log.get('logIndex'))
                direction = 'self' if t[1].lower() == t[2].lower() else ('out' if t[1].lower() == topic_addr else 'in')
                key = (chain, tx, index)
                event = {'event_id': sha256(f'{chain}:{tx}:{index}'.encode()).hexdigest(),
                    'chain_id': chain, 'tx_hash': tx, 'contract': contract, 'asset': symbol,
                    'quantity': _units(_hex(log.get('data')), decimals), 'direction': direction,
                    'confirmed': True, 'location': 'wallet', 'block_number': block,
                    'block_hash': log['blockHash'].lower(), 'source_event_timestamp_utc': None}
                if key in events and events[key] != event: raise ReadOnlyError('CONFLICTING_LOG')
                events[key] = event
    return {'from_block': start, 'to_block': end, 'event_count': len(events),
            'events': list(events.values()), 'scope': 'REGISTERED_ERC20_TRANSFER_LOGS_ONLY',
            'native_internal_nft_defi_history_included': False, 'full_history': False}


def _units(value, decimals):
    with localcontext() as ctx:
        ctx.prec = 100
        return format(Decimal(value) / Decimal(10)**decimals, 'f')


def observe_wallets(config, now, *, rpc=rpc_read, history_blocks=0):
    try: entries = _private_config(config)
    except WalletSourceError: raise ReadOnlyError('WALLET_CONFIG_INVALID') from None
    output = []
    for chain, addr, label, approved in entries:
        if not approved.issubset(TOKENS[chain]): raise ReadOnlyError('TOKEN_NOT_IN_VERIFIED_REGISTRY')
        if _hex(rpc(chain, 'eth_chainId', [])) != chain: raise ReadOnlyError('RPC_CHAIN_MISMATCH')
        b = rpc(chain, 'eth_getBlockByNumber', ['finalized', False])
        number, timestamp = _hex(b.get('number')), _hex(b.get('timestamp'))
        if not HEX32.fullmatch(b.get('hash', '')): raise ReadOnlyError('INVALID_BLOCK_HASH')
        at = datetime.fromtimestamp(timestamp, timezone.utc)
        if not timedelta(seconds=-5) <= now-at <= timedelta(minutes=30):
            raise ReadOnlyError('FINALIZED_BLOCK_STALE_OR_FUTURE')
        tag = hex(number)
        native = _hex(rpc(chain, 'eth_getBalance', [addr, tag]))
        positions = [{'asset': 'ETH', 'contract': 'NATIVE', 'quantity': _units(native, 18)}]
        for contract in sorted(approved):
            symbol, digits = TOKENS[chain][contract]
            raw = rpc(chain, 'eth_call', [{'to': contract, 'data': '0x70a08231'+'0'*24+addr[2:]}, tag])
            positions.append({'asset': symbol, 'contract': contract, 'quantity': _units(_hex(raw), digits)})
        history = _history(chain, addr, approved, number, history_blocks, rpc) if history_blocks else None
        if history is not None:
            for event in history['events']:
                # One blockchain log can be observed by multiple watched wallets.
                # Scope each leg to its local label without exposing the address.
                event['wallet_label'] = label
                event['event_id'] = sha256((label+':'+event['event_id']).encode()).hexdigest()
        check = rpc(chain, 'eth_getBlockByNumber', [tag, False])
        if check.get('hash') != b['hash']: raise ReadOnlyError('SOURCE_BLOCK_CHANGED')
        output.append({'wallet_label': label, 'chain_id': chain, 'source': RPC_URLS[chain],
            'source_block_number': number, 'source_block_hash': b['hash'],
            'source_block_timestamp_utc': at.isoformat(), 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
            'finality': 'PROVIDER_FINALIZED_NOT_INDEPENDENT_CONSENSUS_PROOF',
            'positions': positions, 'history': history, 'usd_valuation': None})
    return {'status': 'FINALIZED_CONFIGURED_BALANCES', 'wallets': output,
            'all_assets_enumerated': False, 'prices_verified': False,
            'scope': 'NATIVE_ETH_AND_EXPLICIT_REGISTRY_TOKENS_ONLY', 'financial_operations': 0}


def reconcile_events(exchange, wallet):
    """Conservative one-to-one match. No symbol mapping, fee guessing or P&L."""
    groups = {}
    seen = set()
    for location, items in (('exchange', exchange), ('wallet', wallet)):
        if not isinstance(items, list) or len(items) > 5000: raise ReadOnlyError('EVENT_LIST_INVALID')
        for e in items:
            if (e.get('location') != location or e.get('chain_id') not in RPC_URLS
                    or not HEX32.fullmatch(e.get('tx_hash', ''))
                    or e.get('contract') not in ('NATIVE', *TOKENS[e['chain_id']])
                    or e.get('direction') not in ('in', 'out', 'self')
                    or not isinstance(e.get('confirmed'), bool)
                    or not isinstance(e.get('event_id'), str) or not e['event_id']):
                raise ReadOnlyError('EVENT_IDENTITY_INVALID')
            ident = (location, e['event_id'])
            if ident in seen: raise ReadOnlyError('DUPLICATE_EVENT')
            seen.add(ident)
            key = (e['chain_id'], e['tx_hash'].lower(), e['contract'], _number(e['quantity'], 'quantity'))
            groups.setdefault(key, []).append(e)
    matched = 0
    for key, legs in groups.items():
        if (key[3] > 0 and len(legs) == 2 and {e['location'] for e in legs} == {'exchange', 'wallet'}
                and {e['direction'] for e in legs} == {'in', 'out'}
                and all(e['confirmed'] for e in legs)):
            matched += 1
    return {'status': 'OBSERVED_LEGS_ONLY_NOT_COMPLETE_FUNDING_HISTORY',
            'matched_internal_movements': matched, 'unmatched_events': len(seen)-2*matched,
            'balance_adjustment': '0', 'unmatched_is_external_funding': False,
            'exchange_history_authenticated_by_cli': False}


def read_private(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as f:
            s = os.fstat(f.fileno())
            if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077 or s.st_size > MAX_BYTES:
                raise ReadOnlyError('PRIVATE_INPUT_PERMISSIONS_OR_SIZE_INVALID')
            raw = f.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES: raise ReadOnlyError('PRIVATE_INPUT_TOO_LARGE')
        data = json.loads(raw)
        if not isinstance(data, dict): raise ReadOnlyError('PRIVATE_INPUT_OBJECT_REQUIRED')
        return data
    except (OSError, ValueError):
        raise ReadOnlyError('PRIVATE_INPUT_REJECTED') from None


def write_private(path, data):
    """Exclusive creation: never overwrite or follow symlinks. Parent must be private."""
    path = Path(path)
    parent = path.parent.stat()
    if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
        raise ReadOnlyError('OUTPUT_PARENT_MUST_BE_PRIVATE_0700')
    raw = json.dumps(data, sort_keys=True, allow_nan=False).encode()
    if len(raw) > MAX_BYTES: raise ReadOnlyError('PRIVATE_OUTPUT_TOO_LARGE')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
    except OSError:
        raise ReadOnlyError('PRIVATE_OUTPUT_NOT_CREATED') from None


def main(argv=None):
    p = argparse.ArgumentParser(description='One-shot PRIVATE read-only portfolio observer; no execution')
    p.add_argument('--exchange-capture', type=Path)
    p.add_argument('--wallet-watchlist', type=Path)
    p.add_argument('--exchange-events', type=Path, help='Private observed history export; never transaction instructions')
    p.add_argument('--history-blocks', type=int, default=0, help='0 disables; max 1000 finalized blocks, registered ERC20 only')
    p.add_argument('--public-markets', action='store_true', help='Include existing Coinbase closed OHLCV + dated NBP FX sources')
    p.add_argument('--at', help='UTC clock for offline capture validation only; not permitted for live wallet reads')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    if not args.exchange_capture and not args.wallet_watchlist: p.error('At least one source required')
    if args.at and (args.wallet_watchlist or args.public_markets): p.error('--at is offline-only')
    try:
        now = _when(args.at) if args.at else datetime.now(timezone.utc)
        exchange = normalize_exchange(read_private(args.exchange_capture), now) if args.exchange_capture else None
        wallet = observe_wallets(read_private(args.wallet_watchlist), now, history_blocks=args.history_blocks) if args.wallet_watchlist else None
        legs = [e for w in wallet['wallets'] for e in (w['history'] or {}).get('events', [])] if wallet else []
        history = read_private(args.exchange_events) if args.exchange_events else None
        if history is not None and history.get('mode') != 'PRIVATE_OBSERVED_EXCHANGE_EVENTS':
            raise ReadOnlyError('EXCHANGE_EVENT_EXPORT_MODE_REQUIRED')
        audit = reconcile_events(history.get('events'), legs) if history else {
            'status': 'EXCHANGE_HISTORY_UNAVAILABLE', 'balance_adjustment': '0',
            'matched_internal_movements': None, 'unmatched_is_external_funding': False}
        market_sources = None
        if args.public_markets:
            from scripts.read_only_portfolio_monitor import fetch_markets, fetch_usdpln
            market_sources = {'coinbase_closed_72h': fetch_markets(now), 'nbp_usdpln': fetch_usdpln(now),
                              'retrieved_at_utc': datetime.now(timezone.utc).isoformat()}
        report = {'status': 'PRIVATE_READ_ONLY_OBSERVATION', 'generated_at_utc': now.isoformat(),
            'clock_mode': 'OFFLINE_REPLAY' if args.at else 'LIVE_RETRIEVAL',
            'exchange': exchange, 'onchain': wallet, 'public_market_sources': market_sources, 'transfer_reconciliation': audit,
            'consolidation': {'exchange_usd': exchange['reported_total_usd'] if exchange else None,
                 'wallet_usd': None, 'combined_total_usd': None,
                 'reason': 'ONCHAIN_PRICES_UNVERIFIED_KEEP_CUSTODY_AND_CHAIN_LEDGERS_SEPARATE',
                 'event_amounts_added_to_balances': False},
            'financial_operations': 0, 'neon_writes': 0}
        write_private(args.output, report)
        print('READ_ONLY_REPORT_WRITTEN_PRIVATE; financial_operations=0; complete_net_worth=false')
        return 0
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError, AttributeError, RecursionError):
        # No traceback, request payload, path, balances, IDs or API messages in stdout/stderr.
        print('READ_ONLY_OBSERVATION_FAILED; no complete report produced')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
