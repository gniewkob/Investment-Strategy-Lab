"""Private connector-capture + public read-only chain evidence for the local panel.

No credentials, execution endpoints or Coinbase authentication in this process.
Capture provenance and deposit links are operator asserted, never API deposit proof.
"""
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import re
from uuid import uuid4
from scripts.operational_read_only import (normalize_exchange, observe_wallets, rpc_read,
    read_private, write_private, TRANSFER_TOPIC)
from scripts.private_wallet_chain_monitor import _private_config

MODE='PRIVATE_PANEL_OBSERVATION_V1'
ADDRESS=re.compile(r'0x[0-9a-fA-F]{40}\Z')
HASH=re.compile(r'0x[0-9a-fA-F]{64}\Z')
ASSET=re.compile(r'[A-Z0-9]{2,12}\Z')
TOKEN='0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf'

class ObservationError(ValueError):pass

def require(ok):
    if not ok:raise ObservationError('OBSERVATION_REJECTED')

def stamp(value,now):
    require(isinstance(value,str))
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(t.tzinfo is not None and t.utcoffset()==timedelta(0) and t<=now+timedelta(seconds=5))
    return t

def number(value):
    require(isinstance(value,str) and len(value)<=80 and re.fullmatch(r'(0|[1-9][0-9]*)(\.[0-9]+)?',value))
    require(Decimal(value).is_finite())
    return value

def integer(value):
    require(type(value) is int and 0<=value<2**64)
    return value

def registered_cases(data,entries,now):
    require(isinstance(data,dict) and set(data)=={'mode','cases'} and data['mode']=='PRIVATE_REGISTERED_TRANSFERS_V1')
    rows=data['cases'];require(isinstance(rows,list) and len(rows)<=20)
    seen=set()
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'chain_id','tx_hash','asset','amount','recipient','operator_credit_link','operator_asserted_at_utc'})
        require(type(row['chain_id']) is int and row['chain_id'] in {e[0] for e in entries})
        require(isinstance(row['tx_hash'],str) and HASH.fullmatch(row['tx_hash']))
        key=(row['chain_id'],row['tx_hash'].lower());require(key not in seen);seen.add(key)
        require(row['asset'] in ('ETH','cbBTC') and type(row['operator_credit_link']) is bool)
        require(row['asset']!='cbBTC' or TOKEN in next(e[3] for e in entries if e[0]==row['chain_id']))
        precision=8 if row['asset']=='cbBTC' else 18
        amount=Decimal(number(row['amount']));require(amount>0 and amount*10**precision==int(amount*10**precision) and amount*10**precision<2**256)
        to=row['recipient'];require(isinstance(to,str) and ADDRESS.fullmatch(to))
        require(to.lower() not in (entries[0][1],TOKEN,'0x'+'0'*40))
        stamp(row['operator_asserted_at_utc'],now)
    return rows

def verify_case(row,sender,rpc,now):
    c=row['chain_id'];h=row['tx_hash'].lower()
    out={**row,'tx_hash':h,'recipient':row['recipient'].lower(),'network':'UNAVAILABLE',
         'block_number':None,'block_time_utc':None,'verified_at_utc':None}
    try:
        require(int(rpc(c,'eth_chainId',[]),16)==c)
        r=rpc(c,'eth_getTransactionReceipt',[h])
        if r is None:return {**out,'network':'PENDING','verified_at_utc':now.isoformat()}
        require(isinstance(r,dict) and r['transactionHash'].lower()==h)
        block=int(r['blockNumber'],16);require(HASH.fullmatch(r['blockHash']))
        b=rpc(c,'eth_getBlockByNumber',[r['blockNumber'],False])
        require(int(b['number'],16)==block and b['hash'].lower()==r['blockHash'].lower())
        at=datetime.fromtimestamp(int(b['timestamp'],16),timezone.utc);require(at<=now+timedelta(seconds=5))
        out.update(block_number=block,block_time_utc=at.isoformat(),verified_at_utc=now.isoformat())
        if r['status']=='0x0':return {**out,'network':'REVERTED'}
        require(r['status']=='0x1')
        units=int(Decimal(row['amount'])*10**(8 if row['asset']=='cbBTC' else 18))
        if row['asset']=='cbBTC':
            matches=[l for l in r['logs'] if l.get('address','').lower()==TOKEN and len(l.get('topics',[]))==3
                and l['topics'][0].lower()==TRANSFER_TOPIC and l['topics'][1].lower()=='0x'+sender[2:].zfill(64)
                and l['topics'][2].lower()=='0x'+out['recipient'][2:].zfill(64) and int(l['data'],16)==units]
            require(len(matches)==1)
        else:
            tx=rpc(c,'eth_getTransactionByHash',[h])
            require(tx['hash'].lower()==h and tx['from'].lower()==sender and tx['to'].lower()==out['recipient']
                and int(tx['value'],16)==units and int(tx['blockNumber'],16)==block)
        f=rpc(c,'eth_getBlockByNumber',['finalized',False])
        require(HASH.fullmatch(f['hash']))
        return {**out,'network':'FINALIZED' if int(f['number'],16)>=block else 'INCLUDED'}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        # No upstream messages, partial proof, fabricated zero, or stale-success fallback.
        return {**out,'network':'UNAVAILABLE','block_number':None,'block_time_utc':None,'verified_at_utc':None}

def build_snapshot(watch,capture,cases,now,*,rpc=rpc_read):
    entries=_private_config(watch);require(len({e[1] for e in entries})==1)
    rows=registered_cases(cases,entries,now)
    exchange={'captured_at_utc':None,'balances':[],'holdings_usd':None,'staked_usd':None,'portfolio_count':None}
    try:
        e=normalize_exchange(capture,now)
        exchange={'captured_at_utc':e['captured_at_utc'],
            'balances':[{'asset':a,**v} for a,v in sorted(e['trading_balances'].items())],
            'holdings_usd':e['reported_total_usd'],'staked_usd':e['staked_value_usd'],'portfolio_count':e['portfolio_count']}
    except (ValueError,TypeError,KeyError,AttributeError):pass
    wallet={'retrieved_at_utc':None,'positions':[],'block_number':None,'block_time_utc':None,'chain_id':None}
    # One source identity, possibly on both configured EVM networks.
    wallets=[]
    for chain,addr,label,tokens in entries:
        one={'mode':'PRIVATE_WALLET_READ_ONLY','watch':[{'chain_id':chain,'address':addr,'label':label,'verified_token_contracts':sorted(tokens)}]}
        try:
            w=observe_wallets(one,now,rpc=rpc)['wallets'][0]
            wallets.append({'retrieved_at_utc':w['retrieved_at_utc'],'positions':w['positions'],
                'block_number':w['source_block_number'],'block_time_utc':w['source_block_timestamp_utc'],'chain_id':chain})
        except (ValueError,TypeError,KeyError,AttributeError):
            wallets.append({**wallet,'chain_id':chain})
    return {'mode':MODE,'clock_mode':'LIVE_RETRIEVAL','expected_account':entries[0][1],
        'generated_at_utc':now.isoformat(),'exchange':exchange,'wallets':wallets,
        'transfers':[verify_case(r,entries[0][1],rpc,now) for r in rows]}

def project(snapshot,expected_accounts,now):
    try:return _project(snapshot,expected_accounts,now)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        raise ObservationError('OBSERVATION_REJECTED') from None

def _project(s,expected,now):
    require(set(s)=={'mode','clock_mode','expected_account','generated_at_utc','exchange','wallets','transfers'})
    require(s['mode']==MODE and s['clock_mode']=='LIVE_RETRIEVAL' and len(expected)==1 and s['expected_account']==expected[0])
    stamp(s['generated_at_utc'],now)
    e=s['exchange'];require(set(e)=={'captured_at_utc','balances','holdings_usd','staked_usd','portfolio_count'})
    require(isinstance(e['balances'],list) and len(e['balances'])<=500)
    seen=set()
    for row in e['balances']:
        require(set(row)=={'asset','available','hold'} and ASSET.fullmatch(row['asset']) and row['asset'] not in seen);seen.add(row['asset'])
        number(row['available']);number(row['hold'])
    if e['holdings_usd'] is not None:number(e['holdings_usd']);number(e['staked_usd']);integer(e['portfolio_count'])
    efresh=e['captured_at_utc'] is not None and now-stamp(e['captured_at_utc'],now)<=timedelta(minutes=15)
    exchange={**e,'status':'FRESH' if efresh else 'STALE' if e['captured_at_utc'] else 'UNAVAILABLE',
        'balances':e['balances'] if efresh else [],'holdings_usd':e['holdings_usd'] if efresh else None,
        'staked_usd':e['staked_usd'] if efresh else None,'source_as_of_utc':None,
        'provenance':'OPERATOR_ASSERTED_CAPTURE_OF_AUTHORIZED_CONNECTOR_READS','scope':'CAPTURED_PORTFOLIOS_ONLY',
        'deposit_history_available':False,'cli_authenticated_coinbase':False}
    require(isinstance(s['wallets'],list) and 1<=len(s['wallets'])<=2)
    wallets=[];chains=set()
    for w in s['wallets']:
        require(set(w)=={'retrieved_at_utc','positions','block_number','block_time_utc','chain_id'})
        require(type(w['chain_id']) is int and w['chain_id'] in (1,8453) and w['chain_id'] not in chains);chains.add(w['chain_id'])
        require(isinstance(w['positions'],list) and len(w['positions'])<=2)
        assets=set()
        for p in w['positions']:
            require(set(p)=={'asset','contract','quantity'} and p['asset'] in ('ETH','cbBTC') and p['asset'] not in assets);assets.add(p['asset'])
            require(p['contract']==('NATIVE' if p['asset']=='ETH' else TOKEN));number(p['quantity'])
        fresh=False
        if w['retrieved_at_utc'] is not None:
            integer(w['block_number'])
            fresh=now-stamp(w['retrieved_at_utc'],now)<=timedelta(minutes=15) and now-stamp(w['block_time_utc'],now)<=timedelta(minutes=30)
        wallets.append({**w,'status':'FRESH' if fresh else 'STALE' if w['retrieved_at_utc'] else 'UNAVAILABLE',
                        'positions':w['positions'] if fresh else []})
    require(isinstance(s['transfers'],list) and len(s['transfers'])<=20)
    transfers=[];seen=set();overlap=False
    for t in s['transfers']:
        require(set(t)=={'chain_id','tx_hash','asset','amount','recipient','operator_credit_link','operator_asserted_at_utc',
                        'network','block_number','block_time_utc','verified_at_utc'})
        registered_cases({'mode':'PRIVATE_REGISTERED_TRANSFERS_V1','cases':[{k:v for k,v in t.items() if k in
             {'chain_id','tx_hash','asset','amount','recipient','operator_credit_link','operator_asserted_at_utc'}}]},
             [(c,s['expected_account'],'source',{TOKEN}) for c in chains],now)
        key=(t['chain_id'],t['tx_hash']);require(key not in seen);seen.add(key)
        require(t['network'] in ('FINALIZED','INCLUDED','PENDING','REVERTED','UNAVAILABLE'))
        if t['network'] in ('FINALIZED','INCLUDED','REVERTED'):
            require(t['verified_at_utc'] is not None and t['block_number'] is not None and t['block_time_utc'] is not None)
        if t['verified_at_utc']:stamp(t['verified_at_utc'],now)
        if t['block_number'] is not None:integer(t['block_number']);stamp(t['block_time_utc'],now)
        asset='BTC' if t['asset']=='cbBTC' else 'ETH'
        balance=next((r for r in exchange['balances'] if r['asset']==asset),None)
        present=balance is not None and Decimal(balance['available'])>=Decimal(t['amount'])
        linked=t['operator_credit_link']
        credit='BALANCE_PRESENT_NOT_DEPOSIT_PROOF' if efresh and present else 'NOT_OBSERVED' if efresh else 'UNAVAILABLE'
        w=next(w for w in wallets if w['chain_id']==t['chain_id'])
        temporal=bool(linked and present and (w['status']!='FRESH' or t['block_number'] is None or w['block_number']<t['block_number']))
        overlap|=temporal
        transfers.append({**t,'credit':credit,'credit_asset':asset,'credit_link':'OPERATOR_ASSERTED' if linked else 'NONE','temporal_overlap':temporal})
    return {'status':'AVAILABLE','generated_at_utc':s['generated_at_utc'],'exchange':exchange,'wallets':wallets,
        'wallet':wallets[0], 'transfers':transfers,'combined_total_usd':None,'event_amounts_added_to_balances':False,
        'temporal_overlap':overlap,'full_history':False,'automatic_coinbase_refresh':False}

def load(path,expected,now):return project(read_private(path),expected,now)

def publish(directory,snapshot):
    directory=Path(directory);latest=directory/'latest.json'
    if os.path.lexists(latest):
        try:
            old=read_private(latest);require(old.get('mode')==MODE and old.get('expected_account')==snapshot['expected_account'])
        except ValueError:raise ObservationError('OBSERVATION_REJECTED') from None
    name='observation-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'-'+uuid4().hex+'.json'
    write_private(directory/name,snapshot)
    temp=directory/('.latest-'+uuid4().hex+'.json')
    try:
        write_private(temp,snapshot);os.replace(temp,latest)
    finally:
        if temp.exists():temp.unlink()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--watchlist',type=Path,required=True);p.add_argument('--exchange-capture',type=Path,required=True)
    p.add_argument('--registered-transfers',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    try:
        now=datetime.now(timezone.utc)
        s=build_snapshot(read_private(args.watchlist),read_private(args.exchange_capture),read_private(args.registered_transfers),now)
        project(s,[s['expected_account']],datetime.now(timezone.utc));publish(args.output_dir,s)
        print('PRIVATE_PANEL_OBSERVATION_PUBLISHED; credentials=0; financial_operations=0; combined_total=unknown')
    except (ValueError,TypeError,KeyError,OSError):p.exit(2,'Observation unavailable; verify private inputs and source freshness.\n')
if __name__=='__main__':main()
