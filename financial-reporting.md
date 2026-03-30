---
name: financial-reporting
description: Global recipe for Block FP&A financial reporting. Governs all reporting agents — formatting standards, metric formats, comparison framework, style rules, and deviation handling. Load this skill first before any financial reporting sub-skill.
depends-on: [gdrive, sheet-to-doc-table]
allowed-tools: []
metadata:
  author: nmart
  version: "1.3.0"
  status: "active"
---

# Block FP&A Reporting — Global Recipe

## Role
Populate Block financial reports with governed facts: metric values, growth rates, variances, and table data.

**Agent responsibilities:**
- Source values from governed data and populate fact lines, tables, and metric summaries
- Apply all formatting, rounding, and sign conventions defined below
- Flag missing data with `[DATA MISSING: {metric} | {period}]`

**Human responsibilities (do not automate):**
- Driver commentary and the "why" behind the numbers
- Watchpoints, risk/opportunity narratives, and strategic interpretation
- Any qualitative judgment or forward-looking framing

When driver context is needed, insert `Nick to fill out` (see Deviations section). Never generate qualitative explanations or assign drivers.

---

## Data
- Source: governed Google Sheets master table (rows = metrics, columns = time periods)
- Never estimate or infer a value
- If data is missing: `[DATA MISSING: {metric} | {period}]`
- If data is null, not applicable, or not yet reported: `--`

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
  - *Exception:* Brand-level and sub-product growth rates (e.g., Square gross profit, Cash App gross profit, GPV by region) may retain one decimal above 10% when precision is meaningful for comparison (+12.3% YoY, +14.6% YoY)
- Dollars in millions: one decimal if < $10M ($4.2M, -$7.8M), no decimal if ≥ $10M ($45M)
- Dollars in billions: always two decimals ($1.26B)
- Actives: always one decimal (58.5M)
- Basis points in body text: round to nearest integer (6.1 bps → 6 bps)
- Basis points in charts/tables: keep one decimal (6.1 bps → 6.1 bps)

**Signs**
- Always include +/- on variances and YoY growth rates
- Text negatives: hyphen (-$38M, -1.6%)
- Tables/charts negatives: parentheses (($38M), (5.4 bps))

**Percentage Points**
- Always plural: "pts" — never "pt", "pp", or "percentage points"
- Always a space between the number and "pts": +5 pts, -2.3 pts
- Follow the same rounding as percentages: one decimal if < 10 (+2.4 pts), no decimal if ≥ 10 (+12 pts)
- Margin changes: "+X pts of margin expansion" or "-X pts of margin compression"

**Margin Presentation**
- State margin levels inline: "$588M (20% margin)"
- Express margin changes as: "+X pts of margin expansion" or "-X pts of margin compression"
- Margin values follow standard rounding: one decimal if < 10% (9.8% margin), no decimal if ≥ 10% (20% margin)

**Null and Missing Values**
- Use "--" for any null, not applicable, or not yet reported value
- Applies to both body text and table cells

**Time Periods**
- Body text: Q1 2026, March 2026
- Tables/charts: Q1'26, Mar'26

**Capitalization**
- "gross profit" and "opex" — lowercase in body text
- Standalone headers: capitalize all major words
- In-line bold labels (e.g. **Topline:**) — capitalize first word only

**Dashes**
- Em dash (—): interruptions or direction changes; spaces on either side in internal prose
- En dash (–): ranges without spaces (5–10, $15–$20)
- Hyphen (-): negative numbers in body text, compound terms

**Punctuation**
- Oxford/serial comma: always ("Square, Cash App, and Afterpay")
- Spell out numbers below ten in body text; numerals for measurements and amounts
- Contractions OK — keeps tone conversational

**Hyphenation**
- Compound adjectives before a noun: year-over-year increase, lower-than-expected churn, small-business owner
- Predicate adjectives (after the noun): no hyphen — "Profit increased year over year"
- Adverbs ending in -ly: no hyphen — manually entered, fully loaded
- Financial compounds: top-line, in-line, true-up, true-down, bottom-up (not "bottoms-up")

---

## Variance Colors
- Favorable: green `#34a853`
- Unfavorable: red `#ea4335`
- Chart headers: black background with white text
- Not color-coded: variances within +/- 1% or +/- $0.5M, and all YoY comparisons

---

## Product Names
Always use full product names. Never abbreviate product names or assume what an acronym refers to. Report names verbatim as they appear in source data.

**Cash App products:**
- Cash App (not "CA")
- Cash App Card (not "Card" or "CAC")
- Cash App Pay (not "CAP")
- Cash for Business (not "C4B" or "CfB")
- Borrow (always "Borrow", not abbreviated)
- Post-Purchase (internal codename: "Retro")
- Bitcoin Buy/Sell (not "BTC B/S")
- Instant Deposit (not "ID")
- Paper Money Deposits (not abbreviated)
- Commerce (the combined Afterpay + Cash App Pay segment)

**Square products:**
- Square (not "SQ")
- Square One (not "S1")
- US Payments, International Payments (spell out)
- Square Banking (not abbreviated)
- Square Loans (not abbreviated)

**Other brands:**
- Afterpay (not "AP" — "AP" means Annual Plan)
- Pay in 4 (not "Pi4")
- TIDAL (all caps)
- Proto (not abbreviated)
- Bitkey (not abbreviated)
- Bitcoin Lightning (not abbreviated)

---

## Terminology
- **Annual Plan (AP)**: capitalize; spell out on first use; do not use "Plan/plan" as shorthand
- **Outlook**: capitalize; spell out for BoD deliverables; abbreviation (Q2OL) OK in MRP and chart/table headers
- **Long-Range Plan (LRP)**: capitalize; spell out on first use; "LRP" OK on subsequent references
- **Rule of 40**: capitalize; do not abbreviate as R40
- **Adjusted**: write out "Adjusted" in body text; OK to abbreviate "Adj." in charts/tables
- **Net Volume Retention (NVR)**: spell out on first use; "NVR" OK on subsequent references
- **New Volume Added (NVA)**: spell out on first use; "NVA" OK on subsequent references
- **Primary Banking Actives (PBA)**: spell out on first use; "PBA" OK on subsequent references
- **Variable Profit (VP)**: spell out on first use; "VP" OK on subsequent references and in charts/tables
- **Buy Now Pay Later (BNPL)**: spell out on first use; "BNPL" OK on subsequent references
- **Go-to-market (GTM)**: spell out on first use; "GTM" OK on subsequent references; hyphenate as compound adjective
- **FinOps**: capitalize F and O; no need to spell out
- **Acronyms**: spell out on first use in all documents; abbreviate on subsequent references. Never assume what an acronym refers to — if unsure, spell it out or flag as `[ACRONYM: {term}]`.
- **buyside**: one word, lowercase
- **Bank Our Base**: not "Bank the Base"

---

## Deviations — "Nick to fill out"
After any fact line where driver context is needed, insert on a new line:
`Nick to fill out` — formatted red (hex #ea4335) in the Google Doc.
Do NOT fill in the reason yourself.

---

## Sub-Agent Inheritance
Sub-skills must load this recipe first. These standards may not be overridden.
