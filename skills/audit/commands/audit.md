---
name: audit
description: Run a full audit of all financial reporting workflows — assesses latency/efficiency and validation/risk across weekly summary, pacing dashboard, and monthly flash. Produces an actionable report with diagnosis and treatment for every finding.
allowed-tools:
  - Read
  - Write
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
metadata:
  author: nmart
  version: "1.0.0"
  status: active
---

# Full Pipeline Audit

Run a comprehensive audit across **all registered financial reporting workflows**.

**Dependencies:** Load these skills in order:
1. `~/skills/weekly-reporting/skills/financial-reporting.md` — formatting standards
2. `~/skills/audit/skills/workflow-registry.md` — workflow inventory
3. `~/skills/audit/skills/latency-checks.md` — Lens A definitions
4. `~/skills/audit/skills/validation-checks.md` — Lens B definitions
5. `~/skills/audit/skills/audit-engine.md` — orchestrator

**Scope:** Full Audit — all workflows, all checks including V1 (cross-workflow consistency).

**Execution:** Follow the audit engine's execution sequence (Phase 1–5). Save the report to:
```
~/Desktop/Nick's Cursor/Audit Reports/audit_YYYY-MM-DD.md
```

Report back to Nick with the executive summary and top findings.
