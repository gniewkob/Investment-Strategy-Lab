"""Offline, paper-only evidence inventory; never creates prices or transactions."""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path

SERIES = ("equity", "bonds", "gold", "usdpln", "eurpln", "inflation", "costs")
MODELS = ("M1_GLOBAL_EQ", "M2_DIVERSIFIED", "M3_TACTICAL")


def assess(data: dict) -> dict:
    """Inventory provenance; a pass is NOT authorization to run a backtest."""
    if not isinstance(data, dict):
        raise ValueError("expected object")
    result = {}
    for name in SERIES:
        item = data.get(name, {})
        if not isinstance(item, dict):
            raise ValueError("invalid series")
        reasons = []
        for field in ("source_url", "license_status", "instrument_kind", "currency", "basis"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                reasons.append("missing_" + field)
        if item.get("license_status") != "verified_permitted":
            reasons.append("license_unverified")
        if name in ("equity", "bonds") and item.get("basis") != "total_return":
            reasons.append("total_return_unverified")
        if name == "bonds" and item.get("market") != "PLN_POLISH_GOVERNMENT":
            reasons.append("bond_market_unverified")
        rows = item.get("observations", [])
        if not isinstance(rows, list):
            raise ValueError("invalid observations")
        if not rows:
            reasons.append("no_observations")
        seen = set()
        for row in rows:
            try:
                observed = date.fromisoformat(row["observed_for"])
                available = datetime.fromisoformat(row["available_at"].replace("Z", "+00:00"))
                retrieved = datetime.fromisoformat(row["retrieved_at"].replace("Z", "+00:00"))
                value = float(row["value"])
                if available.tzinfo is None or retrieved.tzinfo is None or available.date() < observed or retrieved < available:
                    raise ValueError
                if not 0 < value < float("inf") or observed in seen:
                    raise ValueError
                seen.add(observed)
            except (KeyError, ValueError, TypeError, AttributeError):
                reasons.append("invalid_or_duplicate_observation")
        # Evidence inventory does not certify consecutive periods, vintage,
        # source authenticity, costs, or OOS sufficiency from user assertions.
        reasons.append("independent_pit_and_coverage_review_required")
        result[name] = {"status": "INSUFFICIENT_DATA", "observations": len(rows), "reasons": sorted(set(reasons))}
    return {"series": result, "models": {m: "INSUFFICIENT_DATA" for m in MODELS},
            "backtest": "NOT_RUN", "paper_events_created": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(assess(json.loads(args.manifest.read_text())), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
