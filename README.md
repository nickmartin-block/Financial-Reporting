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
├── skills/                          Reporting deliverables — each subdir bundles the slash commands and domain skills for one deliverable
│   ├── weekly-reporting/            Weekly Performance Digest
│   │   ├── commands/                  Slash commands: /weekly-summary, /weekly-tables, /weekly-validate
│   │   ├── skills/                    Domain skills: table specs, validation logic, formatting recipe
│   │   └── gdrive/                    Google Drive CLI (shared tool)
│   │
│   ├── monthly-flash/               Monthly Topline Flash
│   │   ├── commands/                  Slash commands: /monthly-flash, /monthly-validate
│   │   ├── skills/                    Domain skills: formatting recipe (inherited)
│   │   └── flash-data/                /flash-data command + sourcing skill + Python helpers
│   │
│   ├── monthly-reporting-pack/      Monthly Management Reporting Pack
│   │   ├── commands/                  Slash commands: /mrp, /mrp-data, /mrp-validate
│   │   └── skills/                    Domain skills: MRP-specific logic, data packet schema
│   │
│   ├── pacing-dashboard/            Pacing Dashboard
│   │   └── commands/                  Slash commands: /dashboard-refresh
│   │
│   └── audit/                       Audit Layer
│       ├── commands/                  Slash commands: /audit, /audit-workflow
│       └── skills/                    Domain skills: workflow registry, check definitions
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

## Quick Start

To run Numerius on a fresh machine:

1. **Clone the repo** anywhere on disk and capture the path:
   ```bash
   git clone https://github.com/nickmartin-block/Corporate-Financial-Reporting.git
   cd Corporate-Financial-Reporting && export REPO_ROOT=$(pwd)
   ```

2. **Wire deliverables into Claude Code's discovery path.** Symlink each `skills/<deliverable>/` into `~/skills/`, then symlink each deliverable's `commands/*.md` into `~/.claude/commands/` so the slash commands are invokable from any working directory:
   ```bash
   mkdir -p ~/skills ~/.claude/commands
   for d in monthly-flash monthly-reporting-pack weekly-reporting pacing-dashboard audit; do
     ln -s "$REPO_ROOT/skills/$d" ~/skills/$d
     for cmd in "$REPO_ROOT/skills/$d/commands/"*.md; do
       ln -s "$cmd" ~/.claude/commands/$(basename "$cmd")
     done
   done
   ```

3. **Authenticate the data sources** (one-time per machine):
   - **Google Drive / Sheets / Docs**: `cd ~/skills/weekly-reporting/gdrive && uv run gdrive-cli.py auth login`
   - **Block Data MCP**, **Snowflake MCP**, **Slack MCP**: configure each in Claude Code's MCP server settings; the first invocation surfaces the OAuth prompt or auth instructions

4. **Smoke test.** Open Claude Code in any directory and run `/weekly-validate` — it auth-checks Google Drive and returns a validation report, confirming the pipeline is wired correctly.

Once set up, day-to-day usage is just the slash command for the target deliverable (see [Deliverables](#deliverables) above).
