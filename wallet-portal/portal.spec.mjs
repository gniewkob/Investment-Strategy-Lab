import {test,expect} from '@playwright/test';
import {spawn} from 'node:child_process';
const FROM='0x'+'1'.repeat(40),TO='0x'+'2'.repeat(40);
const HASH='0x'+'a'.repeat(64),BLOCK_HASH='0x'+'b'.repeat(64);
const policy={chainId:8453,from:FROM,to:TO,asset:'cbBTC',maxAmount:'0.0001',maxExecutionFeeWei:'1000000000000000',expiresAt:Date.now()+600000};
let server;
test.beforeAll(async()=>{
 server=spawn(process.env.PYTHON||'python3',['-c',"from scripts.wallet_transfer_portal import make_handler; from http.server import ThreadingHTTPServer; from pathlib import Path; ThreadingHTTPServer(('127.0.0.1',18766),make_handler({'accounts':[], 'policy':None},Path('wallet-portal'))).serve_forever()"],{cwd:new URL('..',import.meta.url),stdio:'ignore'});
 let ready=false;for(let i=0;i<100;i++){try{const r=await fetch('http://127.0.0.1:18766');if(r.ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,50));}expect(ready).toBe(true);
});
test.afterAll(()=>server?.kill());
async function setup(page,enabled=true,sendError='reject',fromAccount=FROM,providerChoice='injected',initialChain='0x2105'){
 await page.route('**/session',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({accounts:[FROM],policy:enabled?policy:null})}));
 await page.route('https://mainnet.base.org/**',route=>{
  const r=route.request().postDataJSON();
  if(sendError==='receipt-error'&&r.method==='eth_getTransactionReceipt')return route.fulfill({status:429,body:''});
  const result=({eth_chainId:'0x2105',eth_getBalance:'0x38d7ea4c68000',eth_call:'0xf4240',eth_estimateGas:'0x186a0',eth_gasPrice:'0x3b9aca00',eth_getTransactionReceipt:sendError==='pending'?null:{transactionHash:HASH,status:'0x1',blockNumber:'0x10',blockHash:BLOCK_HASH,logs:[{address:'0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf',topics:['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef','0x'+'0'.repeat(24)+FROM.slice(2),'0x'+'0'.repeat(24)+TO.slice(2)],data:'0x1'}]},eth_getBlockByNumber:{number:'0x10',hash:BLOCK_HASH}})[r.method];
  return route.fulfill({contentType:'application/json',body:JSON.stringify({jsonrpc:'2.0',id:r.id,result})});
 });
 await page.addInitScript(({from,sendError,providerChoice,initialChain})=>{
  let activeChain=initialChain;
  window.walletCalls=[];const listeners={};window.emitWallet=(event,value)=>listeners[event]?.forEach(fn=>fn(value));
  window.ethereum={on:(event,fn)=>{(listeners[event]??=[]).push(fn);},removeListener:()=>{},request:async({method,params})=>{
   window.walletCalls.push(method);
   if(method==='eth_chainId')return activeChain;
   if(method==='wallet_switchEthereumChain'){activeChain=params[0].chainId;return null;}
   if(method==='eth_sendTransaction'){if(sendError==='reject')throw {code:4001};if(sendError==='unsupported')throw {code:4200,message:'PRIVATE_PROVIDER_DETAILS'};if(['success','pending','receipt-error'].includes(sendError))return '0x'+'a'.repeat(64);throw new Error('NO_GAS');}
   return ({eth_requestAccounts:[from],eth_accounts:[from],eth_chainId:'0x2105',eth_getBalance:'0x38d7ea4c68000',eth_call:'0xf4240',eth_estimateGas:'0x186a0',eth_gasPrice:'0x3b9aca00'})[method];
  }};
  if(providerChoice==='coinbase')window.coinbaseWalletExtension=window.ethereum;
 },{from:fromAccount,sendError,providerChoice,initialChain});
 await page.goto('http://127.0.0.1:18766');await expect(page.locator('#connect')).toBeEnabled();
 await expect.poll(()=>page.evaluate(()=>window.walletCalls.length)).toBe(0);
 await page.selectOption('#provider',providerChoice);await page.click('#connect');if(fromAccount===FROM&&initialChain==='0x2105')await expect(page.locator('#account')).toContainText('0x1111');
}
test('connection-only never permits preview or signature',async({page})=>{
 await setup(page,false);await expect(page.locator('#preview')).toBeDisabled();await expect(page.locator('#send')).toBeDisabled();
 await page.screenshot({path:'/tmp/isl-wallet-portal.png',fullPage:true});
 expect(await page.evaluate(()=>window.walletCalls)).toEqual(['eth_requestAccounts']);
});
test('review is explicit; rejected wallet signature clears approval',async({page})=>{
 await setup(page);await page.fill('#amount','0.00000001');await page.click('#preview');
 await expect(page.locator('#review')).toContainText(TO);await expect(page.locator('#send')).toBeDisabled();
 expect(await page.evaluate(()=>window.walletCalls.includes('eth_sendTransaction'))).toBe(false);
 await page.check('#confirm');await page.click('#send');await expect(page.locator('#status')).toContainText('Podpis anulowany');
 await expect(page.locator('#attempt')).toContainText('odmowę');
 await expect(page.locator('#send')).toBeDisabled();expect(await page.evaluate(()=>window.walletCalls.filter(x=>x==='eth_sendTransaction').length)).toBe(1);
});
test('ambiguous send locks session without retry',async({page})=>{
 await setup(page,true,'unknown');await page.fill('#amount','0.00000001');await page.click('#preview');await page.check('#confirm');await page.click('#send');
 await expect(page.locator('#status')).toContainText('nieznany');
 await expect(page.locator('#attempt')).toContainText('ponowienie zablokowane');await expect(page.locator('#preview')).toBeDisabled();await expect(page.locator('#connect')).toBeDisabled();
 expect(await page.evaluate(()=>window.walletCalls.filter(x=>x==='eth_sendTransaction').length)).toBe(1);
});

test('wrong account leaves provider choice available and transfer blocked',async({page})=>{
 await setup(page,false,'reject',TO);
 await expect(page.locator('#status')).toContainText('Wybrano inne konto');
 await expect(page.locator('#provider')).toBeEnabled();
 await expect(page.locator('#send')).toBeDisabled();
 await page.selectOption('#provider','base');
 await expect(page.locator('#connect')).toBeEnabled();
});

test('Coinbase Wallet choice connects existing extension without Base passkey popup',async({page})=>{
 await setup(page,false,'reject',FROM,'coinbase');
 await expect(page.locator('#provider')).toHaveValue('coinbase');
 expect(await page.evaluate(()=>window.walletCalls)).toEqual(['eth_requestAccounts']);
 await expect(page.locator('#send')).toBeDisabled();
 expect(page.context().pages()).toHaveLength(1);
});

test('wrong network can be switched explicitly before preview without signing',async({page})=>{
 await setup(page,true,'reject',FROM,'injected','0x1');
 await expect(page.locator('#status')).toContainText('Zmień sieć');
 await expect(page.locator('#switch-network')).toBeVisible();
 await page.click('#switch-network');
 await expect(page.locator('#amount')).toBeEnabled();
 await page.fill('#amount','0.00000001');await page.click('#preview');
 await expect(page.locator('#review')).toBeVisible();
 expect(await page.evaluate(()=>window.walletCalls.includes('eth_sendTransaction'))).toBe(false);
});

test('review card shows exact fee and expires without requesting a signature',async({page})=>{
 await setup(page);await page.fill('#amount','0.00000001');await page.click('#preview');
 await expect(page.locator('#review')).toContainText('0.00024 ETH');
 await expect(page.locator('#review')).toContainText('PLN: brak zweryfikowanej wyceny');
 await expect(page.locator('#progress')).toContainText('Twój podpis');
 await page.check('#confirm');await expect(page.locator('#send')).toBeEnabled();
 await page.clock.install();await page.clock.fastForward(61000);
 await expect(page.locator('#send')).toBeDisabled();await expect(page.locator('#validity')).toContainText('wygasł');
 expect(await page.evaluate(()=>window.walletCalls.includes('eth_sendTransaction'))).toBe(false);
});

test('returned hash triggers read-only finality verification and keeps exchange credit separate',async({page})=>{
 await setup(page,true,'success');await page.fill('#amount','0.00000001');await page.click('#preview');
 await page.check('#confirm');await page.click('#send');
 await expect(page.locator('#status')).toContainText('sfinalizowany');
 await expect(page.locator('#exchange-credit')).toContainText('Niezweryfikowane');
 await expect(page.locator('#tx-hash')).toHaveText(HASH);
 await expect(page.locator('#send')).toBeDisabled();
 expect(await page.evaluate(()=>window.walletCalls.filter(x=>x==='eth_sendTransaction').length)).toBe(1);
});

test('receipt API failure stops automatic checking without retrying the transfer',async({page})=>{
 let reads=0;page.on('request',r=>{if(r.url().startsWith('https://mainnet.base.org')&&r.postDataJSON()?.method==='eth_getTransactionReceipt')reads++;});
 await setup(page,true,'receipt-error');await page.fill('#amount','0.00000001');await page.click('#preview');
 await page.check('#confirm');await page.click('#send');
 await expect(page.locator('#status')).toContainText('Automatyczne sprawdzanie zatrzymane');
 await page.clock.install();await page.clock.fastForward(90000);
 expect(reads).toBe(1);await expect(page.locator('#receipt')).toBeEnabled();
 expect(await page.evaluate(()=>window.walletCalls.filter(x=>x==='eth_sendTransaction').length)).toBe(1);
});

test('pending confirmation stops after six reads and preserves one submitted transaction',async({page})=>{
 let reads=0;page.on('request',r=>{if(r.url().startsWith('https://mainnet.base.org')&&r.postDataJSON()?.method==='eth_getTransactionReceipt')reads++;});
 await setup(page,true,'pending');await page.fill('#amount','0.00000001');await page.click('#preview');
 await page.clock.install();await page.check('#confirm');await page.click('#send');await page.clock.runFor(10);
 await expect.poll(()=>reads).toBe(1);
 for(let i=2;i<=6;i++){await page.clock.runFor(10000);await expect.poll(()=>reads).toBe(i);}
 await expect(page.locator('#status')).toContainText('po sześciu odczytach');
 await page.clock.runFor(30000);expect(reads).toBe(6);
 await expect(page.locator('#receipt')).toBeEnabled();
 expect(await page.evaluate(()=>window.walletCalls.filter(x=>x==='eth_sendTransaction').length)).toBe(1);
});

test('expired policy is visible and blocks preview and approval',async({page})=>{
 await page.clock.install({time:new Date(policy.expiresAt+1000)});
 await setup(page);
 await expect(page.locator('#policy-note')).toBeVisible();
 await expect(page.locator('#status')).toContainText('Konfiguracja wygasła');
 await expect(page.locator('#preview')).toBeDisabled();await expect(page.locator('#send')).toBeDisabled();
 expect(await page.evaluate(()=>window.walletCalls.includes('eth_sendTransaction'))).toBe(false);
});

test('mobile review fits the viewport and amount edits invalidate approval',async({page})=>{
 await page.setViewportSize({width:390,height:844});await setup(page);
 await page.fill('#amount','0.00000001');await page.click('#preview');await page.check('#confirm');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.fill('#amount','0.00000002');await expect(page.locator('#review')).toBeHidden();
 await expect(page.locator('#send')).toBeDisabled();await expect(page.locator('#confirm')).not.toBeChecked();
});

test('small live fee movement reaches wallet with unchanged reviewed fee limits',async({page})=>{
 await setup(page);let prices=0;
 await page.route('https://mainnet.base.org/**',route=>{
  const r=route.request().postDataJSON();if(r.method!=='eth_gasPrice')return route.fallback();
  return route.fulfill({contentType:'application/json',body:JSON.stringify({jsonrpc:'2.0',id:r.id,result:++prices===1?'0x3b9aca00':'0x4190ab00'})});
 });
 await page.fill('#amount','0.00000001');await page.click('#preview');
 await expect(page.locator('#review')).toContainText('0.00024 ETH');
 await page.check('#confirm');await page.click('#send');
 await expect(page.locator('#status')).toContainText('Podpis anulowany');
 await expect(page.locator('#attempt')).toContainText('odmowę');
 expect(await page.evaluate(()=>window.walletCalls.filter(x=>x==='eth_sendTransaction').length)).toBe(1);
});

test('safe wallet error category is visible while uncertain outcome remains locked',async({page})=>{
 await setup(page,true,'unsupported');await page.fill('#amount','0.00000001');await page.click('#preview');
 await page.check('#confirm');await page.click('#send');
 await expect(page.locator('#attempt')).toContainText('UNSUPPORTED_METHOD (4200)');
 await expect(page.locator('#status')).toContainText('nieznany');await expect(page.locator('#send')).toBeDisabled();
 await expect(page.locator('body')).not.toContainText('PRIVATE_PROVIDER_DETAILS');
 expect(await page.evaluate(()=>window.walletCalls.filter(x=>x==='eth_sendTransaction').length)).toBe(1);
});
