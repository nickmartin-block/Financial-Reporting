---
name: latency-checks
description: Lens A audit checks — identifies parallelization opportunities, redundant reads, API call waste, and dependency chain depth in financial reporting workflows.
depends-on: [workflow-registry]
allowed-tools: []
metadata:
  author: nmart
  version: "1.0.0"
  status: active
---

# Lens A: Latency & Efficiency Checks

Read each workflow's skill and command files (listed in the workflow registry). Analyze the step structure for optimization opportunities. Do NOT re-execute workflows — this is static analysis of the definitions.

---

## Check L1: Parallelization Opportunities

**Goal:** Find sequential steps that operate on independent data sources and could run concurrently.

**Procedure:**

1. For each workflow in the registry, read the command file.
2. List every step and its data dependencies (what it reads, what it produces).
3. Build a dependency graph: Step B depends on Step A if B reads something A produces.
4. Flag any pair of sequential steps where neither depends on the other's output.

**Known findings to verify:**

| Workflow | Steps | Current | Why Parallelizable |
|----------|-------|---------|-------------------|
| `/weekly-summary` | Step 2 (read pacing sheet) + Step 3 (search Slack) | Sequential | Independent data sources — sheet data and Slack messages have no dependency |
| `/dashboard-refresh` | Step 2 (read pacing sheet) + Step 8 (extract Innercore commentary) | Sequential | Independent reads — pacing data and commentary are separate sources |
| `/monthly-flash` | Step 2 (read sheet) is the only data read | N/A | Single source — no parallelization opportunity in the read phase |

**Output format per finding:**

```
L1 | [Workflow] | Steps [X] + [Y] are sequential but independent
  Diagnosis: [Step X] reads [source A], [Step Y] reads [source B]. No data dependency between them.
  Treatment: Add "Run Steps X and Y in parallel" instruction. In the command file, restructure as concurrent reads.
  Est. savings: ~[N] seconds (one fewer serial API call round-trip)
```

---

## Check L2: Redundant Data Reads

**Goal:** Find cases where the same data source is read multiple times within a single pipeline invocation.

**Procedure:**

1. For each workflow, scan all steps (including validation) for API calls: `sheets read`, `docs get`, `docs extract-tables`, `docs read`.
2. Group by target (Sheet ID + range, or Doc ID + tab).
3. Flag any target read more than once.

**Known findings to verify:**

| Workflow | Source | Read Count | Steps |
|----------|--------|------------|-------|
| `/weekly-summary` | Pacing Sheet `1hvKbg3t...` | 2 | Step 2 (generate), Step 6 validate (re-reads) |
| `/weekly-summary` | Doc `1FU4In29v...` | 3+ | Step 5.5a (find tab), after 5.5b (re-read for commentary insertion), after 5.5d (re-read for formatting) |
| `/monthly-flash` | MRP Charts `15j9tou-...` | 2 | Step 2 (generate), Step 6 validate (re-reads) |
| `/monthly-flash` | Doc `1S--3vA6o...` | 2+ | Step 5a (clear), Step 5e (verify), Step 6 validate (re-reads) |
| `/dashboard-refresh` | Pacing Sheet `1hvKbg3t...` | 2 | Step 2 (skill reads), Step 11 (validate.py re-reads) |

**Evaluation criteria:**
- Validation re-reads are **by design** (independent verification). Flag as INFO, not WARN.
- Doc re-reads due to index shifts after batch updates are **necessary** (indices change after each write). Flag as INFO with a note on whether a smarter batching strategy could reduce reads.
- Redundant reads within the generation phase (same source, same step range) are genuine WARN findings.

**Output format:**

```
L2 | [Workflow] | [Source] read [N] times across Steps [list]
  Diagnosis: [Explain which reads are necessary vs redundant]
  Treatment: [If reducible: "Cache the result from Step X and reuse in Step Y." If by design: "INFO — validation intentionally re-reads for independence."]
  Est. savings: ~[N] seconds per eliminated read
```

---

## Check L3: API Call Inventory

**Goal:** Count total API calls per workflow and identify the most expensive operations.

**Procedure:**

1. For each workflow, scan all steps for external calls:
   - `sheets read` — ~3-5s
   - `docs get` / `docs get --include-tabs` — ~5-10s
   - `docs extract-tables` — ~5-8s
   - `docs insert-markdown` — ~3-5s
   - `docs batch-update` (batch JSON) — ~3-8s
   - `Slack get-channel-messages` — ~2-3s
   - `Slack post-message` — ~2s
   - Block Cell upload — ~5-10s
   - `validate.py` (Python script with Snowflake) — ~10-30s

2. For each workflow, produce a summary:

| Workflow | Reads | Writes | Deploys | Total | Est. Duration |
|----------|-------|--------|---------|-------|--------------|
| `/weekly-summary` | ? | ? | 0 | ? | ? |
| `/dashboard-refresh` | ? | ? | 1 | ? | ? |
| `/monthly-flash` | ? | ? | 0 | ? | ? |

3. Flag workflows with high call counts and suggest batch consolidation where possible.

**Specific things to look for:**
- Multiple `docs get` calls that could be consolidated if index tracking were smarter
- Separate `insertText` + `updateTextStyle` + `updateParagraphStyle` requests that could be batched into a single batch-update
- Commentary extraction that could reuse an already-fetched doc structure

**Output format:**

```
L3 | [Workflow] | [N] API calls ([R] reads, [W] writes)
  Heaviest operation: [Step X — description] (~[N]s)
  Potential reduction: [describe consolidation opportunity]
  Est. savings: ~[N] seconds
```

---

## Check L4: Dependency Chain Depth

**Goal:** Trace `depends-on` declarations across skills and flag deep or redundant chains.

**Procedure:**

1. For each workflow's command file, identify all skills it loads (via `depends-on` or explicit "Load skill X" instructions).
2. For each loaded skill, recursively follow its `depends-on` field.
3. Build the full dependency tree.
4. Flag:
   - Chains deeper than 3 levels
   - The same skill loaded via multiple paths (redundant)
   - Missing `depends-on` declarations (skill X references skill Y but doesn't declare it)

**Known dependency chains:**

| Workflow | Chain |
|----------|-------|
| `/weekly-summary` | → financial-reporting, weekly-tables, weekly-validate, gdrive |
| `/dashboard-refresh` | → financial-reporting, gdrive |
| `/monthly-flash` | → financial-reporting, gdrive |

**Output format:**

```
L4 | [Workflow] | Dependency chain depth: [N]
  Chain: [A] → [B] → [C] → ...
  [PASS if ≤3, WARN if >3, INFO if redundant loads detected]
```

---

## Check L5: Step Count Analysis

**Goal:** Flag workflows with high step counts that may benefit from consolidation.

**Procedure:**

1. Count numbered steps (including sub-steps like 5.5a, 5.5b, etc.) in each command file.
2. Compare against complexity thresholds:
   - ≤7 steps: PASS
   - 8-12 steps: INFO (normal for complex workflows)
   - >12 steps: WARN (consider whether steps can be merged)

**Known step counts:**

| Workflow | Steps | Sub-steps | Total |
|----------|-------|-----------|-------|
| `/weekly-summary` | 8 | 5 (5.5a-e) | 13 |
| `/dashboard-refresh` | 13 | 0 | 13 |
| `/monthly-flash` | 7 | 5 (5a-e) | 12 |

**Output format:**

```
L5 | [Workflow] | [N] total steps
  [PASS/INFO/WARN]
  [If WARN: suggest which steps could be merged and why]
```
