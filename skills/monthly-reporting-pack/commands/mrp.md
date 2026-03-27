---
name: mrp
description: Generate the full Monthly Management Reporting Pack — end-to-end pipeline from data fetch through publication and validation. The "one command" end state.
allowed-tools:
  - mcp__blockdata__fetch_metric_data
  - mcp__blockdata__get_metric_details
  - mcp__blockdata__get_dimension_values
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Read
  - Write
  - Agent
metadata:
  author: nmart
  version: "1.0"
  status: development
---

# Monthly Management Reporting Pack — Full Pipeline

Generate, publish, and validate the MRP for a given reporting month. This is the end-to-end orchestrator.

**Dependencies — load ALL of these first:**
1. `~/skills/weekly-reporting/skills/financial-reporting.md` — global formatting recipe
2. `~/skills/monthly-reporting-pack/skills/mrp-data-layer.md` — metric registry and product mappings
3. `~/skills/monthly-reporting-pack/skills/mrp-block-overview.md` — Block Financial Overview + Gross Profit + OpEx sections
4. `~/skills/monthly-reporting-pack/skills/mrp-brand-trends.md` — Topline Trends sections (Cash App, Square, Other Brands)
5. `~/skills/monthly-reporting-pack/skills/mrp-flux-commentary.md` — reads flux sheet, merges DRI commentary
6. `~/skills/monthly-reporting-pack/skills/mrp-commentary-validate.md` — pre-publish validation against data packet
7. `~/skills/monthly-reporting-pack/skills/mrp-publishing.md` — publishing pipeline and post-fixes

---

## Step 0 — Confirm Reporting Month

Ask Nick which month to report on. Default: most recent closed month. Set:
- `reporting_month` (e.g., `2026-02`)
- `comparison_scenario` per financial-reporting recipe (Q1 → "2026 Annual Plan")

Also confirm:
- **Publish target:** New doc or update existing? If existing, get doc ID.
- **Flux commentary:** Is the flux sheet populated for this month? Sheet: `1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw`

---

## Step 1 — Fetch Data (runs /mrp-data)

Execute the data fetch procedure from `~/skills/monthly-reporting-pack/commands/mrp-data.md`:

1. Current month actuals (GP by brand, sub-products, AOI, GAAP OpEx, individual OpEx lines, Square GPV, Cash App Actives/Inflows)
2. Forecast/AP (outlook variants with scenario filter)
3. Prior year actuals (same metrics, -12 months)
4. Prior month actuals (headline metrics only)
5. QTD actuals
6. Compute derived metrics (Adjusted OpEx, Rule of 40, Monetization Rate, Inflows/Active, INTL GPV, Commerce/GAAP GP splits)

**Output:** `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json`

Print the summary table and spot-check validation.

---

## Step 2 — Read Flux Commentary (if available)

Read the flux commentary sheet for the reporting month:
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw --range "Cash App GP Summary!A9:N69"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw --range "Square GP Summary!A9:N41"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw --range "Other Brands GP Summary!A1:N16"
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1qE80DGUNen0VIjisvUEhjVhjzWKwlY4LobCT1r4qvEw --range "Opex Summary!A1:N63"
```

Extract column N ("Strat F&S Commentary") for products where column F = "Yes" (commentary needed). Map each product to the MRP section it belongs in.

If flux commentary is not yet populated, skip this step — use red "Nick to fill out" placeholders.

---

## Step 3 — Generate MRP Markdown

Build the full MRP markdown file at `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_YYYY_MM.md` using the agent-based approach.

**Agent pipeline — use the Agent tool to spawn subagents for each step:**

**3a. Spawn two agents IN PARALLEL** (single message, two Agent tool calls):

- **Agent 1 — Block Overview:** Load `mrp-block-overview.md` skill. Read the data packet at `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json`. Generate markdown for: Block Financial Overview (Rule of 40, pacing), Gross Profit (Block/CA/SQ with sub-metrics), Operating Expenses (GAAP/Adjusted/V-A-F). Write output to `~/Desktop/Nick's Cursor/Monthly Reporting Pack/sections/block_overview.md`.

- **Agent 2 — Brand Trends:** Load `mrp-brand-trends.md` skill. Read the same data packet. Generate markdown for: Cash App detail (GP + 4 core drivers + 1 dynamic + Cash Actives), Square detail (GPV + 5 segment drivers), Other Brands (TIDAL, Proto, Bitkey). Write output to `~/Desktop/Nick's Cursor/Monthly Reporting Pack/sections/brand_trends.md`.

**3b. After both agents complete, spawn Agent 3 — Flux Commentary:**
Load `mrp-flux-commentary.md` skill. Read the flux workbook column N from all 6 tabs. Read the section outputs from 3a. For each [Flux: ...] placeholder, insert the DRI commentary from the matching flux row. If column N is empty for a product, leave the placeholder. Write merged outputs back to the same section files.

**3c. Assemble full markdown:**
Combine section files into one MRP markdown file at `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_YYYY_MM.md`:
1. Title + confidentiality disclaimer + color convention header
2. Contents of `block_overview.md` (Block Financial Overview, Watchpoints, Gross Profit, OpEx)
3. Table placeholders for Block P&L, People by Function, Brand P&L Metrics
4. Contents of `brand_trends.md` (Cash App, Square, Other Brands)
5. Table placeholders for Appendix I, Appendix II
6. Footnotes

**3d. Spawn Agent 4 — Pre-publish Validation:**
Load `mrp-commentary-validate.md` skill. Read the assembled markdown and the data packet. Run all validation checks. Report PASS/FAIL/WARN. If failures found, fix them before proceeding to Step 4.

**Full structure (assembled from agent outputs):**
1. Title + confidentiality disclaimer
2. **Block Financial Overview** — Rule of 40, GP/AOI headlines, Q1 pacing (if available)
3. **Watchpoints** — 3 generic slots (red placeholders unless flux has them)
4. **Gross Profit** — Block GP, Cash App GP with sub-metrics (Actives, Inflows/Active, Monetization Rate), Square GP with GPV (Global, US, INTL with acceleration), Variable Profit
5. **Operating Expenses** — GAAP OpEx, Adjusted OpEx, V/A/F breakdown
6. **Block P&L** — Metric inventory (or table when data supports it)
7. **People by Function** — Metric inventory (headcount not in MCP)
8. **Brand P&L Metrics** — VP & Acquisition Spend
9. **Topline Trends by Brand** — Cash App drivers (4 core + 1 dynamic), Square drivers (5 segments), Other Brands
10. **Cash App Detail** — Metric inventory with data availability
11. **Square Detail** — Same
12. **Other Brands Detail** — Same
13. **Appendix I** — Standardized P&L Double Click (individual OpEx lines)
14. **Appendix II** — GP Breakdown by sub-product (PY, CY, AP, YoY%, vs AP$)

**Color convention:**
- Black text: automated (MCP data or flux commentary)
- `«BLUE»...«/BLUE»`: Nick's judgment (pacing, watchpoints, guidance, consensus)
- `«RED»...«/RED»`: data gap (metric missing from MCP)
- Yellow highlight (`«WARN»`): table placeholder

**Key formatting rules (from financial-reporting.md):**
- Dollars in $M (no decimals unless < $10M)
- Percentages to 1 decimal
- Negative numbers in parentheses
- "versus AP" not "vs plan"

---

## Step 4 — Publish to Google Doc

Follow the publishing pipeline in `mrp-publishing.md`:

### 4a. Create or prepare the doc
- If new: create doc in Drive folder `1uykSB8IQ_pzyUypv6CvzRC9ZWWzNDpN1` (2026 folder), month subfolder `M-YY`
- If existing: clear the main tab body

### 4b. Insert markdown
```bash
cat "~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_YYYY_MM.md" | cd ~/skills/gdrive && uv run gdrive-cli.py docs insert-markdown <doc_id> --tab t.0 --font Inter
```

### 4c. Apply color markers
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs get <doc_id> | python3 ~/skills/weekly-reporting/gdrive/scripts/color_markers.py t.0 --colors RED,BLUE,WARN | uv run gdrive-cli.py docs batch-update <doc_id>
```

### 4d. Fix bullet nesting
Read doc structure → identify 4 narrative sections → apply deleteParagraphBullets → insertText \t → createParagraphBullets pattern (sections processed in reverse document order).

### 4e. Fix heading formatting
- All headings -> bold, BLACK
- H1 -> 20pt (title 22pt)
- H2 -> 16pt, H3 -> 14pt
- Font: Only set fontSize, NOT weightedFontFamily (preserves bold from markdown converter)

### 4f. Manual step
Remind Nick: Format -> Page setup -> Pageless

### 4g. Apply yellow table highlighting
After color markers are applied, find all paragraphs containing "[TABLE" and apply yellow background highlighting (#FFF29A) with dark amber foreground (#594600).

---

## Step 5 — Validate

### 5a. Pre-publish validation (mrp-commentary-validate)

Before publishing, run the **mrp-commentary-validate** skill against the assembled markdown and data packet. This checks:
- Every number in black text traces to a data packet field (within tolerance)
- Color coding is correct (black = automated, blue = judgment, red = data gap, yellow = table placeholder)
- Formatting complies with financial-reporting.md standards
- All expected sections are present with correct heading hierarchy
- Flux commentary references are valid

Fix any FAIL items before proceeding to publish. WARN items are acceptable.

### 5b. Post-publish validation (runs /mrp-validate)

Execute validation from `~/skills/monthly-reporting-pack/commands/mrp-validate.md`.

Compare published doc against data packet. Report PASS/FAIL/WARN counts.

---

## Step 6 — Summary

Print final status:
```
=== MRP Pipeline Complete ===
Month: [Month Year]
Data packet: mrp_data_YYYY_MM.json (vX.X)
Markdown: mrp_YYYY_MM.md
Published doc: [URL]
Validation: XX checks | XX PASS | XX FAIL | XX WARN
Flux commentary: [Used / Not available]
Manual remaining: [list of red placeholder sections]
```
