"""Compile a STRICT, idempotent Neon LAB NBP-reference ingestion SQL statement.

No network, database or trading integration is built into this module.
Only verified output of nbp_lab_prepare is accepted. Operators execute the
generated statement with their existing controlled research data access.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ALLOWED = {
    "USDPLN_NBP": ("nbp_rates", "FX_RATE", "fx"),
    "EURPLN_NBP": ("nbp_rates", "FX_RATE", "fx"),
    "GOLD_NBP_PLN_G": ("nbp_gold", "PRICE_ONLY", "gold"),
}
DIGEST = re.compile(r"^[a-f0-9]{64}$")
NUMBER = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validated_utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("retrieved_at required")
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("retrieved_at timezone required")
    return timestamp.astimezone(timezone.utc)


def _official_url(value):
    if not isinstance(value, str):
        raise ValueError("source URL required")
    parts = urlsplit(value)
    if (parts.scheme != "https" or parts.netloc != "api.nbp.pl"
            or not parts.path.startswith("/api/")
            or parts.fragment or parts.username or parts.password):
        raise ValueError("non-official NBP HTTPS source URL")


def _quoted(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).replace("'", "''")


def build_sql(receipt: dict) -> str:
    if not isinstance(receipt, dict):
        raise ValueError("receipt must be JSON object")
    if (receipt.get("source") != "NBP_OFFICIAL_API"
            or receipt.get("market_data_kind") != "REFERENCE_ONLY_NOT_TOTAL_RETURN"
            or receipt.get("paper_events_created") != 0
            or receipt.get("real_financial_operations") != 0
            or receipt.get("historical_publication_hour_verified") is not False
            or receipt.get("historical_source_vintage_verified") is not False):
        raise ValueError("unexpected receipt intent or trust boundary")

    series = receipt.get("by_series")
    rows = receipt.get("rows")
    source_receipts = receipt.get("source_receipts")
    if (not isinstance(rows, list) or not rows or len(rows) > 279
            or receipt.get("row_count") != len(rows)
            or not isinstance(series, dict) or set(series) != {"usdpln", "eurpln", "gold"}
            or not isinstance(source_receipts, dict) or set(source_receipts) != {"fx", "gold"}):
        raise ValueError("invalid NBP receipt envelope")
    if any(not isinstance(n, int) or n <= 0 for n in series.values()):
        raise ValueError("empty or invalid NBP series")
    if sum(series.values()) != len(rows) or series["usdpln"] != series["eurpln"]:
        raise ValueError("series count disagreement")
    begin, end = receipt.get("start"), receipt.get("end")
    if not isinstance(begin, str) or not DAY.fullmatch(begin) or not isinstance(end, str) or not DAY.fullmatch(end):
        raise ValueError("ISO source range required")
    begin_day, end_day = date.fromisoformat(begin), date.fromisoformat(end)
    if not begin_day <= end_day or (end_day - begin_day).days > 92:
        raise ValueError("invalid NBP date range")

    for kind, r in source_receipts.items():
        if not isinstance(r, dict) or not DIGEST.fullmatch(r.get("sha256", "")):
            raise ValueError("source SHA-256 required")
        _official_url(r.get("url"))
        if kind == "fx" and "/exchangerates/tables/a/" not in r["url"]:
            raise ValueError("table A rates source required")
        if kind == "gold" and "/cenyzlota/" not in r["url"]:
            raise ValueError("NBP gold source required")
        _validated_utc(r.get("retrieved_at"))

    unique, counts = set(), {k: 0 for k in ALLOWED}
    fields = {"instrument_code", "source_code", "observed_for",
              "interval_code", "close_price", "return_basis",
              "source_url", "source_sha256", "retrieved_at"}
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("unexpected NBP row fields")
        inst = row.get("instrument_code")
        if inst not in ALLOWED:
            raise ValueError("unexpected instrument")
        source, basis, receipt_kind = ALLOWED[inst]
        orig = source_receipts[receipt_kind]
        if (row["source_code"] != source or row["return_basis"] != basis
                or row["interval_code"] != "1d" or row["source_url"] != orig["url"]
                or row["source_sha256"] != orig["sha256"]
                or row["retrieved_at"] != orig["retrieved_at"]):
            raise ValueError("source/basis/provenance mismatch")
        d = row["observed_for"]
        if not isinstance(d, str) or not DAY.fullmatch(d):
            raise ValueError("invalid observation date")
        observed = date.fromisoformat(d)
        if observed < begin_day or observed > end_day or observed > _validated_utc(orig["retrieved_at"]).date():
            raise ValueError("observation outside available source range")
        amount = row["close_price"]
        if not isinstance(amount, str) or not NUMBER.fullmatch(amount):
            raise ValueError("invalid numeric price")
        try:
            dec = Decimal(amount)
        except InvalidOperation:
            raise ValueError("invalid numeric price") from None
        if not dec.is_finite() or dec <= 0:
            raise ValueError("invalid NBP price")
        key = (inst, d)
        if key in unique:
            raise ValueError("duplicate instrument/date")
        unique.add(key)
        counts[inst] += 1
    if (counts["USDPLN_NBP"] != series["usdpln"]
            or counts["EURPLN_NBP"] != series["eurpln"]
            or counts["GOLD_NBP_PLN_G"] != series["gold"]):
        raise ValueError("series grouping mismatch")

    key = ("nbp-ref-" + begin.replace("-", "") + "-" + end.replace("-", "") + "-"
           + source_receipts["fx"]["sha256"][:12] + "-" + source_receipts["gold"]["sha256"][:12])
    prepared = _quoted(rows)
    sources = _quoted(source_receipts)
    # NBP publication dates are mapped to explicit UTC midnight regardless
    # of the executing PostgreSQL session TimeZone.
    # All dynamic values above are validated. Strings enter SQL exclusively
    # through SQL-escaped JSON literals, never from arbitrary SQL fragments.
    return f"""
WITH raw AS (SELECT '{prepared}'::jsonb AS rows, '{sources}'::jsonb AS receipts),
candidate AS (
 SELECT r.instrument_code,r.source_code,r.observed_for::date AS publication_day,
 r.close_price::numeric AS value,r.return_basis,r.source_url
 FROM raw,jsonb_to_recordset(raw.rows) AS r(
 instrument_code text,source_code text,observed_for text,interval_code text,
 close_price text,return_basis text,source_url text,source_sha256 text,retrieved_at text)
), conflicts AS (
 SELECT c.instrument_code,c.publication_day FROM candidate c
 JOIN investment_lab.price_observations p
 ON p.instrument_code=c.instrument_code AND p.source_code=c.source_code
 AND p.observed_for=(c.publication_day::timestamp AT TIME ZONE 'UTC') AND p.interval_code='1d'
 WHERE p.close_price<>c.value OR p.return_basis<>c.return_basis
), inserted AS (
 INSERT INTO investment_lab.price_observations
 (instrument_code,source_code,observed_for,ingested_at,interval_code,close_price,return_basis,source_url)
 SELECT c.instrument_code,c.source_code,(c.publication_day::timestamp AT TIME ZONE 'UTC'),
 now(),'1d',c.value,c.return_basis,c.source_url
 FROM candidate c WHERE NOT EXISTS(SELECT 1 FROM conflicts)
 ON CONFLICT (instrument_code,source_code,observed_for,interval_code) DO NOTHING
 RETURNING instrument_code,observed_for
), audited AS (
 INSERT INTO investment_lab.audit_events(kind,record_id,message,metadata)
 SELECT 'INGEST','{key}',
 'Official NBP FX and gold reference data appended; NOT total return',
 jsonb_build_object('source','NBP_OFFICIAL_API','receipts',raw.receipts,
 'source_range_start','{begin}','source_range_end','{end}',
 'actual_inserted',(SELECT count(*) FROM inserted),
 'reference_only',true,'original_publication_hour_known',false,
 'historical_vintage_certified',false,'financial_operations',0,
 'paper_events_created',0,'inserted_per_instrument',(
 SELECT coalesce(jsonb_object_agg(instrument_code,n),'{{}}'::jsonb)
 FROM (SELECT instrument_code,count(*) AS n FROM inserted GROUP BY instrument_code) v))
 FROM raw WHERE EXISTS(SELECT 1 FROM inserted)
 RETURNING audit_id
)
SELECT (SELECT count(*) FROM candidate) AS candidate_rows,
 (SELECT count(*) FROM conflicts) AS conflicting_rows,
 (SELECT count(*) FROM inserted) AS inserted_rows,
 (SELECT count(*) FROM audited) AS audit_rows,
 0 AS paper_events_created,0 AS financial_operations
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt_json", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    raw = args.receipt_json.read_text(encoding="utf-8")
    if raw.startswith("NBP_LAB_RECEIPT_JSON="):
        raw = raw.removeprefix("NBP_LAB_RECEIPT_JSON=")
    sql = build_sql(json.loads(raw))
    if args.out:
        args.out.write_text(sql + "\n", encoding="utf-8")
        print("NBP_LAB_SQL_PREPARED_ROWS=" + str(json.loads(raw)["row_count"]))
    else:
        print(sql)


if __name__ == "__main__":
    main()
