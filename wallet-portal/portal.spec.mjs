import {test,expect} from '@playwright/test';
import {spawn} from 'node:child_process';
const FROM='0x'+'1'.repeat(40),TO='0x'+'2'.repeat(40);
const policy={chainId:8453,from:FROM,to:TO,asset:'cbBTC',maxAmount:'0.0001',maxExecutionFeeWei:'1000000000000000',expiresAt:Date.now()+600000};
let server;
test.beforeAll(async()=>{
 server=spawn(process.env.PYTHON||'python3',['-c',"from scripts.wallet_transfer_portal import make_handler; from http.server import ThreadingHTTPServer; from pathlib import Path; ThreadingHTTPServer(('127.0.0.1',18766),make_handler({'accounts':[], 'policy':None},Path('wallet-portal'))).serve_forever()"],{cwd:new URL('..',import.meta.url),stdio:'ignore'});
 let ready=false;for(let i=0;i<100;i++){try{const r=await fetch('http://127.0.0.1:18766');if(r.ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,50));}expect(ready).toBe(true);
});
test.afterAll(()=>server?.kill());
async function setup(page,enabled=true,sendError='reject'){
 await page.route('**/session',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({accounts:[FROM],policy:enabled?policy:null})}));
 await page.addInitScript(({from,sendError})=>{
  window.walletCalls=[];const listeners={};window.emitWallet=(event,value)=>listeners[event]?.forEach(fn=>fn(value));
  window.ethereum={on:(event,fn)=>{(listeners[event]??=[]).push(fn);},removeListener:()=>{},request:async({method})=>{
   window.walletCalls.push(method);
   if(method==='eth_sendTransaction'){if(sendError==='reject')throw {code:4001};throw new Error('NO_GAS');}
   return ({eth_requestAccounts:[from],eth_accounts:[from],eth_chainId:'0x2105',eth_getBalance:'0x38d7ea4c68000',eth_call:'0xf4240',eth_estimateGas:'0x186a0',eth_gasPrice:'0x3b9aca00'})[method];
  }};
 },{from:FROM,sendError});
 await page.goto('http://127.0.0.1:18766');await expect(page.locator('#connect')).toBeEnabled();
 await expect.poll(()=>page.evaluate(()=>window.walletCalls.length)).toBe(0);
 await page.selectOption('#provider','injected');await page.click('#connect');await expect(page.locator('#account')).toContainText('0x1111');
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
 await expect(page.locator('#send')).toBeDisabled();expect(await page.evaluate(()=>window.walletCalls.filter(x=>x==='eth_sendTransaction').length)).toBe(1);
});
test('ambiguous send locks session without retry',async({page})=>{
 await setup(page,true,'unknown');await page.fill('#amount','0.00000001');await page.click('#preview');await page.check('#confirm');await page.click('#send');
 await expect(page.locator('#status')).toContainText('nieznany');await expect(page.locator('#preview')).toBeDisabled();await expect(page.locator('#connect')).toBeDisabled();
 expect(await page.evaluate(()=>window.walletCalls.filter(x=>x==='eth_sendTransaction').length)).toBe(1);
});
