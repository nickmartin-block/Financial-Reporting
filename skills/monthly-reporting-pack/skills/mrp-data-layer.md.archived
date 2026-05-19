---
name: mrp-data-layer
description: Fetch, compute, and structure all quantitative metrics for the Monthly Management Reporting Pack from Block Data MCP. Produces a JSON data packet consumed by narrative and table generators.
depends-on:
  - financial-reporting
allowed-tools:
  - mcp__blockdata__fetch_metric_data
  - mcp__blockdata__get_metric_details
  - mcp__blockdata__get_dimension_values
  - Read
  - Write
metadata:
  author: nmart
  version: "0.1"
  status: development
---

# MRP Data Layer

Fetch all MRP metrics from Block Data MCP for a given reporting month. Outputs a structured JSON data packet to `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json`.

**Dependencies:** Load `~/skills/weekly-reporting/skills/financial-reporting.md` for comparison framework (which forecast scenario to use per quarter).

---

## Configuration

The data layer requires a **reporting month** (e.g., `2026-02`). From this it derives:

| Parameter | Derivation |
|-----------|-----------|
| `reporting_month` | User-specified (YYYY-MM) |
| `month_start` | First day of month (YYYY-MM-01) |
| `month_end` | Last day of month |
| `quarter` | Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec) |
| `quarter_start` | First day of quarter |
| `prior_year_month_start` | Same month, prior year |
| `prior_year_month_end` | Last day of same month, prior year |
| `prior_month_start` | First day of prior month |
| `prior_month_end` | Last day of prior month |
| `comparison_scenario` | Per financial-reporting recipe: Q1→"2026 Annual Plan", Q2→"Q2 Outlook", Q3→"Q3 Outlook", Q4→"Q4 Outlook" |

**Note on scenario naming:** The metric store uses full names like `"2026 Annual Plan"` and `"Q4 Outlook"`, not shorthand like `AP` or `Q4OL`.

---

## Metric Registry

### Source 1: P&L Metrics (from `finstmt_master` via EPM/Hyperion)

All P&L metrics support dimensions: `product_brand`, `product`, `scenario`, `metric_time` (month/quarter/year granularity).

**Brand-level GP** — fetch with `dimensions=["product_brand"]`:

| Metric | Actual | Outlook |
|--------|--------|---------|
| Gross Profit | `financial__profit_and_loss__pnl_gross_profit_actual` | `financial__profit_and_loss__pnl_gross_profit_outlook` |

`product_brand` values: `Cash App`, `Square`, `All Other Brands`, `Intersegment`
- Block total = no `product_brand` filter (sums all)
- `Intersegment` = $0 (elimination)
- `All Other Brands` = TIDAL + Proto + Bitkey combined

**Sub-product GP** — fetch with `dimensions=["product"]` and `filters={"product_brand": "<brand>"}`:

Cash App product-to-MRP mapping:
| MRP Category | Products (codes) |
|-------------|-----------------|
| Core Cash App | 1310-Cash App Processing |
| ATM | 3044-Cash App ATM Fees |
| Bitcoin Buy/Sell | 3041-Cash App Bitcoin |
| Bitcoin Withdrawal Fees | 3049-Cash App Bitcoin Withdrawal Fee |
| Business Accounts | 1341-Cash for Business Instant Settlement |
| Cash App Card | 3040-Cash Banking Services |
| Instant Deposit | 1340-Cash App Instant Settlement |
| Interest Income | 3046-Cash App Balance Interest |
| Paper Money Deposits | 3050-Paper Money Deposits |
| Borrow | 3047-Cash App Borrow |
| Post-Purchase BNPL | 3073-Pay Monthly |
| Cash App Pay | 1312-Cash App Pay |
| Cash Retro | 3055-Cash Retro |
| Cash App Other | 1311-Cash App Credit Cards, 3045-Cash Card Studio, 3052-Paid in BTC, 3054-Round up BTC, 3057-Cash Gift Card |
| Core BNPL (Commerce) | 3070-Core Buy Now Pay Later |
| SUP-Ads (Commerce) | 3075-Afterpay SUP Ads |
| Commerce Other | 3077-Afterpay Giftcards, 3071-Touch Pay Now, 3074-Plus Card, 3059-Pre-purchase BNPL, 3072-Afterpay Whole Loan Sales |

Cash App GAAP GP = sum of all non-Commerce products above
Commerce GP = Core BNPL + SUP-Ads + Commerce Other
Total Cash App GP = Cash App GAAP GP + Commerce GP

Square product-to-MRP mapping:
| MRP Category | Products (codes) |
|-------------|-----------------|
| Processing (US + INTL combined) | 1010-Processing, 1011-Pay With ACH |
| Banking | 3010-Square Capital, 1330-Instant Settlement, 3042-Square Card, 3013-Square Credit Card, 3011-Savings, 3014-Deposit Sweeps, 3017-Square Bitcoin |
| SaaS | 4079-Square One, 4030-Payroll, 4087-Square Online Store, 4085-Weebly, 4110-Retail POS, 4120-Restaurants POS, 4010-Appointments, 4061-Marketing, 4050-Team Management, 4062-Loyalty, 5050-Gift Cards, 4051-Shifts, 4020-Invoicing, 4031-HR Manager, 4052-Staff, 4055-Team Communication, 4060-CRM, 4063-Franchise Suites, 4070-Developers, 4071-Marketplaces, 4080-Premium Support, 4011-Square Messages, 4086-Weebly Domains, 4088-Square Online Store Domains, 4089-Square Online Store Delivery, 4121-RST KDS, 5020-Professional Services |
| Hardware | 2070-X2, 2120-T3, 2010-Peripherals, 2110-T2, 2030-Stand, 2060-R12, 2040-R6, 2100-A11, 2080-Hardware Installment, 2090-Hardware Bundle (INACTIVE), 2140-Kiosk, 2200-Wallet - W1 Hardware, 2210-Mining - MC1 ASIC |

**Note:** Processing GP cannot be split into US vs INTL from `finstmt_master`. The combined figure is available; the geographic split is a DATA GAP.

**Block-level profitability** — fetch with no dimension filters:

| Metric | Actual | Outlook |
|--------|--------|---------|
| Adjusted Operating Income | `financial__profit_and_loss__adjusted_operating_income_actual` | `financial__profit_and_loss__adjusted_operating_income_outlook` |
| AOI Margin | `financial__profit_and_loss__adjusted_operating_income_margin_actual` | `financial__profit_and_loss__adjusted_operating_income_margin_outlook` |
| GAAP OpEx | `financial__profit_and_loss__pnl_total_block_gaap_opex_actual` | `financial__profit_and_loss__pnl_total_block_gaap_opex_outlook` |

**Derived: Adjusted OpEx** = Gross Profit - Adjusted Operating Income

**Individual OpEx lines** (for Appendix I double-click view) — fetch each with no dimension filters:

| MRP Line | Actual Metric | Outlook Metric |
|----------|--------------|----------------|
| P2P | `pnl_p2p_opex_actual` | `pnl_p2p_opex_outlook` |
| Risk Loss | `pnl_risk_loss_opex_actual` | `pnl_risk_loss_opex_outlook` |
| Customer Support People | `pnl_customer_support_people_opex_actual` | `pnl_customer_support_people_opex_outlook` |
| Card Issuance | `pnl_card_issuance_opex_actual` | `pnl_card_issuance_opex_outlook` |
| Warehouse Financing | `pnl_warehouse_financing_opex_actual` | `pnl_warehouse_financing_opex_outlook` |
| Hardware Logistics | `pnl_hardware_logistics_opex_actual` | `pnl_hardware_logistics_opex_outlook` |
| Bad Debt Expense | `pnl_bad_debt_expense_opex_actual` | `pnl_bad_debt_expense_opex_outlook` |
| Customer Reimbursements | `pnl_customer_reimbursements_opex_actual` | `pnl_customer_reimbursements_opex_outlook` |
| Marketing (Non-People) | `pnl_marketing_opex_actual` | `pnl_marketing_opex_outlook` |
| Sales & Marketing People | `pnl_sales_marketing_people_opex_actual` | `pnl_sales_marketing_people_opex_outlook` |
| Product Development People | `pnl_prod_dev_people_opex_actual` | `pnl_prod_dev_people_opex_outlook` |
| G&A People | `pnl_g_a_people_opex_actual` | `pnl_g_a_people_opex_outlook` |
| Software | `pnl_software_fees_opex_actual` | `pnl_software_fees_opex_outlook` |
| Cloud Fees | `pnl_cloud_fees_opex_actual` | `pnl_cloud_fees_opex_outlook` |
| Taxes, Insurance & Other | `pnl_taxes_insurance_other_corp_opex_actual` | `pnl_taxes_insurance_other_corp_opex_outlook` |
| Legal Fees | `pnl_legal_fees_opex_actual` | `pnl_legal_fees_opex_outlook` |
| Other Professional Services | `pnl_other_professional_services_opex_actual` | `pnl_other_professional_services_opex_outlook` |
| Rent, Facilities, Equipment | `pnl_rent_facilities_equipment_opex_actual` | `pnl_rent_facilities_equipment_opex_outlook` |
| Travel & Entertainment | `pnl_travel_entertainment_opex_actual` | `pnl_travel_entertainment_opex_outlook` |
| Hardware Production Costs | `pnl_hardware_production_costs_opex_actual` | `pnl_hardware_production_costs_opex_outlook` |
| Non-Cash (ex. SBC) | `pnl_non_cash_expense_excl_sbc_opex_actual` | `pnl_non_cash_expense_excl_sbc_opex_outlook` |

All OpEx metric names are prefixed with `financial__profit_and_loss__`.

### Source 2: Square Volume Metrics (from Hexagon)

| Metric | Name | Dimensions |
|--------|------|-----------|
| Global GPV | `financial__square_gpv` | `country_code` for US/INTL |
| Square GP | `financial__square_gross_profit` | — |

US GPV = filter `country_code = "US"`
INTL GPV = Global GPV - US GPV

### Source 3: Cash App Metrics (from FMM)

| Metric | Name |
|--------|------|
| Total Actives | `financial__cash_app_total_actives` |
| Total Inflows | `financial__cash_app_total_inflows_usd` |
| Inflow Actives | `financial__cash_app_inflow_actives` |

### Derived Metrics

| Metric | Formula |
|--------|---------|
| Adjusted OpEx | GP_actual - AOI_actual |
| Rule of 40 | GP_yoy_growth_pct + AOI_margin_pct |
| Cash App Monetization Rate (ex-Commerce) | Cash App GAAP GP (ex-Commerce) / Cash App Total Inflows |
| Inflows per Active | Total Inflows / Total Actives |
| INTL GPV | Global GPV - US GPV |

### Data Gaps (render as red placeholders)

These metrics are NOT in the Block Data MCP. Render as `«RED»[DATA GAP: metric_name]«/RED»`:

- Guidance GP, Guidance AOI
- Consensus GP, Consensus AOI
- Headcount (all functions)
- Commerce GMV
- Borrow originations, Borrow drawdown actives
- Cash App Card actives, spend per active, transactions per active
- Square NVA (total, self-onboard, sales)
- Square NVR, SSG
- US vs INTL Processing GP split (only combined Processing available)

---

## Fetch Procedure

For each reporting month, execute these fetches:

### Step 1 — Current Month Actuals

1. **Block GP by brand:** `pnl_gross_profit_actual`, granularity=month, dimensions=["product_brand"]
2. **Cash App sub-product GP:** `pnl_gross_profit_actual`, granularity=month, dimensions=["product"], filters={"product_brand": "Cash App"}
3. **Square sub-product GP:** `pnl_gross_profit_actual`, granularity=month, dimensions=["product"], filters={"product_brand": "Square"}
4. **Other Brands GP:** already in step 1 as "All Other Brands"
5. **AOI:** `adjusted_operating_income_actual`, granularity=month
6. **AOI Margin:** `adjusted_operating_income_margin_actual`, granularity=month
7. **GAAP OpEx:** `pnl_total_block_gaap_opex_actual`, granularity=month
8. **Individual OpEx lines:** each line from the table above, granularity=month
9. **Square GPV (Global):** `financial__square_gpv`, granularity=month
10. **Square GPV (US):** `financial__square_gpv`, granularity=month, filters={"country_code": "US"}
11. **Cash App Actives:** `financial__cash_app_total_actives`, granularity=month
12. **Cash App Inflows:** `financial__cash_app_total_inflows_usd`, granularity=month

### Step 2 — Forecast (Annual Plan or Outlook)

Same metrics as Step 1 but using `_outlook` variants with `filters={"scenario": "<comparison_scenario>"}`.

Note: Square GPV and Cash App operational metrics do NOT have outlook variants in the metric store. These are DATA GAPs for forecast comparison on volume metrics.

### Step 3 — Prior Year Actuals

Same as Step 1 but with date range shifted back 12 months. Used for YoY computation.

### Step 4b — Fetch PY-1 Headline Actuals (for PY comparisons)

Fetch the same-month data from TWO years ago (month - 24 months). Only needed for headline metrics:
- Block GP: `financial__profit_and_loss__pnl_gross_profit_actual`, granularity=month, start/end = month -24 months
- Block AOI: `financial__profit_and_loss__adjusted_operating_income_actual`, same dates

Purpose: PY GP growth = (PY GP - PY1 GP) / |PY1 GP|, used to compute PY Rule of 40.

### Step 4c — Prior Month Actuals

Same as Step 1 but for the prior month. Used for context lines like "(+28% in January)".

### Step 5 — QTD Actuals

Same as Step 1 but with date range from quarter start to month end. For quarterly pacing figures.

### Step 6 — Compute Derived Metrics

For each period (current, forecast, prior year, prior month, QTD):
- Adjusted OpEx = GP - AOI
- Rule of 40 = GP YoY Growth % + AOI Margin %
- PY Rule of 40 = PY GP YoY Growth % + PY AOI Margin %
  - PY GP YoY% = (prior_year_gp - py1_gp) / |py1_gp| × 100
  - PY AOI Margin = prior_year aoi_margin
- Rule of 40 vs PY = current Rule of 40 - PY Rule of 40
- Monetization Rate (ex-Commerce) = Cash App GAAP GP / Inflows
- Inflows per Active = Inflows / Actives
- INTL GPV = Global GPV - US GPV
- YoY % = (current - prior_year) / |prior_year|
- vs Plan $ = current - forecast
- vs Plan % = (current - forecast) / |forecast|

### Step 7 — Assemble Data Packet

Write JSON to `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_data_YYYY_MM.json`.

Schema:
```json
{
  "meta": {
    "reporting_month": "YYYY-MM",
    "quarter": "QX",
    "comparison_scenario": "YYYY Annual Plan",
    "generated_at": "ISO timestamp"
  },
  "block": {
    "gp": { "actual": N, "forecast": N, "prior_year": N, "prior_month": N, "qtd": N, "yoy_pct": N, "vs_plan_dollar": N, "vs_plan_pct": N },
    "aoi": { ... },
    "aoi_margin": { ... },
    "adjusted_opex": { ... },
    "gaap_opex": { ... },
    "rule_of_40": {
      "actual": 52.9,
      "prior_year": 24.1,
      "vs_py_pts": 28.8,
      "components": {
        "gp_growth_pct": 27.8,
        "aoi_margin_pct": 25.1
      },
      "py_components": {
        "gp_growth_pct": 4.6,
        "aoi_margin_pct": 19.5
      }
    }
  },
  "cash_app": {
    "gp": { ... },
    "gaap_gp": { ... },
    "commerce_gp": { ... },
    "actives": { ... },
    "inflows": { ... },
    "inflows_per_active": { ... },
    "monetization_rate": { ... },
    "sub_products": {
      "borrow": { ... },
      "card": { ... },
      "instant_deposit": { ... },
      "core_bnpl": { ... },
      ...
    }
  },
  "square": {
    "gp": { ... },
    "global_gpv": { ... },
    "us_gpv": { ... },
    "intl_gpv": { ... },
    "sub_products": {
      "processing": { ... },
      "banking": { ... },
      "saas": { ... },
      "hardware": { ... }
    }
  },
  "other_brands": {
    "gp": { ... }
  },
  "opex": {
    "p2p": { ... },
    "risk_loss": { ... },
    "cs_people": { ... },
    ...
  },
  "gaps": [
    "guidance_gp", "consensus_gp", "guidance_aoi", "consensus_aoi",
    "headcount", "commerce_gmv", "borrow_originations", "borrow_drawdown_actives",
    "cashapp_card_actives", "cashapp_card_spend_per_active", "cashapp_card_txns_per_active",
    "square_nva", "square_nvr", "square_ssg", "us_intl_processing_split"
  ]
}
```

Each metric object follows the pattern:
```json
{
  "actual": 921890157.83,
  "forecast": 884195840.80,
  "prior_year": 721408009.22,
  "prior_month": null,
  "qtd": null,
  "yoy_pct": 27.8,
  "vs_plan_dollar": 37694317.03,
  "vs_plan_pct": 4.3,
  "prior_month_yoy_pct": null
}
```

Null values indicate "not yet fetched" or "not applicable". The narrative generator handles nulls by omitting the comparison.
