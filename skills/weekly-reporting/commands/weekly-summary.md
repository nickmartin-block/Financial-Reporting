# Weekly Performance Summary

Generate a management-ready Block Performance Digest combining pacing metrics with Cash App commentary from Slack. The output has two layers: a **Summary** (comprehensive emoji-coded narrative) and **Overview** sections (plain-text reference detail, with performance tables).

**Dependencies:** Read `~/skills/weekly-reporting/skills/financial-reporting.md` for global formatting standards. Read `~/skills/weekly-reporting/skills/weekly-tables.md` for the table population logic (batch-update approach — tables are pre-formatted in the template tab, not generated as markdown).

**Template tab requirement:** Nick must create the template tab in the Google Doc before running this command. The template tab contains headings and pre-formatted tables with empty data cells. See weekly-tables.md for template structure details.

---

## Step 1 — Auth check

Run both in parallel:

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py auth status
```

```bash
/Users/nmart/skills/slack/scripts/slack-cli auth status
```

If gdrive auth fails, tell Nick to run: `cd ~/skills/gdrive && uv run gdrive-cli.py auth login`
If slack auth fails, run: `/Users/nmart/skills/slack/scripts/slack-cli auth callback --workspace block`

Stop if auth cannot be resolved.

---

## Step 2 — Read pacing sheet + search Slack (parallel)

**Run both of these concurrently** — they are independent data sources with no dependency on each other. Both depend only on auth (Step 1).

### 2a — Read the master pacing sheet

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4 --sheet summary > /tmp/pacing_sheet_$(date +%Y-%m-%d).json
```

**Save the raw JSON to `/tmp/pacing_sheet_YYYY-MM-DD.json`.** This file is the single source of truth for the entire pipeline — table population (Step 5b), commentary generation (Step 3), and validation (Step 6) all reference this cached file instead of re-reading the sheet. This prevents mid-run data drift and eliminates redundant API calls.

Extract every in-scope metric from the sheet. The metrics to pull:

| Section | Metrics |
|---------|---------|
| Gross Profit | Block GP, Cash App GP, Square GP, Proto GP, TIDAL GP, Cash ex-Commerce GP, Lending GP, Non-Lending GP (see note below) |
| Profitability | Adjusted Operating Income (+ margin), Rule of 40 |
| Square GPV | Global GPV, US GPV, International GPV |
| Cash App Inflows (ex-Commerce) | Actives, Inflows per Active, Monetization Rate |
| Commerce | Commerce GP, Commerce Inflows, Commerce Monetization Rate |

For **each** metric, extract both monthly and quarterly values:

**Monthly (current month):**
- Value (current month pacing)
- YoY%
- vs AP delta% and delta$

**Quarterly (Q1/Q2/etc.):**
- Q1 Pacing value
- Q1 AP value
- Q1 YoY%
- Q1 vs AP delta% and delta$
- Q1 WoW change (compare current Q1 pacing to prior-week Q1 pacing in the rightmost columns)

**Guidance & Consensus** (extract where available — these appear in dedicated columns in the Q1 area):
- **Block GP**: Q1 Guidance, Q1 Consensus
- **Adjusted Operating Income**: Q1 Guidance, Q1 Consensus
- **Global GPV**: Q1 Consensus
- **Cash App Actives**: Q1 Consensus
- **Rule of 40**: Q1 Guidance, Q1 Consensus

Compute deltas vs guidance/consensus as: (Q1 Pacing - Benchmark) / Benchmark, or in pts for Rule of 40.

**Growth rate vs. value comparisons — "pts" not "%":** When comparing two growth rates (e.g., pacing YoY% vs. consensus YoY%, or GPV growth vs. GP growth), always express the difference in **pts** (percentage points), not %. For example: "growth +0.9 pts above consensus" or "4.2 pts below GPV growth." This avoids confusion with absolute-value deltas. Use "%" only when comparing a pacing dollar value to a benchmark dollar value (e.g., "+3.3% (+$94M) above AP"). This rule applies everywhere — Summary, Overview, and GPV-to-GP spread.

**WoW breakdown**: For Block GP, also note the Q1 WoW split between Cash App and Square (from their respective Q1 WoW values).

**GPV-to-GP Spread**: Compute two spreads:
1. Pacing spread: Q1 Global GPV YoY growth minus Q1 Square GP YoY growth
2. Consensus spread: Q1 Consensus GPV YoY growth minus Q1 Consensus Square GP YoY growth (derive consensus YoY from consensus values vs prior-year actuals)

**Rule of 40**: Extract from the dedicated row in the sheet. Pull:
- Monthly pacing, monthly delta vs AP (pts)
- Q1 pacing, Q1 AP, Q1 delta vs AP (pts), Q1 Guidance, Q1 Consensus
- Decompose as: GP growth% + AOI margin%

**Delta computation rule**: Never compute a delta from rounded or display-formatted numbers. Always use raw cell values from the sheet, or use pre-computed delta columns where they exist (e.g., columns W and X for Cash ex-Commerce GP delta $). Rounding before computing causes mismatches.

**AOI OpEx breakdown**: Compute the monthly AOI delta vs AP breakdown:
- GP contribution = Block GP monthly delta vs AP ($)
- OpEx contribution = AOI monthly delta vs AP ($) minus GP contribution
- Express as: "+$XM above AP (GP +$YM, OpEx +$ZM favorable/unfavorable)"

Assign an emoji based on vs-forecast delta% only:
- Green circle = delta > +0.5%
- Yellow circle = delta between -0.5% and +0.5%
- Red circle = delta < -0.5%

For metrics measured in basis points (monetization rates), compute the proportional delta% as (Pacing - AP) / AP to determine the emoji.

If a metric is missing from the sheet, note it as `[DATA MISSING: {metric}]`.

**Lending / Non-Lending GP breakout:** These are located in the "Cash App Ex-Commerce Breakdown" section of the summary sheet, approximately rows 127–133:
- Row with label `Lending GP`: value, then `YoY %` row, then `Delta vs. AP (%)` row
- Row with label `Non-Lending GP`: value, then `YoY %` row, then `Delta vs. AP (%)` row
- Same column mapping as section 1a (cols 11–13 for monthly, 17–18 for Q1 Pacing/AP)
- Use these to populate the Lending vs. Non-Lending bullets in the Summary section

### 2b — Search Slack for brand digests

Pull the latest messages from the #fpa-ir-planning-reporting channel:

```bash
/Users/nmart/skills/slack/scripts/slack-cli get-channel-messages --channel-id C091W2BA04U --limit 20 --full-text
```

### Cash App Weekly Digest

Scan for the most recent message from **mjansing** (user ID `U01K3T9BQ21`) that contains "Cash App Weekly Digest" or a Google Slides/Presentation link.

**If not found**, ask Nick: "I couldn't find Matt's latest Cash digest in the usual group DM. Where should I look?"

**If not yet posted**, proceed without the digest. Flag it as pending in the output.

When the digest message includes a Google Slides/Presentation link, extract that URL for use in the Overview: Gross Profit Performance section as the "Cash App - Weekly Performance Digest" link.

### Square Weekly Update

Scan the same channel for the most recent message from **jerbe** (James Erbe, user ID `U02UQK7N5SB`) that contains Square performance context — typically a text-only update with commentary on GPV, gross profit, or WoW drivers. Look for messages that mention Square inputs, GPV data, or performance context.

**If not found**, proceed without Square context. The Square WoW driver in the Summary will remain as `[MANUAL]`.

**If found**, use jerbe's commentary to:
1. Synthesize Square WoW driver context in the Topline paragraph (replacing the `[MANUAL]` placeholder for Square-specific WoW driver)
2. Add any relevant Square context to the Square GPV section of the Summary

### Synthesis rules (both digests)

- **No attribution** — do not quote messages directly or mention names in the output
- Synthesize insights professionally to explain WoW drivers and performance context
- If both digests are found, weave Cash App and Square drivers together in the Topline WoW paragraph

---

## Step 3 — Generate the summary

Combine the sheet data and Slack message into a markdown file with two layers:
1. **Summary** — comprehensive emoji-coded narrative (the main content)
2. **Overview sections** — plain-text fact lines + performance table, NO emojis

Each Overview section includes bulleted fact lines with proper nesting (see template below). Metric labels in bullets must be **bold**. Tables are NOT generated in the markdown — they are pre-formatted in the template tab and populated separately by the weekly-tables skill via Docs API batch-update.

### Template

```
# Block Performance Digest

[Month abbreviation] [DD], [YYYY]

## Summary

[emoji] **Topline: Block gross profit** is pacing to [Q1 Value — $B] in Q1 ([Q1 YoY]% YoY), [Q1 AP delta]% ([Q1 AP delta $]) [above/below] AP and [Q1 Guidance delta]% ([Q1 Guidance delta $]) [above/below] guidance. Block gross profit is pacing [Month AP delta]% ([Month AP delta $]) [above/below] AP in [Month], but [Q1 WoW $] [below/above] the previous week (Cash [Cash WoW $], Square [SQ WoW $]) due to [synthesized WoW drivers from Slack digest — no attribution] [MANUAL: and Square-specific WoW driver context]. Cash App gross profit is pacing to [Cash Month Value] in [Month] ([Cash Month YoY]% YoY), [Cash Month AP delta]% ([Cash Month AP delta $]) [above/below] AP. Square gross profit is pacing to [SQ Month Value] in [Month] ([SQ Month YoY]% YoY), [SQ Month AP delta]% ([SQ Month AP delta $]) [above/below] AP.

*(blank line — ensure a non-bulleted blank paragraph separates Topline from the first bullet)*

- [emoji] **Square gross profit** is expected to land [SQ Month AP delta]% ([SQ Month AP delta $]) [below/above] AP in [Month] and [SQ Q1 AP delta]% ([SQ Q1 AP delta $]) [below/above] in Q1. Square gross profit growth is expected to land at [SQ GP Q1 YoY]% YoY in Q1 ([pacing spread] pts below GPV growth).
- [emoji] **Square GPV** In [Month], global GPV is pacing to [Value] ([Global GPV Month YoY]% YoY), [Month AP delta]% [above/below] AP. For the quarter, global GPV is pacing to [Q1 Value] ([Q1 YoY]% YoY), [Q1 AP delta]% [above/below] AP, with growth [+/-X] pts [above/below] consensus. US and International GPV are pacing [above/below/mixed] against AP in [Month]:
    - [emoji] **US GPV** is pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% [above/below] AP. For the quarter, US GPV is pacing to [Q1 Value] ([Q1 YoY]% YoY), [Q1 AP delta]% [above/below] AP.
    - [emoji] **International GPV** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% [above/below] AP.
- [emoji] **Cash ex-Commerce** gross profit is pacing [AP delta]% ([AP delta $]) [above/below] AP in [Month], and [YoY]% YoY.
    - [emoji] **Lending vs. Non-Lending (YoY):** Q1 lending gross profit growth is pacing to [Lending Q1 YoY]% YoY with non-lending growth of [Non-Lending Q1 YoY]% YoY.
        - [emoji] **Lending (vs. AP):** Q1 lending gross profit is pacing [Q1 AP delta]% ([Q1 AP delta $]) ahead of/behind AP.
        - [emoji] **Non-Lending (vs. AP):** Q1 non-lending gross profit is pacing [Q1 AP delta]% ([Q1 AP delta $]) ahead of/behind AP.
    - **Inflows Framework:**
        - [emoji] **Actives** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% ([AP delta count]) [below/above] AP.
        - [emoji] **Inflows per active** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% [above/below] AP
        - [emoji] **Monetization rate** is pacing to [Value] ([YoY bps] bps YoY) in [Month], [AP delta bps] bps [above/below] AP
- [emoji] **Commerce gross profit** is pacing [AP delta]% [above/below] AP in [Month], [YoY]% YoY.
    - [emoji] **Inflows (vs. AP)** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% [above/below] AP
    - [emoji] **Monetization rate (vs. AP)** is pacing to [Value] ([YoY bps] bps YoY) in [Month], [in-line with / above / below] AP
- [emoji] **Proto gross profit** is pacing to [Value] in [Month], [AP delta $] [above/below] AP, [Q1 context]. [MANUAL: qualitative context — e.g., timing of deal close, partnership discussions, etc.]

*(blank line — ensure a non-bulleted blank paragraph separates Proto from Profitability)*

[emoji] **Profitability: Q1 Adjusted Operating Income** is pacing to [AOI Q1 Value] ([margin]% margin), [Guidance delta]% ([Guidance delta $]) [above/below] guidance, and [Consensus delta]% ([Consensus delta $]) [above/below] consensus. [Synthesize WoW driver context — no attribution. E.g., "The modest decrease WoW ([WoW $]) is driven by topline softness from Cash App and Square due to..."]

---

## Overview: Gross Profit Performance

For additional details on performance for each brand, please reference the materials below:

[Cash App - Weekly Performance Digest](https://docs.google.com/presentation/d/1BaovDK5z8RMVSFjtr5SvX4a6YWpDywQZG4EJg8f_L2o/edit?slide=id.g35eb82d16a0_10_141#slide=id.g35eb82d16a0_10_141)
[Square Weekly Execution Update](https://docs.google.com/presentation/d/1ij5SkSVMLjRSMkrXkglR1k00zfNCKO6CfT9deWZy5uQ/edit?slide=id.g3d1d52cd57e_2_0#slide=id.g3d1d52cd57e_2_0)

- **Block gross profit** is pacing to [Block Month Value — $B] in [Month] ([YoY]% YoY), [AP delta]% ([AP delta $]) [above/below] AP.
    - **Cash App gross profit** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% ([AP delta $]) [above/below] AP.
    - **Square gross profit** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% ([AP delta $]) [above/below] AP.
    - **Proto gross profit** is pacing to [Value] in [Month], [Q1 context: in-line with AP for the quarter / above / below].
    - **TIDAL gross profit** is pacing to [Value] ([YoY]% YoY), [AP context].
- [Q]'[YY] **Block gross profit** is pacing to [Q1 Value — $B] ([Q1 YoY]% YoY), [Q1 AP delta]% ([Q1 AP delta $]) [above/below] AP, [Q1 Guidance delta]% ([Q1 Guidance delta $]) [above/below] guidance, [Q1 Consensus delta]% ([Q1 Consensus delta $]) [above/below] consensus.

## Overview: Adjusted Operating Income & Rule of 40

- **Adjusted Operating Income** is pacing to [AOI Month Value] ([AOI Month Margin]% margin) in [Month], [AOI Month AP delta $] [above/below] AP (GP [GP contribution $], OpEx [OpEx contribution $] favorable/unfavorable).
    - We expect to achieve **Rule of [Month Rule of 40]** in [Month] ([Month GP YoY]% growth, [Month AOI Margin]% margin), [Month Rule of 40 AP delta] pts [above/below] AP.
- For the quarter, **Adjusted Operating Income** is pacing to [AOI Q1 Value] ([Q1 Margin]% margin), [Guidance delta]% ([Guidance delta $]) ahead of/behind guidance, [Consensus delta]% ([Consensus delta $]) ahead of/behind consensus, and [AP delta]% ([AP delta $]) [above/below] AP.
    - For the quarter, the business is expected to deliver **Rule of [Q1 Rule of 40]** ([Q1 GP YoY]% growth, [Q1 Margin]% margin), [Q1 Rule of 40 AP delta] pts [above/below] AP, [Q1 Rule of 40 Guidance delta] pts [above/below] guidance and consensus.

## Overview: Inflows Framework

### Cash App (Ex Commerce)

- **Actives** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% ([AP delta count]) [below/above] AP
- **Inflows per active** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% [above/below] AP
- **Monetization rate** is pacing to [Value] ([YoY bps] bps YoY) in [Month], [AP delta bps] bps [above/below] AP

### Commerce

- **Inflows** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% [above/below] AP
- **Monetization rate** is pacing to [Value] ([YoY bps] bps YoY) in [Month], [in-line with / above / below] AP

## Overview: Square GPV

- **Global GPV** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% [above/below] AP
    - **US GPV** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% [above/below] AP
    - **International GPV** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% [above/below] AP
- For the quarter, **Global GPV** is pacing to [Q1 Value] ([Q1 YoY]% YoY), [Q1 AP delta]% [above/below] AP
    - **GPV to GP Spread:** Pacing [pacing spread] pts vs. consensus [consensus spread] pts

```

**If the Cash digest is pending**, note in the source line that the digest is pending. In the Summary, skip WoW driver synthesis and add: "[Cash App WoW driver context pending — digest not yet posted.]"

### Formatting rules

- Dollars: no space — $17M, $1.05B, $358M
- Billions: 2 decimals ($1.04B). Millions: whole number if >= $10M ($358M), 1 decimal if < $10M ($4.2M)
- Use $B format for Block GP (monthly and quarterly) and all GPV figures. Use $M for brand-level GP (Cash, Square, Proto, TIDAL) and AOI.
- Percentages: 1 decimal if < 10% (7.0%), no decimal if >= 10% (24%). Exception: keep 1 decimal for GPV YoY rates in the 10-15% range where precision matters (e.g., 12.6%).
- Basis points: space before (30 bps, +4 bps)
- Actives: 1 decimal (58.5M)
- Quarter notation: Q1'26, Q2'26, etc.
- Always include sign (+/-) on YoY and delta values
- "above"/"below" based on sign of delta vs forecast
- **Percentage points (pts):** Use "pts" when expressing the difference between two rates (growth rates, margins, Rule of 40). Use "%" only for deltas computed as (Value - Benchmark) / Benchmark. Example: "growth +0.9 pts above consensus" (two growth rates), NOT "+0.9% above consensus"
- Date in title: abbreviated month + day + year (e.g., "Mar 17, 2026")
- For [MANUAL] placeholders: preserve the placeholder text exactly, including the bracket notation, so Nick can find and fill them

### Writing style

- Professional tone suitable for senior management — no analyst attribution, no Slack usernames
- **Summary section**: emojis on every metric line. **Topline** and **Profitability** are standalone paragraphs; all other metrics are bulleted (Square GP as level 0; Square GPV → US/INTL sub-bullets; Cash ex-Commerce → Lending/Inflows sub-bullets with further nesting; Commerce → Inflows/Mon rate sub-bullets; Proto as level 0). Each topic starts with [emoji] **Bold label:**
- **"Inflows Framework:"** is a plain-text label with no emoji — the metrics underneath each have their own emoji
- **Overview sections**: NO emojis. Bulleted fact lines with bold metric labels, nested where applicable. Metric labels only are bold (not "is pacing to..." etc.).
- WoW drivers should be synthesized from the Slack digest content without quoting or naming the source
- Keep Summary lines tight — one to three sentences per topic
- [MANUAL] items should clearly describe what content is expected so Nick can fill them efficiently

---

## Step 4 — Save the file

Write to:
```
~/Desktop/Nick's Cursor/Weekly Reporting/weekly_summary_YYYY-MM-DD.md
```

Use today's date for the filename.

---

## Step 5 — Publish to Google Doc

After saving the .md file, publish the content to Nick's pre-existing template tab in the Weekly Performance Digest Google Doc. The template tab contains headings and pre-formatted tables with empty data cells.

**Doc ID:** `1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0`

### 5a — Find the template tab

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs tabs 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0
```

From the response:
1. Find the current quarter parent tab by matching `{Q}Q{YY}` against today's date (Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec)
2. Find a child tab matching today's date (M/D format, e.g., `3/24`)
3. If no template tab exists for today's date → **STOP** and tell Nick to create the template tab first. Do NOT create tabs.

Capture the tab ID.

### 5b — Publish (tables + commentary + formatting)

**Spawn a single agent** to handle all Doc publishing in one consolidated pass. This agent performs table population, commentary insertion, and formatting sequentially — avoiding redundant Doc reads.

The agent receives:
- **Sheet data path:** `/tmp/pacing_sheet_YYYY-MM-DD.json` (cached from Step 2a — do NOT re-read the sheet)
- **Doc ID:** `1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0`
- **Tab ID:** from Step 5a
- **Commentary .md path:** from Step 4
- **Table mapping:** `~/skills/weekly-reporting/skills/weekly-tables.md`

The agent executes these phases in order:

---

**Phase 1 — Populate tables**

Follow the procedure in `~/skills/weekly-reporting/skills/weekly-tables.md` (integrated mode):

1. Read sheet data from the cached temp file (no API call)
2. Read the Doc template structure via `docs get --include-tabs`
3. Navigate to the target tab. Find all 5 tables, extract cell positions (`startIndex` for each data cell)
4. Map Sheet values to Doc cells using the column/row mapping in weekly-tables.md
5. Build batch-update JSON: for each cell (sorted by startIndex descending), create `insertText` + `updateTextStyle` (Roboto 10pt) + `updateParagraphStyle` (CENTER) requests
6. Execute the batch-update
7. Re-read Doc structure, then apply conditional colors on Delta vs. AP rows (green `#007A33` for positive, red `#CC0000` for negative)

---

**Phase 2 — Insert commentary**

Insert the commentary (from the .md file) into the template tab at the correct positions between headings and tables. Since commentary insertion shifts indices, process sections in **reverse document order** (bottom-to-top).

1. Re-read the Doc structure via `docs get --include-tabs` (indices shifted from Phase 1)
2. Build an insertion map — for each section, identify the heading's `endIndex`:

| Section | Heading Text to Match | Insert After |
|---|---|---|
| Square GPV | `Overview: Square GPV` | Heading endIndex |
| Commerce | `Commerce` (H3) | Heading endIndex |
| Cash App | `Cash App (Ex Commerce)` (H3) | Heading endIndex |
| AOI | `Overview: Adjusted Operating Income` | Heading endIndex |
| GP | `Overview: Gross Profit Performance` | Heading endIndex |
| Summary | `Summary` (H2) | Heading endIndex |

3. For each section (bottom-to-top), extract the corresponding markdown fragment from the .md file (just the bullet lines, NOT the heading — headings are already in the template):

```bash
echo '<SECTION_MARKDOWN>' | (cd ~/skills/gdrive && uv run gdrive-cli.py docs insert-markdown DOC_ID --tab TAB_ID --at-index INSERTION_INDEX --font Inter)
```

4. The GP section also includes the reference links (Cash App Digest, Square Update) — insert those as part of the GP section commentary.

---

**Phase 3 — Format**

After all commentary is inserted, apply formatting. Re-read the Doc structure once via `docs get --include-tabs`, then build all formatting requests and execute as batch updates.

**3a. Font size 10pt + line spacing 1.15:**

For every `NORMAL_TEXT` paragraph outside tables:
```json
{"updateTextStyle": {"textStyle": {"fontSize": {"magnitude": 10, "unit": "PT"}}, "fields": "fontSize", "range": {"startIndex": START, "endIndex": END, "tabId": "TAB_ID"}}}
```
```json
{"updateParagraphStyle": {"paragraphStyle": {"lineSpacing": 115, "spaceAbove": {"magnitude": 0, "unit": "PT"}, "spaceBelow": {"magnitude": 0, "unit": "PT"}}, "fields": "lineSpacing,spaceAbove,spaceBelow", "range": {"startIndex": START, "endIndex": END, "tabId": "TAB_ID"}}}
```

**3b. Fix bullet nesting:**

**CRITICAL: Only modify paragraphs OUTSIDE of tables.** Track whether you are inside a `table` element. Skip ALL table cell paragraphs. When computing ranges for `createParagraphBullets`, ensure the range ends BEFORE the next table's startIndex.

1. Identify each bullet section by scanning paragraph text for known labels
2. `deleteParagraphBullets` on each section range
3. `insertText` `\t` (level 1) or `\t\t` (level 2) at sub-item starts (process in **reverse index order**):

**Summary sub-items:**
- Level 1 (`\t`): US GPV, International GPV, Lending vs. Non-Lending, Inflows Framework, Inflows (vs. AP), Monetization rate (vs. AP)
- Level 2 (`\t\t`): Lending (vs. AP), Non-Lending (vs. AP), Actives, Inflows per active, Monetization rate

**Overview GP sub-items (level 1):** Cash App GP, Square GP, Proto GP, TIDAL GP
**Overview AOI sub-items (level 1):** "We expect to achieve" and "For the quarter, the business"
**Overview Square GPV sub-items (level 1):** US GPV, International GPV, GPV to GP Spread

4. `createParagraphBullets` with `BULLET_DISC_CIRCLE_SQUARE` preset. **Range MUST end before the next table startIndex.**

**3c. Bold metric labels in overview commentary:**

Apply `bold: true` to metric names only (not "is pacing to..." text). Labels: Block gross profit, Cash App gross profit, Square gross profit, Proto gross profit, TIDAL gross profit, Adjusted Operating Income, Rule of 40/46/49/50, Actives, Inflows per active, Monetization rate, Inflows, Global GPV, US GPV, International GPV, GPV to GP Spread. **Only non-table paragraphs.**

**3d. Yellow highlight on placeholders:**

Find text containing `[MANUAL`, `[DATA MISSING`, or `[Cash App WoW` and apply yellow background (`rgbColor: {red: 1.0, green: 0.95, blue: 0.0}`).

**3e. Enforce Summary spacing:**

Verify non-bulleted blank paragraphs exist between: (1) Topline and first bullet, (2) last bullet (Proto) and Profitability. Insert if missing. Remove bullet formatting from these spacer paragraphs.

**3f. Post-bullet table safety check:**

Re-read Doc. Scan ALL table cell paragraphs for `bullet` property. Remove any stray bullets with `deleteParagraphBullets`.

### Error handling

If any step in Step 5 fails, skip to Step 6 and report the error. The .md file is already saved — no work is lost. Do not retry automatically.

---

## Step 6 — Validate

After publishing, validate that every number in the Doc's tables matches the sheet data. Follow the full validation procedure in `~/skills/weekly-reporting/skills/weekly-validate.md`, using `~/skills/weekly-reporting/skills/weekly-tables.md` for column mapping.

Use the tab ID from Step 5a (skip the tab identification and confirmation steps — you already know the tab).

**Sheet** (source of truth) — use the cached file from Step 2a (no re-read):
```bash
cat /tmp/pacing_sheet_YYYY-MM-DD.json
```

**Doc tables** (what we're validating):
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs extract-tables 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0 --tab TAB_ID
```

Since the tables were populated from the same cached sheet snapshot, validation is a structural integrity check — confirming the API inserted values correctly. Compare every data cell following the normalization rules and rounding tolerances in the validate skill. Save the validation report to:
```
~/Desktop/Nick's Cursor/Weekly Reporting/validation_YYYY-MM-DD.md
```

---

## Step 7 — Report back

Tell Nick:
- File path (the .md file)
- Google Doc link: `https://docs.google.com/document/d/1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0/edit?tab=TAB_ID` (or note if publish failed)
- **Validation result**: PASS or FAIL (N cells compared, N failures) — include failure details if any
- How many metrics were auto-populated vs. any `[DATA MISSING]` flags
- Count of `[MANUAL]` placeholders that need filling (remind Nick to fill these in the Google Doc)
- Whether the Cash digest was found (and from what date)
- Any notable signals (e.g., a metric flipped from green to red, WoW direction changes)

---

## Step 8 — Send Slack summary

After validation passes and Nick confirms the digest is ready, send a DM to Nick with a formatted summary he can share with the team.

```bash
/Users/nmart/skills/slack/scripts/slack-cli post-message --dm-myself "MESSAGE"
```

### Message format

```
M/D Block Performance Digest is ready for your review: https://docs.google.com/document/d/1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0/edit?tab=TAB_ID

Key takeaways:
• [Block Q1 GP — pacing value, YoY%, delta vs AP $, delta vs guidance $, brief WoW context if notable]
• [Q1 Profitability — AOI pacing value, margin%, delta vs guidance $; Rule of X, delta vs AP pts]
• [Cash App — monthly GP pacing, YoY%, delta vs AP $; WoW direction + driver summary; Q1 positioning]
• [Square — monthly GP pacing, YoY%, delta vs AP $; WoW direction + driver; any watch items like GPV-to-GP spread]
```

### Takeaway guidelines

- **Lead with Q1 quarterly numbers** — these are what leadership tracks
- **Focus on what changed WoW** — the digest numbers are in the doc; the takeaways should highlight movement and drivers
- **Include watch items** — flag metrics trending in the wrong direction or persistent gaps (e.g., actives below AP, GPV-to-GP spread)
- **Keep each bullet to 1–2 lines** — concise, numbers-forward, no filler
- **Use delta $ amounts** (not %) for the topline takeaways — easier to internalize at a glance
- **Tone:** direct, factual, no emojis — this is the message Nick will forward to senior leadership

