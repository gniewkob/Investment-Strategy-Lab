"""Bounded official original Swinkels ODS formula topology audit.

Read-only one-shot publisher verification; never exports formulas, cell values,
return series, workbook, credentials or historical performance.
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

SOURCE_ID = 512630
SOURCE_BYTES = 913425
SOURCE_SHA = "90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847"
T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
O = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
X = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
FORMULA_CAP = 4096
REF_RE = re.compile(r"\[[^\]]{1,100}\]")
EXPECTED_SHEETS = 10


def _formula_shape_digest(formula: str) -> str:
    """Anonymized structural signature; never return formula or observations."""
    if not isinstance(formula, str) or not formula.startswith("of:=") or len(formula) > FORMULA_CAP:
        raise SourceUnavailable("invalid formula for structural fingerprint")
    references = REF_RE.findall(formula)
    if not references:
        raise SourceUnavailable("formula contains no cell reference")
    stripped = REF_RE.sub("[CELL]", formula)
    # Suppress literal numeric values and row coordinates in structural output.
    stripped = re.sub(r"(?<![A-Za-z_])(?:\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)", "#", stripped)
    stripped = re.sub(r"\s+", "", stripped)
    return hashlib.sha256(stripped.encode("utf-8")).hexdigest()


def inspect_formulas(raw: bytes) -> dict:
    if len(raw) != SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise SourceUnavailable("original source ODS size or SHA mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist()
            if len(infos) > 160 or sum(x.file_size for x in infos) > 32_000_000:
                raise SourceUnavailable("ODS exceeds bounded extraction limits")
            for info in infos:
                if info.filename.startswith("/") or ".." in info.filename.split("/"):
                    raise SourceUnavailable("unsafe ODS entry")
            if z.read("mimetype") != b"application/vnd.oasis.opendocument.spreadsheet":
                raise SourceUnavailable("invalid ODS mimetype")
            xml = z.read("content.xml")
        root = ET.fromstring(xml)
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise SourceUnavailable("ODS structure could not be read") from exc

    audit = []
    for sheet in root.iter(T + "table"):
        rows = list(sheet.iter(T + "table-row"))
        idx = None
        header = None
        for rowno, row in enumerate(rows[:25]):
            labels = [_cell_label(c, X) for c in _column_cells(row, T)]
            if "observation_date" in labels and "Return M" in labels:
                idx, header = labels.index("Return M"), rowno
                break
        if idx is None:
            continue
        counts = Counter()
        shapes = Counter()
        for row in rows[header + 1:]:
            cols = _column_cells(row, T)
            if idx >= len(cols):
                continue
            cell = cols[idx]
            if cell.get(O + "value") is None:
                continue
            formula = cell.get(T + "formula")
            if not isinstance(formula, str) or not formula or len(formula) > FORMULA_CAP:
                raise SourceUnavailable("missing or oversized Return M formula")
            if not formula.startswith("of:="):
                raise SourceUnavailable("unexpected formula namespace")
            # Never emit source formula text: only structural reference counts.
            references = REF_RE.findall(formula)
            if not references:
                raise SourceUnavailable("Return M formula has no cell references")
            if cell.get(O + "value-type") != "percentage":
                raise SourceUnavailable("Return M cell has unexpected value type")
            counts[len(references)] += 1
            shapes[_formula_shape_digest(formula)] += 1
        if not counts:
            raise SourceUnavailable("no source Return M formulas found")
        audit.append({
            "sheet_ordinal": len(audit) + 1,
            "formula_cell_count": sum(counts.values()),
            "cell_reference_count_histogram": [
                {"references": count, "formula_cells": frequency}
                for count, frequency in sorted(counts.items())
            ],
            "all_formula_cells_are_percentage_type": True,
            "distinct_anonymized_formula_shapes": len(shapes),
            "largest_shape_cell_count": max(shapes.values()),
        })
    if len(audit) != EXPECTED_SHEETS:
        raise SourceUnavailable("country sheet count does not match expected original")
    return {
        "original_source_sha256_verified": True,
        "country_variant_sheets": len(audit),
        "sheet_formula_topology": audit,
        "formula_economic_semantics_certified": False,
        "historical_pit_certified": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
    }


def main() -> None:
    source = fetch(PUBLISHER + "/api/access/datafile/" + str(SOURCE_ID), 5_000_000)
    print("SWINKELS_RETURN_M_FORMULA_STRUCTURE=" + json.dumps(inspect_formulas(source), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        print("SWINKELS_RETURN_M_FORMULA_AUDIT=BLOCKED: " + str(exc))
        sys.exit(2)
