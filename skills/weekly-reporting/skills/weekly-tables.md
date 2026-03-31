---
name: weekly-tables
description: Populate pre-formatted template tables in the Google Doc with values from the master pacing sheet via Docs API batch-update. Standalone testing via /weekly-tables. Referenced by weekly-summary for integrated table population.
depends-on: [financial-reporting, financial-reporting-weekly, gdrive]
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "2.0.0"
  status: active
---

# Weekly Performance Tables

Populate pre-formatted template tables in the Block Performance Digest Google Doc with values from the master pacing sheet. The template tab (created by Nick) contains 5 tables with row labels, column headers, and styling — but empty data cells. This skill reads values from the Sheet and writes them into the Doc via Docs API `batch-update`.

**Doc ID:** `1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0`
**Sheet ID:** `1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4` (tab: `summary`)

---

## Step 1 — Auth check

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py auth status
```

Stop if not valid.

---

## Step 2 — Read the master pacing sheet

**Integrated mode** (called by the weekly-summary publish agent): Read from the cached temp file at `/tmp/pacing_sheet_YYYY-MM-DD.json` — do NOT re-read the sheet API. The publish agent passes the file path.

**Standalone mode** (called via `/weekly-tables`):
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4 --sheet summary
```

Parse the JSON into a 2D array of cell values.

---

## Step 3 — Find the template tab

**Standalone mode:** List tabs and find the current week's date tab.

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs tabs 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0
```

Find the tab matching today's date (M/D format, e.g., `3/24`) under the current quarter parent (e.g., `1Q26`). If no matching tab exists, STOP and tell Nick to create the template tab first.

**Integrated mode** (called by weekly-summary): The tab ID is passed in. Skip this step.

---

## Step 4 — Read Doc template structure

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs get 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0 --include-tabs
```

Navigate to the target tab in the JSON. Walk `body.content` to find all 5 table elements. For each table:

1. **Identify the table** by the nearest preceding heading text or by scanning the first column (col 0) for row labels:
   - GP Performance: "Block gross profit" in first data row
   - AOI & Rule of 40: "Gross profit" in first data row
   - Cash App Inflows: "Actives" in first data row
   - Commerce: "Inflows" in first data row
   - Square GPV: "Global GPV" in first data row

2. **Extract cell positions** for every data cell (row ≥ 3, col ≥ 1, skip separator col 4). For each cell, find the paragraph element's `startIndex` inside `tableCells[col].content[0].paragraph.elements[0]`. Empty cells contain a single `textRun` with content `"\n"` — the `startIndex` of this element is where we insert text.

---

## Step 5 — Map Sheet values to Doc cells

### Column mapping

Doc columns map to Sheet columns (0-indexed from the Sheet JSON `values` array):

| Doc Col | Content | Sheet Col |
|---|---|---|
| 0 | Row labels | (skip — already in template) |
| 1 | Jan Actual | 11 |
| 2 | Feb Actual | 12 |
| 3 | Mar Pacing | 13 |
| 4 | Separator | (skip — always empty) |
| 5 | Q1 Pacing | 17 |
| 6 | Q1 AP | 18 |
| 7 | Q1 Guidance (1a, 1b) or Q1 Consensus (2, 4) | 20 |
| 8 | Q1 Consensus (1a, 1b only) | 21 |

**Column count by table:**

| Table | Doc Cols | Has Col 7 | Has Col 8 |
|---|---|---|---|
| GP Performance (1a) | 9 | Guidance (sheet 20) | Consensus (sheet 21) |
| AOI & Rule of 40 (1b) | 9 | Guidance (sheet 20) | Consensus (sheet 21) |
| Cash App Inflows (2) | 8 | Consensus (sheet 20) | — |
| Commerce (3) | 7 | — | — |
| Square GPV (4) | 8 | Consensus (sheet 20) | — |

### Row mapping

Each table's data rows map to specific Sheet rows. Identify section start rows by scanning column B (index 1) for section labels, then offset to data rows:

**GP Performance (section `1a) Block gross profit`):**

| Doc Row | Row Label | Sheet Row Offset from Section |
|---|---|---|
| 3 | Block gross profit | +3 (first data row after 3 header rows) |
| 4 | YoY Growth (%) | +4 |
| 5 | Delta vs. AP (%) | +5 |
| 6 | (blank separator) | skip |
| 7 | Cash App gross profit | +7 |
| 8–9 | YoY / Delta | +8, +9 |
| 10 | (blank) | skip |
| 11–13 | Square GP group | +11, +12, +13 |
| 14 | (blank) | skip |
| 15–17 | Proto GP group | +15, +16, +17 |
| 18 | (blank) | skip |
| 19–21 | TIDAL GP group | +19, +20, +21 |

**AOI & Rule of 40 (section `1b) Block adjusted OI`):**

| Doc Row | Row Label | Sheet Row Offset |
|---|---|---|
| 3–5 | Gross profit group | +3, +4, +5 |
| 6 | (blank) | skip |
| 7–9 | AOI group | +7, +8, +9 |
| 10 | (blank) | skip |
| 11 | Rule of 40 | +11 |
| 12 | Delta vs. AP (pts) | +12 |

**Cash App Inflows (section `2) Cash App (Ex Commerce)`):**

| Doc Row | Row Label | Sheet Row Offset |
|---|---|---|
| 3–5 | Actives group | +3, +4, +5 |
| 6 | (blank) | skip |
| 7–9 | Inflows per Active group | +7, +8, +9 |
| 10 | (blank) | skip |
| 11–13 | Monetization rate group | +11, +12, +13 |

**Commerce (section `3) Commerce Inflows Framework`):**

Uses Commerce-specific row offsets. Scan for `Inflows` label (skip Actives/IPA rows which contain `#N/A`):

| Doc Row | Row Label | Sheet Row Offset from `Inflows` label |
|---|---|---|
| 3–5 | Inflows group | 0, +1, +2 |
| 6 | (blank) | skip |
| 7–9 | Monetization rate group | +4, +5, +6 |

**Square GPV (section `4) Square GPV`):**

| Doc Row | Row Label | Sheet Row Offset |
|---|---|---|
| 3–5 | Global GPV group | +3, +4, +5 |
| 6 | (blank) | skip |
| 7–9 | US GPV group | +7, +8, +9 |
| 10 | (blank) | skip |
| 11–13 | International GPV group | +11, +12, +13 |

### Value extraction

For each mapped cell, read the value from `sheet_data[sheet_row][sheet_col]`:
- If the value is non-empty and not a raw decimal internal → use it as-is (the Sheet already has display-formatted values like `$940M`, `29%`, `42 bps`)
- If the value is empty, missing, or `#N/A` → use `--`
- If the value looks like a raw decimal (e.g., `0.2421`, `1040843820.9176`) → skip it, use the formatted value from the corresponding display column instead

---

## Step 6 — Build and execute batch-update

For each data cell that has a value, create three requests:

1. **`insertText`** — insert the value at the cell's `startIndex` (before the existing `\n`)
2. **`updateTextStyle`** — set Roboto 10pt on the inserted text range `[startIndex, startIndex + len(value)]`
3. **`updateParagraphStyle`** — set CENTER alignment on the cell paragraph `[startIndex, startIndex + len(value) + 1]`

**Critical:** Include `"tabId": "TAB_ID"` in every `location` and `range` object.

**Critical:** Sort ALL requests by `startIndex` **descending** (highest first). Since requests are applied sequentially, inserting at higher indices first means lower indices remain valid for subsequent insertions.

Execute as a single batch-update:

```bash
echo '<JSON>' | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0)
```

Verify the response shows `"status": "ok"`.

---

## Step 7 — Apply conditional colors on Delta rows

After populating values, apply green/red text color to "Delta vs. AP" rows.

1. **Re-read the Doc structure** (cell indices have shifted from Step 6 insertions):

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs get 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0 --include-tabs
```

2. For each table, find the "Delta vs. AP (%)" and "Delta vs. AP (pts)" rows by scanning column 0 text.

3. For each data cell in those rows: collect ALL text runs in the cell (the `%` sign may be a separate text run from the number). Concatenate text to determine sign, then use the full range from `first_textRun.startIndex` to `last_textRun.startIndex + len(last_text)` for the color:
   - **Positive** (no parens, not zero, not `--`, not `nm`) → green: `{"rgbColor": {"red": 0.0, "green": 0.48, "blue": 0.2}}`
   - **Negative** (starts with `(` or `-`) → red: `{"rgbColor": {"red": 0.8, "green": 0.0, "blue": 0.0}}`
   - **Zero** (`0.0%`, `0%`, `$0M`, `0 bps`, `0pts`) or `--` → no color change

4. Build `updateTextStyle` requests with `foregroundColor` for each colored cell. The range must span ALL text runs in the cell (not just the first). Execute as a batch-update.

---

## Step 8 — Report back

Tell Nick:
- How many cells populated across all 5 tables
- Any cells that fell back to `--` (table + metric + column)
- Conditional colors applied (count of green/red cells)
- Any issues encountered
