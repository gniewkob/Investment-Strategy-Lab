"""One-shot, SHA-pinned comparative formula dependency audit for Swinkels ODS.

Scope: original publisher ODS, Jan 2020–Dec 2022, 10 Return M variants.
No return values, formulas, workbook, yield values or identifiable rows
are emitted. Formula dependency topology only. No scheduling or trading.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

from scripts.research_swinkels_original_source_probe_v01 import (
    PUBLISHER, SourceUnavailable, _column_cells, _cell_label, fetch
)
from scripts.swinkels_formula_topology_probe_v01 import (
    SOURCE_ID, SOURCE_BYTES, SOURCE_SHA, T, O, X, _formula_shape_digest
)

REF = re.compile(r"\[\.\$?([A-Z]{1,3})\$?(\d+)\]")
ANY_REF = re.compile(r"\[[^\]]{1,130}\]")
OPERATORS = "+-*/^"
MONTHS = frozenset(f"{y:04d}-{m:02d}" for y in range(2020, 2023) for m in range(1, 13))
EXPECTED_VARIANTS = 10
MAX_REF_COUNT = 24


def _column_number(letters: str) -> int:
    if not isinstance(letters, str) or not 1 <= len(letters) <= 3 or not letters.isalpha() or not letters.isupper():
        raise SourceUnavailable("unsupported reference column")
    number = 0
    for c in letters:
        number = number * 26 + (ord(c) - ord("A") + 1)
    return number


def classify_formula(formula: str, sheet_row_number: int) -> dict:
    """Classify only source dependency geometry, never formula constants."""
    if not isinstance(formula, str) or not formula.startswith("of:=") or len(formula) > 4096:
        raise SourceUnavailable("invalid OpenFormula expression")
    all_refs = ANY_REF.findall(formula)
    parsed = REF.findall(formula)
    if not 1 <= len(parsed) <= MAX_REF_COUNT or len(all_refs) != len(parsed):
        raise SourceUnavailable("unsupported or missing OpenFormula cell reference")
    if type(sheet_row_number) is not int or sheet_row_number < 2:
        raise SourceUnavailable("invalid source spreadsheet row number")
    layout = []
    for column, row in parsed:
        offset = int(row) - sheet_row_number
        if not -120 <= offset <= 120:
            raise SourceUnavailable("unexpected formula cross-period dependency")
        layout.append((_column_number(column), offset))
    scrubbed = ANY_REF.sub("@", formula)
    operators = Counter(op for op in scrubbed if op in OPERATORS)
    return {
        "reference_geometry": tuple(layout),
        "operator_counts": tuple((op, operators[op]) for op in OPERATORS if operators[op]),
        "shape": _formula_shape_digest(formula),
    }


def inspect(raw: bytes) -> dict:
    if len(raw) != SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise SourceUnavailable("original ODS SHA/size mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist()
            if len(infos) > 160 or sum(i.file_size for i in infos) > 32_000_000:
                raise SourceUnavailable("ODS zip exceeds parsing limits")
            if any(i.filename.startswith("/") or ".." in i.filename.split("/") for i in infos):
                raise SourceUnavailable("unsafe ODS archive entry")
            if z.read("mimetype") != b"application/vnd.oasis.opendocument.spreadsheet":
                raise SourceUnavailable("unexpected ODS MIME")
            root = ET.fromstring(z.read("content.xml"))
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise SourceUnavailable("unable to decode verified ODS") from exc

    variants = []
    for table in root.iter(T + "table"):
        rows = list(table.iter(T + "table-row"))
        header_idx = None
        date_idx = None
        return_idx = None
        for idx, row in enumerate(rows[:25]):
            labels = [_cell_label(c, X) for c in _column_cells(row, T)]
            if "observation_date" in labels and "Return M" in labels:
                header_idx = idx
                date_idx = labels.index("observation_date")
                return_idx = labels.index("Return M")
                break
        if header_idx is None:
            continue
        found = {}
        for rowno, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
            cells = _column_cells(row, T)
            if max(date_idx, return_idx) >= len(cells):
                continue
            stamp = cells[date_idx].get(O + "date-value", "")
            if not isinstance(stamp, str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}(?:T[0-9:]+)?", stamp):
                continue
            month = stamp[:7]
            if month not in MONTHS:
                continue
            if month in found:
                raise SourceUnavailable("duplicate month in publisher ODS")
            cell = cells[return_idx]
            if cell.get(O + "value-type") != "percentage" or cell.get(O + "value") is None:
                raise SourceUnavailable("Return M is not a numeric percentage cell")
            found[month] = classify_formula(cell.get(T + "formula"), rowno)
        if set(found) != MONTHS:
            raise SourceUnavailable("original ODS has incomplete 36-month formula coverage")
        signatures = {v["shape"] for v in found.values()}
        geometries = {v["reference_geometry"] for v in found.values()}
        op_patterns = {v["operator_counts"] for v in found.values()}
        if len(signatures) != 1 or len(geometries) != 1 or len(op_patterns) != 1:
            raise SourceUnavailable("formula shape drift across 36 months")
        first = found[min(MONTHS)]
        variants.append({
            "variant_ordinal": len(variants) + 1,
            "months": len(found),
            "reference_geometry": [
                {"source_column": col, "month_row_offset": offset}
                for col, offset in first["reference_geometry"]
            ],
            "operator_counts": dict(first["operator_counts"]),
            "stable_shape_across_36_months": True,
            "independent_economic_reproduction": "NOT_VERIFIED",
        })
    if len(variants) != EXPECTED_VARIANTS:
        raise SourceUnavailable("expected ten original country/variant formulas")
    return {
        "source_hash_verified": True,
        "window": "2020-01..2022-12",
        "country_variant_count": len(variants),
        "variants": variants,
        "monthly_financial_values_exported": False,
        "source_formulas_exported": False,
        "historical_point_in_time_certified": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
    }


def main() -> None:
    raw = fetch(PUBLISHER + "/api/access/datafile/" + str(SOURCE_ID), 5_000_000)
    print("SWINKELS_MULTI_VARIANT_DEPENDENCY_AUDIT=" + json.dumps(inspect(raw), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        print("SWINKELS_MULTI_VARIANT_DEPENDENCY_AUDIT=BLOCKED: " + str(exc))
        sys.exit(2)
