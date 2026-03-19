# Weekly Performance Summary

Generate a management-ready Block Performance Digest combining pacing metrics with Cash App commentary from Slack. The output has two layers: a **Summary** (comprehensive emoji-coded narrative) and **Overview** sections (plain-text reference detail, with performance tables).

**Dependencies:** Before generating, read `~/skills/weekly-reporting/skills/weekly-tables.md` for table construction rules (column mapping, row groups, cell formatting). Read `~/skills/weekly-reporting/skills/financial-reporting.md` for global formatting standards.

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

## Step 2 — Read the master pacing sheet

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4 --sheet summary
```

Extract every in-scope metric from the sheet. The metrics to pull:

| Section | Metrics |
|---------|---------|
| Gross Profit | Block GP, Cash App GP, Square GP, Proto GP, TIDAL GP, Cash ex-Commerce GP, Lending GP, Non-Lending GP |
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

**WoW breakdown**: For Block GP, also note the Q1 WoW split between Cash App and Square (from their respective Q1 WoW values).

**GPV-to-GP Spread**: Compute two spreads:
1. Pacing spread: Q1 Global GPV YoY growth minus Q1 Square GP YoY growth
2. Consensus spread: Q1 Consensus GPV YoY growth minus Q1 Consensus Square GP YoY growth (derive consensus YoY from consensus values vs prior-year actuals)

**Rule of 40**: Extract from the dedicated row in the sheet. Pull:
- Monthly pacing, monthly delta vs AP (pts)
- Q1 pacing, Q1 AP, Q1 delta vs AP (pts), Q1 Guidance, Q1 Consensus
- Decompose as: GP growth% + AOI margin%

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

---

## Step 3 — Search Slack for brand digests

Pull the latest messages from the weekly reporting group DM:

```bash
/Users/nmart/skills/slack/scripts/slack-cli get-channel-messages --channel-id C07LV8RS05A --limit 20 --full-text
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

## Step 4 — Generate the summary

Combine the sheet data and Slack message into a markdown file with two layers:
1. **Summary** — comprehensive emoji-coded narrative (the main content)
2. **Overview sections** — plain-text fact lines + performance table, NO emojis

Each Overview section includes plain-text fact lines (as separate paragraphs, NOT bullets) followed by a **markdown table** with 3-row header (year/type/month) and a separator column between monthly and quarterly groups. Generate tables following `~/skills/weekly-reporting/skills/weekly-tables.md` (column mapping, row groups, cell formatting). The table data comes from the same sheet read in Step 2 — no additional API calls needed.

### Template

```
# Block Performance Digest

[Month abbreviation] [DD], [YYYY]

## Summary

[emoji]**Topline:** Block gross profit is pacing to [Q1 Value — $B] in Q1 ([Q1 YoY]% YoY), [Q1 AP delta]% ([Q1 AP delta $]) [above/below] AP and [Q1 Guidance delta]% ([Q1 Guidance delta $]) [above/below] guidance. Block gross profit is pacing [Month AP delta]% ([Month AP delta $]) [above/below] AP in [Month], but [Q1 WoW $] [below/above] the previous week (Cash [Cash WoW $], Square [SQ WoW $]) due to [synthesized WoW drivers from Slack digest — no attribution] [MANUAL: and Square-specific WoW driver context]. Cash App gross profit is pacing to [Cash Month Value] in [Month] ([Cash Month YoY]% YoY), [Cash Month AP delta]% ([Cash Month AP delta $]) [above/below] AP. Square gross profit is pacing to [SQ Month Value] in [Month] ([SQ Month YoY]% YoY), [SQ Month AP delta]% ([SQ Month AP delta $]) [above/below] AP.

[emoji]**Square GPV:** In [Month], global GPV is pacing to [Value] ([Global GPV Month YoY]% YoY), [Month AP delta]% [above/below] AP. For the quarter, global GPV is pacing to [Q1 Value] ([Q1 YoY]% YoY), [Q1 AP delta]% [above/below] AP, with growth [+/-X] pts [above/below] consensus. US and International GPV are both pacing [above/below/mixed] AP in [Month], with Square gross profit pacing [SQ Month AP delta]% ([SQ Month AP delta $]) [above/below] AP in [Month] and [SQ Q1 AP delta]% ([SQ Q1 AP delta $]) [above/below] in Q1.
[emoji]**GPV to GP Spread:** Square gross profit growth is expected to land at [SQ GP Q1 YoY]% YoY in Q1 ([pacing spread] pts below GPV growth).
[emoji]**US GPV** is pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% [above/below] AP. For the quarter, US GPV is pacing to [Q1 Value] ([Q1 YoY]% YoY), [Q1 AP delta]% [above/below] AP.
[emoji]**International GPV** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% [above/below] AP.

[emoji]**Cash ex-Commerce gross profit** is pacing [AP delta]% ([AP delta $]) [above/below] AP in [Month], and [YoY]% YoY.
[emoji]**Lending vs. Non-Lending (YoY):** Q1 lending gross profit growth is pacing to [Lending Q1 YoY]% YoY with non-lending growth of [Non-Lending Q1 YoY]% YoY.
[emoji]**Lending (vs. AP):** Q1 lending gross profit is pacing [Q1 AP delta]% ([Q1 AP delta $]) ahead of/behind AP.
[emoji]**Non-Lending (vs. AP):** Q1 non-lending gross profit is pacing [Q1 AP delta]% ([Q1 AP delta $]) ahead of/behind AP.

**Inflows Framework:**
[emoji]**Actives** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% ([AP delta count]) [below/above] AP.
[emoji]**Inflows per active** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% [above/below] AP
[emoji]**Monetization rate** is pacing to [Value] ([YoY bps] bps YoY) in [Month], [AP delta bps] bps [above/below] AP

[emoji]**Commerce gross profit** is pacing [AP delta]% [above/below] AP in [Month], [YoY]% YoY.
[emoji]**Inflows (vs. AP)** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% [above/below] AP
[emoji]**Monetization rate (vs. AP)** is pacing to [Value] ([YoY bps] bps YoY) in [Month], [in-line with / above / below] AP

[emoji]**Proto gross profit** is pacing to [Value] in [Month], [AP delta $] [above/below] AP, [Q1 context]. [MANUAL: qualitative context — e.g., timing of deal close, partnership discussions, etc.]

[emoji]**Profitability:** Q1 Adjusted Operating Income is pacing to [AOI Q1 Value] ([margin]% margin), [Guidance delta]% ([Guidance delta $]) [above/below] guidance, and [Consensus delta]% ([Consensus delta $]) [above/below] consensus. [Synthesize WoW driver context — no attribution. E.g., "The modest decrease WoW ([WoW $]) is driven by topline softness from Cash App and Square due to..."]

---

## Overview: Gross Profit Performance

For additional details on performance for each brand, please reference the materials below:

[Cash App - Weekly Performance Digest](link from Slack digest message, or placeholder)
[Square Weekly Execution Update](placeholder — link not currently automated)

**Block gross profit** is pacing to [Block Month Value — $B] in [Month] ([YoY]% YoY), [AP delta]% ([AP delta $]) [above/below] AP.

- **Cash App gross profit** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% ([AP delta $]) [above/below] AP.
- **Square gross profit** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% ([AP delta $]) [above/below] AP.
- **Proto gross profit** is pacing to [Value] in [Month], [Q1 context: in-line with AP for the quarter / above / below].
- **TIDAL gross profit** is pacing to [Value] ([YoY]% YoY), [AP context].

[Q]'[YY] **Block gross profit** is pacing to [Q1 Value — $B] ([Q1 YoY]% YoY), [Q1 AP delta]% ([Q1 AP delta $]) [above/below] AP, [Q1 Guidance delta]% ([Q1 Guidance delta $]) [above/below] guidance, [Q1 Consensus delta]% ([Q1 Consensus delta $]) [above/below] consensus.

[TABLE: GP Performance — Metric | Jan'26 Actual | Feb'26 Actual | Mar'26 Pacing | Q1'26 Pacing | Q1 AP | Q1 Guidance | Q1 Consensus. Row groups: Block GP, Cash App GP, Square GP, Proto GP, TIDAL GP (each: value / YoY Growth (%) / Delta vs. AP (%)). Blank row between groups. See weekly-tables SKILL.md for column mapping and cell formatting.]

## Overview: Adjusted Operating Income & Rule of 40

**Adjusted Operating Income** is pacing to [AOI Month Value] ([AOI Month Margin]% margin) in [Month], [AOI Month AP delta $] [above/below] AP (GP [GP contribution $], OpEx [OpEx contribution $] favorable/unfavorable).

**Rule of 40** — we expect to achieve Rule of [Month Rule of 40] in [Month] ([Month GP YoY]% growth, [Month AOI Margin]% margin), [Month Rule of 40 AP delta] pts [above/below] AP.

**Adjusted Operating Income (quarterly)** is pacing to [AOI Q1 Value] ([Q1 Margin]% margin), [Guidance delta]% ([Guidance delta $]) ahead of/behind guidance, [Consensus delta]% ([Consensus delta $]) ahead of/behind consensus, and [AP delta]% ([AP delta $]) [above/below] AP.

**Rule of 40 (quarterly)** — the business is expected to deliver Rule of [Q1 Rule of 40] ([Q1 GP YoY]% growth, [Q1 Margin]% margin), [Q1 Rule of 40 AP delta] pts [above/below] AP, [Q1 Rule of 40 Guidance delta] pts [above/below] guidance and consensus.

[TABLE: AOI & Rule of 40 — same columns as GP Performance. Row groups: Gross profit (value / YoY% / Delta%), AOI (value / Margin% / Delta%), Rule of 40 (value / Delta pts). See weekly-tables SKILL.md.]

## Overview: Inflows Framework

### Cash App (Ex Commerce)

**Actives** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% ([AP delta count]) [below/above] AP

**Inflows per active** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% [above/below] AP

**Monetization rate** is pacing to [Value] ([YoY bps] bps YoY) in [Month], [AP delta bps] bps [above/below] AP

[TABLE: Cash App Inflows — Metric | Jan'26 Actual | Feb'26 Actual | Mar'26 Pacing | Q1'26 Pacing | Q1 AP | Q1 Consensus. Row groups: Actives, Inflows per Active, Monetization rate (each: value / YoY% / Delta%). See weekly-tables SKILL.md.]

### Commerce

**Inflows** are pacing to [Value] ([YoY]% YoY) in [Month], [AP delta]% [above/below] AP

**Monetization rate** is pacing to [Value] ([YoY bps] bps YoY) in [Month], [in-line with / above / below] AP

[TABLE: Commerce — Metric | Jan'26 Actual | Feb'26 Actual | Mar'26 Pacing | Q1'26 Pacing | Q1 AP. Row groups: Inflows, Monetization rate (each: value / YoY% / Delta%). See weekly-tables SKILL.md.]

## Overview: Square GPV

**Global GPV** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% [above/below] AP

- **US GPV** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% [above/below] AP
- **International GPV** is pacing to [Value] in [Month] ([YoY]% YoY), [AP delta]% [above/below] AP

**Global GPV** is pacing to [Q1 Value] ([Q1 YoY]% YoY), [Q1 AP delta]% [above/below] AP
**GPV to GP Spread** — Pacing [pacing spread] pts vs. consensus [consensus spread] pts

[TABLE: Square GPV — Metric | Jan'26 Actual | Feb'26 Actual | Mar'26 Pacing | Q1'26 Pacing | Q1 AP | Q1 Consensus. Row groups: Global GPV, US GPV, International GPV (each: value / YoY% / Delta%). See weekly-tables SKILL.md.]
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
- Date in title: abbreviated month + day + year (e.g., "Mar 17, 2026")
- For [MANUAL] placeholders: preserve the placeholder text exactly, including the bracket notation, so Nick can find and fill them

### Writing style

- Professional tone suitable for senior management — no analyst attribution, no Slack usernames
- **Summary section**: emojis on every metric line. Flowing paragraphs, not bullet points. Each topic starts with [emoji]**Bold label:**
- **"Inflows Framework:"** is a plain-text label with no emoji — the metrics underneath each have their own emoji
- **Overview sections**: NO emojis. Plain narrative text for reference detail.
- WoW drivers should be synthesized from the Slack digest content without quoting or naming the source
- Keep Summary lines tight — one to three sentences per topic
- [MANUAL] items should clearly describe what content is expected so Nick can fill them efficiently

---

## Step 5 — Save the file

Write to:
```
~/Desktop/Nick's Cursor/Weekly Reporting/weekly_summary_YYYY-MM-DD.md
```

Use today's date for the filename.

---

## Step 5.5 — Publish to Google Doc

After saving the .md file, publish the content to the Weekly Performance Digest Google Doc.

**Doc ID:** `1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0`

### 5.5a — List tab metadata

```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs tabs 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0
```

This returns tab titles and IDs only — do NOT read tab content via `docs get`.

From the response:
1. Find the current quarter parent tab by matching `{Q}Q{YY}` against today's date (Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec)
2. Check if a tab for today's date already exists under that parent

### 5.5b — Create quarter parent tab (if needed)

Only if no matching quarter parent tab exists (e.g., quarter just turned over):

```bash
echo '{"requests":[{"addDocumentTab":{"tabProperties":{"title":"XQ2Y"}}}]}' | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0)
```

Use the correct quarter label (e.g., `2Q26`). Capture the new parent tab ID from the response.

### 5.5c — Create the weekly date tab

If no tab exists for today's date:

```bash
echo '{"requests":[{"addDocumentTab":{"tabProperties":{"title":"M/D","parentTabId":"PARENT_TAB_ID"}}}]}' | (cd ~/skills/gdrive && uv run gdrive-cli.py docs batch-update 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0)
```

Tab naming: `M/D` — no leading zeros (e.g., `3/17`, `4/7`). Use the quarter parent tab ID from 5.5a or 5.5b.

If the tab already exists: ask Nick whether to overwrite or skip. If overwrite, use the existing tab ID.

Capture the new tab ID from the response.

### 5.5d — Write markdown to the tab

```bash
cat "FILEPATH_FROM_STEP_5" | (cd ~/skills/gdrive && uv run gdrive-cli.py docs insert-markdown 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0 --tab TAB_ID --at-index 1 --font Inter)
```

Use the file path from Step 5 and the tab ID from 5.5c. Verify the response shows `"status": "ok"`.

### Error handling

If any step in 5.5 fails, skip to Step 6 and report the error. The .md file is already saved — no work is lost. Do not retry automatically (avoids duplicate tabs).

---

## Step 6 — Validate

After publishing, validate that every number in the Doc's tables matches the master sheet. Follow the full validation procedure in `~/skills/weekly-reporting/skills/weekly-validate.md`, using `~/skills/weekly-reporting/skills/weekly-tables.md` for column mapping.

Use the tab ID from Step 5.5c (skip the tab identification and confirmation steps — you already know the tab).

**Sheet** (source of truth):
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py sheets read 1hvKbg3t08uG2gbnNjag04RNHbu9rddIU4woudxeH1d4 --sheet summary
```

**Doc tables** (what we're validating):
```bash
cd ~/skills/gdrive && uv run gdrive-cli.py docs extract-tables 1FU4In29vR_1pvGy1VyIeDTCbglBQ6DvKWKE1wI18Rv0 --tab TAB_ID
```

Compare every data cell following the normalization rules and rounding tolerances in the validate skill. Save the validation report to:
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
