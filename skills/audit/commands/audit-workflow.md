---
name: audit-workflow
description: Run a focused audit on a single financial reporting workflow. Pass the workflow name as an argument (weekly-summary, dashboard-refresh, or monthly-flash). Produces a scoped report with efficiency and risk findings.
allowed-tools:
  - Read
  - Write
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
metadata:
  author: nmart
  version: "1.0.0"
  status: active
---

# Single Workflow Audit

Run a focused audit on **one workflow**.

**Usage:** `/audit-workflow <name>` where name is one of:
- `weekly-summary`
- `dashboard-refresh`
- `monthly-flash`

**Dependencies:** Load these skills in order:
1. `~/skills/weekly-reporting/skills/financial-reporting.md` — formatting standards
2. `~/skills/audit/skills/workflow-registry.md` — workflow inventory
3. `~/skills/audit/skills/latency-checks.md` — Lens A definitions
4. `~/skills/audit/skills/validation-checks.md` — Lens B definitions
5. `~/skills/audit/skills/audit-engine.md` — orchestrator

**Scope:** Single workflow — run all checks except V1 (cross-workflow consistency requires multiple workflows).

**Execution:** Follow the audit engine's execution sequence (Phase 1–5) with scope limited to the specified workflow. Save the report to:
```
~/Desktop/Nick's Cursor/Audit Reports/audit_{workflow-name}_YYYY-MM-DD.md
```

Report back to Nick with the executive summary and top findings.
