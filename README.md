# Block FP&A Reporting — Automation

Automated financial reporting for Block FP&A using Claude Code. Single slash commands that generate, publish, and validate management reports from governed spreadsheet data.

---

## Reports

### Weekly Performance Digest (`/weekly-summary`)

Generates the weekly Block Performance Digest with emoji-coded narrative, detailed overview sections, and formatted performance tables. Pulls from the master pacing sheet and Slack digests, publishes to a dated Google Doc tab, and validates every table cell against the source.

**Pipeline:** Auth → Sheet read → Slack digest scan → Generate commentary → Save .md → Publish to Google Doc (populate template tables via batch-update, insert commentary, format) → Validate (299 cells) → Slack notification with key takeaways

**Pre-requisite:** Before running, duplicate the template tab in the [Weekly Performance Digest Google Doc](https://docs.google.com/document/d/1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0) and rename it to the current week's date (M/D format, e.g., `3/31`). The template tab contains pre-formatted tables with row/column labels and styling — the skill populates values and inserts commentary around them.

See [`skills/weekly-reporting/`](skills/weekly-reporting/) for full details.

### Monthly Topline Flash (`/monthly-flash`)

Generates the monthly topline flash email with preliminary close results. Covers 21 metrics across gross profit, volume, and profitability — all validated against the MRP Charts & Tables sheet (106 values checked).

See [`skills/monthly-flash/`](skills/monthly-flash/) for full details.

---

## Architecture

```
skills/
  ├── weekly-reporting/              Weekly Performance Digest
  │   ├── commands/                    /weekly-summary, /weekly-tables, /weekly-validate
  │   ├── skills/                      Formatting recipe, table specs, validation logic
  │   └── gdrive/                      Google Drive CLI (shared tool)
  │
  └── monthly-flash/                 Monthly Topline Flash
      ├── commands/                    /monthly-flash
      └── skills/                      Formatting recipe (inherited)
```

Both reporting systems share:
- **`financial-reporting.md`** — global formatting recipe (rounding, signs, comparison framework, deviation handling)
- **`gdrive-cli.py`** — CLI tool for Google Sheets, Docs, and Slides operations
- **Validation pattern** — independent re-read of source data, normalize + compare with rounding tolerance, PASS/FAIL report

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

Both commands handle auth, data extraction, narrative generation, Google Doc publishing, and validation end-to-end.
