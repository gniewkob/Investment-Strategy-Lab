"""Deterministic synthetic data demo; never real BTC, ETH or USDPLN quotes."""
from datetime import datetime, timedelta, timezone
import json
from scripts.paper_strategy_tournament import run_tournament

def make_fixture(timeframe="1h"):
    if timeframe not in ("1h","1d"):
        raise ValueError("unsupported demo timeframe")
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    stride=timedelta(hours=1) if timeframe=="1h" else timedelta(days=1)
    count=24*72 if timeframe=="1h" else 180
    bars=[]
    for i in range(count):
        at=start+stride*i
        btc=100+i/80+((i%17)-8)*.09
        eth=80+i/180+((i%29)-14)*.13
        bars.append({"start":at.isoformat(),"fx_asof":at.isoformat(),
                     "usdpln":"4.00","btc_open":str(btc),"btc_close":str(btc+.03),
                     "eth_open":str(eth),"eth_close":str(eth-.03)})
    return {"mode":"EDUCATIONAL_PAPER_ONLY","source_vintage":"SYNTHETIC_OFFLINE_FIXTURE",
            "timeframe":timeframe,"monthly_contribution_pln":"100",
            "fee_bps":"20","slippage_bps":"10","bars":bars}

def main():
    for timeframe in ("1h","1d"):
        result=run_tournament(make_fixture(timeframe))
        print("PAPER_TOURNAMENT_SYNTHETIC_DEMO "+json.dumps({
            "timeframe":timeframe,"input_sha256":result["input_sha256"],
            "bars":result["bars"],"market_source":"NONE_SYNTHETIC",
            "strategies":[{"policy":s["policy"],"ending_value_pln":s["ending_value_pln"],
                           "fees_pln":s["fees_pln"],"transactions":s["transactions"]}
                          for s in result["strategies"]],
            "orders_sent":result["orders_sent"],"profitability_proven":False
        },sort_keys=True))
if __name__=="__main__":
    main()
