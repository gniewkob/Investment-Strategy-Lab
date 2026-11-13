"""UKNF original bounded 2026-09 single-fund unit-NAV audit + KID metadata.

One selected original page and at most TWO follow-up official GETs,
no bulk export, rankings, recommendations, brokerage or portfolio access.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
import re
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from scripts.knf_mf_official_source_probe_v06 import (
    KNF_ROOT, KNF_URLS, MAX_KNF_BYTES, NoRedirect,
    OriginalEvidenceBlocked as Blocked, inspect_knf_page, _utc,
)

MAX_ROWS = 30
MONTH_BEGIN, MONTH_END = "2026-09-01", "2026-09-30"
ID_PATTERN = re.compile(r"^[0-9a-fA-F-]{36}$")
UNIT_PATTERN = re.compile(r"^[\w\- ]{1,32}$", re.ASCII)


def _number(x: object, *, minimum=Decimal(0), maximum=Decimal(1_000_000)):
    if type(x) not in (str, float, int):
        raise Blocked("INVALID_NUMERIC_FIELD")
    try:
        n = Decimal(str(x))
    except (InvalidOperation, ValueError) as exc:
        raise Blocked("INVALID_NUMERIC_FIELD") from exc
    if not n.is_finite() or not minimum <= n <= maximum:
        raise Blocked("INVALID_NUMERIC_FIELD")
    return n


def _first_record(kind: str, raw: bytes, when: datetime) -> dict:
    inspect_knf_page(kind, raw, completed_at=when)
    data = json.loads(raw)
    if not data["content"]:
        raise Blocked("OFFICIAL_SAMPLE_EMPTY")
    return data["content"][0]


def _url(kind: str, initial_row: dict) -> str:
    if kind == "kid":
        docid = initial_row["documentUuid"]
        if not ID_PATTERN.fullmatch(docid):
            raise Blocked("KID_DOC_ID_INVALID")
        return KNF_ROOT + "/v1/key-information/units/" + docid
    if kind != "history":
        raise Blocked("UNSUPPORTED_KNF_REQUEST_TYPE")
    fid = initial_row.get("fundId")
    sid = initial_row.get("subfundId")
    if (type(fid) is not int and fid is not None
            or type(sid) is not int and sid is not None
            or (fid is None) == (sid is None)
            or fid is not None and fid < 1
            or sid is not None and sid < 1):
        raise Blocked("FUND_IDENTITY_NOT_EXCLUSIVE")
    unit = initial_row.get("unit")
    if type(unit) is not str or not UNIT_PATTERN.fullmatch(unit):
        raise Blocked("FUND_UNIT_CLASS_UNSAFE")
    params = {
        "fundId" if fid is not None else "subfundId": fid if fid is not None else sid,
        "unit": unit,
        "currency": "PLN",
        "isPrimary": "true",
        "fromDate": MONTH_BEGIN, "toDate": MONTH_END,
        "page": 0, "size": MAX_ROWS,
    }
    return KNF_ROOT + "/v1/valuations/units?" + urlencode(params)


def fetch_followup(url: str, *, expected_url: str) -> bytes:
    if url != expected_url or not url.startswith(KNF_ROOT+"/v1/"):
        raise Blocked("FOLLOWUP_URL_NOT_EXACT_OFFICIAL")
    op = build_opener(NoRedirect(), HTTPSHandler())
    request = Request(url, headers={"Accept":"application/json",
                                    "User-Agent":"ISL-source-edu-v0.6/single-followup"})
    with op.open(request, timeout=25) as response:
        if response.status != 200 or response.geturl() != expected_url:
            raise Blocked("FOLLOWUP_RESPONSE_NOT_EXACT")
        raw=response.read(MAX_KNF_BYTES+1)
    if not raw or len(raw)>MAX_KNF_BYTES:
        raise Blocked("FOLLOWUP_BYTES_OUT_OF_BOUNDS")
    return raw


def evaluate_sample(preview_raw: bytes, kid_page_raw: bytes,
                    history_raw: bytes, kid_detail_raw: bytes, *,
                    at: datetime) -> dict:
    at_utc=_utc(at)
    chosen=_first_record("primary_pln_valuations",preview_raw,at)
    kid=_first_record("kid_units",kid_page_raw,at)
    history_url=_url("history",chosen)
    kid_url=_url("kid",kid)
    try:
        history=json.loads(history_raw)
        detail=json.loads(kid_detail_raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Blocked("FOLLOWUP_JSON_INVALID") from exc
    if (not isinstance(history,dict) or not isinstance(detail,dict)
            or not isinstance(history.get("content"),list)
            or not isinstance(history.get("page"),dict)):
        raise Blocked("FOLLOWUP_WRONG_STRUCTURE")
    rows=history["content"]
    pg=history["page"]
    if (not 2 <= len(rows) <= MAX_ROWS
            or type(pg.get("number")) is not int or pg["number"] != 0
            or type(pg.get("totalElements")) is not int
            or pg["totalElements"] != len(rows)
            or type(pg.get("size")) is not int or pg["size"] > MAX_ROWS):
        raise Blocked("HISTORY_INCOMPLETE_SINGLE_PAGE")
    if (detail.get("documentUuid") != kid["documentUuid"]
            or detail.get("publicationDate") != kid["publicationDate"]
            or detail.get("subfundId") != kid.get("subfundId")
            or detail.get("fundId") != kid.get("fundId")):
        raise Blocked("KID_DETAIL_IDENTITY_CHANGED")
    seen={}
    for row in rows:
        if not isinstance(row,dict):
            raise Blocked("BAD_HISTORY_ROW")
        if (row.get("fundId") != chosen.get("fundId")
                or row.get("subfundId") != chosen.get("subfundId")
                or row.get("unit") != chosen.get("unit")
                or row.get("currency") != "PLN"
                or row.get("isPrimary") is not True):
            raise Blocked("HISTORY_DIFFERENT_FUND_UNIT")
        try:
            day=date.fromisoformat(row["date"])
        except (KeyError,ValueError,TypeError) as exc:
            raise Blocked("HISTORY_INVALID_DATE") from exc
        if not date.fromisoformat(MONTH_BEGIN) <= day <= date.fromisoformat(MONTH_END) or day in seen:
            raise Blocked("HISTORY_DATE_OUT_OF_SCOPE_OR_DUPLICATE")
        value=_number(row.get("valuation"))
        if value<=0:
            raise Blocked("HISTORY_NAV_NOT_POSITIVE")
        seen[day]=value
    days=sorted(seen)
    if days[-1] != date.fromisoformat(chosen["date"]):
        raise Blocked("HISTORY_NOT_SAME_CURRENT_SAMPLE")
    risk=detail.get("riskLevel")
    if risk is not None and (type(risk) is not int or not 1 <= risk <= 7):
        raise Blocked("KID_RISK_LEVEL_INVALID")
    costs={}
    for field in ("maxEntryFeeRate","maxExitFeeRate",
                  "managementAndOtherFeesRate","transactionCostsRate"):
        val=detail.get(field)
        costs[field]=None if val is None else str(_number(
            val,minimum=Decimal("0"),maximum=Decimal("1")))
    with localcontext() as ctx:
        ctx.prec=40
        delta=(seen[days[-1]]/seen[days[0]]-Decimal(1))*Decimal(100)
    return {
        "schema":"ISL_UKNF_HISTORICAL_PRIMARY_UNIT_SAMPLE_V06",
        "status":"REAL_UKNF_SINGLE_FUND_NAV_LEVEL_CHANGE_EDUCATIONAL_ONLY",
        "source":"UKNF_WYBIERAM_FUNDUSZE_API_V1_2",
        "source_attribution":"https://wybieramfundusze-api.knf.gov.pl",
        "observed_at_utc":at_utc,
        "selected_fund_identity_stable":True,
        "selected_currency":"PLN",
        "selected_primary_share_class":True,
        "daily_same_class_observations":len(seen),
        "first_observation_day":days[0].isoformat(),
        "last_observation_day":days[-1].isoformat(),
        "observed_nav_level_change_pct_not_total_return":format(delta.quantize(Decimal("0.0001")),"f"),
        "kid_risk_level_descriptive_not_recommendation":risk,
        "kid_document_publication_date_not_first_ever":kid["publicationDate"],
        "kid_stated_costs_rates_not_actual_fees":costs,
        "provider_current_snapshot_not_original_historic_asof":True,
        "cash_distributions_verified":False,
        "fund_holding_period_total_return_qualified":False,
        "benchmark_total_return_series_qualified":[],
        "paper_rebalance_authorized":False,
        "historical_pit_certified":False,
        "source_documents": {
            "valuation_preview_sha256":sha256(preview_raw).hexdigest(),
            "history_sha256":sha256(history_raw).hexdigest(),
            "kid_list_sha256":sha256(kid_page_raw).hexdigest(),
            "kid_detail_sha256":sha256(kid_detail_raw).hexdigest(),
        },
        "history_original_url":history_url,
        "kid_original_url":kid_url,
        "accounts_connected":0,"database_writes":0,
        "orders_sent":0,"financial_operations":0,
    }


def observe_once(*, fetch=None, clock=lambda:datetime.now(timezone.utc)):
    if fetch is None:
        raise Blocked("EXPLICIT_KNF_API_FETCH_REQUIRED")
    start=clock()
    _utc(start)
    # 2 small initial pages + at most 2 tightly scoped follow-up GETs.
    initial_preview=fetch(KNF_URLS["primary_pln_valuations"])
    initial_kid=fetch(KNF_URLS["kid_units"])
    chosen=_first_record("primary_pln_valuations",initial_preview,start)
    kid=_first_record("kid_units",initial_kid,start)
    raw_hist=fetch(_url("history",chosen))
    raw_detail=fetch(_url("kid",kid))
    return evaluate_sample(initial_preview,initial_kid,raw_hist,raw_detail,at=clock())


def official_source_fetch(url: str) -> bytes:
    """Only the four controlled URLs generated within observe_once."""
    from scripts.knf_mf_official_source_probe_v06 import fetch_exact
    if url in (KNF_URLS["primary_pln_valuations"], KNF_URLS["kid_units"]):
        return fetch_exact(url)
    if url.startswith(KNF_ROOT + "/v1/valuations/units?") or url.startswith(
            KNF_ROOT + "/v1/key-information/units/"):
        return fetch_followup(url, expected_url=url)
    raise Blocked("NOT_AN_APPROVED_UKNF_FOLLOWUP")


def main() -> None:
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-original-source-read",action="store_true")
    args=parser.parse_args()
    if not args.allow_public_original_source_read:
        parser.error("Explicit --allow-public-original-source-read required")
    receipt=observe_once(fetch=official_source_fetch)
    print("ISL_UKNF_ORIGINAL_SINGLE_UNIT_HISTORY="+json.dumps(
        receipt,sort_keys=True,separators=(",",":")))


if __name__ == "__main__":
    main()
