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

Same two-pass pattern as Step 3, using `populate_stnd_pl.py`:

```bash
# 4a. Values pass — apply to Test tab Table 3
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/populate_stnd_pl.py \
  --packet /tmp/mrp_out_{YYYY_MM}.json \
  --doc /tmp/mrp_doc.json \
  --tab {TAB_ID} \
  --pass values \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})

# 4b. Re-fetch + colors pass
cd ~/skills/gdrive && uv run gdrive-cli.py docs get {DOC_ID} --include-tabs > /tmp/mrp_doc_v2.json
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/populate_stnd_pl.py \
  --packet /tmp/mrp_out_{YYYY_MM}.json \
  --doc /tmp/mrp_doc_v2.json \
  --tab {TAB_ID} \
  --pass colors \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})
```

Helper handles:
- Cell-index discovery: 45×4 table whose R00 col 0 starts with "Standardized P&L"
- Values pass: Roboto 10pt, CENTER, bold for sub-totals (R26 GAAP OpEx, R27 Total Personnel, R33 Contractors, R39 SBC) + section headers (R02 / R10 / R13)
- Colors pass: single vs.OL column polarity-aware (cost rows: positive = red, negative = green)
- Gap rendering: red `[GAP]` for R28-R38 + R40-R44 (function-level Personnel/Contractors/SBC — not in BDM)
- R39 SBC vs.OL stays blank (`share_based_compensation_incl_cogs_outlook` doesn't exist in BDM)
- Safety: refuses to write to `{TAB_ID}` == `t.ea3bz9hprpol`

---

## Step 4b — Populate Table 5 (Cash App detail, 31×5)

Run only when packet includes `cash_app_detail` block (i.e. when `mrp_data.py` was invoked with `--cash-app-raw`).

```bash
# 4b-i. Values pass
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/populate_cash_app_detail.py \
  --packet /tmp/mrp_out_{YYYY_MM}.json \
  --doc /tmp/mrp_doc_v2.json \
  --tab {TAB_ID} \
  --pass values \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})

# 4b-ii. Re-fetch + colors pass
cd ~/skills/gdrive && uv run gdrive-cli.py docs get {DOC_ID} --include-tabs > /tmp/mrp_doc_v3.json
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/populate_cash_app_detail.py \
  --packet /tmp/mrp_out_{YYYY_MM}.json \
  --doc /tmp/mrp_doc_v3.json \
  --tab {TAB_ID} \
  --pass colors \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})
```

Helper handles:
- Cell-index discovery: 31×5 table whose R02 col 0 == "Cash App Actives"
- Values pass: Roboto 10pt, CENTER, bold for subtotals (R04 Core Cash App, R13 Lending, R18 Cash App GAAP GP, R19 Afterpay, R26 Commerce GAAP GP, R27 Total GAAP GP) + rate row (R30 % Margin)
- Colors pass: TWO colored cols ($ vs OL + % vs OL); cols 1 (Actual) + 4 (YoY) always black; thresholds ±$0.5M / ±0.5%
- Gap rendering: per-cell `[GAP]` for R02/R03 cols 2+3 (no actives outlook in BDM); whole-row `[GAP]` for R28/R29/R30 (no per-brand Variable Opex in BDM — Hyperion direct needed for these)
- Safety: refuses to write to `{TAB_ID}` == `t.ea3bz9hprpol`

See `mrp-data/skills/mrp-data-sourcing.md` Table 5 section for per-row source map + reconciliation against manual MRP.

---

## Step 4c — Populate Table 6 (Square detail, 20×5)

Run only when packet includes `square_detail` block (i.e. when `mrp_data.py` was invoked with `--square-raw`).

```bash
# 4c-i. Values pass
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/populate_square_detail.py \
  --packet /tmp/mrp_out_{YYYY_MM}.json \
  --doc /tmp/mrp_doc_v3.json \
  --tab {TAB_ID} \
  --pass values \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})

# 4c-ii. Re-fetch + colors pass
cd ~/skills/gdrive && uv run gdrive-cli.py docs get {DOC_ID} --include-tabs > /tmp/mrp_doc_v4.json
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/populate_square_detail.py \
  --packet /tmp/mrp_out_{YYYY_MM}.json \
  --doc /tmp/mrp_doc_v4.json \
  --tab {TAB_ID} \
  --pass colors \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})
```

Helper handles:
- Cell-index discovery: 20×5 table whose R02 col 0 starts with "New Volume Added"
- Values pass: Roboto 10pt, CENTER, bold for subtotals (R12 Banking, R16 Total GP) + Variable Profit/Margin rows
- Colors pass: cols 2+3 polarity-aware; thresholds ±$0.5M / ±0.5%
- Per-cell `[GAP]` rendering for NVA/GPV/US-Intl Payments vs OL cols + whole-row `[GAP]` for R17-R19 (Variable Opex/Profit/Margin not in BDM per-brand)
- Safety: refuses to write to `{TAB_ID}` == `t.ea3bz9hprpol`

See `mrp-data/skills/mrp-data-sourcing.md` Table 6 section for per-row source map + reconciliation.

---

## Step 4d — Populate Table 7 (Other Brands detail, 9×5)

Run only when packet includes `other_brands_detail` block (i.e. when `mrp_data.py` was invoked with `--other-brands-raw`).

```bash
# 4d-i. Values pass
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/populate_other_brands_detail.py \
  --packet /tmp/mrp_out_{YYYY_MM}.json \
  --doc /tmp/mrp_doc_v4.json \
  --tab {TAB_ID} \
  --pass values \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})

# 4d-ii. Re-fetch + colors pass
cd ~/skills/gdrive && uv run gdrive-cli.py docs get {DOC_ID} --include-tabs > /tmp/mrp_doc_v5.json
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/populate_other_brands_detail.py \
  --packet /tmp/mrp_out_{YYYY_MM}.json \
  --doc /tmp/mrp_doc_v5.json \
  --tab {TAB_ID} \
  --pass colors \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})
```

Helper handles:
- Cell-index discovery: 9×5 table whose R02 col 0 == "TIDAL"
- Values pass: Roboto 10pt, CENTER, bold for subtotals (R05 Other Brands GAAP GP) + Variable Profit/Margin
- Colors pass: cols 2+3 polarity-aware; thresholds ±$0.5M / ±0.5%
- Whole-row `[GAP]` for R06-R08 (Variable Opex/Profit/Margin not in BDM per-brand)
- Safety: refuses to write to `{TAB_ID}` == `t.ea3bz9hprpol`

See `mrp-data/skills/mrp-data-sourcing.md` Table 7 section for per-row source map + reconciliation. Note: TIDAL maps to TIDAL_BU segment; Bitkey is broken out from Proto_BU segment as the 3 "Wallet" products (2200/4301/4302).

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
