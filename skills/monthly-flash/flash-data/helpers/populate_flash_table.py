#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
from __future__ import annotations
"""
populate_flash_table.py

Generate Google Docs API batch-update JSON to populate the Flash summary table
in the Claude tab. Mirrors the weekly-summary populate_tables.py pattern.

Two passes:
  --pass values   (default) populate data cells with text + Roboto 10pt + CENTER
  --pass colors   apply red/green to delta % columns (run AFTER values + re-read)

Usage:
    python3 populate_flash_table.py SHEET_JSON DOC_JSON TAB_ID [--pass values|colors]

    # Values pass:
    cd ~/skills/gdrive && uv run gdrive-cli.py sheets read \
        15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 \
        --range "'MRP Charts & Tables'!L400:S427" > /tmp/flash_sheet.json
    cd ~/skills/gdrive && uv run gdrive-cli.py docs get \
        1faTUvm5CYK-W4J7JeKezbi1aEvRbSJ95vkjMtzc_sJA --include-tabs > /tmp/flash_doc.json
    python3 populate_flash_table.py /tmp/flash_sheet.json /tmp/flash_doc.json t.6lmbmhs5p561 \
        | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update \
              1faTUvm5CYK-W4J7JeKezbi1aEvRbSJ95vkjMtzc_sJA)

    # Colors pass (re-read Doc first so indices are fresh):
    cd ~/skills/gdrive && uv run gdrive-cli.py docs get \
        1faTUvm5CYK-W4J7JeKezbi1aEvRbSJ95vkjMtzc_sJA --include-tabs > /tmp/flash_doc_v2.json
    python3 populate_flash_table.py /tmp/flash_sheet.json /tmp/flash_doc_v2.json t.6lmbmhs5p561 --pass colors \
        | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update \
              1faTUvm5CYK-W4J7JeKezbi1aEvRbSJ95vkjMtzc_sJA)
"""
import argparse
import json
import sys


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

# Doc table columns (Claude tab "Summary Table" — 28 rows × 7 cols)
#   col 0 = label, col 1 = Actual, col 2 = vs. Q2OL $, col 3 = vs. Q2OL %,
#   col 4 = vs. AP %, col 5 = YoY %, col 6 = Mar YoY %
#
# Sheet ranges:
#   MONTHLY    — MRP Charts & Tables!L400:S427 (28 rows × 8 cols)
#                cols 0..7 = label, Actual, OL$, OL%, AP$, AP%, YoY%, Prior-mo YoY%
#   QUARTERLY  — MRP Charts & Tables!T400:Y427 (28 rows × 6 cols, NO label column —
#                labels stay in col L which is shared)
#                cols 0..5 = Actual, OL$, OL%, AP$, AP%, YoY%
#
# Mapping: doc col → sheet col (label col 0 not populated — already in shell).
DOC_TO_SHEET_COL_MONTHLY = {
    1: 1,   # Actual
    2: 2,   # vs. Q2OL $   ← sheet vs. OL $
    3: 3,   # vs. Q2OL %   ← sheet vs. OL %
    4: 5,   # vs. AP %     ← sheet col Q (skip sheet col 4 = vs. AP $)
    5: 6,   # YoY %
    6: 7,   # Mar YoY %    ← sheet Prior-mo YoY %
}

# Quarterly: T-Y range. No label col in the range itself (label stays in col L).
# So sheet col 0 = Actual (T), 1 = OL$ (U), 2 = OL% (V), 3 = AP$ (W), 4 = AP% (X), 5 = YoY% (Y).
# Doc col 6 (Prior-mo YoY) has no QTD equivalent — left empty (cleared in pass).
DOC_TO_SHEET_COL_QUARTERLY = {
    1: 0,   # Actual          ← T
    2: 1,   # vs. Q-OL $       ← U
    3: 2,   # vs. Q-OL %       ← V
    4: 4,   # vs. AP %         ← X (skip W = AP $)
    5: 5,   # YoY %            ← Y
    # doc col 6: no source; values pass will clear stale text
}

# Legacy default (used when --mode isn't passed)
DOC_TO_SHEET_COL = DOC_TO_SHEET_COL_MONTHLY

# Row 0 = period header (col 1 has e.g. "Apr'26"); row 1 = column headers.
# Data rows: doc row N maps 1:1 to sheet row N (range L400:S427 mirrors layout).
HEADER_ROWS = 2
TOTAL_ROWS = 28
DATA_ROW_RANGE = range(HEADER_ROWS, TOTAL_ROWS)  # 2..27 inclusive

# Period header — row 0 col 1 in both sheet and doc.
PERIOD_HEADER = (0, 1)

# Rows whose entire row (label + all data cells) renders bold.
# Row 10 = Block GP, row 26 = Adjusted OI, row 27 = Rule of 40.
BOLD_ROWS = {10, 26, 27}

# Coloring rules per the Flash disclaimer:
#   - YoY columns (5 = YoY %, 6 = Mar YoY %) stay black — never colored.
#   - Variance columns get colored only if the magnitude exceeds the threshold:
#       col 2 (vs. Q2OL $)  → $0.5M
#       col 3 (vs. Q2OL %)  → 1.0%
#       col 4 (vs. AP %)    → 1.0%
DELTA_COL_THRESHOLDS = {
    2: 0.5,   # $M
    3: 1.0,   # %
    4: 1.0,   # %
}

# Variance columns whose values should be reformatted to the 1-decimal-within-±10 rule.
# Rule: |magnitude| ≤ 10 → 1 decimal (9.5%, $9.5M, +5.8 pts).
#       |magnitude| > 10 → integer       (215%, $14M, +22 pts).
# Applies to all variance and YoY columns — matches the published Flash convention
# (e.g. "23%" not "22.6%" for YoY when magnitude > 10).
VARIANCE_COLS_FOR_REFORMAT = (2, 3, 4, 5, 6)

# Row that is itself a percent metric whose Actual (col 1) follows the same ±10 rule
# as variance columns. (R40 actual: "50.1%" → "50%".)
PCT_ACTUAL_ROWS = {27}

GREEN = {"red": 0.0, "green": 0.48, "blue": 0.2}
RED = {"red": 0.8, "green": 0.0, "blue": 0.0}
BLACK = {"red": 0.0, "green": 0.0, "blue": 0.0}

# Columns subject to the colors pass — receive black/green/red foreground.
# col 1 (Actual) is left alone — never recolored.
COLORS_PASS_COLS = (2, 3, 4, 5, 6)

ZERO_TOKENS = {"0%", "0.0%", "0pts", "0 pts", "+0 pts", "-0 pts", "+0.0 pts", "$0M", "$0", "0M", "0", "0.0", "--"}
NEUTRAL_TOKENS = {"--", "nm", "N/A", "n/a", "NA", ""}


# ---------------------------------------------------------------------------
# Sheet / Doc loaders
# ---------------------------------------------------------------------------

def load_sheet(path: str) -> list[list[str]]:
    """Return 2D array of string cell values."""
    with open(path) as f:
        data = json.load(f)
    values = data.get("values") if isinstance(data, dict) else data
    if values is None:
        raise ValueError(f"Sheet JSON missing 'values'. Top-level keys: {list(data.keys())}")
    out = []
    for row in values:
        if isinstance(row, list):
            out.append([str(c) if c is not None else "" for c in row])
        else:
            out.append([])
    return out


def load_doc(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def get_tab_content(doc: dict, tab_id: str) -> list[dict] | None:
    return _search_tabs(doc.get("tabs", []), tab_id)


def _search_tabs(tabs: list[dict], tab_id: str) -> list[dict] | None:
    for tab in tabs:
        if tab.get("tabProperties", {}).get("tabId", "") == tab_id:
            return tab.get("documentTab", {}).get("body", {}).get("content", [])
        child = _search_tabs(tab.get("childTabs", []), tab_id)
        if child is not None:
            return child
    return None


def find_first_table(content: list[dict]) -> dict | None:
    for elem in content:
        if "table" in elem:
            return elem
    return None


# ---------------------------------------------------------------------------
# Cell helpers
# ---------------------------------------------------------------------------

def _cell_text_runs(cell: dict) -> list[dict]:
    """Return list of paragraph elements containing textRuns inside the cell."""
    runs = []
    for content_elem in cell.get("content", []):
        para = content_elem.get("paragraph")
        if not para:
            continue
        for pe in para.get("elements", []):
            if "textRun" in pe:
                runs.append(pe)
    return runs


def _cell_full_text(cell: dict) -> str:
    return "".join(pe["textRun"].get("content", "") for pe in _cell_text_runs(cell))


def _cell_first_start(cell: dict) -> int | None:
    runs = _cell_text_runs(cell)
    return runs[0].get("startIndex") if runs else None


def _cell_existing_text_range(cell: dict) -> tuple[bool, int, int]:
    """
    Returns (has_real_text, start_index, end_index_before_trailing_newline).
    "Real text" means content beyond a single trailing \\n.
    """
    runs = _cell_text_runs(cell)
    if not runs:
        return (False, 0, 0)
    first_start = runs[0].get("startIndex")
    last_end = runs[-1].get("endIndex")
    text = "".join(pe["textRun"].get("content", "") for pe in runs)
    stripped = text.replace("\n", "").strip()
    if stripped and first_start is not None and last_end is not None:
        end_before_newline = last_end - 1 if text.endswith("\n") else last_end
        return (True, first_start, end_before_newline)
    return (False, first_start or 0, first_start or 0)


def _cell_full_range(cell: dict) -> tuple[int, int] | None:
    """Full range covering all text runs in cell (incl. any trailing newline)."""
    runs = _cell_text_runs(cell)
    if not runs:
        return None
    return runs[0].get("startIndex"), runs[-1].get("endIndex")


# ---------------------------------------------------------------------------
# Values pass
# ---------------------------------------------------------------------------

def get_sheet_value(sheet: list[list[str]], row: int, col: int) -> str:
    if row < 0 or row >= len(sheet):
        return ""
    rowdata = sheet[row]
    if col < 0 or col >= len(rowdata):
        return ""
    v = rowdata[col].strip()
    if v in ("#N/A", "#REF!", "#VALUE!", "#DIV/0!"):
        return ""
    return v


def _parse_signed_numeric(s: str) -> tuple[str, str, float, str] | None:
    """Parse a formatted variance string into (sign_form, body_prefix, magnitude, suffix).

    sign_form ∈ {"plain", "plus", "minus", "parens"}.
    body_prefix is the unit prefix kept on the number (e.g. "$").
    suffix is the unit suffix kept on the number (e.g. "%", " pts", "M", "B").
    Returns None if the string can't be parsed as a signed numeric variance.
    """
    s = s.strip()
    if not s:
        return None

    sign_form = "plain"
    inner = s
    if inner.startswith("(") and inner.endswith(")"):
        sign_form = "parens"
        inner = inner[1:-1].strip()
    elif inner.startswith("+"):
        sign_form = "plus"
        inner = inner[1:].strip()
    elif inner.startswith("-"):
        sign_form = "minus"
        inner = inner[1:].strip()

    suffix = ""
    if inner.endswith("%"):
        suffix = "%"
        inner = inner[:-1].strip()
    elif inner.lower().endswith(" pts") or inner.lower().endswith("pts"):
        idx = inner.lower().rfind("pts")
        suffix = " pts"
        inner = inner[:idx].strip()
    elif inner.endswith("M"):
        suffix = "M"
        inner = inner[:-1].strip()
    elif inner.endswith("B"):
        suffix = "B"
        inner = inner[:-1].strip()
    elif inner.endswith("K"):
        suffix = "K"
        inner = inner[:-1].strip()
    elif inner.endswith("bps"):
        suffix = "bps"
        inner = inner[:-3].strip()

    body_prefix = ""
    if inner.startswith("$"):
        body_prefix = "$"
        inner = inner[1:].strip()

    try:
        magnitude = float(inner.replace(",", ""))
    except ValueError:
        return None

    return sign_form, body_prefix, magnitude, suffix


def reformat_variance(value: str) -> str:
    """Apply the 1-decimal-within-±10 rule. % and $M use this rule;
    raw $ amounts (e.g. '$28') get the same — magnitude-based.
    Leaves 'nm', '--', empty, and unparseable strings unchanged.
    """
    if not value:
        return value
    s = value.strip()
    if s in NEUTRAL_TOKENS:
        return value
    parsed = _parse_signed_numeric(s)
    if parsed is None:
        return value
    sign_form, prefix, magnitude, suffix = parsed

    if abs(magnitude) <= 10.0:
        num_str = f"{magnitude:.1f}"
    else:
        # round half-up explicitly (avoid banker's rounding in str.format)
        rounded = int(magnitude + 0.5) if magnitude >= 0 else -int(-magnitude + 0.5)
        num_str = str(rounded)

    body = f"{prefix}{num_str}{suffix}"
    if sign_form == "parens":
        return f"({body})"
    if sign_form == "plus":
        return f"+{body}"
    if sign_form == "minus":
        return f"-{body}"
    return body


def build_cell_value_requests(
    cell: dict,
    value: str,
    tab_id: str,
    bold: bool = False,
) -> list[dict]:
    """Delete existing cell text (if any) then insert + style new value.
    Returns [] if the cell can't be located or value is empty AND cell already empty.
    """
    has_text, ex_start, ex_end = _cell_existing_text_range(cell)
    cell_start = _cell_first_start(cell)
    if cell_start is None:
        return []

    requests: list[dict] = []

    # Always clear existing text — we want stale data wiped even if new value is empty.
    if has_text and ex_end > ex_start:
        requests.append({
            "deleteContentRange": {
                "range": {
                    "startIndex": ex_start,
                    "endIndex": ex_end,
                    "tabId": tab_id,
                }
            }
        })
        insert_at = ex_start
    else:
        insert_at = cell_start

    if not value:
        return requests  # cell cleared, nothing more to insert

    requests.append({
        "insertText": {
            "location": {"index": insert_at, "tabId": tab_id},
            "text": value,
        }
    })
    text_end = insert_at + len(value)
    text_style = {
        "fontSize": {"magnitude": 10, "unit": "PT"},
        "weightedFontFamily": {"fontFamily": "Roboto"},
        "bold": bool(bold),
    }
    requests.append({
        "updateTextStyle": {
            "range": {"startIndex": insert_at, "endIndex": text_end, "tabId": tab_id},
            "textStyle": text_style,
            "fields": "fontSize,weightedFontFamily,bold",
        }
    })
    requests.append({
        "updateParagraphStyle": {
            "range": {"startIndex": insert_at, "endIndex": text_end + 1, "tabId": tab_id},
            "paragraphStyle": {"alignment": "CENTER"},
            "fields": "alignment",
        }
    })
    return requests


def build_label_bold_request(label_cell: dict, tab_id: str, bold: bool) -> dict | None:
    """Apply bold (or unbold) to an existing label cell without disturbing its text."""
    runs = _cell_text_runs(label_cell)
    if not runs:
        return None
    start = runs[0].get("startIndex")
    end = runs[-1].get("endIndex")
    if start is None or end is None:
        return None
    if runs[-1]["textRun"].get("content", "").endswith("\n"):
        end -= 1
    if end <= start:
        return None
    return {
        "updateTextStyle": {
            "range": {"startIndex": start, "endIndex": end, "tabId": tab_id},
            "textStyle": {"bold": bool(bold)},
            "fields": "bold",
        }
    }


def build_values_requests(
    sheet: list[list[str]],
    table_rows: list[dict],
    tab_id: str,
    mode: str = "monthly",
) -> tuple[list[dict], int, list[str]]:
    requests: list[dict] = []
    cells_written = 0
    warnings: list[str] = []

    is_quarterly = (mode == "quarterly")
    col_map = DOC_TO_SHEET_COL_QUARTERLY if is_quarterly else DOC_TO_SHEET_COL_MONTHLY

    # Period header (row 0 col 1). In monthly mode this is sheet (0, 1) = M400 ("Apr'26").
    # In quarterly mode it's sheet (0, 0) since T-Y has no label col → T400 ("Q2 QTD").
    pr, pc_doc = PERIOD_HEADER
    pc_sheet = 0 if is_quarterly else 1
    if pr < len(table_rows):
        cells = table_rows[pr].get("tableCells", [])
        if pc_doc < len(cells):
            value = get_sheet_value(sheet, pr, pc_sheet)
            if value:
                reqs = build_cell_value_requests(cells[pc_doc], value, tab_id)
                if reqs:
                    requests.extend(reqs)
                    cells_written += 1
        else:
            warnings.append(f"Period header: row {pr} has no col {pc_doc}")
    else:
        warnings.append(f"Period header: doc has no row {pr}")

    # Data rows 2..27
    for r in DATA_ROW_RANGE:
        if r >= len(table_rows):
            warnings.append(f"Doc table missing row {r}")
            continue
        cells = table_rows[r].get("tableCells", [])
        is_bold = r in BOLD_ROWS

        if cells:
            label_req = build_label_bold_request(cells[0], tab_id, bold=is_bold)
            if label_req:
                requests.append(label_req)

        # Populate the data columns per the active map.
        for doc_col, sheet_col in col_map.items():
            if doc_col >= len(cells):
                warnings.append(f"Row {r}: doc has no col {doc_col}")
                continue
            value = get_sheet_value(sheet, r, sheet_col)
            if doc_col in VARIANCE_COLS_FOR_REFORMAT:
                value = reformat_variance(value)
            elif doc_col == 1 and r in PCT_ACTUAL_ROWS:
                value = reformat_variance(value)
            reqs = build_cell_value_requests(cells[doc_col], value, tab_id, bold=is_bold)
            if reqs:
                requests.extend(reqs)
                cells_written += 1

        # In quarterly mode, doc col 6 (Prior-mo YoY) has no QTD equivalent.
        # Clear any stale text but don't insert anything.
        if is_quarterly and 6 < len(cells):
            reqs = build_cell_value_requests(cells[6], "", tab_id, bold=is_bold)
            if reqs:
                requests.extend(reqs)

    return requests, cells_written, warnings


# ---------------------------------------------------------------------------
# Colors pass
# ---------------------------------------------------------------------------

def cell_sign_with_threshold(text: str, threshold: float) -> str:
    """Return 'positive' | 'negative' | 'neutral'.
    Neutral if |magnitude| < threshold, empty, or a known non-numeric token.
    """
    s = text.strip().replace("\n", "")
    if not s or s in NEUTRAL_TOKENS or s in ZERO_TOKENS:
        return "neutral"
    parsed = _parse_signed_numeric(s)
    if parsed is None:
        return "neutral"
    sign_form, _prefix, magnitude, _suffix = parsed
    # "within ±threshold" is inclusive (|x| ≤ threshold → no color)
    if abs(magnitude) <= threshold:
        return "neutral"
    if magnitude == 0:
        return "neutral"
    if sign_form == "parens" or sign_form == "minus":
        return "negative"
    return "positive"


def build_color_requests(
    table_rows: list[dict],
    tab_id: str,
) -> tuple[list[dict], dict[str, int], list[str]]:
    """Apply foreground color to data cells in cols 2-6.
    cols 2 (vs. Q2OL $), 3 (vs. Q2OL %), 4 (vs. AP %) → green/red if magnitude
    exceeds the col's threshold; black otherwise.
    cols 5 (YoY %), 6 (Mar YoY %) → always black (per Flash disclaimer).
    Unconditionally writes the foreground color so the cell state is deterministic
    (i.e. prior runs' colors get cleared even when the cell becomes neutral).
    """
    requests: list[dict] = []
    counts = {"green": 0, "red": 0, "black": 0}
    warnings: list[str] = []

    for r in DATA_ROW_RANGE:
        if r >= len(table_rows):
            continue
        cells = table_rows[r].get("tableCells", [])
        for doc_col in COLORS_PASS_COLS:
            if doc_col >= len(cells):
                continue
            cell = cells[doc_col]
            text = _cell_full_text(cell)
            stripped = text.strip().replace("\n", "")
            if not stripped:
                continue  # nothing to color

            # Decide color
            threshold = DELTA_COL_THRESHOLDS.get(doc_col)
            if threshold is None:
                color = BLACK
                key = "black"
            else:
                sign = cell_sign_with_threshold(text, threshold)
                if sign == "positive":
                    color, key = GREEN, "green"
                elif sign == "negative":
                    color, key = RED, "red"
                else:
                    color, key = BLACK, "black"

            rng = _cell_full_range(cell)
            if rng is None:
                continue
            start, end = rng
            # Trim trailing newline (don't color the paragraph terminator)
            text_runs = _cell_text_runs(cell)
            if text_runs and text_runs[-1]["textRun"].get("content", "").endswith("\n"):
                end = end - 1
            if end <= start:
                continue
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end, "tabId": tab_id},
                    "textStyle": {"foregroundColor": {"color": {"rgbColor": color}}},
                    "fields": "foregroundColor",
                }
            })
            counts[key] += 1

    return requests, counts, warnings


# ---------------------------------------------------------------------------
# Sorting / output
# ---------------------------------------------------------------------------

def request_sort_key(req: dict) -> int:
    for key in ("deleteContentRange", "insertText", "updateTextStyle", "updateParagraphStyle"):
        if key in req:
            inner = req[key]
            if "range" in inner:
                return inner["range"].get("startIndex", 0)
            if "location" in inner:
                return inner["location"].get("index", 0)
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("sheet_json")
    p.add_argument("doc_json")
    p.add_argument("tab_id")
    p.add_argument("--pass", dest="pass_", choices=["values", "colors"], default="values")
    p.add_argument("--mode", choices=["monthly", "quarterly"], default="monthly",
                   help="monthly: read M-S (8 sheet cols). quarterly: read T-Y (6 sheet cols, no Prior-mo YoY).")
    args = p.parse_args()

    try:
        sheet = load_sheet(args.sheet_json)
    except Exception as e:
        print(f"Error loading sheet JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        doc = load_doc(args.doc_json)
    except Exception as e:
        print(f"Error loading doc JSON: {e}", file=sys.stderr)
        sys.exit(1)

    content = get_tab_content(doc, args.tab_id)
    if content is None:
        print(f"Error: tab '{args.tab_id}' not found.", file=sys.stderr)
        sys.exit(1)

    table_elem = find_first_table(content)
    if table_elem is None:
        print(f"Error: no table found in tab '{args.tab_id}'.", file=sys.stderr)
        sys.exit(1)

    table_rows = table_elem["table"].get("tableRows", [])
    rows = table_elem["table"].get("rows", 0)
    cols = table_elem["table"].get("columns", 0)
    print(f"Found Claude tab table: {rows} rows × {cols} cols", file=sys.stderr)
    if rows != TOTAL_ROWS or cols != 7:
        print(f"Warning: expected {TOTAL_ROWS} rows × 7 cols, got {rows} × {cols}", file=sys.stderr)

    if args.pass_ == "values":
        if len(sheet) < TOTAL_ROWS:
            print(f"Warning: sheet has {len(sheet)} rows, expected {TOTAL_ROWS}", file=sys.stderr)
        requests, written, warnings = build_values_requests(sheet, table_rows, args.tab_id, mode=args.mode)
        for w in warnings:
            print(f"Warning: {w}", file=sys.stderr)
        requests.sort(key=request_sort_key, reverse=True)
        print(f"Values pass ({args.mode}): {written} cells, {len(requests)} requests", file=sys.stderr)
    else:
        requests, counts, warnings = build_color_requests(table_rows, args.tab_id)
        for w in warnings:
            print(f"Warning: {w}", file=sys.stderr)
        requests.sort(key=request_sort_key, reverse=True)
        print(
            f"Colors pass: green={counts['green']}, red={counts['red']}, "
            f"black={counts['black']}, requests={len(requests)}",
            file=sys.stderr,
        )

    json.dump({"requests": requests}, sys.stdout, indent=2)
    print(file=sys.stdout)


if __name__ == "__main__":
    main()
