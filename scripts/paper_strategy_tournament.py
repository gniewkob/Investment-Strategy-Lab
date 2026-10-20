"""Deterministic education-only paper tournament; supplied bars, no network or orders."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import pstdev

ASSETS=("BTC","ETH")
POLICIES=("equal_dca","momentum","mean_reversion","risk_filter","ensemble")
LOOKBACK={"1h":24,"1d":20}
STEP={"1h":timedelta(hours=1),"1d":timedelta(days=1)}
MAX_BARS=20000
MAX_FX_AGE=timedelta(days=5)
BAND=Decimal(".03")

class ValidationError(ValueError):
    pass

def _decimal(value,label,positive=True):
    if isinstance(value,bool):
        raise ValidationError(f"{label}: boolean not allowed")
    try:
        result=Decimal(str(value))
    except (TypeError,ValueError,InvalidOperation) as exc:
        raise ValidationError(f"{label}: invalid number") from exc
    if not result.is_finite() or result<0 or (positive and result==0):
        raise ValidationError(f"{label}: invalid range")
    return result

def _utc(value):
    if not isinstance(value,str):
        raise ValidationError("timestamp is not string")
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValidationError("bad ISO timestamp") from exc
    if d.tzinfo is None or d.utcoffset()!=timedelta(0):
        raise ValidationError("UTC timestamp required")
    return d.astimezone(timezone.utc)

def validate(payload):
    if not isinstance(payload,dict) or payload.get("mode")!="EDUCATIONAL_PAPER_ONLY":
        raise ValidationError("paper-only mode required")
    if payload.get("source_vintage") not in ("SYNTHETIC_OFFLINE_FIXTURE","RECONSTRUCTED_HISTORICAL_REFERENCE"):
        raise ValidationError("unsupported source provenance/PIT claim")
    tf=payload.get("timeframe")
    if tf not in LOOKBACK:
        raise ValidationError("only 1h and 1d supported")
    fee=_decimal(payload.get("fee_bps"),"fee_bps",False)
    slip=_decimal(payload.get("slippage_bps"),"slippage_bps",False)
    contribution=_decimal(payload.get("monthly_contribution_pln"),"contribution")
    if fee>200 or slip>200 or contribution>100000:
        raise ValidationError("unbounded cost or contribution")
    bars=payload.get("bars")
    if not isinstance(bars,list) or not LOOKBACK[tf]+10<=len(bars)<=MAX_BARS:
        raise ValidationError("invalid bar count")
    rows=[]
    last=None
    for item in bars:
        if not isinstance(item,dict):
            raise ValidationError("bar must be object")
        t=_utc(item.get("start"))
        fx_t=_utc(item.get("fx_asof"))
        if (t.minute,t.second,t.microsecond)!=(0,0,0) or (tf=="1d" and t.hour!=0):
            raise ValidationError("bar not aligned to UTC interval")
        if last is not None and t-last!=STEP[tf]:
            raise ValidationError("duplicate, missing or unordered bars")
        if fx_t>t or t-fx_t>MAX_FX_AGE:
            raise ValidationError("FX reference future or stale")
        row={"start":t,"fx":_decimal(item.get("usdpln"),"USDPLN")}
        for asset in ASSETS:
            row[asset]={"open":_decimal(item.get(asset.lower()+"_open"),asset+" open"),
                        "close":_decimal(item.get(asset.lower()+"_close"),asset+" close")}
        rows.append(row)
        last=t
    return rows,{"timeframe":tf,"fee":fee,"slip":slip,"deposit":contribution,
                 "lookback":LOOKBACK[tf]}

def _signals(rows,t,lookback):
    # Only closes of completed bars strictly preceding the current bar.
    if t<lookback+1:
        return {a:None for a in ASSETS}
    out={}
    for a in ASSETS:
        past=[float(rows[k][a]["close"]) for k in range(t-lookback-1,t)]
        changes=[past[k]/past[k-1]-1 for k in range(1,len(past))]
        out[a]={"trend":past[-1]/past[0]-1,"vol":pstdev(changes)}
    return out

def _weights(policy,signals,monthly,previous,timeframe):
    if policy=="equal_dca":
        return {"BTC":Decimal(".5"),"ETH":Decimal(".5")} if monthly else previous
    if any(v is None for v in signals.values()):
        return {a:Decimal(0) for a in ASSETS}
    strong=max(ASSETS,key=lambda a:(signals[a]["trend"],a))
    weak=min(ASSETS,key=lambda a:(signals[a]["trend"],a))
    if policy=="momentum":
        pick=strong if signals[strong]["trend"]>0 else None
        return {a:Decimal(int(a==pick)) for a in ASSETS}
    if policy=="mean_reversion":
        pick=weak if signals[weak]["trend"]<0 else None
        return {a:Decimal(int(a==pick)) for a in ASSETS}
    cutoff=.03 if timeframe=="1h" else .08
    eligible=[a for a in ASSETS if signals[a]["trend"]>0 and signals[a]["vol"]<cutoff]
    if policy=="risk_filter":
        return {a:Decimal(1)/Decimal(len(eligible)) if a in eligible else Decimal(0)
                for a in ASSETS}
    if policy=="ensemble":
        votes=[]
        if signals[strong]["trend"]>0: votes.append(strong)
        if signals[weak]["trend"]<0: votes.append(weak)
        votes.extend(eligible)
        return {a:Decimal(votes.count(a))/Decimal(len(votes)) if votes else Decimal(0)
                for a in ASSETS}
    raise ValidationError("unknown policy")

def _equity(cash,units,row,kind):
    return cash+sum(units[a]*row[a][kind]*row["fx"] for a in ASSETS)

def _simulate(rows,config,policy):
    cash=Decimal(0)
    units={a:Decimal(0) for a in ASSETS}
    paid=fees=slippage=turnover=Decimal(0)
    trades=0
    month=None
    previous_weights={a:Decimal(0) for a in ASSETS}
    prior_close_equity=Decimal(0)
    peak=unit=Decimal(1)
    max_dd=worst=Decimal(0)
    for i,row in enumerate(rows):
        ym=(row["start"].year,row["start"].month)
        monthly=ym!=month
        month=ym
        inflow=config["deposit"] if monthly else Decimal(0)
        cash+=inflow
        paid+=inflow
        opening=_equity(cash,units,row,"open")
        current_weights={a:units[a]*row[a]["open"]*row["fx"]/opening for a in ASSETS}
        target=_weights(policy,_signals(rows,i,config["lookback"]),monthly,
                        previous_weights,config["timeframe"])
        if policy=="equal_dca" and not monthly:
            target=current_weights
        if sum(target.values())>1:
            raise AssertionError("leverage prohibited")
        drift=max(abs(target[a]-current_weights[a]) for a in ASSETS)
        rebalance=drift>=BAND or (monthly and cash>0 and sum(target.values())>0)
        if rebalance:
            # First sell excess, then buy with available cash; zero credit/shorts.
            for a in ASSETS:
                held=units[a]*row[a]["open"]*row["fx"]
                desired=opening*target[a]
                if held>desired:
                    nominal=held-desired
                    qty=min(units[a],nominal/(row[a]["open"]*row["fx"]))
                    units[a]-=qty
                    fee=nominal*config["fee"]/Decimal(10000)
                    slip=nominal*config["slip"]/Decimal(10000)
                    cash+=nominal-fee-slip
                    fees+=fee
                    slippage+=slip
                    turnover+=nominal
                    trades+=1
            for a in ASSETS:
                held=units[a]*row[a]["open"]*row["fx"]
                shortage=max(Decimal(0),opening*target[a]-held)
                if shortage>0:
                    factor=1+(config["fee"]+config["slip"])/Decimal(10000)
                    nominal=min(shortage,cash/factor)
                    if nominal>0:
                        units[a]+=nominal/(row[a]["open"]*row["fx"])
                        fee=nominal*config["fee"]/Decimal(10000)
                        slip=nominal*config["slip"]/Decimal(10000)
                        cash-=nominal+fee+slip
                        fees+=fee
                        slippage+=slip
                        turnover+=nominal
                        trades+=1
        if cash<Decimal("-0.000001") or any(q<0 for q in units.values()):
            raise AssertionError("cash-only execution violated")
        previous_weights=target
        close=_equity(cash,units,row,"close")
        # Deposits neutral to drawdown and performance; includes opening gaps.
        denominator=prior_close_equity+inflow
        if denominator>0:
            bar_return=close/denominator-1
            worst=min(worst,bar_return)
            unit*=1+bar_return
        prior_close_equity=close
        peak=max(peak,unit)
        max_dd=max(max_dd,1-unit/peak)
    rounded=lambda x:str(x.quantize(Decimal(".01")))
    return {"policy":policy,"contributed_pln":rounded(paid),
            "ending_value_pln":rounded(close),"net_pnl_pln":rounded(close-paid),
            "simple_contribution_roi_pct":rounded((close/paid-1)*100),
            "flow_adjusted_max_drawdown_pct":rounded(max_dd*100),
            "worst_bar_return_pct":rounded(worst*100),
            "transactions":trades,"traded_notional_pln":rounded(turnover),
            "fees_pln":rounded(fees),"slippage_pln":rounded(slippage),
            "ending_cash_pln":rounded(cash),
            "ending_holdings":{a:str(units[a]) for a in ASSETS}}

def run_tournament(payload):
    rows,settings=validate(payload)
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),
                    allow_nan=False).encode()).hexdigest()
    results=[_simulate(rows,settings,p) for p in POLICIES]
    benchmark=Decimal(results[0]["ending_value_pln"])
    for r in results:
        r["difference_vs_equal_dca_pln"]=str((Decimal(r["ending_value_pln"])-benchmark).quantize(Decimal(".01")))
    return {"status":"EDUCATIONAL_PAPER_TOURNAMENT_COMPLETE",
            "source_vintage":payload["source_vintage"],
            "input_sha256":fingerprint,"timeframe":settings["timeframe"],
            "bars":len(rows),"first_bar":rows[0]["start"].isoformat(),
            "last_bar":rows[-1]["start"].isoformat(),
            "monthly_contribution_pln":str(settings["deposit"]),
            "fee_bps":str(settings["fee"]),"slippage_bps":str(settings["slip"]),
            "assumed_execution":"NEXT_BAR_OPEN_PROXY_NO_REAL_FILL",
            "strategies":results,"historical_pit_certified":False,
            "profitability_proven":False,"live_trading_ready":False,
            "orders_sent":0,"database_connections":0,"database_writes":0,
            "existing_M1_M2_M3":"HOLD_NO_CHANGE"}

def main(argv=None):
    parser=argparse.ArgumentParser(description="OFFLINE educational paper strategy comparator")
    parser.add_argument("--input",type=Path,required=True)
    args=parser.parse_args(argv)
    print(json.dumps(run_tournament(json.loads(args.input.read_text(encoding="utf-8"))),
                     sort_keys=True,separators=(",",":")))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
