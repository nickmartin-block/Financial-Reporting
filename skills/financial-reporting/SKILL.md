---
name: financial-reporting
description: Global recipe for Block FP&A financial reporting. Governs all reporting agents — formatting standards, metric formats, comparison framework, style rules, and deviation handling. Load this skill first before any financial reporting sub-skill. Use when generating or populating any Block financial report (weekly, monthly, quarterly, board).
depends-on: [gdrive, sheet-to-doc-table]
allowed-tools: []
metadata:
  author: nmart
  version: "1.1.0"
  status: "active"
---

# Block FP&A Reporting — Global Recipe

## Role
Populate Block financial reports with facts sourced from governed data.
Report numbers only. Do not explain, interpret, or assign drivers.

---

## Data
- Source: governed Google Sheets master table (rows = metrics, columns = time periods)
- Never estimate or infer a value
- If data is missing: `[DATA MISSING: {metric} | {period}]`

---

## Comparison Point
Always compare to the latest forecast for the quarter in scope:

| Quarter | Comparison Point |
|---------|-----------------|
| Q1      | AP              |
| Q2      | Q2OL            |
| Q3      | Q3OL            |
| Q4      | Q4OL            |

Use `[Forecast]` as a placeholder in format templates — substitute the correct label at runtime.

---

## Metric Format

**Pacing / forward-looking:**
```
[emoji] **[Metric]** is pacing to [Value] in [Period] ([+/-]% YoY), [+/-Delta]% ([+/-$Delta]) [above/below] [Forecast]
```
Example: `🟢 **Block gross profit** is pacing to $1.05B in March (+25% YoY), +1.6% (+$17M) above AP.`

**Actuals (closed period):**
```
[emoji] **[Metric]** landed at [Value] ([+/-]% YoY), [+/-Delta]% ([+/-$Delta]) [above/below] [Forecast]
```

Key metric labels are always **bold** in fact lines. This includes metric names like Block gross profit, Cash App gross profit, Square gross profit, Actives, Inflows per active, Monetization rate, Adjusted Operating Income, Global GPV, US GPV, International GPV, etc.

---

## Style Rules

**Numbers**
- Dollars: $M, $B, $K — no space ($17M, $1.05B)
- Units (actives, GPV): M or B — no space (58.5M actives, $23.3B GPV)
- Basis points: space before bps (+5 bps, (5 bps))
- Percentages: no space (25%, +3.0%)

**Rounding**
- Percentages: one decimal if < 10% (9.8%), no decimal if ≥ 10% (15%)
- Dollars in millions: one decimal if < $10M ($4.2M, -$7.8M), no decimal if ≥ $10M ($45M)
- Dollars in billions: always two decimals ($1.26B)
- Actives: always one decimal (58.5M)

**Signs**
- Always include +/- on variances and YoY growth rates
- Text negatives: hyphen (-$38M, -1.6%)
- Tables/charts negatives: parentheses (($38M), (5.4 bps))

**Time Periods**
- Body text: Q1 2026, March 2026
- Tables/charts: Q1'26, Mar'26

**Capitalization**
- "gross profit" and "opex" — lowercase in body text
- Standalone headers: capitalize all major words
- In-line bold labels (e.g. **Topline:**) — capitalize first word only

---

## Deviations — "Nick to fill out"
After any fact line where driver context is needed, insert on a new line:
`Nick to fill out` — formatted red (hex #ea4335) in the Google Doc.
Do NOT fill in the reason yourself.

---

## Sub-Agent Inheritance
Sub-skills must load this recipe first. These standards may not be overridden.
