"""Offline research bridge for supplied monthly EUR equity and PLN/EUR marks.

Values are caller-supplied, not authenticated, licensed or PIT-certified here.
No market data is downloaded and no price is claimed to be an executable fill.
"""
from copy import deepcopy
from datetime import date
from decimal import localcontext
from hashlib import sha256
import json

from scripts.paper_multi_asset_research_v02 import (
    MultiAssetBlocked, compare, number, validated_manifest,
)


def compare_with_equity_marks(manifest, marks):
    """Replace ASSET_A with EUR equity mark times PLN per EUR reference FX.

    Each mark is for the same calendar month as its two dated inputs. The
    observations may be asynchronous by up to seven days; this is descriptive
    valuation, not a simulation of an obtainable execution or PIT knowledge.
    Other assets and all strategy assumptions remain explicitly caller supplied.
    """
    validated_manifest(manifest)
    if manifest["source_class"] != "UNVERIFIED_EXTERNAL":
        raise MultiAssetBlocked("EXTERNAL_MARKS_REQUIRE_UNVERIFIED_SOURCE")
    if type(marks) is not list or len(marks) != len(manifest["observations"]):
        raise MultiAssetBlocked("EQUITY_MARK_COUNT_MISMATCH")
    payload = deepcopy(manifest)
    fields = {"month", "equity_date", "equity_eur", "fx_date", "pln_per_eur"}
    receipt = []
    for row, observation in zip(marks, payload["observations"]):
        if type(row) is not dict or set(row) != fields or row["month"] != observation["month"]:
            raise MultiAssetBlocked("EQUITY_MARK_SCHEMA_OR_MONTH_INVALID")
        try:
            equity_date = date.fromisoformat(row["equity_date"])
            fx_date = date.fromisoformat(row["fx_date"])
            if equity_date.isoformat() != row["equity_date"] or fx_date.isoformat() != row["fx_date"]:
                raise ValueError
        except (ValueError, TypeError) as exc:
            raise MultiAssetBlocked("EQUITY_MARK_DATE_INVALID") from exc
        if (equity_date.strftime("%Y-%m") != row["month"] or
                fx_date.strftime("%Y-%m") != row["month"] or
                abs((equity_date - fx_date).days) > 7):
            raise MultiAssetBlocked("EQUITY_FX_DATE_MISMATCH")
        equity = number(row["equity_eur"], positive=True)
        fx = number(row["pln_per_eur"], positive=True)
        with localcontext() as ctx:
            ctx.prec = 48
            level = equity * fx
        observation["levels_pln"]["ASSET_A"] = format(level, "f")
        receipt.append({"month": row["month"], "equity_date": row["equity_date"],
                        "fx_date": row["fx_date"]})
    report = compare(payload)
    report["equity_bridge"] = {
        "status": "UNVERIFIED_CALLER_SUPPLIED_RETROSPECTIVE_MARKS",
        "equity_currency": "EUR", "fx_unit": "PLN_PER_EUR",
        "price_basis": "EQUITY_MARK_TIMES_REFERENCE_FX_NOT_EXECUTION",
        "source_identity_rights_and_completeness_verified": False,
        "marks_sha256": sha256(json.dumps(marks, sort_keys=True, separators=(",", ":"),
                                         allow_nan=False).encode("utf-8")).hexdigest(),
        "dates": receipt,
    }
    return report
