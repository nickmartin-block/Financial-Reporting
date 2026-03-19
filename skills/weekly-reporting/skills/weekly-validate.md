---
name: weekly-validate
description: Validate that every number in the published Block Performance Digest Google Doc matches the master pacing sheet. Compares table cells value-by-value. Run after /weekly-summary completes.
depends-on: [financial-reporting, weekly-tables, gdrive]
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "2.0.0"
  status: active
---

# Weekly Digest — Data Validation

Your job: confirm that every number in the Doc's tables matches the Sheet. Flag every mismatch. Do not write to the Doc. Do not fix errors.

---

## Step 1 — Auth

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py auth status
```

Stop if not valid.

---

## Step 2 — Identify the Doc tab to validate

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs tabs 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0
```

Find the most recent dated tab under the current quarter parent (1Q26 for Jan–Mar, 2Q26 for Apr–Jun, etc.). Confirm with Nick: **"Validating the [date] tab — correct?"**

Wait for confirmation before proceeding.

---

## Step 3 — Read both sources in parallel

**Sheet** (source of truth):

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4 --sheet summary
```

**Doc tables** (what we're validating):

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs extract-tables 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0 --tab <TAB_ID>
```

---

## Step 4 — Build ground truth from the Sheet

Extract values using the column mapping from `~/skills/weekly-tables/SKILL.md` (Steps 3–4). For each metric row, pull:

| Doc Column | Sheet Column Index |
|---|---|
| Jan'26 Actual | 11 |
| Feb'26 Actual | 12 |
| Mar'26 Pacing | 13 |
| Q1'26 Pacing | 17 |
| Q1 AP | 18 |
| Q1 Guidance | 20 (sections 1a, 1b only) |
| Q1 Consensus | 21 (sections 1a, 1b) or 20 (sections 2, 4) |

Organize by section → metric → column, producing one ground-truth value per cell.

---

## Step 5 — Match Doc tables to Sheet sections

Use the `heading` field and first-column metric names to match each Doc table to a Sheet section:

| Doc Table Heading (contains) | Sheet Section |
|---|---|
| Gross Profit Performance | 1a) Block gross profit |
| Adjusted Operating Income | 1b) Block adjusted OI |
| Cash App (Ex Commerce) | 2) Cash App Inflows Framework |
| Commerce | 3) Commerce Inflows Framework |
| Square GPV | 4) Square GPV |

If a table can't be matched, flag it: `❌ UNMATCHED TABLE | [heading]`

---

## Step 6 — Compare every data cell

For each matched table, walk every non-header, non-separator row. For each cell:

1. **Identify the metric** from the leftmost column (e.g., "Block gross profit", "YoY Growth (%)", "Delta vs. AP (%)")
2. **Identify the column** from the header row (e.g., "Jan'26 Actual", "Q1'26 Pacing")
3. **Get the Sheet value** for that metric + column from Step 4
4. **Normalize both values** before comparing:

### Normalization rules

Strip both the Doc value and Sheet value to a raw number for comparison:

- **Dollars:** Convert to millions. `$0.94B` → 940, `$940M` → 940, `$1,041M` → 1041, `$2.90B` → 2900
- **Percentages:** Strip signs and parens. `+29%` → 29, `(0.3%)` → -0.3, `29%` → 29, `-0.3%` → -0.3
- **Basis points:** Strip signs and parens. `+42 bps` → 42, `(5 bps)` → -5, `42 bps` → 42
- **Points:** Strip signs. `+12 pts` → 12, `12pts` → 12
- **Actives:** Convert to millions. `57.0M` → 57.0, `58.5M` → 58.5
- **Plain numbers:** `$470` → 470, `$1,536` → 1536
- **Special values:** `nm`, `--`, empty → treat as equivalent (all mean "no data")

### Comparison

- If both normalize to the same number (within ±0.5 of the last displayed digit): **PASS**
- If both are special values (nm / -- / empty): **PASS**
- If one is a number and the other is special/empty: **FAIL**
- If the numbers differ beyond rounding tolerance: **FAIL**

### Rounding tolerance

The Sheet may show raw values (e.g., "26.8%") while the Doc shows a rounded value (e.g., "+27%"). This is expected — the formatting rules round ≥10% to no decimal. The tolerance rule:

- Percentages displayed with no decimal: ±0.5 pp (e.g., Sheet "26.8%" vs Doc "27%" → PASS)
- Percentages displayed with 1 decimal: ±0.05 pp (e.g., Sheet "9.9%" vs Doc "+9.9%" → PASS)
- Dollar values in $B (2 decimals): ±$5M (e.g., Sheet "$2,903M" vs Doc "$2.90B" → both = 2900-2903 → PASS)
- Dollar values in $M (no decimal): ±$0.5M
- Basis points: ±0.5 bps

Flag format: `❌ | [Table] | [Metric] | [Column] | Doc: [value] | Sheet: [value]`

---

## Step 7 — Tally results

Count:
- Total cells compared
- Cells passed
- Cells failed
- Tables matched (expect 5)

---

## Step 8 — Output report

Save to: `~/Desktop/Nick's Cursor/Weekly Reporting/validation_YYYY-MM-DD.md`

```
# Validation Report — [Tab Date]

## Result: PASS / FAIL

- Tables matched: [N] / 5
- Cells compared: [N]
- ✅ Passed: [N]
- ❌ Failed: [N]

## Failures

[List every ❌ line from Step 6, grouped by table]

(If zero failures: "No mismatches found.")
```

---

## Step 9 — Report back

Tell Nick:
- **PASS** (zero failures) or **FAIL** ([N] failures)
- Total cells compared
- Any failures with details
- If PASS → "Data is clean."
