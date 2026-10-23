"""Private read-only Coinbase fills and statement import; no credentials or writes.

reader, when used, is an existing authorized host callback. It receives only
coinbase_orders_fills. This module cannot add permissions to a hosted connector.
CSV is a recognized input dialect, not an assertion that every Coinbase report
has that schema. Notes, account IDs and preambles never reach normalized output.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import csv
from io import StringIO
import json
import os
import re
import stat

from scripts.read_only_portfolio_monitor import _when

MAX_BYTES = 2_000_000
MAX_RECORDS = 5000
MAX_PAGES = 50
ASSET = re.compile(r'[A-Z0-9]{2,12}\Z')
PRODUCT = re.compile(r'[A-Z0-9]{2,12}-[A-Z0-9]{2,12}\Z')
REQUIRED_COLUMNS = {'ID','Timestamp','Transaction Type','Asset','Quantity Transacted'}
CATEGORIES = {'Receive':'observed_inflow', 'Deposit':'observed_inflow',
    'Send':'observed_outflow','Withdrawal':'observed_outflow',
    'Buy':'trade','Sell':'trade','Advanced Trade Buy':'trade','Advanced Trade Sell':'trade',
    'Convert':'conversion','Staking Income':'reward','Rewards Income':'reward'}


class HistoryError(ValueError):
    pass


def _object(value):
    if not isinstance(value,dict): raise HistoryError('HISTORY_OBJECT_REQUIRED')
    return value


def _time(value):
    try: return _when(value)
    except ValueError: raise HistoryError('HISTORY_UTC_TIME_REQUIRED') from None


def _id(value):
    if not isinstance(value,str) or not value.strip() or len(value)>200:
        raise HistoryError('HISTORY_STABLE_ID_REQUIRED')
    return value


def _num(value, *, signed=False, positive=False):
    if value is None or isinstance(value,bool) or len(str(value))>100:
        raise HistoryError('HISTORY_NUMBER_INVALID')
    try: n=Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError):
        raise HistoryError('HISTORY_NUMBER_INVALID') from None
    if not n.is_finite() or abs(n.adjusted())>60 or (not signed and n<0) or (positive and n<=0):
        raise HistoryError('HISTORY_NUMBER_OUT_OF_RANGE')
    return n


def _window(portfolios, start, end, captured, now):
    if (not isinstance(portfolios,list) or not 1<=len(portfolios)<=100
        or any(not isinstance(p,str) or not p.strip() or len(p)>200 for p in portfolios)
        or len(set(portfolios))!=len(portfolios)):
        raise HistoryError('HISTORY_PORTFOLIO_SCOPE_INVALID')
    first,last,at=_time(start),_time(end),_time(captured)
    if not first<last<=at+timedelta(seconds=5) or at>now+timedelta(seconds=5):
        raise HistoryError('HISTORY_INTERVAL_INVALID')
    return first,last,at


def _response(page):
    page=_object(page)
    if page.get('proof_token_required') is True or 'error' in page:
        raise HistoryError('HISTORY_SOURCE_REQUIRES_UNAVAILABLE_ACCESS')
    rows=page.get('fills')
    cursor=page.get('cursor','')
    if cursor is None: cursor=''
    if (not isinstance(rows,list) or len(rows)>100 or not isinstance(cursor,str) or len(cursor)>2048):
        raise HistoryError('HISTORY_PAGE_INVALID')
    return rows,cursor


def collect_fills(reader, portfolio_ids, start, end, now):
    """Read the same bounded scope through every cursor. Never choose a write tool."""
    _window(portfolio_ids,start,end,now.isoformat(),now)
    reads=[];count=0
    for portfolio in portfolio_ids:
        cursor=None;seen=set();pages=[]
        for _ in range(MAX_PAGES):
            params={'portfolio_id':portfolio,'start':start,'end':end,'limit':100}
            if cursor: params['cursor']=cursor
            try: response=reader('coinbase_orders_fills',params)
            except Exception: raise HistoryError('HISTORY_AUTHORIZED_READ_FAILED') from None
            rows,next_cursor=_response(response)
            count+=len(rows)
            if count>MAX_RECORDS: raise HistoryError('HISTORY_RECORD_BUDGET_EXCEEDED')
            pages.append({'request_cursor':cursor,'response':response})
            if not next_cursor: break
            if next_cursor in seen: raise HistoryError('HISTORY_CURSOR_LOOP')
            seen.add(next_cursor);cursor=next_cursor
        else: raise HistoryError('HISTORY_PAGE_BUDGET_EXCEEDED')
        reads.append({'portfolio_id':portfolio,'pages':pages})
    return {'mode':'PRIVATE_COINBASE_FILLS_CAPTURE','captured_at':now.isoformat(),
            'start':start,'end':end,'portfolio_ids':list(portfolio_ids),'reads':reads}


def normalize_fills(capture, now):
    _object(capture)
    if capture.get('mode')!='PRIVATE_COINBASE_FILLS_CAPTURE':
        raise HistoryError('HISTORY_CAPTURE_MODE_REQUIRED')
    portfolios=capture.get('portfolio_ids')
    first,last,at=_window(portfolios,capture.get('start'),capture.get('end'),capture.get('captured_at'),now)
    reads=capture.get('reads')
    if not isinstance(reads,list) or len(reads)!=len(portfolios):
        raise HistoryError('HISTORY_PORTFOLIO_COVERAGE_MISSING')
    if {_object(r).get('portfolio_id') for r in reads}!=set(portfolios):
        raise HistoryError('HISTORY_PORTFOLIO_COVERAGE_MISMATCH')
    seen=set();events=[];page_count=0
    for r in reads:
        pages=r.get('pages')
        if not isinstance(pages,list) or not 1<=len(pages)<=MAX_PAGES:
            raise HistoryError('HISTORY_PAGES_REQUIRED')
        expected=None;seen_cursors=set()
        for index,p in enumerate(pages):
            _object(p)
            if p.get('request_cursor')!=expected: raise HistoryError('HISTORY_CURSOR_CHAIN_INVALID')
            rows,cursor=_response(p.get('response'))
            if bool(cursor)!=(index<len(pages)-1) or cursor and cursor in seen_cursors:
                raise HistoryError('HISTORY_PAGINATION_INCOMPLETE_OR_REPEATED')
            if cursor: seen_cursors.add(cursor)
            expected=cursor;page_count+=1
            for row in rows:
                _object(row)
                product=row.get('product_id')
                if not isinstance(product,str) or not PRODUCT.fullmatch(product) or row.get('side') not in ('BUY','SELL'):
                    raise HistoryError('HISTORY_FILL_PRODUCT_OR_SIDE_INVALID')
                trade,order=_id(row.get('trade_id')),_id(row.get('order_id'))
                key=(r['portfolio_id'],product,trade)
                if key in seen: raise HistoryError('HISTORY_DUPLICATE_FILL')
                seen.add(key)
                when=_time(row.get('trade_time'))
                if not first<=when<=last: raise HistoryError('HISTORY_FILL_OUTSIDE_REQUESTED_INTERVAL')
                if row.get('retail_portfolio_id',r['portfolio_id'])!=r['portfolio_id']:
                    raise HistoryError('HISTORY_FILL_SCOPE_MISMATCH')
                size,price=_num(row.get('size'),positive=True),_num(row.get('price'),positive=True)
                flag=row.get('size_in_quote')
                if 'size_in_quote' in row and not isinstance(flag,bool):
                    raise HistoryError('HISTORY_SIZE_UNIT_INVALID')
                base,quote=product.split('-')
                with localcontext() as ctx:
                    ctx.prec=80
                    estimate=format(size/price,'f') if flag is True else None
                commission=_num(row['commission']) if row.get('commission') is not None else None
                events.append({'event_id':sha256(json.dumps(key).encode()).hexdigest(),
                    'source_event_timestamp_utc':when.isoformat(),'product_id':product,'side':row['side'],
                    'reported_size':str(size),'reported_size_unit':quote if flag is True else base if flag is False else 'UNKNOWN',
                    'base_quantity_reported':str(size) if flag is False else None,
                    'base_quantity_estimate':estimate,'price_reported':str(price),
                    'commission_reported':str(commission) if commission is not None else None,
                    'commission_currency':None,'onchain_reconciliation_eligible':False})
                if len(events)>MAX_RECORDS: raise HistoryError('HISTORY_RECORD_BUDGET_EXCEEDED')
    return {'source':'OPERATOR_CAPTURE_OF_AUTHORIZED_COINBASE_FILLS',
        'captured_at_utc':at.isoformat(),'requested_interval_utc':[first.isoformat(),last.isoformat()],
        'portfolio_count':len(portfolios),'page_count':page_count,'pagination_chain_complete':True,
        'snapshot_completeness_certified':False,'event_count':len(events),'events':events,
        'deposit_withdrawal_history_included':False,'balances_adjusted':False,
        'commission_currency_status':'NOT_PROVIDED_BY_CONNECTOR_DO_NOT_AGGREGATE',
        'unknown_size_unit_count':sum(e['reported_size_unit']=='UNKNOWN' for e in events)}


def parse_statement(raw,now):
    """Recognize bounded CSV dialect, discard notes and account-identifying fields."""
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_BYTES:
        raise HistoryError('HISTORY_STATEMENT_SIZE_INVALID')
    try:
        records=csv.reader(StringIO(raw.decode('utf-8-sig')),strict=True)
        header=None
        for _ in range(25):
            candidate=next(records,None)
            if candidate is None: break
            if REQUIRED_COLUMNS.issubset(candidate):
                header=candidate;break
        if header is None or len(header)!=len(set(header)):
            raise HistoryError('HISTORY_STATEMENT_DIALECT_NOT_RECOGNIZED')
        events=[];seen=set();unknown=0
        for values in records:
            if not values: continue
            if len(values)!=len(header) or any(len(v)>8192 for v in values):
                raise HistoryError('HISTORY_STATEMENT_ROW_INVALID')
            row=dict(zip(header,values))
            ident=_id(row['ID'])
            if ident in seen: raise HistoryError('HISTORY_DUPLICATE_STATEMENT_ID')
            seen.add(ident)
            when=_time(row['Timestamp'])
            if when>now+timedelta(seconds=5): raise HistoryError('HISTORY_STATEMENT_FUTURE_EVENT')
            asset=row['Asset']
            if not ASSET.fullmatch(asset): raise HistoryError('HISTORY_STATEMENT_ASSET_INVALID')
            quantity=_num(row['Quantity Transacted'],signed=True)
            category=CATEGORIES.get(row['Transaction Type'],'unclassified')
            unknown+=category=='unclassified'
            events.append({'event_id':sha256(('statement:'+ident).encode()).hexdigest(),
                'source_event_timestamp_utc':when.isoformat(),'asset':asset,
                'quantity_reported':str(quantity),'category':category,
                'onchain_reconciliation_eligible':False,'blockchain_confirmation':'NOT_IN_STATEMENT_SCHEMA'})
            if len(events)>MAX_RECORDS: raise HistoryError('HISTORY_RECORD_BUDGET_EXCEEDED')
    except (csv.Error,UnicodeDecodeError):
        raise HistoryError('HISTORY_STATEMENT_PARSE_FAILED') from None
    return {'source':'USER_SUPPLIED_COINBASE_STATEMENT_NOT_AUTHENTICATED',
        'source_file_sha256_private':sha256(raw).hexdigest(),'event_count':len(events),'events':events,
        'unclassified_event_count':unknown,'complete_funding_history_certified':False,
        'balances_adjusted':False,'preamble_notes_and_raw_ids_discarded':True}


def read_statement(path,now):
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as f:
            s=os.fstat(f.fileno())
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077 or s.st_size>MAX_BYTES:
                raise HistoryError('HISTORY_PRIVATE_STATEMENT_REJECTED')
            raw=f.read(MAX_BYTES+1)
    except OSError: raise HistoryError('HISTORY_PRIVATE_STATEMENT_REJECTED') from None
    return parse_statement(raw,now)
