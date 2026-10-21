"""Synthetic local portal policy + HTTP privacy boundaries. No wallet signature."""
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest import TestCase
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import json
import tempfile

from scripts.wallet_transfer_portal import make_handler, load_config, PortalError
from scripts.operational_read_only import write_private

ADDR='0x'+'1'*40
TO='0x'+'2'*40
TOKEN='0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf'

def watch():
 return {'mode':'PRIVATE_WALLET_READ_ONLY','watch':[{'label':'base','chain_id':8453,
     'address':ADDR,'verified_token_contracts':[TOKEN]}]}

def policy():
 return {'mode':'USER_CONFIRMED_WALLET_TRANSFER','chain_id':8453,'from_label':'base',
   'destination':TO,'asset':'cbBTC','max_amount':'0.0001','max_execution_fee_wei':'1000000000000000',
   'destination_confirmed_in_coinbase':True,
   'confirmed_at':datetime.now(timezone.utc).isoformat(),
   'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}

class PortalTests(TestCase):
 def test_connection_only_default_and_explicit_policy_binding(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);write_private(root/'watch',watch());write_private(root/'policy',policy())
   c=load_config(root/'watch',None)
   self.assertIsNone(c['policy'])
   c=load_config(root/'watch',root/'policy')
   self.assertEqual(c['policy']['from'],ADDR)
   self.assertEqual(c['policy']['to'],TO)
   self.assertEqual(c['policy']['maxAmount'],'0.0001')
 def test_policy_requires_fresh_destination_known_account_and_caps(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);write_private(root/'watch',watch())
   cases=[]
   for k,v in [('destination',ADDR),('destination',TOKEN),('destination','0x'+'0'*40),
      ('from_label','unknown'),('destination_confirmed_in_coinbase',False),('max_amount','1e3'),
      ('max_execution_fee_wei','0'),('expires_at','2020-01-01T00:00:00Z'),('chain_id',10)]:
    a=policy();a[k]=v;cases.append(a)
   for i,a in enumerate(cases):
    write_private(root/str(i),a)
    with self.subTest(i=i),self.assertRaises(PortalError):load_config(root/'watch',root/str(i))
 def test_local_host_origin_no_cache_and_no_post_rpc_proxy(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'index.html').write_text('<!doctype html><title>Test</title>')
   (root/'dist').mkdir();(root/'dist/app.js').write_text('export {};')
   handler=make_handler({'accounts':[ADDR],'policy':None},root)
   server=ThreadingHTTPServer(('127.0.0.1',0),handler)
   t=Thread(target=server.serve_forever,daemon=True);t.start()
   base=f'http://127.0.0.1:{server.server_port}'
   try:
    with urlopen(base) as r:
     self.assertEqual(r.status,200)
     self.assertEqual(r.headers['Cache-Control'],'no-store')
     self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
     self.assertIn("https://mainnet.base.org",r.headers['Content-Security-Policy'])
    with urlopen(Request(base,method='HEAD')) as r:
     self.assertEqual(r.status,200)
     self.assertEqual(r.headers['Cross-Origin-Opener-Policy'],'same-origin-allow-popups')
     self.assertEqual(r.read(),b'')
    with self.assertRaises(HTTPError) as e:urlopen(base+'/session')
    self.assertEqual(e.exception.code,403)
    with urlopen(Request(base+'/session',headers={'Origin':base})) as r:
     self.assertEqual(json.load(r)['accounts'],[ADDR])
    for headers in ({'Origin':'https://attacker.invalid'},{'Host':'attacker.invalid'}):
     with self.assertRaises(HTTPError):urlopen(Request(base+'/session',headers=headers))
    with self.assertRaises(HTTPError) as e:urlopen(Request(base+'/send',data=b'{}',headers={'Origin':base}))
    self.assertEqual(e.exception.code,405)
    with self.assertRaises(HTTPError):urlopen(base+'/../AGENTS.md')
   finally:server.shutdown();server.server_close();t.join()
