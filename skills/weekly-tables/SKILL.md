---
name: weekly-tables
description: Construct markdown performance tables from the master pacing sheet for the Block weekly digest. Standalone testing via /weekly-tables. Referenced by weekly-summary for integrated generation.
depends-on: [financial-reporting, financial-reporting-weekly, gdrive]
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "1.0.0"
  status: active
---

# Weekly Performance Tables

Generate markdown tables from the master pacing sheet for each Overview section of the Block Performance Digest.

---

## Step 1 — Auth check

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py auth status
```

Stop if not valid.

---

## Step 2 — Read the master pacing sheet

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4 --sheet summary
```

Parse the returned JSON into a 2D array of cell values.

---

## Step 3 — Identify sheet structure

The sheet has multiple sections, each with its own header rows. Identify sections by scanning column B (index 1) for these labels:

| Section Label | Table It Feeds |
|---|---|
| `1a) Block gross profit` | GP Performance |
| `1b) Block adjusted OI` | AOI & Rule of 40 |
| `2) Cash App (Ex Commerce) Inflows Framework` | Inflows — Cash App |
| `3) Commerce Inflows Framework` | Inflows — Commerce |
| `4) Square GPV` | Square GPV |

Each section has its own year/type/month header rows immediately below the section label. However, the column structure is consistent across sections:

**Table format: 3-row header with separator column.** Each table uses a 3-row header (year / type / month) matching the 3/17 reference format, plus a blank separator column between monthly and quarterly groups.

**Column layout (9 columns for tables with Guidance + Consensus):**

| Col Index | Header Row 1 (type) | Header Row 2 (month) | Sheet Col |
|---|---|---|---|
| 0 | *(empty)* | *(empty)* | Metric labels (B) |
| 1 | Actual | January | 11 |
| 2 | Actual | February | 12 |
| 3 | Pacing | March | 13 |
| 4 | *(separator — always empty)* | *(separator)* | — |
| 5 | Pacing | Q1 | 17 |
| 6 | Annual Plan | Q1 | 18 |
| 7 | Guidance | Q1 | 20 (sections 1a, 1b) |
| 8 | Consensus | Q1 | 21 (sections 1a, 1b) or 20 (sections 2, 4) |

Header row 0 (year): all data columns show "2026"; col 0 and col 4 are empty.

**Column variations by table:**

| Table | Total Cols | Omitted |
|---|---|---|
| GP Performance (1a) | 9 | — |
| AOI & Rule of 40 (1b) | 9 | — |
| Inflows — Cash App (2) | 8 | Col 7 (Guidance); Consensus at col 7 from sheet 20 |
| Inflows — Commerce (3) | 7 | Col 7 + Col 8 (no Guidance or Consensus) |
| Square GPV (4) | 8 | Col 7 (Guidance); Consensus at col 7 from sheet 20 |

**Omit** Guidance or Consensus columns entirely from the table if no data exists for ANY metric in that table.

---

## Step 4 — Identify metric rows

Within each section, locate metric rows by scanning column B (index 1). Each metric has a value row followed by sub-rows:

### GP Performance (from section 1a)

| Row Group | Col B Labels (in order) |
|---|---|
| Block GP | `Block gross profit` → `YoY Growth (%)` → `Delta vs. AP (%)` |
| Cash App GP | `Cash App gross profit` → `YoY Growth (%)` → `Delta vs. AP (%)` |
| Square GP | `Square gross profit` → `YoY Growth (%)` → `Delta vs. AP (%)` |
| Proto GP | `Proto gross profit` → `YoY Growth (%)` → `Delta vs. AP (%)` |
| TIDAL GP | `TIDAL gross profit` → `YoY Growth (%)` → `Delta vs. AP (%)` |

### AOI & Rule of 40 (from section 1b)

| Row Group | Col B Labels (in order) |
|---|---|
| Gross profit | `Gross profit` → `YoY Growth (%)` → `Delta vs. AP (%)` |
| AOI | `Adjusted operating income` → `Margin (%)` → `Delta vs. AP (%)` |
| Rule of 40 | `Rule of 40` → `Delta vs. AP (pts)` |

### Inflows — Cash App (from section 2)

| Row Group | Col B Labels (in order) |
|---|---|
| Actives | `Actives` → `YoY Growth (%)` → `Delta vs. AP (%)` |
| Inflows per Active | `Inflows per Active` → `YoY Growth (%)` → `Delta vs. AP (%)` |
| Monetization rate | `Monetization rate` → `YoY Growth (%)` → `Delta vs. AP (%)` |

Note: YoY and Delta rows for monetization rate contain bps values (e.g., `42 bps`, `20 bps`). Display these as-is.

### Inflows — Commerce (from section 3)

| Row Group | Col B Labels (in order) |
|---|---|
| Inflows | `Inflows` → `YoY Growth (%)` → `Delta vs. AP (%)` |
| Monetization rate | `Monetization rate` → `YoY Growth (%)` → `Delta vs. AP (%)` |

Skip Commerce Actives and Inflows per Active rows (they contain `#N/A`).

### Square GPV (from section 4)

| Row Group | Col B Labels (in order) |
|---|---|
| Global GPV | `Global GPV` → `YoY Growth (%)` → `Delta vs. AP (%)` |
| US GPV | `US GPV` → `YoY Growth (%)` → `Delta vs. AP (%)` |
| International GPV | `International GPV` → `YoY Growth (%)` → `Delta vs. AP (%)` |

---

## Step 5 — Cell formatting rules (table-specific)

All formatting inherits from the global recipe (`financial-reporting/SKILL.md`), with these table-specific overrides:

**Negatives:** Always use parentheses in tables — `($38M)`, `(1.6%)`, `(5 bps)`. Convert hyphen-prefixed negatives from the sheet (e.g., `-$38M`) to parenthetical format.

**Time periods in headers:** Use abbreviated format — `Q1'26`, `Mar'26`, `Jan'26`, `Feb'26`.

**Dollar rounding:**
- Billions: 2 decimals — `$1.04B`, `$2.90B`
- Millions ≥ $10M: no decimal — `$940M`, `$358M`
- Millions < $10M: 1 decimal — `$4.2M`, `$9.0M`
- Use $B for Block GP and GPV figures. Use $M for brand-level GP and AOI.

**Percentage rounding:**
- < 10%: 1 decimal — `9.0%`, `3.3%`, `7.0%`
- ≥ 10%: no decimal — `29%`, `24%`, `34%`
- Exception: GPV YoY in 10–15% range keeps 1 decimal — `12.6%`, `13.1%`

**Basis points:** Integer with space before `bps` — `42 bps`, `30 bps`, `(5 bps)`

**Actives:** 1 decimal — `58.5M`, `57.0M`

**Special values:**
- `nm` (not meaningful) → display as `nm`
- `#N/A` → display as `--`
- Empty/missing → display as `--`
- Raw decimal values (e.g., `0.2421`) → these are unformatted sheet internals, use the displayed value from the matching formatted row instead

**Signs:** Always include +/- on YoY growth and delta values in tables. Use parentheses for negatives.
- Positive: `+3.3%`, `+$93M`, `+10 bps`
- Negative: `(1.6%)`, `($4.8M)`, `(5 bps)`
- Zero: `0.0%`, `$0M`, `0 bps`

---

## Step 6 — Generate markdown tables

For each table, output a markdown table with a **3-row header** and a blank **separator column** (col 4) between monthly and quarterly groups. Use a row of empty cells between row groups as a visual separator.

The 3-row header in markdown: row 0 (year) is the markdown header row; rows 1–2 (type, month) are body rows with an empty first cell. The converter auto-detects these as header rows.

### Table 1: GP Performance

```
| | 2026 | 2026 | 2026 | | 2026 | 2026 | 2026 | 2026 |
|---|---|---|---|---|---|---|---|---|
| | Actual | Actual | Pacing | | Pacing | Annual Plan | Guidance | Consensus |
| | January | February | March | | Q1 | Q1 | Q1 | Q1 |
| Block gross profit | [val] | [val] | [val] | | [val] | [val] | [val] | [val] |
| YoY Growth (%) | [val] | [val] | [val] | | [val] | [val] | [val] | [val] |
| Delta vs. AP (%) | [val] | [val] | [val] | | [val] | -- | [val] | [val] |
| | | | | | | | | |
| Cash App gross profit | [val] | [val] | [val] | | [val] | [val] | -- | [val] |
| YoY Growth (%) | ... | ... | ... | | ... | ... | -- | ... |
| Delta vs. AP (%) | ... | ... | ... | | ... | -- | -- | ... |
| | | | | | | | | |
| Square gross profit | ... |
...
```

### Table 2: AOI & Rule of 40

Same 9-column layout as Table 1. Row groups: Gross profit (3 rows), AOI (3 rows), Rule of 40 (2 rows — value + Delta vs. AP (pts)).

### Table 3: Inflows — Cash App (Ex Commerce)

8 columns (no Guidance). Same 3-row header; Consensus at col 7.

```
| | 2026 | 2026 | 2026 | | 2026 | 2026 | 2026 |
|---|---|---|---|---|---|---|---|
| | Actual | Actual | Pacing | | Pacing | Annual Plan | Consensus |
| | January | February | March | | Q1 | Q1 | Q1 |
```

Row groups: Actives (3 rows), Inflows per Active (3 rows), Monetization rate (3 rows).

### Table 4: Inflows — Commerce

7 columns (no Guidance or Consensus). Same 3-row header.

```
| | 2026 | 2026 | 2026 | | 2026 | 2026 |
|---|---|---|---|---|---|---|
| | Actual | Actual | Pacing | | Pacing | Annual Plan |
| | January | February | March | | Q1 | Q1 |
```

Row groups: Inflows (3 rows), Monetization rate (3 rows).

### Table 5: Square GPV

8 columns (same as Table 3). Row groups: Global GPV (3 rows), US GPV (3 rows), International GPV (3 rows).

---

## Step 7 — Output

**Standalone mode** (`/weekly-tables`): Write all 5 tables to a single file:

```
~/Desktop/Nick's Cursor/Weekly Reporting/weekly_tables_YYYY-MM-DD.md
```

Use today's date. Each table should have a markdown heading above it matching the Overview section name.

**Integrated mode** (called by weekly-summary): Return the table markdown for each section to be embedded in the weekly summary MD at the appropriate position (above fact lines in each Overview section).

---

## Step 8 — Report back

Tell Nick:
- How many tables generated (expect 5)
- Any cells that fell back to `--` (metric + column)
- Any formatting edge cases encountered
