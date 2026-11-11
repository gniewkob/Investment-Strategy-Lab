"""One-shot Eurostat prc_hicp_fpd schema probe: NO observation values emitted.

This is *not* a first-release HICP revision analyser. It only inspects
the exact JSON-stat dimension shape returned from the official public API,
with no assumptions about the 'release' code or vintage.

Allowed result: metadata names/labels, source canonical SHA, observation
count metadata, and explicit NO_PIT_ATTESTATION/NO_TRADING declarations.
Default local mode reads a bounded supplied JSON; --fetch-official is the
only network path and issues exactly one fixed official HTTPS GET.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

DATASET = "prc_hicp_fpd"
API_ROOT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/" + DATASET
FIXED_QUERY = {
    "geo": "PL",
    "freq": "M",
    "unit": "I25",
    "coicop18": "TOTAL",
    "sinceTimePeriod": "2026-07",
    "untilTimePeriod": "2026-09",
    "lang": "EN",
}
MAX_INPUT_BYTES = 2_000_000
MAX_DIMENSIONS = 12
MAX_DIMENSION_CATEGORIES = 200
SAFE_LABEL = re.compile(r"^[^\x00-\x1f]{0,180}$")


class FPDProbeError(ValueError):
    pass


def _canonical(obj):
    try:
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=True, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise FPDProbeError("invalid canonical JSON-stat") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise FPDProbeError("source JSON exceeds 2 MB cap")
    return raw


def _category_index(index):
    if isinstance(index, dict):
        if (any(not isinstance(k, str) or type(v) is not int
                for k, v in index.items())
                or set(index.values()) != set(range(len(index)))):
            raise FPDProbeError("invalid JSON-stat category position map")
        return [k for k, _ in sorted(index.items(), key=lambda kv: kv[1])]
    if isinstance(index, list) and all(isinstance(x, str) for x in index):
        if len(index) != len(set(index)):
            raise FPDProbeError("duplicate JSON-stat category codes")
        return index
    raise FPDProbeError("unknown JSON-stat category index")


def schema_receipt(data):
    """Inspect shape only; drop any values, rates and index level fields."""
    raw = _canonical(data)
    if (not isinstance(data, dict) or data.get("class") != "dataset"
            or str(data.get("version")) != "2.0"
            or data.get("source") not in ("Eurostat", "ESTAT")):
        raise FPDProbeError("not official-style Eurostat JSON-stat 2.0 dataset")
    dim_ids, sizes, dimensions = (data.get("id"), data.get("size"),
                                  data.get("dimension"))
    if (not isinstance(dim_ids, list) or not 5 <= len(dim_ids) <= MAX_DIMENSIONS
            or len(dim_ids) != len(set(dim_ids))
            or any(not isinstance(x, str) for x in dim_ids)
            or not isinstance(sizes, list) or len(dim_ids) != len(sizes)
            or not isinstance(dimensions, dict) or set(dimensions) != set(dim_ids)):
        raise FPDProbeError("invalid JSON-stat dimension structure")
    dimensions_summary = []
    for name, count in zip(dim_ids, sizes):
        if type(count) is not int or not 1 <= count <= MAX_DIMENSION_CATEGORIES:
            raise FPDProbeError("invalid dimension size")
        dimension = dimensions[name]
        if not isinstance(dimension, dict) or not isinstance(
                dimension.get("category"), dict):
            raise FPDProbeError("missing dimension category metadata")
        category = dimension["category"]
        codes = _category_index(category.get("index"))
        if len(codes) != count:
            raise FPDProbeError("dimension category count mismatch")
        labels = category.get("label", {})
        if not isinstance(labels, dict):
            raise FPDProbeError("invalid dimension category labels")
        sample = []
        for code in codes[:MAX_DIMENSION_CATEGORIES]:
            label = labels.get(code, "")
            if (len(code) > 100 or not SAFE_LABEL.fullmatch(code)
                    or not isinstance(label, str)
                    or not SAFE_LABEL.fullmatch(label)):
                raise FPDProbeError("unbounded category label/code")
            sample.append({"code": code, "label": label})
        dimensions_summary.append({"id": name, "size": count, "codes": sample})
    dimension_names = set(dim_ids)
    for expected in ("freq", "unit", "coicop18", "geo", "time"):
        if expected not in dimension_names:
            raise FPDProbeError("missing mandatory Eurostat dimension " + expected)
    extra = dimension_names - {"freq", "unit", "coicop18", "geo", "time"}
    if len(extra) != 1:
        raise FPDProbeError("expected exactly one extra release dimension")
    release_axis = next(iter(extra))
    if "release" not in release_axis.lower():
        raise FPDProbeError("extra dimension is not recognised as Release")

    output = {
        "schema": "ISL_EUROSTAT_FPD_SOURCE_METADATA_PROBE_V01",
        "status": "OFFICIAL_STYLE_SCHEMA_METADATA_ONLY_NOT_AS_OF_CERTIFIED",
        "dataset": DATASET,
        "expected_selector": FIXED_QUERY,
        "dimensions": dimensions_summary,
        "release_dimension_id": release_axis,
        "canonical_local_response_sha256": sha256(raw).hexdigest(),
        "dataset_updated_field": str(data.get("updated", "UNSPECIFIED"))[:100],
        "historical_pit_certified": False,
        "first_release_value_compared": False,
        "original_release_date_per_value_authenticated": False,
        "index_values_emitted": False,
        "qualified_model_series": [],
        "paper_candidates": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
        "orders_sent": 0,
        "paper_fills": 0,
        "database_writes": 0,
    }
    output["receipt_sha256"] = sha256(_canonical(output)).hexdigest()
    return output


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise FPDProbeError("redirect outside original Eurostat URL prohibited")


def _fetch_official():
    url = API_ROOT + "?" + urlencode(FIXED_QUERY)
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "Investment-Strategy-Lab-FPD-public-schema-probe/0.1",
    })
    opener = build_opener(_NoRedirect(), HTTPSHandler())
    try:
        with opener.open(request, timeout=20) as response:
            if response.status != 200:
                raise FPDProbeError("official Eurostat response not 200")
            if not response.headers.get("Content-Type", "").lower().startswith(
                    ("application/json", "application/vnd.sdmx")):
                raise FPDProbeError("expected Eurostat JSON API content-type")
            raw = response.read(MAX_INPUT_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise FPDProbeError("read-only Eurostat official request failed") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise FPDProbeError("official Eurostat data exceeded 2 MB bound")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FPDProbeError("official source body is not JSON") from exc


def _read_offline(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise FPDProbeError("bounded regular local JSON-stat required")
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise FPDProbeError("offline file exceeded input limit")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FPDProbeError("invalid JSON-stat file") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--offline-json", type=Path)
    source.add_argument("--fetch-official", action="store_true")
    args = parser.parse_args()
    data = _fetch_official() if args.fetch_official else _read_offline(args.offline_json)
    output = schema_receipt(data)
    print("ISL_FPD_METADATA=" + json.dumps(output, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
