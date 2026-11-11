"""v0.25 controlled acquisition: local provider XLSX + official exact-day NBP raw evidence.

No provider scraping or browser clicks; first wait until completed month,
then validate the new original workbook against the frozen baseline. Only
after zero historical revisions may caller opt in to one official NBP HTTPS
read. Raw NBP bytes are archived locally in a new private, exclusive file.
No financial execution, transaction, accounts, database or scheduler.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path

from scripts.nav_forward_preflight_v24 import preflight
from scripts.nav_forward_admission_v23 import _utc
from scripts.nav_forward_admission_v26 import admission
from scripts.nav_forward_freeze_v22 import verify_pending
from scripts.vanguard_xlsx_offline_intake_v04 import inspect_export
from scripts.vanguard_nav_intake_bundle_v04 import _fetch_public_fx, _parse_fx
from scripts.conditional_m1_nav_diagnostic_v20 import evaluate_nav_reference
from scripts.reference_archive_calendar_v04 import _digest

SCHEMA = "ISL_NAV_FX_EVIDENCE_CAPTURE_V25_001"


def collect(frozen, baseline, *, raw_xlsx=None, xlsx_retrieved_at_utc=None,
            allow_nbp_fetch=False, fetch=None, clock=lambda: datetime.now(timezone.utc)):
    """Return public-metadata summary and optionally private raw NBP bytes."""
    now = clock()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("timezone-aware UTC clock required")
    now = now.astimezone(timezone.utc)
    old = evaluate_nav_reference(baseline)
    if (old["source_evidence_sha256"] != frozen.get("source_evidence_sha256")
            or old["nav_file_sha256"] != frozen.get("original_nav_file_sha256")):
        raise ValueError("baseline differs from frozen source")
    check = admission(frozen, clock=lambda: now)
    out = {
        "schema": SCHEMA,
        "status": "PENDING_NEW_PROVIDER_EXPORT",
        "frozen_sha256": check["freeze_receipt_sha256"],
        "historical_baseline_sha256": baseline["evidence_sha256"],
        "first_forward_month": "2026-11",
        "provider_original_sha256": None,
        "nbp_original_sha256": None,
        "nbp_observed_for": None,
        "historical_revision_count": None,
        "historical_revision_months": [],
        "prospective_qualified_months": 0,
        "strict_m1_qualified": False,
        "original_provider_identity_independently_attested": False,
        "source_rights_verified": False,
        "real_trading": False,
        "financial_operations": 0,
        "database_writes": 0,
    }
    if raw_xlsx is None:
        if allow_nbp_fetch:
            raise ValueError("official FX fetch requires a new provider XLSX")
        out["receipt_sha256"] = _digest(out)
        return out, None
    if now.date() < date(2026,12,1):
        raise ValueError("month incomplete: no provider/FX capture before December")
    at = _utc(xlsx_retrieved_at_utc)
    freeze_at = _utc(frozen["frozen_at_utc"])
    if not freeze_at < at <= now:
        raise ValueError("provider retrieval must postdate freeze and not be future")
    if at.date() < date(2026,12,1):
        raise ValueError("original provider export predates completed forward month")
    incoming = inspect_export(raw_xlsx, "2021-11", "2026-11", as_of=now.date())
    out["provider_original_sha256"] = incoming["raw_export_sha256"]
    if out["provider_original_sha256"] == frozen["original_nav_file_sha256"]:
        raise ValueError("provider original SHA identical to frozen original")
    history = {r["month"]:r for r in baseline["monthly"]}
    # Numeric equality: identical source NAV with trailing-zero formatting is
    # not a historical revision. Never round or use binary floats.
    def parsed_nav(row):
        value=row["nav_usd"]
        if not isinstance(value,str):
            raise ValueError("decimal-string NAV required for history comparison")
        try:
            nav=Decimal(value)
        except (ValueError, InvalidOperation) as exc:
            raise ValueError("invalid historical NAV decimal") from exc
        if not nav.is_finite() or nav<=0:
            raise ValueError("historical NAV must be positive and finite")
        return nav

    revisions = [r["month"] for r in incoming["monthly"][:-1]
                 if (r["observed_for"] != history[r["month"]]["observed_for"]
                     or parsed_nav(r) != parsed_nav(history[r["month"]]))]
    out["historical_revision_count"] = len(revisions)
    out["historical_revision_months"] = revisions
    if revisions:
        out["status"] = "BLOCKED_PROVIDER_REVISIONS_NEED_REVIEW"
        out["receipt_sha256"] = _digest(out)
        return out, None
    row = incoming["monthly"][-1]
    observed = row["observed_for"]
    if at.date() <= date.fromisoformat(observed):
        raise ValueError("provider export must be retrieved after observation date")
    out["nbp_observed_for"] = observed
    if not allow_nbp_fetch:
        out["status"] = "READY_FOR_EXPLICIT_NBP_SOURCE_READ"
        out["receipt_sha256"] = _digest(out)
        return out, None
    if fetch is None:
        fetch = _fetch_public_fx
    url = f"https://api.nbp.pl/api/exchangerates/tables/a/{observed}/{observed}/?format=json"
    raw_nbp = fetch(url)
    captured_at = clock().astimezone(timezone.utc)
    fx = _parse_fx(observed, url, raw_nbp, captured_at.isoformat())
    # The exact original raw response is evaluated by v0.24 + v0.23,
    # not only a hand-written USDPLN number.
    evaluated = preflight(frozen, baseline, raw_export=raw_xlsx,
                          raw_nbp=raw_nbp,
                          export_retrieved_at_utc=xlsx_retrieved_at_utc,
                          nbp_retrieved_at_utc=captured_at.isoformat(),
                          clock=lambda: captured_at)
    if evaluated["historical_revisions_count"] != 0 or evaluated[
            "status"] != "CANDIDATE_FORWARD_REFERENCE_REQUIRES_INDEPENDENT_SOURCE_REVIEW":
        raise ValueError("candidate was not admitted by v0.24")
    out["status"] = "PRIVATE_OFFICIAL_NBP_CAPTURED_CANDIDATE_ONLY"
    out["nbp_original_sha256"] = sha256(raw_nbp).hexdigest()
    out["nbp_api_url"] = url
    out["nbp_retrieved_at_utc"] = captured_at.isoformat()
    out["prospective_candidate_sha256"] = evaluated["candidate_sha256"]
    out["nbp_quote_type"] = fx["source"]
    out["receipt_sha256"] = _digest(out)
    return out, raw_nbp


def _private_path(path, max_bytes):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError("bounded regular private file required")
    return path.read_bytes()



def _write_private_raw(dest, raw):
    """Exclusive original-byte write, never a permissive intermediate file."""
    dest = Path(dest)
    dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--new-xlsx", type=Path)
    p.add_argument("--xlsx-retrieved-at-utc")
    p.add_argument("--fetch-official-nbp", action="store_true")
    p.add_argument("--private-nbp-out", type=Path)
    args = p.parse_args()
    if args.fetch_official_nbp != (args.private_nbp_out is not None):
        p.error("--fetch-official-nbp requires --private-nbp-out and vice versa")
    srcs = [args.freeze, args.baseline]
    if args.new_xlsx is not None:
        srcs.append(args.new_xlsx)
    if args.private_nbp_out is not None and (
            args.private_nbp_out.exists() or args.private_nbp_out.is_symlink()
            or args.private_nbp_out.resolve() in {x.resolve() for x in srcs}):
        p.error("output must be a fresh path separate from all inputs")
    frozen = json.loads(_private_path(args.freeze, 3_000_000))
    baseline = json.loads(_private_path(args.baseline, 3_000_000))
    raw = _private_path(args.new_xlsx, 15_000_000) if args.new_xlsx else None
    out, nbp = collect(frozen,baseline,raw_xlsx=raw,
                       xlsx_retrieved_at_utc=args.xlsx_retrieved_at_utc,
                       allow_nbp_fetch=args.fetch_official_nbp)
    if nbp is not None:
        # File must be private; never write to repo, shared runner or Neon.
        _write_private_raw(args.private_nbp_out, nbp)
    print("ISL_NAV_FX_CAPTURE_V25="+
          json.dumps(out, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
