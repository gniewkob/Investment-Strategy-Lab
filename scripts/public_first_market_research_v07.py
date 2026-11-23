"""Offline MF/UKNF/NBP/Eurostat descriptive research (no trading).

Input is local, previously qualified evidence receipts. Fingerprint agreement
is a consistency check, NOT proof of authenticity, source rights or historical
point-in-time availability. Turnover, yield levels and NAV level changes are
not investable total-return series.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from scripts.public_first_market_quality_v07 import integrate_market_quality
from scripts.research_readiness_quality_v07 import compose_source_readiness

SCHEMA="ISL_PUBLIC_FIRST_OFFLINE_MARKET_RESEARCH_V07"
HASH=re.compile(r"^[a-f0-9]{64}$")


class ResearchPipelineBlocked(ValueError):
    """Evidence insufficient or inconsistent for the requested report."""


def _canonical(data: dict) -> bytes:
    return json.dumps(data,sort_keys=True,separators=(",",":"),
                      allow_nan=False).encode("utf-8")


def _sha(value, label: str) -> str:
    if not isinstance(value,str) or not HASH.fullmatch(value):
        raise ResearchPipelineBlocked(label+"_SHA256_INVALID")
    return value


def _clock(value, label: str) -> datetime:
    if not isinstance(value,str):
        raise ResearchPipelineBlocked(label+"_UTC_CLOCK_REQUIRED")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ResearchPipelineBlocked(label+"_UTC_CLOCK_INVALID") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ResearchPipelineBlocked(label+"_UTC_CLOCK_NAIVE")
    return dt.astimezone(timezone.utc)


def _receipt_integrity(receipt: dict, label: str) -> None:
    """Detect accidental mutations; a rehashed receipt is NOT authenticated."""
    digest=receipt.get("receipt_sha256")
    if digest is None:
        return
    digest=_sha(digest,label+"_RECEIPT")
    data={k:v for k,v in receipt.items() if k!="receipt_sha256"}
    if digest!=sha256(_canonical(data)).hexdigest():
        raise ResearchPipelineBlocked("RECEIPT_HASH_MISMATCH:"+label)


def compose_market_research(*, nav_quality: dict, mf_schema: dict,
                            macro_reference: dict | None = None,
                            mf_turnover: dict | None = None,
                            nav_original: dict | None = None,
                            observed_at: datetime) -> dict:
    """Deterministic integration of previously produced local evidence."""
    if (not isinstance(observed_at,datetime) or observed_at.tzinfo is None
            or observed_at.utcoffset() is None):
        raise ResearchPipelineBlocked("AWARE_REPORT_CLOCK_REQUIRED")
    observed_at=observed_at.astimezone(timezone.utc)
    readiness=compose_source_readiness(
        nav_quality=nav_quality,mf_schema=mf_schema,
        macro_reference=macro_reference,observed_at=observed_at)
    any_original=mf_turnover is not None or nav_original is not None
    if any_original and (mf_turnover is None or nav_original is None
                         or macro_reference is None):
        raise ResearchPipelineBlocked("ORIGINAL_CONTEXT_ALL_OR_NOTHING")
    for label,source in (
        ("UKNF_QUALITY",nav_quality),("MF_SCHEMA",mf_schema),
        ("MACRO",macro_reference),("MF_TURNOVER",mf_turnover),
        ("UKNF_ORIGINAL",nav_original),
    ):
        if source is None:
            continue
        if not isinstance(source,dict):
            raise ResearchPipelineBlocked(label+"_RECEIPT_OBJECT_REQUIRED")
        _receipt_integrity(source,label)
    sources=[
        ("UKNF_QUALITY",nav_quality.get("observed_by_runner_at_utc")),
        ("MF_SCHEMA",mf_schema.get("observed_at_utc")),
    ]
    if macro_reference is not None:
        sources.append(("MACRO",macro_reference.get("observed_at_utc")))
    if any_original:
        sources.extend([
            ("MF_TURNOVER",mf_turnover.get("source_observed_at_utc")),
            ("UKNF_ORIGINAL",nav_original.get("observed_at_utc")),
        ])
    for label,clock in sources:
        if _clock(clock,label)>observed_at:
            raise ResearchPipelineBlocked("SOURCE_OBSERVED_AFTER_REPORT:"+label)
    mf_fingerprint=_sha(mf_schema["sha256"],"MF_SCHEMA")
    nav_fingerprint=_sha(nav_quality["source_history_sha256"],"UKNF_QUALITY")
    market=None
    if any_original:
        if mf_fingerprint!=_sha(mf_turnover.get("source_sha256"),"MF_TURNOVER"):
            raise ResearchPipelineBlocked("MF_SOURCE_MISMATCH")
        nav_sources=nav_original.get("source_documents")
        if not isinstance(nav_sources,dict):
            raise ResearchPipelineBlocked("UKNF_ORIGINAL_SOURCE_DOCUMENTS_REQUIRED")
        if nav_fingerprint!=_sha(nav_sources.get("history_sha256"),
                                 "UKNF_ORIGINAL"):
            raise ResearchPipelineBlocked("NAV_SOURCE_MISMATCH")
        market=integrate_market_quality(mf_turnover,nav_original,macro_reference)
        if (market["model_trading_qualification"]!=[]
                or market["m1_m2_m3"]!="INSUFFICIENT_DATA_HOLD_CASH"):
            raise ResearchPipelineBlocked("MARKET_CONTEXT_PROMOTED_TO_TRADING")
    report={
        "schema":SCHEMA,
        "mode":"DESCRIPTIVE_MARKET_CONTEXT" if any_original else "SCHEMA_ONLY",
        "observed_at_utc":observed_at.isoformat(),
        "source_receipt_consistency_only_not_authentication":True,
        "historical_pit_admitted":False,
        "asset_total_return_qualified":[],
        "m1_m2_m3":"INSUFFICIENT_DATA_HOLD_CASH",
        "source_consistency":{
            "mf_workbook_sha256":mf_fingerprint,
            "uknf_same_class_history_sha256":nav_fingerprint,
            "cross_receipt_fingerprints_match":True if any_original else None,
        },
        "source_readiness":readiness,
        "market_context":market,
        "outbound_reads_by_reporter":0,
        "accounts_connected":0,
        "orders_sent":0,
        "database_writes":0,
        "financial_operations":0,
    }
    report["receipt_sha256"]=sha256(_canonical(report)).hexdigest()
    return report


def render_markdown(report: dict) -> str:
    """Concise note without charting incompatible units or false returns."""
    readiness=report["source_readiness"]
    lines=[
        "# Investment Strategy Lab — raport jakości rynku v0.7",
        "",
        f"- Obserwacja raportu (UTC): {report['observed_at_utc']}",
        f"- Tryb: {report['mode']}",
        f"- Rodziny źródeł: {readiness['source_families']}",
        "- Status strategii M1/M2/M3: INSUFFICIENT_DATA_HOLD_CASH",
        "- Dopuszczone szeregi stóp zwrotu: **brak**",
        "- Uwierzytelnienie i historyczna dostępność danych: **niepotwierdzone**",
        "- Operacje finansowe, zlecenia, baza danych, sieć: **0** w tym reporterze",
        "",
        "## Źródła i ograniczenia",
        "",
        "- MF: struktura XLSX i ewentualny obrót rynku wtórnego, nie cena obligacji ani stopa zwrotu.",
        "- UKNF: nominalne NAV jednej klasy jednostek; bez korekty o wypłaty i opłaty.",
        "- NBP/Eurostat: poziomy FX/złota, HICP i rentowność nominalna; nie wynik inwestora.",
    ]
    market=report["market_context"]
    if market is not None:
        gate=market["source_quality_gate"]
        lines.extend([
            "",
            "## Kontekst opisowy",
            "",
            f"- MF: {gate['mf_complete_history_months']} miesięcy obrotu; ostatni raportowany wolumen "
            f"{market['context_only']['mf_latest_total_mln_pln']} mln PLN.",
            f"- UKNF: {gate['uknf_same_primary_class_nav_days']} dni NAV tej samej klasy.",
            f"- NBP: {gate['macro_nbp_publication_days']} z 22 dni roboczych w badanym miesiącu.",
            f"- Pokrycie NBP pełne: {'tak' if gate['macro_nbp_full_22_day_coverage'] else 'nie'}.",
            "- Korelacje zwrotów i zależność przyczynowa: **nieobliczane**.",
        ])
    else:
        lines.extend([
            "",
            "Wyniki obrotu i NAV nie zostały zestawione liczbowo: brak "
            "kompletu spójnych pokwitowań źródłowych.",
        ])
    lines.extend(["",f"SHA-256 raportu: {report['receipt_sha256']}",""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True,help="Local JSON object with source receipts")
    parser.add_argument("--out-dir",required=True,help="Local DEV report directory")
    parser.add_argument("--observed-at-utc",required=True,
                        help="Timezone-aware ISO 8601 observation time")
    args=parser.parse_args(argv)
    source=Path(args.input)
    if source.stat().st_size>2_000_000:
        parser.error("LOCAL_RECEIPTS_EXCEED_2MB")
    try:
        receipts=json.loads(source.read_text(encoding="utf-8"),
                            parse_constant=lambda _: (_ for _ in ()).throw(
                                ValueError("NONFINITE_JSON_NUMBER")))
        if not isinstance(receipts,dict):
            raise ResearchPipelineBlocked("SOURCE_RECEIPTS_OBJECT_REQUIRED")
        allowed={"nav_quality","mf_schema","macro_reference",
                 "mf_turnover","nav_original"}
        if set(receipts)-allowed or not {"nav_quality","mf_schema"}<=set(receipts):
            raise ResearchPipelineBlocked("UNEXPECTED_OR_MISSING_RECEIPT_KEYS")
        stamp=_clock(args.observed_at_utc,"REPORT")
        report=compose_market_research(**receipts,observed_at=stamp)
    except (ValueError,TypeError,KeyError) as exc:
        parser.error(str(exc))
    target=Path(args.out_dir)
    target.mkdir(parents=True,exist_ok=True)
    (target/"market_research_v07.json").write_text(
        json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    (target/"market_research_v07.md").write_text(render_markdown(report),
                                                encoding="utf-8")
    print("ISL_V07_RESEARCH="+json.dumps({
        "status":"PASS","mode":report["mode"],
        "receipt_sha256":report["receipt_sha256"],
        "m1_m2_m3":report["m1_m2_m3"],"financial_operations":0,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
