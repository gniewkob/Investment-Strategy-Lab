"""Synthetic history only. No credentials or execution calls."""
from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import coinbase_read_only_history as h
from scripts.operational_read_only import write_private, read_private

NOW = datetime(2026,10,21,10,tzinfo=timezone.utc)


def fill(**kw):
    return dict({'trade_id':'trade1','order_id':'order1','product_id':'BTC-USD',
        'trade_time':'2026-10-20T12:00:00Z','price':'10000','size':'20',
        'size_in_quote':True,'commission':'.10','side':'BUY'},**kw)


def capture():
    return {'mode':'PRIVATE_COINBASE_FILLS_CAPTURE','captured_at':NOW.isoformat(),
        'start':'2026-10-01T00:00:00Z','end':NOW.isoformat(),'portfolio_ids':['portfolio1'],
        'reads':[{'portfolio_id':'portfolio1','pages':[{'request_cursor':None,
            'response':{'fills':[fill()], 'cursor':''}}]}]}


CSV = ('Coinbase report for [PRIVATE_PERSON]\n\n'
       'ID,Timestamp,Transaction Type,Asset,Quantity Transacted,Price Currency,Notes\n'
       'statement1,2026-10-20T12:00:00Z,Receive,ETH,0.1,USD,[PRIVATE_ADDRESS]\n'
       'statement2,2026-10-20T12:00:00Z,Advanced Trade Buy,BTC,0.002,USD,[PRIVATE_EMAIL]\n')


class HistoryTests(unittest.TestCase):
    def test_quote_size_is_never_mistaken_for_bitcoin_and_fee_currency_not_invented(self):
        out = h.normalize_fills(capture(),NOW)
        e = out['events'][0]
        self.assertEqual(e['reported_size_unit'],'USD')
        self.assertEqual(e['base_quantity_estimate'],'0.002')
        self.assertIsNone(e['base_quantity_reported'])
        self.assertIsNone(e['commission_currency'])
        self.assertEqual(e['commission_reported'],'0.10')
        self.assertNotIn('order1',json.dumps(out))
        self.assertNotIn('portfolio1',json.dumps(out))
        self.assertFalse(out['deposit_withdrawal_history_included'])
        self.assertFalse(out['snapshot_completeness_certified'])

    def test_base_size_and_unknown_size_flag_are_separate(self):
        a=capture();a['reads'][0]['pages'][0]['response']['fills']=[fill(size='.002',size_in_quote=False)]
        e=h.normalize_fills(a,NOW)['events'][0]
        self.assertEqual(e['base_quantity_reported'],'0.002')
        a['reads'][0]['pages'][0]['response']['fills'][0].pop('size_in_quote')
        e=h.normalize_fills(a,NOW)['events'][0]
        self.assertEqual(e['reported_size_unit'],'UNKNOWN')
        self.assertIsNone(e['base_quantity_estimate'])
        self.assertIsNone(e['base_quantity_reported'])

    def test_missing_pages_cursor_loops_duplicates_bad_scope_and_times_rejected(self):
        cases=[]
        for cursor in (0,False,True):
            a=capture();a['reads'][0]['pages'][0]['response']['cursor']=cursor;cases.append(a)
        a=capture();a['reads'][0]['pages'][0]['response']['cursor']='more';cases.append(a)
        a=capture();a['reads'][0]['pages'][0]['request_cursor']='unexpected';cases.append(a)
        a=capture();a['reads'][0]['pages'][0]['response']['fills']*=2;cases.append(a)
        a=capture();a['reads'][0]['portfolio_id']='other';cases.append(a)
        a=capture();a['reads'][0]['pages'][0]['response']['fills'][0]['trade_time']='2026-11-01T00:00:00Z';cases.append(a)
        a=capture();a['reads'][0]['pages'][0]['response']['proof_token_required']=True;cases.append(a)
        a=capture();a['reads'][0]['pages'][0]['response']['fills'][0]['size_in_quote']='false';cases.append(a)
        for i,a in enumerate(cases):
            with self.subTest(i=i),self.assertRaises(h.HistoryError):h.normalize_fills(a,NOW)

    def test_reader_calls_only_fills_and_follows_cursor_with_unchanged_scope(self):
        calls=[]
        def reader(tool, params):
            calls.append((tool,deepcopy(params)))
            return {'fills':[fill()] if not params.get('cursor') else [],
                    'cursor':'next' if not params.get('cursor') else ''}
        result=h.collect_fills(reader,['portfolio1'],'2026-10-01T00:00:00Z',NOW.isoformat(),NOW)
        self.assertEqual(len(calls),2)
        self.assertEqual({c[0] for c in calls},{'coinbase_orders_fills'})
        self.assertEqual(calls[1][1]['cursor'],'next')
        self.assertEqual(calls[0][1]['portfolio_id'],calls[1][1]['portfolio_id'])
        self.assertEqual(h.normalize_fills(result,NOW)['event_count'],1)
        def bad(tool, params):raise RuntimeError('[PRIVATE_ADDRESS]')
        with self.assertRaises(h.HistoryError) as e:
            h.collect_fills(bad,['portfolio1'],'2026-10-01T00:00:00Z',NOW.isoformat(),NOW)
        self.assertNotIn('[PRIVATE_ADDRESS]',str(e.exception))

    def test_statement_import_discards_preamble_notes_and_unconfirmed_linkage(self):
        out=h.parse_statement(CSV.encode(),NOW)
        self.assertEqual(out['event_count'],2)
        self.assertEqual(out['events'][0]['category'],'observed_inflow')
        self.assertEqual(out['events'][1]['category'],'trade')
        for e in out['events']:
            self.assertFalse(e['onchain_reconciliation_eligible'])
        for sensitive in ('[PRIVATE_PERSON]','[PRIVATE_ADDRESS]','[PRIVATE_EMAIL]','statement1'):
            self.assertNotIn(sensitive,json.dumps(out))
        self.assertFalse(out['complete_funding_history_certified'])

    def test_statement_duplicate_ids_unknown_types_bad_values_and_missing_identity(self):
        unknown=CSV.replace('Receive','New Unsupported Type')
        self.assertEqual(h.parse_statement(unknown.encode(),NOW)['unclassified_event_count'],1)
        for bad in (CSV.replace('statement2','statement1'),CSV.replace('0.1,USD','NaN,USD'),
                    CSV.replace('statement1,',' ,'),CSV.replace('Timestamp','Timestamp Local')):
            with self.subTest(bad=bad[:10]),self.assertRaises(h.HistoryError):
                h.parse_statement(bad.encode(),NOW)

    def test_empty_object_is_unknown_and_cursor_loop_is_bounded(self):
        a=capture();a['reads'][0]['pages'][0]['response']={}
        with self.assertRaises(h.HistoryError):h.normalize_fills(a,NOW)
        with self.assertRaises(h.HistoryError):
            h.collect_fills(lambda tool,params:{},['portfolio1'],'2026-10-01T00:00:00Z',NOW.isoformat(),NOW)
        calls=[]
        def loop(tool,params):
            calls.append(params);return {'fills':[],'cursor':'same'}
        with self.assertRaises(h.HistoryError):
            h.collect_fills(loop,['portfolio1'],'2026-10-01T00:00:00Z',NOW.isoformat(),NOW)
        self.assertEqual(len(calls),2)

    def test_statement_cannot_follow_symlink_or_accept_unbounded_decimal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'data').write_text(CSV);(root/'data').chmod(0o600)
            (root/'link').symlink_to(root/'data')
            with self.assertRaises(h.HistoryError):h.read_statement(root/'link',NOW)
        for value in ('Infinity','1e999999','1e-999999'):
            with self.assertRaises(h.HistoryError):
                h.parse_statement(CSV.replace('0.1,USD',value+',USD').encode(),NOW)

    def test_history_only_cli_keeps_fills_and_statement_as_separate_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_private(root/'fills',capture())
            (root/'statement').write_text(CSV);(root/'statement').chmod(0o600)
            cmd=[sys.executable,'-m','scripts.operational_read_only','--fills-capture',str(root/'fills'),
                 '--coinbase-history-csv',str(root/'statement'),'--at',NOW.isoformat(),'--output',str(root/'report')]
            p=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            r=read_private(root/'report')
            self.assertEqual(r['coinbase_history']['fills']['event_count'],1)
            self.assertEqual(r['coinbase_history']['statement']['event_count'],2)
            self.assertFalse(r['coinbase_history']['sources_summed'])
            self.assertIsNone(r['exchange'])
            self.assertEqual(r['financial_operations'],0)
            self.assertNotIn('statement1',p.stdout)
            (root/'statement').chmod(0o644)
            cmd[-1]=str(root/'bad-report')
            p=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(p.returncode,2)
            self.assertFalse((root/'bad-report').exists())
