#!/usr/bin/env python3
"""
color_markers.py <doc_id> <tab_id>

Finds all «RED»...«/RED» blocks in a Google Doc tab, colors the content red (#ea4335),
and strips the markers. Processes blocks in reverse document order to preserve index validity.

Usage:
    cd ~/skills/gdrive && uv run python3 scripts/color_markers.py <doc_id> <tab_id>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from services import get_docs_service

OPEN_MARKER = "«RED»"
CLOSE_MARKER = "«/RED»"
RED_RGB = {"red": 0.918, "green": 0.263, "blue": 0.208}


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


def find_blocks(flat, index_map):
    """Return list of marker block bounds in document index space."""
    blocks = []
    pos = 0
    while True:
        o = flat.find(OPEN_MARKER, pos)
        if o == -1:
            break
        c = flat.find(CLOSE_MARKER, o + len(OPEN_MARKER))
        if c == -1:
            print(f"Warning: unclosed {OPEN_MARKER} at flat position {o}", file=sys.stderr)
            break
        blocks.append({
            "open_start":    index_map[o],
            "open_end":      index_map[o + len(OPEN_MARKER) - 1] + 1,
            "content_start": index_map[o + len(OPEN_MARKER)],
            "content_end":   index_map[c],
            "close_start":   index_map[c],
            "close_end":     index_map[c + len(CLOSE_MARKER) - 1] + 1,
        })
        pos = c + len(CLOSE_MARKER)
    return blocks


def build_requests(blocks, tab_id):
    """
    Build batch-update requests for all blocks.
    Process in reverse order so higher-index deletions don't shift lower-index positions.
    Within each block: delete close marker → color content → delete open marker.
    """
    requests = []
    for b in reversed(blocks):
        requests += [
            {"deleteContentRange": {
                "range": {"startIndex": b["close_start"], "endIndex": b["close_end"], "tabId": tab_id}
            }},
            {"updateTextStyle": {
                "range": {"startIndex": b["content_start"], "endIndex": b["content_end"], "tabId": tab_id},
                "textStyle": {"foregroundColor": {"color": {"rgbColor": RED_RGB}}},
                "fields": "foregroundColor",
            }},
            {"deleteContentRange": {
                "range": {"startIndex": b["open_start"], "endIndex": b["open_end"], "tabId": tab_id}
            }},
        ]
    return requests


def main():
    if len(sys.argv) != 3:
        print("Usage: color_markers.py <doc_id> <tab_id>", file=sys.stderr)
        sys.exit(1)

    doc_id, tab_id = sys.argv[1], sys.argv[2]
    svc = get_docs_service()

    doc = svc.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    content = get_tab_content(doc.get("tabs", []), tab_id)
    if content is None:
        print(f"Error: tab '{tab_id}' not found in document.", file=sys.stderr)
        sys.exit(1)

    flat, index_map = flatten_text(content)
    blocks = find_blocks(flat, index_map)
    print(f"Found {len(blocks)} «RED» block(s).")

    if not blocks:
        return

    requests = build_requests(blocks, tab_id)
    svc.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests}
    ).execute()
    print(f"Done. Colored and cleaned {len(blocks)} block(s).")


if __name__ == "__main__":
    main()
