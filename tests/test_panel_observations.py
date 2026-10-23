"""Private snapshot/feed contract; all identities and RPC data are synthetic."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import panel_observations as m
from tests.test_operational_read_only import capture, watch, fake_rpc, NOW, ADDR, HASH, TOKEN
TO='0x'+'2'*40
TX='0x'+'b'*64

def cases():
 return {'mode':'PRIVATE_REGISTERED_TRANSFERS_V1','cases':[{'chain_id':8453,'tx_hash':TX,
   'asset':'cbBTC','amount':'0.00005','recipient':TO,'operator_credit_link':True,
   'operator_asserted_at_utc':NOW.isoformat()}]}

def rpc(c,method,params):
 if method=='eth_getTransactionReceipt':return {'transactionHash':TX,'status':'0x1','blockNumber':'0x64','blockHash':HASH,
  'logs':[{'address':TOKEN,'topics':[m.TRANSFER_TOPIC,'0x'+ADDR[2:].zfill(64),'0x'+TO[2:].zfill(64)],'data':hex(5000)}]}
 return fake_rpc(c,method,params)

def funded():
 c=capture();c['reads'][0]['balance_pages'][0]['accounts'].append({'uuid':'btc','currency':'BTC',
  'available_balance':{'currency':'BTC','value':'0.00005'},'hold':{'currency':'BTC','value':'0'}})
 return c

class FrozenDateTime(datetime):
 @classmethod
 def now(cls,tz=None):return NOW

class PanelObservationTests(unittest.TestCase):
 def setUp(self):
  patcher=patch('scripts.operational_read_only.datetime',FrozenDateTime)
  patcher.start();self.addCleanup(patcher.stop)
 def snapshot(self):return m.build_snapshot(watch(),funded(),cases(),NOW,rpc=rpc)
 def test_balances_and_history_never_become_a_deposit_history_proof_or_total(self):
  s=self.snapshot();p=m.project(s,[ADDR],NOW)
  self.assertEqual(p['exchange']['status'],'FRESH')
  self.assertEqual(p['transfers'][0]['network'],'FINALIZED')
  self.assertEqual(p['transfers'][0]['credit'],'BALANCE_PRESENT_NOT_DEPOSIT_PROOF')
  self.assertEqual(p['transfers'][0]['credit_link'],'OPERATOR_ASSERTED')
  self.assertIsNone(p['combined_total_usd'])
  self.assertFalse(p['event_amounts_added_to_balances'])
  self.assertIsNone(p['exchange']['source_as_of_utc'])
  raw=str(p);self.assertNotIn('account_uuid',raw);self.assertNotIn('p1',raw)
 def test_foreign_identity_and_offline_clock_are_rejected(self):
  s=self.snapshot()
  with self.assertRaises(m.ObservationError):m.project(s,[TO],NOW)
  s['clock_mode']='OFFLINE_REPLAY'
  with self.assertRaises(m.ObservationError):m.project(s,[ADDR],NOW)
 def test_stale_values_are_hidden_without_losing_historical_finality(self):
  p=m.project(self.snapshot(),[ADDR],NOW+timedelta(minutes=31))
  self.assertEqual(p['exchange']['status'],'STALE');self.assertEqual(p['exchange']['balances'],[])
  self.assertEqual(p['wallet']['status'],'STALE');self.assertEqual(p['wallet']['positions'],[])
  self.assertEqual(p['transfers'][0]['network'],'FINALIZED')
  self.assertEqual(p['transfers'][0]['credit'],'UNAVAILABLE')
 def test_temporal_overlap_is_flagged_not_summed(self):
  s=self.snapshot();s['wallets'][0]['block_number']=99
  p=m.project(s,[ADDR],NOW)
  self.assertTrue(p['temporal_overlap'])
  self.assertIsNone(p['combined_total_usd'])
 def test_duplicate_cases_and_unexpected_fields_rejected(self):
  for mutate in (lambda x:x['cases'].append(deepcopy(x['cases'][0])),lambda x:x['cases'][0].update(secret='never-display')):
   x=cases();mutate(x)
   with self.assertRaises(m.ObservationError):m.build_snapshot(watch(),funded(),x,NOW,rpc=rpc)
 def test_failure_and_ambiguous_capture_do_not_become_zero_balances(self):
  def broken(*a):raise ValueError('PRIVATE_UPSTREAM_DETAILS')
  s=m.build_snapshot(watch(),{},cases(),NOW,rpc=broken);p=m.project(s,[ADDR],NOW)
  self.assertEqual(p['exchange']['status'],'UNAVAILABLE');self.assertEqual(p['wallet']['status'],'UNAVAILABLE')
  self.assertEqual(p['transfers'][0]['network'],'UNAVAILABLE');self.assertNotIn('PRIVATE_UPSTREAM',str(p))
 def test_wrong_transfer_or_block_hash_never_finalizes(self):
  for field,value in (('data','0x1'),('blockHash','0x'+'c'*64)):
   def wrong(c,method,params):
    r=rpc(c,method,params)
    if method=='eth_getTransactionReceipt':
     if field=='data':r['logs'][0]['data']=value
     else:r[field]=value
    return r
   s=m.build_snapshot(watch(),funded(),cases(),NOW,rpc=wrong)
   self.assertEqual(m.project(s,[ADDR],NOW)['transfers'][0]['network'],'UNAVAILABLE')
 def test_atomic_publication_preserves_history_rejects_unrelated_latest_and_symlinks(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);root.chmod(0o700);s=self.snapshot()
   m.publish(root,s);self.assertEqual(len(list(root.glob('observation-*.json'))),1)
   s['generated_at_utc']=(NOW+timedelta(seconds=1)).isoformat();m.publish(root,s)
   self.assertEqual(len(list(root.glob('observation-*.json'))),2)
   self.assertEqual(m.load(root/'latest.json',[ADDR],NOW+timedelta(seconds=1))['exchange']['status'],'FRESH')
   (root/'latest.json').unlink();(root/'latest.json').symlink_to(root/'other')
   with self.assertRaises(m.ObservationError):m.publish(root,s)
 def test_project_rejects_forged_credit_enum_and_future_timestamp(self):
  for mutate in (lambda s:s['transfers'][0].update(credit='VERIFIED_DEPOSIT'),lambda s:s.update(generated_at_utc=(NOW+timedelta(days=1)).isoformat())):
   s=self.snapshot();mutate(s)
   with self.assertRaises(m.ObservationError):m.project(s,[ADDR],NOW)
 def test_pending_reverted_and_direct_native_transfer_are_distinct(self):
  row=cases()['cases'][0]
  self.assertEqual(m.verify_case(row,ADDR,lambda *a: '0x2105' if a[1]=='eth_chainId' else None,NOW)['network'],'PENDING')
  def reverted(c,method,params):
   result=rpc(c,method,params)
   if method=='eth_getTransactionReceipt':result['status']='0x0'
   return result
  self.assertEqual(m.verify_case(row,ADDR,reverted,NOW)['network'],'REVERTED')
  native={**row,'asset':'ETH'}
  def direct(c,method,params):
   if method=='eth_getTransactionByHash':return {'hash':TX,'from':ADDR,'to':TO,'value':hex(50000000000000),'blockNumber':'0x64'}
   return rpc(c,method,params)
  self.assertEqual(m.verify_case(native,ADDR,direct,NOW)['network'],'FINALIZED')
  def bundled(c,method,params):
   if method=='eth_getTransactionByHash':return {'hash':TX,'from':TO,'to':TOKEN,'value':'0x0','blockNumber':'0x64'}
   return rpc(c,method,params)
  self.assertEqual(m.verify_case(native,ADDR,bundled,NOW)['network'],'UNAVAILABLE')
