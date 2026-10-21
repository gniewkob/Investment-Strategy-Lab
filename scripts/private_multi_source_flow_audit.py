"""Private, offline capital-flow accounting: Exchange + Wallet as separate ledgers.

The purpose is to distinguish external contributions from internal movements
and observed changes in USD reference valuations, NEVER to initiate an order,
withdrawal or transfer, or to interpret a residual as investment profit.
No APIs, RPC calls, network, database, credentials, wallets or signing.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

MAX_FILE = 180_000
MAX_EVENTS = 2000
ALLOWED_LOCATIONS = {"exchange", "wallet", "external"}
AUDIT_MODE = "PRIVATE_READ_ONLY_FLOW_AUDIT"
SCOPES = {"BASE_ETHEREUM_WALLET_PRICED_SUBSET", "OTHER_EXPLICITLY_NAMED_SCOPES"}
TYPES = {"internal_movement", "external_inflow", "external_outflow"}


class FlowAuditError(ValueError):
    pass


def _number(value, name):
    if value is None or isinstance(value, bool):
        raise FlowAuditError(name + " not decimal")
    try:
        out = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise FlowAuditError(name + " not decimal") from exc
    if not out.is_finite() or out < 0:
        raise FlowAuditError(name + " outside range")
    return out


def _time(value):
    if not isinstance(value, str):
        raise FlowAuditError("UTC ISO timestamp expected")
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FlowAuditError("Invalid time") from exc
    if at.tzinfo is None or at.utcoffset() != timedelta(0):
        raise FlowAuditError("UTC ISO timestamp required")
    return at.astimezone(timezone.utc)


def _set_keys(obj, allowed, required, label):
    if not isinstance(obj, dict) or not set(obj).issubset(allowed) or not set(required).issubset(obj):
        raise FlowAuditError(label + " has unknown, missing or secret-like fields")


def _snapshot(item, name):
    fields={"captured_at","exchange_priced_usd","wallet_priced_usd",
            "wallet_unpriced_count","wallet_coverage","wallet_observed_at",
            "exchange_observed_at","valuation_source"}
    _set_keys(item, fields, fields, name)
    t = _time(item["captured_at"])
    exchange_time=_time(item["exchange_observed_at"])
    wallet_time=_time(item["wallet_observed_at"])
    if exchange_time>t+timedelta(minutes=2) or wallet_time>t+timedelta(minutes=2):
        raise FlowAuditError("Snapshot component captured after declared time")
    if t-exchange_time>timedelta(hours=24) or t-wallet_time>timedelta(hours=24):
        raise FlowAuditError("Source snapshots too far apart for combined evaluation")
    if item["wallet_coverage"] not in SCOPES:
        raise FlowAuditError("Unknown wallet valuation scope")
    if item["valuation_source"] not in {"PRIVATE_USER_SUPPLIED_REFERENCE",
                                       "SYNTHETIC_OFFLINE_FIXTURE"}:
        raise FlowAuditError("No verified source category")
    count=item["wallet_unpriced_count"]
    if isinstance(count,bool) or not isinstance(count,int) or not 0<=count<=500:
        raise FlowAuditError("Invalid wallet unpriced position count")
    cex=_number(item["exchange_priced_usd"],"exchange_priced_usd")
    wallet=_number(item["wallet_priced_usd"],"wallet_priced_usd")
    return {"time":t,"cex":cex,"wallet":wallet,"total":cex+wallet,
            "unpriced":count,"coverage":item["wallet_coverage"],
            "valuation_source":item["valuation_source"]}


def _event(item, first, last):
    fields={"id","at","type","from","to","amount_usd","fee_usd",
            "confirmed_source","confirmed_destination","reference"}
    _set_keys(item,fields,fields,"event")
    if not isinstance(item["id"],str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}",item["id"]):
        raise FlowAuditError("Invalid safe event ID")
    if not isinstance(item["reference"],str) or not re.fullmatch(
            r"[a-zA-Z0-9:_-]{6,90}",item["reference"]):
        raise FlowAuditError("Invalid non-identifying event reference")
    at=_time(item["at"])
    if at<=first or at>last:
        raise FlowAuditError("Only movements inside (first, last] capture period")
    kind=item["type"]
    origin=item["from"]
    destination=item["to"]
    if kind not in TYPES or origin not in ALLOWED_LOCATIONS or destination not in ALLOWED_LOCATIONS:
        raise FlowAuditError("Unknown transfer category/location")
    if kind=="internal_movement" and (origin,destination) not in {
            ("exchange","wallet"),("wallet","exchange")}:
        raise FlowAuditError("Internal movement must stay within exchange/wallet")
    if kind=="external_inflow" and not(origin=="external" and destination in ("exchange","wallet")):
        raise FlowAuditError("External inflow direction invalid")
    if kind=="external_outflow" and not(destination=="external" and origin in ("exchange","wallet")):
        raise FlowAuditError("External outflow direction invalid")
    amount=_number(item["amount_usd"],"amount_usd")
    fee=_number(item["fee_usd"],"fee_usd")
    if amount<=0 or fee>amount:
        raise FlowAuditError("Transfer amount/fee outside permissible range")
    for field in ("confirmed_source","confirmed_destination"):
        if not isinstance(item[field],bool):
            raise FlowAuditError("Movement evidence confirmation must be boolean")
    return {"id":item["id"],"reference":item["reference"],"at":at,"kind":kind,
            "amount":amount,"fee":fee,"source":origin,"destination":destination,
            "confirmed":item["confirmed_source"] and item["confirmed_destination"]}


def _rounded(num):
    return str(num.quantize(Decimal("0.01")))


def audit_flows(record, report_at=None):
    fields={"mode","currency","snapshots","events"}
    _set_keys(record,fields,fields,"private flow audit")
    if record["mode"] != AUDIT_MODE or record["currency"]!="USD":
        raise FlowAuditError("Only private read-only USD audit is supported")
    src=record["snapshots"]
    if not isinstance(src,list) or len(src)!=2:
        raise FlowAuditError("Exactly two snapshot endpoints needed for an auditable interval")
    first,last=(_snapshot(x,f"snapshot[{i}]") for i,x in enumerate(src))
    if not first["time"]<last["time"]:
        raise FlowAuditError("Snapshots must be strictly chronological")
    if first["coverage"]!=last["coverage"]:
        raise FlowAuditError("Cannot compare different wallet source coverage")
    if first["valuation_source"]!=last["valuation_source"]:
        raise FlowAuditError("Cannot compare synthetic and real reference snapshots")
    events=record["events"]
    if not isinstance(events,list) or len(events)>MAX_EVENTS:
        raise FlowAuditError("Too many events")
    seen_ids,seen_refs=set(),set()
    parsed=[]
    for item in events:
        e=_event(item,first["time"],last["time"])
        if e["id"] in seen_ids or e["reference"] in seen_refs:
            raise FlowAuditError("Duplicate event ID or external reference")
        seen_ids.add(e["id"])
        seen_refs.add(e["reference"])
        parsed.append(e)
    confirmed=[e for e in parsed if e["confirmed"]]
    pending=[e for e in parsed if not e["confirmed"]]
    inflow=sum((e["amount"] for e in confirmed if e["kind"]=="external_inflow"),Decimal(0))
    outflow=sum((e["amount"] for e in confirmed if e["kind"]=="external_outflow"),Decimal(0))
    movement=sum((e["amount"] for e in confirmed if e["kind"]=="internal_movement"),Decimal(0))
    fee=sum((e["fee"] for e in confirmed),Decimal(0))
    delta=last["total"]-first["total"]
    net_external=inflow-outflow
    # This is an arithmetic remainder, NOT market P&L. It mixes valuations,
    # absent activity, spread, taxes, fees not recorded, and source revisions.
    unknown_asset_population_changed = first["unpriced"] != last["unpriced"]
    residual=delta-net_external+fee
    current=_time(report_at) if isinstance(report_at,str) else (
        report_at or datetime.now(timezone.utc))
    if current.utcoffset()!=timedelta(0):
        raise FlowAuditError("UTC report clock required")
    if last["time"]>current+timedelta(seconds=5):
        raise FlowAuditError("Last snapshot in the future")
    lag=current-last["time"]
    warnings=[
        "NOT_A_PROFIT_OR_LOSS_STATEMENT",
        "MISSING_RECORDS_AND_MARKET_PRICE_CHANGES_CAN_AFFECT_RESIDUAL",
        "EXCHANGE_AND_WALLET_VALUATIONS_NOT_EXECUTABLE_CASH",
        "INTERNAL_MOVEMENT_IS_NOT_EXTERNAL_CONTRIBUTION",
        "UNKNOWN_ASSETS_NFT_DEFI_OTHER_CHAINS_EXCLUDED",
    ]
    if first["unpriced"] or last["unpriced"]:
        warnings.append("UNPRICED_WALLET_ASSETS_EXCLUDED")
    if unknown_asset_population_changed:
        warnings.append("UNPRICED_WALLET_ASSET_COUNT_CHANGED_NO_COMPARABLE_RESIDUAL")
    if lag>timedelta(hours=24):
        warnings.append("LAST_BALANCE_SNAPSHOT_OLDER_THAN_24H")
    if pending:
        warnings.append("PENDING_MOVEMENTS_NOT_COUNTED_YET")
    if first["valuation_source"]=="PRIVATE_USER_SUPPLIED_REFERENCE":
        warnings.append("USER_SUPPLIED_SNAPSHOTS_NOT_SOURCE_AUTHENTICATED")
    return {
        "status": "PRIVATE_READ_ONLY_CASH_FLOW_ACCOUNTING",
        "interval_utc": [first["time"].isoformat(),last["time"].isoformat()],
        "source":first["valuation_source"],
        "wallet_coverage":first["coverage"],
        "first_exchange_usd":_rounded(first["cex"]),
        "last_exchange_usd":_rounded(last["cex"]),
        "first_wallet_priced_usd":_rounded(first["wallet"]),
        "last_wallet_priced_usd":_rounded(last["wallet"]),
        "first_identified_subtotal_usd":_rounded(first["total"]),
        "last_identified_subtotal_usd":_rounded(last["total"]),
        "delta_identified_subtotal_usd":_rounded(delta),
        "recorded_external_inflow_usd":_rounded(inflow),
        "recorded_external_outflow_usd":_rounded(outflow),
        "net_recorded_external_funding_usd":_rounded(net_external),
        "confirmed_internal_movement_usd":_rounded(movement),
        "confirmed_internal_movement_count":sum(
            e["kind"]=="internal_movement" for e in confirmed),
        "recorded_event_fees_usd":_rounded(fee),
        "unexplained_reference_change_after_recorded_flows_usd": (
            _rounded(residual) if not pending and not unknown_asset_population_changed else None),
        "pending_event_count":len(pending),
        "recorded_event_count":len(parsed),
        "current_holdings_complete":False,
        "liquid_assets_verified":False,
        "market_profitability_or_return_certified":False,
        "all_transfers_independently_verified":False,
        "warnings":warnings,
        "external_operations":0,"orders":0,"database_writes":0,
    }


def render_markdown(a):
    lines=[
        "# Investment Strategy Lab — prywatny rejestr przepływów (tylko odczyt)",
        "Zakres UTC: "+a["interval_utc"][0]+" — "+a["interval_utc"][1],
        "",
        "| Kategoria | Na początku USD | Na końcu USD |",
        "|---|---:|---:|",
        "| Coinbase Exchange | "+a["first_exchange_usd"]+" | "+a["last_exchange_usd"]+" |",
        "| Wallet, wyceniony podzbiór | "+a["first_wallet_priced_usd"]+" | "+
        a["last_wallet_priced_usd"]+" |",
        "| **Zidentyfikowany podzbiór** | **"+a["first_identified_subtotal_usd"]+
        "** | **"+a["last_identified_subtotal_usd"]+"** |",
        "",
        "Wpłaty zewnętrzne zapisane: "+a["recorded_external_inflow_usd"]+" USD.",
        "Wypłaty zewnętrzne zapisane: "+a["recorded_external_outflow_usd"]+" USD.",
        "Transfery wewnętrzne dwustronnie potwierdzone: "+
        a["confirmed_internal_movement_usd"]+" USD.",
        "Wpisane koszty: "+a["recorded_event_fees_usd"]+" USD.",
        "Nierozstrzygnięte przepływy: "+str(a["pending_event_count"])+".",
    ]
    if a["unexplained_reference_change_after_recorded_flows_usd"] is not None:
        lines.append("Zmiana referencyjna poza zarejestrowanymi przepływami: "+
                     a["unexplained_reference_change_after_recorded_flows_usd"]+
                     " USD — **NIE jest to zweryfikowany zysk ani wynik inwestycyjny**.")
    else:
        lines.append("Zmiana poza przepływami NIEOBLICZANA — są niepotwierdzone ruchy.")
    lines.extend(["", "Granice: "+", ".join(a["warnings"]),
                  "Brak składania zleceń, transferów, operacji finansowych i zapisów do bazy."])
    return "\n".join(lines)


def main(argv=None):
    p=argparse.ArgumentParser(description="OFFLINE private CEX+wallet cash flow audit")
    p.add_argument("--file",type=Path,required=True,
                   help="PRIVATE local movement/snapshot journal, never GitHub")
    p.add_argument("--format",choices=("markdown","json"),default="markdown")
    args=p.parse_args(argv)
    if args.file.stat().st_size>MAX_FILE:
        raise FlowAuditError("Private journal too large")
    raw=args.file.read_bytes()
    data=json.loads(raw)
    result=audit_flows(data)
    print(json.dumps(result,sort_keys=True,ensure_ascii=False) if args.format=="json"
          else render_markdown(result))


if __name__=="__main__":
    main()
