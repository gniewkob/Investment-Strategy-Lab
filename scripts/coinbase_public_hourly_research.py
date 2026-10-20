"""Read-only, no-auth PUBLIC Coinbase OHLCV source quality proof; zero orders."""
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import hashlib,json
from urllib.parse import urlencode,urlparse,parse_qs
from urllib.request import Request,urlopen

HOST="api.coinbase.com"
PREFIX="/api/v3/brokerage/market/products/"
PRODUCTS=("BTC-USD","ETH-USD")
WINDOW=("2026-10-14T00:00:00Z","2026-10-16T00:00:00Z")
MAX_HTTP=2_000_000

class SourceError(ValueError):
    pass

def parse_ohlcv(body,product,begin,end):
    if product not in PRODUCTS or not isinstance(body,bytes) or len(body)>MAX_HTTP:
        raise SourceError("bad source identity/response size")
    if (end-begin)%3600 or not 1<=(end-begin)//3600<=168:
        raise SourceError("bad hourly window")
    try:
        parsed=json.loads(body)
    except (ValueError,UnicodeDecodeError) as exc:
        raise SourceError("invalid source JSON") from exc
    candles=parsed.get("candles") if isinstance(parsed,dict) else None
    if not isinstance(candles,list) or len(candles)>180:
        raise SourceError("invalid candle list")
    found={}
    for c in candles:
        if not isinstance(c,dict):
            raise SourceError("invalid candle record")
        try:
            at=int(c["start"])
            if at%3600:
                raise SourceError("unaligned candle")
            nums={k:Decimal(str(c[k])) for k in ("open","high","low","close","volume")}
        except (KeyError,ValueError,TypeError,InvalidOperation) as exc:
            raise SourceError("bad candle numeric values") from exc
        if (any(not n.is_finite() for n in nums.values()) or
            any(nums[k]<=0 for k in ("open","high","low","close")) or nums["volume"]<0 or
            nums["low"]>min(nums["open"],nums["close"]) or
            nums["high"]<max(nums["open"],nums["close"]) or nums["low"]>nums["high"]):
            raise SourceError("invalid OHLCV shape")
        if begin<=at<end:
            if at in found: raise SourceError("duplicate candle")
            found[at]=nums
        elif at!=end:
            raise SourceError("unexpected candle outside requested period")
    expected=set(range(begin,end,3600))
    if set(found)!=expected:
        raise SourceError("missing or surplus hourly candles")
    canonical=json.dumps([(at,*[str(found[at][k]) for k in ("open","high","low","close","volume")])
                          for at in sorted(found)],separators=(",",":"))
    return {"product_id":product,"validated_candles":len(found),
            "expected_hours":len(expected),
            "range_start_utc":datetime.fromtimestamp(begin,timezone.utc).isoformat(),
            "range_end_exclusive_utc":datetime.fromtimestamp(end,timezone.utc).isoformat(),
            "raw_response_sha256":hashlib.sha256(body).hexdigest(),
            "canonical_ohlcv_sha256":hashlib.sha256(canonical.encode()).hexdigest(),
            "historical_as_published_pit_certified":False,
            "tradeable_fill_verified":False}

def get_one(product,begin,end,opener=urlopen):
    if product not in PRODUCTS:
        raise SourceError("product not allowlisted")
    path=PREFIX+product+"/candles"
    query=urlencode({"start":str(begin),"end":str(end),
                     "granularity":"ONE_HOUR","limit":"168"})
    url="https://"+HOST+path+"?"+query
    with opener(Request(url,headers={"User-Agent":"ISL-Public-ReadOnly-OHLCV-Research/1.0"}),timeout=30) as resp:
        loc=urlparse(resp.geturl())
        if (resp.status!=200 or loc.scheme!="https" or loc.hostname!=HOST or
            loc.path!=path or parse_qs(loc.query)!=parse_qs(query)):
            raise SourceError("source redirected or responded unexpectedly")
        raw=resp.read(MAX_HTTP+1)
    return parse_ohlcv(raw,product,begin,end)

def main():
    start=int(datetime.fromisoformat(WINDOW[0].replace("Z","+00:00")).timestamp())
    end=int(datetime.fromisoformat(WINDOW[1].replace("Z","+00:00")).timestamp())
    outputs=[get_one(product,start,end) for product in PRODUCTS]
    print("COINBASE_PUBLIC_HOURLY_READONLY_EVIDENCE "+json.dumps({
        "status":"REAL_PUBLIC_HOURLY_OHLCV_COVERAGE_VERIFIED",
        "data":outputs,"source_url":"https://api.coinbase.com/api/v3/brokerage/market/products/{product_id}/candles",
        "database_writes":0,"real_orders":0,"USDPLN_asof_source_certified":False,
        "independent_strategy_performance_evaluated":False},sort_keys=True))

if __name__=="__main__":
    main()
