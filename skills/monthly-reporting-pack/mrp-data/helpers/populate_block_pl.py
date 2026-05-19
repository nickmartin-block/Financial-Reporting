#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
from __future__ import annotations
"""populate_block_pl.py

Generate Google Docs API batch-update JSON to populate the Block P&L
Overview table (Test tab Table 2, 30 rows x 7 cols) from the mrp_data.py
JSON packet.

Two passes (run sequentially with a doc re-read in between, like Flash):
  --pass values   populate data cells (text + Roboto 10pt + CENTER + bold-for-totals)
  --pass colors   apply green/red to vs.OL cells (polarity-aware)

Safety:
  Refuses to write if --tab targets the MRP reference tab (t.ea3bz9hprpol).
  Only the Test tab (or any other non-MRP tab) is writable.

Usage:
    # Values pass
    cd ~/skills/gdrive && uv run gdrive-cli.py docs get <DOC_ID> --include-tabs > /tmp/mrp_doc.json
    python3 populate_block_pl.py --packet /tmp/mrp_out_2026_04.json \
                                 --doc /tmp/mrp_doc.json --tab <TAB_ID> --pass values \
        | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update <DOC_ID>)

    # Colors pass (re-read first)
    cd ~/skills/gdrive && uv run gdrive-cli.py docs get <DOC_ID> --include-tabs > /tmp/mrp_doc_v2.json
    python3 populate_block_pl.py --packet /tmp/mrp_out_2026_04.json \
                                 --doc /tmp/mrp_doc_v2.json --tab <TAB_ID> --pass colors \
        | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update <DOC_ID>)
"""

import argparse
import json
import sys

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

MRP_REFERENCE_TAB = "t.ea3bz9hprpol"  # the manual April'26 MRP tab — read-only

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

# Packet row schema: cells[0..5] map to doc cell columns 1..6 (col 0 = label, untouched).
PACKET_CELLS_TO_DOC_COLS = [1, 2, 3, 4, 5, 6]

# Which packet cell indices are "vs OL $" deltas → subject to coloring.
VS_OL_CELL_INDICES = [2, 5]  # packet col 2 (Month vs OL) + col 5 (QTD vs OL)

# Color thresholds — magnitude must exceed to receive non-black color.
DELTA_DOLLAR_THRESHOLD_M = 0.5  # $M
PTS_THRESHOLD = 0.5             # pts (for rate-row pts deltas)

GREEN = {"red": 0.0, "green": 0.48, "blue": 0.2}
RED = {"red": 0.8, "green": 0.0, "blue": 0.0}
BLACK = {"red": 0.0, "green": 0.0, "blue": 0.0}
GAP_RED = {"red": 0.85, "green": 0.16, "blue": 0.16}

# Tokens that always render neutral (no color).
NEUTRAL_TOKENS = {"--", "nm", "N/A", "n/a", "NA", "", "[GAP]"}


# ---------------------------------------------------------------------------
# Doc loaders
# ---------------------------------------------------------------------------

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


def find_block_pl_table(content: list[dict]) -> dict | None:
    """Locate the Block P&L Overview table: 30 rows x 7 cols with R02 label 'Gross profit'."""
    for elem in content:
        if "table" not in elem:
            continue
        tbl = elem["table"]
        rows = tbl.get("rows", 0)
        cols = tbl.get("columns", 0)
        if rows != 30 or cols != 7:
            continue
        try:
            label_text = _cell_full_text(tbl["tableRows"][2]["tableCells"][0]).strip()
        except (IndexError, KeyError):
            continue
        if label_text.startswith("Gross profit"):
            return tbl
    return None


# ---------------------------------------------------------------------------
# Cell helpers
# ---------------------------------------------------------------------------

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


def _cell_full_text(cell: dict) -> str:
    return "".join(pe["textRun"].get("content", "") for pe in _cell_text_runs(cell))


def _cell_first_start(cell: dict) -> int | None:
    runs = _cell_text_runs(cell)
    return runs[0].get("startIndex") if runs else None


def _cell_existing_text_range(cell: dict) -> tuple[bool, int, int]:
    """(has_real_text, start_index, end_before_trailing_newline)."""
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


# ---------------------------------------------------------------------------
# Values pass
# ---------------------------------------------------------------------------

def build_cell_value_requests(
    cell: dict,
    value: str,
    tab_id: str,
    bold: bool = False,
    is_gap: bool = False,
) -> list[dict]:
    """Delete existing cell text then insert + style new value.
    For gap cells, the inserted text is rendered red."""
    has_text, ex_start, ex_end = _cell_existing_text_range(cell)
    cell_start = _cell_first_start(cell)
    if cell_start is None:
        return []

    requests: list[dict] = []

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
        return requests  # cell cleared

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


def build_label_bold_request(label_cell: dict, tab_id: str, bold: bool) -> dict | None:
    """Toggle bold on an existing label cell without touching its text."""
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
    packet: dict,
    table: dict,
    tab_id: str,
) -> tuple[list[dict], int, list[str]]:
    requests: list[dict] = []
    cells_written = 0
    warnings: list[str] = []

    table_rows = table.get("tableRows", [])

    for row_spec in packet["block_pl_overview"]["rows"]:
        row_idx = row_spec["row_idx"]
        if row_idx >= len(table_rows):
            warnings.append(f"Doc table missing row {row_idx} ({row_spec['label']})")
            continue
        doc_cells = table_rows[row_idx].get("tableCells", [])

        is_total = row_spec.get("is_total", False)
        is_gap = row_spec.get("is_gap", False)
        is_header = row_spec.get("is_section_header", False)

        # Bold the label for totals (always re-apply; idempotent)
        if doc_cells:
            label_req = build_label_bold_request(doc_cells[0], tab_id, bold=is_total)
            if label_req:
                requests.append(label_req)

        # Skip data cells for section headers (no values to write)
        if is_header:
            continue

        for packet_col, doc_col in enumerate(PACKET_CELLS_TO_DOC_COLS):
            if doc_col >= len(doc_cells):
                warnings.append(f"Row {row_idx} ({row_spec['label']}): doc has no col {doc_col}")
                continue
            cell_data = row_spec["cells"][packet_col]
            value = cell_data.get("formatted", "")
            reqs = build_cell_value_requests(
                doc_cells[doc_col], value, tab_id,
                bold=is_total, is_gap=is_gap,
            )
            if reqs:
                requests.extend(reqs)
                cells_written += 1

    return requests, cells_written, warnings


# ---------------------------------------------------------------------------
# Colors pass
# ---------------------------------------------------------------------------

def _parse_signed_numeric(s: str) -> tuple[str, float] | None:
    """Return (sign_form, magnitude) where sign_form ∈ {plain, plus, minus, parens}.
    magnitude is always positive."""
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

    # Strip unit suffix
    for suf in (" pts", "pts", "%", "M", "B", "K"):
        if inner.endswith(suf):
            inner = inner[: -len(suf)].strip()
            break
    if inner.startswith("$"):
        inner = inner[1:].strip()

    try:
        return sign_form, float(inner.replace(",", ""))
    except ValueError:
        return None


def cell_signed_value(text: str) -> float | None:
    """Return the signed numeric value of a formatted cell, or None if non-numeric.
    Parens treated as negative."""
    s = text.strip().replace("\n", "")
    if not s or s in NEUTRAL_TOKENS:
        return None
    parsed = _parse_signed_numeric(s)
    if parsed is None:
        return None
    sign_form, magnitude = parsed
    return -magnitude if sign_form in ("parens", "minus") else magnitude


def color_for_cell(value: float, polarity: str, kind: str) -> dict:
    """Return RGB dict for the given signed value + row polarity + cell kind.

    polarity: 'revenue' | 'cost' | 'rate'
      revenue: positive variance = green (good)
      cost: positive variance = red (over budget, bad); negative = green
      rate: positive variance = green (good)
    kind: 'vs_ol_dollar' | 'pts' | 'yoy_pct' | 'actual'
      Only vs_ol_dollar + pts cells get colored. Others stay black.
    """
    if kind == "vs_ol_dollar":
        threshold = DELTA_DOLLAR_THRESHOLD_M  # magnitude in $M
        magnitude_m = abs(value) / 1_000_000
        if magnitude_m < threshold:
            return BLACK
    elif kind == "pts":
        threshold = PTS_THRESHOLD
        magnitude_pts = abs(value) * 100  # value is decimal; pts = value * 100
        if magnitude_pts < threshold:
            return BLACK
    else:
        return BLACK

    if polarity == "cost":
        # For cost, positive variance (actual > plan) is UNFAVORABLE = red
        return RED if value > 0 else GREEN
    # revenue / rate: positive = favorable = green
    return GREEN if value > 0 else RED


def build_color_requests(
    packet: dict,
    table: dict,
    tab_id: str,
) -> tuple[list[dict], dict[str, int], list[str]]:
    requests: list[dict] = []
    counts = {"green": 0, "red": 0, "black": 0, "gap": 0}
    warnings: list[str] = []

    table_rows = table.get("tableRows", [])

    for row_spec in packet["block_pl_overview"]["rows"]:
        row_idx = row_spec["row_idx"]
        if row_idx >= len(table_rows):
            continue
        doc_cells = table_rows[row_idx].get("tableCells", [])
        polarity = row_spec.get("polarity", "revenue")

        # Gap rows keep their red foreground from the values pass; no re-color.
        if row_spec.get("is_gap"):
            counts["gap"] += sum(1 for _ in row_spec["cells"])
            continue

        # Section headers: no data to color
        if row_spec.get("is_section_header"):
            continue

        for packet_col, doc_col in enumerate(PACKET_CELLS_TO_DOC_COLS):
            if doc_col >= len(doc_cells):
                continue
            cell_data = row_spec["cells"][packet_col]
            raw_val = cell_data.get("raw")
            kind = cell_data.get("kind", "actual")

            # Only color vs_ol_dollar and pts cells; everything else stays black.
            if kind == "vs_ol_dollar":
                pass  # apply color
            elif kind == "pts":
                pass  # apply color
            else:
                color, key = BLACK, "black"
                _emit_color(doc_cells[doc_col], color, tab_id, requests, counts, key)
                continue

            if raw_val is None:
                color, key = BLACK, "black"
            else:
                color = color_for_cell(float(raw_val), polarity, kind)
                if color == GREEN:
                    key = "green"
                elif color == RED:
                    key = "red"
                else:
                    key = "black"

            _emit_color(doc_cells[doc_col], color, tab_id, requests, counts, key)

    return requests, counts, warnings


def _emit_color(cell: dict, color: dict, tab_id: str,
                requests: list[dict], counts: dict[str, int], key: str) -> None:
    rng = _cell_full_range(cell)
    if rng is None:
        return
    start, end = rng
    text_runs = _cell_text_runs(cell)
    if text_runs and text_runs[-1]["textRun"].get("content", "").endswith("\n"):
        end -= 1
    if end <= start:
        return
    requests.append({
        "updateTextStyle": {
            "range": {"startIndex": start, "endIndex": end, "tabId": tab_id},
            "textStyle": {"foregroundColor": {"color": {"rgbColor": color}}},
            "fields": "foregroundColor",
        }
    })
    counts[key] += 1


# ---------------------------------------------------------------------------
# Request ordering
# ---------------------------------------------------------------------------

def request_sort_key(req: dict) -> int:
    """Sort requests ascending by startIndex/location index. Docs API processes
    in order and auto-shifts later indices for earlier inserts/deletes."""
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

def main() -> int:
    p = argparse.ArgumentParser(description="Populate Block P&L Overview (Test tab Table 2)")
    p.add_argument("--packet", required=True, help="mrp_data.py JSON packet path")
    p.add_argument("--doc", required=True, help="Docs API output for the target doc (gdrive-cli docs get --include-tabs)")
    p.add_argument("--tab", required=True, help="Target tab ID (must NOT be the MRP reference tab)")
    p.add_argument("--pass", dest="pass_", choices=["values", "colors"], default="values")
    args = p.parse_args()

    # Safety guard
    if args.tab == MRP_REFERENCE_TAB:
        print(f"ERROR: refusing to write to the MRP reference tab ({args.tab}). "
              f"Pass a Test tab (e.g., t.3mz1duijrdf1).", file=sys.stderr)
        return 2

    try:
        with open(args.packet) as f:
            packet = json.load(f)
    except Exception as e:
        print(f"Error loading packet: {e}", file=sys.stderr)
        return 1

    try:
        doc = load_doc(args.doc)
    except Exception as e:
        print(f"Error loading doc JSON: {e}", file=sys.stderr)
        return 1

    content = get_tab_content(doc, args.tab)
    if content is None:
        print(f"ERROR: tab {args.tab} not found in doc.", file=sys.stderr)
        return 1

    table = find_block_pl_table(content)
    if table is None:
        print(f"ERROR: could not locate Block P&L table (30x7 with 'Gross profit' at R02) in tab {args.tab}.", file=sys.stderr)
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
