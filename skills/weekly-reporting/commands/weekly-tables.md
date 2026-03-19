---
name: weekly-tables
description: Generate markdown performance tables from the master pacing sheet. Standalone test for table formatting. Tables match the specs in financial-reporting-weekly domain knowledge.
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "1.0"
  status: active
---

# Weekly Performance Tables

Generate markdown tables from the master pacing sheet for each Overview section of the Block Performance Digest.

Read and follow all instructions in `~/skills/weekly-tables/SKILL.md`. Load the global recipe from `~/skills/financial-reporting/SKILL.md` for formatting standards.

Execute Steps 1–8 from the SKILL.md. Output tables to:

```
~/Desktop/Nick's Cursor/Weekly Reporting/weekly_tables_YYYY-MM-DD.md
```
