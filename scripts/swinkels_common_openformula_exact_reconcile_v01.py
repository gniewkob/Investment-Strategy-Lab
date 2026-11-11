"""Original publisher 9-series OpenFormula cache reconciliation, research only.

Explicitly translates a strict arithmetic subset of OpenFormula: only yield
B-current/B-previous references, known literals, + - * / ^ and parentheses.
Executes NO source text, Python eval, builtins, functions, imports, or I/O from
formula text. Checks original ODS SHA and compares 36 source-cached returns.

Outputs one canonical symbolic *mathematical expression*, no observations or
source workbook. Exact formula translation proves workbook consistency, NOT
independent economic validity, historical PIT, or decision-model qualification.
"""
from __future__ import annotations

import ast
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
from scripts.swinkels_formula_topology_probe_v01 import (
    SOURCE_ID, SOURCE_BYTES, SOURCE_SHA, T, O, X,
)
from scripts.swinkels_nine_equation3_diagnostic_v01 import (
    MONTHS, SOURCE_WINDOW, SHEETS, extract_nine,
)

REF = re.compile(r"\[\.\$?B\$?(\d+)\]")
ANY_REF = re.compile(r"\[[^\]]{1,130}\]")
ALLOWED_SYMBOLS = frozenset({"Y_PREV", "Y_CURR"})
MAX_NODES = 100


def normalize_source_formula(formula: str, row: int) -> str:
    """Replace strict OpenFormula B references with symbolic source yields."""
    if not isinstance(formula, str) or not formula.startswith("of:=") or len(formula) > 4096:
        raise SourceUnavailable("invalid or excessive source formula")
    all_ref = ANY_REF.findall(formula)
    good_ref = REF.findall(formula)
    if len(all_ref) != 5 or len(good_ref) != len(all_ref):
        raise SourceUnavailable("common formula does not contain five local yield references")
    if type(row) is not int or row < 2:
        raise SourceUnavailable("invalid source formula row")
    def replace(match):
        source_row = int(match.group(1))
        if source_row == row:
            return "Y_CURR"
        if source_row == row - 1:
            return "Y_PREV"
        raise SourceUnavailable("formula uses nonadjacent source yield row")
    expression = REF.sub(replace, formula[4:]).replace("^", "**")
    if len(expression) > 400 or "[" in expression or "]" in expression:
        raise SourceUnavailable("unsupported source formula expression")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise SourceUnavailable("invalid source OpenFormula arithmetic") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise SourceUnavailable("formula AST exceeds bounded size")
    if any(type(node) not in {
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult,
        ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Name, ast.Load,
        ast.Constant,
    } for node in nodes):
        raise SourceUnavailable("formula contains unsafe or unsupported operation")
    names = {node.id for node in nodes if isinstance(node, ast.Name)}
    if names != ALLOWED_SYMBOLS:
        raise SourceUnavailable("formula references unsupported source symbol")
    return expression


def safe_formula_math(expression: str, previous_yield_points: float,
                      current_yield_points: float) -> float:
    if not all(math.isfinite(v) and -10 < v < 100 for v in (
            previous_yield_points, current_yield_points)):
        raise SourceUnavailable("invalid or out-of-range source yield")
    if not isinstance(expression, str) or len(expression) > 400:
        raise SourceUnavailable("invalid symbolic formula length")
    try:
        root = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise SourceUnavailable("invalid symbolic arithmetic") from exc
    if len(list(ast.walk(root))) > MAX_NODES:
        raise SourceUnavailable("oversized mathematical expression")

    def calc(node, depth=0):
        if depth > 50:
            raise SourceUnavailable("formula nesting exceeds limit")
        if isinstance(node, ast.Expression):
            return calc(node.body, depth + 1)
        if isinstance(node, ast.Name) and node.id in ALLOWED_SYMBOLS:
            return previous_yield_points if node.id == "Y_PREV" else current_yield_points
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if not math.isfinite(node.value) or abs(node.value) > 1200:
                raise SourceUnavailable("source literal outside validated range")
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
            val = calc(node.operand, depth + 1)
            return val if isinstance(node.op, ast.UAdd) else -val
        if isinstance(node, ast.BinOp) and type(node.op) in (
                ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow):
            left = calc(node.left, depth + 1)
            right = calc(node.right, depth + 1)
            try:
                if isinstance(node.op, ast.Add):
                    result = left + right
                elif isinstance(node.op, ast.Sub):
                    result = left - right
                elif isinstance(node.op, ast.Mult):
                    result = left * right
                elif isinstance(node.op, ast.Div):
                    result = left / right
                else:
                    if abs(right) > 30:
                        raise SourceUnavailable("unbounded power exponent")
                    result = left ** right
            except (ZeroDivisionError, OverflowError, ValueError) as exc:
                raise SourceUnavailable("source mathematical evaluation failed") from exc
            if not isinstance(result, (int, float)) or not math.isfinite(result):
                raise SourceUnavailable("non-finite source calculation")
            return float(result)
        raise SourceUnavailable("unsupported symbolic formula evaluation")
    result = calc(root)
    if not math.isfinite(result):
        raise SourceUnavailable("nonfinite formula output")
    return result


def collect_source_math(raw: bytes) -> dict:
    # SHA-validated numeric observations are parsed through independent
    # verified ODS reader; this function inspects only expression syntax.
    original = extract_nine(raw)
    if len(raw) != SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise SourceUnavailable("source formula SHA mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            root = ET.fromstring(z.read("content.xml"))
    except (ET.ParseError, zipfile.BadZipFile, KeyError) as exc:
        raise SourceUnavailable("invalid original publisher ODS content") from exc
    source_formulas = {}
    for table in root.iter(T + "table"):
        name = table.get(T + "name")
        if name not in SHEETS:
            continue
        rows = list(table.iter(T + "table-row"))
        pos = None
        header_row = -1
        for idx, row in enumerate(rows[:25]):
            labels = [_cell_label(c, X) for c in _column_cells(row, T)]
            if "observation_date" in labels and "Return M" in labels:
                pos = {
                    "date": labels.index("observation_date"),
                    "ret": labels.index("Return M"),
                }
                header_row = idx
                break
        if pos is None:
            raise SourceUnavailable("missing original country formula header")
        monthly_expr = {}
        for row_number, row in enumerate(rows[header_row + 1:], start=header_row + 2):
            cells = _column_cells(row, T)
            if len(cells) <= max(pos.values()):
                continue
            stamp = cells[pos["date"]].get(O + "date-value", "")
            if not isinstance(stamp, str) or not re.fullmatch(
                    r"20\d{2}-\d{2}-\d{2}(?:T[0-9:]+)?", stamp):
                continue
            month = stamp[:7]
            if month not in MONTHS:
                continue
            if month in monthly_expr:
                raise SourceUnavailable("duplicate source formula month")
            expr = normalize_source_formula(cells[pos["ret"]].get(T + "formula"), row_number)
            monthly_expr[month] = expr
        if set(monthly_expr) != set(MONTHS):
            raise SourceUnavailable("source formula coverage is not 36 months")
        if len(set(monthly_expr.values())) != 1:
            raise SourceUnavailable("formula expression differs across 36 months")
        discrepancies = []
        for idx, month in enumerate(MONTHS):
            prev_y = original[name][SOURCE_WINDOW[idx]]["yield_points"]
            curr_y = original[name][month]["yield_points"]
            original_return = original[name][month]["return_fraction"]
            math_value = safe_formula_math(monthly_expr[month], prev_y, curr_y)
            discrepancies.append(abs(math_value - original_return))
        source_formulas[name] = {
            "months": len(MONTHS),
            "max_abs_cached_return_residual": f"{max(discrepancies):.3e}",
            "rms_cached_return_residual": f"{math.sqrt(sum(x*x for x in discrepancies)/len(discrepancies)):.3e}",
            "exact_openformula_reconciliation": max(discrepancies) <= 1e-11,
            "canonical_symbolic_expression": next(iter(monthly_expr.values())),
        }
    if set(source_formulas) != set(SHEETS):
        raise SourceUnavailable("nine country expression inventory incomplete")
    expressions = {x["canonical_symbolic_expression"] for x in source_formulas.values()}
    return {
        "publisher_original_sha_verified": True,
        "source_mathematical_expression_count": len(expressions),
        "source_canonical_math": next(iter(expressions)) if len(expressions) == 1 else "VARIANT_DIFFERENCES",
        "source_cached_return_reconciliation": source_formulas,
        "independent_economic_method_certified": False,
        "historical_point_in_time_certified": False,
        "model_series_qualified": [],
        "model_state": "HOLD_CASH",
    }


def main():
    raw = fetch(PUBLISHER + "/api/access/datafile/" + str(SOURCE_ID), 5_000_000)
    summary = collect_source_math(raw)
    print("SWINKELS_COMMON_OPENFORMULA_REPRODUCTION=" + json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        print("SWINKELS_COMMON_OPENFORMULA_REPRODUCTION=BLOCKED: " + str(exc))
        sys.exit(2)
