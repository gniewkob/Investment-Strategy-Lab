"""Fail-closed common monthly research calendar; no trading or Neon writes.

This is an *evidence inventory*, not a backtest authorisation. A publication
date without an authenticated timestamp is usable no earlier than the next
explicitly supplied trading session. This is a conservative modelling rule,
NOT proof of point-in-time vintage, licensing, or actual availability.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

from scripts.data_readiness_v1 import MODELS, SERIES

SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _date(value):
    if not isinstance(value, str):
        raise ValueError("date required")
    return date.fromisoformat(value)


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return result


def _ordered_days(values, field):
    if not isinstance(values, list):
        raise ValueError(field + " must be a list")
    days = [_date(value) for value in values]
    if days != sorted(set(days)):
        raise ValueError(field + " must contain unique increasing dates")
    return days


def _check_row(row, name, sessions):
    if not isinstance(row, dict):
        raise ValueError("row must be an object")
    observed = _date(row["observed_for"])
    published = _date(row["publication_date"])
    retrieved = _timestamp(row["retrieved_at"])
    if published < observed or retrieved.date() < published:
        raise ValueError("impossible publication/retrieval chronology")
    try:
        val = Decimal(str(row["value"]))
    except (InvalidOperation, TypeError):
        raise ValueError("invalid value") from None
    if not val.is_finite() or val < 0 or (name != "costs" and val == 0):
        raise ValueError("nonpositive or nonfinite value")
    if not isinstance(row.get("source_url"), str) or not row["source_url"].startswith("https://"):
        raise ValueError("source URL required")
    if not isinstance(row.get("source_sha256"), str) or not SHA256.fullmatch(row["source_sha256"]):
        raise ValueError("source SHA-256 required")
    if not row.get("currency") or not row.get("basis"):
        raise ValueError("currency and basis required")
    # Never infer a historical timestamp from today's retrieval timestamp.
    usable_day = next((day for day in sessions if day > published), None)
    return {
        "observed_for": observed.isoformat(),
        "publication_date": published.isoformat(),
        "retrieved_at": retrieved.isoformat(),
        "first_usable_session": usable_day.isoformat() if usable_day else None,
        "historical_vintage_verified": row.get("historical_vintage_verified") is True,
        "license_verified": row.get("license_status") == "verified_permitted",
        "source_sha256": row["source_sha256"].lower(),
        "source_url": row["source_url"],
        "basis": row["basis"],
        "currency": row["currency"],
    }


def assess_calendar(manifest):
    """Create an indicative common calendar, never a certified simulation."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    sessions = _ordered_days(manifest.get("sessions", []), "sessions")
    decisions = _ordered_days(manifest.get("decision_dates", []), "decision_dates")
    if any(day not in sessions for day in decisions):
        raise ValueError("decisions must be listed trading sessions")
    if not sessions or not decisions:
        raise ValueError("nonempty sessions and decisions required")
    series = manifest.get("series")
    if not isinstance(series, dict) or set(series) - set(SERIES):
        raise ValueError("invalid series keys")

    normalized = {}
    issues = {}
    for name in SERIES:
        rows = series.get(name, [])
        if not isinstance(rows, list):
            raise ValueError("series rows must be a list")
        good, problems, seen = [], [], set()
        for index, row in enumerate(rows):
            try:
                candidate = _check_row(row, name, sessions)
                day = candidate["observed_for"]
                if day in seen:
                    raise ValueError("duplicate observation date")
                seen.add(day)
                good.append(candidate)
            except (KeyError, ValueError, TypeError, OverflowError) as exc:
                problems.append({"row": index, "issue": str(exc)})
        good.sort(key=lambda x: x["observed_for"])
        normalized[name], issues[name] = good, problems

    coverage = []
    for decision in decisions:
        selected, missing = {}, []
        for name in SERIES:
            candidates = [
                row for row in normalized[name]
                if row["first_usable_session"] is not None
                and row["first_usable_session"] <= decision.isoformat()
                and row["observed_for"] <= decision.isoformat()
            ]
            if not candidates:
                missing.append(name)
                continue
            latest = candidates[-1]
            selected[name] = {
                "observed_for": latest["observed_for"],
                "first_usable_session": latest["first_usable_session"],
                "historical_vintage_verified": latest["historical_vintage_verified"],
                "license_verified": latest["license_verified"],
                "lag_months": (decision.year - _date(latest["observed_for"]).year) * 12
                    + decision.month - _date(latest["observed_for"]).month,
            }
        coverage.append({
            "decision_session": decision.isoformat(),
            "available_series": selected,
            "missing_series": missing,
            "all_series_present": not missing,
            "historical_pit_certified": False,
        })
    return {
        "status": "INSUFFICIENT_DATA",
        "models": {model: "INSUFFICIENT_DATA" for model in MODELS},
        "backtest": "NOT_RUN",
        "paper_events_created": 0,
        "calendar_rule": "next_explicit_trading_session_after_publication_date",
        "caveat": "Indicative only: input claims do not verify vintage, entitlement, publication time, or total-return validity.",
        "series": {name: {"accepted_rows": len(normalized[name]), "issues": issues[name]}
                   for name in SERIES},
        "coverage_by_decision": coverage,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(assess_calendar(json.loads(args.manifest.read_text(encoding="utf-8"))),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
