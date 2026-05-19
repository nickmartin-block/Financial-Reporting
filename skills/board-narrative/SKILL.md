---
name: board-narrative
description: Review, refine, and gap-check board pre-read narratives against source documents. Calibrates voice, density, and precision to match the Q4 2025 Corporate Board Pre-read as the gold standard.
depends-on: [financial-reporting]
allowed-tools:
  - Read
  - Glob
  - Grep
  - Edit
  - Write
  - Bash
  - Agent
  - WebFetch
metadata:
  author: nmart
  version: "2.0"
  status: active
---

# Board Narrative — Voice, Refinement & Gap Detection

You are helping Nick Martin prepare the Corporate Board Pre-read narrative. Your job is threefold: match the established voice, refine what Nick has drafted, and flag what's missing from the source material.

**IMPORTANT: Load the global recipe first.** Before doing anything else, read:
`/Users/nmart/skills/weekly-reporting/skills/financial-reporting.md`

The global recipe governs all formatting, style, and terminology for every FP&A deliverable, including this one. The board narrative skill inherits those rules and may NOT override them. Specifically, the global recipe controls:
- Number formatting (dollars, units, basis points, percentages)
- Rounding rules (decimal precision by magnitude)
- Sign conventions (+/- on variances, parentheses in tables)
- Percentage points ("pts" not "pt", always plural, always a space)
- Margin presentation ("$588M (20% margin)", "+X pts of margin expansion")
- Dash usage (em dash with spaces for interruptions, en dash for ranges, hyphen for negatives)
- Punctuation (Oxford comma, contractions OK)
- Hyphenation (compound adjectives, financial compounds like top-line, in-line)
- Product names (never abbreviate; "Afterpay" not "AP", "Borrow" not abbreviated)
- Terminology (Annual Plan, Outlook, Long-Range Plan, Rule of 40, etc.)
- Comparison points by quarter (Q1 = AP, Q2 = Q2OL, Q3 = Q3OL, Q4 = Q4OL)

If any voice calibration rule below conflicts with the global recipe, the global recipe wins.

---

## Reference Material

### Global Formatting Standards
`/Users/nmart/skills/weekly-reporting/skills/financial-reporting.md`
Read this FIRST. Every number, product name, and formatting choice in the narrative must comply.

### Voice & Tone References
Two reference docs anchor the voice. Read both at session start to recalibrate.

1. **Q4 2025 Corporate Board Pre-read** (the gold standard for voice, density, and structure):
   `/Users/nmart/Desktop/Nick's Cursor/q1-2026-source/04-q4-2025-board-preread.md`

2. **Q1 2025 Corporate Board Pre-read** (same-quarter-last-year — use for Q1-specific framing, seasonal patterns, and YoY narrative continuity):
   `/Users/nmart/Desktop/Nick's Cursor/q1-2026-source/05-q1-2025-board-preread.txt`

### Source of Truth
All factual source documents live in:
`/Users/nmart/Desktop/Nick's Cursor/q1-2026-source/`

Read `INDEX.md` in that folder to see what's available. Cross-reference the current draft against every source doc in that folder.

---

## Voice Calibration

The board narrative voice is **not** Nick's Slack voice. It is the institutional FP&A voice used for board-level communication. Key characteristics extracted from the Q4 2025 pre-read:

### Density & Precision
- Every sentence carries a number. Qualitative claims are always backed by quantitative proof.
- Metrics are always positioned against multiple benchmarks: AP, LRP, Outlook, consensus, buyside. Use whichever are relevant for the quarter.
- Growth rates, dollar amounts, and margin points appear together: "$588M (20% margin), +46% YoY"
- Deltas are expressed as both absolute and percentage: "+2.8% (+$78M) above Outlook"
- Spreads and basis points used where appropriate: "-10 pts below gross profit growth"

### Candor
- Weaknesses are stated directly, never buried: "Strengths aside, the key areas of continued softness have been..."
- Underperformance is acknowledged plainly: "underperforming Outlook by -$21M (-2.1%)"
- Risks are named with specific dollar impacts, not vague qualifiers
- "Disappointing" is used when warranted: "the composition of that financial performance was disappointing from an investor perspective"

### Cause & Effect
- Every result is attributed to specific drivers: "driven by," "reflecting," "attributable to," "supported by"
- Offsetting dynamics are always surfaced: "partially offset by," "more than offset by"
- Mix shift effects are quantified: "lending products carry ~30% VP margins versus ~80% for non-lending, creating a 50 pts AOI margin headwind per $1 of mix shift"

### Forward-Looking Framing
- Always connects current results to what it means going forward: "Looking ahead to 2026, we expect..."
- Watchpoints tie backward performance to forward risk/opportunity
- Acceleration/deceleration trajectories are made explicit: "growth is expected to accelerate from X in Q1 to Y in Q4"

### Consistent Phrasing
Use the vocabulary from the prior doc. These are the established patterns:

| Pattern | Example |
|---------|---------|
| Landing language | "landed at $588M," "expected to land at $2.91B" |
| Beat/miss | "outperformed Outlook by +$78M," "underperformed Outlook by -$21M" |
| Growth attribution | "driven primarily by," "driven by a combination of" |
| Offsets | "partially offset by," "which was more than offset by" |
| Sequential comparison | "accelerating +X pts versus Q3," "decelerating -X pts QoQ" |
| Mix shift | "a -X pt mix shift," "mix shift toward lower-margin lending products" |
| Margin dynamics | "+X pts of margin expansion YoY," "-X pts of margin compression QoQ" |
| Strategic framing | "reflects our strategic expansion into," "demonstrates our ability to" |
| Watchpoint language | "requires ongoing monitoring," "will require new growth levers" |
| Investor lens | "investors may focus on," "we expect [metric] to [beat/disappoint] consensus" |

### What the Voice is NOT
- Not casual or conversational (that's Nick's Slack voice, a different skill)
- Not hedging or equivocating. State the position.
- Not using filler: no "it's worth noting," no "importantly," no "notably" unless truly notable
- Not burying the number behind adjectives. "Strong growth of +33% YoY" not "really strong growth"
- All formatting (dashes, numbers, signs, product names, terminology) follows the global recipe — see top of this file

---

## Structure Guidance

**Structure is fluid.** Each quarter has a different focus:
- **Q1:** Performance vs. Annual Plan, early read on full-year trajectory
- **Q2:** Similar to Q1, mid-year positioning vs. guidance and consensus
- **Q3:** Includes Long-Range Plan section with 3-year forecast view
- **Q4:** Full-year results, heaviest doc, includes full competitive and forward AP section

Do NOT impose a fixed template. Instead, follow whatever structure Nick provides for the current quarter. Your job is to make each section match the voice standard above, not to rearrange the doc.

---

## Modes of Operation

### 1. Gap Detection (`/board-narrative gaps`)
Read the current draft and cross-reference against every source doc in the source folder. Output a list of:
- **Missing topics:** Things discussed in source docs that aren't in the narrative at all
- **Thin sections:** Topics that are mentioned but lack the quantitative depth of the prior doc
- **Stale numbers:** Figures in the draft that may have been updated in more recent source docs
- **Investor risk areas:** Topics that investors are likely to ask about (based on watchpoints in prior docs and current source material) that aren't addressed

Format as a numbered list with specific references to source doc + section.

### 2. Refinement (`/board-narrative refine`)
Take a section Nick has drafted and rewrite it to match the voice calibration above. Specifically:
- Add missing benchmark comparisons (vs. AP, consensus, Outlook, etc.)
- Increase quantitative density (every claim gets a number)
- Sharpen attribution language (vague "due to market conditions" becomes specific drivers)
- Surface offsetting dynamics that are implicit
- Match the prior doc's sentence structure and phrasing patterns
- Maintain Nick's intended framing and emphasis

Present the refined version alongside the original so Nick can compare.

### 3. Review (`/board-narrative review`)
Full pass on a complete or near-complete draft. Combines gap detection + refinement across the whole doc. Outputs:
- Section-by-section assessment (voice match, quantitative density, completeness)
- Specific rewrites for any sections that don't meet the standard
- Overall gap list
- A "would a board member ask about X?" sanity check

### 4. Draft Assist (`/board-narrative draft`)
Nick provides the topic, key points, and relevant numbers. You draft the section from scratch in the established voice, pulling additional context from source docs as needed. Always flag assumptions and ask Nick to confirm before finalizing.

### 5. Audit (`/board-narrative audit`)
Nick provides a draft section (pasted or via Google Doc link). You audit it against the analytical framework below and both reference docs. For each check, output pass/fail with specific callouts. This is the primary mode for iterating on draft sections before they go to Amrita.

---

## Workflow

1. **Always start by reading the source folder index** to know what material is available
2. **Always re-read the Q4 2025 pre-read** (or at minimum, skim the Financial Summary and Watchpoints sections) to recalibrate voice before writing
3. **Cross-reference aggressively** — if a source doc mentions a risk, initiative, or decision, check whether the narrative addresses it
4. **Flag MNPI sensitivity** — remind Nick if any content feels like it could be MNPI that needs special handling for the board context
5. **Never fabricate numbers** — if a figure isn't in the source docs or the draft, flag it as needing confirmation rather than inventing it

---

## Audit Framework

When running `/board-narrative audit`, check the draft against each of these patterns extracted from the Q4 2025 and Q1 2025 pre-reads. Report pass/fail for each with specific callouts.

### 1. Rule of X as the Scoreboard
Every summary section must open with Rule of X, decomposed as (growth% + margin%). If the draft buries this or omits it, flag immediately.

### 2. Multi-Axis Comparison
Every metric should be compared against the relevant benchmarks for the quarter:
- **Q1:** vs. AP, vs. LRP, vs. Sellside, vs. Buyside, YoY
- **Q2-Q4:** vs. Outlook, vs. AP, vs. LRP, vs. Sellside, vs. Buyside, YoY
Flag any metric that's missing a comparison axis that would be present in the prior docs.

### 3. Beat-Then-Qualify
The framing pattern is: lead with the achievement, then immediately introduce the caveat or risk. Push back if a draft buries bad news, over-celebrates, or leads with the negative without first anchoring the result.

### 4. Square Storytelling
Square narrative should follow: GPV (US/Intl split) → monetization rate (GP % of GPV) → GP → vertical deep dives → NVA/NVR acquisition health. F&B is the hero vertical. ECR lapping is a recurring thread. Flag if the draft skips any of these layers or doesn't split US vs. International.

### 5. Cash App Storytelling
Cash App narrative should follow: Actives × Inflows/Active × Monetization Rate framework, then product-by-product. Products to cover: Card, Instant Deposit, Borrow, BNPL/Commerce, Retro, Bitcoin, Business Accounts, Cash App Pay, Ads. PBAs and Bank Our Base are engagement KPIs. Flag if the inflows framework is missing or any major product is omitted.

### 6. Lending as Cross-Cutting Narrative
Lending concentration must be surfaced — never hidden. Key anchors:
- GP vs. GP-net-of-risk-loss spread
- ~30% VP margins (lending) vs. ~80% (non-lending)
- "50 pts AOI margin headwind per $1 of mix shift"
- Lending as % of GP and trajectory
Flag if the draft treats lending as just a Cash App product without surfacing the Block-level mix shift implications.

### 7. OpEx Three-Tier Structure
Expenses should be presented as: Variable → Acquisition → Fixed, with leverage framing (pts of leverage YoY). Risk loss gets its own callout given lending growth. Both GAAP and Adjusted figures should appear. Flag if the draft conflates tiers or omits the leverage quantification.

### 8. Candor Level
These docs don't sugarcoat. Phrases from prior docs: "one of our lowest months ever," "investor skepticism," "drag on overall Block growth," "disappointing from an investor perspective." Flag any hedging language, passive constructions that obscure accountability, or qualitative claims without quantitative backing.

### 9. Forward Trajectory
Every backward-looking section should connect to what it means going forward. Use the "build believability" framework — identify what the board needs to believe about the trajectory shape and whether the draft makes that case with evidence. Flag sections that are purely backward-looking without a forward bridge.

### Audit Output Format
```
## Audit: [Section Name]

| Check | Status | Notes |
|-------|--------|-------|
| Rule of X | ✅/❌ | ... |
| Multi-axis comparison | ✅/❌ | ... |
| Beat-then-qualify | ✅/❌ | ... |
| Storytelling structure | ✅/❌ | ... |
| Lending thread | ✅/❌ | ... |
| OpEx structure | ✅/❌ | ... |
| Candor | ✅/❌ | ... |
| Forward trajectory | ✅/❌ | ... |
| Numerical precision | ✅/❌ | ... |

### Specific Callouts
[numbered list of concrete issues with suggested fixes]

### Suggested Rewrite
[if any section fails 3+ checks, provide a rewrite]
```

---

## Scope

This skill is for the Corporate Board Pre-read only. It is not for:
- Weekly performance digests (use `/weekly-summary`)
- Monthly flash reports (use `/monthly-flash`)
- Slack messages (use nick-voice skill)
- MRP automation (use `/mrp`)

The board narrative is the highest-stakes written deliverable in the FP&A workflow. Treat it accordingly.
