---
name: mrp
description: Populate the Block P&L Overview and Standardized P&L tables on the Test tab of the April 2026 MRP doc from BDM + Snowflake data. v2.0 — deterministic helpers, JSON packet contract, no narrative, no flux sheet.
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Bash(python3:*)
  - Read
  - Write
  - Edit
metadata:
  author: nmart
  version: "2.0"
  status: development
---

# Monthly Management Reporting Pack — v2.0

Populate the MRP test tab's P&L tables (Block P&L Overview + Standardized P&L) from automated data. **No commentary, no narrative paragraphs, no flux sheet integration in v1.** Tables only.

**Dependencies:**
- `~/skills/monthly-reporting-pack/mrp-data/commands/mrp-data.md` — invoked in Step 2 (data layer)
- `~/skills/monthly-reporting-pack/mrp-data/skills/mrp-data-sourcing.md` — per-row source mapping
- `~/skills/monthly-reporting-pack/skills/financial-reporting.md` — global formatting recipe (rounding, ±10, nm rule)
- `~/skills/monthly-reporting-pack/mrp-data/helpers/populate_block_pl.py` — Table 2 populator
- `~/skills/monthly-reporting-pack/mrp-data/helpers/populate_stnd_pl.py` — Table 3 populator (Phase 6)

**Scope (v1):** Apr'26. Test tab `t.3mz1duijrdf1` on doc `1OLp-j58TDAY3af-LCcdxo6749naA1_CgQm0z5ddPT9E`. Populates Test tab Tables 2 (Block P&L Overview, 30×7) and 3 (Stnd P&L Double Click, 45×4) only. Other 6 tables remain empty.

**Safety:** The populator refuses to write to the MRP tab (`t.ea3bz9hprpol`). Only the Test tab is writable.

---

## Step 1 — Receive Doc URL + parse

User invokes `/mrp <DOC_URL>`. Parse:
- `DOC_ID` from `/d/<DOC_ID>/`
- `TAB_ID` from `?tab=<TAB_ID>`. Default to the first tab if absent. **Refuse if TAB_ID == `t.ea3bz9hprpol` (MRP reference tab).**

Determine reporting period from doc title or user arg (default: most recently closed month).

State back: `Running /mrp for {period} on Doc {DOC_ID}, tab {TAB_ID}. Populating Block P&L (Table 2) + Stnd P&L (Table 3).`

---

## Step 2 — Build the data layer

Invoke `/mrp-data --month {YYYY-MM} [--cache]` to produce the JSON packet at `/tmp/mrp_out_{YYYY_MM}.json`.

If the packet exists and `--cache` is supplied (or the user has confirmed a recent run), skip re-pull.

See `mrp-data.md` for full sourcing details.

---

## Step 3 — Populate Table 2 (Block P&L Overview, 30×7)

Two passes — fetch doc, apply values, re-fetch, apply colors.

```bash
# 3a. Fetch doc JSON (current state)
cd ~/skills/gdrive && uv run gdrive-cli.py docs get {DOC_ID} --include-tabs > /tmp/mrp_doc.json

# 3b. Values pass — apply to Test tab
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/populate_block_pl.py \
  --packet /tmp/mrp_out_{YYYY_MM}.json \
  --doc /tmp/mrp_doc.json \
  --tab {TAB_ID} \
  --pass values \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})

# 3c. Re-fetch doc (indices shifted by inserts)
cd ~/skills/gdrive && uv run gdrive-cli.py docs get {DOC_ID} --include-tabs > /tmp/mrp_doc_v2.json

# 3d. Colors pass — apply green/red to vs.OL cells
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/populate_block_pl.py \
  --packet /tmp/mrp_out_{YYYY_MM}.json \
  --doc /tmp/mrp_doc_v2.json \
  --tab {TAB_ID} \
  --pass colors \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})
```

Helper handles:
- Cell-index discovery: locates the 30×7 table whose R02 = "Gross profit" (not brittle ordinal)
- Values pass: Roboto 10pt, center align, bold for total rows; red foreground on `[GAP]` text
- Colors pass: green/red on vs.OL `$` deltas above ±$0.5M and on pt deltas above ±0.5pt; YoY cols stay black
- Safety guard: refuses if `{TAB_ID}` == `t.ea3bz9hprpol` (MRP reference tab)

---

## Step 4 — Populate Table 3 (Stnd P&L Double Click, 45×4)

*(Phase 6 — gated on Phase 5 Table 2 validation passing.)*

Same two-pass pattern; helper `populate_stnd_pl.py` not yet implemented.

---

## Step 5 — Validate

Invoke `/mrp-validate` with the Test tab ID + packet path. See `mrp-validate.md` for details. Calls `validate_block_pl.py` end-to-end against both layers.

---

## Step 6 — Summary

Print:
```
=== /mrp complete ===
Period: {Month YYYY}
Doc: <url>
Test tab populated: Table 2 ({n2}/30 rows), Table 3 ({n3}/45 rows)
Gaps: {gap_count} cells
Validation: {pass}/{total} PASS, {fail} FAIL, {warn} WARN
```
