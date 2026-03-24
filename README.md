# Block FP&A Reporting — Automation

Automated financial reporting for Block FP&A using Claude Code. Single slash commands that generate, publish, and validate management reports from governed spreadsheet data.

---

## Reports

### Weekly Performance Digest (`/weekly-summary`)

Generates the weekly Block Performance Digest with emoji-coded narrative, detailed overview sections, and formatted performance tables. Pulls from the master pacing sheet and Slack digests, publishes to a dated Google Doc tab, and validates every table cell against the source.

**Pipeline:** Auth → Sheet read → Slack digest scan → Narrative + tables → Save .md → Publish to Google Doc (create tab, insert markdown, set 10pt body font, fix nesting/spacing/bold/colors) → Validate (299 cells) → Slack notification with key takeaways

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
| 4 | Generate Summary (emoji narrative) + Overview sections (tables + fact lines) |
| 5 | Save dated .md file |
| 5.5 | Publish to Google Doc — create tab, insert markdown, set 10pt body font, fix bullet nesting, fix table spacing, bold labels, apply green/red conditional formatting, verify missing lines |
| 6 | Validate every table cell against source sheet |
| 7 | Report results to user |
| 8 | Send Slack DM with key takeaways + doc link |

---

## Quick Start

1. Open Claude Code in the project directory
2. Run a command:

```
/weekly-summary     # Full weekly digest pipeline
/monthly-flash      # Full monthly flash pipeline
```

Both commands handle auth, data extraction, narrative generation, Google Doc publishing, and validation end-to-end.
