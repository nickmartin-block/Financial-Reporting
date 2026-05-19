#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
from __future__ import annotations
"""validate_block_pl.py

Cell-by-cell validation of the Block P&L Overview population on the
Test tab. Two layers:

  Layer 1 (publish-pipeline check)
    Test tab cell text ↔ JSON packet `formatted` string.
    Catches populator bugs (wrong cell targeted, missing rows, etc.).

  Layer 2 (source-mapping check)
    Test tab cell text ↔ MRP tab reference cell text (parsed numeric +
    tolerance). Catches source-mapping errors that Layer 1 misses
    (Test tab and packet agree, but both are wrong vs. the manual MRP).

Known WARN-not-FAIL cases (no source available, or expected divergence):
  - People row (R29): always GAP
  - Bitcoin Lightning / Bitkey (R07/R08): segment label TBD
  - Adj EBITDA / margin (R27/R28): TBD source
  - QTD Pace columns: ~$20M contingency divergence from manual MRP

Tolerance defaults:
  - $ amounts:   $1.0M
  - %/rate:      1.0 pt
  - pts deltas:  0.5 pts

Usage:
    python3 validate_block_pl.py \\
        --doc /tmp/mrp_doc.json \\
        --packet /tmp/mrp_out_2026_04.json \\
        --test-tab t.3mz1duijrdf1 \\
        --mrp-tab t.ea3bz9hprpol \\
        --out ~/Desktop/Nick's\\ Cursor/Monthly\\ Reporting\\ Pack/mrp_validation_2026_04.md

Exit codes:
    0  all checks PASS or WARN
    1  one or more FAIL
"""

import argparse
import json
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Tolerance + known-warn config
# ---------------------------------------------------------------------------

DEFAULT_DOLLAR_TOL_M = 1.0   # $M
DEFAULT_PCT_TOL = 0.01       # 1 percentage point = 0.01 decimal
DEFAULT_PTS_TOL = 0.5        # pts (margin / R40 deltas)

# Rows always treated as WARN regardless of result:
WARN_ROW_LABELS = {
    "People": "Headcount not in BDM (confirmed gap)",
    "Bitcoin Lightning": "BDM segment label TBD (Phase 2 verification)",
    "Bitkey": "BDM segment label TBD (Phase 2 verification)",
    "Adjusted EBITDA": "Adj EBITDA source TBD (Phase 2 verification)",
}

# QTD cells (packet cell indices 3, 4, 5) are expected to diverge from manual MRP
# due to Nick's judgment contingency on May/June pacing. Layer 2 diffs on these
# columns are WARN, not FAIL.
QTD_CELL_INDICES = {3, 4, 5}
QTD_LAYER2_WARN_REASON = "QTD Pace contingency divergence (~$20M, documented)"


# ---------------------------------------------------------------------------
# Doc loaders + cell helpers (mirrors populate_block_pl.py)
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
    """30x7 table whose R02 col 0 starts with 'Gross profit'."""
    for elem in content:
        if "table" not in elem:
            continue
        tbl = elem["table"]
        if tbl.get("rows", 0) != 30 or tbl.get("columns", 0) != 7:
            continue
        try:
            label = _cell_text(tbl["tableRows"][2]["tableCells"][0]).strip()
        except (IndexError, KeyError):
            continue
        if label.startswith("Gross profit"):
            return tbl
    return None


def _cell_text(cell: dict) -> str:
    parts: list[str] = []
    for c in cell.get("content", []):
        for el in c.get("paragraph", {}).get("elements", []):
            if "textRun" in el:
                parts.append(el["textRun"].get("content", ""))
    return "".join(parts).replace("\n", "").strip()


# ---------------------------------------------------------------------------
# Numeric parsing (shared with the populator)
# ---------------------------------------------------------------------------

def parse_to_raw(s: str) -> tuple[float | None, str | None]:
    """Parse a formatted cell string into (raw_value, unit_kind).
    Returns (None, None) if non-numeric.

    unit_kind in {'dollar', 'pct', 'pts', None}:
      - dollar: returns value in raw $ (so $1.02B -> 1020000000, $21M -> 21000000)
      - pct:    returns decimal (23% -> 0.23, (5%) -> -0.05)
      - pts:    returns pts as decimal (5.8 pts -> 0.058, -2 pts -> -0.02)
    """
    s = s.strip().replace("\n", "")
    if not s:
        return None, None
    if s in ("[GAP]", "nm", "--", "N/A", "n/a"):
        return None, None

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

    # detect unit suffix
    unit_kind = None
    multiplier = 1.0
    if inner.lower().endswith(" pts") or inner.lower().endswith("pts"):
        unit_kind = "pts"
        idx = inner.lower().rfind("pts")
        inner = inner[:idx].strip()
        multiplier = 0.01  # pts -> decimal
    elif inner.endswith("%"):
        unit_kind = "pct"
        inner = inner[:-1].strip()
        multiplier = 0.01  # % -> decimal
    elif inner.endswith("B"):
        unit_kind = "dollar"
        inner = inner[:-1].strip()
        multiplier = 1_000_000_000
    elif inner.endswith("M"):
        unit_kind = "dollar"
        inner = inner[:-1].strip()
        multiplier = 1_000_000
    elif inner.endswith("K"):
        unit_kind = "dollar"
        inner = inner[:-1].strip()
        multiplier = 1_000

    if inner.startswith("$"):
        if unit_kind is None:
            unit_kind = "dollar"
        inner = inner[1:].strip()

    try:
        magnitude = float(inner.replace(",", ""))
    except ValueError:
        return None, None

    value = magnitude * multiplier
    if sign_form in ("parens", "minus"):
        value = -value
    return value, unit_kind


# ---------------------------------------------------------------------------
# Validation core
# ---------------------------------------------------------------------------

@dataclass
class Check:
    row_idx: int
    row_label: str
    col: int                   # 1-indexed doc col (1 = Actual, etc.)
    cell_kind: str             # actual / yoy_pct / vs_ol_dollar / pts
    layer: str                 # 'L1' | 'L2'
    test_text: str
    expected_text: str
    status: str                # 'PASS' | 'FAIL' | 'WARN'
    delta: float | None = None
    note: str | None = None


def within_tolerance(a: float | None, b: float | None, kind: str) -> tuple[bool, float | None]:
    """Compare two values with kind-appropriate tolerance.
    Returns (within, delta_signed) where delta = a - b."""
    if a is None or b is None:
        return (a is None and b is None), None
    delta = a - b
    if kind == "dollar":
        tol = DEFAULT_DOLLAR_TOL_M * 1_000_000
    elif kind == "pct":
        tol = DEFAULT_PCT_TOL
    elif kind == "pts":
        tol = DEFAULT_PTS_TOL * 0.01  # pts threshold in decimal
    else:
        tol = 0.0
    return abs(delta) <= tol, delta


def kind_to_unit(kind: str) -> str:
    """Map packet cell kind -> parse_to_raw unit_kind."""
    if kind == "vs_ol_dollar":
        return "dollar"
    if kind == "yoy_pct":
        return "pct"
    if kind == "pts":
        return "pts"
    # 'actual' could be $ or rate — caller infers from parsed unit
    return "auto"


def validate(packet: dict, test_table: dict, mrp_table: dict | None,
             test_tab: str, mrp_tab: str) -> list[Check]:
    checks: list[Check] = []
    test_rows = test_table.get("tableRows", [])
    mrp_rows = mrp_table.get("tableRows", []) if mrp_table else None

    for row_spec in packet["block_pl_overview"]["rows"]:
        row_idx = row_spec["row_idx"]
        label = row_spec["label"]
        if row_idx >= len(test_rows):
            checks.append(Check(row_idx, label, 0, "structure", "L1",
                                "(missing)", "(row expected)", "FAIL",
                                note="Test tab missing row"))
            continue
        test_cells = test_rows[row_idx].get("tableCells", [])
        mrp_cells = mrp_rows[row_idx].get("tableCells", []) if mrp_rows and row_idx < len(mrp_rows) else None

        is_gap = row_spec.get("is_gap", False)
        is_header = row_spec.get("is_section_header", False)
        if is_header:
            continue
        force_warn_reason = WARN_ROW_LABELS.get(label)

        for packet_col, cell_data in enumerate(row_spec["cells"]):
            doc_col = packet_col + 1  # cells[0] = doc col 1
            if doc_col >= len(test_cells):
                checks.append(Check(row_idx, label, doc_col, cell_data.get("kind", "actual"),
                                    "L1", "(missing col)", "(expected)", "FAIL"))
                continue
            test_text = _cell_text(test_cells[doc_col])
            expected_text = cell_data.get("formatted", "")
            kind = cell_data.get("kind", "actual")

            # ---- Layer 1: Test tab vs packet ----
            l1_status, l1_delta, l1_note = compare_text_to_expected(
                test_text, expected_text, kind, cell_data.get("raw")
            )
            if force_warn_reason and l1_status == "FAIL":
                l1_status = "WARN"
                l1_note = (l1_note or "") + " | " + force_warn_reason
            if is_gap and expected_text == "[GAP]":
                # Gap rows: Layer 1 passes if test text is also [GAP] or empty
                l1_status = "PASS" if test_text in ("[GAP]", "") else l1_status
            checks.append(Check(row_idx, label, doc_col, kind, "L1",
                                test_text, expected_text, l1_status,
                                delta=l1_delta, note=l1_note))

            # ---- Layer 2: Test tab vs MRP tab ----
            if mrp_cells and doc_col < len(mrp_cells):
                mrp_text = _cell_text(mrp_cells[doc_col])
                l2_status, l2_delta, l2_note = compare_text_to_text(test_text, mrp_text, kind)
                # QTD col divergence -> WARN
                if packet_col in QTD_CELL_INDICES and l2_status == "FAIL":
                    l2_status = "WARN"
                    l2_note = (l2_note or "") + " | " + QTD_LAYER2_WARN_REASON
                if force_warn_reason and l2_status == "FAIL":
                    l2_status = "WARN"
                    l2_note = (l2_note or "") + " | " + force_warn_reason
                if is_gap and mrp_text:
                    # Test shows [GAP] but MRP has a manual value -> WARN
                    l2_status = "WARN"
                    l2_note = "Manual MRP has value; automation reports GAP"
                checks.append(Check(row_idx, label, doc_col, kind, "L2",
                                    test_text, mrp_text, l2_status,
                                    delta=l2_delta, note=l2_note))

    return checks


def compare_text_to_expected(test_text: str, expected_text: str,
                              kind: str, expected_raw) -> tuple[str, float | None, str | None]:
    """Layer 1 compare. Allow exact string match OR numeric within tolerance."""
    if test_text.strip() == expected_text.strip():
        return "PASS", None, None
    test_val, test_unit = parse_to_raw(test_text)
    exp_val, exp_unit = parse_to_raw(expected_text)
    # If either side non-numeric, require exact match
    if test_val is None or exp_val is None:
        return "FAIL", None, f"text mismatch: '{test_text}' vs '{expected_text}'"
    # Tolerance compare
    unit = test_unit or exp_unit or "dollar"
    ok, delta = within_tolerance(test_val, exp_val, unit)
    if ok:
        return "PASS", delta, None
    return "FAIL", delta, f"|{test_val:,.4g} - {exp_val:,.4g}| = {abs(delta):,.4g} ({unit})"


def compare_text_to_text(a_text: str, b_text: str, kind: str) -> tuple[str, float | None, str | None]:
    """Layer 2 compare. Numeric within tolerance."""
    if not a_text and not b_text:
        return "PASS", None, None
    if not b_text:
        return "WARN", None, "MRP tab cell empty"
    a_val, a_unit = parse_to_raw(a_text)
    b_val, b_unit = parse_to_raw(b_text)
    if a_val is None or b_val is None:
        if a_text.strip() == b_text.strip():
            return "PASS", None, None
        return "FAIL", None, f"text mismatch: '{a_text}' vs '{b_text}'"
    unit = a_unit or b_unit or "dollar"
    ok, delta = within_tolerance(a_val, b_val, unit)
    if ok:
        return "PASS", delta, None
    return "FAIL", delta, f"|{a_val:,.4g} - {b_val:,.4g}| = {abs(delta):,.4g} ({unit})"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def fmt_delta(delta: float | None, kind: str) -> str:
    if delta is None:
        return ""
    if kind in ("dollar", "vs_ol_dollar"):
        abs_v = abs(delta)
        if abs_v >= 1_000_000:
            return f"{abs_v/1_000_000:.1f}M"
        return f"{abs_v:,.0f}"
    if kind in ("pct", "yoy_pct"):
        return f"{abs(delta)*100:.1f}pt"
    if kind == "pts":
        return f"{abs(delta)*100:.2f}pts"
    return f"{delta}"


def write_report(checks: list[Check], packet: dict, out_path: str) -> dict[str, int]:
    pass_n = sum(1 for c in checks if c.status == "PASS")
    fail_n = sum(1 for c in checks if c.status == "FAIL")
    warn_n = sum(1 for c in checks if c.status == "WARN")

    l1 = [c for c in checks if c.layer == "L1"]
    l2 = [c for c in checks if c.layer == "L2"]

    def counts(rows: list[Check]) -> dict[str, int]:
        return {"PASS": sum(1 for r in rows if r.status == "PASS"),
                "FAIL": sum(1 for r in rows if r.status == "FAIL"),
                "WARN": sum(1 for r in rows if r.status == "WARN")}

    l1_c = counts(l1)
    l2_c = counts(l2)

    lines = []
    meta = packet.get("meta", {})
    lines.append(f"# MRP Validation Report — {meta.get('report_month', '?')}")
    lines.append("")
    lines.append(f"**Generated:** {meta.get('generated_at', '?')}")
    lines.append(f"**Quarter:** {meta.get('quarter', '?')} ({meta.get('ol_label', '?')} = {meta.get('ol_scenario', '?')})")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total checks:** {len(checks)}")
    lines.append(f"- **PASS:** {pass_n}  | **FAIL:** {fail_n}  | **WARN:** {warn_n}")
    lines.append(f"- **Layer 1** (Test tab ↔ JSON packet): "
                 f"{l1_c['PASS']} PASS / {l1_c['FAIL']} FAIL / {l1_c['WARN']} WARN")
    lines.append(f"- **Layer 2** (Test tab ↔ MRP tab manual reference): "
                 f"{l2_c['PASS']} PASS / {l2_c['FAIL']} FAIL / {l2_c['WARN']} WARN")
    lines.append("")
    if meta.get("qtd_pace_contingency_note"):
        lines.append(f"_QTD Pace note: {meta['qtd_pace_contingency_note']}_")
        lines.append("")

    def section(title: str, rows: list[Check]) -> None:
        if not rows:
            return
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Layer | R | Row | Col | Kind | Test | Expected | Δ | Note |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for c in rows:
            lines.append(
                f"| {c.layer} | {c.row_idx} | {c.row_label} | {c.col} | {c.cell_kind} | "
                f"`{c.test_text}` | `{c.expected_text}` | "
                f"{fmt_delta(c.delta, c.cell_kind)} | {c.note or ''} |"
            )
        lines.append("")

    section("Failures", [c for c in checks if c.status == "FAIL"])
    section("Warnings", [c for c in checks if c.status == "WARN"])

    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    return {"PASS": pass_n, "FAIL": fail_n, "WARN": warn_n,
            "L1_PASS": l1_c["PASS"], "L1_FAIL": l1_c["FAIL"], "L1_WARN": l1_c["WARN"],
            "L2_PASS": l2_c["PASS"], "L2_FAIL": l2_c["FAIL"], "L2_WARN": l2_c["WARN"]}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Validate MRP Block P&L Overview population")
    p.add_argument("--doc", required=True, help="Path to docs-get JSON (with --include-tabs)")
    p.add_argument("--packet", required=True, help="Path to mrp_data.py JSON packet")
    p.add_argument("--test-tab", required=True, help="Test tab ID (where automation wrote)")
    p.add_argument("--mrp-tab", default="t.ea3bz9hprpol", help="MRP reference tab ID")
    p.add_argument("--out", required=True, help="Output markdown report path")
    args = p.parse_args()

    with open(args.packet) as f:
        packet = json.load(f)

    doc = load_doc(args.doc)
    test_content = get_tab_content(doc, args.test_tab)
    if test_content is None:
        print(f"ERROR: test tab {args.test_tab} not in doc", file=sys.stderr)
        return 1
    test_table = find_block_pl_table(test_content)
    if test_table is None:
        print(f"ERROR: Block P&L table not found in test tab {args.test_tab}", file=sys.stderr)
        return 1

    mrp_content = get_tab_content(doc, args.mrp_tab)
    mrp_table = find_block_pl_table(mrp_content) if mrp_content else None
    if mrp_table is None:
        print(f"WARN: MRP reference tab {args.mrp_tab} table not found; Layer 2 skipped", file=sys.stderr)

    checks = validate(packet, test_table, mrp_table, args.test_tab, args.mrp_tab)
    counts = write_report(checks, packet, args.out)

    print(f"Validation: {counts['PASS']} PASS / {counts['FAIL']} FAIL / {counts['WARN']} WARN")
    print(f"  Layer 1: {counts['L1_PASS']}/{counts['L1_FAIL']}/{counts['L1_WARN']}")
    print(f"  Layer 2: {counts['L2_PASS']}/{counts['L2_FAIL']}/{counts['L2_WARN']}")
    print(f"Report: {args.out}")
    return 0 if counts["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
