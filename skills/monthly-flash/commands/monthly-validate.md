---
name: monthly-validate
description: Validate the published Block Monthly Topline Flash Google Doc against the validation-copy brand reporting model ranges. Compares every metric value-by-value. Run after /monthly-flash completes or independently to re-check after manual edits. Auto-detects monthly vs quarterly mode from the period in the Doc.
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Bash(sq agent-tools google-drive:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "2.0"
  status: active
---

# Monthly Flash — Data Validation

Your job: confirm every number in the published Doc matches the validation copy in `MRP Charts & Tables` (the sheet that `/flash-data` populated from BDM + Snowflake). Flag every mismatch. Do not write to the Doc. Do not fix errors.

**Dependencies:** Load `~/skills/monthly-flash/skills/financial-reporting.md` for formatting standards and rounding rules.

---

## Configuration

| Parameter | Value |
|---|---|
| Data workbook | `15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0` |
| Data tab | `MRP Charts & Tables` |
| Flash table range (monthly) | `L400:S427` |
| Flash table range (quarterly) | `T400:Y427` (labels still in col L) |
| Standardized P&L range | `L432:R468` |
| Validation Path | `~/Desktop/Nick's Cursor/Monthly Reporting/validation_YYYY_MM.md` |

Target Doc + Tab are supplied as a URL argument: `/monthly-validate <DOC_URL>` or read from the most recent `/monthly-flash` invocation context. Parse the URL like the `/monthly-flash` command does (Step 1 there).

---

## Step 1 — Auth + parse target

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py auth status
```

Parse `<DOC_URL>` → `DOC_ID` + `TAB_ID`. Stop if auth or URL is invalid.

Determine mode from the period in the doc:
- Read the H1 of the target tab. If it says "Block Topline Flash: {Month} {Year}" (e.g. "April 2026") → **monthly**.
- If it says "Block Topline Flash: Q{N} {Year}" (e.g. "Q2 2026") → **quarterly**.

---

## Step 2 — Read both sources in parallel

**Sheet (validation copy):**

Monthly mode:
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 --range "'MRP Charts & Tables'!L400:S427"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 --range "'MRP Charts & Tables'!L432:R468"
```

Quarterly mode (labels still in col L, plus T-Y for the QTD data):
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 --range "'MRP Charts & Tables'!L400:L427"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 --range "'MRP Charts & Tables'!T400:Y427"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0 --range "'MRP Charts & Tables'!L432:R468"
```

**Doc text (what we're validating):**

Read the target tab's content via `docs get {DOC_ID} --include-tabs` and navigate to `tabId={TAB_ID}`.

---

## Step 3 — Build ground truth from the sheet

### Flash table column mapping

**Monthly (L400:S427):**

| Index (col offset) | Content |
|---|---|
| 0 | Row label |
| 1 | Actual |
| 2 | vs. OL $ |
| 3 | vs. OL % |
| 4 | vs. AP $ |
| 5 | vs. AP % |
| 6 | YoY % |
| 7 | Prior-month YoY % |

**Quarterly (T400:Y427, no label col within the range — labels live in col L):**

| Index (col offset in T-Y) | Content |
|---|---|
| 0 | Actual (T) |
| 1 | vs. Q-OL $ (U) |
| 2 | vs. Q-OL % (V) |
| 3 | vs. AP $ (W) |
| 4 | vs. AP % (X) |
| 5 | YoY % (Y) |

Quarterly mode has no Prior-month YoY — skip that comparison.

### Flash table row mapping (0-indexed from values array, which starts at row 400)

| Row offset | Metric | Doc Label |
|---|---|---|
| 2 | Cash App Actives | Cash App Actives |
| 3 | Cash App Inflows per Active | Cash App Inflows per Active |
| 4 | Commerce GMV | Commerce GMV |
| 5 | Square GPV | Global GPV |
| 6 | Square US GPV | US GPV |
| 7 | Square INTL GPV | INTL GPV |
| 10 | Block GP | Block gross profit |
| 11 | Cash App GP | Cash App gross profit |
| 17 | Square GP | Square gross profit |
| 23 | TIDAL GP | TIDAL gross profit |
| 24 | Proto GP | Proto gross profit |
| 25 | Adjusted Opex | Adjusted Opex |
| 26 | Adjusted OI | Adjusted Operating Income |
| 27 | Rule of 40 | Rule of 40 |

**Cash App sub-products (vs OL $ for outperformance line — narrative ranks by OL delta in Q2-Q4):**

| Row | Metric |
|---|---|
| 12 | Commerce GP |
| 13 | Borrow GP |
| 14 | Cash App Card GP |
| 15 | Instant Deposit GP |
| 16 | Post-Purchase BNPL GP |

**Square sub-products (vs OL $ for outperformance line — narrative ranks by OL delta in Q2-Q4):**

| Row | Metric |
|---|---|
| 18 | US Payments GP |
| 19 | INTL Payments GP |
| 20 | Banking GP |
| 21 | SaaS GP |
| 22 | Hardware GP |

### Standardized P&L column mapping (L432:R468)

| Index | Content |
|---|---|
| 0 | Row label |
| 1 | Actual |
| 2 | vs. OL $ |
| 3 | vs. OL % |
| 4 | vs. AP $ |
| 5 | vs. AP % |
| 6 | YoY % |

### V/A/F bucket totals (row offset from row 432)

| Row offset | Metric | Doc Label |
|---|---|---|
| 10 | Total Variable Operational Costs | Variable costs |
| 18 | Total Acquisition Costs | Acquisition costs |
| 35 | Total Fixed Costs | Fixed costs |
| 36 | Total Block GAAP OpEx | (cross-check vs Adjusted Opex headline; should ≈ Adj OpEx + restructuring + amort intangibles) |

For each metric row, extract values from the appropriate columns. Skip cells containing `#REF!`, `#DIV/0!`, `n/a`, `nm`, or empty values.

---

## Step 4 — Compare every value

For each metric in ground truth, find its label in the doc text and verify each value.

### What to check per metric

| Value Type | Where it appears in the doc |
|---|---|
| Actual | Dollar amount / count / percentage immediately after the metric label |
| vs OL $ | Dollar amount near "vs. Q2OL" (or QnOL for the quarter) |
| vs OL % | Percentage near "vs. Q2OL" |
| vs AP $ | Dollar amount near "vs. AP" |
| vs AP % | Percentage near "vs. AP" |
| YoY % | Percentage immediately before "YoY" |
| Prior-month YoY % | Percentage in parentheses near "in [Prior Month]" |
| Rule of 40 deltas | "+X.X pts" with sign, near "vs. AP" / "YoY" |

### Also check

- **Sub-product deltas:** Cash App outperformance line lists sub-products with OL $ deltas (vs Q2OL / Q3OL / Q4OL for Q2-Q4; vs AP $ only when running Q1). Square outperformance line same. Verify each delta.
- **Brand bridge:** Block GP headline includes contributions from Cash App, Square, and Other Brands. Verify each — the bridge uses OL deltas (or AP in Q1). Other Brands = TIDAL vs OL $ + Proto vs OL $.
- **V/A/F driver bullets:** the bucket totals + vs OL deltas in the doc must match Stnd P&L totals. Per-line driver call-outs need not be exhaustively validated, but the bucket-level numbers must.

### Normalization rules

Strip both doc and sheet values to raw numbers before comparing:

- **Dollars:** Strip `$`, `M`, `B`, `K`, commas. Convert $B to $M (×1000). Parentheses → negative.
- **Percentages:** Strip `%`, `+`, `-`. Parentheses → negative.
- **Points:** Strip `pts`, `+`, `-`.
- **Actives:** Strip `M`.
- **Special values:** `n/a`, `nm`, `--`, empty → treat as equivalent (skip comparison).

### Rounding tolerance

| Display format | Tolerance |
|---|---|
| Percentages (no decimal) | ±0.5 pp |
| Percentages (1 decimal) | ±0.05 pp |
| Dollar values in $B (2 decimals) | ±$5M |
| Dollar values in $M (no decimal) | ±$0.5M |
| Dollar values in $M (1 decimal) | ±$0.05M |
| Points (no decimal) | ±0.5 pts |
| Points (1 decimal) | ±0.05 pts |

**PASS** if within tolerance. **FAIL** if outside tolerance or expected value not found in doc.

### Special cases

- **Rule of 40:** Actual is a percentage; deltas are in pts, not dollars or percentages
- **Actives:** Actual is in M; delta is in M (not dollars)
- **Proto/Hardware:** May have negative actuals — verify sign matches
- **"nm" YoY:** Skip the YoY comparison for that metric (variance > 1000%)

---

## Step 5 — Tally results

Count:
- Total values compared
- Values passed
- Values failed

---

## Step 6 — Output report

Save to `~/Desktop/Nick's Cursor/Monthly Reporting/validation_YYYY_MM.md`:

```
# Monthly Flash Validation — [Month] [Year]

## Result: PASS / FAIL

- Metrics validated: [N]
- Values compared: [N]
- ✅ Passed: [N]
- ❌ Failed: [N]

## Failures

[List every failure: ❌ | [Metric] | [Value Type] | Doc: [value] | Sheet: [value]]

(If zero failures: "No mismatches found.")
```

---

## Step 7 — Report back

Tell Nick:
- **PASS** (zero failures) or **FAIL** ([N] failures)
- Total values compared
- Any failures with details
- If PASS → "Data is clean."
