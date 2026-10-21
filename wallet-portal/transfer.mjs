// Wallet-held signing only. No private keys, allowances, session keys or retries.
export const TOKEN='0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf';
const TOPIC='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef';
const ADDRESS=/^0x[0-9a-fA-F]{40}$/, HASH=/^0x[0-9a-fA-F]{64}$/;
function check(ok,code){if(!ok)throw new Error(code);}
function address(v){check(typeof v==='string'&&ADDRESS.test(v),'INVALID_ADDRESS');return v.toLowerCase();}
function quantity(v){check(typeof v==='string'&&/^0x[0-9a-fA-F]{1,64}$/.test(v),'INVALID_RPC_QUANTITY');return BigInt(v);}
const hex=v=>'0x'+v.toString(16);
export function parseAmount(value,decimals){
 check(typeof value==='string'&&value.length<=80&&/^(0|[1-9][0-9]*)(\.[0-9]+)?$/.test(value),'INVALID_AMOUNT');
 const [whole,fraction='']=value.split('.');check(fraction.length<=decimals,'EXCESS_PRECISION');
 const result=BigInt(whole)*10n**BigInt(decimals)+BigInt(fraction.padEnd(decimals,'0')||'0');
 check(result>0n&&result<2n**256n,'INVALID_AMOUNT');return result;
}
export class TransferSession{
 constructor(provider,policy,expectedAccounts=[],readProvider=provider){
  this.provider=provider;this.readProvider=readProvider;this.policy=policy?Object.freeze({...policy}):null;
  this.expectedAccounts=(policy?[policy.from]:expectedAccounts).map(address);
  this.state='disconnected';this.prepared=null;this.hash=null;this.generation=0;this.busy=false;
  this.invalidate=()=>{this.generation++;this.prepared=null;if(!['submitted','unknown','submitting'].includes(this.state))this.state='disconnected';};
  for(const e of ['accountsChanged','chainChanged','disconnect'])provider.on?.(e,this.invalidate);
 }
 async connect(){
  check(!['submitting','submitted','unknown'].includes(this.state),'SESSION_LOCKED');
  const accounts=await this.provider.request({method:'eth_requestAccounts'});
  check(Array.isArray(accounts)&&accounts.length>0,'NO_ACCOUNT');this.account=address(accounts[0]);
  check(this.expectedAccounts.includes(this.account),'UNEXPECTED_ACCOUNT');
  if(this.policy)await this.checkIdentity();
  this.state='connected';return this.account;
 }
 async switchToPolicyChain(){
  check(this.policy,'POLICY_REQUIRED');
  check(!this.busy&&!['submitting','submitted','unknown'].includes(this.state),'SESSION_LOCKED');
  check(this.account===address(this.policy.from),'UNEXPECTED_ACCOUNT');
  this.busy=true;this.prepared=null;this.generation++;this.state='disconnected';
  try{
   const accounts=await this.provider.request({method:'eth_accounts'});
   check(Array.isArray(accounts)&&accounts.length>0&&address(accounts[0])===this.account,'ACCOUNT_CHANGED');
   await this.provider.request({method:'wallet_switchEthereumChain',params:[{chainId:hex(BigInt(this.policy.chainId))}]});
   await this.checkIdentity();this.state='connected';
  }catch(e){throw new Error(e?.code===4001?'USER_REJECTED':'NETWORK_SWITCH_FAILED');}
  finally{this.busy=false;}
 }
 async checkIdentity(){
  const accounts=await this.provider.request({method:'eth_accounts'});
  check(Array.isArray(accounts)&&accounts.length>0&&address(accounts[0])===this.account,'ACCOUNT_CHANGED');
  const chain=quantity(await this.provider.request({method:'eth_chainId'}));
  check(chain===BigInt(this.policy.chainId),'WRONG_CHAIN');
 }
 async readQuantity(method,params,errorCode){
  try{return quantity(await this.readProvider.request({method,params}));}
  catch(e){const error=new Error(errorCode);if(/no rpc url/i.test(String(e?.message)))error.safeReason='RPC_URL_MISSING';throw error;}
 }
 async inspect(amount){
  const p=this.policy;check(p,'POLICY_REQUIRED');
  check(Number.isSafeInteger(p.expiresAt)&&Date.now()<p.expiresAt,'POLICY_EXPIRED');
  check([1,8453].includes(p.chainId)&&['ETH','cbBTC'].includes(p.asset),'INVALID_SCOPE');
  check(address(p.from)===this.account,'UNEXPECTED_ACCOUNT');
  const to=address(p.to);check(!['0x'+'0'.repeat(40),this.account,TOKEN].includes(to),'INVALID_DESTINATION');
  const units=parseAmount(amount,p.asset==='cbBTC'?8:18);
  check(units<=parseAmount(p.maxAmount,p.asset==='cbBTC'?8:18),'AMOUNT_CAP_EXCEEDED');
  check(typeof p.maxExecutionFeeWei==='string'&&/^[1-9][0-9]{0,29}$/.test(p.maxExecutionFeeWei),'FEE_CAP_REQUIRED');
  await this.checkIdentity();
  const native=await this.readQuantity('eth_getBalance',[this.account,'latest'],'BALANCE_RPC_UNAVAILABLE');
  check(native>0n,'NO_GAS');
  const tx={from:this.account,to:p.asset==='cbBTC'?TOKEN:to,value:p.asset==='ETH'?hex(units):'0x0',
    data:p.asset==='cbBTC'?'0xa9059cbb'+to.slice(2).padStart(64,'0')+units.toString(16).padStart(64,'0'):'0x',chainId:hex(BigInt(p.chainId))};
  if(p.asset==='cbBTC'){
   const balance=await this.readQuantity('eth_call',[{to:TOKEN,data:'0x70a08231'+this.account.slice(2).padStart(64,'0')},'latest'],'TOKEN_RPC_UNAVAILABLE');
   check(balance>=units,'INSUFFICIENT_TOKEN_BALANCE');
  }
  const estimated=await this.readQuantity('eth_estimateGas',[tx],'GAS_ESTIMATE_UNAVAILABLE');
  const price=await this.readQuantity('eth_gasPrice',[],'GAS_PRICE_UNAVAILABLE');
  check(estimated>0n&&price>0n,'GAS_ESTIMATE_MISSING');
  const gas=(estimated*120n+99n)/100n,gasPrice=price*2n,fee=gas*gasPrice;
  check(fee<=BigInt(p.maxExecutionFeeWei),'EXECUTION_FEE_CAP_EXCEEDED');
  check(native>=fee+(p.asset==='ETH'?units:0n),'INSUFFICIENT_GAS_BALANCE');
  return {transaction:{...tx,gas:hex(gas),gasPrice:hex(gasPrice)},amount,units:units.toString(),
   recipient:to,chainId:p.chainId,asset:p.asset,executionFeeUpperWei:fee.toString(),
   fullNetworkFeeVerified:false,reviewedAt:Date.now(),generation:this.generation};
 }
 async prepare(amount){
  check(this.state==='connected'||this.state==='prepared','NOT_CONNECTED');check(!this.busy,'REQUEST_BUSY');
  this.busy=true;const generation=this.generation;this.prepared=null;this.state='connected';
  try{const result=await this.inspect(amount);check(generation===this.generation,'IDENTITY_CHANGED');
   Object.freeze(result.transaction);this.prepared=Object.freeze(result);this.state='prepared';return result;
  }finally{this.busy=false;}
 }
 async submit(reviewConfirmed){
  check(reviewConfirmed===true,'REVIEW_REQUIRED');check(this.state==='prepared'&&!this.busy,'NOT_READY');
  const reviewed=this.prepared;check(Date.now()-reviewed.reviewedAt<60000,'REVIEW_EXPIRED');
  this.state='submitting';this.busy=true;let sendAttempted=false;
  try{
   const current=await this.inspect(reviewed.amount);
   check(current.generation===reviewed.generation,'IDENTITY_CHANGED');
   check(current.executionFeeUpperWei===reviewed.executionFeeUpperWei,'FEE_CHANGED_REVIEW_AGAIN');
   await this.checkIdentity();
   check(this.generation===reviewed.generation,'IDENTITY_CHANGED');
   // Keep the reviewed fields, not a mutable form object. Wallet approval is final.
   sendAttempted=true;
   const result=await this.provider.request({method:'eth_sendTransaction',params:[{...reviewed.transaction}]});
   check(typeof result==='string'&&HASH.test(result),'SEND_STATUS_UNKNOWN');
   this.hash=result;this.prepared=reviewed;this.state='submitted';return result;
  }catch(e){
   if(e?.code===4001){this.state='connected';this.prepared=null;throw new Error('USER_REJECTED');}
   if(!sendAttempted&&['POLICY_EXPIRED','WRONG_CHAIN','ACCOUNT_CHANGED','IDENTITY_CHANGED','FEE_CHANGED_REVIEW_AGAIN','NO_GAS',
       'INSUFFICIENT_TOKEN_BALANCE','INSUFFICIENT_GAS_BALANCE','EXECUTION_FEE_CAP_EXCEEDED',
       'BALANCE_RPC_UNAVAILABLE','TOKEN_RPC_UNAVAILABLE','GAS_ESTIMATE_UNAVAILABLE','GAS_PRICE_UNAVAILABLE'].includes(e?.message)){
    this.state='connected';this.prepared=null;throw new Error(e.message);
   }
   this.state='unknown';throw new Error('SEND_STATUS_UNKNOWN');
  }finally{this.busy=false;}
 }
 async checkReceipt(){
  check(this.state==='submitted'&&HASH.test(this.hash),'NO_SUBMITTED_HASH');await this.checkIdentity();
  const receipt=await this.readProvider.request({method:'eth_getTransactionReceipt',params:[this.hash]});
  if(!receipt)return {status:'PENDING',exchangeCreditVerified:false};
  check(receipt.transactionHash?.toLowerCase()===this.hash.toLowerCase(),'RECEIPT_HASH_MISMATCH');
  if(receipt.status==='0x0')return {status:'REVERTED',exchangeCreditVerified:false};
  check(receipt.status==='0x1','UNKNOWN_RECEIPT_STATUS');
  const p=this.policy,r=this.prepared;
  if(p.asset==='cbBTC'){
   const matched=(receipt.logs||[]).filter(l=>l.address?.toLowerCase()===TOKEN&&l.topics?.length===3&&
    l.topics[0]?.toLowerCase()===TOPIC&&l.topics[1]?.toLowerCase()==='0x'+this.account.slice(2).padStart(64,'0')&&
    l.topics[2]?.toLowerCase()==='0x'+r.recipient.slice(2).padStart(64,'0')&&quantity(l.data)===BigInt(r.units));
   check(matched.length===1,'RECEIPT_TRANSFER_NOT_PROVEN');
  }else{
   const tx=await this.readProvider.request({method:'eth_getTransactionByHash',params:[this.hash]});
   check(tx?.hash?.toLowerCase()===this.hash.toLowerCase()&&address(tx.from)===this.account&&
    address(tx.to)===r.recipient&&quantity(tx.value)===BigInt(r.units)&&quantity(tx.blockNumber)===quantity(receipt.blockNumber),'RECEIPT_TRANSFER_NOT_PROVEN');
  }
  const finalized=await this.readProvider.request({method:'eth_getBlockByNumber',params:['finalized',false]});
  if(quantity(finalized?.number)<quantity(receipt.blockNumber))return {status:'INCLUDED_NOT_FINALIZED',exchangeCreditVerified:false};
  const block=await this.readProvider.request({method:'eth_getBlockByNumber',params:[receipt.blockNumber,false]});
  check(HASH.test(block?.hash)&&HASH.test(receipt.blockHash)&&
   quantity(block.number)===quantity(receipt.blockNumber)&&
   block.hash.toLowerCase()===receipt.blockHash.toLowerCase(),'RECEIPT_BLOCK_CHANGED');
  return {status:'FINALIZED_ONCHAIN',exchangeCreditVerified:false};
 }
 disconnect(){
  check(!this.busy,'REQUEST_BUSY');this.invalidate();
  for(const e of ['accountsChanged','chainChanged','disconnect'])this.provider.removeListener?.(e,this.invalidate);
 }
}
