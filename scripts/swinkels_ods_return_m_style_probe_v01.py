"""Bounded original Swinkels ODS Return M cell-style audit, not return calculation."""
from __future__ import annotations

from collections import Counter
import hashlib
import io
import json
import sys
import xml.etree.ElementTree as ET
import zipfile

from scripts.research_swinkels_original_source_probe_v01 import (
    PUBLISHER, SourceUnavailable, fetch, _column_cells, _cell_label
)

ODS_ID = 512630
ODS_SIZE = 913425
ODS_SHA = "90a634328d14dec82bfcbbac83625105c49ff93e9ea2771762c2294d42435847"
T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
O = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
X = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
S = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}"
N = "{urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0}"

def audit():
    raw = fetch(PUBLISHER + "/api/access/datafile/" + str(ODS_ID), 5000000)
    if len(raw) != ODS_SIZE or hashlib.sha256(raw).hexdigest() != ODS_SHA:
        raise SourceUnavailable("source ODS digest/length mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for name in ("content.xml", "styles.xml"):
            if z.getinfo(name).file_size > 32000000:
                raise SourceUnavailable("ODS XML oversized")
        root = ET.fromstring(z.read("content.xml"))
        styles_root = ET.fromstring(z.read("styles.xml"))
    style_to_data = {}
    data_type = {}
    for parent in (root, styles_root):
        for node in parent.iter(S+"style"):
            key = node.get(S+"name")
            d = node.get(S+"data-style-name")
            if key and d:
                style_to_data[key] = d
        for kind in ("percentage-style", "number-style", "currency-style"):
            for node in parent.iter(N+kind):
                k = node.get(S+"name")
                if k:
                    data_type[k] = kind
    results = []
    for table in root.iter(T+"table"):
        rows = list(table.iter(T+"table-row"))
        source_name = table.get(T+"name", "")
        index = None
        header = -1
        for i,row in enumerate(rows[:25]):
            cells = _column_cells(row,T)
            labels = [_cell_label(cell,X) for cell in cells]
            if "observation_date" in labels and "Return M" in labels:
                index = labels.index("Return M")
                header = i
                break
        if index is None:
            continue
        count = Counter()
        for row in rows[header+1:]:
            cols = _column_cells(row,T)
            if index >= len(cols):
                continue
            c=cols[index]
            if c.get(O+"value") is None:
                continue
            st=c.get(T+"style-name","UNSPECIFIED")
            typ=c.get(O+"value-type","UNSPECIFIED")
            formula="HAS_FORMULA" if c.get(T+"formula") else "NO_FORMULA"
            data_style=style_to_data.get(st,"UNRESOLVED")
            fmt=data_type.get(data_style,"UNRESOLVED")
            count[(typ,fmt,formula)] += 1
        results.append({"sheet":source_name[:75],"cell_type_style_formula_counts":[
            {"value_type":a,"format_class":b,"formula":c,"count":v}
            for (a,b,c),v in sorted(count.items())]})
    print("SOURCE_SHA256_VERIFIED=true")
    print("RETURN_M_STYLE_AUDIT="+json.dumps(results,sort_keys=True))
    print("RETURN_M_UNIT_CERTIFIED=false")
    print("QUALIFIED_MODEL_SERIES=[]")
    print("M1_M2_M3=HOLD_CASH")

if __name__ == "__main__":
    try:
        audit()
    except (SourceUnavailable, KeyError, ET.ParseError, zipfile.BadZipFile) as e:
        print("RETURN_M_STYLE_AUDIT=BLOCKED: "+str(e))
        sys.exit(2)
