# MRP-Data Sourcing Reference

Source-of-truth mapping for every value the MRP automation writes to the Test tab. Each row identifies the data source (BDM metric or Snowflake query), the filter convention, and any derivation logic.

**Key principle:** No hardcoded values. Every value comes from a query you can re-run.

**Scope (v1):** Test tab Tables 2 (Block P&L Overview, 30×7) and 3 (Standardized P&L Double Click, 45×4). Both under the "Block P&Ls" heading. Other tables out of scope.

---

## Period anchors

For a report month `YYYY-MM`:

| Anchor | Definition |
|---|---|
| `actual` | Report month, scenario=Actual (e.g. Apr'26) |
| `yoy_prior` | Same month, prior year, scenario=Actual (e.g. Apr'25) |
| `ol` | Report month, scenario=current Outlook (Q1→AP, Q2→Q2OL, Q3→Q3OL, Q4→Q4OL) |
| `ap` | Report month, scenario=`{Year} Annual Plan` (always available) |
| `qtd_actuals` | Sum of `actual` for each closed month in the report quarter through the report month |
| `qtd_yoy_prior_actuals` | Sum of `actual` for the same months in the prior year |
| `qtd_pace` | **`qtd_actuals` + `ol` for remaining months in the quarter.** Represents the full-quarter projection assuming remaining months land at outlook. |
| `qtd_ol` | Sum of `ol` for all 3 months of the report quarter (full-quarter outlook) |

**QTD Pace contingency note:** The manual MRP applies a ~$20M contingency reserve when forecasting May/June pacing. The automated `qtd_pace` does NOT include this judgment adjustment — it sums pure Q2OL for remaining months. **Expect ~$20M divergence between automated QTD Pace and the manual MRP tab.** Documented in `feedback_mrp_qtd_contingency.md` (to add).

---

## Comparison scenario by quarter

Per `financial-reporting.md`:

| Quarter | OL label | OL scenario string (BDM) |
|---|---|---|
| Q1 | AP | `2026 Annual Plan` (no Q1OL exists) |
| Q2 | Q2OL | `Q2 Outlook` |
| Q3 | Q3OL | `Q3 Outlook` |
| Q4 | Q4OL | `Q4 Outlook` |

April'26 is Q2 → `Q2 Outlook` is the primary anchor on the "vs. OL" columns.

---

## Table 2 — Block P&L Overview (30 rows × 7 cols)

Column layout (after the label col):

| Col | Header | Period | Comparison |
|---|---|---|---|
| 1 | label | — | — |
| 2 | Actual | `actual` (Apr'26) | absolute |
| 3 | YoY % | `actual` vs `yoy_prior` | `(actual - yoy_prior) / abs(yoy_prior)` |
| 4 | vs. OL | `actual` vs `ol` | `actual - ol` ($ delta) |
| 5 | QTD Pace¹ | `qtd_pace` (see above) | absolute |
| 6 | YoY % (QTD) | `qtd_pace` vs `qtd_yoy_prior_actuals` | `(qtd_pace - qtd_yoy_prior) / abs(qtd_yoy_prior)` |
| 7 | vs. OL (QTD) | `qtd_pace` vs `qtd_ol` | `qtd_pace - qtd_ol` ($ delta) |

### Row map

| R | Label | Source / Derivation |
|---|---|---|
| R02 | Gross profit | BDM `financial__profit_and_loss__pnl_gross_profit_actual` / `_outlook` |
| R03 | Cash App (GP) | BDM `pnl_gross_profit_actual` filter `product_brand=Cash App` |
| R04 | Square (GP) | BDM `pnl_gross_profit_actual` filter `product_brand=Square` |
| R05 | Other Brands (GP, parent) | BDM `pnl_gross_profit_actual` filter `product_brand=All Other Brands` |
| R06 | TIDAL | BDM `pnl_gross_profit_actual` filter `parent_segment=Emerging_BU, segment=TIDAL_BU` (verify exact label via `get_dimension_values`) |
| R07 | Bitcoin Lightning | **TBD — verify in Phase 2.** Likely `segment=Bitcoin_Lightning_BU` or similar under `All Other Brands`. If not in BDM → render as GAP for v1. |
| R08 | Bitkey | **TBD — verify in Phase 2.** Likely `segment=Bitkey_BU` under `All Other Brands`. If not in BDM → render as GAP. |
| R09 | Proto | BDM `pnl_gross_profit_actual` filter `segment=Proto_BU` |
| R10 | Variable Operational Costs (total) | BDM `pnl_total_variable_operational_costs_actual` / `_outlook` |
| R11 | P2P marketing | BDM `pnl_p2p_opex_actual` / `_outlook`. Label says "marketing" but the underlying metric is the P2P line item from Flash convention. |
| R12 | Risk loss | BDM `pnl_risk_loss_opex_actual` / `_outlook` |
| R13 | Other variable² | **DERIVED as residual:** `pnl_total_variable_operational_costs_actual − pnl_p2p_opex_actual − pnl_risk_loss_opex_actual`. The MRP convention sums the residual variable line items (including Card Issuance + Warehouse Financing on top of HW Logistics + Bad Debt + Customer Reimbursements). Phase 5b Apr'26 verified: sum-of-three = $3.8M vs manual $16M; residual = $16M ✓. |
| R14 | Acquisition Costs (incl. S&M people) | BDM `pnl_total_acquisition_costs_actual` / `_outlook` |
| R15 | Fixed Costs (total) | **DERIVED:** `pnl_total_block_gaap_opex_actual − pnl_total_variable_operational_costs_actual − pnl_total_acquisition_costs_actual`. **Do NOT use BDM `pnl_total_fixed_costs_actual`** — that returns ~$504M vs source convention ~$407M. (Flash v2.0 fix.) |
| R16 | Product development people | BDM `pnl_prod_dev_people_opex_actual` / `_outlook` |
| R17 | G&A people (ex. CS) | BDM `pnl_g_a_people_opex_actual` / `_outlook`. BDM returns the ex-CS value (not the parent rollup). |
| R18 | Customer support (people) | BDM `pnl_customer_support_people_opex_actual` / `_outlook` |
| R19 | Software & cloud | **DERIVED:** `pnl_software_fees_opex_actual` + `pnl_cloud_fees_opex_actual` |
| R20 | Other Fixed³ | **DERIVED:** Fixed Costs (R15) − Prod Dev People (R16) − G&A People ex CS (R17) − CS People (R18) − Software & Cloud (R19). Captures remaining Fixed line items (Taxes/Insurance, Legal, Other Pro Services, Rent, T&E, Hardware Production, Non-Cash ex SBC). |
| R21 | GAAP OpEx | BDM `pnl_total_block_gaap_opex_actual` / `_outlook` |
| R22 | GAAP Operating income | **DERIVED:** Block GP (R02) − GAAP OpEx (R21). |
| R23 | Adjusted Opex | **DERIVED:** Block GP (R02) − Adj OI (R24). **Flash v2.0 identity** — do NOT derive via bridge subtraction (GAAP − restructuring − amort), that path has no Q2OL/AP coverage. |
| R24 | Adjusted Operating Income | BDM `financial__profit_and_loss__adjusted_operating_income_actual` / `_outlook` |
| R25 | % Margin (AOI) | BDM `financial__profit_and_loss__adjusted_operating_income_margin_actual` / `_outlook`. Display as %; deltas in pts. |
| R26 | Rule of 40 | **DERIVED:** GP YoY% (col 3 of R02) + AOI margin % (col 2 of R25). Display as %; deltas in pts. |
| R27 | Adjusted EBITDA | **TBD — verify in Phase 2.** Search BDM for `*ebitda*` metric. If not present → derive Adj EBITDA = Adj OI + D&A. May need separate D&A metric or fetch from Hyperion. If derivation infeasible → render as GAP for v1. |
| R28 | % Margin (Adj EBITDA) | **DERIVED:** Adj EBITDA (R27) / Block GP (R02). pts deltas. |
| R29 | People (headcount) | **GAP — confirmed.** BDM does not have headcount. Render as red `[GAP]` in all 6 data cells per `feedback_mrp_gaps_as_placeholders.md`. |

### Methodology fixes carried forward from Flash v2.0

These are non-obvious source-mapping choices documented because the "natural" BDM path returns wrong values:

1. **Total Fixed Costs derived, not from BDM rollup** — see R15 above.
2. **Adj OpEx via GP − AOI identity** — see R23 above.
3. **Variances >1000% display as "nm"** — applies to `YoY %` and `vs. OL %` cols. (Table 2 has no `vs. OL %` cols, only `vs. OL $`, but YoY can still trigger.)

### Bold rows (populator must apply bold per Flash convention)

R02 Gross profit, R10 Variable Operational Costs, R14 Acquisition Costs, R15 Fixed Costs, R21 GAAP OpEx, R22 GAAP Operating income, R23 Adjusted Opex, R24 Adjusted Operating Income, R26 Rule of 40, R27 Adjusted EBITDA.

---

## Table 3 — Standardized P&L Double Click (45 rows × 4 cols)

Column layout:

| Col | Header | Period | Comparison |
|---|---|---|---|
| 1 | label | — | — |
| 2 | Actual | `actual` (Apr'26) | absolute |
| 3 | YoY Growth | `actual` vs `yoy_prior` | `(actual - yoy_prior) / abs(yoy_prior)` |
| 4 | vs. OL | `actual` vs `ol` | `actual - ol` ($ delta) |

No QTD cols on this table.

### Row map

| R | Label | Source / Derivation |
|---|---|---|
| **R02** | **Variable Operational Costs (section header)** | non-data; leave blank |
| R03 | P2P | BDM `pnl_p2p_opex_actual` |
| R04 | Risk Loss | BDM `pnl_risk_loss_opex_actual` |
| R05 | Card Issuance | BDM `pnl_card_issuance_opex_actual` |
| R06 | Warehouse Financing | BDM `pnl_warehouse_financing_opex_actual` |
| R07 | Hardware Logistics | BDM `pnl_hardware_logistics_opex_actual` |
| R08 | Bad Debt Expense | BDM `pnl_bad_debt_expense_opex_actual` |
| R09 | Customer Reimbursements | BDM `pnl_customer_reimbursements_opex_actual` |
| **R10** | **Acquisition Costs (section header)** | non-data; leave blank |
| R11 | Marketing (Non-People) | **DERIVED:** `pnl_marketing_opex + pnl_onboarding_opex + pnl_partnership_fees_opex + pnl_reader_expense_opex`. Phase 6 Apr'26 verified: Marketing alone = $53.5M (doesn't match manual $63M); sum of four = $63.1M ≈ manual $63M ✓. |
| R12 | Sales & Marketing (People) | BDM `pnl_sales_marketing_people_opex_actual` |
| **R13** | **Fixed Costs (section header)** | non-data; leave blank |
| R14 | Product Development People | BDM `pnl_prod_dev_people_opex_actual` |
| R15 | G&A People (ex. CS) | BDM `pnl_g_a_people_opex_actual` |
| R16 | Customer Support People | BDM `pnl_customer_support_people_opex_actual` |
| R17 | Software | BDM `pnl_software_fees_opex_actual` |
| R18 | Cloud fees | BDM `pnl_cloud_fees_opex_actual` |
| R19 | Taxes, Insurance & Other Corp | BDM `pnl_taxes_insurance_other_corp_opex_actual` |
| R20 | Legal fees | BDM `pnl_legal_fees_opex_actual` |
| R21 | Other Professional Services | BDM `pnl_other_professional_services_opex_actual` |
| R22 | Rent, Facilities, Equipment | BDM `pnl_rent_facilities_equipment_opex_actual` |
| R23 | Travel & Entertainment | BDM `pnl_travel_entertainment_opex_actual` |
| R24 | Hardware Production Costs | BDM `pnl_hardware_production_costs_opex_actual` |
| R25 | Non-Cash expenses (ex. SBC) | BDM `pnl_non_cash_expense_excl_sbc_opex_actual` |
| **R26** | **GAAP OpEx (subtotal)** | BDM `pnl_total_block_gaap_opex_actual` |
| **R27** | **Total FTE Personnel Costs (incl. SBC) (subtotal)** | BDM `pnl_total_personnel_cost_opex_actual` / `_outlook`. The metric is CS + S&M + PD + G&A people (excludes Compliance and excludes SBC per metric description). Apr'26 Phase 6 verified: BDM $283M vs manual R27 $251M — **$32M divergence**; the manual label "(incl. SBC)" doesn't match BDM's definition. Treat as known Layer 2 WARN. |
| R28-R32 | FTE Personnel by function (PD/S&M/G&A/CS/Compliance) | **CONFIRMED GAP (Phase 6)** — no function-level Personnel metric in BDM. Render as red `[GAP]`. |
| **R33** | **Total Contractors (subtotal)** | **CONFIRMED GAP (Phase 6)** — Contractors not exposed as a metric in BDM. |
| R34-R38 | Contractors by function | **CONFIRMED GAP (Phase 6)** — same. |
| **R39** | **SBC (subtotal)** | BDM `financial__profit_and_loss__share_based_compensation_incl_cogs_actual`. Apr'26 $108M ✓ matches manual. **No `_outlook` variant exists in BDM**, so R39 vs.OL cell is rendered blank (empty), not `[GAP]`. |
| R40-R44 | SBC by function | **CONFIRMED GAP (Phase 6)** — no function-level SBC metric in BDM. |

### Bold rows

R02, R10, R13, R26, R27, R33, R39 (section headers + subtotals).

### Phase 2 verification tasks for Table 3

1. `metric_store_search` for `*personnel*`, `*contractor*`, `*sbc*` to enumerate what BDM exposes at the function level.
2. `get_metric_details` on any candidate to confirm dimension labels (function = "Product Development" / "S&M" / etc.).
3. If gaps confirmed, render R28-R44 as red `[GAP]` per the convention.

---

## Formatting rules (applied by helper)

Per `financial-reporting.md` + Flash v2.0:

- **Dollars:** `$10M+` → integer (`$87M`); `$1-10M` → 1 decimal (`$4.8M`); `$1B+` → 2 decimals (`$2.79B`); `<$100K` → comma-formatted.
- **Percent:** 1 decimal default (`5.9%`). Negative wrapped in parens (`(2.3%)`).
- **±10 rule on variances:** `|magnitude| ≤ 10` → 1 decimal (`9.5%`, `$9.5M`, `+5.8 pts`); `> 10` → integer (`215%`, `$14M`, `+22 pts`). Applies to `YoY %`, `vs. OL $`, pts deltas. YoY columns / direct rates are not reformatted (the ±10 rule applies only to variance values).
- **nm rule:** any variance percentage with `abs(value) > 1000%` displays as `nm`. Applies to all % delta columns.
- **Rule of 40 deltas:** in points with explicit sign (`+5.8 pts`, `-2.3 pts`).
- **Margin deltas:** points with explicit sign (`+3.3 pts`).
- **Negatives:** wrap in parens — `($2.0M)`, `(15%)`, `($0.5M)`.
- **Gap cells:** red text `[GAP]` (per convention from `feedback_mrp_gaps_as_placeholders.md`).
- **Blank cells (no data, no error):** empty string. The cell stays empty in the Docs API write.

---

## BDM gotchas (memorized)

- Snake_case params (`country_code` not `country`).
- 300s warehouse timeout — for multi-year history use direct Snowflake.
- `_outlook` variants of some metrics don't exist; derive via `pnl_gross_profit_outlook` + filter.
- SSG/Churn metrics throw ambiguous-column SQL errors; not in v1 scope.

## Snowflake gotchas (for any Hyperion direct path needed)

- `app_hexagon.schedule2.finstmt_master`: `entity='101-Block, Inc.'`, scenario field is `SCENARIO`, date field is `MONTH_FIRST_DAY` (first-of-month, NOT last-of-month).
- Not currently used for Tables 2 + 3 — all BDM-sourced. Hyperion direct may come in if Block GP via product_brand disagrees with the published MRP.

---

## Open verifications (Phase 2 will resolve)

1. **R07 Bitcoin Lightning, R08 Bitkey:** confirm BDM segment labels.
2. **R11 Marketing (Non-People) on Table 3:** confirm derivation matches MRP convention (Marketing+Onboarding+Partnership+Reader vs just Marketing).
3. **R27 Adj EBITDA:** confirm BDM has it or derive from D&A.
4. **R27-R44 Table 3 Personnel/Contractors/SBC by function:** confirm gap or find metrics.
5. **QTD Pace contingency:** confirm $20M is the right number for April. Document divergence.
