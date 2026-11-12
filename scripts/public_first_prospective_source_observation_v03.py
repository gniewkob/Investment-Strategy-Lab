"""Public-first prospective *observed snapshot* fingerprints, not historic PIT.

Uses official public NBP and Eurostat adapters. Does not save raw prices,
issue trade signals, write database rows or authorize model qualification.
A current fetch proves only that the current version was observed by this
research runner at fetch completion, NOT when it was first published.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Callable

from scripts.nbp_reference_capture import capture
from scripts.public_first_nbp_reference_research_v01 import official_fetch
from scripts.eurostat_hicp_macro_context_v01 import (
    _fetch as official_hicp_fetch, _query as eurostat_query, inspect_hicp,
)

SCHEMA = "ISL_PUBLIC_FIRST_SOURCE_OBSERVATION_V03"
COMPARE_SCHEMA = "ISL_PUBLIC_FIRST_SOURCE_OBSERVATION_COMPARISON_V03"
_SHA = re.compile(r"^[a-f0-9]{64}$")
MAX_ELAPSED = timedelta(minutes=10)
MAX_LOCAL_RECEIPT_BYTES = 20_000
SOURCE_TYPES = {
    "nbp_fx": "NBP_TABLE_A_MID_REFERENCE_NON_EXECUTABLE",
    "nbp_gold": "NBP_PRICE_ONLY_PLN_PER_GRAM",
    "eurostat_hicp": "EUROSTAT_PL_TOTAL_HICP_2025_100_NOT_AN_ASSET",
}


class SourceObservationBlocked(ValueError):
    """Current official-source observation/metadata validation failed."""


def _json(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SourceObservationBlocked("UTC_AWARE_CLOCK_REQUIRED")
    return value.astimezone(timezone.utc)


def _read_utc(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise SourceObservationBlocked("RECEIPT_TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SourceObservationBlocked("RECEIPT_TIMESTAMP_INVALID") from exc
    return _utc(parsed)


def _bounded_day(value: object) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", value):
        raise SourceObservationBlocked("SOURCE_DATE_INVALID")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SourceObservationBlocked("SOURCE_DATE_INVALID") from exc


def _provider_update(value: object, observed_at: datetime) -> str:
    """Validate provider's latest-update timestamp; never first publication."""
    if value == "NOT_PROVIDED":
        return value
    if (type(value) is not str or len(value) > 40 or not re.fullmatch(
            r"[12]\d{3}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
            r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:?\d{2})", value)):
        raise SourceObservationBlocked("EUROSTAT_PROVIDER_UPDATED_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceObservationBlocked("EUROSTAT_PROVIDER_UPDATED_INVALID") from exc
    if parsed.tzinfo is None or parsed.astimezone(timezone.utc) > (
            observed_at + timedelta(minutes=5)):
        raise SourceObservationBlocked("EUROSTAT_PROVIDER_UPDATED_INVALID")
    return value


def _sha(value: object) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise SourceObservationBlocked("SOURCE_FINGERPRINT_INVALID")
    return value


def assemble_receipt(nbp: object, hicp: object, *, nbp_start: str,
                     nbp_end: str, hicp_since: str, hicp_until: str,
                     completed_at: datetime) -> dict:
    """Only bounded official-source metadata from existing typed adapters."""
    finished = _utc(completed_at)
    start, end = _bounded_day(nbp_start), _bounded_day(nbp_end)
    if (end < start or (end - start).days > 92 or end > finished.date()
            or not isinstance(hicp_since, str) or not isinstance(hicp_until, str)
            or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", hicp_since)
            or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", hicp_until)
            or not hicp_since <= hicp_until <= finished.strftime("%Y-%m")):
        raise SourceObservationBlocked("SOURCE_WINDOW_OUTSIDE_OBSERVATION")

    if (not isinstance(nbp, dict) or nbp.get("source") != "NBP"
            or nbp.get("start") != nbp_start or nbp.get("end") != nbp_end
            or nbp.get("gold_basis") != "PRICE_ONLY_PLN_PER_GRAM"
            or nbp.get("fx_basis") != "TABLE_A_MID_PLN_PER_FOREIGN_UNIT"
            or nbp.get("license_status") != "UNVERIFIED"
            or nbp.get("pit_status") != "UNVERIFIED_HISTORICAL_VINTAGE_AND_PUBLICATION_TIME"
            or nbp.get("paper_events_created") != 0):
        raise SourceObservationBlocked("NBP_SOURCE_CONTRACT_INVALID")
    receipts = nbp.get("receipts")
    series = nbp.get("series")
    if (not isinstance(receipts, dict) or set(receipts) != {"fx", "gold"}
            or not isinstance(series, dict)
            or set(series) != {"usdpln", "eurpln", "gold"}
            or any(not isinstance(series[key], list) or not series[key] for key in series)):
        raise SourceObservationBlocked("NBP_RECEIPTS_OR_SERIES_INCOMPLETE")

    source_hashes = {}
    capture_times = {}
    for kind in ("fx", "gold"):
        part = receipts[kind]
        path = ("exchangerates/tables/a" if kind == "fx" else "cenyzlota")
        expected_url = f"https://api.nbp.pl/api/{path}/{nbp_start}/{nbp_end}/?format=json"
        if not isinstance(part, dict) or part.get("url") != expected_url:
            raise SourceObservationBlocked("NBP_SOURCE_URL_MISMATCH")
        source_hashes["nbp_" + kind] = _sha(part.get("sha256"))
        seen_at = _read_utc(part.get("retrieved_at"))
        if not timedelta(0) <= finished - seen_at <= MAX_ELAPSED:
            raise SourceObservationBlocked("SOURCE_CAPTURE_CLOCK_INVALID")
        capture_times["nbp_" + kind] = seen_at.isoformat()
    for code, rows in series.items():
        concept = ("PRICE_ONLY_PLN_PER_GRAM" if code == "gold"
                   else "TABLE_A_MID_PLN_PER_FOREIGN_UNIT")
        if any(not isinstance(row, dict)
               or row.get("basis") != concept
               or row.get("currency") != "PLN"
               or row.get("historical_vintage_verified") is not False
               or row.get("available_at") is not None
               or row.get("source_sha256") != source_hashes[
                   "nbp_gold" if code == "gold" else "nbp_fx"]
               or not nbp_start <= row.get("publication_date", "") <= nbp_end
               for row in rows):
            raise SourceObservationBlocked("NBP_REFERENCE_SEMANTICS_INVALID")

    if (not isinstance(hicp, dict)
            or hicp.get("schema") != "ISL_EUROSTAT_HICP_PL_MACRO_CONTEXT_V01"
            or hicp.get("status") != "AVAILABLE_CONTEXT_NOT_HISTORICAL_PIT"
            or hicp.get("source") != "Eurostat"
            or hicp.get("dataset") != "prc_hicp_minr"
            or hicp.get("country") != "PL" or hicp.get("frequency") != "M"
            or hicp.get("measure_unit") != "I25_INDEX_2025_100"
            or hicp.get("dataflow_semantics") != "ECOICOP_V2_ALL_ITEMS_HICP"
            or hicp.get("retrieval_scope") != "EUROSTAT_PUBLIC_READ_ONLY"
            or hicp.get("historical_point_in_time_certified") is not False
            or hicp.get("historical_first_release_captured") is not False
            or hicp.get("price_index_as_asset_return") is not False
            or hicp.get("missing_months") != []
            or hicp.get("qualified_model_series") != []
            or hicp.get("model_state") != "HOLD_CASH"
            or any(type(hicp.get(key)) is not int or hicp[key] != 0
                   for key in ("orders_sent", "financial_operations", "database_writes"))):
        raise SourceObservationBlocked("EUROSTAT_SOURCE_CONTRACT_INVALID")
    observations = hicp.get("observations")
    if (not isinstance(observations, list) or not observations
            or hicp.get("observed_month_count") != len(observations)
            or hicp.get("available_month_count") != len(observations)
            or observations[0].get("month") != hicp_since
            or observations[-1].get("month") != hicp_until
            or any(not isinstance(row, dict) or row.get("index_2025_100") is None
                   for row in observations)):
        raise SourceObservationBlocked("EUROSTAT_MONTHS_INCOMPLETE")
    source_hashes["eurostat_hicp"] = _sha(hicp.get("source_payload_canonical_sha256"))
    capture_times["eurostat_hicp"] = finished.isoformat()

    rec = {
        "schema": SCHEMA,
        "source_mode": "PUBLIC_OFFICIAL_READ_ONLY_CAPTURE",
        "captured_at_utc": finished.isoformat(),
        "nbp_window": {"start": nbp_start, "end": nbp_end},
        "eurostat_window": {"since": hicp_since, "until": hicp_until},
        "source_fingerprints_sha256": source_hashes,
        "source_capture_completed_at_utc": capture_times,
        "source_semantics": SOURCE_TYPES.copy(),
        "eurostat_provider_reported_updated": _provider_update(
            hicp.get("provider_reported_last_update"), finished),
        "nbp_observation_counts": {k: len(v) for k, v in series.items()},
        "eurostat_observation_months": len(observations),
        "historical_first_publication_timestamp_verified": False,
        "historical_pit_certified": False,
        "observed_now_is_not_original_release_date": True,
        "source_authorization_review": "SCOPE_SPECIFIC_REVIEW_NOT_MODEL_ADMISSION",
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "paper_events_created": 0,
        "database_writes": 0,
        "orders_sent": 0,
        "financial_operations": 0,
    }
    rec["receipt_sha256"] = sha256(_json(rec)).hexdigest()
    return rec


def verify_receipt(receipt: object) -> dict:
    """Self-consistency, NOT authentication of the runner or source origin."""
    if not isinstance(receipt, dict):
        raise SourceObservationBlocked("RECEIPT_INVALID")
    expected = {
        "schema", "source_mode", "captured_at_utc", "nbp_window",
        "eurostat_window", "source_fingerprints_sha256",
        "source_capture_completed_at_utc", "source_semantics",
        "eurostat_provider_reported_updated", "nbp_observation_counts",
        "eurostat_observation_months", "historical_first_publication_timestamp_verified",
        "historical_pit_certified", "observed_now_is_not_original_release_date",
        "source_authorization_review", "qualified_model_series", "model_state",
        "paper_events_created", "database_writes", "orders_sent",
        "financial_operations", "receipt_sha256",
    }
    if (set(receipt) != expected or receipt.get("schema") != SCHEMA
            or receipt.get("source_mode") != "PUBLIC_OFFICIAL_READ_ONLY_CAPTURE"
            or receipt.get("source_semantics") != SOURCE_TYPES
            or receipt.get("historical_first_publication_timestamp_verified") is not False
            or receipt.get("historical_pit_certified") is not False
            or receipt.get("observed_now_is_not_original_release_date") is not True
            or receipt.get("qualified_model_series") != []
            or receipt.get("model_state") != "HOLD_CASH"
            or receipt.get("source_authorization_review") !=
                "SCOPE_SPECIFIC_REVIEW_NOT_MODEL_ADMISSION"
            or any(type(receipt.get(k)) is not int or receipt[k] != 0 for k in (
                "paper_events_created", "database_writes", "orders_sent",
                "financial_operations"))
            or _sha(receipt.get("receipt_sha256")) !=
                sha256(_json({k: v for k, v in receipt.items()
                              if k != "receipt_sha256"})).hexdigest()):
        raise SourceObservationBlocked("RECEIPT_INTEGRITY_OR_SAFETY_INVALID")
    finished = _read_utc(receipt.get("captured_at_utc"))
    _provider_update(receipt.get("eurostat_provider_reported_updated"), finished)
    nbp = receipt.get("nbp_window")
    est = receipt.get("eurostat_window")
    fingerprints = receipt.get("source_fingerprints_sha256")
    times = receipt.get("source_capture_completed_at_utc")
    if (not isinstance(nbp, dict) or set(nbp) != {"start", "end"}
            or not isinstance(est, dict) or set(est) != {"since", "until"}
            or not isinstance(fingerprints, dict) or set(fingerprints) != set(SOURCE_TYPES)
            or not isinstance(times, dict) or set(times) != set(SOURCE_TYPES)):
        raise SourceObservationBlocked("RECEIPT_SCOPE_INVALID")
    _bounded_day(nbp["start"])
    _bounded_day(nbp["end"])
    if (not nbp["start"] <= nbp["end"] <= finished.date().isoformat()
            or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", est.get("since", ""))
            or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", est.get("until", ""))
            or not est["since"] <= est["until"] <= finished.strftime("%Y-%m")):
        raise SourceObservationBlocked("RECEIPT_SCOPE_INVALID")
    for key in SOURCE_TYPES:
        _sha(fingerprints[key])
        seen_at = _read_utc(times[key])
        if not timedelta(0) <= finished - seen_at <= MAX_ELAPSED:
            raise SourceObservationBlocked("RECEIPT_CAPTURE_CLOCK_INVALID")
    return receipt


def compare_receipts(previous: object, current: object) -> dict:
    """Detect fingerprint drift only for identical source periods."""
    before, after = verify_receipt(previous), verify_receipt(current)
    if (before["nbp_window"] != after["nbp_window"]
            or before["eurostat_window"] != after["eurostat_window"]):
        raise SourceObservationBlocked("DIFFERENT_SOURCE_WINDOWS")
    if _read_utc(after["captured_at_utc"]) <= _read_utc(before["captured_at_utc"]):
        raise SourceObservationBlocked("NON_INCREASING_CAPTURE_TIME")
    changed = sorted(
        k for k in SOURCE_TYPES
        if before["source_fingerprints_sha256"][k] !=
           after["source_fingerprints_sha256"][k]
    )
    return {
        "schema": COMPARE_SCHEMA,
        "status": "SOURCE_FINGERPRINTS_CHANGED" if changed else "SOURCE_FINGERPRINTS_UNCHANGED",
        "changed_sources": changed,
        "same_source_windows": True,
        "prior_receipt_sha256": before["receipt_sha256"],
        "new_receipt_sha256": after["receipt_sha256"],
        "does_not_establish_historic_first_release": True,
        "historical_pit_certified": False,
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def observe_once(*, nbp_start: str, nbp_end: str, hicp_since: str,
                 hicp_until: str, nbp_fetch: Callable | None,
                 hicp_fetch: Callable | None,
                 clock: Callable = lambda: datetime.now(timezone.utc)) -> dict:
    """Explicit injection: callers must opt in; never auto-run HTTP."""
    if nbp_fetch is None or hicp_fetch is None:
        raise SourceObservationBlocked("EXPLICIT_OFFICIAL_SOURCE_FETCH_REQUIRED")
    # Validate both date windows and an aware clock BEFORE any HTTP request.
    started = _utc(clock())
    first, last = _bounded_day(nbp_start), _bounded_day(nbp_end)
    if (last < first or (last - first).days > 92
            or last > started.date()
            or not isinstance(hicp_since, str) or not isinstance(hicp_until, str)
            or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", hicp_since)
            or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", hicp_until)
            or not hicp_since <= hicp_until <= started.strftime("%Y-%m")):
        raise SourceObservationBlocked("SOURCE_WINDOW_OUTSIDE_OBSERVATION")
    hicp_url = eurostat_query(hicp_since, hicp_until)
    nbp = capture(nbp_start, nbp_end, fetch=nbp_fetch, clock=clock)
    data = hicp_fetch(hicp_url)
    hicp = inspect_hicp(data, since=hicp_since, until=hicp_until,
                        retrieval_scope="EUROSTAT_PUBLIC_READ_ONLY")
    return assemble_receipt(
        nbp, hicp, nbp_start=nbp_start, nbp_end=nbp_end,
        hicp_since=hicp_since, hicp_until=hicp_until,
        completed_at=clock())


def _load_previous(path: Path) -> dict:
    """Read only a bounded, already-open regular file without symlink races."""
    if not isinstance(path, Path) or not hasattr(os, "O_NOFOLLOW"):
        raise SourceObservationBlocked("PREVIOUS_RECEIPT_UNSAFE_FILE_SYSTEM")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise SourceObservationBlocked("PREVIOUS_RECEIPT_UNREADABLE") from exc
    try:
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_size <= 0
                    or info.st_size > MAX_LOCAL_RECEIPT_BYTES):
                raise SourceObservationBlocked(
                    "PREVIOUS_RECEIPT_NOT_BOUNDED_REGULAR_FILE")
            raw = stream.read(MAX_LOCAL_RECEIPT_BYTES + 1)
    except OSError as exc:
        raise SourceObservationBlocked("PREVIOUS_RECEIPT_UNREADABLE") from exc
    if not raw or len(raw) > MAX_LOCAL_RECEIPT_BYTES:
        raise SourceObservationBlocked("PREVIOUS_RECEIPT_NOT_BOUNDED_REGULAR_FILE")
    try:
        previous = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SourceObservationBlocked("PREVIOUS_RECEIPT_UNREADABLE") from exc
    return verify_receipt(previous)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nbp-start", required=True)
    parser.add_argument("--nbp-end", required=True)
    parser.add_argument("--hicp-since", required=True)
    parser.add_argument("--hicp-until", required=True)
    parser.add_argument("--allow-public-source-fetch", action="store_true")
    parser.add_argument("--previous-receipt", type=Path)
    args = parser.parse_args()
    if not args.allow_public_source_fetch:
        parser.error("Explicit --allow-public-source-fetch required")
    try:
        previous = (_load_previous(args.previous_receipt)
                    if args.previous_receipt is not None else None)
        if previous is not None and (
                previous["nbp_window"] != {
                    "start": args.nbp_start, "end": args.nbp_end}
                or previous["eurostat_window"] != {
                    "since": args.hicp_since, "until": args.hicp_until}):
            raise SourceObservationBlocked("PREVIOUS_RECEIPT_WINDOW_MISMATCH")
        current = observe_once(
            nbp_start=args.nbp_start, nbp_end=args.nbp_end,
            hicp_since=args.hicp_since, hicp_until=args.hicp_until,
            nbp_fetch=official_fetch, hicp_fetch=official_hicp_fetch)
        print("ISL_PROSPECTIVE_PUBLIC_SOURCE_RECEIPT=" + json.dumps(
            current, sort_keys=True, separators=(",", ":")))
        if previous is not None:
            comparison = compare_receipts(previous, current)
            print("ISL_PUBLIC_SOURCE_REVISION_COMPARISON=" + json.dumps(
                comparison, sort_keys=True, separators=(",", ":")))
    except (SourceObservationBlocked, ValueError, OSError) as exc:
        parser.error("PUBLIC_SOURCE_OBSERVATION_BLOCKED: " + type(exc).__name__)


if __name__ == "__main__":
    main()
