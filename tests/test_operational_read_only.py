"""Synthetic inputs only; exercise consolidation, RPC boundaries and real CLI."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError

from scripts import operational_read_only as m

NOW = datetime(2026, 10, 21, 9, tzinfo=timezone.utc)
ADDR = '0x' + '1' * 40
HASH = '0x' + 'a' * 64
TOKEN = '0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf'


def capture():
    return {'mode': 'COINBASE_CONNECTOR_READ_ONLY_CAPTURE',
            'captured_at': NOW.isoformat(),
            'portfolios': [{'uuid': 'p1', 'deleted': False}],
            'reads': [{'portfolio_id': 'p1',
                       'breakdown': {'portfolio': {'uuid': 'p1'},
                         'portfolio_balances': {'total_balance': {'currency': 'USD', 'value': '100'}},
                         'spot_positions': [
                          {'account_uuid': 's1', 'asset': 'ETH', 'account_type': 'ACCOUNT_TYPE_STAKED_FUNDS',
                           'total_balance_fiat': '80', 'total_balance_crypto': '.04'},
                          {'account_uuid': 'a1', 'asset': 'ETH', 'total_balance_fiat': '20', 'total_balance_crypto': '.01'}]},
                       'balance_pages': [{'portfolio_id': 'p1', 'has_next': False,
                            'accounts': [{'uuid': 'a1', 'currency': 'ETH',
                             'available_balance': {'currency': 'ETH', 'value': '.007'},
                             'hold': {'currency': 'ETH', 'value': '.003'}}]}]}]}


def watch():
    return {'mode': 'PRIVATE_WALLET_READ_ONLY', 'watch': [
        {'label': 'primary', 'chain_id': 8453, 'address': ADDR,
         'verified_token_contracts': [TOKEN]}]}


def fake_rpc(chain, method, params):
    if method == 'eth_chainId': return hex(chain)
    if method == 'eth_getBlockByNumber':
        return {'number': '0x64', 'hash': HASH, 'timestamp': hex(int(NOW.timestamp())-30)}
    if method == 'eth_getBalance': return hex(10**17)
    if method == 'eth_call': return hex(123456789)
    if method == 'eth_getLogs':
        if len(params[0]['topics']) == 3: return []
        return [{'address': TOKEN, 'topics': [m.TRANSFER_TOPIC, '0x'+'0'*24+ADDR[2:], '0x'+'2'*64],
                 'transactionHash': HASH, 'blockHash': HASH, 'blockNumber': '0x64',
                 'logIndex': '0x0', 'data': hex(100), 'removed': False}]
    raise AssertionError(method)


class OperationalTests(unittest.TestCase):
    def test_holdings_and_trading_balance_are_not_added(self):
        r = m.normalize_exchange(capture(), NOW)
        self.assertEqual(r['reported_total_usd'], '100.0000')
        self.assertEqual(r['staked_value_usd'], '80.0000')
        self.assertEqual(r['trading_balances']['ETH'], {'available': '0.007', 'hold': '0.003'})
        self.assertNotIn('p1', json.dumps(r))
        self.assertFalse(r['cli_authenticated_coinbase_directly'])

    def test_missing_repeated_or_incomplete_portfolios_fail_closed(self):
        cases = []
        a = capture(); a['reads'] = []; cases.append(a)
        a = capture(); a['reads'] *= 2; cases.append(a)
        a = capture(); a['reads'][0]['balance_pages'][0]['has_next'] = True; cases.append(a)
        a = capture(); a['reads'][0]['balance_pages'][0]['portfolio_id'] = 'other'; cases.append(a)
        a = capture(); a['reads'][0]['breakdown']['spot_positions'] *= 2; cases.append(a)
        a = capture(); a['reads'][0]['balance_pages'] *= 2; cases.append(a)
        for a in cases:
            with self.subTest(a=cases.index(a)), self.assertRaises(m.ReadOnlyError):
                m.normalize_exchange(a, NOW)

    def test_stale_capture_and_nonspot_valuation_are_rejected(self):
        a = capture(); a['captured_at'] = (NOW-timedelta(hours=1)).isoformat()
        with self.assertRaises(m.ReadOnlyError): m.normalize_exchange(a, NOW)
        a = capture(); a['reads'][0]['breakdown']['futures_positions'] = [{'amount': '1'}]
        with self.assertRaises(m.ReadOnlyError): m.normalize_exchange(a, NOW)

    def test_finalized_balance_uses_pinned_block_and_keeps_contract_identity(self):
        calls = []
        def rpc(c, method, params):
            calls.append((method, params)); return fake_rpc(c, method, params)
        r = m.observe_wallets(watch(), NOW, rpc=rpc, history_blocks=10)
        row = r['wallets'][0]
        self.assertEqual(row['positions'][0]['quantity'], '0.1')
        self.assertEqual(row['positions'][1]['quantity'], '1.23456789')
        self.assertEqual(row['source_block_number'], 100)
        self.assertEqual(row['history']['event_count'], 1)
        self.assertEqual(row['history']['from_block'], 91)
        self.assertNotIn(ADDR, json.dumps(r))
        for method, params in calls:
            if method in ('eth_call', 'eth_getBalance'): self.assertEqual(params[-1], '0x64')
        self.assertFalse(r['all_assets_enumerated'])

    def test_wrong_chain_stale_block_reorg_unknown_token_fail(self):
        def wrong(c, method, params):
            return '0x1' if method == 'eth_chainId' else fake_rpc(c, method, params)
        with self.assertRaises(m.ReadOnlyError): m.observe_wallets(watch(), NOW, rpc=wrong)
        def stale(c, method, params):
            out = fake_rpc(c, method, params)
            if method == 'eth_getBlockByNumber': out['timestamp'] = '0x1'
            return out
        with self.assertRaises(m.ReadOnlyError): m.observe_wallets(watch(), NOW, rpc=stale)
        a = watch(); a['watch'][0]['verified_token_contracts'] = ['0x'+'f'*40]
        with self.assertRaises(m.ReadOnlyError): m.observe_wallets(a, NOW, rpc=fake_rpc)
        a = watch(); a['watch'].append(deepcopy(a['watch'][0]))
        with self.assertRaises(m.ReadOnlyError): m.observe_wallets(a, NOW, rpc=fake_rpc)
        def reorg(c, method, params):
            out = fake_rpc(c, method, params)
            if method == 'eth_getBlockByNumber' and params[0] != 'finalized': out['hash'] = '0x'+'b'*64
            return out
        with self.assertRaises(m.ReadOnlyError): m.observe_wallets(watch(), NOW, rpc=reorg)

    def test_rpc_denies_writes_before_network_and_redacts_errors(self):
        for method in ('eth_sendRawTransaction', 'personal_sign', 'eth_sign', 'wallet_sendCalls'):
            with self.assertRaises(m.ReadOnlyError): m.rpc_read(8453, method, [])
        def deny(req, timeout): raise HTTPError(ADDR, 403, ADDR, {}, None)
        with self.assertRaises(m.ReadOnlyError) as e:
            m.rpc_read(8453, 'eth_chainId', [], opener=deny)
        self.assertNotIn(ADDR, str(e.exception))
        self.assertIsNone(e.exception.__cause__)

    def test_transaction_lookup_hash_validation_and_pending_null_receipt(self):
        def forbidden(*a, **k): self.fail('Malformed lookup reached network')
        for method in ('eth_getTransactionReceipt','eth_getTransactionByHash'):
            for params in ([], ['bad-hash'], [HASH, HASH], {'hash': HASH}):
                with self.assertRaises(m.ReadOnlyError):m.rpc_read(8453,method,params,opener=forbidden)
        class Response(BytesIO):
            status=200
            def geturl(self):return m.RPC_URLS[8453]
        def pending(*a,**k):return Response(b'{"jsonrpc":"2.0","id":1,"result":null}')
        self.assertIsNone(m.rpc_read(8453,'eth_getTransactionReceipt',[HASH],opener=pending))
        def found(*a,**k):return Response(b'{"jsonrpc":"2.0","id":1,"result":{"status":"0x1"}}')
        self.assertEqual(m.rpc_read(8453,'eth_getTransactionReceipt',[HASH],opener=found),{'status':'0x1'})
        self.assertEqual(m.rpc_read(8453,'eth_getTransactionByHash',[HASH],opener=found),{'status':'0x1'})
        with self.assertRaises(m.ReadOnlyError):m.rpc_read(8453,'eth_getTransactionByHash',[HASH],opener=pending,sleep=lambda _:None)

    def test_rate_limit_retry_after_and_jsonrpc_error(self):
        class Response(BytesIO):
            status = 200
            def geturl(self): return m.RPC_URLS[8453]
        count = []
        def limited(req, timeout):
            count.append(1)
            if len(count) == 1: raise HTTPError(req.full_url, 429, 'limited', {'Retry-After': '2'}, None)
            return Response(b'{"jsonrpc":"2.0","id":1,"result":"0x2105"}')
        sleeps = []
        self.assertEqual(m.rpc_read(8453, 'eth_chainId', [], opener=limited, sleep=sleeps.append), '0x2105')
        self.assertEqual(sleeps, [2])
        def error(req, timeout): return Response(b'{"id":1,"error":{"code":-32005,"message":"private"}}')
        with self.assertRaises(m.ReadOnlyError):
            m.rpc_read(8453, 'eth_chainId', [], opener=error, sleep=lambda _: None)

    def test_reconciliation_needs_unique_matching_legs_and_never_adds_to_balance(self):
        leg = {'chain_id': 8453, 'tx_hash': HASH, 'contract': TOKEN, 'quantity': '1',
               'direction': 'out', 'confirmed': True, 'location': 'exchange', 'event_id': 'e1'}
        other = dict(leg, direction='in', location='wallet', event_id='w1')
        r = m.reconcile_events([leg], [other])
        self.assertEqual(r['matched_internal_movements'], 1)
        self.assertEqual(r['balance_adjustment'], '0')
        self.assertEqual(m.reconcile_events([leg], [])['unmatched_events'], 1)
        self.assertEqual(m.reconcile_events([leg, dict(leg, event_id='e2')], [other])['matched_internal_movements'], 0)
        self.assertEqual(m.reconcile_events([dict(leg, confirmed=False)], [other])['matched_internal_movements'], 0)
        self.assertEqual(m.reconcile_events([dict(leg, chain_id=1)], [other])['matched_internal_movements'], 0)

    def test_pagination_missing_terminal_evidence_and_rate_limit_budget(self):
        a = capture()
        page = a['reads'][0]['balance_pages'][0]
        page.pop('has_next')
        page['accounts'] *= 250
        with self.assertRaises(m.ReadOnlyError): m.normalize_exchange(a, NOW)
        def limited(req, timeout):
            raise HTTPError(req.full_url, 429, 'limited', {'Retry-After': '120'}, None)
        sleeps = []
        with self.assertRaises(m.ReadOnlyError):
            m.rpc_read(8453, 'eth_chainId', [], opener=limited, sleep=sleeps.append)
        self.assertEqual(sleeps, [])

    def test_chain_error_shape_and_zero_movement_are_not_confirmation(self):
        class Response(BytesIO):
            status = 200
            def geturl(self): return m.RPC_URLS[8453]
        def invalid(req, timeout): return Response(b'{"id":1,"error":"private data"}')
        with self.assertRaises(m.ReadOnlyError):
            m.rpc_read(8453, 'eth_chainId', [], opener=invalid)
        a = {'chain_id': 8453, 'tx_hash': HASH, 'contract': TOKEN, 'quantity': '0',
             'direction': 'out', 'confirmed': True, 'location': 'exchange', 'event_id': 'a'}
        b = dict(a, location='wallet', direction='in', event_id='b')
        self.assertEqual(m.reconcile_events([a], [b])['matched_internal_movements'], 0)

    def test_two_portfolios_and_combined_cli_do_not_double_count(self):
        from unittest.mock import patch
        from contextlib import redirect_stdout
        from io import StringIO
        a = capture(); p2 = deepcopy(a['reads'][0])
        p2['portfolio_id'] = 'p2'; p2['breakdown']['portfolio']['uuid'] = 'p2'
        for pos in p2['breakdown']['spot_positions']: pos['account_uuid'] += 'other'
        p2['balance_pages'][0]['portfolio_id'] = 'p2'
        p2['balance_pages'][0]['accounts'][0]['uuid'] = 'a2'
        a['portfolios'].append({'uuid': 'p2'}); a['reads'].append(p2)
        self.assertEqual(m.normalize_exchange(a, NOW)['reported_total_usd'], '200.0000')
        self.assertEqual(m.normalize_exchange(a, NOW)['trading_balances']['ETH']['available'], '0.014')
        a['captured_at'] = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m.write_private(root/'cex', a); m.write_private(root/'watch', watch())
            observe = m.observe_wallets
            def current_rpc(c, method, params):
                r = fake_rpc(c, method, params)
                if method == 'eth_getBlockByNumber':
                    r['timestamp'] = hex(int(datetime.now(timezone.utc).timestamp())-30)
                return r
            def wallet(config, now, **kw): return observe(config, now, rpc=current_rpc, **kw)
            output = StringIO()
            with patch.object(m, 'observe_wallets', side_effect=wallet), redirect_stdout(output):
                rc = m.main(['--exchange-capture', str(root/'cex'), '--wallet-watchlist', str(root/'watch'),
                             '--history-blocks', '10', '--output', str(root/'out')])
            self.assertEqual(rc, 0)
            report = m.read_private(root/'out')
            self.assertEqual(report['exchange']['reported_total_usd'], '200.0000')
            self.assertEqual(report['onchain']['wallets'][0]['history']['event_count'], 1)
            self.assertIsNone(report['consolidation']['combined_total_usd'])
            self.assertNotIn(ADDR, output.getvalue())

    def test_malformed_rpc_shape_and_capture_do_not_emit_tracebacks(self):
        class Response(BytesIO):
            status = 200
            def geturl(self): return m.RPC_URLS[8453]
        def wrong_shape(req, timeout):
            return Response(b'{"jsonrpc":"2.0","id":1,"result":[]}')
        with self.assertRaises(m.ReadOnlyError):
            m.rpc_read(8453, 'eth_getBlockByNumber', ['finalized', False], opener=wrong_shape)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); a = capture(); a['reads'][0]['breakdown'] = []
            m.write_private(root/'bad', a)
            r = subprocess.run([sys.executable, '-m', 'scripts.operational_read_only',
                '--exchange-capture', str(root/'bad'), '--at', NOW.isoformat(),
                '--output', str(root/'out')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertNotIn('Traceback', r.stderr)
            self.assertFalse((root/'out').exists())

    def test_real_http_redirect_is_rejected_before_following(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        from unittest.mock import patch
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(self.path)
                self.send_response(302)
                self.send_header('Location', '/forbidden')
                self.end_headers()
            def do_GET(self):
                requests.append(self.path)
                self.send_response(200); self.end_headers()
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with patch.dict(m.RPC_URLS, {8453: 'http://127.0.0.1:'+str(server.server_port)}):
                with self.assertRaises(m.ReadOnlyError):
                    m.rpc_read(8453, 'eth_chainId', [])
            self.assertEqual(requests, ['/'])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_shared_transfer_between_watched_wallets_does_not_abort_audit(self):
        other = '0x'+'2'*40
        cfg = watch()
        cfg['watch'].append(dict(cfg['watch'][0], label='secondary', address=other))
        transfer = {'address': TOKEN, 'topics': [m.TRANSFER_TOPIC,
            '0x'+'0'*24+ADDR[2:], '0x'+'0'*24+other[2:]],
            'transactionHash': HASH, 'blockHash': HASH, 'blockNumber': '0x64',
            'logIndex': '0x0', 'data': hex(100), 'removed': False}
        def rpc(c, method, params):
            if method == 'eth_getLogs':
                topics = params[0]['topics']
                matches = all(v is None or transfer['topics'][i] == v for i,v in enumerate(topics))
                return [deepcopy(transfer)] if matches else []
            return fake_rpc(c, method, params)
        result = m.observe_wallets(cfg, NOW, rpc=rpc, history_blocks=10)
        legs = [e for w in result['wallets'] for e in w['history']['events']]
        self.assertEqual(len(legs), 2)
        self.assertEqual({e['direction'] for e in legs}, {'in','out'})
        audit = m.reconcile_events([], legs)
        self.assertEqual({e['wallet_label'] for e in legs}, {'primary','secondary'})
        self.assertNotEqual(legs[0]['event_id'], legs[1]['event_id'])
        self.assertEqual(audit['matched_internal_movements'], 0)
        self.assertEqual(audit['unmatched_events'], 2)
        self.assertEqual(audit['balance_adjustment'], '0')
        self.assertNotIn(ADDR, json.dumps(result))
        self.assertNotIn(other, json.dumps(result))

    def test_history_event_time_is_from_matching_source_block(self):
        r = m.observe_wallets(watch(), NOW, rpc=fake_rpc, history_blocks=10)
        event = r['wallets'][0]['history']['events'][0]
        self.assertEqual(event['source_event_timestamp_utc'], '2026-10-21T08:59:30+00:00')
        self.assertEqual(r['wallets'][0]['history']['status'], 'COMPLETE_REQUESTED_TOKEN_RANGE')
        def wrong_block(c, method, params):
            value = fake_rpc(c, method, params)
            if method == 'eth_getLogs':
                for log in value: log['blockHash'] = '0x'+'b'*64
            return value
        with self.assertRaises(m.ReadOnlyError):
            m.observe_wallets(watch(), NOW, rpc=wrong_block, history_blocks=10)

    def test_partial_history_keeps_confirmed_balances_and_marks_missing_not_zero(self):
        cfg = watch()
        cfg['watch'].append(dict(cfg['watch'][0], label='ethereum', chain_id=1))
        def limited(c, method, params):
            if c == 8453 and method == 'eth_getLogs':
                raise m.ReadOnlyError('UPSTREAM_CONTAINS_'+ADDR)
            return fake_rpc(c, method, params)
        with self.assertRaises(m.ReadOnlyError):
            m.observe_wallets(cfg, NOW, rpc=limited, history_blocks=10)
        result = m.observe_wallets(cfg, NOW, rpc=limited, history_blocks=10, allow_partial_history=True)
        self.assertFalse(result['history_complete_for_requested_range'])
        base = result['wallets'][0]
        self.assertEqual(base['positions'][0]['quantity'], '0.1')
        self.assertIsNone(base['history']['event_count'])
        self.assertEqual(base['history']['status'], 'UNAVAILABLE')
        self.assertEqual(result['wallets'][1]['history']['event_count'], 1)
        self.assertNotIn(ADDR, json.dumps(result))

    def test_partial_history_cli_writes_private_report_and_returns_exit_three(self):
        from unittest.mock import patch
        from contextlib import redirect_stdout
        from io import StringIO
        observe = m.observe_wallets
        def limited(c, method, params):
            if method == 'eth_getLogs': raise m.ReadOnlyError('UNAVAILABLE_'+ADDR)
            value = fake_rpc(c, method, params)
            if method == 'eth_getBlockByNumber':
                value['timestamp'] = hex(int(datetime.now(timezone.utc).timestamp())-30)
            return value
        def wallet(config, now, **kw): return observe(config, now, rpc=limited, **kw)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); m.write_private(root/'watch', watch())
            a = capture(); a['captured_at'] = datetime.now(timezone.utc).isoformat()
            m.write_private(root/'cex', a)
            output = StringIO()
            with patch.object(m, 'observe_wallets', side_effect=wallet), redirect_stdout(output):
                rc = m.main(['--exchange-capture',str(root/'cex'),'--wallet-watchlist', str(root/'watch'),
                    '--history-blocks','10','--allow-partial-history','--output',str(root/'report')])
            self.assertEqual(rc, 3)
            r = m.read_private(root/'report')
            self.assertEqual(r['status'], 'PRIVATE_READ_ONLY_PARTIAL_OBSERVATION')
            self.assertEqual(r['exchange']['reported_total_usd'], '100.0000')
            self.assertEqual(r['onchain']['wallets'][0]['positions'][0]['quantity'], '0.1')
            self.assertEqual(r['transfer_reconciliation']['wallet_history_coverage'], 'PARTIAL')
            self.assertNotIn(ADDR,output.getvalue())

    def test_older_event_block_time_is_verified_and_fetched_once(self):
        calls = []
        older_hash = '0x'+'b'*64
        def older(c, method, params):
            calls.append((method, params))
            value = fake_rpc(c, method, params)
            if method == 'eth_getLogs':
                for log in value:
                    log['blockNumber'] = '0x63'; log['blockHash'] = older_hash
            if method == 'eth_getBlockByNumber' and params[0] == '0x63':
                return {'number':'0x63','hash':older_hash,'timestamp':hex(int(NOW.timestamp())-60)}
            return value
        r = m.observe_wallets(watch(), NOW, rpc=older, history_blocks=10)
        e = r['wallets'][0]['history']['events'][0]
        self.assertEqual(e['source_event_timestamp_utc'], '2026-10-21T08:59:00+00:00')
        self.assertEqual(e['block_hash'], older_hash)
        self.assertEqual(sum(method == 'eth_getBlockByNumber' and params[0] == '0x63'
                             for method,params in calls), 1)

    def test_partial_mode_cannot_relax_bad_range_or_changed_balance_block(self):
        calls = []
        def rpc(c, method, params):
            calls.append(method); return fake_rpc(c, method, params)
        for count in (-1, 1001, True):
            with self.subTest(count=count), self.assertRaises(m.ReadOnlyError):
                m.observe_wallets(watch(),NOW,rpc=rpc,history_blocks=count,allow_partial_history=True)
        self.assertEqual(calls, [])
        def changed(c, method, params):
            if method == 'eth_getLogs': raise m.ReadOnlyError('MISSING')
            value = fake_rpc(c, method, params)
            if method == 'eth_getBlockByNumber' and params[0] != 'finalized':
                value['hash'] = '0x'+'b'*64
            return value
        with self.assertRaises(m.ReadOnlyError):
            m.observe_wallets(watch(),NOW,rpc=changed,history_blocks=10,allow_partial_history=True)

    def test_private_file_permissions_symlinks_and_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'capture.json'; m.write_private(p, capture())
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            self.assertEqual(m.read_private(p)['mode'], capture()['mode'])
            link = Path(d)/'link'; link.symlink_to(p)
            with self.assertRaises(m.ReadOnlyError): m.read_private(link)
            with self.assertRaises(m.ReadOnlyError): m.write_private(link, {})
            with self.assertRaises(m.ReadOnlyError): m.write_private(p, {})
            out = Path(d)/'report.json'
            r = subprocess.run([sys.executable, '-m', 'scripts.operational_read_only',
                '--exchange-capture', str(p), '--at', NOW.isoformat(), '--output', str(out)],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn('100.0000', r.stdout)
            self.assertNotIn('p1', r.stdout)
            result = json.loads(out.read_text())
            self.assertEqual(result['exchange']['reported_total_usd'], '100.0000')
            self.assertEqual(result['financial_operations'], 0)
            self.assertEqual(result['transfer_reconciliation']['status'], 'EXCHANGE_HISTORY_UNAVAILABLE')
            p.chmod(0o644)
            with self.assertRaises(m.ReadOnlyError): m.read_private(p)
