---
name: mrp-data
description: Build the MRP data layer. Pulls all in-scope metrics for the Block P&L Overview and Standardized P&L tables from BDM + Snowflake, runs derivations (Adj OpEx via GP-AOI, V/A/F rollups, R40, Adj EBITDA), applies the ±10 precision + nm rules, and emits a JSON packet consumed by /mrp.
allowed-tools:
  - mcp__blockdata__fetch_metric_data
  - mcp__blockdata__metric_store_search
  - mcp__blockdata__get_metric_details
  - mcp__blockdata__get_dimension_values
  - mcp__snowflake__execute_query
  - Bash(python3:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "2.0"
  status: development
---

# MRP-Data

Build the data layer for the Monthly Management Reporting Pack. Pulls all metrics from BDM + Snowflake, runs derivations, emits a JSON packet.

**No sheet validation copy in v1.** Output is `/tmp/mrp_out_{YYYY_MM}.json` only.

**Dependencies:**
- `~/skills/monthly-reporting-pack/mrp-data/skills/mrp-data-sourcing.md` — every BDM metric and Snowflake query mapped to each row
- `~/skills/monthly-reporting-pack/mrp-data/helpers/mrp_data.py` — Python helper for derivations + formatting
- `~/skills/monthly-reporting-pack/skills/financial-reporting.md` — global formatting recipe

---

## Scope (v1)

- **Table 2 — Block P&L Overview (30×7):** GP by brand, V/A/F rollups, GAAP OpEx, AOI, R40, QTD cols
- **Table 3 — Stnd P&L Double Click (45×4):** OpEx line items + Personnel/Contractors/SBC by function

All other MRP tables out of scope for v1.

---

## Step 1 — Determine the report period

- If user passed a period arg (e.g., `--month 2026-04`), use it.
- Otherwise default to the most recently closed month.

Set anchors:

| Anchor | Calc |
|---|---|
| `report_month` | YYYY-MM-01 → end-of-month |
| `qtd_start` | First day of report month's quarter |
| `yoy_prior` | Same month, prior year (e.g. Apr'26 → Apr'25) |
| `qtd_yoy_prior` | QTD range, prior year |
| `scenario_ol` | Q1→`2026 Annual Plan`, Q2→`Q2 Outlook`, Q3→`Q3 Outlook`, Q4→`Q4 Outlook` |
| `scenario_ap` | `{Year} Annual Plan` (always, for AP supplemental on Adj OpEx + R40) |

State: `Building MRP data for {Month'YY}. OL scenario = {scenario_ol}.`

---

## Step 2 — Pull raw values

See `mrp-data-sourcing.md` for the per-row mapping (populated in Phase 1).

Run BDM + Snowflake fetches in parallel where possible. Use:
- `mcp__blockdata__fetch_metric_data` — BDM metrics
- `mcp__snowflake__execute_query` — Hyperion direct (US Payments, etc.)

Save raw values to a Python dict, then write to a fixture for the helper:
```
/tmp/mrp_raw_{YYYY_MM}.json
```

---

## Step 3 — Derive + format

```bash
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/mrp_data.py \
  --month {YYYY-MM} \
  --raw /tmp/mrp_raw_{YYYY_MM}.json \
  --out /tmp/mrp_out_{YYYY_MM}.json
```

Helper computes:
- Adj OpEx = Block GP − Adj OI (identity)
- V/A/F bucket totals (Variable / Acquisition / Fixed)
- Total Fixed Costs derived (GAAP OpEx − Variable − Acquisition; never use BDM `pnl_total_fixed_costs_actual`)
- Block GAAP OI = Block GP − Block GAAP OpEx
- R40 = GP YoY% + AOI margin
- Adj EBITDA + margin
- YoY % deltas (`nm` if abs > 1000%)
- vs.OL $ + %
- QTD versions of all above

Applies formatting:
- $: `$10M+` → integer; `$1-10M` → 1 decimal; `$1B+` → 2 decimals
- %: 1 decimal, parens for negatives
- Pts: `+5.8 pts`, `-2.3 pts`
- ±10 rule on |magnitude|: ≤10 → 1 decimal, >10 → integer

Output JSON shape:
```json
{
  "meta": {
    "report_month": "2026-04",
    "quarter": "Q2",
    "scenario_ol": "Q2 Outlook",
    "scenario_ap": "2026 Annual Plan",
    "generated_at": "..."
  },
  "block_pl": {
    "rows": [
      {
        "label": "Gross profit",
        "actual_raw": 1018234567.89,  "actual_formatted": "$1,018M",
        "yoy_raw": 0.23,              "yoy_formatted": "23%",
        "vs_ol_raw": 21345678,        "vs_ol_formatted": "$21M",
        "qtd_actual_raw": ...,        "qtd_actual_formatted": "$3,132M",
        ...
      },
      ...
    ]
  },
  "stnd_pl": { "rows": [...] },
  "gaps": ["headcount", "personnel_by_function_pd", ...]
}
```

---

## Step 4 — Summary

Print:
```
=== MRP Data Packet ===
Period: Apr 2026 (Q2)
OL scenario: Q2 Outlook
Block GP:    $1,018M actual | Q2OL $X,XXXM | YoY +23%
Adj OI:      $280M actual   | margin 27%   | YoY +40%
Rule of 40:  50%             | +X pts vs PY
Gaps:        [list]
JSON: /tmp/mrp_out_2026_04.json
```
