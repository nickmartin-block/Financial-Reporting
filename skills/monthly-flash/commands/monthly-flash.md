---
name: monthly-flash
description: Generate, publish, and validate the Block Monthly Topline Flash end-to-end. Takes a target Google Doc URL as Step 1, builds the data layer from BDM + Snowflake via /flash-data, generates the narrative with GAAP V/A/F + driver commentary, populates the in-tab Summary Table, and validates. Auto-detects monthly vs quarterly mode from the report period.
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Bash(sq agent-tools google-drive:*)
  - Bash(python3:*)
  - Read
  - Write
  - Edit
metadata:
  author: nmart
  version: "2.0"
  status: active
---

# Block Monthly Topline Flash

Generate, publish, and validate the monthly flash report in one pass. Data is sourced from BDM + Snowflake via `/flash-data` and written into a "validation copy" in the brand reporting model (`MRP Charts & Tables`), then read by the narrative + Doc table populator. The target Doc is supplied as a URL argument so the same skill works for any month + any Doc.

**Dependencies:**
- `~/skills/monthly-flash/flash-data/commands/flash-data.md` — Step 1 invokes this
- `~/skills/monthly-flash/flash-data/skills/flash-data-sourcing.md` — source-of-truth mapping
- `~/skills/monthly-flash/skills/financial-reporting.md` — global formatting recipe

**Scope:** v2.0 supports both **monthly** (intra-quarter: Jan, Feb, Apr, May, Jul, Aug, Oct, Nov) and **quarterly** (quarter-end: Mar, Jun, Sep, Dec) modes. Mode auto-detects from the report period. Quarterly mode reads the QTD view at `MRP Charts & Tables!T400:Y427` and uses Q1/Q2/Q3/Q4 narrative labels.

---

## Configuration

| Parameter | Value |
|---|---|
| Data workbook | `15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0` |
| Data tab | `MRP Charts & Tables` |
| Flash table range (monthly) | `L400:S427` (28 rows × 8 cols) |
| Flash table range (quarterly) | `T400:Y427` (28 rows × 6 cols — no label col, no Prior-mo YoY) |
| Standardized P&L range | `L432:R468` |
| Output Path | `~/Desktop/Nick's Cursor/Monthly Reporting/monthly_flash_YYYY_MM.md` |
| Validation Path | `~/Desktop/Nick's Cursor/Monthly Reporting/validation_YYYY_MM.md` |
| Helper data packet | `/tmp/flash_out_{period}.json` (produced by `/flash-data`) |

The target Doc + tab are supplied as a URL argument (Step 1).

---

## Step 1 — Receive Doc URL and configure run

The user invokes `/monthly-flash <DOC_URL>` where `<DOC_URL>` looks like:

```
https://docs.google.com/document/d/<DOC_ID>/edit?tab=<TAB_ID>
```

Parse the URL into:

- `DOC_ID` — the path segment between `/d/` and the next `/` or `?`.
- `TAB_ID` — the value of the `tab` query parameter (e.g. `t.6lmbmhs5p561`). If the URL has no `tab=` param, default to the first tab returned by `gdrive-cli.py docs tabs <DOC_ID>`.

Determine the report period:

- If the user passed a period argument (e.g. `Apr'26`), use it.
- Otherwise default to the most recently closed month (one back from today).

Detect **mode**:

- Monthly: report month ∈ {Jan, Feb, Apr, May, Jul, Aug, Oct, Nov}
- Quarterly: report month ∈ {Mar, Jun, Sep, Dec} → narrative anchors to the full quarter (`Q1 / Q2 / Q3 / Q4`), reads QTD columns `T400:Y427`

OL scenario label:

| Quarter | OL label |
|---|---|
| Q1 | `AP` (no Q1OL — Annual Plan is Q1's plan) |
| Q2 | `Q2OL` |
| Q3 | `Q3OL` |
| Q4 | `Q4OL` |

State back: `Running /monthly-flash for {period} ({mode} mode) on Doc {DOC_ID}, tab {TAB_ID}. OL scenario = {ol_label}.`

---

## Step 2 — Build the data layer

Invoke `/flash-data --period {period} --mode {mode}` to populate the sheet ranges and emit `/tmp/flash_out_{period}.json`. See `flash-data.md` for full sourcing.

If `/flash-data` was already run for this period and the packet exists at `/tmp/flash_out_{period}.json`, re-run is optional.

The packet contains:
- `flash_table_raw` / `flash_table_formatted` — 28 rows × 8 cols (label + 7 data cols, identical shape regardless of mode)
- `pnl_table_raw` / `pnl_table_formatted` — 37 rows × 7 cols (always GAAP OpEx breakdown)
- `raw_derived` — all derived values (Adj OpEx, R40 components, V/A/F bucket totals, every OpEx line item delta) needed for driver attribution

---

## Step 3 — Read the populated data layer

For **monthly mode** (M-S, 8 cols):
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 --range "'MRP Charts & Tables'!L400:S427"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 --range "'MRP Charts & Tables'!L432:R468"
```

For **quarterly mode** (T-Y QTD view, 6 cols — labels live in col L, shared with the monthly view):
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 --range "'MRP Charts & Tables'!L400:L427"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 --range "'MRP Charts & Tables'!T400:Y427"
```

Equivalent — load the formatted tables directly from the JSON packet (`flash_table_formatted` + `pnl_table_formatted`).

### Flash table row mapping (rows 400–427, both modes share the same row order)

| Row offset | Metric |
|---|---|
| 0 | Period header (e.g., `Apr'26`) |
| 1 | Column headers |
| 2 | Cash App Actives |
| 3 | Cash App Inflows per Active |
| 4 | Commerce GMV |
| 5 | Square GPV |
| 6 | Square US GPV |
| 7 | Square INTL GPV |
| 8 | Square INTL GPV (CC) — blank in v1 |
| 9 | "Gross Profit" section header |
| 10 | Block GP |
| 11 | Cash App GP |
| 12 | Commerce GP |
| 13 | Borrow GP |
| 14 | Cash App Card GP |
| 15 | Instant Deposit GP |
| 16 | Post-Purchase BNPL GP |
| 17 | Square GP |
| 18 | US Payments GP |
| 19 | INTL Payments GP |
| 20 | Banking GP |
| 21 | SaaS GP |
| 22 | Hardware GP |
| 23 | TIDAL GP |
| 24 | Proto GP |
| 25 | Adjusted Opex |
| 26 | Adjusted OI |
| 27 | Rule of 40 |

### Column mapping (Flash table)

**Monthly (M-S):**

| Col offset | Content |
|---|---|
| 0 | Row label (col L) |
| 1 | Actual (M) |
| 2 | vs. OL $ (N) |
| 3 | vs. OL % (O) |
| 4 | vs. AP $ (P) |
| 5 | vs. AP % (Q) |
| 6 | YoY % (R) |
| 7 | Prior-month YoY % (S) |

**Quarterly (T-Y):**

| Col offset (T-Y range) | Content |
|---|---|
| 0 | Actual (T) |
| 1 | vs. Q-OL $ (U) |
| 2 | vs. Q-OL % (V) |
| 3 | vs. AP $ (W) |
| 4 | vs. AP % (X) |
| 5 | YoY % (Y) |

QTD view has no Prior-month YoY column. Labels still live in col L.

### Standardized P&L row mapping (L432:R468)

| Row offset | Section / Metric |
|---|---|
| 0 | Column headers |
| 1 | "Variable Operational Costs" (section) |
| 2 | P2P |
| 3 | Risk Loss |
| 4 | Card Issuance |
| 5 | Warehouse Financing |
| 6 | Other (parent) |
| 7 | Hardware Logistics (child) |
| 8 | Bad Debt Expense (child) |
| 9 | Customer Reimbursements (child) |
| 10 | **Total Variable Operational Costs** |
| 11 | "Acquisition Costs" (section) |
| 12 | Marketing (Non-People) (parent) |
| 13-16 | Marketing, Onboarding, Partnership Fees, Reader Expense (children) |
| 17 | Sales & Marketing (People) |
| 18 | **Total Acquisition Costs** |
| 19 | "Fixed Costs" (section) |
| 20 | Product Development People |
| 21 | G&A People (parent) |
| 22-23 | G&A People (ex. CS), Customer Support People (children) |
| 24 | Software & Cloud (parent) |
| 25-26 | Software, Cloud fees (children) |
| 27 | Taxes, Insurance & Other Corp |
| 28 | Litigation & Professional Services (parent) |
| 29-30 | Legal fees, Other Professional Services (children) |
| 31 | Rent, Facilities, Equipment |
| 32 | Travel & Entertainment |
| 33 | Hardware Production Costs |
| 34 | Non-Cash expenses (ex. SBC) |
| 35 | **Total Fixed Costs** |
| 36 | **Total Block GAAP OpEx** |

### Comparison point detection

The Outlook scenario depends on the report quarter: Q1 → AP (no Q1OL — Annual Plan IS Q1's plan), Q2 → Q2OL, Q3 → Q3OL, Q4 → Q4OL. Flash-data already wrote the correct scenario into the "vs. OL" columns — narrative just references "Q2OL" (or whichever) per the financial-reporting recipe.

---

## Step 4 — Generate the flash narrative

Invoke `build_narrative.py` directly. The script applies the full Flash convention: Q2OL (or active OL) as the primary comparison anchor for all metric lines, AP supplementally on Adj OpEx + Rule of 40, V/A/F driver attribution with the materiality threshold + Corp-context flag, Block Variable Profit and GAAP Operating Income lines, brand bridge bullet, and the ±10 precision rule on every variance/YoY/pts cell.

```bash
python3 ~/skills/monthly-flash/flash-data/helpers/build_narrative.py \
  --packet /tmp/flash_out_{period}.json \
  --period "{Mon'YY}" \
  --ol-label "{OL scenario}" \
  --mode {monthly|quarterly} \
  --output ~/Desktop/Nick's\ Cursor/Monthly\ Reporting/monthly_flash_YYYY_MM.md
```

Args:
- `--packet` — JSON packet emitted by `/flash-data` in Step 2 (must exist).
- `--period` — e.g. `Apr'26`. Drives the H1 title and month-label substitutions.
- `--ol-label` — e.g. `Q2OL`. For Q1 use `AP` (no Q1OL — AP is Q1's plan).
- `--mode` — `monthly` for intra-quarter months, `quarterly` for Mar/Jun/Sep/Dec. `auto` lets the script detect.

The script handles everything the narrative needs — do not edit its output. If a driver attribution call-out looks off or a Corp-context flag fires incorrectly, fix in `build_narrative.py` (thresholds, leaf lists) or `flash_data.py` (raw inputs), not by hand-editing the MD.

### Thresholds (encoded in `build_narrative.py`)

- **Driver inclusion:** abs(line item Δ vs OL) ≥ $2M OR ≥ 5% of bucket total. Top 2-3 per bucket, ranked by abs Δ desc.
- **Corp-context flag:** bucket-level variance ≥ $20M abs OR ≥ 10% vs OL → appends `**Corp to include context.**` (red bold via Step 6h).
- **±10 precision rule:** |magnitude| ≤ 10 → 1 decimal; > 10 → integer. Applied to every variance/YoY/pts value.

### Comparison anchor (matches Flash convention)

- **Primary anchor:** active OL scenario for Q2/Q3/Q4 (e.g. Q2OL); AP for Q1.
- **Supplementary AP mention** on Adj OpEx (`-$XM below AP`) and Rule of 40 (`+X pts above AP`).
- **Brand bridge** on the Block GP line uses OL deltas (Cash App + Square + Other Brands sum to Block GP vs OL).
- **Sub-product outperformance** lines for Cash App / Square rank sub-products by OL $ delta (positive first, then "partially offset by" negatives).

---

## Step 5 — Save the MD

Write to `~/Desktop/Nick's Cursor/Monthly Reporting/monthly_flash_YYYY_MM.md`.

---

## Step 6 — Publish to Google Doc

The target tab (`{TAB_ID}`) is a persistent template: H1 with `[MONTH] [YEAR]` placeholders, italic disclaimer with `[MRP DATE]` + `[YEAR]` placeholders, H2 "[MONTH] Summary", empty narrative space, H2 "Summary Table", 28×7 table shell. **Do not clear the tab** — operate in place.

### 6a — Fill template placeholders

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs replace {DOC_ID} --find "[MONTH]" --replace "{MonthName}"
cd ~/skills/gdrive && uv run gdrive-cli.py docs replace {DOC_ID} --find "[YEAR]" --replace "{Year}"
```

For quarterly mode, also adjust H2 from "MonthName Summary" → "Q{N} {Year} Summary":
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs replace {DOC_ID} --find "{MonthName} Summary" --replace "Q{N} {Year} Summary"
```

**Caveat:** `gdrive-cli.py docs replace` is NOT tab-scoped. Confirm the placeholder strings don't exist in other tabs of the same Doc before running; if they do, use direct `batchUpdate` with `tabId` instead.

`[MRP DATE]` stays — Nick fills in manually.

### 6b — Delete any existing narrative body

Fetch the doc, find the H2 "{PeriodLong} Summary" and H2 "Summary Table" paragraphs (where PeriodLong is e.g. "April 2026" for monthly, "Q2 2026" for quarterly). Delete the content range `[endIndex(H2 Summary), startIndex(H2 Summary Table)]` via `deleteContentRange` with `tabId`. This wipes any prior narrative without touching the H2 anchors or the table shell.

### 6c — Insert the narrative markdown body

The narrative MD (from Step 5) includes H1 + disclaimers + H2 markers + body. Strip the prefix (first 8 lines through and including the H2 line + the blank line after it) and pipe only the body to `insert-markdown` at the index of the H2 Summary's `endIndex` (the start of the empty space we just cleared):

```bash
tail -n +9 ~/Desktop/Nick\'s\ Cursor/Monthly\ Reporting/monthly_flash_YYYY_MM.md \
  | (cd ~/skills/gdrive && uv run gdrive-cli.py docs insert-markdown {DOC_ID} \
       --tab {TAB_ID} --at-index {h2_summary_end_index} --font Roboto)
```

The narrative MD was written to `~/Desktop/Nick's Cursor/Monthly Reporting/monthly_flash_YYYY_MM.md` in Step 4/5 (not `/tmp`). Use the same path.

### 6d — Bullet nesting fix

The markdown converter renders parent bullets ("- **Cash App gross profit**") as paragraphs and child bullets at the SAME nesting level rather than nested. After insert:

1. Re-read the doc; find the range from "Cash App gross profit" paragraph start through "Proto gross profit" paragraph end.
2. `deleteParagraphBullets` on that range.
3. Insert a `\t` at the start of each sub-product paragraph (Commerce GMV, Cash App Actives, Cash App Inflows per Active, Global GPV, US GPV, INTL GPV) — process in **descending** index order so earlier inserts don't shift later ones.
4. `createParagraphBullets` with `BULLET_DISC_CIRCLE_SQUARE` preset on the (expanded) range. Tab chars are consumed and converted into nesting level 1.

### 6e — Reset narrative paragraphs to NORMAL_TEXT

Known `insert-markdown` quirk: when inserting at an index immediately after an H2, every inserted paragraph inherits `namedStyleType=HEADING_2`. Apply `updateParagraphStyle` with `paragraphStyle.namedStyleType=NORMAL_TEXT` and `fields=namedStyleType` over the narrative range to fix this. Use `[narrative_start, narrative_end_after_inserts]` and be careful **not to overshoot into the H2 "Summary Table"** (a strict-less-than check on the H2's `startIndex`).

If the H2 "Summary Table" gets accidentally demoted, restore it with `updateParagraphStyle({namedStyleType: HEADING_2})` on its range.

### 6f — Apply Roboto on the narrative range

```
updateTextStyle({weightedFontFamily: {fontFamily: "Roboto"}}) over the narrative range, fields=weightedFontFamily
```

Don't apply tab-wide — the table cells are already Roboto from Step 6j's populator and tab-wide ranges can collide with section/table segment boundaries.

### 6g — Apply bold to metric labels

`insert-markdown` sometimes drops bold styling when paragraphs inherit HEADING_2 (and the NORMAL_TEXT reset doesn't re-apply bold). Restore by finding each metric label at the start of its paragraph and applying `bold: true`:

```
Block gross profit, Cash App gross profit, Commerce GMV, Cash App Actives,
Cash App Inflows per Active, Square gross profit, Global GPV, US GPV, INTL GPV,
TIDAL gross profit, Proto gross profit, Block variable profit, Adjusted Opex,
Variable costs, Acquisition costs, Fixed costs, GAAP operating income,
Adjusted Operating Income, {MonthName} Rule of 40  (or Q{N} Rule of 40)
```

### 6h — Apply red bold to "Corp to include context." phrases

For each occurrence of `Corp to include context.` (V/A/F bucket bullets that triggered the corp-context flag): apply `updateTextStyle` with `foregroundColor={red:0.85,green:0.16,blue:0.16}` AND `bold:true` over the phrase range. Process in descending index order.

### 6i — Populate the Summary Table

```bash
# 1. Read the right sheet range based on mode
RANGE_MONTHLY="'MRP Charts & Tables'!L400:S427"
RANGE_QUARTERLY="'MRP Charts & Tables'!T400:Y427"  # labels still come from L400:L427 separately

cd ~/skills/gdrive && uv run gdrive-cli.py sheets read \
    15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 \
    --range "$RANGE" > /tmp/flash_sheet.json

# 2. Read doc, run populator (values pass)
cd ~/skills/gdrive && uv run gdrive-cli.py docs get {DOC_ID} --include-tabs > /tmp/flash_doc.json
python3 ~/skills/monthly-flash/flash-data/helpers/populate_flash_table.py \
    /tmp/flash_sheet.json /tmp/flash_doc.json {TAB_ID} --pass values --mode {mode} \
    | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})

# 3. Re-read doc, run populator (colors pass — needs fresh indices)
cd ~/skills/gdrive && uv run gdrive-cli.py docs get {DOC_ID} --include-tabs > /tmp/flash_doc_v2.json
python3 ~/skills/monthly-flash/flash-data/helpers/populate_flash_table.py \
    /tmp/flash_sheet.json /tmp/flash_doc_v2.json {TAB_ID} --pass colors --mode {mode} \
    | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update {DOC_ID})
```

What the populator does:
- **Values pass** clears every data cell in rows 2–27, inserts the formatted sheet value, applies Roboto 10pt + CENTER. Variance cols (2, 3, 4) get the ±10 precision rule via `reformat_variance` before insert. Rows 10 (Block GP), 26 (Adjusted OI), 27 (Rule of 40) get `bold:true`; all other rows `bold:false` for deterministic state. Doc col 6 (Prior-mo YoY) is cleared in quarterly mode (no QTD source).
- **Colors pass** sets foreground color on cols 2-6:
  - col 2 (vs. OL $) → green/red if `|Δ| > $0.5M`, else black
  - col 3 (vs. OL %) → green/red if `|Δ| > 1.0%`, else black
  - col 4 (vs. AP %) → green/red if `|Δ| > 1.0%`, else black
  - cols 5 + 6 (YoY %, Mar YoY %) → always black (per Flash disclaimer: "Variances in charts are not color coded for ... YoY comparisons")
  - `nm`, `--`, empty → black

### 6j — Verify

Read back the doc structure and confirm:
- H1: "Block Topline Flash: {PeriodLong}"
- Italic disclaimer paragraphs (first with bold MRP reference)
- H2: "{PeriodLong} Summary"
- Bullet nesting: Cash App / Square at level 0, sub-items at level 1
- All metric labels bold
- "Corp to include context" phrases in red bold wherever they appear
- Summary Table populated with sheet values, % cols color-coded, rows 10/26/27 bold

---

## Step 7 — Validate

Run `~/skills/monthly-flash/commands/monthly-validate.md`.

Execute its Steps 1–7. The validation re-reads the populated ranges (`L400:S427` + `L432:R468`) and the published Doc, compares every metric value, and saves a validation report to:

```
~/Desktop/Nick's Cursor/Monthly Reporting/validation_YYYY_MM.md
```

---

## Step 8 — Report back

Tell Nick:
- **File:** path to the saved .md
- **Doc:** link to the Google Doc with tab
- **Data layer refresh time:** when `/flash-data` last populated the ranges
- **Validation:** PASS or FAIL (N values compared, N failures). Include failure details if any.
- **Corp-context flags:** which V/A/F buckets are flagged for context
- **Placeholders:** count of `[MRP DATE]` items remaining
- If PASS → "Data is clean."

---

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| L400:S427 is empty or stale | `/flash-data` didn't run for this month, or wrote to a different period | Re-run Step 1. Check the period header in row 400 col M. |
| Driver attribution misses obvious lines | Threshold too strict (e.g. all line items under $2M for a small bucket) | Lower threshold in this run, or report top 3 unconditionally. Use discretion. |
| Red text didn't apply | Phrase string mismatch (extra punctuation / spaces) | Step 6h find-string must match exactly — adjust if narrative text drifted. |
| Validation fails on a sub-product GP | Source convention change since flash-data last ran | Re-run /flash-data; if persistent, check flash-data-sourcing.md mapping for the row. |
