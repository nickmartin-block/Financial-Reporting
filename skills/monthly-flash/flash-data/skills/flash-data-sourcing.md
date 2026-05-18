# Flash-Data Sourcing Reference

Source-of-truth mapping for every value in the Flash table (`L400:S427`) and the Standardized P&L (`L432:R468`). Each row identifies the data source (BDM metric or Snowflake query), the filter convention, and any derivation logic.

**Key principle:** No hardcoded values, no manual sheet edits, no MRP Charts & Tables dependency. Every value comes from a query you can re-run.

---

## Period anchors

For a report month `YYYY-MM`:

| Anchor | Definition |
|---|---|
| `actual` | Report month, scenario=Actual |
| `ol` | Report month, scenario=current Outlook (Q1→AP — Annual Plan, no Q1OL; Q2→Q2OL, Q3→Q3OL, Q4→Q4OL) |
| `ap` | Report month, scenario=`{Year} Annual Plan` |
| `yoy_prior` | Same month, prior year (e.g. Apr'26 → Apr'25), scenario=Actual |
| `prior_month_actual` | One month back from report month (e.g. Apr'26 → Mar'26), scenario=Actual |
| `prior_month_yoy_prior` | One month back, prior year (e.g. Apr'26 → Mar'25), scenario=Actual |
| `yoy_prior_prior` / `prior_month_yoy_prior_prior` | Two months back's YoY anchor — only needed for Block GP to compute prior-period Rule of 40 |

---

## Flash table — Range `L400:S427`

### Operational metrics

| Output row | Source | Filter |
|---|---|---|
| Cash App Actives | Snowflake `app_finance_cash.fands.business_metrics_actuals_outlooks` | `METRIC_DESC='TOTAL ENDING ACTIVES'`, LOB='Network', VERSION ∈ {Actual, Q2 Outlook, Annual Plan 2026, …}. MONTH is end-of-month (use `LAST_DAY(period)`) |
| Cash App Inflows USD (raw — for derivation) | Same table | `METRIC_DESC='TOTAL INFLOWS'`, same filters |
| Cash App Inflows per Active (output) | **DERIVED** | `Inflows USD / Total Actives` for each period |
| Commerce GMV Actual + historicals | Snowflake `AP_CUR_BI_G.CURATED_ANALYTICS_GREEN.CUR_C_M_ORDER_MASTER` | Sum `ORDER_AMOUNT_USD` across all `PRODUCT_DETAIL` by `ORDER_DATE` (full month) |
| Commerce GMV OL + AP | Snowflake `app_hexagon.block.operational_metrics_forecast` | `BUSINESS_UNIT='Commerce'`, `METRIC_NAME='GPV'`, `CURRENCY_CODE='USD'`, `REPORT_PERIOD='Monthly'`, `PRODUCT <> '1312-Cash App Pay'`, sum across products |
| Square GPV (total) | **DERIVED** | `Square US GPV + Square INTL GPV` |
| Square US GPV Actual + historicals | BDM `financial__square_gpv` | filter `country_region='US'` |
| Square US GPV OL + AP | Snowflake `app_bi.square_fns.vcompany_goals` | `METRIC_NAME='GPV'`, `TYPE='gpv by size and cohort'`, `ATTRIBUTE_1='ALL'`, `ATTRIBUTE_2='ALL'`, `COUNTRY_CODE='US'`, scenario ∈ {2026 Q2 OL, 2026 AP}. REPORT_DATE is end-of-month |
| Square INTL GPV Actual + historicals | BDM `financial__square_gpv` | filter `country_region='International'` |
| Square INTL GPV OL + AP | Same Snowflake table | sum METRIC_VALUE where `COUNTRY_CODE <> 'US'` (METRIC_VALUE is USD-converted) |
| Square INTL GPV (CC) | **GAP — not in v1** | constant-currency series not yet sourced; leave blank |

### Gross Profit rows

| Output row | Source | Filter / notes |
|---|---|---|
| Block GP | BDM `financial__profit_and_loss__pnl_gross_profit_actual` / `_outlook` | scenario filter for OL / AP |
| Cash App GP | BDM `financial__profit_and_loss__cash_app_pnl_total_gp_actual` | Outlooks via `pnl_gross_profit_outlook` filtered to `parent_segment='CashApp_BU'` (sum) |
| Commerce GP | BDM `financial__profit_and_loss__afterpay_pnl_total_gp_actual` | Outlooks via `pnl_gross_profit_outlook` filtered to `parent_segment='Marketplace_BU'` minus product `1312-Cash App Pay` |
| Borrow GP | BDM `financial__profit_and_loss__cash_app_pnl_borrow_gp_actual` | Outlooks via `pnl_gross_profit_outlook` `product=3047` |
| Cash App Card GP | BDM `financial__profit_and_loss__cash_app_pnl_card_gp_actual` | Outlooks via `pnl_gross_profit_outlook` `product=3040` |
| Instant Deposit GP | BDM `financial__profit_and_loss__cash_app_pnl_instant_deposit_gp_actual` | Outlooks via `pnl_gross_profit_outlook` `product=1340` |
| Post-Purchase BNPL GP | BDM `financial__profit_and_loss__cash_app_pnl_retro_gp_actual` | Outlooks via `pnl_gross_profit_outlook` `product=3055` |
| Square GP | BDM `financial__profit_and_loss__square_pnl_total_gp_actual` | Outlooks via `pnl_gross_profit_outlook` `parent_segment='Square_BU'` (sum) |
| **US Payments GP** | **Hyperion direct** `app_hexagon.schedule2.finstmt_master` | `entity='101-Block, Inc.'`, `product='1010-Processing'`, `account='Gross Profit (NonGAAP)'`. **Important:** NOT the BDM `square_pnl_processing_gp_actual` metric — that sums 1010+1011+1020+1030+1510 and disagrees with Flash convention by ~$17M |
| INTL Payments GP | BDM `financial__profit_and_loss__square_pnl_processing_gp_actual` filter entity ≠ 101 (sum non-US entities) | Outlooks via `pnl_gross_profit_outlook` `product=1010` non-101 |
| Banking GP | BDM `financial__profit_and_loss__square_pnl_banking_gp_actual + ..._capital_gp_actual` | Outlooks via product sum (1330, 3011, 3013, 3014, 3017, 3042, 3010) |
| SaaS GP | BDM `financial__profit_and_loss__square_pnl_saas_gp_actual` | All 4xxx products |
| Hardware GP | BDM `financial__profit_and_loss__square_pnl_hardware_gp_actual` | All 2xxx products |
| TIDAL GP | BDM `pnl_gross_profit_actual` filtered `parent_segment='Emerging_BU', segment='TIDAL_BU'` | |
| Proto GP | Same, filtered `segment='Proto_BU'` | |

### Profitability footer

| Output row | Source / derivation |
|---|---|
| Adjusted Opex | **DERIVED:** `Block GP − Adj OI` (identity). Same formula for every period. |
| Adjusted OI | BDM `financial__profit_and_loss__adjusted_operating_income_actual` / `_outlook` |
| Rule of 40 (Actual) | **DERIVED:** `(Block GP / Block GP_yoy_prior − 1) + Adj OI / Block GP` |
| Rule of 40 vs OL (pts) | R40_actual − R40 computed at OL using `(Block GP_ol / Block GP_yoy_prior − 1) + Adj OI_ol / Block GP_ol` |
| Rule of 40 vs AP (pts) | R40_actual − R40 computed at AP (same formula, AP values) |
| Rule of 40 YoY (pts) | R40_actual − R40_prior_year. R40_prior_year uses `Block GP_yoy_prior / Block GP_yoy_prior_prior − 1` + `Adj OI_yoy_prior / Block GP_yoy_prior`. **Needs prior-prior-year GP anchor** — e.g. for Apr'26 report, pull Apr'24 Block GP. |
| Rule of 40 Prior-mo YoY (pts) | R40_prior_month − R40 at prior-month one-year-ago. Same logic, shifted one month. Needs `Block GP_prior_month_yoy_prior_prior` (e.g. Mar'24 for Apr'26 report). |

---

## Standardized P&L — Range `L432:R468`

27 GAAP OpEx line items + 4 derived rollups + 4 totals. All from BDM `financial__profit_and_loss__*_opex_actual` / `_outlook` and historicals.

### Direct BDM metrics

| Output row | BDM metric |
|---|---|
| P2P | `pnl_p2p_opex_actual` / `_outlook` |
| Risk Loss | `pnl_risk_loss_opex_actual` / `_outlook` |
| Card Issuance | `pnl_card_issuance_opex_actual` / `_outlook` |
| Warehouse Financing | `pnl_warehouse_financing_opex_actual` / `_outlook` |
| Hardware Logistics | `pnl_hardware_logistics_opex_actual` / `_outlook` |
| Bad Debt Expense | `pnl_bad_debt_expense_opex_actual` / `_outlook` |
| Customer Reimbursements | `pnl_customer_reimbursements_opex_actual` / `_outlook` |
| Total Variable Operational Costs | `pnl_total_variable_operational_costs_actual` / `_outlook` |
| Marketing | `pnl_marketing_opex_actual` / `_outlook` |
| Onboarding Costs | `pnl_onboarding_opex_actual` / `_outlook` |
| Partnership Fees | `pnl_partnership_fees_opex_actual` / `_outlook` |
| Reader Expense | `pnl_reader_expense_opex_actual` / `_outlook` |
| Sales & Marketing (People) | `pnl_sales_marketing_people_opex_actual` / `_outlook` |
| Total Acquisition Costs | `pnl_total_acquisition_costs_actual` / `_outlook` |
| Product Development People | `pnl_prod_dev_people_opex_actual` / `_outlook` |
| G&A People (ex. CS) | `pnl_g_a_people_opex_actual` / `_outlook` (BDM returns ex-CS value, not the parent rollup) |
| Customer Support People | `pnl_customer_support_people_opex_actual` / `_outlook` |
| Software | `pnl_software_fees_opex_actual` / `_outlook` |
| Cloud fees | `pnl_cloud_fees_opex_actual` / `_outlook` |
| Taxes, Insurance & Other Corp | `pnl_taxes_insurance_other_corp_opex_actual` / `_outlook` |
| Legal fees | `pnl_legal_fees_opex_actual` / `_outlook` |
| Other Professional Services | `pnl_other_professional_services_opex_actual` / `_outlook` |
| Rent, Facilities, Equipment | `pnl_rent_facilities_equipment_opex_actual` / `_outlook` |
| Travel & Entertainment | `pnl_travel_entertainment_opex_actual` / `_outlook` |
| Hardware Production Costs | `pnl_hardware_production_costs_opex_actual` / `_outlook` |
| Non-Cash expenses (ex. SBC) | `pnl_non_cash_expense_excl_sbc_opex_actual` / `_outlook` |
| Total Block GAAP OpEx | `pnl_total_block_gaap_opex_actual` / `_outlook` |

### Derived rollups (computed by helper)

| Output row | Derivation |
|---|---|
| Other (Variable) | Hardware Logistics + Bad Debt Expense + Customer Reimbursements |
| Marketing (Non-People) | Marketing + Onboarding + Partnership Fees + Reader Expense |
| G&A People (parent) | G&A People (ex. CS) + Customer Support People |
| Software & Cloud | Software + Cloud fees |
| Litigation & Professional Services | Legal fees + Other Professional Services |
| **Total Fixed Costs** | Total Block GAAP OpEx − Total Variable − Total Acquisition. **Note:** BDM `pnl_total_fixed_costs_actual` returns ~$504M which doesn't match source convention (~$407M). Always derive — do NOT use the BDM rollup. |

---

## Quick lookup: which scenario value goes where in the Snowflake tables

| Source | Scenario field | Values |
|---|---|---|
| `app_finance_cash.fands.business_metrics_actuals_outlooks` | `VERSION` | `Actual`, `Annual Plan 2026`, `Q2 Outlook`, `Q3 Outlook`, `Q4 Outlook`, … |
| `app_bi.square_fns.vcompany_goals` | `SCENARIO` | `2026 AP`, `2026 Q2 OL`, `2025 Q3 OL`, `2025 Q4 OL` (forecasts only; no Actual) |
| `app_hexagon.block.operational_metrics_forecast` | `SCENARIO` | `Q2 Outlook`, `2026 Annual Plan`, others |
| `app_hexagon.schedule2.finstmt_master` (Hyperion) | `SCENARIO` + `YEARS` + `PERIOD` | `Actual`, `Q2 Outlook`, `2026 Annual Plan`. Date filter is `MONTH_FIRST_DAY` (first-of-month) |

---

## Formatting rules (applied by the helper)

- Dollar amounts: `$10M+` → no decimal (`$87M`), `$1M–$10M` → 1 decimal (`$4.8M`), `≥$1B` → 2 decimals (`$2.79B`), `<$100K` → comma-formatted
- Counts (Actives): `58.3M` style. Dollar deltas for count metrics drop the `$` sign.
- Percent: 1 decimal default (`5.9%`). Negative wrapped in parens (`(2.3%)`).
- **nm rule:** any variance percentage with `abs(value) > 1000%` displays as `nm`. Applies to all % delta columns and YoY columns.
- Rule of 40 deltas: in **points** with explicit sign (`+5.8 pts`, `-2.3 pts`).
- Blank cells (no data): empty string, not `0` or `null`. The sheet renders these as blank.
