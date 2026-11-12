"""Official Eurostat monthly Polish sovereign convergence-yield source shape probe.

No model data, account access, trades, databases or local files. One-shot
explicit opt-in. Logs *schema only*, never values, yields or series.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

ROOT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/irt_lt_mcby_m"
ARGS = (
    ("lang", "EN"), ("freq", "M"), ("int_rt", "MCBY"), ("geo", "PL"),
    ("sinceTimePeriod", "2021-11"), ("untilTimePeriod", "2026-09"),
)
URL = ROOT + "?" + urlencode(ARGS)
MAX_BYTES = 600_000


class PublicEurostatProbeBlocked(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise PublicEurostatProbeBlocked("REDIRECT_REJECTED")


def fetch_official() -> bytes:
    """One official allowlisted HTTPS request, never redirect to third party."""
    req = Request(URL, headers={"Accept": "application/json",
                                 "User-Agent": "ISL-edu-public-source/1"})
    opener = build_opener(NoRedirect(), HTTPSHandler())
    with opener.open(req, timeout=25) as response:
        if response.status != 200 or response.geturl() != URL:
            raise PublicEurostatProbeBlocked("OFFICIAL_RESPONSE_STATUS_OR_URL_CHANGED")
        content = response.read(MAX_BYTES + 1)
    if not content or len(content) > MAX_BYTES:
        raise PublicEurostatProbeBlocked("SOURCE_RESPONSE_OUT_OF_BOUNDS")
    return content


def inspect_source_shape(raw: object, *, observed_at: datetime) -> dict:
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES:
        raise PublicEurostatProbeBlocked("SOURCE_RESPONSE_OUT_OF_BOUNDS")
    if (not isinstance(observed_at, datetime) or observed_at.tzinfo is None
            or observed_at.utcoffset() is None):
        raise PublicEurostatProbeBlocked("UTC_AWARE_OBSERVATION_CLOCK_REQUIRED")
    try:
        data = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PublicEurostatProbeBlocked("NOT_OFFICIAL_JSON") from exc
    if (not isinstance(data, dict) or data.get("version") != "2.0"
            or data.get("class") != "dataset"
            or data.get("source") not in ("ESTAT", "Eurostat")
            or not isinstance(data.get("id"), list)
            or not isinstance(data.get("size"), list)
            or not isinstance(data.get("dimension"), dict)):
        raise PublicEurostatProbeBlocked("JSONSTAT_STRUCTURE_NOT_MATCHED")
    dims = data["dimension"]
    names = data["id"]
    if (not 1 <= len(names) <= 7 or len(names) != len(set(names))
            or set(names) != set(dims) or len(data["size"]) != len(names)):
        raise PublicEurostatProbeBlocked("DIMENSIONS_INCOHERENT")
    codes = {}
    for name, count in zip(names, data["size"]):
        if (not isinstance(name, str) or not name.isidentifier()
                or type(count) is not int or not 1 <= count <= 120
                or not isinstance(dims[name], dict)):
            raise PublicEurostatProbeBlocked("DIMENSION_INVALID")
        cat = dims[name].get("category")
        ix = cat.get("index") if isinstance(cat, dict) else None
        if not isinstance(ix, dict) or len(ix) != count:
            raise PublicEurostatProbeBlocked("CATEGORIES_INVALID")
        codes[name] = sorted(str(k) for k in ix)
    # No raw data or complete time series is ever printed/returned.
    return {
        "schema": "ISL_PUBLIC_EUROSTAT_PL_BONDS_YIELD_SHAPE_PROBE_V04",
        "source": "Eurostat",
        "dataset": "irt_lt_mcby_m",
        "query": URL,
        "source_bytes_sha256": sha256(raw).hexdigest(),
        "observed_by_runner_at_utc": observed_at.astimezone(timezone.utc).isoformat(),
        "dimensions": names,
        "sizes": data["size"],
        "fixed_category_codes": {k: v for k, v in codes.items() if k != "time"},
        "time_first": codes["time"][0] if "time" in codes else None,
        "time_last": codes["time"][-1] if "time" in codes else None,
        "time_count": len(codes.get("time", [])),
        "provider_updated_not_first_release": str(data.get("updated", "UNKNOWN"))[:50],
        "actual_rate_values_in_output": False,
        "historical_pit_certified": False,
        "bond_holding_period_total_return": False,
        "qualified_model_series": [],
        "financial_operations": 0,
        "database_writes": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-eurostat-read", action="store_true")
    args = parser.parse_args()
    if not args.allow_public_eurostat_read:
        parser.error("explicit --allow-public-eurostat-read required")
    result = inspect_source_shape(fetch_official(),
                                  observed_at=datetime.now(timezone.utc))
    print("ISL_PUBLIC_EUROSTAT_PL_YIELD_SHAPE=" +
          json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
