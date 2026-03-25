---
name: workflow-registry
description: Registry of all financial reporting workflows — maps data sources, outputs, shared metrics, and data lineage. Foundation for cross-workflow auditing.
depends-on: []
allowed-tools: []
metadata:
  author: nmart
  version: "1.0.0"
  status: active
---

# Workflow Registry

This file is the single source of truth for what workflows exist, what they read, what they produce, and which metrics they share. Every audit check references this registry.

---

## Workflow Inventory

### 1. Weekly Summary (`/weekly-summary`)

| Field | Value |
|-------|-------|
| Command | `~/.claude/commands/weekly-summary.md` |
| Skills | `~/skills/weekly-reporting/skills/financial-reporting.md`, `~/skills/weekly-reporting/skills/weekly-tables.md`, `~/skills/weekly-reporting/skills/weekly-validate.md` |
| Cadence | Weekly (every Monday/Tuesday) |
| Status | Active, v2.0 |

**Data Sources:**

| Source | ID / Path | What It Provides |
|--------|-----------|-----------------|
| Master Pacing Sheet | `1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4` (tab: `summary`) | All metric values — GP, GPV, inflows, AOI, Rule of 40 |
| Slack Group DM | Channel `C07LV8RS05A` | Cash App digest (mjansing), Square update (jerbe) |

**Output Artifacts:**

| Artifact | Path / ID |
|----------|-----------|
| Markdown | `~/Desktop/Nick's Cursor/Weekly Reporting/weekly_summary_YYYY-MM-DD.md` |
| Google Doc | `1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0` (dated child tab under quarter parent) |
| Validation Report | `~/Desktop/Nick's Cursor/Weekly Reporting/validation_YYYY-MM-DD.md` |

**Validator:** `~/skills/weekly-reporting/skills/weekly-validate.md` — cell-by-cell table comparison (5 tables, ~299 cells)

**Step Count:** 8 steps (auth → read sheet → search Slack → generate → save → publish + tables → validate → report + Slack)

---

### 2. Pacing Dashboard (`/dashboard-refresh`)

| Field | Value |
|-------|-------|
| Command | `~/.claude/commands/dashboard-refresh.md` |
| Skills | `~/skills/pacing-dashboard/skills/dashboard-refresh.md`, `~/skills/weekly-reporting/skills/financial-reporting.md` |
| Cadence | Weekly (same cycle as weekly summary) |
| Status | Active, v1.0 |

**Data Sources:**

| Source | ID / Path | What It Provides |
|--------|-----------|-----------------|
| Master Pacing Sheet | `1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4` (tab: `summary`) | Q1 pacing, AP, guidance, consensus, vs Tues delta |
| Innercore Doc | `1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0` | Commentary takeaways for dashboard |
| Corporate Model | `1OyVIvezXnvLgoPJUWTCpLqJoOfP3na6YG3awUtdyE5M` | Q2-Q4 forecast data |
| Consensus Model | `1CKtWmWd8buOeHfZnUivOGGGvONoy7WQM03DBzUe8WwQ` | Consensus estimates |

**Output Artifacts:**

| Artifact | Path / ID |
|----------|-----------|
| Dashboard Data | `~/Desktop/Nick's Cursor/Pacing Dashboard/dashboard_data.js` |
| Block Cell Site | `nmart-pacing-dashboard` (https://blockcell.sqprod.co/sites/nmart-pacing-dashboard/index.html) |

**Validator:** `validate.py` in Pacing Dashboard directory — cross-checks Q2-Q4 forecasts against Snowflake (EPM/Hyperion)

**Step Count:** 13 steps (auth → read sheet → scan sections → column ref → extract → format → derive → commentary → write JS → sync index → validate → deploy → notify)

---

### 3. Monthly Flash (`/monthly-flash`)

| Field | Value |
|-------|-------|
| Command | `~/.claude/commands/monthly-flash.md` (also `~/skills/monthly-flash/commands/monthly-flash.md`) |
| Skills | `~/skills/weekly-reporting/skills/financial-reporting.md` |
| Cadence | Monthly (after month-end close) |
| Status | Active, v1.1 |

**Data Sources:**

| Source | ID / Path | What It Provides |
|--------|-----------|-----------------|
| MRP Charts & Tables | `15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0` (tab: `MRP Charts & Tables`, range: `L11:Y90`) | Actuals, vs AP, YoY, Jan YoY for all metrics |

**Output Artifacts:**

| Artifact | Path / ID |
|----------|-----------|
| Markdown | `~/Desktop/Nick's Cursor/Monthly Reporting/monthly_flash_YYYY_MM.md` |
| Google Doc | `1S--3vA6obl4hBF2Nw2jqD1M4sjEkD8FcpC073-OlAUY` (tab: `t.mkykw9vq4coc`) |
| Validation Report | `~/Desktop/Nick's Cursor/Monthly Reporting/validation_YYYY_MM.md` |

**Validator:** `~/skills/monthly-flash/commands/monthly-validate.md` — narrative metric extraction + comparison (~106 values)

**Step Count:** 7 steps (auth → read sheet → generate → save → publish (5 sub-steps) → validate → report)

---

## Shared Metric Map

Metrics that appear in 2+ workflows. When the auditor runs V1 (cross-workflow consistency), it compares these values across workflows for the same period.

### Quarterly Pacing Metrics (Q1 scope)

| Metric | Weekly Summary | Dashboard | Monthly Flash |
|--------|---------------|-----------|---------------|
| Block GP | Pacing Sheet col 17 (Q1 Pacing) | Pacing Sheet col 17 | MRP Charts row 10, col 1 (Actual) |
| Cash App GP | Pacing Sheet col 17 | Pacing Sheet col 17 | MRP Charts row 11, col 1 |
| Square GP | Pacing Sheet col 17 | Pacing Sheet col 17 | MRP Charts row 17, col 1 |
| TIDAL GP | Pacing Sheet col 17 | -- | MRP Charts row 23, col 1 |
| Proto GP | Pacing Sheet col 17 | -- | MRP Charts row 24, col 1 |
| AOI | Pacing Sheet col 17 | Pacing Sheet col 17 | MRP Charts row 26, col 1 |
| Rule of 40 | Pacing Sheet (section 1b) | Pacing Sheet (section 1b) | MRP Charts row 27, col 1 |
| Global GPV | Pacing Sheet col 17 | Pacing Sheet col 17 | MRP Charts row 5, col 1 |
| US GPV | Pacing Sheet col 17 | Pacing Sheet col 17 | MRP Charts row 6, col 1 |
| INTL GPV | Pacing Sheet col 17 | Pacing Sheet col 17 | MRP Charts row 7, col 1 |
| Cash App Actives | Pacing Sheet col 17 | Pacing Sheet col 17 | MRP Charts row 2, col 1 |
| Inflows per Active | Pacing Sheet col 17 | Pacing Sheet col 17 | MRP Charts row 3, col 1 |
| Monetization Rate | Pacing Sheet (section 2) | Pacing Sheet (section 2) | MRP Charts row 35, col 1 |

### Cross-Workflow Consistency Notes

- **Weekly + Dashboard** share the same source (pacing sheet, same columns) → values should be identical
- **Monthly Flash** uses a different source (MRP Charts & Tables) → values may differ by timing (pacing = forward-looking, flash = actuals after close)
- Cross-workflow comparison is most meaningful when comparing the **same reporting period** (e.g., Q1 actuals in monthly flash vs Q1 final pacing in weekly summary)

---

## Data Source Lineage

| System of Record | Google Sheet | Consumers |
|-----------------|-------------|-----------|
| FP&A Pacing Model | `1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4` | Weekly Summary, Dashboard |
| MRP Charts & Tables (EPM/Hyperion) | `15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0` | Monthly Flash |
| Corporate Model | `1OyVIvezXnvLgoPJUWTCpLqJoOfP3na6YG3awUtdyE5M` | Dashboard (Q2-Q4 forecasts) |
| Consensus Model | `1CKtWmWd8buOeHfZnUivOGGGvONoy7WQM03DBzUe8WwQ` | Dashboard (consensus estimates) |
| Innercore Weekly Digest | `1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0` | Dashboard (commentary) |
| Slack Group DM | Channel `C07LV8RS05A` | Weekly Summary (Cash App + Square context) |

---

## Formatting Standards

All workflows inherit from `~/skills/weekly-reporting/skills/financial-reporting.md` (v1.1.0):

| Rule | Standard |
|------|----------|
| $B format | 2 decimals ($2.90B) |
| $M format (>=10M) | No decimal ($940M) |
| $M format (<10M) | 1 decimal ($4.2M) |
| % format (>=10%) | No decimal (27%) |
| % format (<10%) | 1 decimal (7.0%) |
| Basis points | Space before (30 bps) |
| Actives | 1 decimal (58.5M) |
| Signs | Always +/- on deltas and YoY |
| Comparison point | Q1→AP, Q2→Q2OL, Q3→Q3OL, Q4→Q4OL |

---

## Validator Tolerance Comparison

| Tolerance | Weekly Validate | Monthly Validate | Dashboard Validate |
|-----------|----------------|-----------------|-------------------|
| % (no decimal) | ±0.5 pp | ±0.5 pp | N/A (Python script) |
| % (1 decimal) | ±0.05 pp | ±0.05 pp | N/A |
| $B (2 decimals) | ±$5M | ±$5M | N/A |
| $M (no decimal) | ±$0.5M | ±$0.5M | N/A |
| $M (1 decimal) | N/A | ±$0.05M | N/A |
| Basis points | ±0.5 bps | N/A | N/A |
| Points | N/A | ±0.5 pts | N/A |

---

## Extension: Adding New Workflows

When MRP or board doc workflows are established:

1. Add a new section under **Workflow Inventory** with the same structure
2. Add shared metrics to the **Shared Metric Map** table
3. Add data sources to the **Data Source Lineage** table
4. Add validator tolerances to the **Validator Tolerance Comparison** table
5. The audit engine automatically picks up the new workflow via the registry
