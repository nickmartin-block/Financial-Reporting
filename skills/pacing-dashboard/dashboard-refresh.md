---
name: dashboard-refresh
description: Read the master pacing sheet and generate dashboard_data.js for the live pacing dashboard. Extracts Block consolidated, Cash App, and Square metrics with quarterly pacing, WoW delta, YoY growth, and consensus comparisons.
depends-on: [financial-reporting, gdrive]
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "1.0.0"
  status: active
---

# Dashboard Refresh Skill

Generate `dashboard_data.js` for the Block Pacing Dashboard by reading the master pacing sheet.

## Step 1: Auth Check

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py auth status
```

If auth fails, stop and ask user to re-authenticate.

## Step 2: Read Pacing Sheet

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4 --sheet summary
```

This returns a JSON 2D array. Parse it into rows.

## Step 3: Section Label Scanning

Scan column B (index 1) for these exact section labels:

| Label | Section ID | Purpose |
|-------|-----------|---------|
| `1a) Block gross profit` | 1a | GP Performance (Block, Cash App, Square, Proto, TIDAL) |
| `1b) Block adjusted OI` | 1b | AOI & Rule of 40 |
| `2) Cash App (Ex Commerce) Inflows Framework` | 2 | Cash App Inflows (Actives, Inflows/Active, Monetization) |
| `4) Square GPV` | 4 | Square GPV (Global, US, International) |

Skip section 3 (Commerce) — not shown on dashboard.

## Step 4: Column Index Reference

| Data | Sheet Column Index |
|------|--------------------|
| Metric labels | 1 (col B) |
| Q1 Pacing | 17 |
| Q1 Annual Plan (AP) | 18 |
| Q1 Guidance | 20 (sections 1a, 1b only) |
| Q1 Consensus | 21 (sections 1a, 1b) or 20 (sections 2, 4) |
| Prior Week Q1 Pacing (Tues Innercore share) | 27 |
| vs. Tues Delta (col AC — change vs. prior Innercore share) | 28 |

**Consensus column differs by section:**
- Sections 1a, 1b → col 21
- Sections 2, 4 → col 20

## Step 5: Extract Metrics

Within each section, find metric rows by scanning col B for exact label matches. Each metric group has 2-3 rows:

### From Section 1a (GP Performance):

**Block Gross Profit** (3 rows):
- Row with col B = `Block gross profit` → value row
- Next row: `YoY Growth (%)` → growth row
- Next row: `Delta vs. AP (%)` → delta row

Extract from value row: Q1 Pacing (col 17), Q1 AP (col 18), Q1 Guidance (col 20), Q1 Consensus (col 21), vs. Tues Delta (col 28)
Extract from growth row: YoY at col 17 (internal), YoY at col 21 (consensus YoY)

**Cash App gross profit** — same 3-row pattern, same columns
**Square gross profit** — same 3-row pattern, same columns

### From Section 1b (AOI & Rule of 40):

**Adjusted operating income** (3 rows):
- `Adjusted operating income` → value
- `Margin (%)` → margin row
- `Delta vs. AP (%)` → delta

**Rule of 40** (2 rows):
- `Rule of 40` → value
- `Delta vs. AP (pts)` → delta

**GP Net of Risk Loss**: Scan for `Gross profit net of risk loss` or similar label in section 1b. If not found, check if it's derived (Block GP minus risk loss). Extract value and YoY if available. Guidance = "--" (not guided).

### From Section 2 (Cash App Inflows):

**Actives** (3 rows): `Actives` → `YoY Growth (%)` → `Delta vs. AP (%)`
**Inflows per Active** (3 rows): `Inflows per Active` → `YoY Growth (%)` → `Delta vs. AP (%)`
**Monetization rate** (3 rows): `Monetization rate` → `YoY Growth (%)` → `Delta vs. AP (%)`

Consensus for section 2 is at col **20** (not 21).
Monetization YoY is in basis points.

### From Section 4 (Square GPV):

**Global GPV** (3 rows): `Global GPV` → `YoY Growth (%)` → `Delta vs. AP (%)`
**US GPV** (3 rows): `US GPV` → `YoY Growth (%)` → `Delta vs. AP (%)`
**International GPV** (3 rows): `International GPV` → `YoY Growth (%)` → `Delta vs. AP (%)`

Consensus for section 4 is at col **20** (not 21).

## Step 6: Formatting Rules

### Dollar Amounts
- Billions: 2 decimals → `$2.90B`, `$1.04B`
- Millions ≥ $10M: no decimal → `$940M`, `$638M`
- Millions < $10M: 1 decimal → `$4.2M`, `$9.0M`
- Use $B for: Block GP, all GPV figures
- Use $M for: brand-level GP (Cash App, Square), AOI

### Percentages
- < 10%: 1 decimal → `7.0%`, `3.3%`
- ≥ 10%: no decimal → `27%`, `34%`
- Exception: GPV YoY 10-15% range keeps 1 decimal → `12.6%`

### Basis Points
- Integer with space: `30 bps`, `4 bps`

### Actives
- Always 1 decimal: `58.5M`

### Signs
- Always +/- on YoY and deltas: `+27%`, `+$100M`, `-1.6%`
- Negatives in parentheses: `(1.6%)`, `($38M)`, `(5 bps)`

### Special Values
- Missing/empty/error → `--`
- Not meaningful → `nm`

## Step 7: Compute Derived Values

### vs. Tues Delta
Use col 28 (AC) directly. This is the change vs. the prior Tuesday Innercore share — the anchor our executive team is grounded in. Format as dollar amount with sign. Column displays as "vs. Tues" in the dashboard.

### vs. Consensus
Calculate: Q1 Pacing (col 17) minus Q1 Consensus. Format as dollar delta with sign.
If consensus is empty/missing, show `--`.

### Consensus YoY (Block table only)
Read the YoY Growth row at the consensus column (col 21 for sections 1a/1b).

### Scorecard Signals
- Green: delta vs comparison > +0.5%
- Yellow: delta between -0.5% and +0.5%
- Red: delta < -0.5%

### Key Takeaways
Generate two sentences:
- "**Gross profit** is expected to land at {Block GP Q1 Pacing}, {YoY}% YoY, {vs cons dollar} vs. consensus"
- "**Adjusted operating income** is expected to land at {AOI Q1 Pacing}, {margin}% margin, {vs cons dollar} vs. consensus"

## Step 8: Extract Commentary from Innercore Doc

Read the Innercore weekly performance digest:
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs get 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0 --include-tabs
```

**Find the most recent weekly tab** (highest date under 1Q26 parent). Navigate: `tabs[0].childTabs[0]` for the latest.

**Extract 3-5 key takeaways** beyond the auto-generated GP and AOI headlines. Focus on:
- **AOI WoW change and drivers** — what moved AOI this week, with dollar amounts
- **Outperformance / expectations management** — any notes on beat magnitude and implications
- **Notable risks or opportunities** — quantified dollar impact items
- **Actives or other call-outs** — anything pertinent that week (use judgment)

**Format each takeaway** as an HTML string with `<strong>` tags for the topic label:
```
"<strong>AOI WoW drivers</strong>: +$23M WoW driven by ..."
```

**Write to** `/tmp/commentary.json` as a JSON array of strings:
```bash
python3 -c "import json; json.dump([...takeaways...], open('/tmp/commentary.json','w'), indent=2)"
```

The refresh.py script will pick up `/tmp/commentary.json` automatically.

## Step 9: Write dashboard_data.js

Run the refresh script to generate `dashboard_data.js` (reads pacing sheet, corp/consensus models, and commentary):
```bash
cd ~/Desktop/Nick's\ Cursor/Pacing\ Dashboard && python3 refresh.py
```

## Step 10: Sync index.html

Copy `dashboard.html` → `index.html` so Block Cell serves the page correctly (Block Cell does not auto-resolve `/` to `/index.html`).

## Step 11: Validate

Run the validation suite:
```bash
cd ~/Desktop/Nick's\ Cursor/Pacing\ Dashboard && uv run validate.py --quick
```

Use `--quick` for local checks only (fast). Use full mode (no flag) if Snowflake connectivity is available.

**If validation fails:** Read `/tmp/validation_report.json` and send a Slack DM to nmart (U051CL4GC2X) with the failures. Use the Slack MCP `post_message` tool:
- Channel: channel_id: U051CL4GC2X (Nick's DM — use channel_id, not username)
- Message format:
  ```
  :red_circle: *Dashboard Validation Failed*
  {N} checks failed:
  • {failure 1}
  • {failure 2}
  Dashboard was NOT deployed. Fix the issues and re-run.
  ```
- **Do NOT deploy to Block Cell if validation fails.** Stop and alert.

**If validation passes with warnings:** Include warnings in the report output but proceed with deployment.

**If validation passes:** Proceed to deploy.

## Step 12: Deploy to Block Cell

Upload the Pacing Dashboard directory to Block Cell:
- Site name: `nmart-pacing-dashboard`
- Production URL: https://blockcell.sqprod.co/sites/nmart-pacing-dashboard/index.html

## Step 13: Report & Notify

Output a summary:
- Timestamp
- Number of metrics populated
- Any missing cells (flagged as `--`)
- Validation results (passes, warnings)
- Number of commentary takeaways extracted from Innercore doc

**On successful deploy**, send a Slack DM to nmart (U051CL4GC2X):
```
:white_check_mark: *Dashboard Refreshed*
{timestamp} — {N} checks passed, {W} warnings
Key metrics: GP {value}, AOI {value}, Rule of 40 {value}
:link: https://blockcell.sqprod.co/sites/nmart-pacing-dashboard/index.html
```
