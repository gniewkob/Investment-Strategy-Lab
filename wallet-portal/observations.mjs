// Read-only local observations. No wallet calls, credentials, transaction requests or retries.
const labels={FINALIZED:'Sfinalizowany w sieci',INCLUDED:'W bloku — oczekuje na finalizację',PENDING:'Oczekuje na blok',REVERTED:'Odrzucony w sieci',UNAVAILABLE:'Brak wiarygodnego odczytu'};
const stateLabel={FRESH:'Odczyt aktualny',STALE:'Odczyt wymaga odświeżenia',UNAVAILABLE:'Dane niedostępne'};
function node(tag,text,className){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;}
function when(value){return value?new Intl.DateTimeFormat('pl-PL',{dateStyle:'short',timeStyle:'medium',timeZone:'Europe/Warsaw'}).format(new Date(value))+' (Warszawa)':'brak czasu odczytu';}
function table(head,rows){const t=node('table'),thead=node('thead'),tr=node('tr');for(const h of head)tr.append(node('th',h));thead.append(tr);t.append(thead);const b=node('tbody');for(const row of rows){const r=node('tr');for(const v of row)r.append(node('td',v));b.append(r);}t.append(b);return t;}
export function mountObservations({root,getHash,creditNode,onAvailable=()=>{}}){
 let data=null,reading=false;
 const status=node('p','Wczytywanie prywatnych odczytów…','note');status.id='observation-status';status.setAttribute('role','status');
 const button=node('button','Wczytaj nowszy odczyt','secondary');button.id='refresh-observations';
 const exchange=node('section'),wallet=node('section'),history=node('section');
 exchange.id='exchange-observation';wallet.id='wallet-observation';history.id='transfer-history';
 const grid=node('div',undefined,'read-grid');grid.append(exchange,wallet);
 root.replaceChildren(node('h2','Salda i historia — tylko odczyt'),status,button,
  node('p','Panel co 30 sekund wczytuje najnowszy lokalny zrzut. Sam nie loguje się do Coinbase ani nie odświeża konektora.','note'),grid,history);
 function syncCredit(){
  const row=data?.transfers?.find(t=>t.tx_hash===getHash());
  if(!row){creditNode.textContent='Niezweryfikowane';return;}
  if(row.credit==='BALANCE_PRESENT_NOT_DEPOSIT_PROOF')creditNode.textContent=`Dostępne saldo ${row.credit_asset} zaobserwowane. ${row.credit_link==='OPERATOR_ASSERTED'?'Powiązanie wpłaty potwierdzone ręcznie.':'Brak dowodu powiązania z tą wpłatą.'}`;
  else creditNode.textContent=row.credit==='NOT_OBSERVED'?'Nie zaobserwowano odpowiedniego dostępnego salda.':'Brak świeżego odczytu Coinbase.';
 }
 function render(){
  exchange.replaceChildren();wallet.replaceChildren();history.replaceChildren();
  if(data?.status!=='AVAILABLE'){
   status.textContent=data?.status==='NOT_CONFIGURED'?'Nie skonfigurowano prywatnych odczytów sald.':'Odczyt niedostępny. Poprzednie salda zostały ukryte.';
   syncCredit();return;
  }
  status.textContent=`Zrzut: ${when(data.generated_at_utc)}. Łączna wycena portfela i giełdy: niedostępna. Zdarzenia nie są dodawane do sald.`;
  const e=data.exchange;
  exchange.append(node('h3','Coinbase'),node('p',stateLabel[e.status],'badge'),
   node('p',`Pobrano z konektora: ${when(e.captured_at_utc)}. Coinbase nie udostępnia źródłowego czasu tych danych.`,`note`));
  if(e.status==='FRESH'){
   const nonzero=e.balances.filter(r=>/[1-9]/.test(r.available)||/[1-9]/.test(r.hold));
   exchange.append(table(['Aktywo','Dostępne','Zablokowane'],nonzero.map(r=>[r.asset,r.available,r.hold])),
    node('p',`Ukryto ${e.balances.length-nonzero.length} pozycji z potwierdzonym zerowym saldem.`,`note`),
    node('p',`Wartość pozycji giełdowych: ${e.holdings_usd} USD; w tym staking: ${e.staked_usd} USD. Sald dostępnych nie dodajemy do tej wartości.`,`note`));
  }else exchange.append(node('p','Salda ukryte do czasu uzyskania świeżego odczytu.','note'));
  exchange.append(node('p',`Zakres: ${e.portfolio_count??'nieustalona liczba'} portfeli ze zrzutu. Pochodzenie zrzutu deklaruje operator; serwer nie uwierzytelnia Coinbase. Historia wpłat z konektora: niedostępna.`,'note'));
  wallet.append(node('h3','Portfel na blockchainie'));
  for(const w of data.wallets){
   wallet.append(node('h4',w.chain_id===8453?'Base':'Ethereum'),node('p',stateLabel[w.status],'badge'),
    node('p',`Odczyt: ${when(w.retrieved_at_utc)}. Blok ${w.block_number??'nieznany'}; czas bloku: ${when(w.block_time_utc)}.`,'note'));
   if(w.status==='FRESH')wallet.append(table(['Aktywo','Ilość'],w.positions.map(p=>[p.asset,p.quantity])));
   else wallet.append(node('p','Salda ukryte do czasu uzyskania świeżego odczytu.','note'));
  }
  history.append(node('h3','Zarejestrowane transfery'),node('p','To historia wskazanych przypadków, nie pełna historia portfela ani giełdy. Kwoty zdarzeń nie zwiększają sald.','note'));
  if(!data.transfers.length)history.append(node('p','Brak zarejestrowanych przypadków.','note'));
  for(const t of data.transfers){
   const item=node('article',undefined,'history-case');
   item.append(node('h4',`${t.amount} ${t.asset} · ${t.chain_id===8453?'Base':'Ethereum'}`),node('p',labels[t.network]),
    node('p',`Czas bloku: ${when(t.block_time_utc)}; sprawdzono: ${when(t.verified_at_utc)}.`,'note'),
    node('p',`Identyfikator: ${t.tx_hash}`,'note'),node('p',`Odbiorca: ${t.recipient}`,'note'));
   item.append(node('p',t.credit==='BALANCE_PRESENT_NOT_DEPOSIT_PROOF'?`Dostępne saldo ${t.credit_asset} zaobserwowane w Coinbase.`:t.credit==='NOT_OBSERVED'?'Nie zaobserwowano odpowiedniego dostępnego salda Coinbase.':'Saldo Coinbase: brak świeżego odczytu.'));
   item.append(node('p',t.credit_link==='OPERATOR_ASSERTED'?'Powiązanie wpłaty: potwierdzone ręcznie przez operatora, bez identyfikatora wpłaty z API.':'Powiązanie wpłaty: niepotwierdzone.','note'));
   if(t.temporal_overlap)item.append(node('p','Czasy sald mogą obejmować tę samą kwotę w dwóch miejscach. Nie obliczamy wspólnej sumy.','note warning'));
   history.append(item);
  }
  syncCredit();onAvailable(data);
 }
 async function refresh(){
  if(reading)return;reading=true;button.disabled=true;
  try{
   const r=await fetch('/observations',{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(5000)});
   if(!r.ok)throw new Error();const raw=await r.text();if(raw.length>1000000)throw new Error();
   data=JSON.parse(raw);render();
  }catch{data=null;render();}
  finally{reading=false;button.disabled=false;}
 }
 button.onclick=refresh;void refresh();const timer=setInterval(refresh,30000);
 return {syncCredit,refresh,stop:()=>clearInterval(timer)};
}
