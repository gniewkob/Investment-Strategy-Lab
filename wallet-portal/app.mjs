import {createBaseAccountSDK} from '@base-org/account';
import {TransferSession} from './transfer.mjs';
import {createReadOnlyRpc} from './read-rpc.mjs';
const $=id=>document.getElementById(id);
let config,session,provider,connecting=false,busy=false,receiptTimer,receiptChecks=0,receiptState;
const text={PREFLIGHT_FAILED:'Sprawdzenie przed podpisem nie powiodło się. Żądanie wysyłki nie zostało przekazane do portfela. Przygotuj nowy podgląd.',BALANCE_RPC_UNAVAILABLE:'Portfel nie udostępnił odczytu ETH w wybranej sieci. Podpis zablokowany.',TOKEN_RPC_UNAVAILABLE:'Portfel nie udostępnił odczytu cbBTC. Podpis zablokowany.',GAS_ESTIMATE_UNAVAILABLE:'Nie udało się oszacować gas dla transferu. Podpis zablokowany.',GAS_PRICE_UNAVAILABLE:'Nie udało się odczytać ceny gas. Podpis zablokowany.',NETWORK_SWITCH_FAILED:'Portfel nie przełączył sieci. Wybierz Base w aplikacji portfela i podłącz ponownie.',UNEXPECTED_ACCOUNT:'Wybrano inne konto niż zatwierdzone przez operatora.',WRONG_CHAIN:'Zmień sieć w portfelu na wskazaną w konfiguracji, a następnie podłącz ponownie.',NO_GAS:'Brak ETH na opłatę sieciową. Transfer zablokowany.',INSUFFICIENT_GAS_BALANCE:'Za mało ETH na kwotę i szacowaną opłatę.',INSUFFICIENT_TOKEN_BALANCE:'Za małe saldo tokena.',POLICY_REQUIRED:'Tryb podłączenia: brak konfiguracji transferu.',POLICY_EXPIRED:'Konfiguracja wygasła. Operator musi ponownie sprawdzić adres docelowy.',AMOUNT_CAP_EXCEEDED:'Kwota przekracza limit operatora.',EXECUTION_FEE_CAP_EXCEEDED:'Opłata wykonania przekracza limit.',USER_REJECTED:'Podpis anulowany. Niczego automatycznie nie ponawiamy.',SEND_STATUS_UNKNOWN:'Wynik wysyłki jest nieznany. Sprawdź historię w portfelu przed jakąkolwiek kolejną próbą. Panel jest zablokowany.',REVIEW_EXPIRED:'Podgląd wygasł. Przygotuj go ponownie.',FEE_CHANGED_REVIEW_AGAIN:'Aktualne wymagania opłaty przekraczają limit podglądu. Przygotuj nowy podgląd. Prośba nie trafiła do portfela.',NO_PROVIDER:'Nie znaleziono rozszerzenia portfela. Otwórz panel w przeglądarce z właściwym portfelem.',IDENTITY_CHANGED:'Konto lub sieć zmieniły się. Podłącz ponownie.',ACCOUNT_CHANGED:'Konto zmieniło się. Podłącz ponownie.',INVALID_AMOUNT:'Wpisz dodatnią kwotę dziesiętną bez notacji wykładniczej.',EXCESS_PRECISION:'Kwota ma zbyt wiele miejsc dziesiętnych.'};
function status(message){$('status').textContent=message;}
function eth(wei){const n=BigInt(wei),fraction=(n%10n**18n).toString().padStart(18,'0').replace(/0+$/,'');return `${n/10n**18n}${fraction?'.'+fraction:''} ETH`;}
function render(){
 const state=session?.state,locked=['submitting','submitted','unknown'].includes(state);
 if(state==='disconnected')$('connection').open=true;
 const expired=state==='prepared'&&Date.now()-session.prepared.reviewedAt>=60000;
 const policyExpired=config?.policy&&Date.now()>=config.policy.expiresAt;
 $('connect').disabled=busy||locked||!config;
 $('reset').disabled=!provider||locked||(busy&&!connecting);
 $('switch-network').hidden=!(config?.policy&&session?.account===config.policy.from.toLowerCase()&&state==='disconnected');
 $('switch-network').disabled=busy||locked;
 $('amount').disabled=busy||!config?.policy||!['connected','prepared'].includes(state);
 $('preview').disabled=$('amount').disabled||policyExpired;
 $('confirm').disabled=busy||state!=='prepared'||expired||policyExpired;
 $('send').disabled=$('confirm').disabled||!$('confirm').checked;
 $('receipt').disabled=busy||state!=='submitted'||['FINALIZED_ONCHAIN','REVERTED'].includes(receiptState);
 if(expired||policyExpired)$('confirm').checked=false;
 $('policy-note').hidden=!policyExpired;
 $('validity').textContent=state==='prepared'?(expired?'Podgląd wygasł. Przygotuj go ponownie.':`Podgląd ważny jeszcze ${Math.ceil((60000-Date.now()+session.prepared.reviewedAt)/1000)} s`):'';
 const step=state==='submitted'?3:['submitting','unknown'].includes(state)?2:state==='prepared'?2:state==='connected'?1:0;
 for(const [i,node] of [...$('progress').children].entries()){
  node.dataset.state=i<step?'done':i===step?'current':'next';
  if(i===step)node.setAttribute('aria-current','step');else node.removeAttribute('aria-current');
 }
 $('network-state').textContent=receiptState==='FINALIZED_ONCHAIN'?'Sfinalizowany w sieci':receiptState==='REVERTED'?'Odrzucony przez sieć':receiptState==='PENDING'?'Oczekuje na włączenie do bloku':receiptState==='INCLUDED_NOT_FINALIZED'?'W bloku — oczekuje na finalizację':state==='submitted'?'Identyfikator otrzymany':state==='unknown'?'Wynik nieznany — nie ponawiaj':'Oczekuje na Twój podpis';
 $('result').hidden=!['submitted','unknown'].includes(state);
 $('tx-hash').textContent=session?.hash||'Brak identyfikatora z portfela';
 if(!['prepared','submitting','submitted','unknown'].includes(state)){$('review').hidden=true;$('empty').hidden=false;$('confirm').checked=false;}
}
async function action(fn){if(busy)return;busy=true;render();try{await fn();}catch(e){status((text[e?.message]||'Operacja przerwana. Sprawdź stan portfela; szczegóły prywatne nie są zapisywane w logach.')+(e?.safeReason==='RPC_URL_MISSING'?' Sesja portfela nie przekazała adresu RPC dla tej sieci.':''));}finally{busy=false;render();}}
$('connect').onclick=()=>action(async()=>{
 clearTimeout(receiptTimer);receiptState=null;receiptChecks=0;$('attempt').textContent='';$('account').textContent='Oczekuje na podłączenie.';
 status('Oczekiwanie na odpowiedź portfela. Sprawdź aplikację na telefonie.');
 if(session)session.disconnect();
 if(!provider){
  if(config.connection.provider==='injected'){provider=window.ethereum;if(!provider)throw new Error('NO_PROVIDER');}
  else provider=createBaseAccountSDK({appName:'Investment Strategy Lab',appChainIds:config.connection.chainIds,preference:{telemetry:false},subAccounts:{creation:'manual',defaultAccount:'universal',funding:'manual'}}).getProvider();
 }
 // Reuse the wallet's existing approval; connect still verifies its actual address.
 // Clearing this app session is an explicit reset action, never a side effect of reconnecting.
 session=new TransferSession(provider,config.policy,config.accounts,config.policy?createReadOnlyRpc(config.policy.chainId):provider);
 session.onAttempt=attempt=>{
  const labels={preflight:'Sprawdzanie przed podpisem — żądanie wysyłki jeszcze niewysłane.',wallet_confirmation:'Żądanie przekazane do portfela — sprawdź potwierdzenie w telefonie.',broadcast_hash_received:'Portfel zwrócił identyfikator — pozostaje sprawdzić potwierdzenie w sieci.',preflight_failed:'Błąd przed podpisem — nie przekazano żądania wysyłki.',wallet_rejected:'Portfel zgłosił odmowę potwierdzenia.',outcome_unknown:'Brak potwierdzonego wyniku żądania portfela — ponowienie zablokowane.'};
  $('attempt').textContent=labels[attempt.phase]+(attempt.diagnostic?` Diagnostyka: ${attempt.diagnostic.category}${attempt.diagnostic.code!==null?` (${attempt.diagnostic.code})`:''}.`:'');
  render();
  if(attempt.phase==='wallet_confirmation')status('Otwórz aplikację portfela na telefonie. Oczekiwanie na Twoją decyzję; nie ponawiaj żądania.');
 };
 for(const event of ['accountsChanged','chainChanged','disconnect'])provider.on?.(event,()=>{render();status('Zmieniło się konto lub połączenie. Podgląd został unieważniony.');});
 connecting=true;render();
 let account;
 try{account=await session.connect();}
 catch(e){
  if(e?.message==='UNEXPECTED_ACCOUNT')$('account').textContent=`Odrzucone konto: ${session.account}. Oczekiwane: ${config.connection.account}.`;
  throw e;
 }finally{connecting=false;}
 $('account').textContent=`Połączono ${config.connection.label}: ${account}`;
 $('connection').open=false;
 status(config.policy&&Date.now()>=config.policy.expiresAt?text.POLICY_EXPIRED:config.policy?'Portfel podłączony. Wpisz kwotę i przygotuj podgląd.':'Portfel podłączony. Tryb wyłącznie podłączenia — transfer pozostaje zablokowany.');
});
$('reset').onclick=async()=>{
 if(!provider||['submitting','submitted','unknown'].includes(session?.state)||(busy&&!connecting))return;
 $('reset').disabled=true;
 try{await provider.disconnect?.();location.reload();}
 catch{status('Nie udało się wyczyścić sesji. Zamknij okno logowania i odśwież panel.');}
};
$('switch-network').onclick=()=>action(async()=>{status('Oczekiwanie na potwierdzenie zmiany sieci w aplikacji portfela.');await session.switchToPolicyChain();$('account').textContent=`Połączono ${session.account.slice(0,6)}…${session.account.slice(-4)}`;status('Sieć zgodna z konfiguracją. Wpisz kwotę i przygotuj podgląd.');});
$('preview').onclick=()=>action(async()=>{
 status('Sprawdzanie sald i opłaty w wybranej sieci…');
 $('confirm').checked=false;const r=await session.prepare($('amount').value.trim());
 const rows=[['Kwota',`${r.amount} ${r.asset}`],['Wartość w złotych','PLN: brak zweryfikowanej wyceny'],['Z portfela',`${session.account.slice(0,6)}…${session.account.slice(-4)}`],['Do Coinbase — adres wskazany przez Ciebie',r.recipient],['Sieć',r.chainId===8453?'Base (8453)':'Ethereum (1)'],['Górne oszacowanie kosztu wykonania',eth(r.executionFeeUpperWei)],['Pełna opłata sieciowa','Do sprawdzenia w portfelu przed zatwierdzeniem']];
 $('review').replaceChildren(...rows.flatMap(([label,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;return[dt,dd];}));
 $('review').hidden=false;$('empty').hidden=true;status('Podgląd gotowy. Sprawdź odbiorcę i sieć przed otwarciem portfela.');
});
$('confirm').onchange=render;
$('amount').oninput=()=>{if(session?.state==='prepared'){session.prepared=null;session.state='connected';render();}};
$('send').onclick=()=>action(async()=>{await session.submit($('confirm').checked);status('Portfel zwrócił identyfikator. Sprawdzamy potwierdzenie w sieci.');receiptChecks=0;receiptTimer=setTimeout(checkReceipt,0);});
async function checkReceipt(){
 clearTimeout(receiptTimer);
 if(busy||session?.state!=='submitted')return;
 busy=true;render();receiptChecks++;
 try{
  const r=await session.checkReceipt();receiptState=r.status;
  status(({PENDING:'Transakcja oczekuje na włączenie do bloku.',REVERTED:'Transakcja odrzucona przez sieć. Opłata mogła zostać pobrana.',INCLUDED_NOT_FINALIZED:'Transakcja w bloku; oczekuje na finalizację.',FINALIZED_ONCHAIN:'Transfer potwierdzony i sfinalizowany w sieci. Uznanie wpłaty przez Coinbase wymaga osobnej weryfikacji.'})[r.status]);
  if(['PENDING','INCLUDED_NOT_FINALIZED'].includes(r.status)){
   if(receiptChecks<6)receiptTimer=setTimeout(checkReceipt,10000);
   else status('Automatyczne sprawdzanie zakończone po sześciu odczytach. Potwierdzenie nadal oczekuje. Możesz sprawdzić ponownie przyciskiem poniżej.');
  }
 }catch{status('Automatyczne sprawdzanie zatrzymane: brak wiarygodnej odpowiedzi. Transferu nie ponawiamy. Możesz sprawdzić potwierdzenie ponownie.');}
 finally{busy=false;render();}
}
$('receipt').onclick=()=>{receiptChecks=5;return checkReceipt();};
setInterval(render,1000);
try{const response=await fetch('/session',{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw new Error();config=await response.json();if(!config.connection||config.accounts.length!==1||config.accounts[0]!==config.connection.account||!['base','injected'].includes(config.connection.provider))throw new Error();$('expected-label').textContent=config.connection.label;$('expected-account').textContent=config.connection.account;$('connector-name').textContent=config.connection.provider==='base'?'Połączenie: Base Account':'Połączenie: rozszerzenie portfela';if(!config.policy){$('portal-title').textContent='Połącz jeden właściwy portfel.';$('portal-intro').textContent='Sprawdzimy adres zwrócony przez portfel. Inne konto zostanie odrzucone. Transfery są na razie wyłączone.';$('transfer-panel').hidden=true;$('progress').hidden=true;$('portal-grid').classList.add('connection-only');}$('mode').textContent=config.policy?'Transfer z potwierdzeniem użytkownika':'Tylko podłączenie';if(config.policy){$('asset').textContent=config.policy.asset;$('limits').textContent=`Sieć ${config.policy.chainId===8453?'Base':'Ethereum'} · maksymalnie ${config.policy.maxAmount} ${config.policy.asset}`;}status(config.policy&&Date.now()>=config.policy.expiresAt?text.POLICY_EXPIRED:config.policy?'Konfiguracja dostępna. Podłącz zatwierdzone konto portfela.':'Tryb podłączenia. Transfer wymaga potwierdzonego adresu wpłaty Coinbase i prywatnej konfiguracji limitów.');render();}catch{config=null;render();status('Nie można wczytać lokalnej konfiguracji. Uruchom panel przez lokalny serwer.');}
