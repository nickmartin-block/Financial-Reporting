---
name: weekly-summary
description: Generate a combined weekly performance summary with tables and narrative from the master pacing sheet and Slack brand digests. Outputs a dated MD file, then publishes to Google Doc. Invoke via /weekly-summary.
depends-on: [financial-reporting, financial-reporting-weekly, weekly-tables]
allowed-tools:
  - Bash(cd ~/skills/gdrive && uv run gdrive-cli.py:*)
  - Bash(/Users/nmart/skills/slack/scripts/slack-cli:*)
  - Read
  - Write
metadata:
  author: nmart
  version: "1.1"
  status: active
---

# Weekly Performance Summary

Generate a management-ready Block Performance Digest combining pacing metrics with Cash App commentary from Slack. The output has two layers: a **Summary** (comprehensive emoji-coded narrative) and **Overview** sections (performance tables + plain-text reference detail).

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
| Gross Profit | Block GP, Cash App GP, Square GP |
| Profitability | Adjusted Operating Income |
| Square GPV | Global GPV, US GPV, International GPV |
| Cash App Inflows (ex-Commerce) | Actives, Inflows per Active, Monetization Rate |
| Commerce | Commerce Inflows, Commerce Monetization Rate |

For each metric, extract:
- **Value** (current month pacing)
- **YoY%** (year-over-year change)
- **vs Forecast delta%** and **delta$** (vs AP for Q1, vs Q2OL for Q2, etc.)
- **WoW change** (change from prior week, if available)

Assign an emoji based on vs-forecast delta only:
- Green circle = delta > +0.5%
- Yellow circle = delta between -0.5% and +0.5%
- Red circle = delta < -0.5%

If a metric is missing from the sheet, note it as `[DATA MISSING: {metric}]`.

---

## Step 3 — Search Slack for Cash App Weekly Digest

Search for mjansing's latest Cash digest. Try the group DM first:

```bash
/Users/nmart/skills/slack/scripts/slack-cli get-channel-messages --channel-id C07LV8RS05A --limit 20 --full-text
```

Scan for the most recent message from mjansing (user ID `U01K3T9BQ21`) that contains "Cash App Weekly Digest" or a Google Slides/Presentation link.

**If not found in that channel**, ask Nick: "I couldn't find Matt's latest Cash digest in the usual group DM. Where should I look?"

**If Matt hasn't posted yet**, proceed to Step 4 without the digest. Flag it in the output as pending.

---

## Step 4 — Generate the summary

Combine the sheet data and Slack message into a markdown file using this template:

```
# Weekly Performance Summary — [Month] [Year] (Week of [date])

_Sources: Master pacing sheet (summary tab) as of [today's date];
Cash App Weekly Digest from mjansing ([digest date, or "pending"])._

---

## Gross Profit
- [emoji] **Block gross profit** is pacing to [Value] in [Month] ([+/-]% YoY), [+/-Delta]% ([+/-$Delta]) [above/below] AP
  - **Cash App gross profit** pacing to [Value] ([+/-]% YoY), [+/-Delta]% [above/below] AP
  - **Square gross profit** pacing to [Value] ([+/-]% YoY), [+/-Delta]% [above/below] AP

## Profitability
- [emoji] **Adjusted operating income** pacing to [Value] ([+/-]% YoY), [+/-Delta]% ([+/-$Delta]) [above/below] AP

## Square GPV
- [emoji] **Global GPV** pacing to [Value] ([+/-]% YoY), [+/-Delta]% [above/below] AP
  - **US GPV** at [Value] ([+/-]% YoY), [+/-Delta]% [above/below] AP
  - **International GPV** at [Value] ([+/-]% YoY), [+/-Delta]% [above/below] AP

## Cash App Inflows Framework
- [emoji] **Actives** pacing to [Value] ([+/-]% YoY), [+/-Delta]% [above/below] AP
- [emoji] **Inflows per active** at [Value] ([+/-]% YoY), [+/-Delta]% [above/below] AP
- [emoji] **Monetization rate** at [Value] ([+/-] bps YoY), [+/-] bps [above/below] AP

### Cash App Commentary (mjansing — [date])
> [Full text of mjansing's digest message, blockquoted]

Key takeaways:
- [Synthesis bullet connecting mjansing's narrative to the quantitative data above]
- [Another synthesis bullet if applicable]

## Commerce
- [emoji] **Commerce inflows** pacing to [Value] ([+/-]% YoY), [+/-Delta]% [above/below] AP
- [emoji] **Commerce monetization rate** at [Value] ([+/-] bps YoY), [+/-] bps [above/below] AP
```

**If the Cash digest is pending**, replace the Commentary section with:

```
### Cash App Commentary
> mjansing's Cash App Weekly Digest has not been posted yet for this week.
> Check group DM (C07LV8RS05A) or ask mjansing directly.
```

### Formatting rules

- Dollars: no space — $17M, $1.05B, $358M
- Billions: 2 decimals ($1.05B). Millions: whole number if >= $10M ($358M), 1 decimal if < $10M ($4.2M)
- Percentages: 1 decimal if < 10% (7.0%), no decimal if >= 10% (24%)
- Basis points: space before (30 bps, +4 bps)
- Actives: 1 decimal (58.5M)
- Always include sign (+/-) on YoY and delta values
- "above"/"below" based on sign of delta vs forecast

---

## Step 5 — Save the file

Write to:
```
~/Desktop/Nick's Cursor/Weekly Reporting/weekly_summary_YYYY-MM-DD.md
```

Use today's date for the filename.

---

## Step 6 — Report back

Tell Nick:
- File path
- How many metrics were populated vs. any `[DATA MISSING]` flags
- Whether the Cash digest was found (and from what date/message)
- Any notable signals (e.g., a metric flipped from green to red)
