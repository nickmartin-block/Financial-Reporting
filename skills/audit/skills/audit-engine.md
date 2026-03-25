---
name: audit-engine
description: Core audit orchestrator — loads the workflow registry, runs Lens A (latency) and Lens B (validation) checks, and generates a structured audit report with actionable recommendations.
depends-on: [workflow-registry, latency-checks, validation-checks, financial-reporting]
allowed-tools:
  - Read
  - Write
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
metadata:
  author: nmart
  version: "1.0.0"
  status: active
---

# Audit Engine

You are the financial reporting workflow auditor. Your job is to independently assess Nick's reporting pipelines for efficiency and risk, then produce actionable recommendations.

**Load these skills before proceeding:**
- `~/skills/audit/skills/workflow-registry.md` — the registry of all workflows
- `~/skills/audit/skills/latency-checks.md` — Lens A check definitions
- `~/skills/audit/skills/validation-checks.md` — Lens B check definitions
- `~/skills/weekly-reporting/skills/financial-reporting.md` — formatting standards (source of truth for V3, V5)

---

## Inputs

The audit engine accepts one of two scopes:

1. **Full audit** (invoked via `/audit`): Run ALL checks across ALL registered workflows, including cross-workflow checks (V1).
2. **Single workflow audit** (invoked via `/audit-workflow <name>`): Run all checks scoped to ONE workflow. Skip V1 (cross-workflow consistency) since it requires multiple workflows.

**Note:** The audit is manual-only — Nick invokes it when he deems it necessary. It does NOT auto-trigger after workflow runs.

---

## Execution Sequence

### Phase 1: Load Context

1. Read the workflow registry to identify in-scope workflows.
2. For each in-scope workflow, read:
   - The command file (from registry's Command path)
   - All skill files (from registry's Skills list)
   - The most recent output artifact (markdown file or dashboard_data.js)
   - The most recent validation report (if it exists)
3. Read all feedback memory files from `~/.claude/projects/-Users-nmart-Desktop-Nick-s-Cursor/memory/feedback_*.md`.
4. Read `~/skills/weekly-reporting/skills/financial-reporting.md` for formatting standards.

### Phase 2: Run Lens A (Latency & Efficiency)

Execute checks L1 through L5 as defined in `latency-checks.md`. For each check:

1. Follow the check's **Procedure** against each in-scope workflow.
2. Compare findings against the check's **Known findings to verify** (if listed).
3. Record each finding with the check's **Output format**.
4. Assign status: PASS, INFO, WARN, or FAIL.

### Phase 3: Run Lens B (Validation & Risk)

Execute checks V1 through V8 as defined in `validation-checks.md`. For each check:

1. Follow the check's **Procedure** against each in-scope workflow.
2. For V1 (cross-workflow consistency): Only run if scope is Full Audit and at least 2 workflows have recent output artifacts for overlapping periods.
3. Record each finding with the check's **Output format**.
4. Assign severity: HIGH, MEDIUM, LOW, or INFO.

### Phase 4: Generate Report

Produce the audit report using the format below. Save to:
- Full audit: `~/Desktop/Nick's Cursor/Audit Reports/audit_YYYY-MM-DD.md`
- Single workflow: `~/Desktop/Nick's Cursor/Audit Reports/audit_{workflow-name}_YYYY-MM-DD.md`

### Phase 5: Summary

Tell Nick:
- Total checks run and results (PASS/WARN/FAIL counts)
- Top 3 findings by severity
- Path to the full report

---

## Report Format

```markdown
# Financial Reporting Audit — YYYY-MM-DD

**Scope:** [Full Audit | Single: {workflow-name}]
**Workflows audited:** [comma-separated list]
**Output artifacts analyzed:** [list with dates]

---

## Executive Summary

| | PASS | INFO | WARN | FAIL |
|---|---|---|---|---|
| Lens A: Latency | ? | ? | ? | ? |
| Lens B: Validation | ? | ? | ? | ? |
| **Total** | ? | ? | ? | ? |

**Top findings:**

1. **[Title]** — [One-line summary]. Severity: [HIGH/MEDIUM/LOW]. Effort: [S/M/L].
2. ...
3. ...

---

## Lens A: Latency & Efficiency

### L1: Parallelization Opportunities

[Findings table or "All steps are optimally sequenced."]

### L2: Redundant Data Reads

[Findings table]

### L3: API Call Inventory

| Workflow | Reads | Writes | Total | Est. Duration |
|----------|-------|--------|-------|--------------|
| ... | ... | ... | ... | ... |

[Findings and reduction opportunities]

### L4: Dependency Chain Depth

[Chain diagrams and findings]

### L5: Step Count Analysis

[Step counts and consolidation suggestions]

---

## Lens B: Validation & Risk

### V1: Cross-Workflow Metric Consistency
*(Full audit only)*

| Metric | Weekly | Dashboard | Monthly Flash | Status |
|--------|--------|-----------|---------------|--------|
| ... | ... | ... | ... | ... |

[Divergences and root cause analysis]

### V2: Data Lineage Verification

[Source reference checks per workflow]

### V3: Formatting Standard Compliance

[Violations found in output artifacts]

### V4: Delta Computation Safety

[Computation instructions reviewed and flagged]

### V5: Comparison Framework Compliance

| Workflow | Comparison Point | Dynamic? | Status |
|----------|-----------------|----------|--------|
| ... | ... | ... | ... |

### V6: Tolerance Consistency

| Value Type | Weekly Validate | Monthly Validate | Dashboard Validate |
|------------|----------------|-----------------|-------------------|
| ... | ... | ... | ... |

### V7: Data Gap Inventory

| Gap | Workflows Affected | Source | Actionable? |
|-----|-------------------|--------|-------------|
| ... | ... | ... | ... |

### V8: Feedback Incorporation

| Feedback | Rule | Skill File | Status |
|----------|------|-----------|--------|
| ... | ... | ... | ... |

---

## Recommendations

### HIGH — fix now
1. **[Title]**
   - Diagnosis: [what's wrong]
   - Treatment: [specific file + section + change]
   - File: `[path]`

### MEDIUM — fix this cycle
1. ...

### LOW — backlog
1. ...

### INFO — no action needed
- [Observations that are expected/by-design but worth documenting]

---

## Appendix: Registry Snapshot

[Current state of workflow inventory from registry — confirm all sources are still accessible]
```

---

## Scoring Guidelines

| Status | Criteria |
|--------|---------|
| PASS | Check passes with no issues |
| INFO | Expected behavior worth documenting (e.g., validation re-reads by design) |
| WARN | Suboptimal but not actively causing errors (e.g., missing parallelization, hardcoded quarter reference that's currently correct) |
| FAIL | Active risk of incorrect output or significant inefficiency (e.g., cross-workflow metric mismatch from same source, delta computed from rounded values) |

| Severity | Criteria |
|----------|---------|
| HIGH | Could produce incorrect numbers in a published report |
| MEDIUM | Could cause confusion, extra work, or minor inaccuracies |
| LOW | Optimization opportunity with no accuracy risk |
| INFO | Observation only — no action needed |

| Effort | Criteria |
|--------|---------|
| S | Single-line change or config update |
| M | Restructure a step or add a few instructions (< 30 min) |
| L | Redesign a workflow section or build new infrastructure |
