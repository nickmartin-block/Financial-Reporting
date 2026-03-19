---
name: weekly-validate
description: Validate the published Block Performance Digest Google Doc against the source pacing sheet. Compares every table cell value-by-value. Run after /weekly-summary completes.
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "2.0"
  status: active
---

# Weekly Digest — Data Validation

Read and follow all instructions in `~/skills/weekly-validate/SKILL.md`. Load `~/skills/weekly-tables/SKILL.md` for table column mapping and formatting rules.

Execute Steps 1–9 from the SKILL.md. Save the validation report to:

```
~/Desktop/Nick's Cursor/Weekly Reporting/validation_YYYY-MM-DD.md
```
