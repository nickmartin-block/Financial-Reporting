---
name: weekly-tables
description: Populate pre-formatted template tables in the Google Doc with values from the master pacing sheet via Docs API batch-update. Standalone test for table population.
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "2.0"
  status: active
---

# Weekly Performance Tables

Populate pre-formatted template tables in the Block Performance Digest Google Doc with values from the master pacing sheet. The template tab (created by Nick) contains 5 tables with row labels, column headers, and styling — but empty data cells. This command reads Sheet values and writes them into the Doc via Docs API batch-update.

Read and follow all instructions in `~/skills/weekly-reporting/skills/weekly-tables.md`. Load the global recipe from `~/skills/weekly-reporting/skills/financial-reporting.md` for formatting standards.

Execute Steps 1–8 from the SKILL.md. In standalone mode, the skill finds the template tab by date match and populates tables directly in the Google Doc. Report the cell count and any issues.
