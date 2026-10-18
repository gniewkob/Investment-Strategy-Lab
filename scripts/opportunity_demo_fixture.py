"""Generate fake, deterministic educational prices for CI end-to-end tests.

Numbers are ARTIFICIAL and have no relationship with actual market prices.
No finance data retrieval, Neon connection, brokers or external requests.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path


def generate() -> dict:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = []
    for name, start_price, rhythm in (
        ("BTC-USD", 100.0, 0.28),
        ("ETH-USD", 100.0, 0.39),
    ):
        price = start_price
        for day in range(180):
            if day:
                movement = math.sin(day * rhythm) * 0.005
                if day in (121, 133, 149, 164):
                    movement += 0.115 if name == "BTC-USD" else -0.085
                price *= (1 + movement)
            records.append({
                "instrument_code": name,
                "interval_code": "1d",
                "return_basis": "PRICE_ONLY",
                "observed_for": (start + timedelta(days=day)).isoformat(),
                "ingested_at": "2026-10-17T20:00:00+00:00",
                "close_price": f"{price:.8f}",
            })
    return {
        "mode": "RETROSPECTIVE_RESEARCH_ONLY",
        "dataset_kind": "SYNTHETIC_OFFLINE_FIXTURE",
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "as_of": "2026-10-18T18:00:00+00:00",
        "records": records,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Synthetic fake price fixture")
    ap.add_argument("--output", required=True)
    path = Path(ap.parse_args().output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(generate(), ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("SYNTHETIC_EDUCATIONAL_PRICE_FIXTURE", len(generate()["records"]))


if __name__ == "__main__":
    main()
