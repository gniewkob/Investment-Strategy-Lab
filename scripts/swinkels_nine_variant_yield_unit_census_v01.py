"""Source-only ODF storage-unit census for the nine common-formula bond series.

One-shot, SHA-pinned original DataverseNL ODS; 36 months 2020-2022.
No source values, raw formulas, file, or per-month observations logged.
Do not infer yield percentage-point scale from magnitude or from labels.
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
    SOURCE_ID, SOURCE_BYTES, SOURCE_SHA, T, O, X
)

STYLE = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}"
NUMBER = "{urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0}"
MONTHS = frozenset(f"{y:04d}-{m:02d}" for y in range(2020, 2023) for m in range(1, 13))


def storage_semantics(value_type: str, number_format: str) -> str:
    """ODF's percentage cell type+format supports fractional storage.

    Generic float cells do NOT establish percentage-point vs decimal scaling.
    """
    if value_type == "percentage" and number_format == "percentage-style":
        return "ODF_PERCENT_FRACTION"
    if value_type == "float" and number_format == "number-style":
        return "GENERIC_FLOAT_SCALE_NOT_CERTIFIED"
    return "STORAGE_SEMANTICS_REVIEW_REQUIRED"


def _style_maps(content_root, styles_root):
    style_data = {}
    number_style = {}
    for root in (content_root, styles_root):
        for element in root.iter(STYLE + "style"):
            key = element.get(STYLE + "name")
            data = element.get(STYLE + "data-style-name")
            if key and data:
                style_data[key] = data
        for kind in ("percentage-style", "number-style", "currency-style"):
            for element in root.iter(NUMBER + kind):
                name = element.get(STYLE + "name")
                if name:
                    number_style[name] = kind
    return style_data, number_style


def inspect(raw: bytes) -> dict:
    if len(raw) != SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise SourceUnavailable("original ODS source SHA/size mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            entries = z.infolist()
            if len(entries) > 160 or sum(e.file_size for e in entries) > 32_000_000:
                raise SourceUnavailable("source exceeds bounded ODS parsing limits")
            if any(e.filename.startswith("/") or ".." in e.filename.split("/") for e in entries):
                raise SourceUnavailable("unsafe archive path")
            if z.read("mimetype") != b"application/vnd.oasis.opendocument.spreadsheet":
                raise SourceUnavailable("unsupported original source MIME")
            content = ET.fromstring(z.read("content.xml"))
            styles = ET.fromstring(z.read("styles.xml"))
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise SourceUnavailable("invalid original ODS XML") from exc

    styles_for_cell, formats = _style_maps(content, styles)
    report = []
    for table in content.iter(T + "table"):
        if table.get(T + "name") == "Original_US_1962":
            continue
        rows = list(table.iter(T + "table-row"))
        layout = None
        header = -1
        for idx, row in enumerate(rows[:25]):
            labels = [_cell_label(c, X) for c in _column_cells(row, T)]
            if all(k in labels for k in ("observation_date", "Yield 10Y", "Return M")):
                layout = {k: labels.index(k) for k in ("observation_date", "Yield 10Y", "Return M")}
                header = idx
                break
        if layout is None:
            continue
        months = {}
        for row in rows[header + 1:]:
            cells = _column_cells(row, T)
            if max(layout.values()) >= len(cells):
                continue
            stamp = cells[layout["observation_date"]].get(O + "date-value", "")
            if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}(?:T[0-9:]+)?", stamp):
                continue
            month = stamp[:7]
            if month not in MONTHS:
                continue
            if month in months:
                raise SourceUnavailable("duplicate original source month")
            ycell = cells[layout["Yield 10Y"]]
            rcell = cells[layout["Return M"]]
            if ycell.get(O + "value") is None or rcell.get(O + "value") is None:
                raise SourceUnavailable("source numeric observation missing")
            ytype = ycell.get(O + "value-type", "UNSPECIFIED")
            ystyle = ycell.get(T + "style-name", "UNSPECIFIED")
            yfmt = formats.get(styles_for_cell.get(ystyle), "UNRESOLVED")
            rtype = rcell.get(O + "value-type", "UNSPECIFIED")
            rstyle = rcell.get(T + "style-name", "UNSPECIFIED")
            rfmt = formats.get(styles_for_cell.get(rstyle), "UNRESOLVED")
            months[month] = (ytype, yfmt, rtype, rfmt)
        if set(months) != MONTHS:
            raise SourceUnavailable("incomplete nine-variant source window")
        patterns = Counter(months.values())
        report.append({
            "variant_ordinal_without_original_us": len(report) + 1,
            "source_month_count": len(months),
            "yield_and_return_type_style_histogram": [{
                "yield_value_type": key[0],
                "yield_display_format": key[1],
                "yield_unit_class": storage_semantics(key[0], key[1]),
                "return_value_type": key[2],
                "return_display_format": key[3],
                "return_unit_class": storage_semantics(key[2], key[3]),
                "month_count": count,
            } for key, count in sorted(patterns.items())],
        })
    if len(report) != 9:
        raise SourceUnavailable("expected 9 common-formula country/variant sheets")
    return {
        "original_source_sha_verified": True,
        "country_variant_sheets": 9,
        "window": "2020-01..2022-12",
        "storage_census": report,
        "yield_economic_scale_certified": False,
        "formula_economic_semantics_certified": False,
        "historical_pit_certified": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
    }


def main() -> None:
    raw = fetch(PUBLISHER + "/api/access/datafile/" + str(SOURCE_ID), 5_000_000)
    print("SWINKELS_9_SERIES_SOURCE_UNIT_CENSUS=" + json.dumps(inspect(raw), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        print("SWINKELS_9_SERIES_SOURCE_UNIT_CENSUS=BLOCKED: " + str(exc))
        sys.exit(2)
