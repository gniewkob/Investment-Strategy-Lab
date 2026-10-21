import {createCoinbaseWalletSDK} from '@coinbase/wallet-sdk';
import {createBaseAccountSDK} from '@base-org/account';
import {TransferSession} from './transfer.mjs';
import {createReadOnlyRpc} from './read-rpc.mjs';
const $=id=>document.getElementById(id);
let config,session,busy=false;
const text={BALANCE_RPC_UNAVAILABLE:'Portfel nie udostępnił odczytu ETH w wybranej sieci. Podpis zablokowany.',TOKEN_RPC_UNAVAILABLE:'Portfel nie udostępnił odczytu cbBTC. Podpis zablokowany.',GAS_ESTIMATE_UNAVAILABLE:'Nie udało się oszacować gas dla transferu. Podpis zablokowany.',GAS_PRICE_UNAVAILABLE:'Nie udało się odczytać ceny gas. Podpis zablokowany.',NETWORK_SWITCH_FAILED:'Portfel nie przełączył sieci. Wybierz Base w aplikacji portfela i podłącz ponownie.',UNEXPECTED_ACCOUNT:'Wybrano inne konto niż zatwierdzone przez operatora.',WRONG_CHAIN:'Zmień sieć w portfelu na wskazaną w konfiguracji, a następnie podłącz ponownie.',NO_GAS:'Brak ETH na opłatę sieciową. Transfer zablokowany.',INSUFFICIENT_GAS_BALANCE:'Za mało ETH na kwotę i szacowaną opłatę.',INSUFFICIENT_TOKEN_BALANCE:'Za małe saldo tokena.',POLICY_REQUIRED:'Tryb podłączenia: brak konfiguracji transferu.',POLICY_EXPIRED:'Konfiguracja wygasła. Operator musi ponownie sprawdzić adres docelowy.',AMOUNT_CAP_EXCEEDED:'Kwota przekracza limit operatora.',EXECUTION_FEE_CAP_EXCEEDED:'Opłata wykonania przekracza limit.',USER_REJECTED:'Podpis anulowany. Niczego automatycznie nie ponawiamy.',SEND_STATUS_UNKNOWN:'Wynik wysyłki jest nieznany. Sprawdź historię w portfelu przed jakąkolwiek kolejną próbą. Panel jest zablokowany.',REVIEW_EXPIRED:'Podgląd wygasł. Przygotuj go ponownie.',FEE_CHANGED_REVIEW_AGAIN:'Zmieniła się opłata. Przygotuj nowy podgląd.',NO_PROVIDER:'Nie znaleziono rozszerzenia. Otwórz panel w przeglądarce z portfelem albo wybierz Coinbase Wallet (QR).',IDENTITY_CHANGED:'Konto lub sieć zmieniły się. Podłącz ponownie.',ACCOUNT_CHANGED:'Konto zmieniło się. Podłącz ponownie.',INVALID_AMOUNT:'Wpisz dodatnią kwotę dziesiętną bez notacji wykładniczej.',EXCESS_PRECISION:'Kwota ma zbyt wiele miejsc dziesiętnych.'};
function status(message){$('status').textContent=message;}
function render(){
 const state=session?.state,locked=['submitting','submitted','unknown'].includes(state);
 $('connect').disabled=busy||locked||!config;$('provider').disabled=busy||locked||['connected','prepared'].includes(state);
 $('switch-network').hidden=!(config?.policy&&session?.account===config.policy.from.toLowerCase()&&state==='disconnected');
 $('switch-network').disabled=busy||locked;
 $('amount').disabled=busy||!config?.policy||!['connected','prepared'].includes(state);
 $('preview').disabled=$('amount').disabled;
 $('confirm').disabled=busy||state!=='prepared';
 $('send').disabled=busy||state!=='prepared'||!$('confirm').checked;
 $('receipt').disabled=busy||state!=='submitted';
 if(state!=='prepared'&&state!=='submitted'){$('review').hidden=true;$('empty').hidden=false;$('confirm').checked=false;}
}
async function action(fn){if(busy)return;busy=true;render();try{await fn();}catch(e){status((text[e?.message]||'Operacja przerwana. Sprawdź stan portfela; szczegóły prywatne nie są zapisywane w logach.')+(e?.safeReason==='RPC_URL_MISSING'?' Sesja portfela nie przekazała adresu RPC dla tej sieci.':''));}finally{busy=false;render();}}
$('connect').onclick=()=>action(async()=>{
 status('Oczekiwanie na odpowiedź portfela. Sprawdź aplikację na telefonie.');
 if(session)session.disconnect();
 let provider;
 if($('provider').value==='injected'){provider=window.ethereum;if(!provider)throw new Error('NO_PROVIDER');}
 else if($('provider').value==='coinbase')provider=createCoinbaseWalletSDK({appName:'Investment Strategy Lab',appChainIds:[1,8453],preference:{options:'eoaOnly'}}).getProvider();
 else provider=createBaseAccountSDK({appName:'Investment Strategy Lab',appChainIds:[1,8453],preference:{telemetry:false},subAccounts:{creation:'manual',defaultAccount:'universal',funding:'manual'}}).getProvider();
 session=new TransferSession(provider,config.policy,config.accounts,config.policy?createReadOnlyRpc(config.policy.chainId):provider);
 for(const event of ['accountsChanged','chainChanged','disconnect'])provider.on?.(event,()=>{render();status('Zmieniło się konto lub połączenie. Podgląd został unieważniony.');});
 const account=await session.connect();$('account').textContent=`Połączono ${account.slice(0,6)}…${account.slice(-4)}`;
 status(config.policy?'Portfel podłączony. Wpisz kwotę i przygotuj podgląd.':'Portfel podłączony. Tryb wyłącznie podłączenia — transfer pozostaje zablokowany.');
});
$('switch-network').onclick=()=>action(async()=>{status('Oczekiwanie na potwierdzenie zmiany sieci w aplikacji portfela.');await session.switchToPolicyChain();$('account').textContent=`Połączono ${session.account.slice(0,6)}…${session.account.slice(-4)}`;status('Sieć zgodna z konfiguracją. Wpisz kwotę i przygotuj podgląd.');});
$('preview').onclick=()=>action(async()=>{
 status('Sprawdzanie sald i opłaty w wybranej sieci…');
 $('confirm').checked=false;const r=await session.prepare($('amount').value.trim());
 const rows=[['Sieć',r.chainId===8453?'Base (8453)':'Ethereum (1)'],['Odbiorca',r.recipient],['Kwota',`${r.amount} ${r.asset}`],['Limit kosztu wykonania',`${r.executionFeeUpperWei} wei`],['Ważność podglądu','60 sekund']];
 $('review').replaceChildren(...rows.flatMap(([label,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;return[dt,dd];}));
 $('review').hidden=false;$('empty').hidden=true;status('Podgląd gotowy. Sprawdź odbiorcę i sieć przed otwarciem portfela.');
});
$('confirm').onchange=render;
$('amount').oninput=()=>{if(session?.state==='prepared'){session.prepared=null;session.state='connected';render();}};
$('send').onclick=()=>action(async()=>{await session.submit($('confirm').checked);status('Portfel zwrócił identyfikator transakcji. Oczekuje na potwierdzenie; uznanie wpłaty przez Coinbase nie zostało sprawdzone.');});
$('receipt').onclick=()=>action(async()=>{const r=await session.checkReceipt();status(({PENDING:'Transakcja oczekuje na włączenie do bloku.',REVERTED:'Transakcja odrzucona przez sieć. Opłata mogła zostać pobrana.',INCLUDED_NOT_FINALIZED:'Transakcja w bloku; oczekuje na finalizację.',FINALIZED_ONCHAIN:'Transfer potwierdzony i sfinalizowany w sieci. Uznanie wpłaty przez Coinbase wymaga osobnej weryfikacji.'})[r.status]);});
try{const response=await fetch('/session',{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw new Error();config=await response.json();$('mode').textContent=config.policy?'Transfer z potwierdzeniem użytkownika':'Tylko podłączenie';if(config.policy){$('asset').textContent=config.policy.asset;$('limits').textContent=`Sieć ${config.policy.chainId===8453?'Base':'Ethereum'} · maksymalnie ${config.policy.maxAmount} ${config.policy.asset}`;}status(config.policy?'Konfiguracja dostępna. Podłącz zatwierdzone konto portfela.':'Tryb podłączenia. Transfer wymaga potwierdzonego adresu wpłaty Coinbase i prywatnej konfiguracji limitów.');render();}catch{status('Nie można wczytać lokalnej konfiguracji. Uruchom panel przez lokalny serwer.');}
