"""One-shot numerical reconciliation with Swinkels (2019), Eq. 3.

Research-only: original source ODS with pinned SHA, US Original variant only,
36 monthly observations Jan 2020–Dec 2022. Separately computes par-bond
duration and convexity from discounted coupon cash flows, and reconciles the
publisher's cached Return M to the paper's first/second-order approximation.
Logs only aggregate discrepancies, never financial observations or source files.
No trading, model qualification, secrets, scheduling or external storage.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

from scripts.research_swinkels_original_source_probe_v01 import (
    PUBLISHER, SourceUnavailable, _column_cells, _cell_label, fetch,
)

FILE_ID = 512630
FILE_SIZE = 913425
FILE_SHA = "90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847"
SHEET_NAME = "Original_US_1962"
T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
O = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
X = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
FIELDS = ("observation_date", "DGS10", "Mod Dur", "Convexity", "Return M")
MONTHS = tuple(f"{y:04d}-{m:02d}" for y in range(2020, 2023) for m in range(1, 13))
ALL_MONTHS = ("2019-12",) + MONTHS


def par_bond_sensitivities(annual_yield: float, years: int = 10) -> tuple[float, float]:
    """Independent semiannual par-coupon discounted-cash-flow derivatives."""
    if not math.isfinite(annual_yield) or annual_yield <= -0.5 or not 1 <= years <= 50:
        raise SourceUnavailable("invalid yield or tenor")
    n = 2 * years
    base = 1.0 + annual_yield / 2
    coupon = annual_yield / 2
    principal_pv = base ** (-n)
    price = principal_pv
    first = -(n / 2) * base ** (-n - 1)
    second = (n * (n + 1) / 4) * base ** (-n - 2)
    for k in range(1, n + 1):
        price += coupon * base ** (-k)
        first -= coupon * (k / 2) * base ** (-k - 1)
        second += coupon * (k * (k + 1) / 4) * base ** (-k - 2)
    if not math.isfinite(price) or price <= 0:
        raise SourceUnavailable("nonpositive par bond model price")
    return -first / price, second / price


def equation3(y_previous: float, y_current: float, duration: float, convexity: float) -> float:
    """Swinkels 2019 Eq. 3, monthly compounded yield and annual delta yield."""
    if any(not math.isfinite(x) for x in (y_previous, y_current, duration, convexity)):
        raise SourceUnavailable("non-finite model input")
    if y_previous <= -1:
        raise SourceUnavailable("invalid annual yield")
    delta = y_current - y_previous
    return (1 + y_previous) ** (1 / 12) - 1 - duration * delta + 0.5 * convexity * delta**2


def _finite_cell(cell, field: str) -> float:
    value = cell.get(O + "value")
    if not isinstance(value, str) or len(value) > 64:
        raise SourceUnavailable("missing or oversized numeric cell: " + field)
    try:
        parsed = float(value)
    except ValueError as exc:
        raise SourceUnavailable("invalid numeric cell: " + field) from exc
    if not math.isfinite(parsed):
        raise SourceUnavailable("non-finite cell: " + field)
    return parsed


def extract_original_us(raw: bytes) -> dict:
    if len(raw) != FILE_SIZE or hashlib.sha256(raw).hexdigest() != FILE_SHA:
        raise SourceUnavailable("original ODS size/digest mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            entries = z.infolist()
            if len(entries) > 160 or sum(e.file_size for e in entries) > 32_000_000:
                raise SourceUnavailable("ODS size/extraction cap exceeded")
            if any(e.filename.startswith("/") or ".." in e.filename.split("/") for e in entries):
                raise SourceUnavailable("unsafe ODS archive entry")
            if z.read("mimetype") != b"application/vnd.oasis.opendocument.spreadsheet":
                raise SourceUnavailable("invalid ODS mime")
            root = ET.fromstring(z.read("content.xml"))
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise SourceUnavailable("unable to parse verified ODS") from exc

    tables = [t for t in root.iter(T + "table") if t.get(T + "name") == SHEET_NAME]
    if len(tables) != 1:
        raise SourceUnavailable("US original worksheet not unique")
    rows = list(tables[0].iter(T + "table-row"))
    positions = None
    header = None
    for i, row in enumerate(rows[:25]):
        labels = [_cell_label(c, X) for c in _column_cells(row, T)]
        if all(f in labels for f in FIELDS):
            positions = {field: labels.index(field) for field in FIELDS}
            header = i
            break
    if positions is None:
        raise SourceUnavailable("required original US source columns unavailable")
    records = {}
    for row in rows[header + 1:]:
        cols = _column_cells(row, T)
        if max(positions.values()) >= len(cols):
            continue
        d = cols[positions["observation_date"]]
        stamp = d.get(O + "date-value", "")
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}(?:T[0-9:]+)?", stamp):
            continue
        month = stamp[:7]
        if month not in ALL_MONTHS:
            continue
        if month in records:
            raise SourceUnavailable("duplicate original US source month")
        yield_cell = cols[positions["DGS10"]]
        ret_cell = cols[positions["Return M"]]
        if yield_cell.get(O + "value-type") != "percentage" or ret_cell.get(O + "value-type") != "percentage":
            raise SourceUnavailable("US source yield or return cell not ODF percentage type")
        records[month] = {
            "yield": _finite_cell(yield_cell, "DGS10"),
            "duration": _finite_cell(cols[positions["Mod Dur"]], "Mod Dur"),
            "convexity": _finite_cell(cols[positions["Convexity"]], "Convexity"),
            "return": _finite_cell(ret_cell, "Return M"),
        }
    if set(records) != set(ALL_MONTHS):
        raise SourceUnavailable("original US 2019-12 to 2022-12 window incomplete")
    return records


def reconcile(records: dict) -> dict:
    if set(records) != set(ALL_MONTHS):
        raise SourceUnavailable("reconciliation window mismatch")
    cached_diffs = []
    model_diffs = []
    duration_diffs = []
    convexity_diffs = []
    for i, month in enumerate(MONTHS):
        current = records[month]
        previous = records[ALL_MONTHS[i]]
        y_prev, y_now = previous["yield"], current["yield"]
        # ODF percentage-valued cells already hold the decimal fraction.
        d_ind, c_ind = par_bond_sensitivities(y_now, years=10)
        cached_diffs.append(abs(
            equation3(y_prev, y_now, current["duration"], current["convexity"])
            - current["return"]))
        model_diffs.append(abs(
            equation3(y_prev, y_now, d_ind, c_ind) - current["return"]))
        duration_diffs.append(abs(d_ind - current["duration"]))
        convexity_diffs.append(abs(c_ind - current["convexity"]))
    if any(not math.isfinite(x) for xs in (
            cached_diffs, model_diffs, duration_diffs, convexity_diffs) for x in xs):
        raise SourceUnavailable("non-finite independent reconciliation")
    # Diagnostic only: absence of a predefined, published numerical tolerance
    # prevents promoting this to an accepted historical economic backtest.
    return {
        "source_sha_verified": True,
        "variant": SHEET_NAME,
        "months_reconciled": len(MONTHS),
        "window": "2020-01..2022-12",
        "calculation_reference": "Swinkels 2019 Eq. 3",
        "independent_sensitivities": "discounted semiannual par-coupon cashflows",
        "yield_input_storage": "ODF_percentage_fraction",
        "max_abs_return_gap_using_stored_duration_convexity": f"{max(cached_diffs):.3e}",
        "max_abs_return_gap_using_independent_duration_convexity": f"{max(model_diffs):.3e}",
        "max_abs_duration_gap": f"{max(duration_diffs):.3e}",
        "max_abs_convexity_gap": f"{max(convexity_diffs):.3e}",
        "formula_economic_semantics_certified": False,
        "historical_point_in_time_certified": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def main() -> None:
    raw = fetch(PUBLISHER + "/api/access/datafile/" + str(FILE_ID), 5_000_000)
    print("SWINKELS_US_EQUATION3_DIAGNOSTIC=" +
          json.dumps(reconcile(extract_original_us(raw)), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        print("SWINKELS_US_EQUATION3_DIAGNOSTIC=BLOCKED: " + str(exc))
        sys.exit(2)
