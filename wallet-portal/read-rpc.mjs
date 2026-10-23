// Independent public observations only. Wallet retains identity and signing.
import {TOKEN} from './transfer.mjs';
const URLS=Object.freeze({1:'https://ethereum-rpc.publicnode.com',8453:'https://mainnet.base.org'});
const METHODS=new Set(['eth_chainId','eth_getBalance','eth_call','eth_estimateGas','eth_gasPrice',
 'eth_getTransactionReceipt','eth_getTransactionByHash','eth_getBlockByNumber']);
export function createReadOnlyRpc(chainId,fetcher=fetch){
 if(!Object.hasOwn(URLS,chainId))throw new Error('READ_RPC_CHAIN_FORBIDDEN');
 let id=0;
 async function send(method,params){
  const requestId=++id,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
  try{
   const response=await fetcher(URLS[chainId],{method:'POST',credentials:'omit',redirect:'error',cache:'no-store',
    headers:{'Content-Type':'application/json'},signal:controller.signal,
    body:JSON.stringify({jsonrpc:'2.0',id:requestId,method,params})});
   if(!response.ok)throw new Error('READ_RPC_HTTP_REJECTED');
   const raw=await response.text();if(raw.length>1500000)throw new Error('READ_RPC_RESPONSE_TOO_LARGE');
   const data=JSON.parse(raw);
   if(data.id!==requestId||data.jsonrpc!=='2.0'||data.error||!Object.hasOwn(data,'result'))throw new Error('READ_RPC_RESPONSE_REJECTED');
   return data.result;
  }finally{clearTimeout(timer);}
 }
 return Object.freeze({async request({method,params=[]}){
  if(!METHODS.has(method)||!Array.isArray(params)||JSON.stringify(params).length>16000)throw new Error('READ_RPC_METHOD_FORBIDDEN');
  if(method==='eth_call'&&(params.length!==2||params[0]?.to?.toLowerCase()!==TOKEN||
   Object.keys(params[0]).some(k=>!['to','data'].includes(k))||!/^0x70a08231[0-9a-f]{64}$/i.test(params[0]?.data)))throw new Error('READ_RPC_CALL_FORBIDDEN');
  const chain=await send('eth_chainId',[]);
  if(typeof chain!=='string'||!/^0x[0-9a-f]+$/i.test(chain)||BigInt(chain)!==BigInt(chainId))throw new Error('READ_RPC_CHAIN_MISMATCH');
  return method==='eth_chainId'?chain:send(method,params);
 }});
}
