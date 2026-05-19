---
name: mrp-block-overview
description: Generate Block Financial Overview, Gross Profit, and Operating Expenses commentary from the MRP data packet. Produces quantitative text with color-coded gaps.
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

# MRP Block Overview Skill

Generate Sections 1-3 of the MRP commentary:

1. **Block Financial Overview** — Rule of 40, pacing bullets, watchpoints
2. **Gross Profit** — Block GP summary, Cash App GP, Square GP, Variable Profit
3. **Operating Expenses** — GAAP/Adjusted headlines, variable/acquisition/fixed cost bullets

These sections use quantitative metrics from the data packet and qualitative context from Nick or the flux commentary skill.

---

## Input

Data packet JSON at `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json`

---

## Color Convention

| Color | Meaning |
|-------|---------|
| Black | Quantitative from Block Data MCP (governed) |
| `<<BLUE>>` | Nick's judgment or metrics not in MCP (data gap) |
| `<<RED>>` | Data gap — placeholder for missing data or Nick's input |
| Yellow highlight | Table placeholder |

---

## Section 1: Block Financial Overview

### Rule of 40 Paragraph

**Pattern:**
```
Block achieved **Rule of X% (X% growth, X% margin)** in [Month], +X pts above the previous year and +X pts above AP, with growth +X pts and margin +X pts above forecast.
```

**Data sources:**
- `block.rule_of_40.actual` — current month Rule of 40 score
- `block.rule_of_40.vs_py_pts` — vs prior year in pts
- `block.rule_of_40.components` — growth % and margin %
- `block.rule_of_40.py_components` — prior year growth % and margin %

**Color coding:**
- Rule of 40 headline and vs PY: **Black** (from MCP)
- Pacing sentence ("GP expected to land at..."): ALL **BLUE** (Nick's judgment)
- Lending vs non-lending composition: **BLUE** (requires lending GP definition from Nick)

### GP Pacing Bullet

ALL **BLUE** — Nick's judgment on where GP is tracking for the quarter.

### AOI Pacing Bullet

ALL **BLUE** — Nick's judgment on where AOI is tracking for the quarter.

### Watchpoints (3 slots)

ALL **BLUE** — Nick fills manually each month. No flux source.

Placeholders:
```
<<RED>>Nick to fill out — Watchpoint 1<</RED>>
<<RED>>Nick to fill out — Watchpoint 2<</RED>>
<<RED>>Nick to fill out — Watchpoint 3<</RED>>
```

### Reverse Index — Block Financial Overview

| Placeholder | Flux Source |
|-------------|-----------|
| Growth composition context | No direct flux source — synthesize from Cash App + Square GP data |
| GP expected to land at... | No direct flux source — Q1 pacing context from Nick |
| AOI expected to land at... | No direct flux source — Q1 pacing context from Nick |
| Watchpoint 1-3 | No flux source — Nick fills manually each month |

---

## Section 2: Gross Profit

### Block GP Summary

**Pattern:**
```
**Block gross profit** was $[X]M in [Month] (+X% YoY), which was +$[X]M above Annual Plan.
```

**Data sources:**
- `block.gp.actual` — current month GP
- `block.gp.yoy_pct` — year-over-year growth
- `block.gp.vs_plan_dollar` — variance to Annual Plan

**Framing sentence:** Auto-generate by checking which brands beat AP and finding largest sub-product AP beat.

### Cash App GP Bullet

**Pattern:**
```
**Cash App gross profit** was $[X]M (+X% YoY), +$[X]M above Annual Plan.
```

**Data sources:**
- `cash_app.gp` — actual, yoy_pct, vs_plan_dollar

**Sub-metrics:**
- **Actives:** `cash_app.actives` — actual + YoY
- **Inflows per Active:** `cash_app.inflows_per_active` — actual + YoY
- **Monetization Rate:** `cash_app.monetization_rate` — actual + YoY
- vs AP for Actives/IPA/MonRate: **RED** if forecast is null in data packet

### Square GP Bullet

**Pattern:**
```
**Square gross profit** was $[X]M (+X% YoY), +$[X]M above Annual Plan.
```

**Data sources:**
- `square.gp` — actual, yoy_pct, vs_plan_dollar

**GPV sub-metrics:**
- **Global GPV:** `square.global_gpv` — actual + YoY growth
- **US GPV:** `square.us_gpv` — actual + YoY growth + MoM acceleration
- **International GPV:** `square.intl_gpv` — actual + YoY growth + MoM acceleration
- **GPV Acceleration:** `square.gpv_acceleration` — MoM change in growth rate
- vs AP for GPV metrics: **RED** if forecast is null
- Constant currency: **RED** (not in MCP)

### Variable Profit Paragraph

**Data sources:**
- Derived from GP - variable costs

**Color coding:**
- **RED** if variable cost framework not aligned (MCP aggregate vs MRP definition gap)
- Brand-level VP: **RED** (not allocated in MCP)

### Reverse Index — Gross Profit

| Placeholder | Flux Source |
|-------------|-----------|
| Cash App outperformance drivers | Aggregate: top commentary from Cash App GP Summary col N where F="Yes" |
| Square outperformance drivers | Aggregate: Square GP Summary -> Total Payments + SaaS + Banking + Hardware commentary |

---

## Section 3: Operating Expenses

### GAAP OpEx Headline

**Data sources:**
- `block.gaap_opex.actual` — current month GAAP operating expenses

**Color coding:**
- GAAP YoY: **RED** (PY aggregates not reliably available)
- GAAP vs AP: **RED** (AP aggregates not reliably available)

### Adjusted OpEx Headline

**Pattern:**
```
**Adjusted operating expenses** were $[X]M in [Month], +$[X]M above Annual Plan.
```

**Data sources:**
- `block.adjusted_opex.actual` — current month Adjusted OpEx
- `block.adjusted_opex.vs_plan` — variance to Annual Plan

**Color coding:**
- Adjusted OpEx YoY: **RED** (PY not available)
- Severance exclusion note: **BLUE** (Nick's context)

### Variable Cost Bullet

**RED** — CY data quality issue: individual lines sum to 3x aggregate.

Placeholder: `[Flux commentary]` for variable cost drivers.

### Acquisition Cost Bullet

**RED** — same data quality issue as variable costs.

Placeholder: `[Flux commentary]` for acquisition cost drivers.

### Fixed Cost Bullet

**RED** — same data quality issue as variable costs.

Placeholder: `[Flux commentary]` for fixed cost drivers.

### Reverse Index — Operating Expenses

| Placeholder | Flux Source |
|-------------|-----------|
| Adjusted OpEx context | People Summary + Opex Summary -> Fixed Costs commentary |
| Variable cost drivers | Opex Summary -> Cash App + Commerce + Square variable cost rows |
| Acquisition cost drivers | Opex Summary -> Marketing + Onboarding + Partnership rows |
| Fixed cost drivers | Opex Summary -> All Functions Fixed Costs rows |

---

## Formatting Rules (inherited from financial-reporting.md)

- **Dollars:** $XM (no decimal if >= $10M), $X.XM (1 decimal if < $10M), $X.XXB (2 decimals)
- **Percentages:** 1 decimal if < 10%, no decimal if >= 10%
- **Basis points:** integer in body text
- **Metric names:** always **bold**
- **Signs:** always shown (+/-)
- **Comparisons:** "versus AP" not "vs plan"

---

## Output

Markdown text for Sections 1-3 (Block Financial Overview, Gross Profit, Operating Expenses), ready to be assembled into the full MRP file.
