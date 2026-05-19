#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
from __future__ import annotations
"""
apply_colors.py

Generate Google Docs API batch-update JSON to apply conditional green/red
text colors on Delta-vs-forecast rows in the Block Performance Digest tables.

Coloring scope (both conditions must hold):
  - Row: a "Delta vs. <forecast>" row (AP / Q2OL / etc., in %, pts, or bps)
  - Column: a "Pacing" column (April Pacing = col 1, Q2 Pacing = col 5)

Magnitude thresholds (applied to the delta value, proportional for bps):
  -  delta >= +0.5%   → green
  -  delta <= -0.5%   → red
  -  otherwise        → no color (yellow band)

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
    "Delta vs. AP (%)", "Delta vs. AP (pts)", "Delta vs. AP (bps)",
    "Delta vs. Q2OL (%)", "Delta vs. Q2OL (pts)", "Delta vs. Q2OL (bps)",
    "Delta vs. Q1OL (%)", "Delta vs. Q1OL (pts)", "Delta vs. Q1OL (bps)",
    "Delta vs. Q3OL (%)", "Delta vs. Q3OL (pts)", "Delta vs. Q3OL (bps)",
    "Delta vs. Q4OL (%)", "Delta vs. Q4OL (pts)", "Delta vs. Q4OL (bps)",
}

# Columns to color: April Pacing (1) and Q2/Q-current Pacing (5)
PACING_COLUMNS = {1, 5}

# Magnitude threshold — values with |delta| < THRESHOLD get no color
THRESHOLD = 0.5

# Values that should NOT be colored (non-numeric or missing)
SKIP_VALUES = {"", "--", "nm"}


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
# Parsing + classification
# ---------------------------------------------------------------------------

def parse_delta(text: str):
    """Parse a delta cell. Returns (value, unit) or (None, None).

    Units: 'pct', 'pts', 'bps'. Parens indicate a negative.
    """
    if not text or text in SKIP_VALUES:
        return None, None
    t = text.strip().replace("\xa0", " ")
    is_neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(",", "").replace("+", "").replace(" ", "")
    if t.endswith("bps"):
        unit, t = "bps", t[:-3]
    elif t.endswith("pts"):
        unit, t = "pts", t[:-3]
    elif t.endswith("%"):
        unit, t = "pct", t[:-1]
    else:
        return None, None
    try:
        v = float(t)
    except ValueError:
        return None, None
    return (-v if is_neg else v), unit


def parse_rate_pct(text: str):
    """Parse a rate cell like '1.87%' → 1.87. Returns None if not a rate."""
    if not text:
        return None
    t = text.strip().replace("%", "").replace(",", "").replace(" ", "")
    try:
        return float(t)
    except ValueError:
        return None


def classify(value, unit, base_rate_pct=None):
    """Return 'green', 'red', or None (no color).

    For bps, converts to proportional % using base_rate_pct before thresholding.
    """
    if value is None or unit is None:
        return None
    if unit == "bps":
        if base_rate_pct is None or base_rate_pct == 0:
            return None
        # delta (bps) / rate (bps) = proportional delta in absolute (e.g. -0.0107)
        # Convert to % points: multiply by 100
        proportional = value / (base_rate_pct * 100) * 100
        v = proportional
    else:
        # pct and pts treated identically (both are already in percentage points)
        v = value
    if v >= THRESHOLD:
        return "green"
    if v <= -THRESHOLD:
        return "red"
    return None


# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------

def build_color_requests(body: list, tab_id: str) -> list[dict]:
    """Scan tables; color only (Pacing col) x (Delta row) cells past threshold."""
    requests = []

    for elem in body:
        tbl = elem.get("table")
        if not tbl:
            continue

        rows = tbl["tableRows"]
        for row_idx, row in enumerate(rows):
            cells = row.get("tableCells", [])
            if not cells:
                continue

            first_text = extract_cell_text(cells[0])
            if first_text not in DELTA_LABELS:
                continue

            is_bps = "(bps)" in first_text
            # For bps rows, the rate value row sits 2 rows above
            rate_cells = (
                rows[row_idx - 2].get("tableCells", [])
                if is_bps and row_idx >= 2
                else []
            )

            for col_idx, cell in enumerate(cells):
                if col_idx not in PACING_COLUMNS:
                    continue

                # Aggregate all text-run content + index span for this cell so
                # that numbers split across multiple runs (e.g. prior formatting
                # left "(2 bps" and ")" as separate runs) still parse correctly.
                aggregate = ""
                span_start = None
                span_end = None
                for p in cell.get("content", []):
                    for el in p.get("paragraph", {}).get("elements", []):
                        tr = el.get("textRun", {})
                        content = tr.get("content", "")
                        s = el.get("startIndex")
                        e = el.get("endIndex")
                        if s is None or e is None:
                            continue
                        aggregate += content
                        if span_start is None:
                            span_start = s
                        span_end = e

                text = aggregate.strip()
                if span_start is None:
                    continue

                value, unit = parse_delta(text)
                if unit is None:
                    continue

                base_rate = None
                if is_bps and col_idx < len(rate_cells):
                    base_rate = parse_rate_pct(extract_cell_text(rate_cells[col_idx]))

                verdict = classify(value, unit, base_rate)
                if verdict is None:
                    continue

                # Trim trailing newline from the range end
                range_end = span_end - 1 if aggregate.endswith("\n") else span_end
                if range_end <= span_start:
                    continue

                color = GREEN if verdict == "green" else RED
                requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": span_start,
                            "endIndex": range_end,
                            "tabId": tab_id,
                        },
                        "textStyle": {
                            "foregroundColor": {"color": {"rgbColor": color}}
                        },
                        "fields": "foregroundColor",
                    }
                })

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
        description="Apply conditional green/red colors to Delta-vs-forecast cells in the Pacing columns."
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
