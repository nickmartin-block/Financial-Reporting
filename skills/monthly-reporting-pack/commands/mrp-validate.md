---
name: mrp-validate
description: Validate the published MRP Test tab against the JSON data packet (Layer 1) and the manual MRP tab reference (Layer 2). Cell-by-cell comparison for Block P&L Overview + Standardized P&L tables. Reports PASS/FAIL/WARN.
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Bash(python3:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "2.0"
  status: development
---

# MRP Validate

Cell-by-cell validation of the published MRP Test tab. Two layers:

- **Layer 1 (publish-pipeline check):** Test tab cell ↔ JSON packet value. Catches populator bugs.
- **Layer 2 (source-mapping check):** Test tab cell ↔ MRP tab manual reference cell. Catches data-source mapping errors that Layer 1 misses.

**Scope (v1):** Test tab Tables 2 (Block P&L Overview, 30×7) and 3 (Stnd P&L Double Click, 45×4). Other tables not validated.

---

## Step 1 — Inputs

- `DOC_ID` — required (from URL or arg)
- `TEST_TAB_ID` — default `t.3mz1duijrdf1`
- `MRP_TAB_ID` — default `t.ea3bz9hprpol` (manual reference)
- `PACKET_PATH` — default `/tmp/mrp_out_{YYYY_MM}.json` (derive YYYY_MM from packet meta or from period arg)

---

## Step 2 — Read Test tab + MRP tab

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs get {DOC_ID}
```

Parse out Tables 2 and 3 from both tabs. Extract cell text into a structured form:
```python
{tab_id: {table_idx: [[cell_text per col] per row]}}
```

---

## Step 3 — Layer 1 validation (Test tab ↔ JSON packet)

For each row in `packet["block_pl"]["rows"]`:
- Compare `*_formatted` strings to Test tab cell text exactly
- For numeric mismatches, parse + compare with tolerance: $1M for amounts, 0.5pts for rates
- Flag missing cells (empty when JSON has a value) and extra cells (non-empty when JSON has `null`/gap)

Same for `packet["stnd_pl"]["rows"]`.

---

## Step 4 — Layer 2 validation (Test tab ↔ MRP tab manual)

For each cell in (Test tab Table 2 ∪ Table 3):
- Compare to the same cell position in (MRP tab corresponding table)
- Parse numerics with tolerance ($1M / 0.5pts)
- Flag deltas

Known WARN-not-FAIL discrepancies (from Flash v2.0 + Mar'26 MRP work):
- Square sub-product groupings (Banking, SaaS, Hardware basis differences)
- GAAP OpEx ~$13M gap (MCP aggregate vs reference)
- People row (headcount) — DATA GAP, always WARN

---

## Step 5 — Output report

Write to `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_validation_{YYYY_MM}.md`:

```markdown
# MRP Validation Report — {Month YYYY}

**Date:** YYYY-MM-DD
**Test tab:** {TEST_TAB_ID}
**MRP tab (reference):** {MRP_TAB_ID}
**Packet:** {PACKET_PATH}

## Summary
- Table 2 (Block P&L): {pass}/{total} cells PASS, {fail} FAIL, {warn} WARN
- Table 3 (Stnd P&L): {pass}/{total} cells PASS, {fail} FAIL, {warn} WARN
- Layer 1 (cell ↔ packet): {summary}
- Layer 2 (cell ↔ MRP tab): {summary}

## Failures
| Table | Row | Col | Test value | Expected | Source | Notes |
|---|---|---|---|---|---|---|

## Warnings (known discrepancies)
| Table | Row | Col | Test value | MRP tab | Notes |
|---|---|---|---|---|---|

## Gaps
| Table | Row | Cell | Status |
|---|---|---|---|
```

Print console summary:
```
=== /mrp-validate ===
Layer 1: {n_pass}/{n_total} PASS | {n_fail} FAIL | {n_warn} WARN
Layer 2: {n_pass}/{n_total} PASS | {n_fail} FAIL | {n_warn} WARN
Report: {path}
```
