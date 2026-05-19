#!/usr/bin/env python3
"""Format the Block Performance Digest: font, spacing, bullets, bold, highlights.

Generates Google Docs API batch-update JSON to apply all formatting fixes
after commentary has been inserted. Replaces LLM-based formatting with
pure Python -- runs in seconds instead of minutes.

Usage:
    python3 format_doc.py DOC_JSON TAB_ID

Output:
    Prints {"requests": [...]} JSON to stdout, ready for:
        gdrive docs batch-update DOC_ID --tab TAB_ID < requests.json
"""

from __future__ import annotations

import json
import sys
import re
import argparse
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Element = dict[str, Any]
Request = dict[str, Any]

# ---------------------------------------------------------------------------
# Sub-item classification labels
# ---------------------------------------------------------------------------

# Summary section -- level 1
SUMMARY_L1_LABELS = [
    "Square GPV",
    "Lending vs. Non-Lending",
    "Inflows Framework:",
    "Inflows (vs. AP)",
    "Inflows (vs. Q2OL)",
    "Inflows (vs. Q3OL)",
    "Inflows (vs. Q4OL)",
    "Monetization rate (vs. AP)",
    "Monetization rate (vs. Q2OL)",
    "Monetization rate (vs. Q3OL)",
    "Monetization rate (vs. Q4OL)",
]

# Summary section -- level 2
SUMMARY_L2_LABELS = [
    "US GPV",
    "International GPV",
    "Lending (vs. AP):",
    "Non-Lending (vs. AP):",
    "Lending (vs. Q2OL):",
    "Non-Lending (vs. Q2OL):",
    "Lending (vs. Q3OL):",
    "Non-Lending (vs. Q3OL):",
    "Lending (vs. Q4OL):",
    "Non-Lending (vs. Q4OL):",
    "Actives",
    "Inflows per active",
]

# Overview: Gross Profit Performance -- level 1
GP_L1_LABELS = [
    "Cash App gross profit",
    "Square gross profit",
    "Proto gross profit",
    "TIDAL gross profit",
]

# Overview: Square GPV -- level 1
SQUARE_GPV_L1_LABELS = [
    "US GPV",
    "International GPV",
    "GPV to GP Spread",
]

# Bold labels for overview sections
BOLD_LABELS = [
    "Block gross profit",
    "Cash App gross profit",
    "Square gross profit",
    "Proto gross profit",
    "TIDAL gross profit",
    "Adjusted Operating Income",
    "Actives",
    "Inflows per active",
    "Monetization rate",
    "Inflows",
    "Global GPV",
    "US GPV",
    "International GPV",
    "GPV to GP Spread",
]

# Generate Rule of 40..55
BOLD_LABELS += [f"Rule of {n}" for n in range(40, 56)]

# Placeholder patterns that should be yellow-highlighted
PLACEHOLDER_PATTERNS = ["[MANUAL", "[DATA MISSING", "[Cash App WoW"]


# ---------------------------------------------------------------------------
# Doc structure helpers
# ---------------------------------------------------------------------------

def get_body_content(doc: dict) -> list[Element]:
    """Extract body content elements from the doc JSON."""
    try:
        return doc["tabs"][0]["documentTab"]["body"]["content"]
    except (KeyError, IndexError) as e:
        print(f"ERROR: Cannot parse doc structure: {e}", file=sys.stderr)
        print("Expected doc['tabs'][0]['documentTab']['body']['content']", file=sys.stderr)
        sys.exit(1)


def para_style_type(para: dict) -> str:
    """Return the namedStyleType of a paragraph, defaulting to NORMAL_TEXT."""
    return para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")


def para_text(para: dict) -> str:
    """Concatenate all text runs in a paragraph."""
    return "".join(
        el.get("textRun", {}).get("content", "")
        for el in para.get("elements", [])
    )


def is_bulleted(para: dict) -> bool:
    """Check if a paragraph has bullet formatting."""
    return "bullet" in para


def collect_table_paragraphs(element: Element) -> list[dict]:
    """Collect all paragraphs inside a table element."""
    paras = []
    table = element.get("table", {})
    for row in table.get("tableRows", []):
        for cell in row.get("tableCells", []):
            for content_el in cell.get("content", []):
                if "paragraph" in content_el:
                    paras.append(content_el)
    return paras


# ---------------------------------------------------------------------------
# Task 1: Font size 10pt + line spacing 1.15 for non-table NORMAL_TEXT
# ---------------------------------------------------------------------------

def build_font_spacing_requests(
    body_content: list[Element], tab_id: str
) -> list[Request]:
    """Build updateTextStyle and updateParagraphStyle requests for NORMAL_TEXT paragraphs."""
    requests: list[Request] = []

    for element in body_content:
        # Skip table elements entirely -- only process top-level paragraphs
        if "table" in element:
            continue

        if "paragraph" not in element:
            continue

        para = element["paragraph"]
        style_type = para_style_type(para)

        if style_type != "NORMAL_TEXT":
            continue

        start = element["startIndex"]
        end = element["endIndex"]

        # Font size 10pt
        requests.append({
            "updateTextStyle": {
                "textStyle": {
                    "fontSize": {"magnitude": 10, "unit": "PT"}
                },
                "fields": "fontSize",
                "range": {
                    "startIndex": start,
                    "endIndex": end,
                    "tabId": tab_id,
                },
            }
        })

        # Line spacing 1.15 (115%), zero space above/below
        requests.append({
            "updateParagraphStyle": {
                "paragraphStyle": {
                    "lineSpacing": 115,
                    "spaceAbove": {"magnitude": 0, "unit": "PT"},
                    "spaceBelow": {"magnitude": 0, "unit": "PT"},
                },
                "fields": "lineSpacing,spaceAbove,spaceBelow",
                "range": {
                    "startIndex": start,
                    "endIndex": end,
                    "tabId": tab_id,
                },
            }
        })

    return requests


# ---------------------------------------------------------------------------
# Task 2: Bullet nesting
# ---------------------------------------------------------------------------

def identify_section(heading_text: str) -> str | None:
    """Classify a heading into a section name for bullet-nesting logic."""
    t = heading_text.strip().lower()
    if t == "summary":
        return "summary"
    if "gross profit performance" in t:
        return "gp_performance"
    if "adjusted operating income" in t:
        return "aoi"
    if "square gpv" in t:
        return "square_gpv"
    return None


def _strip_leading_emoji(text: str) -> str:
    """Remove a leading status emoji + whitespace, returning the rest."""
    t = text.lstrip()
    for emoji in ("\U0001F7E2", "\U0001F7E1", "\U0001F534"):  # 🟢 🟡 🔴
        if t.startswith(emoji):
            return t[len(emoji):].lstrip()
    return t


def _has_benchmark_suffix(text: str) -> bool:
    """True if text contains a "(vs. <Benchmark>)" pattern (AP, Q1OL..Q4OL)."""
    for bench in ("(vs. AP)", "(vs. Q1OL)", "(vs. Q2OL)", "(vs. Q3OL)", "(vs. Q4OL)"):
        if bench in text:
            return True
    return False


def classify_bullet_level(text: str, section: str, saw_inflows_per_active: bool) -> int:
    """Return the nesting level (0, 1, or 2) for a bulleted paragraph.

    Matches labels against the start of the paragraph (after the optional status
    emoji) so a paragraph that *mentions* another bullet's label downstream does
    not accidentally inherit that level.
    """
    stripped = text.strip()
    body = _strip_leading_emoji(stripped)

    if section == "summary":
        # Level 2 checks first (more specific)
        for label in SUMMARY_L2_LABELS:
            if body.startswith(label):
                return 2

        # Special case: "Monetization rate" without a "(vs. <Benchmark>)"
        # suffix is level 2 when it follows "Inflows per active"
        if body.startswith("Monetization rate") and not _has_benchmark_suffix(body) and saw_inflows_per_active:
            return 2

        # Level 1
        for label in SUMMARY_L1_LABELS:
            if body.startswith(label):
                return 1

        return 0

    elif section == "gp_performance":
        for label in GP_L1_LABELS:
            if body.startswith(label):
                return 1
        return 0

    elif section == "aoi":
        if body.startswith("We expect to achieve") or body.startswith("For the quarter, the business"):
            return 1
        return 0

    elif section == "square_gpv":
        for label in SQUARE_GPV_L1_LABELS:
            if body.startswith(label):
                return 1
        return 0

    return 0


def find_next_table_start(body_content: list[Element], after_index: int) -> int | None:
    """Find the startIndex of the next table element after a given index."""
    for element in body_content:
        if "table" in element and element.get("startIndex", 0) >= after_index:
            return element["startIndex"]
    return None


def should_be_bulleted(text: str, section: str) -> bool:
    """Determine if a paragraph should be bulleted based on content and section.

    This does NOT rely on the paragraph's current bullet state — it decides
    purely from the text, so paragraphs that insert-markdown missed still
    get bulleted.
    """
    stripped = text.strip()
    if not stripped:
        return False

    if section == "summary":
        # Topline and Profitability are standalone paragraphs, not bullets
        if "Topline:" in stripped:
            return False
        if "Profitability:" in stripped:
            return False
        # Separator line
        if stripped.startswith("\u2500") or stripped == "---":
            return False
        # Everything else in the Summary bullet block should be bulleted
        return True

    elif section == "gp_performance":
        # Skip intro and link paragraphs
        if "For additional details" in stripped:
            return False
        if "Weekly Performance Digest" in stripped or "Weekly Execution Update" in stripped:
            return False
        # Metric content — bullet it
        if "gross profit" in stripped.lower() or stripped.startswith("Q1'"):
            return True
        return False

    elif section == "aoi":
        if "Adjusted Operating Income" in stripped:
            return True
        if "Rule of" in stripped:
            return True
        if stripped.startswith("We expect") or stripped.startswith("For the quarter"):
            return True
        return False

    elif section == "square_gpv":
        if "GPV" in stripped or "Spread" in stripped:
            return True
        if stripped.startswith("For the quarter"):
            return True
        return False

    return False


def build_bullet_requests(
    body_content: list[Element], tab_id: str
) -> list[Request]:
    """Build bullet nesting requests: delete, insertText (tabs), createParagraphBullets.

    Uses should_be_bulleted() to identify paragraphs that need bullets,
    regardless of their current bullet state. This handles cases where
    insert-markdown didn't create bullets for some paragraphs.
    """
    requests_delete: list[Request] = []
    requests_strip: list[Request] = []   # remove old leading tabs
    requests_create: list[Request] = []

    # Gather all top-level paragraphs with their section context
    current_section: str | None = None
    paragraphs_with_context: list[tuple[Element, str | None]] = []

    for element in body_content:
        if "table" in element:
            continue
        if "paragraph" not in element:
            continue

        para = element["paragraph"]
        style = para_style_type(para)
        text = para_text(para).strip()

        # Track headings to know which section we're in
        if style in ("HEADING_1", "HEADING_2", "HEADING_3"):
            sec = identify_section(text)
            if sec is not None:
                current_section = sec
            elif text == "---" or text.startswith("Overview:"):
                new_sec = identify_section(text)
                if new_sec:
                    current_section = new_sec
            continue

        # Separator "---" ends the summary section
        if text == "---" and current_section == "summary":
            current_section = None
            continue

        paragraphs_with_context.append((element, current_section))

    # Group contiguous should-be-bulleted paragraphs into runs.
    # A run breaks on: (a) a paragraph that should NOT be bulleted, or
    # (b) a gap in startIndex (heading, table, or separator in between).
    bullet_runs: list[list[tuple[Element, str | None]]] = []
    current_run: list[tuple[Element, str | None]] = []
    prev_end: int | None = None

    for elem, section in paragraphs_with_context:
        text = para_text(elem["paragraph"]).strip()
        elem_start = elem["startIndex"]

        # Detect index gap (heading/table/separator filtered out)
        gap = prev_end is not None and elem_start > prev_end

        want_bullet = section is not None and should_be_bulleted(text, section)

        if want_bullet and not gap:
            current_run.append((elem, section))
        elif want_bullet and gap:
            if current_run:
                bullet_runs.append(current_run)
            current_run = [(elem, section)]
        else:
            if current_run:
                bullet_runs.append(current_run)
                current_run = []

        prev_end = elem["endIndex"]

    if current_run:
        bullet_runs.append(current_run)

    if not bullet_runs:
        return []

    # Indent-based approach: create all bullets at L0, then set visual indent
    # via updateParagraphStyle. This avoids nesting-level inheritance from
    # insert-markdown's list structure, which persists through delete+create.
    #
    # Indent values (from the published 3/31 tab):
    INDENT = {
        0: {"indentStart": {"magnitude": 36, "unit": "PT"}, "indentFirstLine": {"magnitude": 18, "unit": "PT"}},
        1: {"indentStart": {"magnitude": 72, "unit": "PT"}, "indentFirstLine": {"magnitude": 54, "unit": "PT"}},
        2: {"indentStart": {"magnitude": 108, "unit": "PT"}, "indentFirstLine": {"magnitude": 90, "unit": "PT"}},
    }

    requests_indent: list[Request] = []

    for run_paras in bullet_runs:
        if not run_paras:
            continue

        run_start = run_paras[0][0]["startIndex"]
        run_end = run_paras[-1][0]["endIndex"]

        saw_inflows_per_active = False

        for elem, section in run_paras:
            para = elem["paragraph"]
            text = para_text(para)
            para_start = elem["startIndex"]
            para_end = elem["endIndex"]

            # 1. Delete existing bullet (per-paragraph to break old list)
            if is_bulleted(para):
                requests_delete.append({
                    "deleteParagraphBullets": {
                        "range": {
                            "startIndex": para_start,
                            "endIndex": para_end,
                            "tabId": tab_id,
                        }
                    }
                })

            # 2. Strip existing leading tabs
            raw = para_text(para)
            old_tabs = 0
            for ch in raw:
                if ch == "\t":
                    old_tabs += 1
                else:
                    break
            if old_tabs > 0:
                requests_strip.append({
                    "_sort_key": para_start,
                    "deleteContentRange": {
                        "range": {
                            "startIndex": para_start,
                            "endIndex": para_start + old_tabs,
                            "tabId": tab_id,
                        }
                    }
                })

            # 3. Determine desired visual nesting level
            if "Inflows per active" in text:
                saw_inflows_per_active = True

            level = classify_bullet_level(text, section or "", saw_inflows_per_active)
            level = min(level, 2)  # cap at 2

            # 4. Queue indent update for this paragraph
            indent_props = INDENT[level]
            requests_indent.append({
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": para_start,
                        "endIndex": para_end,
                        "tabId": tab_id,
                    },
                    "paragraphStyle": indent_props,
                    "fields": "indentStart,indentFirstLine",
                }
            })

        # 5. Range-based createParagraphBullets (all at L0 — indent handles visual nesting)
        next_table = find_next_table_start(body_content, run_end)
        create_end = min(run_end, next_table) if next_table is not None else run_end
        requests_create.append({
            "createParagraphBullets": {
                "range": {
                    "startIndex": run_start,
                    "endIndex": create_end,
                    "tabId": tab_id,
                },
                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
            }
        })

    # Sort strip requests in REVERSE startIndex order
    requests_strip.sort(key=lambda r: r["_sort_key"], reverse=True)
    for r in requests_strip:
        del r["_sort_key"]

    # Combine: delete → strip (reverse) → create → indent
    # (indent runs AFTER create so the bullets exist when we set their indentation)
    return requests_delete + requests_strip + requests_create + requests_indent


# ---------------------------------------------------------------------------
# Task 3: Bold metric labels in overview sections
# ---------------------------------------------------------------------------

def find_first_overview_index(body_content: list[Element]) -> int | None:
    """Find the startIndex of the first 'Overview:' heading."""
    for element in body_content:
        if "paragraph" not in element:
            continue
        para = element["paragraph"]
        style = para_style_type(para)
        if style in ("HEADING_1", "HEADING_2", "HEADING_3"):
            text = para_text(para).strip()
            if text.startswith("Overview:"):
                return element["startIndex"]
    return None


def build_bold_requests(
    body_content: list[Element], tab_id: str
) -> list[Request]:
    """Build updateTextStyle requests to bold metric labels in overview sections."""
    requests: list[Request] = []

    # Find where overview sections begin
    overview_start = find_first_overview_index(body_content)
    if overview_start is None:
        return []

    for element in body_content:
        if "table" in element:
            continue
        if "paragraph" not in element:
            continue

        # Only process paragraphs after the first overview heading
        if element.get("startIndex", 0) < overview_start:
            continue

        para = element["paragraph"]
        style = para_style_type(para)

        # Skip headings -- they have their own styling
        if style != "NORMAL_TEXT":
            continue

        # Get full paragraph text and its absolute start position
        full_text = para_text(para)
        if not full_text.strip():
            continue

        # Calculate the paragraph's text start from its first element
        para_elements = para.get("elements", [])
        if not para_elements:
            continue
        first_el = para_elements[0]
        para_abs_start = first_el.get(
            "startIndex",
            first_el.get("textRun", {}).get("startIndex", element["startIndex"]),
        )

        # Search for each bold label in the paragraph text
        for label in BOLD_LABELS:
            # Find all occurrences of the label
            search_start = 0
            while True:
                idx = full_text.find(label, search_start)
                if idx == -1:
                    break

                abs_start = para_abs_start + idx
                abs_end = abs_start + len(label)

                requests.append({
                    "updateTextStyle": {
                        "textStyle": {"bold": True},
                        "fields": "bold",
                        "range": {
                            "startIndex": abs_start,
                            "endIndex": abs_end,
                            "tabId": tab_id,
                        },
                    }
                })

                search_start = idx + len(label)

    return requests


# ---------------------------------------------------------------------------
# Task 4: Yellow highlight on placeholders
# ---------------------------------------------------------------------------

def build_highlight_requests(
    body_content: list[Element], tab_id: str
) -> list[Request]:
    """Build updateTextStyle requests to yellow-highlight placeholder text."""
    requests: list[Request] = []

    for element in body_content:
        if "table" in element:
            continue
        if "paragraph" not in element:
            continue

        para = element["paragraph"]
        para_elements = para.get("elements", [])

        for text_el in para_elements:
            text_run = text_el.get("textRun")
            if not text_run:
                continue

            content = text_run.get("content", "")
            # startIndex may be on the element wrapper or inside textRun
            el_start = text_el.get("startIndex", text_run.get("startIndex", 0))

            # Check each placeholder pattern
            for pattern in PLACEHOLDER_PATTERNS:
                search_start = 0
                while True:
                    idx = content.find(pattern, search_start)
                    if idx == -1:
                        break

                    # Find the opening bracket
                    bracket_start = content.rfind("[", 0, idx + 1)
                    if bracket_start == -1:
                        bracket_start = idx

                    # Find the closing bracket
                    bracket_end = content.find("]", idx)
                    if bracket_end == -1:
                        # No closing bracket -- highlight to end of text run
                        bracket_end = len(content) - 1  # skip trailing \n
                    else:
                        bracket_end += 1  # include the ]

                    abs_start = el_start + bracket_start
                    abs_end = el_start + bracket_end

                    if abs_end > abs_start:
                        requests.append({
                            "updateTextStyle": {
                                "textStyle": {
                                    "backgroundColor": {
                                        "color": {
                                            "rgbColor": {
                                                "red": 1.0,
                                                "green": 0.95,
                                                "blue": 0.0,
                                            }
                                        }
                                    }
                                },
                                "fields": "backgroundColor",
                                "range": {
                                    "startIndex": abs_start,
                                    "endIndex": abs_end,
                                    "tabId": tab_id,
                                },
                            }
                        })

                    search_start = bracket_end if bracket_end > idx else idx + 1

    return requests


# ---------------------------------------------------------------------------
# Task 5: Summary spacing (blank paragraph between last bullet and Profitability)
# ---------------------------------------------------------------------------

def build_summary_spacing_requests(
    body_content: list[Element], tab_id: str
) -> list[Request]:
    """Ensure a blank paragraph separates the last Summary bullet from Profitability."""
    requests: list[Request] = []

    in_summary = False
    last_bullet_end: int | None = None
    profitability_start: int | None = None
    has_gap = False

    for elem in body_content:
        if "paragraph" not in elem:
            continue
        para = elem["paragraph"]
        style = para_style_type(para)
        text = para_text(para).strip()

        if "HEADING" in style:
            if "Summary" in text:
                in_summary = True
            elif in_summary:
                break  # left the Summary section
            continue

        if not in_summary:
            continue

        if "bullet" in para:
            last_bullet_end = elem["endIndex"]
            has_gap = False  # reset — any gap must come after the LAST bullet

        elif last_bullet_end is not None and not text:
            has_gap = True  # blank paragraph after a bullet

        elif last_bullet_end is not None and "Profitability:" in text:
            profitability_start = elem["startIndex"]
            break

    if last_bullet_end and profitability_start and not has_gap:
        # Insert a newline at the end of the last bullet to create a blank paragraph.
        # The newline goes right before the Profitability paragraph.
        requests.append({
            "insertText": {
                "text": "\n",
                "location": {
                    "index": profitability_start,
                    "tabId": tab_id,
                },
            }
        })
        print(f"  Inserted blank paragraph before Profitability at index {profitability_start}", file=sys.stderr)

    return requests


# ---------------------------------------------------------------------------
# Task 6: Post-bullet table safety check
# ---------------------------------------------------------------------------

def build_table_bullet_cleanup_requests(
    body_content: list[Element], tab_id: str
) -> list[Request]:
    """Generate deleteParagraphBullets for any table cell paragraphs that have bullets."""
    requests: list[Request] = []

    for element in body_content:
        if "table" not in element:
            continue

        table_paras = collect_table_paragraphs(element)
        for cell_el in table_paras:
            para = cell_el.get("paragraph", {})
            if is_bulleted(para):
                start = cell_el.get("startIndex", 0)
                end = cell_el.get("endIndex", start)
                if end > start:
                    requests.append({
                        "deleteParagraphBullets": {
                            "range": {
                                "startIndex": start,
                                "endIndex": end,
                                "tabId": tab_id,
                            }
                        }
                    })

    return requests


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def print_summary(
    font_spacing: list,
    bullets: list,
    bold: list,
    highlights: list,
    table_cleanup: list,
    file=sys.stderr,
) -> None:
    """Print a human-readable summary of request counts."""
    def count_type(reqs, key):
        return sum(1 for r in reqs if key in r)

    print("--- format_doc.py summary ---", file=file)
    print(f"  Font size (updateTextStyle):     {count_type(font_spacing, 'updateTextStyle')}", file=file)
    print(f"  Line spacing (updateParagraphStyle): {count_type(font_spacing, 'updateParagraphStyle')}", file=file)
    print(f"  Delete bullets:                  {count_type(bullets, 'deleteParagraphBullets')}", file=file)
    print(f"  Insert tabs (nesting):           {count_type(bullets, 'insertText')}", file=file)
    print(f"  Create bullets:                  {count_type(bullets, 'createParagraphBullets')}", file=file)
    print(f"  Bold labels:                     {len(bold)}", file=file)
    print(f"  Placeholder highlights:          {len(highlights)}", file=file)
    print(f"  Table bullet cleanup:            {len(table_cleanup)}", file=file)
    total = len(font_spacing) + len(bullets) + len(bold) + len(highlights) + len(table_cleanup)
    print(f"  TOTAL requests:                  {total}", file=file)
    print("-----------------------------", file=file)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Google Docs API batch-update JSON to format the Block Performance Digest."
    )
    parser.add_argument("doc_json", help="Path to Doc structure JSON (from gdrive docs get)")
    parser.add_argument("tab_id", help="Tab ID (e.g., t.c1h7yqcqcq60)")
    parser.add_argument("--phase", choices=["1", "2"], default=None,
                        help="Phase 1: cleanup (delete bullets + strip tabs). "
                             "Phase 2: build (insert tabs + create bullets + all formatting). "
                             "Omit for both phases in one batch (works on fresh docs).")
    args = parser.parse_args()

    try:
        with open(args.doc_json, "r") as f:
            doc = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {args.doc_json}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {args.doc_json}: {e}", file=sys.stderr)
        sys.exit(1)

    tab_id = args.tab_id
    body_content = get_body_content(doc)

    print(f"Loaded doc with {len(body_content)} top-level elements", file=sys.stderr)

    if args.phase == "1":
        # Phase 1: cleanup only — delete bullets + strip tabs
        bullets = build_bullet_requests(body_content, tab_id)
        # Extract only delete and strip requests
        cleanup = [r for r in bullets if "deleteParagraphBullets" in r or "deleteContentRange" in r]
        table_cleanup = build_table_bullet_cleanup_requests(body_content, tab_id)
        all_requests = cleanup + table_cleanup
        print(f"Phase 1 (cleanup): {len(cleanup)} delete/strip + {len(table_cleanup)} table cleanup", file=sys.stderr)

    elif args.phase == "2":
        # Phase 2: build — insert tabs + create bullets + font/spacing/bold/highlights
        font_spacing = build_font_spacing_requests(body_content, tab_id)
        bullets = build_bullet_requests(body_content, tab_id)
        # Extract only insert and create requests
        build = [r for r in bullets if "insertText" in r or "createParagraphBullets" in r]
        bold = build_bold_requests(body_content, tab_id)
        highlights = build_highlight_requests(body_content, tab_id)
        table_cleanup = build_table_bullet_cleanup_requests(body_content, tab_id)
        all_requests = font_spacing + build + bold + highlights + table_cleanup
        print(f"Phase 2 (build): {len(font_spacing)} font/spacing + {len(build)} bullet build + {len(bold)} bold + {len(highlights)} highlights", file=sys.stderr)

    else:
        # Both phases in one batch (works on fresh docs without prior bullet state)
        font_spacing = build_font_spacing_requests(body_content, tab_id)
        bullets = build_bullet_requests(body_content, tab_id)
        bold = build_bold_requests(body_content, tab_id)
        highlights = build_highlight_requests(body_content, tab_id)
        table_cleanup = build_table_bullet_cleanup_requests(body_content, tab_id)
        spacing = build_summary_spacing_requests(body_content, tab_id)
        print_summary(font_spacing, bullets, bold, highlights, table_cleanup)
        all_requests = font_spacing + bullets + bold + highlights + table_cleanup + spacing

    if not all_requests:
        print("WARNING: No formatting requests generated.", file=sys.stderr)

    json.dump({"requests": all_requests}, sys.stdout, indent=2)
    print(file=sys.stdout)


if __name__ == "__main__":
    main()
