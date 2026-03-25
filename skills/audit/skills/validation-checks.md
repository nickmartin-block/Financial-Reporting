---
name: validation-checks
description: Lens B audit checks — cross-workflow metric consistency, data lineage, formatting compliance, delta safety, comparison framework, tolerance consistency, data gaps, and feedback incorporation.
depends-on: [workflow-registry]
allowed-tools: []
metadata:
  author: nmart
  version: "1.0.0"
  status: active
---

# Lens B: Validation & Risk Checks

These checks audit the integrity, consistency, and correctness of the reporting pipeline. They complement (not duplicate) existing validators, which check source-to-doc accuracy within a single workflow. These checks look *across* workflows and *into* the skill definitions themselves.

---

## Check V1: Cross-Workflow Metric Consistency

**Severity if failed: HIGH**

**Goal:** Verify that the same metric reports the same value across all workflows that include it, for the same period.

**Procedure:**

1. From the workflow registry's **Shared Metric Map**, identify all metrics that appear in 2+ workflows.
2. For each workflow, read the most recent output artifact:
   - Weekly: `~/Desktop/Nick's Cursor/Weekly Reporting/weekly_summary_YYYY-MM-DD.md`
   - Monthly Flash: `~/Desktop/Nick's Cursor/Monthly Reporting/monthly_flash_YYYY_MM.md`
   - Dashboard: `~/Desktop/Nick's Cursor/Pacing Dashboard/dashboard_data.js`
3. Extract each shared metric's value from each artifact using normalization:
   - Strip `$`, `M`, `B`, `%`, `+`, `-`, commas, parentheses
   - Convert $B to $M (x1000)
   - Parse to raw number
4. Compare values within the tolerance rules from `financial-reporting.md`.
5. Flag divergences with root cause analysis:
   - **Same source, different values**: Bug — the extraction or formatting logic differs
   - **Different sources, different values**: Expected for pacing vs actuals — flag as INFO with timing context
   - **Same source, timing difference**: The sheet was updated between workflow runs — flag as INFO

**Important context:**
- Weekly summary and dashboard both read the pacing sheet → their values MUST match
- Monthly flash reads MRP Charts & Tables (actuals) → may legitimately differ from pacing sheet (forward-looking)
- Only compare metrics for the **same reporting period** (don't compare March weekly pacing to February monthly flash)

**Output format:**

```
V1 | [Metric] | [Workflow A] vs [Workflow B]
  Values: [A value] vs [B value] (delta: [amount])
  Sources: [A source] vs [B source]
  Status: [FAIL if same source + different values | INFO if different sources | PASS if match]
  Treatment: [If FAIL: specific extraction/formatting bug to investigate. If INFO: explain timing difference.]
```

---

## Check V2: Data Lineage Verification

**Severity if failed: MEDIUM**

**Goal:** Confirm each workflow reads from its documented data source. Catch hardcoded IDs that have changed.

**Procedure:**

1. For each workflow, read the command and skill files.
2. Extract every Google Sheet ID, Doc ID, tab name, range, and Slack channel ID referenced in the files.
3. Compare against the registry's documented sources.
4. Flag:
   - **Mismatch**: A file references a different ID than the registry documents
   - **Undocumented source**: A file reads from a source not in the registry
   - **Stale reference**: A hardcoded tab ID or range that may need updating for a new quarter

**Specific things to check:**

| Pattern | Example | Risk |
|---------|---------|------|
| Hardcoded tab IDs | `--tab t.mkykw9vq4coc` | Tab ID changes if doc structure changes |
| Hardcoded ranges | `--range "MRP Charts & Tables\!L11:Y90"` | Range may expand with new metrics |
| Hardcoded column indices | `col 17`, `col 21` | Column layout changes between quarters |
| Quarter-specific labels | `Q1`, `1Q26` | Must update each quarter |

**Output format:**

```
V2 | [Workflow] | [Source type] reference check
  File: [path]
  Expected: [registry value]
  Found: [actual value in file]
  Status: [PASS/WARN/FAIL]
  Treatment: [If WARN: "This hardcoded value may need updating for [quarter/period]. Verify it's still correct."]
```

---

## Check V3: Formatting Standard Compliance

**Severity if failed: MEDIUM**

**Goal:** Read recent output artifacts and verify compliance with `financial-reporting.md` formatting rules.

**Procedure:**

1. Read the most recent output markdown file for each workflow.
2. Extract all formatted values (dollar amounts, percentages, basis points, actives counts).
3. For each value, check against the formatting rules:

| Rule | Pattern to Match | Violation Example |
|------|-----------------|-------------------|
| $B = 2 decimals | `\$\d+\.\d{2}B` | `$2.9B` (missing second decimal) |
| $M >= 10 = no decimal | `\$\d{2,}M` | `$940.0M` (unnecessary decimal) |
| $M < 10 = 1 decimal | `\$\d\.\dM` | `$4M` (missing decimal) |
| % >= 10 = no decimal | `\d{2,}%` | `27.0%` (unnecessary decimal) |
| % < 10 = 1 decimal | `\d\.\d%` | `7%` (missing decimal) |
| Basis points spacing | `\d+ bps` | `30bps` (missing space) |
| Actives = 1 decimal | `\d+\.\dM` (in actives context) | `58M` (missing decimal) |
| Signs on deltas | `[+-]` prefix on all delta values | `$100M above AP` (missing + sign) |

4. Also check for:
   - Emoji spacing: space between status emoji and metric name (per `feedback_emoji_spacing.md`)
   - Square GP before GPV ordering (per `feedback_square_gp_before_gpv.md`)

**Output format:**

```
V3 | [Workflow] | Formatting violation
  File: [path]
  Line: "[the line containing the violation]"
  Rule: [which formatting rule is violated]
  Found: [the incorrectly formatted value]
  Expected: [correct format]
  Status: WARN
  Treatment: Fix the formatting template in the skill's Step [N] template section.
```

---

## Check V4: Delta Computation Safety

**Severity if failed: HIGH**

**Goal:** Verify that skill files never instruct computing deltas from rounded/display-formatted numbers.

**Background:** `feedback_no_rounded_deltas.md` — computing deltas from rounded numbers causes mismatches (e.g., rounding $939.6M to $940M then subtracting $935M gives $5M instead of $4.6M).

**Procedure:**

1. For each workflow, read the command and skill files.
2. Search for delta computation instructions. Look for patterns:
   - "Compute delta", "Calculate delta", "Compute the difference"
   - "minus", "subtract", "difference between"
   - Derived metrics: "GP contribution = ...", "OpEx contribution = ..."
3. For each computation found, verify it either:
   - References raw source values ("use raw cell values", "from the sheet")
   - References pre-computed delta columns ("columns W and X", "vs AP $")
4. Flag any computation that:
   - References a display-formatted value ("$940M minus $935M")
   - Doesn't explicitly specify raw source usage
   - Uses a previously rounded value as input

**Known safe patterns:**
- `/weekly-summary` Step 2: "Never compute a delta from rounded or display-formatted numbers. Always use raw cell values..."
- `/weekly-summary` Step 2: "use pre-computed delta columns where they exist (e.g., columns W and X for Cash ex-Commerce GP delta $)"

**Known risk areas:**
- `/weekly-summary` Step 2: "Compute deltas vs guidance/consensus as: (Q1 Pacing - Benchmark) / Benchmark" — verify this uses raw values
- `/weekly-summary` Step 2: AOI OpEx breakdown — "GP contribution = Block GP monthly delta vs AP ($)" — verify source
- `/dashboard-refresh` Step 7: "vs. Consensus: Q1 Pacing minus Q1 Consensus" — verify raw values used

**Output format:**

```
V4 | [Workflow] | Delta computation in [file]:[step]
  Instruction: "[the computation instruction]"
  Status: [PASS if explicitly uses raw values | WARN if ambiguous | FAIL if uses rounded values]
  Treatment: [If WARN/FAIL: "Add explicit instruction: 'Use raw cell values from col [X], not display-formatted amounts.'"]
```

---

## Check V5: Comparison Framework Compliance

**Severity if failed: HIGH**

**Goal:** Verify each workflow uses the correct comparison scenario for the current quarter.

**Background:** Financial-reporting.md defines: Q1→AP, Q2→Q2OL, Q3→Q3OL, Q4→Q4OL. A workflow built in Q1 might hardcode "vs. AP" labels that won't be correct in Q2.

**Procedure:**

1. Determine the current quarter from today's date.
2. For each workflow, read the command file.
3. Search for comparison point references:
   - Column references: "col 4" (vs AP $), "col 5" (vs AP %)
   - Label references: "vs. AP", "vs. Q1OL", "vs. Q2OL"
   - Template text: "above/below AP", "ahead of/behind AP"
4. Verify:
   - The comparison point matches the current quarter per the recipe
   - The skill handles quarter transitions (does it dynamically select the comparison point, or is it hardcoded?)

**Known patterns:**
- `/monthly-flash` Step 2: "Comparison point: Q1 → AP (columns 4-5). For Q2 use Q2OL, Q3 use Q3OL, Q4 use Q4OL per the financial-reporting recipe." — GOOD (documents the rotation)
- `/weekly-summary` Step 2: References col 17 (Q1 Pacing) and col 18 (Q1 AP) — check if these are Q1-specific hardcodes
- `/dashboard-refresh` Step 4: Column 18 = "Q1 Annual Plan (AP)" — hardcoded to Q1/AP

**Output format:**

```
V5 | [Workflow] | Comparison framework check
  Current quarter: Q[N] → expected comparison: [AP/Q2OL/Q3OL/Q4OL]
  File: [path]
  Found: [what the file references]
  Status: [PASS if dynamic | WARN if hardcoded but correct for this quarter | FAIL if hardcoded and wrong]
  Treatment: [If WARN: "This hardcoded reference is correct for Q[N] but will need manual update for Q[N+1]. Consider parameterizing." If FAIL: "Update comparison point from [old] to [new]."]
```

---

## Check V6: Tolerance Consistency

**Severity if failed: MEDIUM**

**Goal:** Verify all validators use consistent rounding tolerances.

**Procedure:**

1. Read each validator skill file:
   - `~/skills/weekly-reporting/skills/weekly-validate.md`
   - `~/skills/monthly-flash/commands/monthly-validate.md`
   - Dashboard `validate.py`
2. Extract the tolerance table from each.
3. Compare tolerances across validators for the same value type.
4. Flag any inconsistencies.

**Reference: Registry's Validator Tolerance Comparison table.** Verify it's still accurate by reading the actual files.

**Output format:**

```
V6 | Tolerance consistency across validators
  | Value Type | Weekly | Monthly | Dashboard |
  | ...        | ...    | ...     | ...       |
  Status: [PASS if all consistent | WARN if minor differences | FAIL if significant divergence]
  Treatment: [If inconsistent: "Standardize tolerances across all validators. Recommend using the stricter threshold: [value]."]
```

---

## Check V7: Data Gap Inventory

**Severity: INFO (aggregation, not a failure)**

**Goal:** Aggregate all known data gaps, missing metrics, and placeholders across all workflows into a single view.

**Procedure:**

1. For each workflow's most recent output artifact, search for:
   - `[DATA MISSING: ...]`
   - `[MANUAL: ...]` or `[MANUAL]`
   - `[DATA GAP: ...]`
   - `--` in data cells (dashboard)
   - Any red color markers or placeholder text

2. For each workflow's skill files, search for:
   - Metrics marked as "not available" or "skip"
   - Commented-out metric rows
   - Known gaps documented in the skill

3. Produce an aggregate inventory:

| Gap | Affected Workflows | Source | Status |
|-----|-------------------|--------|--------|
| [metric/field] | [list] | [why missing] | [known/new] |

**Output format:**

```
V7 | Data Gap Inventory — [N] total gaps across [N] workflows
  [Table of gaps]
  New gaps since last audit: [list or "none"]
  Treatment: [For each actionable gap: what would resolve it — new MCP metric, sheet formula, manual input process]
```

---

## Check V8: Feedback Incorporation Audit

**Severity if failed: MEDIUM**

**Goal:** Verify that each lesson captured in memory feedback files has been incorporated into the relevant skill files.

**Procedure:**

1. Read all feedback memory files from `~/.claude/projects/-Users-nmart-Desktop-Nick-s-Cursor/memory/feedback_*.md`.
2. For each feedback file, extract:
   - The rule (what to do or not do)
   - The affected workflow(s) or skill(s)
3. For each rule, verify it's reflected in the relevant skill file:

| Feedback File | Rule | Where to Check |
|---------------|------|----------------|
| `feedback_no_rounded_deltas.md` | Never compute deltas from rounded numbers | weekly-summary Step 2, dashboard-refresh Step 7 |
| `feedback_cashapp_commerce_gp_source.md` | Use columns W/X for Cash App Commerce GP | weekly-summary Step 2 |
| `feedback_square_gp_before_gpv.md` | Lead Square section with GP, then GPV | weekly-summary Step 4 template |
| `feedback_emoji_spacing.md` | Space between emoji and metric name | weekly-summary Step 4 formatting rules |
| `feedback_dashboard_tues_anchor.md` | Dashboard deltas anchor to Tuesday Innercore share (col 28) | dashboard-refresh Step 4, Step 7 |
| `feedback_opex_gaap_nongaap.md` | Commentary uses Non-GAAP V/A/F | monthly-flash template, MRP narrative |
| `feedback_mrp_gaps_as_placeholders.md` | Data gaps → red placeholders, not supplements | MRP publishing (future) |

4. For each rule, grep the relevant skill file for evidence the rule is implemented.

**Output format:**

```
V8 | [Feedback file] | Incorporation check
  Rule: [the lesson]
  Skill file: [path]
  Evidence: [matching text found, or "NOT FOUND"]
  Status: [PASS if found | FAIL if not found]
  Treatment: [If FAIL: "Add this instruction to [file] at [section]: '[instruction text]'"]
```
