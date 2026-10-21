import test from 'node:test';
import assert from 'node:assert/strict';
import {TransferSession, parseAmount, TOKEN} from './transfer.mjs';
const FROM='0x'+'1'.repeat(40), TO='0x'+'2'.repeat(40), HASH='0x'+'a'.repeat(64);
const TRANSFER='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef';
const policy=()=>({chainId:8453,from:FROM,to:TO,asset:'cbBTC',maxAmount:'0.0001',maxExecutionFeeWei:'1000000000000000',expiresAt:Date.now()+600000});
function provider(overrides={}){
 const calls=[],listeners={};
 const p={calls,on:(e,f)=>{listeners[e]=f;},removeListener:(e)=>delete listeners[e],emit:(e,v)=>listeners[e]?.(v),
  request:async({method,params})=>{calls.push({method,params});if(method in overrides)return overrides[method](params);
   return ({eth_requestAccounts:[FROM],eth_accounts:[FROM],eth_chainId:'0x2105',eth_getBalance:'0x38d7ea4c68000',
    eth_call:'0xf4240',eth_estimateGas:'0x186a0',eth_gasPrice:'0x3b9aca00',eth_sendTransaction:HASH})[method];}};
 return p;
}
test('exact units reject exponent, excess precision, zero and overflow',()=>{
 assert.equal(parseAmount('0.00000001',8),1n);
 for(const v of ['1e-8','0.000000001','0','-1','9'.repeat(80)])assert.throws(()=>parseAmount(v,8));
});
test('connect and preview never sign; transfer calldata has exact recipient and units',async()=>{
 const p=provider();const s=new TransferSession(p,policy());await s.connect();const r=await s.prepare('0.00000001');
 assert.equal(p.calls.filter(x=>x.method==='eth_sendTransaction').length,0);
 assert.equal(r.transaction.to,TOKEN);
 assert.equal(r.transaction.data,'0xa9059cbb'+'0'.repeat(24)+TO.slice(2)+'0'.repeat(63)+'1');
 assert.equal(r.transaction.value,'0x0');assert.equal(r.fullNetworkFeeVerified,false);
});
test('wrong account, wrong chain, no gas, cap and stale policy block before signing',async()=>{
 for(const changes of [
  {eth_requestAccounts:()=>[TO]}, {eth_chainId:()=> '0x1'}, {eth_getBalance:()=> '0x0'},
  {eth_call:()=> '0x0'},
 ]){
  const p=provider(changes),s=new TransferSession(p,policy());
  await assert.rejects(async()=>{await s.connect();await s.prepare('0.00000001');});
  assert.equal(p.calls.some(x=>x.method==='eth_sendTransaction'),false);
 }
 const p=provider();const s=new TransferSession(p,policy());await s.connect();await assert.rejects(s.prepare('1'));
 const expired=new TransferSession(provider(),{...policy(),expiresAt:Date.now()-1});await expired.connect();await assert.rejects(expired.prepare('0.00000001'));
});
test('only explicit reviewed submit signs once; concurrent clicks cannot duplicate',async()=>{
 const p=provider();const s=new TransferSession(p,policy());await s.connect();await s.prepare('0.00000001');
 await assert.rejects(s.submit(false));assert.equal(p.calls.some(x=>x.method==='eth_sendTransaction'),false);
 const results=await Promise.allSettled([s.submit(true),s.submit(true)]);
 assert.equal(results.filter(r=>r.status==='fulfilled').length,1);
 assert.equal(p.calls.filter(x=>x.method==='eth_sendTransaction').length,1);
 assert.equal(s.state,'submitted');assert.equal(s.hash,HASH);
});
test('account/chain event invalidates review and uncertain send is never retried',async()=>{
 const p=provider();const s=new TransferSession(p,policy());await s.connect();await s.prepare('0.00000001');p.emit('chainChanged','0x1');
 await assert.rejects(s.submit(true));assert.equal(p.calls.some(x=>x.method==='eth_sendTransaction'),false);
 const q=provider({eth_sendTransaction:()=>{throw new Error('private user data');}});const t=new TransferSession(q,policy());await t.connect();await t.prepare('0.00000001');
 await assert.rejects(t.submit(true),/SEND_STATUS_UNKNOWN/);assert.equal(t.state,'unknown');await assert.rejects(t.submit(true));
 assert.equal(q.calls.filter(x=>x.method==='eth_sendTransaction').length,1);
});
test('rejected signature resets review and receipt success requires matching transfer and finality',async()=>{
 const p=provider({eth_sendTransaction:()=>{throw {code:4001};}});const s=new TransferSession(p,policy());await s.connect();await s.prepare('0.00000001');
 await assert.rejects(s.submit(true),/USER_REJECTED/);assert.equal(s.state,'connected');
 const bh='0x'+'b'.repeat(64);
 const q=provider({eth_getTransactionReceipt:()=>({transactionHash:HASH,status:'0x1',blockNumber:'0x64',blockHash:bh,
  logs:[{address:TOKEN,topics:[TRANSFER,'0x'+'0'.repeat(24)+FROM.slice(2),'0x'+'0'.repeat(24)+TO.slice(2)],data:'0x'+'0'.repeat(63)+'1'}]}),
  eth_getBlockByNumber:([tag])=>({number:'0x64',hash:bh})});
 const t=new TransferSession(q,policy());await t.connect();await t.prepare('0.00000001');await t.submit(true);
 const r=await t.checkReceipt();assert.equal(r.status,'FINALIZED_ONCHAIN');assert.equal(r.exchangeCreditVerified,false);
});
test('connection-only policy cannot prepare a transfer',async()=>{
 const p=provider();const s=new TransferSession(p,null,[FROM]);await s.connect();await assert.rejects(s.prepare('0.00000001'),/POLICY_REQUIRED/);
 assert.equal(p.calls.some(x=>x.method==='eth_sendTransaction'),false);
});
test('review transaction is immutable and send errors cannot masquerade as preflight',async()=>{
 const p=provider(),s=new TransferSession(p,policy());await s.connect();const r=await s.prepare('0.00000001');
 assert.throws(()=>{r.transaction.to=TO;},TypeError);
 const q=provider({eth_sendTransaction:()=>{throw new Error('NO_GAS');}}),t=new TransferSession(q,policy());
 await t.connect();await t.prepare('0.00000001');await assert.rejects(t.submit(true),/SEND_STATUS_UNKNOWN/);
 assert.equal(t.state,'unknown');await assert.rejects(t.submit(true));
});
test('receipt cannot finalize without actual matching block hashes',async()=>{
 const q=provider({eth_getTransactionReceipt:()=>({transactionHash:HASH,status:'0x1',blockNumber:'0x64',
  logs:[{address:TOKEN,topics:[TRANSFER,'0x'+'0'.repeat(24)+FROM.slice(2),'0x'+'0'.repeat(24)+TO.slice(2)],data:'0x1'}]}),eth_getBlockByNumber:()=>({number:'0x64'})});
 const s=new TransferSession(q,policy());await s.connect();await s.prepare('0.00000001');await s.submit(true);
 await assert.rejects(s.checkReceipt(),/RECEIPT_BLOCK_CHANGED/);
});
test('identity change at last preflight check prevents submission',async()=>{
 let reads=0;const p=provider({eth_accounts:()=> (++reads===4?[TO]:[FROM])});
 const s=new TransferSession(p,policy());await s.connect();await s.prepare('0.00000001');
 await assert.rejects(s.submit(true),/ACCOUNT_CHANGED/);assert.equal(p.calls.some(x=>x.method==='eth_sendTransaction'),false);
});
test('explicit network switch checks watched identity and never submits funds',async()=>{
 let chain='0x1';
 const p=provider({eth_chainId:()=>chain,wallet_switchEthereumChain:([target])=>{chain=target.chainId;return null;}});
 const s=new TransferSession(p,policy());await assert.rejects(s.connect(),/WRONG_CHAIN/);
 await s.switchToPolicyChain();assert.equal(s.state,'connected');
 assert.equal(p.calls.filter(c=>c.method==='wallet_switchEthereumChain').length,1);
 assert.equal(p.calls.some(c=>c.method==='eth_sendTransaction'),false);
 const q=provider({eth_requestAccounts:()=>[TO]}),wrong=new TransferSession(q,policy());
 await assert.rejects(wrong.connect());await assert.rejects(wrong.switchToPolicyChain());
 assert.equal(q.calls.some(c=>c.method==='wallet_switchEthereumChain'),false);
});
test('preflight read errors report fixed stage without leaking provider details',async()=>{
 for(const [method,code] of [['eth_getBalance','BALANCE_RPC_UNAVAILABLE'],['eth_call','TOKEN_RPC_UNAVAILABLE'],['eth_estimateGas','GAS_ESTIMATE_UNAVAILABLE'],['eth_gasPrice','GAS_PRICE_UNAVAILABLE']]){
  const p=provider({[method]:()=>{throw new Error('PRIVATE_PROVIDER_DETAILS');}}),s=new TransferSession(p,policy());await s.connect();
  await assert.rejects(s.prepare('0.00000001'),new RegExp(code));
  assert.equal(p.calls.some(c=>c.method==='eth_sendTransaction'),false);
 }
});
test('independent read RPC rejects execution, bad chain and arbitrary calls',async()=>{
 const {createReadOnlyRpc}=await import('./read-rpc.mjs');const calls=[];
 const fetcher=async(url,options)=>{const r=JSON.parse(options.body);calls.push(r.method);return {ok:true,text:async()=>JSON.stringify({jsonrpc:'2.0',id:r.id,result:r.method==='eth_chainId'?'0x2105':'0x1'})};};
 const reader=createReadOnlyRpc(8453,fetcher);
 for(const method of ['eth_sendTransaction','eth_sendRawTransaction','eth_signTransaction','wallet_switchEthereumChain'])await assert.rejects(reader.request({method}));
 assert.equal(calls.length,0);
 await assert.rejects(reader.request({method:'eth_call',params:[{to:TOKEN,data:'0x095ea7b3'},'latest']}));
 assert.equal(await reader.request({method:'eth_getBalance',params:[FROM,'latest']}),'0x1');
 assert.deepEqual(calls,['eth_chainId','eth_getBalance']);
 const bad=createReadOnlyRpc(1,fetcher);await assert.rejects(bad.request({method:'eth_getBalance',params:[FROM,'latest']}),/CHAIN_MISMATCH/);
});
test('wallet identity and signature stay separate from independent preflight reads',async()=>{
 const p=provider({eth_getBalance:()=>{throw new Error('wallet read unavailable');}}),reads=provider();
 const s=new TransferSession(p,policy(),[],reads);await s.connect();await s.prepare('0.00000001');
 assert.equal(p.calls.some(c=>c.method==='eth_getBalance'),false);
 assert.equal(reads.calls.some(c=>c.method==='eth_getBalance'),true);
 assert.equal(reads.calls.some(c=>c.method==='eth_sendTransaction'),false);
});
