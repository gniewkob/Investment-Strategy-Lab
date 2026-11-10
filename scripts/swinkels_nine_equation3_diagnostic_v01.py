"""Nine-variant Swinkels Eq3 independent research diagnostic (2020-2022).

One-shot original publisher SHA-pinned ODS. All nine common-formula sheets:
Yield 10Y in percent points inferred from common explicit formula literal
conventions (200 semiannual, 1200 monthly), independently compared against
Swinkels 2019 Eq3. This is a diagnostic *hypothesis* and does not certify
the economic meaning of every national source yield.

No per-month values, series, formulas, dataset, or trading data emitted.
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
    PUBLISHER, SourceUnavailable, _column_cells, _cell_label, fetch
)
from scripts.swinkels_formula_topology_probe_v01 import (
    SOURCE_ID, SOURCE_BYTES, SOURCE_SHA, T, O, X
)
from scripts.swinkels_original_us_equation3_audit_v01 import (
    equation3, par_bond_sensitivities
)

MONTHS = tuple(f"{year:04d}-{month:02d}"
               for year in range(2020, 2023) for month in range(1, 13))
SOURCE_WINDOW = ("2019-12",) + MONTHS
SHEETS = (
    "Improved_US_1947", "Germany_DE_1972", "Japan_JP_1974",
    "France_FR_1987", "UK_1970", "Australia_AU_1969",
    "Canada_CA_1986", "Norway_NO_1921", "Sweden_SE_1920"
)


def _numeric(cell, label):
    raw = cell.get(O + "value")
    if not isinstance(raw, str) or len(raw) > 64:
        raise SourceUnavailable("missing source numeric field " + label)
    try:
        number = float(raw)
    except ValueError as exc:
        raise SourceUnavailable("invalid source numeric field " + label) from exc
    if not math.isfinite(number):
        raise SourceUnavailable("nonfinite source numeric field " + label)
    return number


def extract_nine(raw):
    if len(raw) != SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise SourceUnavailable("original publisher source SHA/size mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist()
            if len(infos) > 160 or sum(i.file_size for i in infos) > 32_000_000:
                raise SourceUnavailable("ODS extraction limit exceeded")
            if any(i.filename.startswith("/") or ".." in i.filename.split("/") for i in infos):
                raise SourceUnavailable("unsafe ODS archive")
            if z.read("mimetype") != b"application/vnd.oasis.opendocument.spreadsheet":
                raise SourceUnavailable("original ODS MIME mismatch")
            root = ET.fromstring(z.read("content.xml"))
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise SourceUnavailable("original ODS structure unavailable") from exc

    parsed = {}
    for table in root.iter(T + "table"):
        name = table.get(T + "name")
        if name not in SHEETS:
            continue
        if name in parsed:
            raise SourceUnavailable("duplicate publisher worksheet")
        rows = list(table.iter(T + "table-row"))
        positions = None
        header = None
        for idx, row in enumerate(rows[:25]):
            labels = [_cell_label(cell, X) for cell in _column_cells(row, T)]
            if all(k in labels for k in ("observation_date", "Yield 10Y", "Return M")):
                positions = {k: labels.index(k) for k in
                             ("observation_date", "Yield 10Y", "Return M")}
                header = idx
                break
        if positions is None:
            raise SourceUnavailable("missing source columns in country worksheet")
        records = {}
        for row in rows[header + 1:]:
            cells = _column_cells(row, T)
            if len(cells) <= max(positions.values()):
                continue
            stamp = cells[positions["observation_date"]].get(O + "date-value", "")
            if not isinstance(stamp, str) or not re.fullmatch(
                    r"20\d{2}-\d{2}-\d{2}(?:T[0-9:]+)?", stamp):
                continue
            month = stamp[:7]
            if month not in SOURCE_WINDOW:
                continue
            if month in records:
                raise SourceUnavailable("duplicate month in source worksheet")
            ycell = cells[positions["Yield 10Y"]]
            rcell = cells[positions["Return M"]]
            if ycell.get(O + "value-type") != "float":
                raise SourceUnavailable("national yield type not plain ODF float")
            if rcell.get(O + "value-type") != "percentage":
                raise SourceUnavailable("Return M ODF percentage type mismatch")
            records[month] = {
                "yield_points": _numeric(ycell, "Yield 10Y"),
                "return_fraction": _numeric(rcell, "Return M"),
            }
        if set(records) != set(SOURCE_WINDOW):
            raise SourceUnavailable("country 37-month source window incomplete")
        parsed[name] = records
    if set(parsed) != set(SHEETS):
        raise SourceUnavailable("not all nine original worksheet variants found")
    return parsed


def compare_series(records):
    if set(records) != set(SOURCE_WINDOW):
        raise SourceUnavailable("invalid country reconciliation window")
    residuals = []
    residuals_simple_carry = []
    for i, month in enumerate(MONTHS):
        prior = records[SOURCE_WINDOW[i]]
        current = records[month]
        # Only source-specific common-formula unit hypothesis; ODF plain float
        # alone is insufficient to establish percent-point convention.
        prev_y = prior["yield_points"] / 100.0
        now_y = current["yield_points"] / 100.0
        duration, convexity = par_bond_sensitivities(now_y, years=10)
        model = equation3(prev_y, now_y, duration, convexity)
        # Alternative carry convention is diagnostic, not selection of units.
        simple = prev_y / 12 - duration * (now_y - prev_y) + (
            0.5 * convexity * (now_y - prev_y) ** 2
        )
        cached = current["return_fraction"]
        if any(not math.isfinite(v) for v in (model, simple, cached)):
            raise SourceUnavailable("nonfinite 36-month country reconciliation")
        residuals.append(model - cached)
        residuals_simple_carry.append(simple - cached)
    rms = math.sqrt(sum(e * e for e in residuals) / len(residuals))
    rms_simple = math.sqrt(sum(e * e for e in residuals_simple_carry)
                           / len(residuals_simple_carry))
    return {
        "months": len(MONTHS),
        "max_abs_gap_compound_carry": f"{max(map(abs, residuals)):.3e}",
        "rms_gap_compound_carry": f"{rms:.3e}",
        "max_abs_gap_simple_carry": f"{max(map(abs, residuals_simple_carry)):.3e}",
        "rms_gap_simple_carry": f"{rms_simple:.3e}",
        "independent_economic_reproduction": "DIAGNOSTIC_ONLY",
        "yield_scale_evidence": "source_formula_constants_200_1200_not_fully_validated",
    }


def diagnostic(groups):
    if set(groups) != set(SHEETS):
        raise SourceUnavailable("incomplete independent country source set")
    return {
        "source_sha_verified": True,
        "window": "2020-01..2022-12",
        "country_variant_count": len(SHEETS),
        "series": [{"variant": name, **compare_series(groups[name])} for name in SHEETS],
        "formula_economic_semantics_certified": False,
        "historical_pit_certified": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def main():
    raw = fetch(PUBLISHER + "/api/access/datafile/" + str(SOURCE_ID), 5_000_000)
    print("SWINKELS_NINE_EQ3_DIAGNOSTIC=" +
          json.dumps(diagnostic(extract_nine(raw)), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        print("SWINKELS_NINE_EQ3_DIAGNOSTIC=BLOCKED: " + str(exc))
        sys.exit(2)
