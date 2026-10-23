"""Offline Coinbase App List Transactions capture import. No HTTP or credentials.

Only receive events are retained. Network identifiers from receive records are
deliberately not promoted to reconciliation evidence: the current provider
contract documents hash/network_name only for sends. All captures are untrusted.
"""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import re
from urllib.parse import parse_qs, urlsplit

from scripts.coinbase_read_only_history import HistoryError, _time
from scripts.deposit_evidence_reconciliation import reconcile

UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
CAPTURE_MODE = "PRIVATE_COINBASE_APP_TRANSACTIONS_V1"
BUNDLE_MODE = "PRIVATE_COINBASE_DEPOSIT_REVIEW_V1"
MAX_PAGES = 50
MAX_RECORDS = 5000


def _require(condition):
    if not condition:
        raise HistoryError("DEPOSIT_HISTORY_REJECTED")


def _uuid(value):
    _require(isinstance(value, str) and bool(UUID.fullmatch(value)))
    return value


def _provider_time(value):
    """Provider events may use explicit nonzero offsets; emit canonical UTC."""
    _require(isinstance(value, str))
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        _require(parsed.tzinfo is not None and parsed.utcoffset() is not None)
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise HistoryError("DEPOSIT_HISTORY_REJECTED") from None


def _cursor(uri, path):
    if uri is None:
        return None
    _require(isinstance(uri, str) and len(uri) <= 2048)
    try:
        parts = urlsplit(uri)
        query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True,
                         max_num_fields=3)
    except ValueError:
        raise HistoryError("DEPOSIT_HISTORY_REJECTED") from None
    _require(not parts.scheme and not parts.netloc and not parts.fragment
             and parts.path == path and uri.startswith(path + "?")
             and set(query) <= {"starting_after", "limit", "order"}
             and "starting_after" in query and all(len(v) == 1 for v in query.values()))
    if "order" in query:
        _require(query["order"] == ["desc"])
    if "limit" in query:
        _require(query["limit"][0] in {str(n) for n in range(1, 101)})
    return _uuid(query["starting_after"][0])


def normalize_receives(capture, now):
    """Validate a private, account-scoped page chain; return minimized receives.

    Capture: mode, account_id, captured_at, pages. Each page has request_cursor
    (None for first), response (documented data and pagination). The input is
    operator supplied; no authenticity or point-in-time completeness is claimed.
    """
    _require(isinstance(capture, dict) and set(capture) == {
        "mode", "account_id", "captured_at", "pages"} and capture["mode"] == CAPTURE_MODE)
    account = _uuid(capture["account_id"])
    path = f"/v2/accounts/{account}/transactions"
    captured = _time(capture["captured_at"])
    _require(captured <= now + timedelta(seconds=5))
    pages = capture["pages"]
    _require(isinstance(pages, list) and 1 <= len(pages) <= MAX_PAGES)
    cursor = None
    seen = set()
    events = []
    count = 0
    for index, page in enumerate(pages):
        _require(isinstance(page, dict) and set(page) == {"request_cursor", "response"}
                 and page["request_cursor"] == cursor)
        response = page["response"]
        _require(isinstance(response, dict) and "error" not in response
                 and "errors" not in response and response.get("proof_token_required") is not True)
        rows, pagination = response.get("data"), response.get("pagination")
        _require(isinstance(rows, list) and isinstance(pagination, dict)
                 and {"next_uri", "starting_after", "ending_before", "order", "limit"} <= set(pagination))
        limit = pagination["limit"]
        _require(type(limit) is int and 1 <= limit <= 100 and len(rows) <= limit
                 and pagination["starting_after"] == cursor
                 and pagination["ending_before"] is None and pagination["order"] == "desc")
        next_cursor = _cursor(pagination["next_uri"], path)
        _require((next_cursor is not None) == (index < len(pages) - 1))
        last_id = None
        for row in rows:
            count += 1
            _require(count <= MAX_RECORDS and isinstance(row, dict))
            ident = _uuid(row.get("id"))
            _require(ident not in seen and row.get("resource") == "transaction"
                     and row.get("resource_path") == path + "/" + ident)
            seen.add(ident)
            last_id = ident
            kind, status = row.get("type"), row.get("status")
            _require(isinstance(kind, str) and bool(re.fullmatch(r"[a-z_]{1,64}", kind))
                     and isinstance(status, str) and bool(re.fullmatch(r"[a-z_]{1,64}", status)))
            created = _provider_time(row.get("created_at"))
            _require(created <= captured + timedelta(seconds=5))
            if kind != "receive":
                continue
            money = row.get("amount")
            _require(isinstance(money, dict))
            amount, asset = money.get("amount"), money.get("currency")
            _require(isinstance(amount, str) and len(amount) <= 80
                     and bool(re.fullmatch(r"(0|[1-9][0-9]*)(\.[0-9]+)?", amount))
                     and Decimal(amount) > 0 and isinstance(asset, str)
                     and bool(re.fullmatch(r"[A-Za-z0-9]{2,12}", asset)))
            events.append({"event_id": sha256(f"{account}:{ident}".encode()).hexdigest(),
                "source_event_timestamp_utc": created.isoformat(), "asset": asset,
                "quantity_reported": amount,
                "status": status.upper() if status in {"completed", "pending", "failed", "canceled"} else "UNKNOWN",
                "onchain_reconciliation_eligible": False,
                "blockchain_linkage": "NOT_GUARANTEED_FOR_RECEIVE_BY_PROVIDER_CONTRACT"})
        if next_cursor is not None:
            _require(last_id is not None and next_cursor == last_id and next_cursor != cursor)
        cursor = next_cursor
    return {"source": "OPERATOR_SUPPLIED_COINBASE_APP_CAPTURE_NOT_AUTHENTICATED",
        "captured_at_utc": captured.isoformat(), "page_count": len(pages),
        "observed_record_count": count, "excluded_non_receive_count": count - len(events),
        "event_count": len(events), "events": events, "pagination_chain_complete": True,
        "snapshot_completeness_certified": False, "complete_funding_history_certified": False,
        "coinbase_provenance_verified": False, "balances_adjusted": False}


def review_bundle(bundle, now):
    """Keep observed receives separate from operator-supplied chain/deposit claims."""
    _require(isinstance(bundle, dict) and set(bundle) == {
        "mode", "history", "network_transfers", "deposit_records"} and bundle["mode"] == BUNDLE_MODE)
    history = normalize_receives(bundle["history"], now)
    matches = reconcile(bundle["network_transfers"], bundle["deposit_records"])
    return {"mode": "PRIVATE_OFFLINE_DEPOSIT_REVIEW", "history": history,
        "operator_evidence_reconciliation": matches,
        "receive_events_linked_to_chain": False, "sources_summed": False,
        "financial_operations": 0, "balances_adjusted": False}


def main(argv=None):
    from scripts.operational_read_only import read_private, write_private
    parser = argparse.ArgumentParser(description="Private offline deposit-history review")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--at", help="UTC validation time; defaults to now")
    args = parser.parse_args(argv)
    try:
        now = _time(args.at) if args.at else datetime.now(timezone.utc)
        report = review_bundle(read_private(args.input), now)
        write_private(args.output, report)
    except (ValueError, OSError, TypeError, OverflowError):
        print("DEPOSIT_HISTORY_PRIVATE_REVIEW_REJECTED")
        return 2
    print("DEPOSIT_HISTORY_PRIVATE_REVIEW_READY financial_operations=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
