#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
color_markers.py

Reads a Google Doc JSON (from stdin), finds color marker blocks,
and outputs batch-update requests JSON (to stdout) that apply colors and strip markers.

Supported markers:
    «RED»...«/RED»       → Red text (#EA4335)   — manual placeholders
    «BLUE»...«/BLUE»     → Blue text (#4285F4)  — data gaps
    «GREEN»...«/GREEN»   → Green text (#34A853)  — favorable variance
    «WARN»...«/WARN»     → Red text (#D93025)   — unfavorable variance

Usage (pipe with gdrive-cli):
    cd ~/skills/gdrive
    uv run gdrive-cli.py docs get <doc_id> | uv run scripts/color_markers.py <tab_id> [--colors RED,BLUE] | uv run gdrive-cli.py docs batch-update <doc_id>

Legacy usage (standalone, requires services module):
    cd ~/skills/gdrive && uv run scripts/color_markers.py <doc_id> <tab_id> --standalone
"""
import json
import sys

COLOR_DEFS = {
    "RED":   {"red": 0.918, "green": 0.263, "blue": 0.208},  # #EA4335
    "BLUE":  {"red": 0.259, "green": 0.522, "blue": 0.957},  # #4285F4
    "GREEN": {"red": 0.204, "green": 0.659, "blue": 0.325},  # #34A853
    "WARN":  {"red": 0.851, "green": 0.188, "blue": 0.145},  # #D93025
}
DEFAULT_COLORS = list(COLOR_DEFS.keys())


def get_tab_content(tabs, tab_id):
    """Recursively search tabs and childTabs for the given tab_id."""
    for tab in tabs:
        if tab.get("tabProperties", {}).get("tabId") == tab_id:
            return tab.get("documentTab", {}).get("body", {}).get("content", [])
        result = get_tab_content(tab.get("childTabs", []), tab_id)
        if result is not None:
            return result
    return None


def flatten_text(content):
    """
    Returns (flat_text, index_map) where index_map[i] is the Google Docs
    character index corresponding to flat_text[i].
    """
    chars, indices = [], []
    for elem in content:
        para = elem.get("paragraph")
        if not para:
            continue
        for pe in para.get("elements", []):
            tr = pe.get("textRun")
            if tr:
                start = pe["startIndex"]
                for i, ch in enumerate(tr["content"]):
                    chars.append(ch)
                    indices.append(start + i)
    return "".join(chars), indices


def find_blocks_for_color(flat, index_map, color_name):
    """Return list of marker block bounds in document index space for a given color."""
    open_marker = f"\u00ab{color_name}\u00bb"
    close_marker = f"\u00ab/{color_name}\u00bb"
    blocks = []
    pos = 0
    while True:
        o = flat.find(open_marker, pos)
        if o == -1:
            break
        c = flat.find(close_marker, o + len(open_marker))
        if c == -1:
            print(f"Warning: unclosed {open_marker} at flat position {o}", file=sys.stderr)
            break
        blocks.append({
            "color":         color_name,
            "open_start":    index_map[o],
            "open_end":      index_map[o + len(open_marker) - 1] + 1,
            "content_start": index_map[o + len(open_marker)],
            "content_end":   index_map[c],
            "close_start":   index_map[c],
            "close_end":     index_map[c + len(close_marker) - 1] + 1,
        })
        pos = c + len(close_marker)
    return blocks


def find_all_blocks(flat, index_map, colors):
    """Find all marker blocks across all requested colors, sorted by document position."""
    all_blocks = []
    for color_name in colors:
        all_blocks.extend(find_blocks_for_color(flat, index_map, color_name))
    all_blocks.sort(key=lambda b: b["open_start"])
    return all_blocks


def build_requests(blocks, tab_id):
    """
    Build batch-update requests for all blocks.
    Process in reverse order so higher-index deletions don't shift lower-index positions.
    Within each block: delete close marker → color content → delete open marker.
    """
    requests = []
    for b in reversed(blocks):
        rgb = COLOR_DEFS[b["color"]]
        requests += [
            {"deleteContentRange": {
                "range": {"startIndex": b["close_start"], "endIndex": b["close_end"], "tabId": tab_id}
            }},
            {"updateTextStyle": {
                "range": {"startIndex": b["content_start"], "endIndex": b["content_end"], "tabId": tab_id},
                "textStyle": {"foregroundColor": {"color": {"rgbColor": rgb}}},
                "fields": "foregroundColor",
            }},
            {"deleteContentRange": {
                "range": {"startIndex": b["open_start"], "endIndex": b["open_end"], "tabId": tab_id}
            }},
        ]
    return requests


def main():
    if len(sys.argv) < 2:
        print("Usage: ... | color_markers.py <tab_id> [--colors RED,BLUE,GREEN,WARN] | ...", file=sys.stderr)
        sys.exit(1)

    tab_id = sys.argv[1]

    # Parse --colors flag
    colors = DEFAULT_COLORS
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--colors" and i + 1 < len(sys.argv):
            colors = [c.strip().upper() for c in sys.argv[i + 1].split(",")]
            break

    # Read doc JSON from stdin
    doc = json.load(sys.stdin)
    content = get_tab_content(doc.get("tabs", []), tab_id)
    if content is None:
        print(f"Error: tab '{tab_id}' not found in document.", file=sys.stderr)
        sys.exit(1)

    flat, index_map = flatten_text(content)
    blocks = find_all_blocks(flat, index_map, colors)

    counts = {}
    for b in blocks:
        counts[b["color"]] = counts.get(b["color"], 0) + 1
    for color, count in counts.items():
        print(f"Found {count} \u00ab{color}\u00bb block(s).", file=sys.stderr)

    if not blocks:
        print("No color marker blocks found.", file=sys.stderr)
        json.dump({"requests": []}, sys.stdout)
        return

    requests = build_requests(blocks, tab_id)
    json.dump({"requests": requests}, sys.stdout)
    print(f"Generated {len(requests)} requests for {sum(counts.values())} block(s) across {len(counts)} color(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
