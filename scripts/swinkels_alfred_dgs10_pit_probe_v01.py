"""One-shot ALFRED DGS10 point-in-time evidence probe (research only).

Scans 3 historical *daily* observations by archived as-of date using the
official FRED observations API. Compares to original Swinkels US monthly
DGS10 ODS values, but never treats equality as PIT qualification.

Requires GitHub Actions FRED_API_KEY secret. If absent, emits BLOCKED status
and performs no request. Key is never printed, persisted, or forwarded.
No current-mode fallback, no heuristic units, no trading or model admission.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from scripts.research_swinkels_original_source_probe_v01 import (
    PUBLISHER, SourceUnavailable, fetch,
)
from scripts.swinkels_original_us_equation3_audit_v01 import (
    FILE_ID, extract_original_us,
)

OFFICIAL_API = "https://api.stlouisfed.org/fred/series/observations"
SERIES_ID = "DGS10"
MAX_REPLY_BYTES = 120_000
MAX_GAP_PCT_POINTS = 1e-8
# Each as-of date is deliberately after month-end. This tests whether an
# archived snapshot exists by that later date, NOT decision-day eligibility.
CHECKS = (
    ("2020-01", "2020-01-31", "2020-02-15"),
    ("2021-06", "2021-06-30", "2021-07-15"),
    ("2022-12", "2022-12-30", "2023-01-15"),
)


def validate_api_key(key):
    if not isinstance(key, str) or re.fullmatch(r"[a-z0-9]{32}", key) is None:
        raise SourceUnavailable("FRED_API_KEY absent or invalid format")
    return key


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward the API key in the URL to another host.
        raise SourceUnavailable("ALFRED API redirect blocked")


def parse_snapshot(data: bytes, observed_date: str, asof_date: str):
    if not isinstance(data, bytes) or len(data) > MAX_REPLY_BYTES:
        raise SourceUnavailable("ALFRED reply missing or too large")
    try:
        doc = json.loads(data)
    except (UnicodeError, ValueError) as exc:
        raise SourceUnavailable("ALFRED reply is not valid JSON") from exc
    if not isinstance(doc, dict):
        raise SourceUnavailable("ALFRED reply must be an object")
    observations = doc.get("observations")
    if not isinstance(observations, list) or len(observations) != 1:
        raise SourceUnavailable("ALFRED response does not identify one observation")
    item = observations[0]
    if not isinstance(item, dict) or item.get("date") != observed_date:
        raise SourceUnavailable("ALFRED observation date mismatch")
    if item.get("realtime_start") != asof_date or item.get("realtime_end") != asof_date:
        raise SourceUnavailable("ALFRED archived as-of time not confirmed")
    raw = item.get("value")
    if not isinstance(raw, str) or not re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{1,10})?", raw):
        raise SourceUnavailable("ALFRED historical daily yield missing or invalid")
    value = float(raw)
    if not math.isfinite(value):
        raise SourceUnavailable("ALFRED nonfinite daily yield")
    return value


def _request_snapshot(key, observation_date: str, asof_date: str):
    validate_api_key(key)
    query = urllib.parse.urlencode({
        "api_key": key,
        "series_id": SERIES_ID,
        "file_type": "json",
        "units": "lin",
        "output_type": "1",
        "observation_start": observation_date,
        "observation_end": observation_date,
        "realtime_start": asof_date,
        "realtime_end": asof_date,
    })
    req = urllib.request.Request(
        OFFICIAL_API + "?" + query,
        headers={"Accept": "application/json", "User-Agent": "ISL-DGS10-PIT-one-shot/0.1"},
    )
    opener = urllib.request.build_opener(RejectRedirect())
    try:
        with opener.open(req, timeout=20) as response:
            if response.status != 200:
                raise SourceUnavailable("ALFRED HTTP status not OK")
            if urllib.parse.urlparse(response.geturl()).hostname != "api.stlouisfed.org":
                raise SourceUnavailable("ALFRED final origin mismatch")
            payload = response.read(MAX_REPLY_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        # Errors from libraries can embed full request URLs containing secrets:
        # deliberately do NOT print str(exc) or exception URLs.
        code = getattr(exc, "code", None)
        raise SourceUnavailable(
            "ALFRED API error HTTP_" + str(code) if code is not None
            else "ALFRED API transport error"
        ) from None
    return parse_snapshot(payload, observation_date, asof_date)


def compare_archived_samples(alfred_samples, original_monthly):
    if set(alfred_samples) != {month for month, _, _ in CHECKS}:
        raise SourceUnavailable("ALFRED sample scope incomplete")
    gaps = []
    status = []
    for month, obsdate, asof in CHECKS:
        entry = alfred_samples[month]
        if not isinstance(entry, dict) or entry.get("date") != obsdate or entry.get("asof") != asof:
            raise SourceUnavailable("ALFRED observation-asof binding mismatch")
        value = entry.get("value")
        original = original_monthly[month]["yield"]
        if any(type(v) not in (float, int) or not math.isfinite(v) for v in (value, original)):
            raise SourceUnavailable("ALFRED or ODS reference value invalid")
        # ODS Original_US_1962 yields are fractional per the previous explicit
        # source normalizer; ALFRED DGS10 is percent points (3 means 3%).
        delta = abs(value - original * 100)
        gaps.append(delta)
        status.append({
            "month": month,
            "daily_observation_date": obsdate,
            "historic_asof_date": asof,
            "archive_snapshot_present": True,
            "comparison_to_original_ods": (
                "MATCH" if delta <= MAX_GAP_PCT_POINTS else "NOT_MATCHED"
            ),
        })
    return {
        "series": SERIES_ID,
        "source": "official_ALFRED_realtime_period",
        "archived_asof_sample_count": len(CHECKS),
        "samples": status,
        "max_abs_ods_gap_percentage_points": f"{max(gaps):.6e}",
        "original_ods_monthly_aggregation_method_certified": False,
        "availability_at_month_end_decision_certified": False,
        "underlying_first_release_timestamp_certified": False,
        "historical_pit_certified": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def main():
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        print("ALFRED_DGS10_PIT_PROBE=BLOCKED_NO_FRED_API_KEY")
        print("ALFRED_PIT_CERTIFIED=false")
        print("QUALIFIED_MODEL_SERIES=[]")
        print("M1_M2_M3=HOLD_CASH")
        return
    validate_api_key(key)
    # Use only original pinned ODS; no mirror or guess.
    orig = extract_original_us(fetch(PUBLISHER + "/api/access/datafile/" + str(FILE_ID), 5_000_000))
    samples = {}
    for month, observation, asof in CHECKS:
        samples[month] = {
            "date": observation,
            "asof": asof,
            "value": _request_snapshot(key, observation, asof),
        }
    summary = compare_archived_samples(samples, orig)
    print("ALFRED_DGS10_PIT_PROBE=" + json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        # All raised diagnostic messages are source-controlled and contain
        # no key, URL parameters or returned numeric observation values.
        print("ALFRED_DGS10_PIT_PROBE=BLOCKED: " + str(exc))
        print("ALFRED_PIT_CERTIFIED=false")
        print("M1_M2_M3=HOLD_CASH")
        sys.exit(2)
