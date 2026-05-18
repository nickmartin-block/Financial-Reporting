# Numerius — Block Financial Reporting Agent

Numerius is Block's financial reporting agent. It automates the production, publication, and validation of the CFO's core financial deliverables — sourcing governed data, enforcing formatting standards, and validating every output before delivery.

The system is built as a collection of Claude Code skills, each mapped to a specific deliverable. Two governing documents sit at the repo root and apply to every skill:

- **[`numerius.md`](numerius.md)** — Agent identity, non-negotiable principles, 5-phase workflow, deliverable registry
- **[`financial-reporting.md`](financial-reporting.md)** — Global formatting recipe: rounding, signs, product names, terminology, style rules

---

## Deliverables

### Weekly Performance Digest — `automated`

The Tuesday leadership share. Emoji-coded performance narrative with 5 formatted tables covering gross profit, AOI, Cash App inflows, and Square GPV. Published to Google Docs with cell-level validation.

| Command | What it does |
|---------|-------------|
| `/weekly-summary` | End-to-end: sheet read → narrative → publish → validate |
| `/weekly-tables` | Populate 5 pre-formatted template tables via Docs API batch-update |
| `/weekly-validate` | Cell-by-cell validation of published doc against source sheet |

**Pre-requisite:** Before running, duplicate the template tab in the [Weekly Performance Digest Google Doc](https://docs.google.com/document/d/1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0) and rename it to the current week's date (M/D format, e.g., `3/31`).

### Monthly Topline Flash — `automated`

Preliminary month-end close results. 21 metrics across gross profit, volume, and profitability — sourced from Block Data MCP and Snowflake (Hyperion `finstmt_master`), populated to the MRP Charts & Tables validation sheet, and validated cell-by-cell against the published Doc (106 values checked). Adapts format for intra-quarter months vs. quarter-end.

| Command | What it does |
|---------|-------------|
| `/flash-data` | Fetch metrics from BDM + Snowflake → populate MRP Charts & Tables validation sheet + emit JSON packet |
| `/monthly-flash` | End-to-end: data fetch → narrative → publish → validate |
| `/monthly-validate` | Metric-by-metric validation of published doc against validation sheet |

### Monthly Management Reporting Pack — `preliminary`

The monthly MRP delivered to the CFO and senior leadership. Full P&L narrative with brand breakouts (Cash App, Square, Other Brands), operating expense detail, and flux commentary. Data sourced from the Block Metric Store via Block Data MCP, with driver narratives pulled from the flux commentary sheet.

| Command | What it does |
|---------|-------------|
| `/mrp-data` | Fetch all metrics from Block Data MCP → structured JSON data packet |
| `/mrp` | Full pipeline: data fetch → parallel narrative generation → publish → validate |
| `/mrp-validate` | Post-publish validation against data packet and optional reference MRP |

Skills are built and functional. Pipeline is under iteration as we refine the narrative structure and flux commentary integration.

### Board of Directors Pre-Read — `planned`

The quarterly board pre-read covering financial highlights, key watchpoints, quarterly and full-year performance, annual plan overview, and competitive landscape. This is the most narrative-heavy deliverable — Numerius will handle metric population, table generation, and formatting, while strategic commentary and watchpoints remain human-authored.

No skills built yet. The global recipe and agent definition already cover the formatting and terminology standards this deliverable requires.

---

## Architecture

```
Corporate-Financial-Reporting/
│
├── numerius.md                      Agent identity & operating manual
├── financial-reporting.md           Global formatting recipe (v1.3.0)
│
├── skills/
│   ├── weekly-reporting/            Weekly Performance Digest
│   │   ├── commands/                  /weekly-summary, /weekly-tables, /weekly-validate
│   │   ├── skills/                    Table specs, validation logic, formatting recipe
│   │   └── gdrive/                    Google Drive CLI (shared tool)
│   │
│   ├── monthly-flash/               Monthly Topline Flash
│   │   ├── commands/                  /monthly-flash, /monthly-validate
│   │   ├── skills/                    Formatting recipe (inherited)
│   │   └── flash-data/                /flash-data command, sourcing skill, Python helpers
│   │
│   ├── monthly-reporting-pack/      Monthly Management Reporting Pack
│   │   ├── commands/                  /mrp, /mrp-data, /mrp-validate
│   │   └── skills/                    MRP-specific logic, data packet schema
│   │
│   ├── pacing-dashboard/            Pacing Dashboard
│   │   └── commands/                  /dashboard-refresh
│   │
│   └── audit/                       Audit Layer
│       ├── commands/                  /audit, /audit-workflow
│       └── skills/                    Workflow registry, check definitions
│
└── pacing-dashboard/                Dashboard static site (HTML/CSS/JS)
```

### Shared infrastructure

All skills inherit from the two root-level governing documents and share:

- **`financial-reporting.md`** — Formatting recipe: rounding, signs, comparison framework, product names, terminology, deviation handling
- **`gdrive-cli.py`** — CLI tool for Google Sheets, Docs, and Slides operations
- **Block Data MCP** — Governed metric access via the Block Metric Store (preferred for any metric BMS publishes)
- **Snowflake** — Direct query access for Hyperion (`app_hexagon.schedule2.finstmt_master`) and warehouse-only metrics; fallback when BDM doesn't have the metric
- **Validation pattern** — Every deliverable gets a post-publish validation pass: independent re-read of source data, normalize + compare with rounding tolerance, PASS/FAIL report

### 5-phase workflow

Every command follows the same phased workflow. Each phase has an explicit gate — no phase may be skipped. See [`numerius.md`](numerius.md) for full details.

```
Source → Validate Source → Populate → Review → Deliver & Validate
```

---

## Weekly Digest Steps

| Step | What it does |
|------|-------------|
| 1 | Auth check (Google Drive + Slack) |
| 2 | Read master pacing sheet (20+ metrics, monthly + quarterly) |
| 3 | Scan Slack for Cash App and Square brand digests |
| 4 | Generate Summary (emoji narrative) + Overview commentary (no tables in markdown) |
| 5 | Save dated .md file |
| 5.5a | Find Nick's pre-existing template tab (by date match) |
| 5.5b | Populate template tables via Docs API batch-update (Roboto 10pt, center-aligned, conditional colors) |
| 5.5d | Insert commentary sections between headings and tables (bottom-to-top) |
| 5.5e | Format commentary — 10pt font, bullet nesting, bold labels, yellow highlights |
| 6 | Validate every table cell against source sheet |
| 7 | Report results to user |
| 8 | Send Slack DM with key takeaways + doc link |

---

## Quick Start

1. Open Claude Code in the project directory
2. For weekly digest:
   - **Duplicate the template tab** in the Google Doc and rename to this week's date (e.g., `3/31`)
   - Run `/weekly-summary`
3. For monthly flash:
   - Run `/monthly-flash`
4. For MRP:
   - Run `/mrp-data` to fetch and inspect the data packet
   - Run `/mrp` for the full pipeline

All commands handle auth, data extraction, formatting, publishing, and validation end-to-end.
