# Monthly Management Reporting Pack — Automation

A pipeline (`/mrp`, `/mrp-data`, `/mrp-validate`) that populates the P&L tables on the MRP Test tab using Claude Code. **v2.0** — sources data from BDM + Snowflake (via `/mrp-data`), populates the Test tab tables via the Docs API, and validates cell-by-cell against both the JSON packet and the manual MRP tab reference.

**v1 scope:** Test tab `t.3mz1duijrdf1` on the April'26 MRP doc, Tables 2 (Block P&L Overview, 30×7) and 3 (Stnd P&L Double Click, 45×4) only. No commentary, no flux sheet, no other tables.

---

## What It Does

Each month after close, Block FP&A publishes the Monthly Management Reporting Pack for Inner Core and ARC reviewers. This system automates the quantitative tables in the pack:

1. **Builds the data layer** (`/mrp-data`) — pulls every in-scope metric directly from BDM + Snowflake, computes derivations (Adj OpEx via the GP − Adj OI identity, V/A/F bucket totals via GAAP OpEx − Variable − Acquisition, R40, Adj EBITDA, etc.), and emits a JSON packet at `/tmp/mrp_out_{YYYY_MM}.json` with both `*_raw` (numbers) and `*_formatted` (display strings) for every value.

2. **Populates the Test tab tables** — `populate_block_pl.py` and `populate_stnd_pl.py` build Docs API `batchUpdate` requests targeting each cell's `startIndex` directly. Values pass writes text + Roboto 10pt + alignment + bold for total rows. Colors pass applies green/red to `vs. OL` columns above thresholds (±$0.5M, ±1%). Gap rendering writes red `[GAP]` for unfillable cells.

3. **Validates** (`/mrp-validate`) — two layers:
   - **Layer 1:** Test tab ↔ JSON packet (catches populator bugs)
   - **Layer 2:** Test tab ↔ MRP tab manual reference (catches source-mapping bugs)

The output is the Test tab populated with automated values, a JSON data packet, and a validation report. The MRP tab (`t.ea3bz9hprpol`) is the manual reference and is **never written to** by the automation.

---

## How To Run

Open Claude Code in the project directory and type:

```
/mrp <DOC_URL>
```

where `<DOC_URL>` includes the Test tab fragment, e.g. `https://docs.google.com/document/d/1OLp.../edit?tab=t.3mz1duijrdf1`.

That's it. The command handles:
- Step 1: Parse Doc URL → DOC_ID + TAB_ID. Refuse if TAB_ID == MRP tab.
- Step 2: Invoke `/mrp-data` to build the JSON packet
- Step 3: Populate Test tab Table 2 (Block P&L Overview)
- Step 4: Populate Test tab Table 3 (Stnd P&L Double Click) — gated on Phase 6
- Step 5: Validate via `/mrp-validate`
- Step 6: Print summary

Output files:
- `/tmp/mrp_out_{YYYY_MM}.json` — JSON data packet
- `~/Desktop/Nick's Cursor/Monthly Reporting Pack/mrp_validation_{YYYY_MM}.md` — validation report

### Standalone commands

- `/mrp-data --month YYYY-MM` — rebuild the packet without populating any tab
- `/mrp-validate <DOC_URL>` — re-validate an already-populated Test tab

---

## What's In This Directory

```
skills/monthly-reporting-pack/
  ├── commands/                          Slash commands (what you type)
  │   ├── mrp.md                          Full pipeline: data → populate → validate
  │   ├── mrp-data.md                     Data-only command (used by /mrp Step 2)
  │   └── mrp-validate.md                 Standalone validation
  │
  ├── skills/                            Reference docs (loaded as context)
  │   ├── financial-reporting.md         → symlink to canonical formatting recipe
  │   └── *.archived                     Mar'26 agent-pipeline skills (preserved for history)
  │
  └── mrp-data/                          Data + populator layer (v2.0)
      ├── skills/
      │   └── mrp-data-sourcing.md       Source-of-truth: BDM metric / Snowflake table per row
      └── helpers/
          ├── mrp_data.py                Derivations + formatting (raw + formatted JSON)
          ├── populate_block_pl.py       Docs API batch-update: Table 2 (Block P&L Overview)
          └── populate_stnd_pl.py        Docs API batch-update: Table 3 (Stnd P&L Double Click)
```

The MRP reuses the same `gdrive-cli.py` tool from `skills/weekly-reporting/gdrive/` for all Google Doc operations.

---

## Key Data Sources

| Source | What It Provides |
|--------|-----------------|
| BDM (Block Data Mart) | Headline GP, sub-product GP, GAAP OpEx line items, AOI, AOI margin |
| Hyperion — `app_hexagon.schedule2.finstmt_master` | US Payments GP direct (product='1010-Processing'; BDM aggregate disagrees by ~$17M) |
| Snowflake — other tables | Square sub-product overrides where BDM rollups disagree with published convention |
| Test tab (target) | Populated by automation; mirrors MRP tab table shells with empty value columns |
| MRP tab (reference) | Manual April'26 MRP; never written to; Layer 2 validation anchor |

The full per-row source-of-truth mapping lives in `mrp-data/skills/mrp-data-sourcing.md`.

### Tables Covered (v1)

| Section | Table | Rows × Cols | Notes |
|---------|-------|-------------|-------|
| Block P&Ls → Overview | Test tab Table 2 | 30×7 | GP by brand, V/A/F rollups, GAAP OpEx, AOI, R40, QTD cols |
| Block P&Ls → Stnd P&L | Test tab Table 3 | 45×4 | OpEx line items + Personnel/Contractors/SBC by function |

Other tables (Brand P&Ls, Cash App detail, Square detail, Other Brands, GP Breakdown) are out of scope for v1.

---

## Comparison Framework

The MRP compares to **Annual Plan (AP)** for Q1 and the **most recent Outlook** for Q2+. April'26 is Q2, so the primary anchor is **Q2OL**.

| Quarter | Comparison Point |
|---------|-----------------|
| Q1 | AP |
| Q2 | Q2OL |
| Q3 | Q3OL |
| Q4 | Q4OL |

---

## What's Automated vs. Manual (v1)

| Automated | Manual |
|-----------|--------|
| Sourcing every metric from BDM + Snowflake (`/mrp-data`) | Qualitative commentary (out of scope) |
| Populating Test tab Tables 2 + 3 with Roboto 10pt + alignment + bold + colors | DRI flux narratives (out of scope) |
| Gap rendering (red `[GAP]` for unfillable cells) | Other 6 tables (Brand P&Ls, Cash App detail, etc.) |
| Cell-by-cell validation (Layer 1 + Layer 2) | Final review before distribution |
| ±10 precision rule + nm rule for variances >1000% | |

---

## Doc Publishing Notes

- **Doc URL as Step 1.** The target Doc + tab are supplied as a URL argument. The same skill works for any month + any target Doc; nothing is hardcoded.
- **Persistent template tab.** The Test tab is a cloned shell of the MRP tab with all row labels intact and all value columns empty. Each run fills the value cells — it does not wipe + reinsert the tab structure.
- **Table population path.** `populate_*.py` builds Docs API `batchUpdate` requests targeting each cell's `startIndex` directly. This avoids the multi-table-per-tab limitation in `sq agent-tools docs-edit update_table_cell` (which ignores `table_start_position` / `table_index`).
- **Safety guard.** The populator refuses to write if `target_tab_id == 't.ea3bz9hprpol'` (the manual MRP reference tab).
- **Roboto everywhere.** Both narrative paragraphs (when later added) and table cells use Roboto 10pt. The populator writes Roboto on each table cell's text style.
