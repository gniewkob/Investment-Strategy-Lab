"""Offline Coinbase App List Transactions capture import. No HTTP or credentials.

Receive and generic tx events are retained in separate lists. Network identifiers from receive records are
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
from scripts.deposit_evidence_reconciliation import reconcile_inventory

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
    unclassified = []
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
            _require(isinstance(kind, str) and bool(re.fullmatch(r"[a-z][a-z0-9_]{0,63}", kind))
                     and isinstance(status, str) and bool(re.fullmatch(r"[a-z_]{1,64}", status)))
            created = _provider_time(row.get("created_at"))
            _require(created <= captured + timedelta(seconds=5))
            if kind not in {"receive", "tx"}:
                continue
            # Prior runtime versions intentionally omitted amounts for non-receive
            # records. Preserve these legacy tx observations as UNKNOWN, never zero.
            amount = asset = None
            if not (kind == "tx" and "amount" not in row):
                money = row.get("amount")
                _require(isinstance(money, dict))
                amount, asset = money.get("amount"), money.get("currency")
                pattern = r"-?(0|[1-9][0-9]*)(\.[0-9]+)?" if kind == "tx" else r"(0|[1-9][0-9]*)(\.[0-9]+)?"
                _require(isinstance(amount, str) and len(amount) <= 80
                         and bool(re.fullmatch(pattern, amount))
                         and (kind == "tx" or Decimal(amount) > 0) and isinstance(asset, str)
                         and bool(re.fullmatch(r"[A-Za-z0-9]{2,12}", asset)))
            event = {"event_id": sha256(f"{account}:{ident}".encode()).hexdigest(),
                "source_event_timestamp_utc": created.isoformat(), "asset": asset,
                "quantity_reported": amount,
                "status": status.upper() if status in {"completed", "pending", "failed", "canceled"} else "UNKNOWN",
                "onchain_reconciliation_eligible": False}
            if kind == "receive":
                event["blockchain_linkage"] = "NOT_GUARANTEED_FOR_RECEIVE_BY_PROVIDER_CONTRACT"
                events.append(event)
            else:
                value = Decimal(amount) if amount is not None else None
                event.update({"source_transaction_type": "tx", "classification": "UNCLASSIFIED_ACCOUNT_EVENT",
                    "amount_status": "REPORTED" if amount is not None else "NOT_CAPTURED_UNKNOWN",
                    "direction": "UNKNOWN" if value is None else "ACCOUNT_CREDIT" if value > 0 else "ACCOUNT_DEBIT" if value < 0 else "ZERO_REPORTED",
                    "external_funding_certified": False,
                    "blockchain_linkage": "NOT_ESTABLISHED_BY_SOURCE_SCHEMA"})
                unclassified.append(event)
        if next_cursor is not None:
            _require(last_id is not None and next_cursor == last_id and next_cursor != cursor)
        cursor = next_cursor
    return {"source": "OPERATOR_SUPPLIED_COINBASE_APP_CAPTURE_NOT_AUTHENTICATED",
        "captured_at_utc": captured.isoformat(), "page_count": len(pages),
        "observed_record_count": count, "excluded_non_receive_count": count - len(events),
        "event_count": len(events), "events": events, "pagination_chain_complete": True,
        "unclassified_account_events": unclassified, "unclassified_account_event_count": len(unclassified),
        "excluded_other_event_count": count - len(events) - len(unclassified),
        "absence_of_receive_proves_no_funding": False,
        "snapshot_completeness_certified": False, "complete_funding_history_certified": False,
        "coinbase_provenance_verified": False, "balances_adjusted": False}


def compare_receive_captures(previous, current, now):
    """Compare observations, never infer new funding or deletion from visibility.

    Both untrusted page chains must validate independently for the same account.
    Amount/asset/time mutations outrank status changes and remain evidence conflicts.
    """
    before = normalize_receives(previous, now)
    after = normalize_receives(current, now)
    _require(previous["account_id"] == current["account_id"]
             and _time(previous["captured_at"]) < _time(current["captured_at"]))
    old = {e["event_id"]: e for e in before["events"]}
    new = {e["event_id"]: e for e in after["events"]}
    changes = []
    unchanged = 0
    for ident in sorted(old.keys() | new.keys()):
        earlier, later = old.get(ident), new.get(ident)
        changed_fields = []
        if earlier is None:
            classification = "NEWLY_OBSERVED_NOT_NEW_FUNDING"
        elif later is None:
            classification = "NOT_OBSERVED_IN_CURRENT_CAPTURE"
        else:
            for field in ("asset", "quantity_reported", "source_event_timestamp_utc"):
                equal = (Decimal(earlier[field]) == Decimal(later[field])
                         if field == "quantity_reported" else earlier[field] == later[field])
                if not equal:
                    changed_fields.append(field)
            if changed_fields:
                classification = "CONFLICTING_RECEIVE_RECORD"
            elif earlier["status"] != later["status"]:
                classification = "STATUS_CHANGED_NOT_NEW_FUNDING"
            else:
                unchanged += 1
                continue
        changes.append({"event_id": ident, "classification": classification,
            "changed_fields": changed_fields,
            "previous_status": earlier["status"] if earlier else None,
            "current_status": later["status"] if later else None})
    return {"scope": "SAME_OPERATOR_ACCOUNT_CAPTURES_ONLY",
        "records_compared": "RECEIVE_ONLY", "unclassified_account_events_compared": False,
        "previous_captured_at_utc": before["captured_at_utc"],
        "current_captured_at_utc": after["captured_at_utc"],
        "previous_receive_count": len(old), "current_receive_count": len(new),
        "unchanged_receive_count": unchanged, "changes": changes,
        "new_external_funding_certified": False, "missing_means_deleted": False,
        "coinbase_provenance_verified": False, "balances_adjusted": False}


def review_bundle(bundle, now, *, previous_history=None):
    """Keep observed receives separate from operator-supplied chain/deposit claims."""
    _require(isinstance(bundle, dict) and set(bundle) == {
        "mode", "history", "network_transfers", "deposit_records"} and bundle["mode"] == BUNDLE_MODE)
    history = normalize_receives(bundle["history"], now)
    inventory = reconcile_inventory(bundle["network_transfers"], bundle["deposit_records"])
    report = {"mode": "PRIVATE_OFFLINE_DEPOSIT_REVIEW", "history": history,
        "operator_evidence_reconciliation": inventory["network_results"],
        "operator_evidence_coverage": {k: v for k, v in inventory.items() if k != "network_results"},
        "receive_events_linked_to_chain": False, "sources_summed": False,
        "financial_operations": 0, "balances_adjusted": False}
    if previous_history is not None:
        report["receive_history_comparison"] = compare_receive_captures(
            previous_history, bundle["history"], now)
    return report


def main(argv=None):
    from scripts.operational_read_only import read_private, write_private
    parser = argparse.ArgumentParser(description="Private offline deposit-history review")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--at", help="UTC validation time; defaults to now")
    parser.add_argument("--previous-history", help="Private earlier capture for the same account")
    args = parser.parse_args(argv)
    try:
        now = _time(args.at) if args.at else datetime.now(timezone.utc)
        previous = read_private(args.previous_history) if args.previous_history else None
        report = review_bundle(read_private(args.input), now, previous_history=previous)
        write_private(args.output, report)
    except (ValueError, OSError, TypeError, OverflowError):
        print("DEPOSIT_HISTORY_PRIVATE_REVIEW_REJECTED")
        return 2
    print("DEPOSIT_HISTORY_PRIVATE_REVIEW_READY financial_operations=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
