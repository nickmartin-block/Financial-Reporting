---
name: mrp-validate
description: Validate the published MRP Google Doc against the data packet and reference MRP. Compares headline metrics, sub-product GP, and flags discrepancies.
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "1.0"
  status: development
---

# MRP Validation

Cross-check the published MRP Google Doc against the data packet JSON and (optionally) the reference MRP. Reports PASS/FAIL for every metric with tolerance thresholds.

**Dependencies:**
- Load `~/skills/weekly-reporting/skills/financial-reporting.md` for formatting standards
- Load `~/skills/monthly-reporting-pack/skills/mrp-data-layer.md` for metric registry

**Inputs:**
- Data packet: `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json`
- Published doc: the Google Doc ID from the data packet or user
- Reference MRP (optional): `1Fusutm1sHO5zNhKR31XWywQaUSeYR2R25Ozmm4PqqnM` (tab `t.ea3bz9hprpol`)

---

## Step 1 — Load Data Packet

Read `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json`. Extract all metric values.

---

## Step 2 — Read Published Doc

Use `cd ~/skills/gdrive && uv run gdrive-cli.py docs get <doc_id>` to read the published Google Doc. Extract all numbers from:
- Narrative paragraphs (e.g., "$922M", "+28% YoY", "+$38M above AP")
- Metric inventory bullet items (e.g., "Actual ✓ ($140M)")

---

## Step 3 — Headline Metric Checks

Compare these against the data packet (tolerance: $1M or 0.5 pts):

| Check | Data Packet Field | Expected Format in Doc |
|-------|-------------------|----------------------|
| Block GP Actual | `block.gp.actual` | "$922M" |
| Block GP YoY | `block.gp.yoy_pct` | "+28% YoY" |
| Block GP vs AP | `block.gp.vs_plan_dollar` | "+$38M above AP" |
| Cash App GP Actual | `cash_app.gp.actual` | "$601M" |
| Cash App GP YoY | `cash_app.gp.yoy_pct` | "+38% YoY" |
| Cash App GP vs AP | `cash_app.gp.vs_plan_dollar` | "+$30M" or "+5.2%" |
| Square GP Actual | `square.gp.actual` | "$317M" |
| Square GP YoY | `square.gp.yoy_pct` | "+12% YoY" |
| Square GP vs AP | `square.gp.vs_plan_dollar` | "+$5.8M" or "+1.9%" |
| AOI Actual | `block.aoi.actual` | "$231M" or "$231M" |
| AOI Margin | `block.aoi_margin.actual` | "25%" |
| Rule of 40 | `block.rule_of_40.actual` | "53%" |
| Adjusted OpEx | `block.adjusted_opex.actual` | "$691M" |
| Square GPV Global | `square.global_gpv.actual` | "$19.5B" |
| Square GPV US | `square.us_gpv.actual` | "$15.2B" |
| Cash App Actives | `cash_app.actives.actual` | "56.9M" |
| Inflows per Active | `cash_app.inflows_per_active.actual` | "$541" |
| Monetization Rate | `cash_app.monetization_rate.actual` | "1.68%" |

---

## Step 4 — GPV Acceleration Checks

| Check | Data Packet | Expected in Doc |
|-------|-------------|-----------------|
| Global GPV acceleration | `square.gpv_acceleration.global_pts` | "+2.4 pt acceleration" |
| US GPV acceleration | `square.gpv_acceleration.us_pts` | "+2.2 pt" |
| INTL GPV acceleration | `square.gpv_acceleration.intl_pts` | "+3.6 pt" |

---

## Step 5 — Sub-Product GP Checks

For each sub-product in `cash_app.sub_products` and `square.sub_products`:
- Check that the actual value appears in the doc (rounded to nearest $M)
- If PY exists, check YoY % appears
- If AP exists, check vs AP $ appears

Tolerance: $1M for actuals, 1 pt for percentages.

---

## Step 6 — Reference MRP Cross-Check (Optional)

If the reference doc is available, compare key values:

| Category | What to Check |
|----------|--------------|
| Block P&L table | Every row: Actual, YoY%, vs AP |
| Cash App Detail table | Every product: Actual, $ vs AP, % vs AP, YoY% |
| Square Detail table | Same |
| Appendix I | OpEx lines: Actual, YoY, vs AP |
| Appendix II | Sub-product GP: PY, CY, AP, YoY%, vs AP$ |

Known discrepancies to flag but not fail on:
- GAAP OpEx: MCP aggregate ($1,171M) vs reference ($1,184M) — $13M gap
- Variable Costs: MCP ($234M) vs reference ($247M) — $13M gap
- Cash App vs Commerce split: $10M categorization shift (totals match)
- Business Accounts: Ref $10M vs MCP $4M (product grouping)
- OpEx CY individual lines: ~3x issue (flag, don't fail)

---

## Step 7 — Output Validation Report

Write report to:
```
~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_validation_YYYY_MM.md
```

Format:
```markdown
# MRP Validation Report — [Month Year]

**Date:** YYYY-MM-DD
**Data Packet:** mrp_data_YYYY_MM.json (version X.X)
**Published Doc:** [doc URL]

## Summary
- Total checks: XX
- PASS: XX
- FAIL: XX
- WARN: XX (known discrepancies)

## Headline Metrics
| Check | Expected | Found | Status |
|-------|----------|-------|--------|
| ... | ... | ... | ✅/❌/⚠️ |

## Sub-Product GP
| Product | Expected | Found | Status |
|---------|----------|-------|--------|

## Known Discrepancies
| Issue | Expected | Actual | Notes |
|-------|----------|--------|-------|

## Failures (if any)
[Details on any unexpected mismatches]
```

Print the summary to the console:
```
=== MRP Validation ===
Checks: XX total | XX PASS | XX FAIL | XX WARN
Status: [PASS / FAIL]
Report saved to: [path]
```
