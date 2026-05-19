---
name: mrp-validate
description: Validate the published MRP Test tab against the JSON data packet (Layer 1) and the manual MRP tab reference (Layer 2). Cell-by-cell comparison for Block P&L Overview + Standardized P&L tables. Reports PASS/FAIL/WARN.
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Bash(python3:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "2.0"
  status: development
---

# MRP Validate

Cell-by-cell validation of the published MRP Test tab. Two layers:

- **Layer 1 (publish-pipeline check):** Test tab cell ↔ JSON packet value. Catches populator bugs.
- **Layer 2 (source-mapping check):** Test tab cell ↔ MRP tab manual reference cell. Catches data-source mapping errors that Layer 1 misses.

**Scope (v1):** Test tab Tables 2 (Block P&L Overview, 30×7) and 3 (Stnd P&L Double Click, 45×4). Other tables not validated.

---

## Step 1 — Inputs

- `DOC_ID` — required (from URL or arg)
- `TEST_TAB_ID` — default `t.3mz1duijrdf1`
- `MRP_TAB_ID` — default `t.ea3bz9hprpol` (manual reference)
- `PACKET_PATH` — default `/tmp/mrp_out_{YYYY_MM}.json` (derive YYYY_MM from packet meta or from period arg)
- `REPORT_PATH` — default `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_validation_{YYYY_MM}.md`

---

## Step 2 — Fetch current doc state

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs get {DOC_ID} --include-tabs > /tmp/mrp_doc.json
```

---

## Step 3 — Run validator helper

```bash
python3 ~/skills/monthly-reporting-pack/mrp-data/helpers/validate_block_pl.py \
  --doc /tmp/mrp_doc.json \
  --packet {PACKET_PATH} \
  --test-tab {TEST_TAB_ID} \
  --mrp-tab {MRP_TAB_ID} \
  --out {REPORT_PATH}
```

The helper handles both layers:

**Layer 1 — Test tab ↔ JSON packet (publish-pipeline check).** For each row in the packet, compares the `formatted` string to the Test tab cell text. Exact match passes; otherwise both sides are parsed numerically and compared with tolerance ($1M for $, 1pt for rates, 0.5pts for pts deltas).

**Layer 2 — Test tab ↔ MRP tab manual reference (source-mapping check).** For each cell, compares Test tab text to the same cell in the manual MRP tab. Catches source-mapping bugs Layer 1 misses (Test tab and packet agree, but both wrong vs. published).

Known WARN-not-FAIL cases hard-coded in the helper:
- People row (R29): headcount not in BDM
- Bitcoin Lightning / Bitkey (R07/R08): BDM segment labels TBD
- Adj EBITDA + margin (R27/R28): source TBD
- QTD Pace columns (cols 4-6): ~$20M contingency divergence

Report format (markdown):

```markdown
# MRP Validation Report — {Month YYYY}

**Generated:** ISO timestamp
**Quarter:** Q2 (Q2OL = Q2 Outlook)

## Summary
- Total checks: N
- PASS: N | FAIL: N | WARN: N
- Layer 1: N PASS / N FAIL / N WARN
- Layer 2: N PASS / N FAIL / N WARN

## Failures
| Layer | R | Row | Col | Kind | Test | Expected | Δ | Note |

## Warnings
| Layer | R | Row | Col | Kind | Test | Expected | Δ | Note |
```

Exit code: `0` if all checks PASS or WARN; `1` if any FAIL.

---

## Step 4 — Console summary

The helper prints:
```
Validation: N PASS / N FAIL / N WARN
  Layer 1: P/F/W
  Layer 2: P/F/W
Report: {path}
```

Surface this to Nick along with any FAIL items needing attention.
