---
name: mrp-commentary-validate
description: Validate MRP commentary markdown against the data packet before publishing. Checks every number traces to a data source, color coding is correct, and formatting complies with standards.
depends-on:
  - financial-reporting
  - mrp-data-layer
allowed-tools:
  - Read
metadata:
  author: nmart
  version: "1.0"
  status: active
---

# MRP Commentary Validator

Pre-publish validation that checks the generated MRP markdown against the data packet before it goes to Google Docs.

## Inputs
- MRP commentary markdown: `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_YYYY_MM.md`
- Data packet: `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json`

## Validation Checks

### 1. Quantitative Accuracy
For every number in black text, verify it traces to a data packet field:
- Block GP actual, YoY%, vs AP$ -> block.gp
- Cash App GP actual, YoY%, vs AP$ -> cash_app.gp
- Square GP actual, YoY%, vs AP$ -> square.gp
- AOI actual -> block.aoi
- Rule of 40 %, growth/margin components, vs PY pts -> block.rule_of_40
- Adjusted OpEx actual, vs AP -> block.adjusted_opex
- GAAP OpEx actual -> block.gaap_opex
- Actives, YoY% -> cash_app.actives
- Inflows/Active, YoY% -> cash_app.inflows_per_active
- Monetization Rate, YoY bps -> cash_app.monetization_rate
- GPV (Global/US/INTL), YoY%, acceleration pts -> square.global_gpv, us_gpv, intl_gpv, gpv_acceleration
- Sub-product drivers: YoY%, vs AP$ -> cash_app.sub_products.*, square.sub_products.*

Tolerance: $1M for dollar amounts, 0.5 pts for percentages/bps

### 2. Color Coding Correctness
- Black text: must correspond to a populated data packet field OR a flux commentary source
- «BLUE» text: must be genuinely judgment-dependent (pacing, guidance, consensus, watchpoints, Proto deal, Cash Actives drivers, severance context)
- «RED» text: must correspond to a data gap listed in the data packet's `gaps` array OR a metric where the data packet field is null
- No black text should contain stale values from a prior month's template
- «WARN» / yellow: only for [TABLE] placeholders

### 3. Formatting Compliance (per financial-reporting.md)
- All metric names are **bold** (Rule of 40, Block gross profit, Cash App gross profit, Actives, Inflows per active, Monetization rate, Square gross profit, Global GPV, US GPV, International GPV, Variable profit, GAAP operating expenses, Adjusted operating expenses, Variable costs, Acquisition costs, Fixed costs, etc.)
- Dollar rounding: >=10M -> no decimal ($922M), <$10M -> 1 decimal ($5.8M), billions -> 2 decimals ($1.05B)
- Percentage rounding: >=10% -> no decimal (+28%), <10% -> 1 decimal (+5.2%)
- bps: integer in body text (+32 bps)
- Actives: 1 decimal (56.9M)
- Signs always present (+/-) on variances and YoY
- "versus AP" not "vs plan"

### 4. Structural Completeness
- All expected sections present: Block Financial Overview, Watchpoints, Gross Profit, Operating Expenses, Block P&L, People by Function, Brand P&L Metrics, Topline Trends (Cash App, Square, Other Brands), Appendix I, Appendix II
- Heading hierarchy correct: H1 for Block Financial Overview / Topline Trends / Appendix, H2 for sub-sections
- Table placeholders have «WARN» markers
- Footnotes present where expected

### 5. Flux Commentary References
- All [Flux: ...] markers reference valid tab names (Cash App GP Summary, Square GP Summary, Other Brands GP Summary, Opex Summary, Personnel Summary, People Summary)
- Row numbers are within valid ranges per tab
- Column N is correctly referenced

## Output

Print validation report:
```
=== MRP Commentary Validation ===
Total checks: XX
PASS: XX
FAIL: XX
WARN: XX

Failures:
- [description of each failure]

Warnings:
- [description of each warning]
```
