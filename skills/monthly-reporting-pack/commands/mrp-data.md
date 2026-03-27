---
name: mrp-data
description: Fetch all MRP metrics from Block Data MCP and output a structured JSON data packet. Standalone command — run before /mrp to inspect data, or as part of the full pipeline.
allowed-tools:
  - mcp__blockdata__fetch_metric_data
  - mcp__blockdata__get_dimension_values
  - Read
  - Write
metadata:
  author: nmart
  version: "0.1"
  status: development
---

# MRP Data Fetch

Fetch all available MRP metrics from Block Data MCP for a given reporting month.

**Dependencies:**
- Load `~/skills/weekly-reporting/skills/financial-reporting.md` for comparison framework
- Load `~/skills/monthly-reporting/skills/mrp-data-layer.md` for metric registry and product mappings

**Output:** `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json`

---

## Step 1 — Determine Reporting Period

Ask Nick which month to report on, or derive from context. Set:
- `reporting_month` (e.g., `2026-02`)
- `month_start` / `month_end`
- `quarter` and `quarter_start`
- `prior_year_month_start` / `prior_year_month_end`
- `prior_month_start` / `prior_month_end`
- `comparison_scenario` per the financial-reporting recipe:
  - Q1 → `"2026 Annual Plan"` (or `"YYYY Annual Plan"`)
  - Q2 → `"Q2 Outlook"`
  - Q3 → `"Q3 Outlook"`
  - Q4 → `"Q4 Outlook"`

---

## Step 2 — Fetch Current Month Actuals

Run these fetches in parallel where possible. All use `granularity="month"`, `start_date=month_start`, `end_date=month_end`.

### 2a. GP by brand
```
metric: financial__profit_and_loss__pnl_gross_profit_actual
dimensions: ["product_brand"]
```

### 2b. Cash App sub-product GP
```
metric: financial__profit_and_loss__pnl_gross_profit_actual
dimensions: ["product"]
filters: {"product_brand": "Cash App"}
sort_by: [{"financial__profit_and_loss__pnl_gross_profit_actual": "desc"}]
limit: 50
```

### 2c. Square sub-product GP
```
metric: financial__profit_and_loss__pnl_gross_profit_actual
dimensions: ["product"]
filters: {"product_brand": "Square"}
sort_by: [{"financial__profit_and_loss__pnl_gross_profit_actual": "desc"}]
limit: 50
```

### 2d. AOI + AOI Margin
```
metric: financial__profit_and_loss__adjusted_operating_income_actual
metric: financial__profit_and_loss__adjusted_operating_income_margin_actual
```

### 2e. GAAP OpEx
```
metric: financial__profit_and_loss__pnl_total_block_gaap_opex_actual
```

### 2f. Individual OpEx lines
Fetch each of these (all prefixed `financial__profit_and_loss__`):
- `pnl_p2p_opex_actual`
- `pnl_risk_loss_opex_actual`
- `pnl_customer_support_people_opex_actual`
- `pnl_card_issuance_opex_actual`
- `pnl_warehouse_financing_opex_actual`
- `pnl_hardware_logistics_opex_actual`
- `pnl_bad_debt_expense_opex_actual`
- `pnl_customer_reimbursements_opex_actual`
- `pnl_marketing_opex_actual`
- `pnl_sales_marketing_people_opex_actual`
- `pnl_prod_dev_people_opex_actual`
- `pnl_g_a_people_opex_actual`
- `pnl_software_fees_opex_actual`
- `pnl_cloud_fees_opex_actual`
- `pnl_taxes_insurance_other_corp_opex_actual`
- `pnl_legal_fees_opex_actual`
- `pnl_other_professional_services_opex_actual`
- `pnl_rent_facilities_equipment_opex_actual`
- `pnl_travel_entertainment_opex_actual`
- `pnl_hardware_production_costs_opex_actual`
- `pnl_non_cash_expense_excl_sbc_opex_actual`

### 2g. Square GPV
```
metric: financial__square_gpv  (no filter → Global)
metric: financial__square_gpv  filters: {"country_code": "US"} → US GPV
```

### 2h. Cash App Operational
```
metric: financial__cash_app_total_actives
metric: financial__cash_app_total_inflows_usd
```

---

## Step 3 — Fetch Forecast (Annual Plan / Outlook)

Same structure as Step 2 but using `_outlook` metric variants and adding `filters: {"scenario": "<comparison_scenario>"}`.

**Important:** Only P&L metrics from `finstmt_master` have outlook variants. Square GPV and Cash App operational metrics do NOT have forecasts in the metric store — these are data gaps.

Fetch:
- GP by brand (outlook)
- Cash App sub-product GP (outlook)
- Square sub-product GP (outlook)
- AOI (outlook)
- AOI Margin (outlook)
- GAAP OpEx (outlook)
- Individual OpEx lines (outlook — each with `_outlook` suffix)

---

## Step 4 — Fetch Prior Year Actuals

Same as Step 2 but with dates shifted back 12 months. Same metrics, same dimensions.

---

## Step 4b — Fetch PY-1 Headline Actuals

Fetch same-month from 24 months ago (for PY Rule of 40 computation):
```
metric: financial__profit_and_loss__pnl_gross_profit_actual
granularity: month
start_date: [month_start - 24 months]
end_date: [month_end - 24 months]
```
```
metric: financial__profit_and_loss__adjusted_operating_income_actual
granularity: month
start_date: [month_start - 24 months]
end_date: [month_end - 24 months]
```

---

## Step 5 — Fetch Prior Month Actuals

Same as Step 2 but for the month before `reporting_month`. Used for context like "(+28% in January)".

Only fetch the key headline metrics (GP by brand, AOI, Square GPV, Cash App Actives/Inflows) — not all sub-products.

---

## Step 6 — Fetch QTD Actuals

Same as Step 2 but with `start_date=quarter_start`, `end_date=month_end`.

For QTD, fetch:
- Block GP (no brand split needed, just total)
- GP by brand
- AOI + AOI Margin
- GAAP OpEx
- Square GPV (Global + US)
- Cash App Actives, Inflows

---

## Step 7 — Compute Derived Metrics

For each period (current, forecast, prior_year, prior_month, qtd):

1. **Adjusted OpEx** = GP - AOI
2. **Rule of 40** = GP YoY Growth % + AOI Margin % (current month and QTD)
3. **PY GP YoY %** = (prior_year_gp - py1_gp) / |py1_gp| × 100
4. **PY Rule of 40** = PY GP YoY % + PY AOI Margin %
5. **Rule of 40 vs PY pts** = Rule of 40 - PY Rule of 40
6. **Cash App Monetization Rate (ex-Commerce)** = Cash App GAAP GP (non-Commerce products) / Cash App Inflows
7. **Inflows per Active** = Cash App Inflows / Cash App Actives
8. **INTL GPV** = Global GPV - US GPV
9. **Commerce GP** = sum of Commerce products (Core BNPL + SUP-Ads + Commerce Other per mapping in mrp-data-layer.md)
10. **Cash App GAAP GP** = Total Cash App GP - Commerce GP

For comparisons:
- **YoY %** = (actual - prior_year) / |prior_year| × 100
- **vs Plan $** = actual - forecast
- **vs Plan %** = (actual - forecast) / |forecast| × 100
- **Prior Month YoY %** = (prior_month - prior_month_prior_year) / |prior_month_prior_year| × 100

Group sub-products into MRP categories using the product-to-MRP mapping in `mrp-data-layer.md`.

---

## Step 8 — Assemble and Write JSON

Build the data packet following the schema in `mrp-data-layer.md`. Write to:
```
~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json
```

Print a summary table to confirm key values:
```
=== MRP Data Packet Summary ===
Reporting Month: February 2026
Comparison: 2026 Annual Plan

Block GP:       $XXM actual | $XXM AP | +X% YoY | +$XXM vs AP
Cash App GP:    $XXM actual | $XXM AP | +X% YoY | +$XXM vs AP
Square GP:      $XXM actual | $XXM AP | +X% YoY | +$XXM vs AP
AOI:            $XXM actual | $XXM AP | XX% margin
Adjusted OpEx:  $XXM actual (derived: GP - AOI)
Rule of 40:     XX% (XX% growth + XX% margin) | PY: XX% | +XX pts vs PY
Square GPV:     $XX.XB global | $XX.XB US | $XX.XB INTL
CA Actives:     XX.XM
CA Inflows:     $XX.XB | $XXX/active
CA Mon Rate:    X.XX%

Data Gaps: [list of gaps]
```

---

## Step 9 — Spot-Check Validation

If February 2026, cross-check these known values from the MRP example:
- Block GP = ~$922M
- Cash App GP = ~$601M
- Square GP = ~$317M
- AOI = ~$231M
- Cash App Actives = ~56.9M
- Square GPV = ~$19.5B
- US GPV = ~$15.2B

Report PASS/FAIL for each.
