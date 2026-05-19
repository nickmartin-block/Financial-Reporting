#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
from __future__ import annotations
"""populate_stnd_pl.py — Stnd P&L Double Click (Test tab Table 3, 45x4).

Same shape as populate_block_pl.py but for the 4-column Standardized P&L
table. Column layout: label / Actual / YoY Growth / vs. OL. No QTD cols.

Two passes (run sequentially with a doc re-read in between):
  --pass values   populate data cells (text + Roboto 10pt + CENTER + bold-for-totals)
  --pass colors   apply green/red to vs.OL cells (polarity-aware)
"""

import argparse
import json
import sys


MRP_REFERENCE_TAB = "t.ea3bz9hprpol"

# Table 3 cell layout: packet cells[0..2] map to doc cols 1..3
PACKET_CELLS_TO_DOC_COLS = [1, 2, 3]
VS_OL_CELL_INDEX = 2  # cells[2] is vs.OL — the only colored col

DELTA_DOLLAR_THRESHOLD_M = 0.5
GREEN = {"red": 0.0, "green": 0.48, "blue": 0.2}
RED = {"red": 0.8, "green": 0.0, "blue": 0.0}
BLACK = {"red": 0.0, "green": 0.0, "blue": 0.0}
GAP_RED = {"red": 0.85, "green": 0.16, "blue": 0.16}
NEUTRAL_TOKENS = {"--", "nm", "N/A", "n/a", "NA", "", "[GAP]"}


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


def find_stnd_pl_table(content: list[dict]) -> dict | None:
    """45 rows x 4 cols, R00 col 0 starts with 'Standardized P&L'."""
    for elem in content:
        if "table" not in elem:
            continue
        tbl = elem["table"]
        if tbl.get("rows", 0) != 45 or tbl.get("columns", 0) != 4:
            continue
        try:
            label = _cell_text(tbl["tableRows"][0]["tableCells"][0]).strip()
        except (IndexError, KeyError):
            continue
        if label.startswith("Standardized P&L"):
            return tbl
    return None


def _cell_text_runs(cell: dict) -> list[dict]:
    runs = []
    for content_elem in cell.get("content", []):
        para = content_elem.get("paragraph")
        if not para:
            continue
        for pe in para.get("elements", []):
            if "textRun" in pe:
                runs.append(pe)
    return runs


def _cell_text(cell: dict) -> str:
    return "".join(pe["textRun"].get("content", "") for pe in _cell_text_runs(cell)).replace("\n", "").strip()


def _cell_first_start(cell: dict) -> int | None:
    runs = _cell_text_runs(cell)
    return runs[0].get("startIndex") if runs else None


def _cell_existing_text_range(cell: dict) -> tuple[bool, int, int]:
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
    runs = _cell_text_runs(cell)
    if not runs:
        return None
    return runs[0].get("startIndex"), runs[-1].get("endIndex")


def build_cell_value_requests(cell, value, tab_id, bold=False, is_gap=False):
    has_text, ex_start, ex_end = _cell_existing_text_range(cell)
    cell_start = _cell_first_start(cell)
    if cell_start is None:
        return []
    requests = []
    if has_text and ex_end > ex_start:
        requests.append({
            "deleteContentRange": {
                "range": {"startIndex": ex_start, "endIndex": ex_end, "tabId": tab_id}
            }
        })
        insert_at = ex_start
    else:
        insert_at = cell_start
    if not value:
        return requests
    requests.append({
        "insertText": {"location": {"index": insert_at, "tabId": tab_id}, "text": value}
    })
    text_end = insert_at + len(value)
    text_style = {
        "fontSize": {"magnitude": 10, "unit": "PT"},
        "weightedFontFamily": {"fontFamily": "Roboto"},
        "bold": bool(bold),
    }
    if is_gap:
        text_style["foregroundColor"] = {"color": {"rgbColor": GAP_RED}}
    requests.append({
        "updateTextStyle": {
            "range": {"startIndex": insert_at, "endIndex": text_end, "tabId": tab_id},
            "textStyle": text_style,
            "fields": "fontSize,weightedFontFamily,bold" + (",foregroundColor" if is_gap else ""),
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


def build_label_bold_request(label_cell, tab_id, bold):
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


def build_values_requests(packet, table, tab_id):
    requests = []
    cells_written = 0
    warnings = []
    table_rows = table.get("tableRows", [])
    for row_spec in packet["stnd_pl_double_click"]["rows"]:
        row_idx = row_spec["row_idx"]
        if row_idx >= len(table_rows):
            warnings.append(f"Doc table missing row {row_idx} ({row_spec['label']})")
            continue
        doc_cells = table_rows[row_idx].get("tableCells", [])
        is_total = row_spec.get("is_total", False)
        is_gap = row_spec.get("is_gap", False)
        is_header = row_spec.get("is_section_header", False)

        # Section headers in Table 3 keep their label bold; subtotals (is_total) bold too
        if doc_cells:
            label_req = build_label_bold_request(doc_cells[0], tab_id, bold=(is_total or is_header))
            if label_req:
                requests.append(label_req)

        if is_header:
            continue

        for packet_col, doc_col in enumerate(PACKET_CELLS_TO_DOC_COLS):
            if doc_col >= len(doc_cells):
                warnings.append(f"Row {row_idx} ({row_spec['label']}): doc has no col {doc_col}")
                continue
            cell_data = row_spec["cells"][packet_col]
            value = cell_data.get("formatted", "")
            reqs = build_cell_value_requests(doc_cells[doc_col], value, tab_id,
                                              bold=is_total, is_gap=is_gap)
            if reqs:
                requests.extend(reqs)
                cells_written += 1
    return requests, cells_written, warnings


def color_for_value(value: float, polarity: str) -> dict:
    """vs.OL color: cost rows red on positive (over budget), green on negative.
    Below threshold → black."""
    magnitude_m = abs(value) / 1_000_000
    if magnitude_m < DELTA_DOLLAR_THRESHOLD_M:
        return BLACK
    if polarity == "cost":
        return RED if value > 0 else GREEN
    return GREEN if value > 0 else RED


def build_color_requests(packet, table, tab_id):
    requests = []
    counts = {"green": 0, "red": 0, "black": 0, "gap": 0}
    warnings = []
    table_rows = table.get("tableRows", [])
    for row_spec in packet["stnd_pl_double_click"]["rows"]:
        row_idx = row_spec["row_idx"]
        if row_idx >= len(table_rows):
            continue
        doc_cells = table_rows[row_idx].get("tableCells", [])
        polarity = row_spec.get("polarity", "cost")
        if row_spec.get("is_gap"):
            counts["gap"] += 3
            continue
        if row_spec.get("is_section_header"):
            continue
        # Only color the vs.OL cell (cells[2] = doc col 3)
        for packet_col, doc_col in enumerate(PACKET_CELLS_TO_DOC_COLS):
            if doc_col >= len(doc_cells):
                continue
            cell_data = row_spec["cells"][packet_col]
            raw_val = cell_data.get("raw")
            kind = cell_data.get("kind", "actual")
            if kind != "vs_ol_dollar":
                color, key = BLACK, "black"
            elif raw_val is None:
                color, key = BLACK, "black"
            else:
                color = color_for_value(float(raw_val), polarity)
                key = "green" if color == GREEN else ("red" if color == RED else "black")
            rng = _cell_full_range(doc_cells[doc_col])
            if rng is None:
                continue
            start, end = rng
            runs = _cell_text_runs(doc_cells[doc_col])
            if runs and runs[-1]["textRun"].get("content", "").endswith("\n"):
                end -= 1
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


def request_sort_key(req):
    kind_order = {"deleteContentRange": 0, "insertText": 1,
                  "updateTextStyle": 2, "updateParagraphStyle": 3}
    for key, order in kind_order.items():
        if key in req:
            inner = req[key]
            if "range" in inner:
                idx = inner["range"].get("startIndex", 0)
            elif "location" in inner:
                idx = inner["location"].get("index", 0)
            else:
                idx = 0
            return (-idx, order)
    return (0, 0)


def main() -> int:
    p = argparse.ArgumentParser(description="Populate Stnd P&L Double Click (Test tab Table 3)")
    p.add_argument("--packet", required=True)
    p.add_argument("--doc", required=True)
    p.add_argument("--tab", required=True)
    p.add_argument("--pass", dest="pass_", choices=["values", "colors"], default="values")
    args = p.parse_args()

    if args.tab == MRP_REFERENCE_TAB:
        print(f"ERROR: refusing to write to MRP reference tab ({args.tab}).", file=sys.stderr)
        return 2

    with open(args.packet) as f:
        packet = json.load(f)
    doc = load_doc(args.doc)
    content = get_tab_content(doc, args.tab)
    if content is None:
        print(f"ERROR: tab {args.tab} not found.", file=sys.stderr)
        return 1
    table = find_stnd_pl_table(content)
    if table is None:
        print(f"ERROR: Stnd P&L table (45x4) not found in tab {args.tab}.", file=sys.stderr)
        return 1

    if args.pass_ == "values":
        requests, n_cells, warnings = build_values_requests(packet, table, args.tab)
        for w in warnings:
            print(f"WARN: {w}", file=sys.stderr)
        print(f"Values pass: {len(requests)} requests for {n_cells} cells", file=sys.stderr)
    else:
        requests, counts, warnings = build_color_requests(packet, table, args.tab)
        for w in warnings:
            print(f"WARN: {w}", file=sys.stderr)
        print(f"Colors pass: {len(requests)} requests "
              f"(green={counts['green']}, red={counts['red']}, "
              f"black={counts['black']}, gap={counts['gap']})", file=sys.stderr)

    requests.sort(key=request_sort_key)
    print(json.dumps({"requests": requests}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
