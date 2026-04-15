#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
from __future__ import annotations
"""
apply_colors.py

Generate Google Docs API batch-update JSON to apply conditional green/red
text colors on Delta rows in the Block Performance Digest tables.

Positive deltas → green, negative deltas → red, zero/nm/-- → no color.
Colors both the delta percentage cells AND the corresponding metric value
cells (the row showing absolute dollar/count values).

Usage:
    python3 apply_colors.py DOC_JSON TAB_ID

Output:
    Prints {"requests": [...]} JSON to stdout, ready for:
        cat output.json | gdrive docs batch-update DOC_ID

Must be run AFTER populate_tables.py (needs values in Delta rows).
Requires a fresh Doc read (indices shift after table population).
"""

import json
import sys
import argparse

# ---------------------------------------------------------------------------
# Color constants — match the published 3/31 digest exactly
# ---------------------------------------------------------------------------

GREEN = {
    "red": 0.04313725490196078,
    "green": 0.5019607843137255,
    "blue": 0.2627450980392157,
}

RED = {
    "red": 0.7725490196078432,
    "green": 0.2235294117647059,
    "blue": 0.1607843137254902,
}

# Row labels that should receive conditional coloring
DELTA_LABELS = {
    "Delta vs. AP (%)", "Delta vs. AP (pts)",
    "Delta vs. Q2OL (%)", "Delta vs. Q2OL (pts)", "Delta vs. Q2OL (bps)",
}

# Values that should NOT be colored
SKIP_VALUES = {"", "--", "nm"}

# Values treated as zero (no color)
ZERO_VALUES = {"0%", "0.0%", "0 bps", "0 pts", "(0 bps)", "(0 pts)"}


# ---------------------------------------------------------------------------
# Doc parsing
# ---------------------------------------------------------------------------

def get_tab_content(doc: dict, tab_id: str) -> dict:
    """Navigate nested tab structure to find the target tab."""
    def search_tabs(tabs: list) -> dict | None:
        for tab in tabs:
            if tab["tabProperties"]["tabId"] == tab_id:
                return tab
            for child in tab.get("childTabs", []):
                if child["tabProperties"]["tabId"] == tab_id:
                    return child
        return None

    result = search_tabs(doc.get("tabs", []))
    if result is None:
        raise ValueError(f"Tab {tab_id} not found in document")
    return result["documentTab"]["body"]["content"]


def extract_cell_text(cell: dict) -> str:
    """Extract plain text from a table cell element."""
    text = ""
    for p in cell.get("content", []):
        for el in p.get("paragraph", {}).get("elements", []):
            text += el.get("textRun", {}).get("content", "")
    return text.strip()


# ---------------------------------------------------------------------------
# Color logic
# ---------------------------------------------------------------------------

def is_negative(text: str) -> bool:
    """Check if a delta value is negative (parentheses or minus sign)."""
    return text.startswith("(") or text.startswith("-")


def _color_text_runs(cell: dict, color: dict, tab_id: str, requests: list) -> None:
    """Add foreground-color requests for every non-empty text run in *cell*."""
    for p in cell.get("content", []):
        for el in p.get("paragraph", {}).get("elements", []):
            tr = el.get("textRun", {})
            text = tr.get("content", "").strip()
            start = el.get("startIndex")
            end = el.get("endIndex")
            if not text or text in SKIP_VALUES or start is None or end is None:
                continue
            requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": start,
                        "endIndex": end - 1,
                        "tabId": tab_id,
                    },
                    "textStyle": {
                        "foregroundColor": {"color": {"rgbColor": color}}
                    },
                    "fields": "foregroundColor",
                }
            })


def build_color_requests(body: list, tab_id: str) -> list[dict]:
    """Scan all tables for Delta rows and build color update requests.

    Colors both the delta percentage cells AND the corresponding metric
    value cells (the row showing absolute dollar/count values).  The value
    row sits 2 rows above a ``(%)`` / ``(bps)`` delta row or 1 row above a
    ``(pts)`` delta row (Rule of 40).
    """
    requests = []

    for elem in body:
        tbl = elem.get("table")
        if not tbl:
            continue

        table_rows = tbl["tableRows"]

        for row_idx, row in enumerate(table_rows):
            cells = row.get("tableCells", [])
            if not cells:
                continue

            # Check if this is a Delta row by examining the first cell
            first_text = extract_cell_text(cells[0])
            if first_text not in DELTA_LABELS:
                continue

            # Locate the value row: pts → 1 row above, % / bps → 2 rows above
            value_offset = 1 if "pts" in first_text else 2
            value_row_idx = row_idx - value_offset
            value_cells = (
                table_rows[value_row_idx].get("tableCells", [])
                if 0 <= value_row_idx < len(table_rows)
                else []
            )

            # Process data cells (skip label column)
            for col_idx, cell in enumerate(cells):
                if col_idx == 0:
                    continue

                for p in cell.get("content", []):
                    for el in p.get("paragraph", {}).get("elements", []):
                        tr = el.get("textRun", {})
                        text = tr.get("content", "").strip()
                        start = el.get("startIndex")
                        end = el.get("endIndex")

                        if text in SKIP_VALUES:
                            continue
                        if text.replace(" ", "") in ZERO_VALUES:
                            continue

                        color = RED if is_negative(text) else GREEN

                        # Color the delta cell
                        requests.append({
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": start,
                                    "endIndex": end - 1,  # exclude trailing newline
                                    "tabId": tab_id,
                                },
                                "textStyle": {
                                    "foregroundColor": {
                                        "color": {"rgbColor": color}
                                    }
                                },
                                "fields": "foregroundColor",
                            }
                        })

                        # Color the corresponding value row cell
                        if col_idx < len(value_cells):
                            _color_text_runs(
                                value_cells[col_idx], color, tab_id, requests,
                            )

    # Sort descending by startIndex for safe batch application
    requests.sort(
        key=lambda r: r["updateTextStyle"]["range"]["startIndex"],
        reverse=True,
    )
    return requests


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply conditional green/red colors to Delta rows in the digest."
    )
    parser.add_argument("doc_json", help="Path to Doc JSON (from gdrive docs get)")
    parser.add_argument("tab_id", help="Tab ID to process (e.g., t.abc123)")
    args = parser.parse_args()

    doc = json.load(open(args.doc_json))
    body = get_tab_content(doc, args.tab_id)
    requests = build_color_requests(body, args.tab_id)

    green_count = sum(
        1 for r in requests
        if r["updateTextStyle"]["textStyle"]["foregroundColor"]["color"]["rgbColor"]["green"] > 0.4
    )
    red_count = len(requests) - green_count

    print(json.dumps({"requests": requests}))
    print(
        f"Color requests: {len(requests)} (green: {green_count}, red: {red_count})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
