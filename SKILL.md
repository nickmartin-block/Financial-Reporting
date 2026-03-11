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

Use `[Forecast]` as a placeholder in the format templates below — substitute the correct label at runtime.

---

## Metric Format

**Pacing / forward-looking:**
```
[Metric] is pacing to [Value] in [Period] ([+/-Delta]% YoY), [+/-Delta]% ([+/-$Delta]) [above/below] [Forecast]
```
→ gross profit is pacing to $1.05B in March (+25% YoY), +1.6% (+$17M) above AP

**Actuals:**
```
[Metric] landed at [Value] ([+/-Delta]% YoY), [+/-Delta]% ([+/-$Delta]) [above/below] [Forecast]
```
→ gross profit landed at $940M (+29% YoY), +5.2% (+$47M) above AP

---

## Style Rules (FP&A Standard)

**Numbers**
- Dollars: $M, $B, $K — no space between symbol and number ($17M, $1.05B)
- Units (actives, GPV): M or B — no space (58.5M actives, $23.3B GPV)
- Basis points: space before bps (+5 bps, (5 bps))
- Percentages: no space (25%, +3.0%)

**Rounding**
- Single-digit numbers/percentages → one decimal (9.8%, $4.2M)
- Double-digit → nearest whole (15%, $45M)
- Billions → two decimals ($1.26B)
- Actives → always one decimal (58.5M)

**Signs**
- Always include +/- on variances and YoY growth rates, even alongside directional words
- Text negatives: hyphen, e.g., -$38M, -1.6% below AP
- Charts/tables negatives: parentheses, e.g., ($38M), (5.4 bps)

**Time Periods**
- Text: Q1 2026, March 2026
- Charts/tables: Q1'26, Mar'26

**Capitalization**
- "gross profit" and "opex" — lowercase in body text
- Standalone headers: capitalize all major words
- In-line headers (bold label + colon): capitalize first word only

**Comparisons**
- Abbreviate YoY, QoQ, WoW in body copy and always in charts/tables
- "vs." (with period) for versus

---

## Deviations
For any metric with a meaningful deviation from [Forecast], consensus, or prior period:
- Populate the fact line as normal
- Add on the next line: `[DRI to include context]`
- Do NOT fill in the reason yourself

---

## Sub-Agent Inheritance
Sub-agents must load this recipe first, then apply their specific deliverable instructions.
These standards may not be overridden.
