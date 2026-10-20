"""Read-only one-shot real-source educational hourly paper tournament.

BTC/ETH source: public Coinbase 1h OHLCV, checked for UTC completeness.
PLN reference: NBP historical Table A mid USDPLN by publication *date*.
NBP effectiveDate does NOT give exact historical API availability;
model uses NEXT CALENDAR DAY 00:00 UTC as conservative availability proxy.
This is reconstructed research, NOT verified PIT, brokerage fills or profit.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen

from scripts.coinbase_public_hourly_research import (
    HOST, PREFIX, PRODUCTS, MAX_HTTP, parse_ohlcv, SourceError,
)
from scripts.paper_strategy_tournament import run_tournament, ValidationError

# Frozen before seeing returns. No fitting on this source period.
START = "2026-08-01T00:00:00Z"
END = "2026-10-01T00:00:00Z"       # end exclusive; two calendar months
FX_START = "2026-07-20"
FX_END = "2026-09-30"
MAX_HOURS_PER_CALL = 144
NBP_HOST = "api.nbp.pl"
NBP_PATH = "/api/exchangerates/rates/a/usd/"
MAX_NBP_BYTES = 100_000


def _timestamp(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def _http_exact(url, expected_host, expected_path, expected_query, limit, opener=urlopen):
    with opener(Request(url, headers={
        "User-Agent": "ISL-Public-Research-Paper-Only/1.0",
        "Accept": "application/json",
    }), timeout=45) as resp:
        got = urlparse(resp.geturl())
        if (resp.status != 200 or got.scheme != "https"
                or got.hostname != expected_host or got.path != expected_path
                or parse_qs(got.query) != parse_qs(expected_query)):
            raise SourceError("Unexpected source response or redirect")
        data = resp.read(limit + 1)
    if not data or len(data) > limit:
        raise SourceError("Source payload out of bounds")
    return data


def fetch_hourly(product, begin, end, opener=urlopen):
    if product not in PRODUCTS or begin % 3600 or end % 3600 or begin >= end:
        raise SourceError("Unapproved source series or invalid UTC window")
    # Bounded public source calls, no authentication/account access.
    if end - begin > 92 * 86400:
        raise SourceError("Historical window exceeds frozen maximum")
    joined = {}
    receipts = []
    for a in range(begin, end, MAX_HOURS_PER_CALL * 3600):
        b = min(a + MAX_HOURS_PER_CALL * 3600, end)
        path = PREFIX + product + "/candles"
        query = urlencode({"start":str(a),"end":str(b),
                           "granularity":"ONE_HOUR","limit":"168"})
        url = "https://" + HOST + path + "?" + query
        raw = _http_exact(url,HOST,path,query,MAX_HTTP,opener)
        receipt = parse_ohlcv(raw, product, a, b)
        try:
            obj = json.loads(raw)
            candles = obj["candles"]
        except (ValueError, KeyError, TypeError) as exc:
            raise SourceError("Invalid validated candle envelope") from exc
        for candle in candles:
            t = int(candle["start"])
            if not a <= t < b: continue  # strict end-exclusive window
            if t in joined: raise SourceError("Repeated hour across calls")
            joined[t] = {
                name: str(Decimal(str(candle[name])))
                for name in ("open","high","low","close")
            }
        receipts.append(receipt)
    if set(joined) != set(range(begin,end,3600)):
        raise SourceError("Full-range hourly gap or duplication")
    serialized = json.dumps([[t,joined[t]] for t in sorted(joined)],sort_keys=True,
                            separators=(",",":"))
    return joined, {
        "product_id":product,"bars":len(joined),
        "source_chunks":len(receipts),
        "source_chunk_proofs":receipts,
        "combined_canonical_sha256":sha256(serialized.encode()).hexdigest(),
        "historical_publication_pit_certified":False
    }


def parse_nbp(raw, start_date, end_date):
    if not isinstance(raw,bytes) or len(raw)>MAX_NBP_BYTES:
        raise SourceError("NBP response not bounded")
    try: obj=json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise SourceError("NBP response not JSON") from exc
    if (not isinstance(obj,dict) or obj.get("table")!="A"
            or obj.get("code")!="USD" or not isinstance(obj.get("rates"),list)
            or len(obj["rates"])>100):
        raise SourceError("Incorrect NBP Table A/USD response")
    found={}
    for row in obj["rates"]:
        if not isinstance(row,dict): raise SourceError("Bad NBP rate")
        try:
            day=date.fromisoformat(row["effectiveDate"])
            mid=Decimal(str(row["mid"]))
            no=row["no"]
        except (ValueError, InvalidOperation, TypeError, KeyError) as exc:
            raise SourceError("Invalid NBP rate") from exc
        if (not isinstance(no,str) or not no.endswith("/A/NBP/"+str(day.year))
                or not start_date<=day<=end_date or not mid.is_finite()
                or mid<=0 or day in found):
            raise SourceError("Out of range/duplicate NBP publication date")
        # Avoid mistaking a historic effectiveDate for a verified exact fetch time.
        available=datetime(day.year,day.month,day.day,tzinfo=timezone.utc)+timedelta(days=1)
        found[day]={"mid":str(mid),"assumed_eligible_utc":available.isoformat(),
                    "effective_date":day.isoformat(),"table_no":no}
    if len(found)<15:
        raise SourceError("Too few NBP reference publication days")
    serialized=json.dumps([(d.isoformat(),found[d]) for d in sorted(found)],
                          separators=(",",":"),sort_keys=True)
    return found,{"observed_nbp_release_dates":len(found),
                  "raw_sha256":sha256(raw).hexdigest(),
                  "canonical_sha256":sha256(serialized.encode()).hexdigest(),
                  "eligibility_assumption":"NEXT_CALENDAR_DAY_00_UTC_NOT_HISTORICAL_EXACT_RELEASE_TIME",
                  "publication_day_verified_from_NBP_current_archive":True,
                  "historical_as_published_content_certified":False}


def fetch_nbp(start_date, end_date, opener=urlopen):
    if end_date < start_date or (end_date-start_date).days>90:
        raise SourceError("NBP request window out of bounds")
    path=NBP_PATH+start_date.isoformat()+"/"+end_date.isoformat()+"/"
    query="format=json"
    url="https://"+NBP_HOST+path+"?"+query
    body=_http_exact(url,NBP_HOST,path,query,MAX_NBP_BYTES,opener)
    rows,receipt=parse_nbp(body,start_date,end_date)
    receipt["url"]=url
    return rows,receipt


def build_payload(btc,eth,rates,begin,end):
    lookup={}
    for day,entry in rates.items():
        ts=int(datetime.fromisoformat(entry["assumed_eligible_utc"]).timestamp())
        if ts in lookup: raise SourceError("Duplicate eligible FX timestamp")
        lookup[ts]=entry
    known=sorted(lookup)
    bars=[]
    for t in range(begin,end,3600):
        if t not in btc or t not in eth:
            raise SourceError("Missing market bar")
        pos=bisect_right(known,t)-1
        if pos<0: raise SourceError("No previously eligible USD/PLN reference")
        last=known[pos]
        if t-last>5*86400: raise SourceError("Stale NBP rate")
        fx=lookup[last]
        base={"start":datetime.fromtimestamp(t,timezone.utc).isoformat(),
              "fx_asof":fx["assumed_eligible_utc"],"usdpln":fx["mid"],
              "btc_open":btc[t]["open"],"btc_close":btc[t]["close"],
              "eth_open":eth[t]["open"],"eth_close":eth[t]["close"]}
        bars.append(base)
    return {"mode":"EDUCATIONAL_PAPER_ONLY",
            "source_vintage":"RECONSTRUCTED_HISTORICAL_REFERENCE",
            "timeframe":"1h","monthly_contribution_pln":"100",
            "fee_bps":"20","slippage_bps":"10","bars":bars}


def research_once():
    begin,end=_timestamp(START),_timestamp(END)
    if (end-begin)!=61*86400:
        raise SourceError("Research window must remain frozen")
    output={}
    receipts={}
    for asset in PRODUCTS:
        output[asset],receipts[asset]=fetch_hourly(asset,begin,end)
    rates,nbp_receipt=fetch_nbp(date.fromisoformat(FX_START),date.fromisoformat(FX_END))
    payload=build_payload(output["BTC-USD"],output["ETH-USD"],rates,begin,end)
    result=run_tournament(payload)
    if (result["orders_sent"] or result["database_writes"]
            or result["historical_pit_certified"] or result["profitability_proven"]):
        raise ValidationError("Invalid research-only output")
    # One fixed source snapshot, same policies and monthly deposits throughout.
    # Cost sensitivity explains financial friction; it does NOT optimize signals
    # or promote an in-sample historical result into predictive evidence.
    sensitivity=[]
    for label,fee_bps,slip_bps in (
        ("ZERO_COST_DIAGNOSTIC","0","0"),
        ("FROZEN_BASELINE","20","10"),
        ("DOUBLE_COST_STRESS","40","20"),
    ):
        candidate=dict(payload,fee_bps=fee_bps,slippage_bps=slip_bps)
        trial=run_tournament(candidate)
        if (trial["orders_sent"] or trial["database_writes"]
                or trial["historical_pit_certified"] or trial["profitability_proven"]):
            raise ValidationError("Cost sensitivity guard violated")
        sensitivity.append({"scenario":label,"fee_bps":fee_bps,"slippage_bps":slip_bps,
                            "policies":[{"policy":s["policy"],
                                         "ending_value_pln":s["ending_value_pln"],
                                         "transactions":s["transactions"],
                                         "fees_pln":s["fees_pln"],
                                         "slippage_pln":s["slippage_pln"]}
                                        for s in trial["strategies"]]})
    if sensitivity[1]["policies"]!=[
            {"policy":s["policy"],"ending_value_pln":s["ending_value_pln"],
             "transactions":s["transactions"],"fees_pln":s["fees_pln"],
             "slippage_pln":s["slippage_pln"]}
            for s in result["strategies"]]:
        raise ValidationError("Frozen baseline cost scenario does not reproduce")
    return {
        "status":"REAL_HISTORICAL_REFERENCES_RECONSTRUCTED_PAPER_ONLY",
        "source_receipts":{"coinbase":receipts,"nbp":nbp_receipt},
        "FX_time_model":"NBP_EFFECTIVE_DATE_PLUS_ONE_UTC_DAY_ASSUMPTION",
        "no_intraday_historical_fx_price_certification":True,
        "brokerage_costs_are_ASSUMED_NOT_MEASURED":True,
        "real_world_trade_execution_verified":False,
        "market_prediction_edge_proven":False,
        "frozen_research_window":[START,END],
        "results":result,
        "fixed_policy_friction_sensitivity":sensitivity,
        "external_orders":0,
        "data_persistence":False
    }


if __name__=="__main__":
    x=research_once()
    print("REAL_PAPER_STRATEGY_RESEARCH "+json.dumps(x,sort_keys=True))
