---
name: flash-data
description: Build the Flash data layer. Pulls all metrics from BDM + Snowflake, computes derivations (Adj OpEx, Rule of 40, Inflows/Active, V/A/F bucket totals), applies the nm rule for >1000% variances, and writes formatted values to the validation copy in MRP Charts & Tables — `L400:S427` for monthly, `T400:Y427` for quarterly — alongside the Standardized P&L at `L432:R468`. Also emits a JSON packet consumed by /monthly-flash for narrative + Doc table population.
allowed-tools:
  - mcp__blockdata__fetch_metric_data
  - mcp__blockdata__metric_store_search
  - mcp__blockdata__get_metric_details
  - mcp__snowflake__execute_query
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Bash(sq agent-tools google-drive sheets-tool:*)
  - Bash(python3:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "1.0"
  status: active
---

# Flash-Data

Build the data layer for the Monthly Flash. Pulls all metrics from BDM + Snowflake, runs derivations, writes to the brand reporting model.

**Dependencies:**
- `~/skills/monthly-flash/flash-data/skills/flash-data-sourcing.md` — every BDM metric and Snowflake query mapped to each row
- `~/skills/monthly-flash/flash-data/helpers/flash_data.py` — Python helper for derivations + formatting

---

## Configuration

| Parameter | Value |
|---|---|
| Output workbook | `15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0` |
| Output tab | `MRP Charts & Tables` |
| Flash table range (monthly) | `L400:S427` (28 rows × 8 cols) — single-month values |
| Flash table range (quarterly) | `T400:Y427` (28 rows × 6 cols, labels in col L) — QTD/full-quarter sums |
| Standardized P&L range | `L432:R468` (37 rows × 7 cols) |
| Helper script | `~/skills/monthly-flash/flash-data/helpers/flash_data.py` |

**Mode selection:** auto-detect from period.
- Quarter-end months (Mar, Jun, Sep, Dec) → **quarterly** mode → write to `T400:Y427` (QTD-summed values, 6 data cols)
- Intra-quarter months → **monthly** mode → write to `L400:S427` (single-month values, 7 data cols)

The orchestrator (this command) determines mode from the period; the underlying `flash_data.py` helper currently emits a single 28×8 packet regardless of mode. **Quarterly write path is not yet wired end-to-end** — first Jun'26 run will need to extend the helper to (a) sum each metric across the three months of the quarter and (b) write to `T400:Y427`. Until then, quarterly runs will populate the monthly range instead.

---

## Step 1 — Determine the report period and mode

- If user passed a period arg (e.g., `Apr'26`, `Jun'26`), use it.
- Otherwise default to the most recently closed month (one month back from today).
- **Mode:** quarter-end (Mar/Jun/Sep/Dec) → quarterly. Otherwise → monthly.

### Quarterly mode date math

For a quarterly run on (e.g.) `Jun'26`:
- The report quarter is `Q2 2026` covering Apr/May/Jun 2026.
- Pull each metric for **all three months in the quarter** and sum to get the QTD value.
- YoY prior = same quarter, prior year (Q2 2025 = Apr/May/Jun 2025 summed).
- Q2OL for the quarter = sum of monthly Q2OL values across Apr/May/Jun.
- AP for the quarter = sum of monthly AP values across Apr/May/Jun.
- No prior-month YoY in quarterly mode (the T-Y view has no equivalent column).

Compute the anchor dates:

| Anchor | Calculation |
|---|---|
| `report_month` | YYYY-MM (e.g., 2026-04) |
| `prior_month` | one month back (2026-03) |
| `yoy_anchor` | same month, one year back (2025-04) |
| `prior_month_yoy_anchor` | one month back, one year back (2025-03) |
| `yoy_prior_prior` | same month, two years back (2024-04) — for R40 YoY delta |
| `prior_month_yoy_prior_prior` | one month back, two years back (2024-03) — for R40 prior-mo YoY delta |
| Scenario `ol` label | derived from quarter: Q1→`AP` (Annual Plan — no Q1OL), Q2→`Q2 Outlook`, Q3→`Q3 Outlook`, Q4→`Q4 Outlook`. |
| Scenario `ap` label | `{Year} Annual Plan` for the report year |

State to user: "Building Flash data for {Month'YY}. OL scenario = {scenario}, AP scenario = {scenario}."

---

## Step 2 — Pull raw values

Reference `flash-data-sourcing.md` for the exact source per row.

Use these MCP tools:
- `mcp__blockdata__fetch_metric_data` for BDM metrics — pass `metric_name`, `granularity="month"`, `start_date`/`end_date` bracketing the periods needed, optional `dimensions` (e.g., `["entity"]` for US Payments)
- `mcp__snowflake__execute_query` for Snowflake direct queries

Build a single Python dict `raw` keyed by `{metric}_{scenario}`:
- `cash_app_actives_actual`, `cash_app_actives_ol`, `cash_app_actives_ap`, `cash_app_actives_yoy_prior`, `cash_app_actives_prior_month_actual`, `cash_app_actives_prior_month_yoy_prior`
- Same suffix pattern for every Flash table and Stnd P&L row

**Key gotchas (memorized):**
- BDM Snowflake date conventions differ between tables — `app_finance_cash` uses end-of-month; `app_bi.square_fns.vcompany_goals` uses end-of-month; Hyperion `finstmt_master` uses first-of-month (`MONTH_FIRST_DAY`).
- US Payments: do NOT use BDM `square_pnl_processing_gp_actual` for Actual — query Hyperion directly with `product='1010-Processing'` `account='Gross Profit (NonGAAP)'`. The BDM metric aggregates 1010+1011+1020+1030+1510 and disagrees with Flash by ~$17M.
- Cash App Inflows/Active denominator: use total actives, not inflow-actives. BDM `cash_app_inflows_per_active` uses the wrong denominator — derive from raw inflows / total actives.
- Commerce GMV Q2OL: BDM is sparse; pull from `app_hexagon.block.operational_metrics_forecast` filter `PRODUCT <> '1312-Cash App Pay'`.

Save `raw` to a JSON fixture for the helper:

```bash
echo '<raw dict as JSON>' > /tmp/flash_raw_{month}.json
```

---

## Step 3 — Run derivation helper

```bash
python3 ~/skills/monthly-flash/flash-data/helpers/flash_data.py \
  --input /tmp/flash_raw_{month}.json \
  --period "{Mon'YY}" \
  --output /tmp/flash_out_{month}.json
```

The helper produces both raw and formatted versions of each table:
- `flash_table_raw`: 28 rows × 8 cols of **raw numeric values** (decimals for %) → goes to L400:S427 in the G-sheet. Sheet stores raw numbers; sheet's own column formatting renders display (e.g., $1.02B). Percentages are stored as decimals (0.0586 = 5.9%).
- `flash_table_formatted`: same shape, but formatted strings ($1.02B, 5.9%) → used by Skill B for doc narrative
- `pnl_table_raw` / `pnl_table_formatted`: same pattern for the Stnd P&L
- `raw_derived`: full dict including derived rollups + Adj OpEx + R40 anchors (for Skill B's driver attribution)

**Why both?** Sheet holds raw for testing/audit/formulas. Doc uses formatted strings for narrative. Skill B picks the formatted variant for doc output.

---

## Step 4 — Write RAW values to brand reporting model

Use the `_raw` variants so the sheet stores numbers (not formatted strings). Convert each cell value to a string for the sheets-tool payload — Sheets will recognize numeric strings as numbers automatically.

```python
# Flash table (raw)
sq agent-tools google-drive sheets-tool --json '{
  "spreadsheet_id_or_url": "15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0",
  "operation": "update_values",
  "sheet_name": "MRP Charts & Tables",
  "range": "L400:S427",
  "values": <flash_table_raw, each cell stringified>
}'

# Standardized P&L (raw)
sq agent-tools google-drive sheets-tool --json '{
  "spreadsheet_id_or_url": "15j9tou-7OmLxvk41cmkJkYTAQLXXLl08slX9p8RsVL0",
  "operation": "update_values",
  "sheet_name": "MRP Charts & Tables",
  "range": "L432:R468",
  "values": <pnl_table_raw, each cell stringified>
}'
```

Sheet has hidden columns (P, T-Z) — values still land in them correctly.

### Apply cell number formats

The sheet stores raw numbers; the display format is applied via `sheets-formatting`. Apply once after a fresh shell setup (formats persist across value updates). Patterns:

| Range | Pattern | Type |
|---|---|---|
| Flash table % cols (rows 402-426) — `O402:O426`, `Q402:S426` (NOT col P which is vs. AP $) | `0.0%;(0.0%)` | PERCENT |
| Flash R40 row pts deltas `O427`, `Q427`, `R427`, `S427` | `+0.0" pts";-0.0" pts";0" pts"` | NUMBER |
| Flash R40 actual `M427` | `0.0%;(0.0%)` | PERCENT |
| Flash col P (vs. AP $) rows 402-426 — `P402:P426` | `[>=10000000]$#,##0,,"M";[<=-10000000]($#,##0,,"M");$#,##0.0,,"M"` | CURRENCY |
| Stnd P&L $ cols `M433:M468`, `N433:N468`, `P433:P468` | `[>=1000000000]$#,##0.00,,,"B";[<=-1000000000]($#,##0.00,,,"B");[>=10000000]$#,##0,,"M";[<=-10000000]($#,##0,,"M");$#,##0.0,,"M";($#,##0.0,,"M")` | CURRENCY |
| Stnd P&L % cols `O433:O468`, `Q433:Q468`, `R433:R468` | `0.0%;(0.0%)` | PERCENT |

The Flash table $ columns (M, N, P rows 402-426) already have appropriate currency formatting in Nick's shell — don't overwrite.

**R40 special handling:** R40 actual is a decimal (0.501 displays as 50.1%). R40 deltas are pre-scaled to **points** (e.g., 5.8 not 0.058) so the `" pts"` format works without `%`-implied multiplication. This is handled by the helper.

**"nm" cells:** when a variance exceeds 1000%, the cell holds the text "nm" (not a number) — text bypasses numeric format and displays as-is.

---

## Step 5 — Sanity check

Read back the first 5 rows and verify they parse. If the sheets-tool times out, retry once.

Quick validation checks the helper has already applied:
- Block GP YoY ≈ 22.6% for Apr'26 (validate against `(GP_actual / GP_yoy_prior) - 1`)
- Adj OpEx = GP − Adj OI (identity check)
- Rule of 40 sum: GP YoY + Adj OI / GP

---

## Step 6 — Report back

Tell Nick:
- **Period:** {Month'YY}
- **Ranges written:** L400:S427 (Flash table, 28 rows) + L432:R468 (Stnd P&L, 37 rows)
- **Headline:** Block GP actual + YoY%, Adj OI actual + YoY%, Rule of 40
- **Variances flagged for corp-context:** any V/A/F bucket where |Δ| ≥ $20M OR ≥ 10% vs OL — list them
- **Data packet:** `/tmp/flash_out_{month}.json` (for Skill B narrative)

Hand off to Step 2 of `/monthly-flash` (narrative generation).

---

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| BDM metric returns empty | Wrong scenario filter or date convention | Check `flash-data-sourcing.md` — confirm scenario label (e.g., `Q2 Outlook` not `Q2OL`) and date format |
| Snowflake query returns 0 rows | Date convention mismatch (end-of-month vs first-of-month) | Switch the date filter |
| BDM US Payments doesn't match Flash | Used the BDM metric instead of Hyperion direct | Run the Hyperion direct query — see Sourcing reference |
| Sheets write times out | Transient API issue | Retry once. If persistent, split into smaller ranges |
| Helper output looks wrong | Missing key in raw dict | Helper writes `EMPTY` for any missing key. Inspect `raw_derived` JSON to find the gap |
